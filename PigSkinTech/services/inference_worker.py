"""One-shot inference worker, executed with the training environment's Python."""
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_IMNET_PIG_INDICES = (341, 342, 343)
_CLOSEUP_SKIN_SAFE_IMNET_LABELS = frozenset({
    "hog", "wild boar", "warthog", "axolotl", "bolete", "mushroom",
    "sea cucumber", "sea urchin", "stinkhorn", "platypus", "band aid",
    "meat loaf", "earthstar", "coral fungus", "hen-of-the-woods",
    "gyromitra", "agaric", "hippopotamus", "rhinoceros",
})


def run_checkpoint_inference(image_path, checkpoint_path, config_path=None):
    import torch
    from torch import nn
    from torchvision import models, transforms
    from PIL import Image, ImageOps

    checkpoint_path = Path(checkpoint_path)
    config_path = Path(config_path) if config_path else checkpoint_path.parent / "config.json"
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Thiếu file trọng số checkpoint: {checkpoint_path}")
    if not config_path.is_file():
        raise FileNotFoundError(f"Thiếu file cấu hình config.json: {config_path}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    model_name = checkpoint.get("model", config.get("model"))
    classes = checkpoint.get("classes", config.get("classes", []))
    if classes != config.get("classes"):
        raise ValueError("Danh sách lớp trong checkpoint không khớp config.json.")
    if checkpoint.get("label_mode", config.get("label_mode")) != "single":
        raise ValueError("App hiện chỉ hỗ trợ checkpoint phân loại đơn nhãn.")

    constructors = {
        "mobilenet_v2": models.mobilenet_v2,
        "mobilenet_v3_large": models.mobilenet_v3_large,
        "efficientnet_b0": models.efficientnet_b0,
    }
    if model_name not in constructors:
        raise ValueError(f"Kiến trúc checkpoint chưa được hỗ trợ: {model_name}")
    model = constructors[model_name](weights=None)
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

    t0 = time.perf_counter()
    with Image.open(image_path) as source:
        rgb = ImageOps.exif_transpose(source).convert("RGB")
        # Layer 0: Image texture/noise/screenshot check
        arr = transforms.PILToTensor()(rgb.resize((224, 224))).float()
        spatial_std = float(arr.std(dim=(1, 2)).mean().item())
        dx = (arr[:, :, 1:] - arr[:, :, :-1]).abs()
        dy = (arr[:, 1:, :] - arr[:, :-1, :]).abs()
        hf = float(((dx.mean() + dy.mean()) / 2.0).item())
        flat_ratio = float((((dx.max(dim=0).values <= 1.0).float().mean() + (dy.max(dim=0).values <= 1.0).float().mean()) / 2.0).item())
        gray = arr.mean(dim=0)
        g1, g2 = gray[:, :-1].reshape(-1), gray[:, 1:].reshape(-1)
        s1, s2 = g1.std(), g2.std()
        autocorr = float((((g1 - g1.mean()) * (g2 - g2.mean())).mean() / (s1 * s2)).item()) if (s1 > 1e-3 and s2 > 1e-3) else 0.0
        if spatial_std < 10.0 or hf < 1.2 or autocorr < 0.45 or hf > 32.0 or flat_ratio > 0.82:
            return {
                "mode": "invalid_image",
                "ok": False,
                "is_valid_pig": False,
                "label": None,
                "confidence": 0.0,
                "scores": [],
                "validation_reason": "Ảnh màu trơn, nhiễu hạt hoặc ảnh đồ họa/màn hình không hợp lệ.",
                "message": "Ảnh tải lên không phải là heo hoặc vùng da heo hợp lệ. Vui lòng chụp rõ vùng da heo cần kiểm tra.",
            }
        cpu_tensor = transform(rgb).unsqueeze(0)

    with torch.inference_mode():
        try:
            tensor = cpu_tensor.to(device)
            probabilities = torch.softmax(model(tensor)[0], dim=0).cpu().tolist()
        except RuntimeError:
            device = torch.device("cpu")
            model.to(device).eval()
            probabilities = torch.softmax(model(cpu_tensor)[0], dim=0).cpu().tolist()
    inference_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    indices = sorted(range(len(classes)), key=lambda index: probabilities[index], reverse=True)
    all_scores = [
        {"label": classes[index], "confidence": float(probabilities[index])}
        for index in indices
    ]
    scores = all_scores[:5]

    max_prob = float(probabilities[indices[0]])
    second_prob = float(probabilities[indices[1]]) if len(indices) > 1 else 0.0
    margin = max_prob - second_prob
    entropy = float(-sum(p * math.log(max(p, 1e-12)) for p in probabilities))
    norm_entropy = entropy / math.log(max(2, len(classes)))
    if max_prob < 0.45 or norm_entropy > 0.72 or (max_prob < 0.55 and margin < 0.12 and entropy > 1.35):
        return {
            "mode": "invalid_image",
            "ok": False,
            "is_valid_pig": False,
            "label": None,
            "confidence": max_prob,
            "scores": scores,
            "top3": scores[:3],
            "entropy": round(entropy, 4),
            "validation_reason": f"Độ tự tin thấp ({max_prob * 100:.1f}%) hoặc Entropy cao ({entropy:.2f}).",
            "message": "Ảnh tải lên không phải là heo hoặc vùng da heo hợp lệ. Vui lòng chụp rõ vùng da heo cần kiểm tra.",
        }

    return {
        "mode": "ai",
        "ok": True,
        "is_valid_pig": True,
        "label": scores[0]["label"],
        "confidence": scores[0]["confidence"],
        "scores": scores,
        "top3": scores[:3],
        "all_scores": all_scores,
        "entropy": round(entropy, 4),
        "inference_ms": inference_ms,
        "architecture": model_name,
        "model_info": (
            f"{model_name} | {checkpoint_path.parent.name} | {device.type.upper()} | {inference_ms}ms"
        ),
        "best_epoch": checkpoint.get("best_epoch"),
        "checkpoint_modified": datetime.fromtimestamp(
            checkpoint_path.stat().st_mtime, timezone.utc
        ).isoformat(timespec="seconds"),
        "image_size": image_size,
        "class_count": len(config.get("classes", [])),
    }


def main(image_path, checkpoint_path, config_path=None):
    # Support both (IMAGE, CHECKPOINT, [CONFIG]) and legacy (CHECKPOINT, IMAGE) order
    p1, p2 = Path(image_path), Path(checkpoint_path)
    if p1.suffix.lower() in (".pt", ".pth", ".onnx") and p2.suffix.lower() not in (".pt", ".pth", ".onnx"):
        checkpoint_path, image_path = p1, p2
    result = run_checkpoint_inference(image_path, checkpoint_path, config_path)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        raise SystemExit("Usage: inference_worker.py IMAGE CHECKPOINT [CONFIG]")
    try:
        main(*sys.argv[1:])
    except Exception as error:
        print(f"Inference failed: {error}", file=sys.stderr)
        raise SystemExit(1)
