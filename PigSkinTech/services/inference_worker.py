"""One-shot inference worker, executed with the training environment's Python."""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def run_checkpoint_inference(image_path, checkpoint_path, config_path=None):
    import torch
    from torch import nn
    from torchvision import models, transforms
    from PIL import Image

    checkpoint_path = Path(checkpoint_path)
    config_path = Path(config_path) if config_path else checkpoint_path.parent / "config.json"
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
    with Image.open(image_path) as source:
        tensor = transform(source.convert("RGB")).unsqueeze(0).to(device)

    t0 = time.perf_counter()
    with torch.inference_mode():
        probabilities = torch.softmax(model(tensor)[0], dim=0).cpu().tolist()
    inference_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    indices = sorted(range(len(classes)), key=lambda index: probabilities[index], reverse=True)
    all_scores = [
        {"label": classes[index], "confidence": float(probabilities[index])}
        for index in indices
    ]
    scores = all_scores[:5]
    return {
        "mode": "ai",
        "label": scores[0]["label"],
        "confidence": scores[0]["confidence"],
        "scores": scores,
        "top3": scores[:3],
        "all_scores": all_scores,
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
