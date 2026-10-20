"""Engine suy luận.

Hiện là MOCK có tính tất định (cùng ảnh + cùng model → cùng kết quả) để giao diện chạy được
trước khi ml_workspace/models có trọng số thật.
ponytail: thay thân hàm `predict()` bằng torch/ultralytics khi có file .pt; giữ nguyên format trả về.
"""
import hashlib
import math
import random


def predict(image_bytes: bytes, model: dict, classes: list[dict]) -> dict:
    digest = hashlib.sha256(image_bytes).hexdigest()
    base = random.Random(int(digest[:12], 16))            # chung cho mọi model: "nhãn thật" + vị trí tổn thương
    rng = random.Random(int(digest[:12], 16) ^ (model["id"] * 7919))

    true_idx = base.randrange(len(classes))
    acc = (model.get("metrics") or {}).get("accuracy", 0.9)
    peak = true_idx if rng.random() < acc else rng.randrange(len(classes))   # model đôi khi nhầm
    logits = [rng.gauss(0, 0.8) for _ in classes]
    logits[peak] += rng.uniform(2.0, 4.5)
    exp = [math.exp(x) for x in logits]
    probs = [e / sum(exp) for e in exp]

    order = sorted(range(len(classes)), key=lambda i: -probs[i])
    top = classes[order[0]]
    healthy = top["code"] == "HEALTHY"

    regions = [] if healthy else [
        {"x": base.uniform(0.1, 0.6), "y": base.uniform(0.1, 0.6),
         "w": base.uniform(0.15, 0.35), "h": base.uniform(0.15, 0.35)}
        for _ in range(base.randint(1, 3))
    ]
    for r in regions:
        r["conf"] = round(min(0.99, probs[order[0]] * rng.uniform(0.6, 1.1)), 3)
        r["code"] = top["code"]

    return {
        "engine": "mock",
        "status": "HEALTHY" if healthy else "ABNORMAL",
        "probs": {classes[i]["code"]: round(probs[i], 4) for i in order},
        "top3": [{"code": classes[i]["code"], "name": classes[i]["name"], "prob": round(probs[i], 4)} for i in order[:3]],
        "confidence": round(probs[order[0]], 4),
        "predicted_code": top["code"],
        "inference_ms": round(model["latency_ms"] * rng.uniform(0.92, 1.08), 1),
        # detection → bounding boxes; classification → điểm nóng Grad-CAM
        "boxes": regions if model["task"] == "detection" else [],
        "heatmap": [] if model["task"] == "detection" else
        [{"cx": r["x"] + r["w"] / 2, "cy": r["y"] + r["h"] / 2, "r": max(r["w"], r["h"]) * 0.8,
          "intensity": r["conf"]} for r in regions],
        "sha256": digest,
    }


if __name__ == "__main__":
    cls = [{"code": c, "name": c} for c in ["HEALTHY", "BACT_ERY", "VIRA_FMD"]]
    m = {"id": 1, "task": "detection", "latency_ms": 10, "metrics": {"accuracy": 0.9}}
    a, b = predict(b"x", m, cls), predict(b"x", m, cls)
    assert a == b and abs(sum(a["probs"].values()) - 1) < 1e-3 and len(a["top3"]) == 3
    print("ok")
