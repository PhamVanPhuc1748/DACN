from pathlib import Path
from datetime import datetime
import os

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import csv
import json
import gc
import numpy as np
import torch

from torch import nn
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from PIL import Image
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)

from train_model import (
    load_classes,
    validate_manifest,
    sha256_file,
)

# ==========================================
# CONFIGURATION
# ==========================================

ROOT = Path(__file__).resolve().parents[1]
IMAGE_ROOT = Path(os.environ["PIGSKIN_IMAGE_ROOT"]).expanduser()
BASE = Path(os.environ.get("PIGSKIN_CHECKPOINT_RUNS", ROOT / "PigSkinTech/models/runs"))
OUTPUT_ROOT = Path(os.environ.get("PIGSKIN_EVAL_OUTPUT", ROOT / "ml_workspace/runs"))

RUNS = {
    "E01": BASE / "rf_v1_conservative_baseline_01",
    "E03": BASE / "rf_v1_efficientnet_b0_E03_ls01",
    "E06": BASE / "rf_v1_efficientnet_b0_E06_ls01_adamw",
}

EXPECTED_MODELS = {
    "E01": "mobilenet_v2",
    "E03": "efficientnet_b0",
    "E06": "efficientnet_b0",
}

OUT = OUTPUT_ROOT / (
    "rf_v1_E08_ensemble_tta_" +
    datetime.now().strftime("%Y%m%d_%H%M%S_%f")
)

DEVICE = torch.device("cuda")
BATCH_SIZE = 16

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def read_json(path):
    return json.loads(
        path.read_text(encoding="utf-8-sig")
    )

require(torch.cuda.is_available(), "CUDA unavailable")

torch.backends.cudnn.benchmark = False
torch.use_deterministic_algorithms(True, warn_only=True)

print("GPU:", torch.cuda.get_device_name(0))

# ==========================================
# VALIDATE DATASET
# ==========================================

reference = read_json(RUNS["E03"] / "config.json")
manifest = ROOT / "ml_workspace/manifests/rf_v1_conservative/manifest_draft.csv"
classes_file = manifest.parent / "classes.json"

classes = load_classes(classes_file)
class_to_index = {
    name: index for index, name in enumerate(classes)
}

require(len(classes) == 10, "Expected 10 classes")

manifest_hash = sha256_file(manifest)
classes_hash = sha256_file(classes_file)

rows, summary = validate_manifest(
    manifest,
    IMAGE_ROOT,
    classes,
    "single",
)

require(
    summary["split_counts"] == {
        "train": 3152,
        "val": 838,
        "test": 423,
    },
    "Unexpected split counts",
)

val_rows = [
    row for row in rows
    if row["split"] == "val"
]

require(len(val_rows) == 838, "Invalid validation size")

configs = {}
hashes = {}

for key, run_dir in RUNS.items():
    config = read_json(run_dir / "config.json")
    checkpoint_path = run_dir / "best_model.pt"

    require(
        config["manifest_sha256"] == manifest_hash,
        f"{key}: manifest hash mismatch",
    )

    require(
        config["classes_file_sha256"] == classes_hash,
        f"{key}: classes hash mismatch",
    )

    require(
        config["split_sha256"] == summary["split_sha256"],
        f"{key}: split hash mismatch",
    )

    require(
        config["classes"] == classes,
        f"{key}: class order mismatch",
    )

    require(
        config["model"] == EXPECTED_MODELS[key],
        f"{key}: architecture mismatch",
    )

    require(
        config["label_mode"] == "single",
        f"{key}: label mode mismatch",
    )

    require(
        config["image_size"] == 224,
        f"{key}: image size mismatch",
    )

    require(
        config["normalization"] == reference["normalization"],
        f"{key}: normalization mismatch",
    )

    require(
        checkpoint_path.is_file(),
        f"{key}: missing checkpoint",
    )

    configs[key] = config
    hashes[key] = sha256_file(checkpoint_path)

    print(f"{key} checkpoint SHA256: {hashes[key]}")

require(
    len(set(hashes.values())) == len(hashes),
    "Unexpected identical checkpoints",
)

print("Dataset and checkpoint configuration: PASS")
print("Validation images:", len(val_rows))
print("TEST INFERENCE: DISABLED")

# ==========================================
# EXACT VALIDATION PREPROCESSING
# ==========================================

normalization = reference["normalization"]

eval_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        normalization["mean"],
        normalization["std"],
    ),
])

class ValidationDataset(Dataset):

    def __len__(self):
        return len(val_rows)

    def __getitem__(self, index):
        row = val_rows[index]

        with Image.open(row["path"]) as image:
            image = image.convert("RGB")

        x = eval_transform(image)
        y = class_to_index[row["labels"][0]]

        return x, y

loader = DataLoader(
    ValidationDataset(),
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=0,
    pin_memory=True,
)

targets = np.asarray([
    class_to_index[row["labels"][0]]
    for row in val_rows
])

# ==========================================
# MODEL LOADING
# ==========================================

def load_model(key):

    checkpoint = torch.load(
        RUNS[key] / "best_model.pt",
        map_location="cpu",
        weights_only=True,
    )

    require(
        checkpoint["classes"] == classes,
        f"{key}: checkpoint classes mismatch",
    )

    require(
        checkpoint["class_to_index"] == class_to_index,
        f"{key}: checkpoint class mapping mismatch",
    )

    require(
        checkpoint["model"] == EXPECTED_MODELS[key],
        f"{key}: checkpoint architecture mismatch",
    )

    require(
        checkpoint["label_mode"] == "single",
        f"{key}: checkpoint label mode mismatch",
    )

    require(
        checkpoint["image_size"] == 224,
        f"{key}: checkpoint image size mismatch",
    )

    require(
        json.dumps(checkpoint["normalization"], sort_keys=True)
        == json.dumps(normalization, sort_keys=True),
        f"{key}: checkpoint normalization mismatch",
    )

    if checkpoint["model"] == "mobilenet_v2":
        model = models.mobilenet_v2(weights=None)

    elif checkpoint["model"] == "efficientnet_b0":
        model = models.efficientnet_b0(weights=None)

    else:
        raise RuntimeError("Unsupported architecture")

    model.classifier[-1] = nn.Linear(
        model.classifier[-1].in_features,
        len(classes),
    )

    model.load_state_dict(
        checkpoint["state_dict"],
        strict=True,
    )

    return (
        model.to(DEVICE).eval(),
        checkpoint["val_metrics"],
    )

# ==========================================
# METRICS
# ==========================================

def calculate_metrics(probabilities):

    require(
        probabilities.shape == (838, 10),
        "Unexpected probability shape",
    )

    require(
        np.isfinite(probabilities).all(),
        "Non-finite probabilities",
    )

    require(
        np.allclose(probabilities.sum(axis=1), 1, atol=1e-5),
        "Invalid probability sum",
    )

    predictions = probabilities.argmax(axis=1)

    p, r, f, s = precision_recall_fscore_support(
        targets,
        predictions,
        labels=list(range(len(classes))),
        zero_division=0,
    )

    matrix = confusion_matrix(
        targets,
        predictions,
        labels=list(range(len(classes))),
    )

    healthy = class_to_index["Healthy"]

    sick_as_healthy = int(
        matrix[:, healthy].sum() -
        matrix[healthy, healthy]
    )

    return {
        "accuracy": float(
            accuracy_score(targets, predictions)
        ),
        "macro_precision": float(p.mean()),
        "macro_recall": float(r.mean()),
        "macro_f1": float(f.mean()),
        "weighted_f1": float(np.average(f, weights=s)),
        "correct_images": int((targets == predictions).sum()),
        "sick_as_healthy": sick_as_healthy,
        "per_class": {
            name: {
                "precision": float(p[i]),
                "recall": float(r[i]),
                "f1": float(f[i]),
                "support": int(s[i]),
            }
            for i, name in enumerate(classes)
        },
        "confusion_matrix": matrix.tolist(),
    }

# ==========================================
# SINGLE MODEL INFERENCE
# ==========================================

probabilities = {}
tta_probabilities = {}
results = {}

for key in RUNS:

    print(f"\n=== INFERENCE {key} ===", flush=True)

    model, saved_metrics = load_model(key)

    chunks = []
    tta_chunks = []
    observed_targets = []

    with torch.inference_mode():

        for index, (images, labels) in enumerate(loader, 1):

            logits = model(images.to(DEVICE))
            probs = torch.softmax(logits, dim=1)

            chunks.append(probs.cpu().numpy())
            flipped_images = torch.flip(images, dims=[3])
            flipped_logits = model(flipped_images.to(DEVICE))
            flipped_probs = torch.softmax(flipped_logits, dim=1)
            tta_probs = (probs + flipped_probs) / 2.0
            tta_chunks.append(tta_probs.cpu().numpy())
            observed_targets.extend(labels.tolist())

            if index % 10 == 0:
                print(
                    f"{key}: batch {index}/{len(loader)}",
                    flush=True,
                )

    require(
        np.array_equal(targets, observed_targets),
        f"{key}: target order mismatch",
    )

    probabilities[key] = np.concatenate(chunks, axis=0)
    tta_probabilities[key] = np.concatenate(tta_chunks, axis=0)

    metrics = calculate_metrics(probabilities[key])

    results[key] = metrics

    print(
        f"{key}: Accuracy={metrics['accuracy']:.4%} "
        f"Macro-F1={metrics['macro_f1']:.4%}"
    )

    require(
        np.array_equal(
            metrics["confusion_matrix"],
            saved_metrics["confusion_matrix"],
        ),
        f"{key}: validation confusion matrix mismatch",
    )

    require(
        abs(metrics["macro_f1"] -
            saved_metrics["macro_f1"]) < 1e-8,
        f"{key}: validation Macro-F1 mismatch",
    )

    print(f"{key}: baseline reproduction PASS")

    del model, chunks, tta_chunks, images, labels, logits, probs
    del flipped_images, flipped_logits, flipped_probs, tta_probs
    gc.collect()
    torch.cuda.empty_cache()

# ==========================================
# ENSEMBLE CONFIGURATIONS
# ==========================================

weights = {
    "E07-A": {"E03": 0.5, "E06": 0.5},
    "E07-B": {"E03": 0.7, "E06": 0.3},
    "E07-C": {"E01": 0.5, "E03": 0.5},
    "E07-D": {
        "E01": 1/3,
        "E03": 1/3,
        "E06": 1/3,
    },
}

for name, mapping in weights.items():

    combined = sum(
        probabilities[key].astype(np.float64) * weight
        for key, weight in mapping.items()
    )

    probabilities[name] = combined

    results[name] = calculate_metrics(combined)

# ==========================================
# SAVE RESULTS
# ==========================================


# E08: Test-Time Augmentation

tta_experiments = {
    "E08-A": {"E03": 1.0},
    "E08-B": {"E06": 1.0},
    "E08-C": {"E03": 0.5, "E06": 0.5},
    "E08-D": {"E01": 1/3, "E03": 1/3, "E06": 1/3},
}

for name, mapping in tta_experiments.items():

    combined = sum(
        tta_probabilities[key].astype(np.float64) * weight
        for key, weight in mapping.items()
    )

    probabilities[name] = combined
    results[name] = calculate_metrics(combined)

OUT.mkdir(parents=True, exist_ok=False)


best = max(
    results,
    key=lambda name: results[name]["macro_f1"],
)

report = {
    "split": "val",
    "validation_images": len(targets),
    "test_skipped": True,
    "manifest_sha256": manifest_hash,
    "classes_sha256": classes_hash,
    "split_sha256": summary["split_sha256"],
    "checkpoint_sha256": hashes,
    "checkpoint_paths": {
        key: str(run / "best_model.pt")
        for key, run in RUNS.items()
    },
    "ensemble_weights": weights,
    "tta_weights": tta_experiments,
    "tta_transforms": ["identity", "horizontal_flip"],
    "best_candidate_by_macro_f1": best,
    "results": results,
}

(OUT / "ensemble_metrics.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

with (OUT / "comparison.csv").open(
    "w", newline="", encoding="utf-8-sig"
) as file:

    writer = csv.writer(file)

    writer.writerow([
        "Experiment",
        "Accuracy",
        "Macro_F1",
        "Macro_Precision",
        "Macro_Recall",
        "Correct_Images",
        "Sick_As_Healthy",
    ])

    for name, m in results.items():

        writer.writerow([
            name,
            m["accuracy"],
            m["macro_f1"],
            m["macro_precision"],
            m["macro_recall"],
            m["correct_images"],
            m["sick_as_healthy"],
        ])

np.savez_compressed(
    OUT / "validation_probabilities.npz",
    targets=targets,
    classes=np.asarray(classes),
    relative_paths=np.asarray([
        row["relative_path"] for row in val_rows
    ]),
    **probabilities,
)

for name, m in results.items():

    with (OUT / f"{name}_confusion.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:

        writer = csv.writer(file)
        writer.writerow(["True / Predicted", *classes])

        for label, row in zip(classes, m["confusion_matrix"]):
            writer.writerow([label, *row])

print("\n=== E08 TTA VALIDATION BENCHMARK ===")
print(
    f"{'Model':<10} {'Accuracy':>12} "
    f"{'Macro-F1':>12} {'Correct':>10} "
    f"{'Sick->Healthy':>15}"
)

for name, m in results.items():

    print(
        f"{name:<10} "
        f"{m['accuracy']:>11.2%} "
        f"{m['macro_f1']:>11.2%} "
        f"{m['correct_images']:>10} "
        f"{m['sick_as_healthy']:>15}"
    )

print("\nBEST CANDIDATE:", best)
print("BEST MACRO-F1:", f"{results[best]['macro_f1']:.2%}")
print("TEST SKIPPED")
print("OUTPUT:", OUT)
print("E08 COMPLETE")
