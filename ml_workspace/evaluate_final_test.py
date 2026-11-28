from pathlib import Path
from datetime import datetime
import os

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import csv
import json
import gc
import time
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
    "E03": BASE / "rf_v1_efficientnet_b0_E03_ls01",
    "E06": BASE / "rf_v1_efficientnet_b0_E06_ls01_adamw",
}

EXPECTED_MODELS = {
    "E03": "efficientnet_b0",
    "E06": "efficientnet_b0",
}

OUT = OUTPUT_ROOT / (
    "rf_v1_E09_final_test_" +
    datetime.now().strftime("%Y%m%d_%H%M%S_%f")
)

# Frozen on validation before evaluating test.
EXPECTED_HASHES = {
    "E03": "0de930e0d089f6ed5b2835f12b1461ecf87fca217dfa442c2264b6beac8625d9",
    "E06": "61b7198191df1fe9b9b1f42879dcab1fac8b946e2049735aeb7288f0a5d6bb96",
}
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
require(manifest_hash == "d07aa8d72568457ae5ab97c1b9b1634111442cf6ab1af021edee77b9c2434300", "Frozen manifest mismatch")
require(classes_hash == "4a069a6fb036ffb8e23bf0aea0f39e8dafcdd680515d4e3f059abbbc59cf169e", "Frozen classes mismatch")

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

test_rows = [
    row for row in rows
    if row["split"] == "test"
]

require(len(test_rows) == 423, "Invalid test size")

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
    require(hashes[key] == EXPECTED_HASHES[key], f"{key}: frozen checkpoint hash mismatch")

    print(f"{key} checkpoint SHA256: {hashes[key]}")

require(
    len(set(hashes.values())) == len(hashes),
    "Unexpected identical checkpoints",
)

print("Dataset and checkpoint configuration: PASS")
print("Test images:", len(test_rows))
print("FROZEN CANDIDATE: E07-A, E03/E06 50:50, no TTA")
print("TEST INFERENCE: ENABLED; no training or model selection")

# ==========================================
# EXACT TEST PREPROCESSING
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

class TestDataset(Dataset):

    def __len__(self):
        return len(test_rows)

    def __getitem__(self, index):
        row = test_rows[index]

        with Image.open(row["path"]) as image:
            image = image.convert("RGB")

        x = eval_transform(image)
        y = class_to_index[row["labels"][0]]

        return x, y

loader = DataLoader(
    TestDataset(),
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=0,
    pin_memory=True,
)

targets = np.asarray([
    class_to_index[row["labels"][0]]
    for row in test_rows
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
        probabilities.shape == (423, 10),
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
        "weighted_precision": float(np.average(p, weights=s)),
        "weighted_recall": float(np.average(r, weights=s)),
        "negative_log_likelihood": float(-np.log(np.clip(probabilities[np.arange(len(targets)), targets], 1e-30, 1.0)).mean()),
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
results = {}
forward_seconds = {}

for key in RUNS:

    print(f"\n=== INFERENCE {key} ===", flush=True)

    model, saved_metrics = load_model(key)

    chunks = []
    observed_targets = []
    elapsed = 0.0
    # Warm up kernels with synthetic input; no test labels used.
    with torch.inference_mode():
        dummy = torch.zeros((BATCH_SIZE, 3, 224, 224), device=DEVICE)
        for _ in range(3):
            torch.softmax(model(dummy), dim=1)
        torch.cuda.synchronize()
        del dummy

    with torch.inference_mode():

        for index, (images, labels) in enumerate(loader, 1):

            gpu_images = images.to(DEVICE)
            torch.cuda.synchronize()
            start = time.perf_counter()
            logits = model(gpu_images)
            probs = torch.softmax(logits, dim=1)
            torch.cuda.synchronize()
            elapsed += time.perf_counter() - start

            chunks.append(probs.cpu().numpy())
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

    metrics = calculate_metrics(probabilities[key])

    results[key] = metrics

    print(
        f"{key}: Accuracy={metrics['accuracy']:.4%} "
        f"Macro-F1={metrics['macro_f1']:.4%}"
    )

    forward_seconds[key] = elapsed
    print(f"{key}: forward+softmax seconds={elapsed:.4f}")
    del model, chunks, images, labels, logits, probs, gpu_images
    gc.collect()
    torch.cuda.empty_cache()

# ==========================================
# ENSEMBLE CONFIGURATIONS
# ==========================================

weights = {"E07-A": {"E03": 0.5, "E06": 0.5}}

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

OUT.mkdir(parents=True, exist_ok=False)

# Fixed candidate; never choose a winner using test metrics.
forward_seconds["E07-A"] = forward_seconds["E03"] + forward_seconds["E06"]
for name, m in results.items():
    m["forward_softmax_seconds"] = forward_seconds[name]
    m["amortized_forward_softmax_ms_per_image"] = forward_seconds[name] * 1000 / len(targets)

report = {
    "split": "test",
    "test_images": len(targets),
    "test_skipped": False,
    "selected_on_validation": "E07-A",
    "tta": False,
    "batch_size": BATCH_SIZE,
    "device": str(DEVICE),
    "gpu_name": torch.cuda.get_device_name(0),
    "torch_version": torch.__version__,
    "timing_note": "Synchronized GPU forward+softmax only, batch size 16, warmup excluded. Ensemble sums component times; not end-to-end or single-image latency.",
    "evaluation_note": "Test split previously evaluated for E01 and E02; not a new external holdout.",
    "manifest_sha256": manifest_hash,
    "classes_sha256": classes_hash,
    "split_sha256": summary["split_sha256"],
    "checkpoint_sha256": hashes,
    "checkpoint_paths": {
        key: str(run / "best_model.pt")
        for key, run in RUNS.items()
    },
    "ensemble_weights": weights,
    "results": results,
}

(OUT / "final_test_metrics.json").write_text(
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
        "Amortized_Forward_Softmax_MS_Per_Image",
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
            m["amortized_forward_softmax_ms_per_image"],
        ])

np.savez_compressed(
    OUT / "test_probabilities.npz",
    targets=targets,
    classes=np.asarray(classes),
    relative_paths=np.asarray([
        row["relative_path"] for row in test_rows
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

with (OUT / "per_class.csv").open("w", newline="", encoding="utf-8-sig") as file:
    writer = csv.writer(file)
    writer.writerow(["Experiment", "Class", "Precision", "Recall", "F1", "Support"])
    for name, m in results.items():
        for label, v in m["per_class"].items():
            writer.writerow([name, label, v["precision"], v["recall"], v["f1"], v["support"]])

print("\n=== E09 FINAL TEST BENCHMARK ===")
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

print("\nFROZEN CANDIDATE: E07-A")
print("FINAL TEST ACCURACY:", f"{results['E07-A']['accuracy']:.4%}")
print("FINAL TEST MACRO-F1:", f"{results['E07-A']['macro_f1']:.4%}")
print("No test-based model selection performed")
print("OUTPUT:", OUT)
print("E09 COMPLETE")
