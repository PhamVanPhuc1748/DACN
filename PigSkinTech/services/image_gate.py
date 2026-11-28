"""Zero-shot CLIP gate for rejecting images outside pig/skin scope."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import torch
from PIL import Image


MODEL_NAME = "ViT-B-32"
PRETRAINED = "laion2b_s34b_b79k"
POSITIVE_PROMPTS = (
    "a close-up photograph of pig skin",
    "a close-up photo of a pig's skin with a skin condition",
    "a photograph of the skin of a domestic pig",
    "a close-up view of a pig with a visible skin lesion",
    "a veterinary photograph of pig skin",
)
NEGATIVE_PROMPTS = (
    "a photograph of a shoe",
    "a photograph of footwear",
    "a photograph of a human",
    "a photograph of a dog or cat",
    "a photograph of a cow or sheep",
    "a photograph of food",
    "a photograph of a landscape or building",
    "a photograph of a household object",
    "a screenshot, drawing, or document",
)

# Conservative initial thresholds for a trial. Similarity is not probability;
# validate these on a separate set of real pig-skin and out-of-scope photos.
MIN_PIG_SCORE = 0.245
MIN_SCORE_MARGIN = 0.015

_MODEL_CACHE: tuple[object, object, object, torch.device] | None = None


def load_model():
    """Load pretrained CLIP once per process; first use downloads weights."""
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE
    try:
        import open_clip
    except ImportError as exc:
        raise RuntimeError(
            "Thiếu OpenCLIP. Cài bằng: python -m pip install -r PigSkinTech/requirements-clip.txt"
        ) from exc

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, _, preprocess = open_clip.create_model_and_transforms(
        MODEL_NAME, pretrained=PRETRAINED, device=device
    )
    model.eval()
    tokenizer = open_clip.get_tokenizer(MODEL_NAME)
    prompts = POSITIVE_PROMPTS + NEGATIVE_PROMPTS
    with torch.inference_mode():
        text = tokenizer(prompts).to(device)
        text_features = model.encode_text(text).float()
        text_features /= text_features.norm(dim=-1, keepdim=True).clamp_min(1e-12)
        positive = text_features[:len(POSITIVE_PROMPTS)].mean(dim=0)
        negative = text_features[len(POSITIVE_PROMPTS):].mean(dim=0)
        positive /= positive.norm().clamp_min(1e-12)
        negative /= negative.norm().clamp_min(1e-12)
    _MODEL_CACHE = (model, preprocess, (positive, negative), device)
    return _MODEL_CACHE


def check(path: str | Path) -> dict:
    model, preprocess, text_features, device = load_model()
    positive, negative = text_features
    with Image.open(path) as image:
        tensor = preprocess(image.convert("RGB")).unsqueeze(0).to(device)
    with torch.inference_mode():
        image_features = model.encode_image(tensor).float()
        image_features /= image_features.norm(dim=-1, keepdim=True).clamp_min(1e-12)
        pig_score = float((image_features @ positive).item())
        other_score = float((image_features @ negative).item())
    margin = pig_score - other_score
    accepted = pig_score >= MIN_PIG_SCORE and margin >= MIN_SCORE_MARGIN
    return {
        "accepted": accepted,
        "gate": "open_clip_zero_shot",
        "model": f"{MODEL_NAME}:{PRETRAINED}",
        "pig_similarity": round(pig_score, 5),
        "other_similarity": round(other_score, 5),
        "margin": round(margin, 5),
        "thresholds": {"min_pig_similarity": MIN_PIG_SCORE, "min_margin": MIN_SCORE_MARGIN},
        "device": str(device),
    }


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "check":
        raise SystemExit("Usage: image_gate.py check IMAGE")
    try:
        print(json.dumps(check(sys.argv[2]), ensure_ascii=False))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
