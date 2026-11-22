"""Validate images, run Non-Pig/OOD Gatekeeper, and execute PyTorch inference with best_model.pt."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import gc
from io import BytesIO
import json
import math
import os
import subprocess
import threading
import time
from pathlib import Path

from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError

from services.config_store import read_settings
from services.project_data import (
    APP_MODEL_NAMES,
    active_run,
    available_model_runs,
    display_class,
    get_class_info,
    torch_python,
)

# Keep strict pixel decoding in inspect_image so corrupted/truncated files are caught
ImageFile.LOAD_TRUNCATED_IMAGES = False

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 15 * 1024 * 1024  # 15 MB limit
WORKER = ROOT / "services" / "inference_worker.py"

INVALID_PIG_USER_MESSAGE = (
    "Ảnh tải lên không phải là heo hoặc vùng da heo hợp lệ. "
    "Vui lòng chụp rõ vùng da heo cần kiểm tra."
)

# ImageNet indices for pig/swine classes: 341=hog, 342=wild boar, 343=warthog
_IMNET_PIG_INDICES = (341, 342, 343)

# Organic/skin-like ImageNet classes that close-up pig skin lesion photos may match at low confidence
_CLOSEUP_SKIN_SAFE_IMNET_LABELS = frozenset({
    "hog",
    "wild boar",
    "warthog",
    "axolotl",
    "bolete",
    "mushroom",
    "sea cucumber",
    "sea urchin",
    "stinkhorn",
    "platypus",
    "band aid",
    "meat loaf",
    "earthstar",
    "coral fungus",
    "hen-of-the-woods",
    "gyromitra",
    "agaric",
    "hippopotamus",
    "rhinoceros",
})

_MODEL_CACHE_LOCK = threading.Lock()
_MODEL_RUNTIME_CACHE: dict[str, dict] = {}
_MAX_CACHED_MODELS = 2
_OOD_CACHE_LOCK = threading.Lock()
_OOD_GATEKEEPER_CACHE: dict[str, object] = {}


def clear_model_cache(keep_key: str | None = None) -> None:
    """Release cached PyTorch models from RAM/VRAM when switching active checkpoints."""
    with _MODEL_CACHE_LOCK:
        keys_to_drop = [k for k in list(_MODEL_RUNTIME_CACHE.keys()) if k != keep_key]
        for k in keys_to_drop:
            _MODEL_RUNTIME_CACHE.pop(k, None)
    if keys_to_drop:
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass


def ensure_cached_model(run: dict) -> dict | None:
    """Load and cache a PyTorch checkpoint safely (max 2 models in RAM/VRAM for Dual-Model Benchmark)."""
    try:
        import torch
        from torch import nn
        from torchvision import models, transforms
    except ImportError:
        return None

    ckpt_path = Path(run["checkpoint"]).resolve()
    if not ckpt_path.is_file():
        raise FileNotFoundError(f"Thiếu file trọng số mô hình: {ckpt_path}")
    cache_key = str(ckpt_path)

    with _MODEL_CACHE_LOCK:
        entry = _MODEL_RUNTIME_CACHE.get(cache_key)
        if entry is not None:
            return entry

        # Evict oldest cached model when exceeding _MAX_CACHED_MODELS to keep RAM/VRAM bounded
        while len(_MODEL_RUNTIME_CACHE) >= _MAX_CACHED_MODELS:
            oldest_key = next(iter(_MODEL_RUNTIME_CACHE))
            _MODEL_RUNTIME_CACHE.pop(oldest_key, None)
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

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
        try:
            model.to(device).eval()
        except RuntimeError:
            device = torch.device("cpu")
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
            "ckpt_path": ckpt_path,
            "best_epoch": checkpoint.get("best_epoch", run.get("metrics", {}).get("best_epoch")),
        }
        _MODEL_RUNTIME_CACHE[cache_key] = entry
        return entry


def _current_run(run_name: str | None = None):
    return active_run(run_name)


def inspect_image(path):
    p = Path(path)
    if not p.is_file() or p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
        raise ValueError("Chọn ảnh JPG, PNG hoặc WEBP hợp lệ.")
    count = p.stat().st_size
    if not 0 < count <= MAX_BYTES:
        raise ValueError("Ảnh phải có dung lượng tối đa 15 MB.")
    try:
        with Image.open(p) as im:
            if im.format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError("Định dạng ảnh không hỗ trợ hoặc file đã bị đổi đuôi giả mạo.")
            width, height = im.size
            if width <= 0 or height <= 0:
                raise ValueError("Kích thước ảnh không hợp lệ.")
            im.verify()
        # Second pass: decode pixels completely to catch corrupted/truncated payloads and verify RGB conversion
        with Image.open(p) as im2:
            im2.load()
            rgb = ImageOps.exif_transpose(im2).convert("RGB")
            width, height = rgb.size
    except ValueError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError) as ex:
        raise ValueError("Không thể mở ảnh; file có thể đã bị hỏng hoặc không phải tệp ảnh hợp lệ.") from ex
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


def _load_imnet_gatekeeper():
    """Load a cached lightweight ImageNet pretrained classifier (offline-first, thread-safe)."""
    with _OOD_CACHE_LOCK:
        if "ready" in _OOD_GATEKEEPER_CACHE:
            return _OOD_GATEKEEPER_CACHE.get("entry")
        try:
            import torch
            from torchvision import models

            ckpt_dir = Path(torch.hub.get_dir()) / "checkpoints"
            candidates = [
                ("mobilenet_v3_large", models.mobilenet_v3_large, models.MobileNet_V3_Large_Weights.DEFAULT, "mobilenet_v3_large"),
                ("efficientnet_b0", models.efficientnet_b0, models.EfficientNet_B0_Weights.DEFAULT, "efficientnet_b0"),
                ("mobilenet_v2", models.mobilenet_v2, models.MobileNet_V2_Weights.DEFAULT, "mobilenet_v2"),
            ]
            # Prefer a checkpoint already cached locally to stay instant and offline-safe
            chosen = None
            if ckpt_dir.is_dir():
                cached_names = [f.name.lower() for f in ckpt_dir.iterdir() if f.is_file()]
                for cand in candidates:
                    if any(cand[3] in fn for fn in cached_names):
                        chosen = cand
                        break
            if chosen is None:
                chosen = candidates[2]  # mobilenet_v2 lightest fallback

            _, ctor, weights, _ = chosen
            model = ctor(weights=weights)
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            try:
                model.to(device).eval()
            except RuntimeError:
                device = torch.device("cpu")
                model.to(device).eval()

            entry = {
                "model": model,
                "device": device,
                "transform": weights.transforms(),
                "categories": list(weights.meta.get("categories") or []),
            }
            _OOD_GATEKEEPER_CACHE["entry"] = entry
        except Exception:
            _OOD_GATEKEEPER_CACHE["entry"] = None
        _OOD_GATEKEEPER_CACHE["ready"] = True
        return _OOD_GATEKEEPER_CACHE.get("entry")


def _gemini_vision_check_pig(rgb_image: Image.Image) -> bool | None:
    """Optional fast Gemini Vision check when GEMINI_API_KEY is configured and ImageNet is uncertain."""
    try:
        cfg = read_settings()
        api_key = (cfg.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
        if not api_key:
            return None
        import requests

        thumb = rgb_image.copy()
        thumb.thumbnail((256, 256))
        buf = BytesIO()
        thumb.save(buf, format="JPEG", quality=75)
        b64_img = base64.b64encode(buf.getvalue()).decode("ascii")
        model_name = (cfg.get("GEMINI_MODEL") or "gemini-2.5-flash").strip()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                "Does this image show a pig/swine or a close-up of animal/pig skin or skin lesion? "
                                "Answer strictly with YES or NO."
                            )
                        },
                        {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}},
                    ],
                }
            ],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 8},
        }
        resp = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            timeout=6,
        )
        if resp.status_code == 200:
            data = resp.json()
            cands = data.get("candidates") or []
            if cands:
                parts = ((cands[0].get("content") or {}).get("parts")) or []
                txt = "".join(str(p.get("text") or "") for p in parts).strip().upper()
                if txt.startswith("NO"):
                    return False
                if txt.startswith("YES"):
                    return True
    except Exception:
        pass
    return None


def _check_image_signal_and_ood(rgb_image: Image.Image) -> dict:
    """
    Layer 0 (Image texture/noise/screenshot check) + Layer 1 (ImageNet Pretrained / Gemini Vision Gatekeeper).
    Carefully preserves genuine close-up pig skin photos while rejecting blank, noisy, screenshot, or clear non-pig objects.
    """
    import torch
    from torchvision import transforms

    resized = rgb_image.resize((224, 224))
    arr = transforms.PILToTensor()(resized).float()  # [3, 224, 224], values 0..255
    spatial_std = float(arr.std(dim=(1, 2)).mean().item())
    dx = (arr[:, :, 1:] - arr[:, :, :-1]).abs()
    dy = (arr[:, 1:, :] - arr[:, :-1, :]).abs()
    hf = float(((dx.mean() + dy.mean()) / 2.0).item())
    flat_ratio = float(
        (((dx.max(dim=0).values <= 1.0).float().mean() + (dy.max(dim=0).values <= 1.0).float().mean()) / 2.0).item()
    )
    gray = arr.mean(dim=0)
    g1, g2 = gray[:, :-1].reshape(-1), gray[:, 1:].reshape(-1)
    s1, s2 = g1.std(), g2.std()
    autocorr = float((((g1 - g1.mean()) * (g2 - g2.mean())).mean() / (s1 * s2)).item()) if (s1 > 1e-3 and s2 > 1e-3) else 0.0

    # Layer 0: Reject solid/blank, synthetic random noise, and flat UI/screenshot images
    if spatial_std < 10.0 or hf < 1.2:
        return {
            "is_valid": False,
            "pig_imnet_prob": 0.0,
            "imnet_top1": "",
            "reason": "Ảnh màu trơn hoặc quá mờ, không có chi tiết bề mặt da heo.",
        }
    if autocorr < 0.45 or hf > 32.0:
        return {
            "is_valid": False,
            "pig_imnet_prob": 0.0,
            "imnet_top1": "",
            "reason": "Ảnh nhiễu hạt hoặc ảnh giả lập, không phải ảnh chụp thực tế vùng da heo.",
        }
    if flat_ratio > 0.82:
        return {
            "is_valid": False,
            "pig_imnet_prob": 0.0,
            "imnet_top1": "",
            "reason": "Ảnh có quá nhiều vùng phẳng đồng màu (ảnh chụp màn hình, đồ họa hoặc văn bản), không phải vùng da heo.",
        }

    # Layer 1: Pretrained ImageNet Gatekeeper
    pig_prob = 0.0
    imnet_top1 = ""
    gate = _load_imnet_gatekeeper()
    if gate is not None:
        try:
            cpu_x = gate["transform"](rgb_image).unsqueeze(0)
            with torch.inference_mode():
                try:
                    probs = torch.softmax(gate["model"](cpu_x.to(gate["device"]))[0], dim=0).cpu()
                except RuntimeError:
                    gate["device"] = torch.device("cpu")
                    gate["model"].to(gate["device"]).eval()
                    probs = torch.softmax(gate["model"](cpu_x)[0], dim=0).cpu()
            cats = gate["categories"]
            pig_prob = float(sum(float(probs[i]) for i in _IMNET_PIG_INDICES if i < len(probs)))
            top3_v, top3_i = torch.topk(probs, 3)
            top3_items = [
                (cats[int(idx)] if int(idx) < len(cats) else str(int(idx)), float(val))
                for val, idx in zip(top3_v, top3_i)
            ]
            top1_label, top1_prob = top3_items[0]
            imnet_top1 = f"{top1_label} ({top1_prob * 100:.1f}%)"

            if pig_prob >= 0.10:
                return {"is_valid": True, "pig_imnet_prob": pig_prob, "imnet_top1": imnet_top1, "reason": ""}

            non_pig_top3_prob = sum(
                p for lbl, p in top3_items if lbl not in _CLOSEUP_SKIN_SAFE_IMNET_LABELS
            )
            if (top1_label not in _CLOSEUP_SKIN_SAFE_IMNET_LABELS and top1_prob >= 0.35) or (
                top1_label not in _CLOSEUP_SKIN_SAFE_IMNET_LABELS and non_pig_top3_prob >= 0.52
            ):
                return {
                    "is_valid": False,
                    "pig_imnet_prob": pig_prob,
                    "imnet_top1": imnet_top1,
                    "reason": f"Đối tượng trong ảnh được nhận diện không phải heo ({top1_label} • {top1_prob * 100:.0f}%).",
                }
        except Exception:
            pass

    # Optional Gemini Vision check only when ImageNet did not see a pig and GEMINI_API_KEY is set
    if pig_prob < 0.08:
        gem_ok = _gemini_vision_check_pig(rgb_image)
        if gem_ok is False:
            return {
                "is_valid": False,
                "pig_imnet_prob": pig_prob,
                "imnet_top1": imnet_top1,
                "reason": "Bộ lọc thị giác AI xác định ảnh không chứa heo hoặc vùng da heo.",
            }

    return {"is_valid": True, "pig_imnet_prob": pig_prob, "imnet_top1": imnet_top1, "reason": ""}


def _evaluate_softmax_ood(probabilities: list[float], indices: list[int], pig_imnet_prob: float = 0.0) -> tuple[bool, float, float, str]:
    """
    Layer 2: Softmax Confidence & Shannon Entropy gatekeeper on the 10-class pig skin classifier.
    Returns (is_valid_pig, entropy, norm_entropy, reason).
    """
    n_cls = max(2, len(probabilities))
    max_prob = float(probabilities[indices[0]]) if indices else 0.0
    second_prob = float(probabilities[indices[1]]) if len(indices) > 1 else 0.0
    margin = max_prob - second_prob
    entropy = float(-sum(p * math.log(max(p, 1e-12)) for p in probabilities))
    norm_entropy = entropy / math.log(n_cls)

    if max_prob < 0.45:
        return (
            False,
            entropy,
            norm_entropy,
            f"Độ tự tin dự đoán quá thấp ({max_prob * 100:.1f}% < 45.0%). Ảnh không rõ vùng da heo.",
        )
    if norm_entropy > 0.72:
        return (
            False,
            entropy,
            norm_entropy,
            f"Phân bố xác suất quá phân tán (Entropy={entropy:.2f}), không thể xác định bệnh lý da heo.",
        )
    if max_prob < 0.55 and margin < 0.12 and entropy > 1.35 and pig_imnet_prob < 0.15:
        return (
            False,
            entropy,
            norm_entropy,
            f"Chênh lệch Top-1/Top-2 quá nhỏ ({margin * 100:.1f}%) kèm độ tự tin thấp ({max_prob * 100:.1f}%).",
        )
    return True, entropy, norm_entropy, ""


def _build_invalid_pig_result(
    reason: str,
    info: dict,
    run: dict,
    inference_ms: float = 0.0,
    scores: list[dict] | None = None,
    entropy: float = 0.0,
    imnet_top1: str = "",
) -> dict:
    model_code = run.get("model") or run.get("config", {}).get("model", "mobilenet_v2")
    arch_label = APP_MODEL_NAMES.get(model_code, model_code)
    return {
        "mode": "invalid_image",
        "ok": False,
        "is_valid_pig": False,
        "label": None,
        "display_label": "Không thể xác định / Ảnh không rõ vùng da heo",
        "confidence": float(scores[0]["confidence"]) if scores else 0.0,
        "scores": scores or [],
        "top3": (scores or [])[:3],
        "all_scores": scores or [],
        "entropy": round(entropy, 4),
        "imnet_top1": imnet_top1,
        "validation_reason": reason,
        "inference_ms": inference_ms,
        "architecture": arch_label,
        "model": model_code,
        "model_label": arch_label,
        "run_name": run["name"],
        "model_info": f"{arch_label} | {run['name']} | REJECTED",
        "info": info,
        "message": INVALID_PIG_USER_MESSAGE,
    }


def _predict_inprocess(image_path: str | Path, run: dict, info: dict) -> dict | None:
    """Run real PyTorch forward pass in-process with OOD gatekeeper and cached weights."""
    try:
        import torch
    except ImportError:
        return None

    entry = ensure_cached_model(run)
    if entry is None:
        return None
    ckpt_path = entry["ckpt_path"]

    t0 = time.perf_counter()
    with Image.open(image_path) as source:
        rgb_image = ImageOps.exif_transpose(source).convert("RGB")
        # Layer 0 & Layer 1: Non-Pig / OOD Gatekeeper
        ood_check = _check_image_signal_and_ood(rgb_image)
        if not ood_check["is_valid"]:
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return _build_invalid_pig_result(
                reason=ood_check["reason"],
                info=info,
                run=run,
                inference_ms=elapsed_ms,
                imnet_top1=ood_check.get("imnet_top1", ""),
            )
        cpu_tensor = entry["transform"](rgb_image).unsqueeze(0)

    with torch.inference_mode():
        try:
            tensor = cpu_tensor.to(entry["device"])
            probabilities = torch.softmax(entry["model"](tensor)[0], dim=0).cpu().tolist()
        except RuntimeError:
            entry["device"] = torch.device("cpu")
            entry["model"].to(entry["device"]).eval()
            probabilities = torch.softmax(entry["model"](cpu_tensor)[0], dim=0).cpu().tolist()
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

    # Layer 2: Softmax Confidence & Entropy Gatekeeper
    valid_softmax, entropy, norm_entropy, softmax_reason = _evaluate_softmax_ood(
        probabilities, indices, pig_imnet_prob=ood_check.get("pig_imnet_prob", 0.0)
    )
    if not valid_softmax:
        return _build_invalid_pig_result(
            reason=softmax_reason,
            info=info,
            run=run,
            inference_ms=inference_ms,
            scores=scores,
            entropy=entropy,
            imnet_top1=ood_check.get("imnet_top1", ""),
        )

    model_code = entry["model_code"]
    arch_label = APP_MODEL_NAMES.get(model_code, model_code)
    dev_label = entry["device"].type.upper()

    return {
        "mode": "ai",
        "is_valid_pig": True,
        "validation_reason": "",
        "entropy": round(entropy, 4),
        "norm_entropy": round(norm_entropy, 4),
        "imnet_top1": ood_check.get("imnet_top1", ""),
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
    """Run the matching model and OOD gatekeeper and return validated Softmax predictions."""
    info = inspect_image(path)
    run = _current_run(run_name)
    if not run:
        return {
            "mode": "unavailable",
            "ok": False,
            "is_valid_pig": False,
            "label": None,
            "confidence": None,
            "scores": [],
            "message": "Không tìm thấy checkpoint (best_model.pt) và báo cáo train (config.json) hoàn chỉnh trong models/runs/.",
        }

    result = _predict_inprocess(info["path"], run, info)
    if result is None:
        python = torch_python()
        if not python:
            raise RuntimeError("Không tìm thấy Python có PyTorch và TorchVision.")
        command = [
            str(python),
            str(WORKER),
            str(info["path"]),
            str(run["checkpoint"]),
            str(run["config_path"]),
        ]
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
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

    if result.get("mode") == "invalid_image" or result.get("is_valid_pig") is False:
        result.setdefault("ok", False)
        result["is_valid_pig"] = False
        result["mode"] = "invalid_image"
        result.setdefault("display_label", "Không thể xác định / Ảnh không rõ vùng da heo")
        result.setdefault("message", INVALID_PIG_USER_MESSAGE)
        result.setdefault("info", info)
        return result

    if result.get("mode") != "ai" or not result.get("scores"):
        raise RuntimeError(result.get("message", "Mô hình không trả về dự đoán."))

    for sc in result["scores"]:
        sc.setdefault("display_label", display_class(sc["label"]))

    cls_meta = get_class_info(result["label"])
    model_code = run.get("model") or run.get("config", {}).get("model", "mobilenet_v2")
    arch_label = APP_MODEL_NAMES.get(model_code, model_code)

    result["ok"] = True
    result["is_valid_pig"] = True
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
                "ok": False,
                "is_valid_pig": False,
                "label": None,
                "display_label": "Lỗi đọc/xử lý ảnh",
                "confidence": 0.0,
                "scores": [],
                "info": {"name": Path(p).name, "path": str(p)},
                "message": str(exc),
            })
    return results
