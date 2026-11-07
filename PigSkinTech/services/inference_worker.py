"""One-shot inference worker, executed with the training environment's Python."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main(image_path, checkpoint_path, config_path):
    import torch
    from torch import nn
    from torchvision import models, transforms
    from PIL import Image

    checkpoint_path = Path(checkpoint_path)
    config_path = Path(config_path)
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
    model.load_state_dict(checkpoint["state_dict"], strict=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device).eval()
    image_size = int(checkpoint.get("image_size", config.get("image_size", 224)))
    normalization = checkpoint.get("normalization", config.get("normalization", {}))
    mean = normalization.get("mean", [0.485, 0.456, 0.406])
    std = normalization.get("std", [0.229, 0.224, 0.225])
    # Match the training pipeline: resize directly to the configured square size.
    transform = transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])
    with Image.open(image_path) as source:
        tensor = transform(source.convert("RGB")).unsqueeze(0).to(device)
    with torch.inference_mode():
        probabilities = torch.softmax(model(tensor)[0], dim=0).cpu().tolist()
    indices = sorted(range(len(classes)), key=lambda index: probabilities[index], reverse=True)[:5]
    scores = [
        {"label": classes[index], "confidence": float(probabilities[index])}
        for index in indices
    ]
    run_config = json.loads(config_path.read_text(encoding="utf-8"))
    result = {
        "mode": "ai",
        "label": scores[0]["label"],
        "confidence": scores[0]["confidence"],
        "scores": scores,
        "model_info": (
            f"{model_name} | {checkpoint_path.parent.name} | {device.type.upper()}"
        ),
        "best_epoch": checkpoint.get("best_epoch"),
        "checkpoint_modified": datetime.fromtimestamp(
            checkpoint_path.stat().st_mtime, timezone.utc
        ).isoformat(timespec="seconds"),
        "image_size": image_size,
        "class_count": len(run_config.get("classes", [])),
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: inference_worker.py IMAGE CHECKPOINT CONFIG")
    try:
        main(*sys.argv[1:])
    except Exception as error:
        print(f"Inference failed: {error}", file=sys.stderr)
        raise SystemExit(1)
