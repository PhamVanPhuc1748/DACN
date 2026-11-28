"""Validate images and run predictions with the selected local checkpoint (best_model.pt)."""
from datetime import datetime, timezone
import json
import subprocess
import threading
import time
from pathlib import Path

from PIL import Image, ImageFile, UnidentifiedImageError

ImageFile.LOAD_TRUNCATED_IMAGES = True

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
IMAGE_GATE = ROOT / "services" / "image_gate.py"

_MODEL_CACHE_LOCK = threading.Lock()
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
    config = run["config"]
    paths = [ckpt_path]
    if ckpt_path.name == "ensemble.json":
        manifest = json.loads(ckpt_path.read_text(encoding="utf-8"))
        paths = [(ckpt_path.parent / member).resolve() for member in manifest["members"]]
        if len(paths) != 2 or len(set(paths)) != 2 or any(path.suffix != ".pt" for path in paths):
            raise ValueError("E07-A requires two distinct PyTorch checkpoints.")
    cache_key = repr([(str(path), path.stat().st_mtime_ns) for path in [ckpt_path, *paths]])

    with _MODEL_CACHE_LOCK:
        entry = _MODEL_RUNTIME_CACHE.get(cache_key)
        if entry is None:
            constructors = {
                "mobilenet_v2": models.mobilenet_v2,
                "mobilenet_v3_large": models.mobilenet_v3_large,
                "efficientnet_b0": models.efficientnet_b0,
            }
            classes = config.get("classes", [])
            model_code = config.get("model", "mobilenet_v2")
            if model_code not in constructors:
                return None
            image_size = int(config.get("image_size", 224))
            normalization = config.get("normalization", {})
            mean = normalization.get("mean", [0.485, 0.456, 0.406])
            std = normalization.get("std", [0.229, 0.224, 0.225])
            members = []
            for path in paths:
                checkpoint = torch.load(path, map_location="cpu", weights_only=True)
                if (
                    not classes
                    or checkpoint.get("classes", classes) != classes
                    or checkpoint.get("model", model_code) != model_code
                    or checkpoint.get("label_mode", config.get("label_mode")) != "single"
                    or int(checkpoint.get("image_size", image_size)) != image_size
                    or tuple(checkpoint.get("normalization", {}).get("mean", mean)) != tuple(mean)
                    or tuple(checkpoint.get("normalization", {}).get("std", std)) != tuple(std)
                ):
                    raise ValueError(f"Checkpoint incompatible with run configuration: {path.name}")
                model = constructors[model_code](weights=None)
                model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(classes))
                state_dict = checkpoint.get("state_dict") or checkpoint.get("model_state_dict") or checkpoint
                model.load_state_dict(state_dict, strict=True)
                members.append(model.eval())

            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            try:
                for model in members:
                    model.to(device)
            except RuntimeError:
                if device.type == "cpu":
                    raise
                device = torch.device("cpu")
                for model in members:
                    model.to(device)

            transform = transforms.Compose([
                transforms.Resize((image_size, image_size)),
                transforms.ToTensor(),
                transforms.Normalize(mean, std),
            ])
            entry = {
                "members": members,
                "device": device,
                "transform": transform,
                "classes": list(classes),
                "model_code": model_code,
                "image_size": image_size,
                "best_epoch": checkpoint.get("best_epoch") if len(members) == 1 else None,
            }
            _MODEL_RUNTIME_CACHE[cache_key] = entry

    with Image.open(image_path) as source:
        cpu_tensor = entry["transform"](source.convert("RGB")).unsqueeze(0)

    t0 = time.perf_counter()
    with _MODEL_CACHE_LOCK, torch.inference_mode():
        device = entry["device"]
        members = entry["members"]
        try:
            tensor = cpu_tensor.to(device)
            distributions = [torch.softmax(model(tensor)[0], dim=0) for model in members]
        except RuntimeError:
            if device.type == "cpu":
                raise
            entry["device"] = torch.device("cpu")
            distributions = [torch.softmax(model.cpu()(cpu_tensor)[0], dim=0) for model in members]
        probabilities = torch.stack(distributions).mean(dim=0).cpu().tolist()
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
    arch_label = run.get("model_label") or APP_MODEL_NAMES.get(model_code, model_code)
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
    python = torch_python()
    if not python:
        raise RuntimeError("Không tìm thấy môi trường Python để kiểm tra ảnh da heo.")
    gate = subprocess.run(
        [str(python), str(IMAGE_GATE), "check", str(info["path"])],
        cwd=ROOT.parent, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=180,
    )
    if gate.returncode:
        raise RuntimeError(gate.stderr.strip()[-1000:] or "Không thể kiểm tra ảnh da heo.")
    try:
        gate_result = json.loads(gate.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Bộ lọc ảnh trả về kết quả không hợp lệ.") from exc
    if not gate_result.get("accepted"):
        raise ValueError("Ảnh không đủ dấu hiệu là da heo. Hãy chọn ảnh rõ vùng da heo để phân tích.")
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
    arch_label = run.get("model_label") or APP_MODEL_NAMES.get(model_code, model_code)

    result["ok"] = True
    result["display_label"] = display_class(result["label"])
    result["danger_level"] = cls_meta.get("danger_level", "Trung bình")
    result["recommendation"] = cls_meta.get("treatment", "")
    result["prevention_ref"] = cls_meta.get("prevention", "")
    result["symptoms_ref"] = cls_meta.get("symptoms", "")
    result["disease"] = {
        "code": result["label"],
        "name_vi": result["display_label"],
        "danger_level": result["danger_level"],
        "symptoms": result["symptoms_ref"],
        "drugs": result["recommendation"],
        "isolation": result["prevention_ref"],
    }
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
