"""Validate images and run predictions with the selected local checkpoint (best_model.pt)."""
from datetime import datetime, timezone
import json
import subprocess
import time
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from services.project_data import (
    APP_MODEL_NAMES,
    active_run,
    available_model_runs,
    display_class,
    get_class_info,
    torch_python,
)


ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 10 * 1024 * 1024
WORKER = ROOT / "services" / "inference_worker.py"

_MODEL_RUNTIME_CACHE: dict[str, dict] = {}


def _current_run(run_name: str | None = None):
    return active_run(run_name)


def inspect_image(path):
    p = Path(path)
    if not p.is_file() or p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
        raise ValueError("Chọn ảnh JPG, PNG hoặc WEBP hợp lệ.")
    count = p.stat().st_size
    if not 0 < count <= MAX_BYTES:
        raise ValueError("Ảnh phải có dung lượng tối đa 10 MB.")
    try:
        with Image.open(p) as im:
            if im.format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError("Định dạng ảnh không hỗ trợ.")
            width, height = im.size
            im.verify()
    except (UnidentifiedImageError, OSError) as ex:
        raise ValueError("Không thể mở ảnh; file có thể đã bị hỏng.") from ex
    return {"name": p.name, "path": str(p), "bytes": count, "width": width, "height": height}


def labels(run_name: str | None = None):
    run = _current_run(run_name)
    if not run:
        raise FileNotFoundError("Chưa tìm thấy lần train có checkpoint và báo cáo đầy đủ.")
    names = run["config"].get("classes", [])
    if not names or not all(isinstance(name, str) and name for name in names):
        raise ValueError("config.json của lần train không có danh sách lớp hợp lệ.")
    return names


def model_ready(run_name: str | None = None):
    run = _current_run(run_name)
    return bool(run and run["checkpoint"].is_file() and run["config"].get("classes"))


def model_status(run_name: str | None = None):
    run = _current_run(run_name)
    python = torch_python()
    return {
        "ready": model_ready(run_name),
        "run": run,
        "runs": available_model_runs(),
        "python": python,
        "runtime_ready": bool(python),
    }


def _predict_inprocess(image_path: str | Path, run: dict) -> dict | None:
    """Run real PyTorch forward pass in-process with cached model weights to avoid subprocess cold-start."""
    try:
        import torch
        from torch import nn
        from torchvision import models, transforms
    except ImportError:
        return None

    ckpt_path = Path(run["checkpoint"]).resolve()
    cache_key = str(ckpt_path)
    entry = _MODEL_RUNTIME_CACHE.get(cache_key)

    if entry is None:
        config = run["config"]
        checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=True)
        model_code = checkpoint.get("model", config.get("model", "mobilenet_v2"))
        classes = checkpoint.get("classes", config.get("classes", []))
        constructors = {
            "mobilenet_v2": models.mobilenet_v2,
            "mobilenet_v3_large": models.mobilenet_v3_large,
            "efficientnet_b0": models.efficientnet_b0,
        }
        if model_code not in constructors:
            return None
        model = constructors[model_code](weights=None)
        final_layer = model.classifier[-1]
        model.classifier[-1] = nn.Linear(final_layer.in_features, len(classes))
        state_dict = checkpoint.get("state_dict") or checkpoint.get("model_state_dict") or checkpoint
        model.load_state_dict(state_dict, strict=True)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device).eval()

        image_size = int(checkpoint.get("image_size", config.get("image_size", 224)))
        normalization = checkpoint.get("normalization", config.get("normalization", {}))
        mean = normalization.get("mean", [0.485, 0.456, 0.406])
        std = normalization.get("std", [0.229, 0.224, 0.225])
        transform = transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean, std),
        ])
        entry = {
            "model": model,
            "device": device,
            "transform": transform,
            "classes": list(classes),
            "model_code": model_code,
            "image_size": image_size,
            "best_epoch": checkpoint.get("best_epoch", run.get("metrics", {}).get("best_epoch")),
        }
        _MODEL_RUNTIME_CACHE[cache_key] = entry

    with Image.open(image_path) as source:
        tensor = entry["transform"](source.convert("RGB")).unsqueeze(0).to(entry["device"])

    t0 = time.perf_counter()
    with torch.inference_mode():
        probabilities = torch.softmax(entry["model"](tensor)[0], dim=0).cpu().tolist()
    inference_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    classes = entry["classes"]
    indices = sorted(range(len(classes)), key=lambda idx: probabilities[idx], reverse=True)
    all_scores = [
        {
            "label": classes[idx],
            "display_label": display_class(classes[idx]),
            "confidence": float(probabilities[idx]),
        }
        for idx in indices
    ]
    scores = all_scores[:5]
    model_code = entry["model_code"]
    arch_label = APP_MODEL_NAMES.get(model_code, model_code)
    dev_label = entry["device"].type.upper()

    return {
        "mode": "ai",
        "label": scores[0]["label"],
        "confidence": scores[0]["confidence"],
        "scores": scores,
        "top3": scores[:3],
        "all_scores": all_scores,
        "inference_ms": inference_ms,
        "architecture": arch_label,
        "model": model_code,
        "model_label": arch_label,
        "run_name": run["name"],
        "model_info": f"{arch_label} | {run['name']} | {dev_label} | {inference_ms}ms",
        "best_epoch": entry["best_epoch"],
        "checkpoint_modified": datetime.fromtimestamp(
            ckpt_path.stat().st_mtime, timezone.utc
        ).isoformat(timespec="seconds"),
        "image_size": entry["image_size"],
        "class_count": len(classes),
    }


def predict(path, run_name: str | None = None):
    """Run the matching model in the training environment and return 100% real tensor softmax scores."""
    info = inspect_image(path)
    run = _current_run(run_name)
    if not run:
        return {
            "mode": "unavailable",
            "label": None,
            "confidence": None,
            "scores": [],
            "message": "Không tìm thấy checkpoint và báo cáo train hoàn chỉnh.",
        }

    result = _predict_inprocess(info["path"], run)
    if result is None:
        python = torch_python()
        if not python:
            raise RuntimeError(
                "Không tìm thấy Python có PyTorch và TorchVision."
            )
        command = [
            str(python),
            str(WORKER),
            str(info["path"]),
            str(run["checkpoint"]),
            str(run["config_path"]),
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        if completed.returncode:
            message = completed.stderr.strip() or completed.stdout.strip() or "Không thể chạy mô hình."
            raise RuntimeError(message[-1800:])
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Tiến trình mô hình trả về dữ liệu không hợp lệ.") from exc

    if result.get("mode") != "ai" or not result.get("scores"):
        raise RuntimeError(result.get("message", "Mô hình không trả về dự đoán."))

    for sc in result["scores"]:
        sc.setdefault("display_label", display_class(sc["label"]))

    cls_meta = get_class_info(result["label"])
    model_code = run.get("model") or run.get("config", {}).get("model", "mobilenet_v2")
    arch_label = APP_MODEL_NAMES.get(model_code, model_code)

    result["display_label"] = display_class(result["label"])
    result["danger_level"] = cls_meta.get("danger_level", "Trung bình")
    result["recommendation"] = cls_meta.get("treatment", "")
    result["prevention_ref"] = cls_meta.get("prevention", "")
    result["symptoms_ref"] = cls_meta.get("symptoms", "")
    result["info"] = info
    result["run_name"] = run["name"]
    result["model"] = model_code
    result["model_label"] = arch_label
    result.setdefault("architecture", arch_label)
    result.setdefault("top3", result["scores"][:3])
    result["message"] = (
        f"Suy luận thực tế từ mô hình {arch_label} ({run['name']}) • "
        f"Độ trễ: {result.get('inference_ms', 0)} ms"
    )
    return result


def predict_batch(paths: list[str], run_name: str | None = None) -> list[dict]:
    """Run batch inference across multiple image paths."""
    results = []
    for p in paths:
        try:
            results.append(predict(p, run_name=run_name))
        except Exception as exc:
            results.append({
                "mode": "error",
                "label": None,
                "display_label": "Lỗi đọc/xử lý ảnh",
                "confidence": 0.0,
                "scores": [],
                "info": {"name": Path(p).name, "path": str(p)},
                "message": str(exc),
            })
    return results
