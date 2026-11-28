#!/usr/bin/env python3
"""Train an image classifier from a reviewed, group-safe CSV manifest.

The script never discovers labels from folder names. It reads only files listed in
the manifest and writes checkpoints/logs to a new run directory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPLIT_ALIASES = {"train": "train", "val": "val", "valid": "val", "validation": "val", "test": "test"}

# Edit this block to configure a run directly in this file. CLI arguments, when
# provided, override these values. Set MANIFEST and CLASSES_FILE after reviewing
# the dataset labels and split; this script does not infer either from folders.
CONFIG: dict[str, Any] = {
    "manifest": None,  # Example: PROJECT_ROOT / "data/splits/v1/manifest.csv"
    "image_root": PROJECT_ROOT,
    "classes_file": None,  # Example: PROJECT_ROOT / "data/splits/v1/classes.json"
    "label_mode": "single",  # "single" or "multilabel"
    "model": "mobilenet_v2",  # one model per run: mobilenet_v2, mobilenet_v3_large, efficientnet_b0
    "output_dir": None,  # None creates ml_workspace/runs/<timestamp>
    "epochs": 25,
    "head_epochs": 5,
    "batch_size": 16,
    "num_workers": 0,
    "head_lr": 1e-3,
    "finetune_lr": 1e-4,
    "weight_decay": 1e-4,
    "early_stopping_patience": 4,
    "image_size": 224,
    "seed": 42,
    "pretrained": False,
    "augmentation": True,
    "rotation_degrees": 10.0,
    "horizontal_flip_probability": 0.5,
    "brightness_jitter": 0.10,
    "contrast_jitter": 0.10,
    "saturation_jitter": 0.05,
    "multilabel_threshold": 0.5,
    "device": "auto",  # "auto", "cpu", or "cuda"
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train one supported image classifier using an explicitly reviewed CSV manifest."
    )
    parser.add_argument("--label-smoothing", type=float, default=0.0, help="Label smoothing for single-label training.")
    parser.add_argument("--lr-scheduler", choices=("none", "cosine"), default="none")
    parser.add_argument("--min-lr", type=float, default=1e-6)
    parser.add_argument("--optimizer", choices=("adam", "adamw"), default="adam")
    parser.add_argument("--manifest", type=Path, default=CONFIG["manifest"], help="CSV with relative_path, split, labels, and group_id columns.")
    parser.add_argument("--image-root", type=Path, default=CONFIG["image_root"], help="Root used to resolve manifest relative_path values.")
    parser.add_argument("--classes-file", type=Path, default=CONFIG["classes_file"], help="JSON list or class->index mapping approved for this dataset.")
    parser.add_argument("--label-mode", choices=("single", "multilabel"), default=CONFIG["label_mode"])
    parser.add_argument("--model", choices=("mobilenet_v2", "mobilenet_v3_large", "efficientnet_b0"), default=CONFIG["model"])
    parser.add_argument("--output-dir", type=Path, default=CONFIG["output_dir"], help="New run directory; default is ml_workspace/runs/<timestamp>.")
    parser.add_argument("--epochs", type=int, default=CONFIG["epochs"])
    parser.add_argument("--head-epochs", type=int, default=CONFIG["head_epochs"], help="Train only classifier head for the first N epochs.")
    parser.add_argument("--batch-size", type=int, default=CONFIG["batch_size"])
    parser.add_argument("--num-workers", type=int, default=CONFIG["num_workers"], help="Default 0 is safest on Windows.")
    parser.add_argument("--head-lr", type=float, default=CONFIG["head_lr"])
    parser.add_argument("--finetune-lr", type=float, default=CONFIG["finetune_lr"])
    parser.add_argument("--weight-decay", type=float, default=CONFIG["weight_decay"])
    parser.add_argument("--early-stopping-patience", type=int, default=CONFIG["early_stopping_patience"])
    parser.add_argument("--image-size", type=int, default=CONFIG["image_size"])
    parser.add_argument("--seed", type=int, default=CONFIG["seed"])
    parser.add_argument("--rotation-degrees", type=float, default=CONFIG["rotation_degrees"])
    parser.add_argument("--horizontal-flip-probability", type=float, default=CONFIG["horizontal_flip_probability"])
    parser.add_argument("--brightness-jitter", type=float, default=CONFIG["brightness_jitter"])
    parser.add_argument("--contrast-jitter", type=float, default=CONFIG["contrast_jitter"])
    parser.add_argument("--saturation-jitter", type=float, default=CONFIG["saturation_jitter"])
    parser.add_argument("--multilabel-threshold", type=float, default=CONFIG["multilabel_threshold"])
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default=CONFIG["device"])
    parser.add_argument("--pretrained", action=argparse.BooleanOptionalAction, default=CONFIG["pretrained"], help="Use torchvision ImageNet weights; they may download if not cached.")
    parser.add_argument("--augmentation", action=argparse.BooleanOptionalAction, default=CONFIG["augmentation"], help="Enable/disable training-only augmentation.")
    parser.add_argument("--dry-run", action="store_true", help="Validate manifest/images and print counts without importing PyTorch or training.")
    parser.add_argument("--skip-test", action="store_true", help="Validate the full manifest but skip test inference after training.")
    return parser.parse_args()


def load_classes(path: Path) -> list[str]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(value, list):
        classes = [str(item) for item in value]
    elif isinstance(value, dict):
        pairs = sorted(((int(index), str(name)) for name, index in value.items()), key=lambda item: item[0])
        if [index for index, _ in pairs] != list(range(len(pairs))):
            raise ValueError("classes-file mapping indices must be contiguous from 0")
        classes = [name for _, name in pairs]
    else:
        raise ValueError("classes-file must contain a JSON list or a JSON class-to-index object")
    if not classes or len(classes) != len(set(classes)):
        raise ValueError("classes-file must contain at least one unique class")
    return classes


def parse_labels(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        value = json.loads(raw)
        if not isinstance(value, list):
            raise ValueError("JSON labels value must be a list")
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in raw.split(";") if part.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_manifest(manifest: Path, image_root: Path, classes: list[str], label_mode: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not manifest.is_file():
        raise ValueError(f"Manifest not found: {manifest}")
    if not image_root.is_dir():
        raise ValueError(f"Image root not found: {image_root}")
    required = {"relative_path", "split", "labels", "group_id"}
    with manifest.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or [])
        missing = required - fields
        if missing:
            raise ValueError(f"Manifest is missing columns: {', '.join(sorted(missing))}")
        rows = list(reader)
    if not rows:
        raise ValueError("Manifest has no data rows")

    root = image_root.resolve()
    seen_paths: set[str] = set()
    group_splits: dict[str, set[str]] = defaultdict(set)
    hash_splits: dict[str, set[str]] = defaultdict(set)
    split_counts: Counter[str] = Counter()
    class_counts: dict[str, Counter[str]] = {split: Counter() for split in ("train", "val", "test")}
    normalized: list[dict[str, Any]] = []

    for row_number, row in enumerate(rows, start=2):
        relative = (row.get("relative_path") or "").strip()
        group_id = (row.get("group_id") or "").strip()
        split_raw = (row.get("split") or "").strip().lower()
        split = SPLIT_ALIASES.get(split_raw)
        labels = parse_labels(row.get("labels", ""))
        if not relative or not group_id or split is None or not labels:
            raise ValueError(f"Invalid/empty path, group_id, split, or labels at CSV row {row_number}")
        if len(labels) != len(set(labels)):
            raise ValueError(f"Repeated label at CSV row {row_number}: {relative}")
        if label_mode == "single" and len(labels) != 1:
            raise ValueError(f"Single-label mode requires exactly one label; row {row_number} has {labels}")
        unknown = set(labels) - set(classes)
        if unknown:
            raise ValueError(f"Unknown class(es) at CSV row {row_number}: {', '.join(sorted(unknown))}")

        path = (root / Path(relative)).resolve()
        if path != root and root not in path.parents:
            raise ValueError(f"Path escapes image-root at CSV row {row_number}: {relative}")
        path_key = path.as_posix().casefold()
        if path_key in seen_paths:
            raise ValueError(f"Duplicate path in manifest: {relative}")
        seen_paths.add(path_key)
        if not path.is_file():
            raise ValueError(f"Image does not exist (CSV row {row_number}): {path}")
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image.load()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ValueError(f"Unreadable image at CSV row {row_number}: {path} ({exc})") from exc

        digest = sha256_file(path)
        group_splits[group_id].add(split)
        hash_splits[digest].add(split)
        split_counts[split] += 1
        for label in labels:
            class_counts[split][label] += 1
        normalized.append({"relative_path": relative, "path": path, "group_id": group_id, "split": split, "labels": labels, "sha256": digest})

    cross_split_groups = [group for group, splits in group_splits.items() if len(splits) > 1]
    cross_split_hashes = [digest for digest, splits in hash_splits.items() if len(splits) > 1]
    if cross_split_groups:
        raise ValueError(f"Group leakage: {len(cross_split_groups)} group_id values occur in multiple splits")
    if cross_split_hashes:
        raise ValueError(f"Exact duplicate leakage: {len(cross_split_hashes)} SHA-256 values occur in multiple splits")
    missing_splits = {"train", "val", "test"} - set(split_counts)
    if missing_splits:
        raise ValueError(f"Manifest must include all three splits; missing: {', '.join(sorted(missing_splits))}")
    if any(class_counts["train"][name] == 0 for name in classes):
        absent = [name for name in classes if class_counts["train"][name] == 0]
        raise ValueError(f"Every configured class must appear in train; absent: {', '.join(absent)}")
    for split in ("val", "test"):
        if not class_counts[split]:
            raise ValueError(f"No labels found in {split}")

    summary = {
        "rows": len(normalized),
        "split_counts": dict(split_counts),
        "class_counts": {split: {name: class_counts[split][name] for name in classes} for split in ("train", "val", "test")},
        "groups": len(group_splits),
        "cross_split_group_leaks": 0,
        "cross_split_exact_hash_leaks": 0,
        "split_sha256": {
            split: hashlib.sha256(json.dumps(sorted(
                (row["sha256"], row["labels"]) for row in normalized if row["split"] == split
            ), ensure_ascii=False).encode("utf-8")).hexdigest()
            for split in ("train", "val", "test")
        },
    }
    return normalized, summary


def print_summary(summary: dict[str, Any], classes: list[str]) -> None:
    print(f"Manifest valid: {summary['rows']} images / {summary['groups']} groups")
    print("Split counts:", ", ".join(f"{split}={summary['split_counts'].get(split, 0)}" for split in ("train", "val", "test")))
    print("Class counts:")
    for split in ("train", "val", "test"):
        counts = summary["class_counts"][split]
        print(f"  {split}: " + ", ".join(f"{name}={counts[name]}" for name in classes))
    print("Leakage checks: group_id and exact SHA-256 do not cross splits")


def train(args: argparse.Namespace, rows: list[dict[str, Any]], classes: list[str], summary: dict[str, Any]) -> None:
    try:
        import numpy as np
        import torch
        from torch import nn
        from torch.utils.data import DataLoader, Dataset
        from torchvision import models, transforms
        from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
    except ImportError as exc:
        raise RuntimeError(
            "Training dependencies are missing. Install a PyTorch/torchvision build matching your CUDA/CPU setup, "
            "then install ml_workspace/requirements.txt. No packages were installed automatically."
        ) from exc

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = False
    try:
        torch.use_deterministic_algorithms(True, warn_only=True)
    except (AttributeError, TypeError):
        pass

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but PyTorch cannot access a CUDA device")
    device_name = "cuda" if args.device == "auto" and torch.cuda.is_available() else args.device
    if device_name == "auto":
        device_name = "cpu"
    device = torch.device(device_name)
    class_to_index = {name: index for index, name in enumerate(classes)}
    mean, std = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
    train_ops: list[Any] = [transforms.Resize((args.image_size, args.image_size))]
    if args.augmentation:
        train_ops.extend([
            transforms.RandomHorizontalFlip(p=args.horizontal_flip_probability),
            transforms.RandomRotation(degrees=args.rotation_degrees),
            transforms.ColorJitter(
                brightness=args.brightness_jitter,
                contrast=args.contrast_jitter,
                saturation=args.saturation_jitter,
                hue=0.0,
            ),
        ])
    train_ops.extend([transforms.ToTensor(), transforms.Normalize(mean, std)])
    eval_transform = transforms.Compose([
        transforms.Resize((args.image_size, args.image_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])
    train_transform = transforms.Compose(train_ops)

    class ManifestDataset(Dataset):
        def __init__(self, data: list[dict[str, Any]], split: str, evaluation: bool = False):
            self.rows = [row for row in data if row["split"] == split]
            self.transform = eval_transform if evaluation or split != "train" else train_transform

        def __len__(self) -> int:
            return len(self.rows)

        def __getitem__(self, index: int):
            row = self.rows[index]
            with Image.open(row["path"]) as image:
                image = image.convert("RGB")
            x = self.transform(image)
            if args.label_mode == "single":
                y = torch.tensor(class_to_index[row["labels"][0]], dtype=torch.long)
            else:
                y = torch.zeros(len(classes), dtype=torch.float32)
                for label in row["labels"]:
                    y[class_to_index[label]] = 1.0
            return x, y

    def build_model():
        if args.model == "mobilenet_v2":
            weights = models.MobileNet_V2_Weights.DEFAULT if args.pretrained else None
            net = models.mobilenet_v2(weights=weights)
        elif args.model == "mobilenet_v3_large":
            weights = models.MobileNet_V3_Large_Weights.DEFAULT if args.pretrained else None
            net = models.mobilenet_v3_large(weights=weights)
        else:
            weights = models.EfficientNet_B0_Weights.DEFAULT if args.pretrained else None
            net = models.efficientnet_b0(weights=weights)
        in_features = net.classifier[-1].in_features
        net.classifier[-1] = nn.Linear(in_features, len(classes))
        return net

    def set_trainable(model, head_only: bool) -> list[Any]:
        for parameter in model.parameters():
            parameter.requires_grad = not head_only
        if head_only:
            for parameter in model.classifier.parameters():
                parameter.requires_grad = True
        return [parameter for parameter in model.parameters() if parameter.requires_grad]

    def collect_predictions(model, loader, criterion):
        model.eval()
        loss_sum = 0.0
        targets, predictions, probabilities = [], [], []
        with torch.inference_mode():
            for images, labels in loader:
                images, labels = images.to(device), labels.to(device)
                logits = model(images)
                loss = criterion(logits, labels)
                loss_value = float(loss.item())
                if not math.isfinite(loss_value):
                    raise RuntimeError(f"Non-finite evaluation loss on {loader.dataset.rows[0]['split']}")
                loss_sum += loss_value * images.size(0)
                if args.label_mode == "single":
                    probs = torch.softmax(logits, dim=1)
                    preds = probs.argmax(dim=1)
                    targets.extend(labels.cpu().numpy().tolist())
                    predictions.extend(preds.cpu().numpy().tolist())
                    probabilities.extend(probs.cpu().numpy().tolist())
                else:
                    probs = torch.sigmoid(logits)
                    preds = probs >= args.multilabel_threshold
                    targets.extend(labels.cpu().numpy().tolist())
                    predictions.extend(preds.cpu().numpy().astype(int).tolist())
                    probabilities.extend(probs.cpu().numpy().tolist())
        average_loss = loss_sum / max(len(loader.dataset), 1)
        target_array, prediction_array = np.asarray(targets), np.asarray(predictions)
        if args.label_mode == "single":
            precision, recall, f1, support = precision_recall_fscore_support(
                target_array, prediction_array, labels=list(range(len(classes))), zero_division=0
            )
            metrics = {
                "accuracy": float(accuracy_score(target_array, prediction_array)),
                "macro_precision": float(np.mean(precision)),
                "macro_recall": float(np.mean(recall)),
                "macro_f1": float(np.mean(f1)),
                "weighted_precision": float(np.average(precision, weights=support)),
                "weighted_recall": float(np.average(recall, weights=support)),
                "weighted_f1": float(np.average(f1, weights=support)),
                "per_class": {name: {"precision": float(precision[i]), "recall": float(recall[i]),
                                     "f1": float(f1[i]), "support": int(support[i])} for i, name in enumerate(classes)},
                "confusion_matrix": confusion_matrix(target_array, prediction_array, labels=list(range(len(classes)))).tolist(),
            }
        else:
            precision, recall, f1, _ = precision_recall_fscore_support(
                target_array, prediction_array, average=None, zero_division=0
            )
            metrics = {
                "subset_accuracy": float(np.all(target_array == prediction_array, axis=1).mean()),
                "macro_precision": float(np.mean(precision)),
                "macro_recall": float(np.mean(recall)),
                "macro_f1": float(np.mean(f1)),
                "per_class": {name: {"precision": float(precision[i]), "recall": float(recall[i]), "f1": float(f1[i])} for i, name in enumerate(classes)},
            }
        metrics["loss"] = float(average_loss)
        return metrics

    def print_metrics(split: str, metrics: dict[str, Any]) -> None:
        accuracy = metrics.get("accuracy", metrics.get("subset_accuracy"))
        accuracy_name = "accuracy" if "accuracy" in metrics else "subset_accuracy"
        print(
            f"[{split}] loss={metrics['loss']:.4f} {accuracy_name}={accuracy:.4f} "
            f"macro_precision={metrics['macro_precision']:.4f} "
            f"macro_recall={metrics['macro_recall']:.4f} macro_f1={metrics['macro_f1']:.4f}"
        )
        print(f"[{split}] Per-class metrics (precision / recall / F1):")
        for name in classes:
            values = metrics["per_class"][name]
            print(
                f"  {name}: {values['precision']:.4f} / "
                f"{values['recall']:.4f} / {values['f1']:.4f}"
            )
        if "confusion_matrix" in metrics:
            print(f"[{split}] Confusion matrix; rows=true, columns=predicted; class order:")
            print("  " + ", ".join(f"{index}={name}" for index, name in enumerate(classes)))
            for name, row in zip(classes, metrics["confusion_matrix"]):
                print(f"  {name}: {row}")

    evaluated_splits = ("train", "val") if args.skip_test else ("train", "val", "test")
    datasets = {split: ManifestDataset(rows, split) for split in evaluated_splits}
    train_eval_dataset = ManifestDataset(rows, "train", evaluation=True)
    loaders = {
        split: DataLoader(
            dataset,
            batch_size=args.batch_size,
            shuffle=(split == "train"),
            num_workers=args.num_workers,
            pin_memory=(device.type == "cuda"),
        )
        for split, dataset in datasets.items()
    }
    train_eval_loader = DataLoader(train_eval_dataset, batch_size=args.batch_size, shuffle=False,
                                   num_workers=args.num_workers, pin_memory=(device.type == "cuda"))
    model = build_model().to(device)
    criterion = nn.CrossEntropyLoss() if args.label_mode == "single" else nn.BCEWithLogitsLoss()
    train_criterion = (
        nn.CrossEntropyLoss(label_smoothing=args.label_smoothing)
        if args.label_mode == "single" else criterion
    )
    trainable = set_trainable(model, head_only=(args.head_epochs > 0))
    optimizer_cls = (
        torch.optim.AdamW if args.optimizer == "adamw"
        else torch.optim.Adam
    )
    optimizer = optimizer_cls(trainable, lr=args.head_lr, weight_decay=args.weight_decay)
    torchvision_version = __import__("torchvision").__version__
    gpu_name = torch.cuda.get_device_name(device) if device.type == "cuda" else None
    gpu_memory_gib = (
        torch.cuda.get_device_properties(device).total_memory / (1024 ** 3)
        if device.type == "cuda" else None
    )

    output_dir = args.output_dir or (PROJECT_ROOT / "ml_workspace" / "runs" / datetime.now().strftime("%Y%m%d_%H%M%S"))
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    manifest_hash = sha256_file(args.manifest.resolve())
    config = {
        "model": args.model,
        "label_mode": args.label_mode,
        "classes": classes,
        "class_to_index": class_to_index,
        "image_size": args.image_size,
        "normalization": {"mean": mean, "std": std},
        "augmentation": {
            "enabled": args.augmentation,
            "horizontal_flip_probability": args.horizontal_flip_probability,
            "rotation_degrees": args.rotation_degrees,
            "brightness": args.brightness_jitter,
            "contrast": args.contrast_jitter,
            "saturation": args.saturation_jitter,
            "hue": 0.0,
        },
        "multilabel_threshold": args.multilabel_threshold,
        "pretrained": args.pretrained,
        "weights_source": "torchvision ImageNet DEFAULT" if args.pretrained else "random initialization",
        "epochs": args.epochs,
        "skip_test": args.skip_test,
        "label_smoothing": args.label_smoothing,
        "evaluation_label_smoothing": 0.0,
        "head_epochs": args.head_epochs,
        "head_lr": args.head_lr,
        "finetune_lr": args.finetune_lr,
        "batch_size": args.batch_size,
        "num_workers": args.num_workers,
        "weight_decay": args.weight_decay,
        "early_stopping_patience": args.early_stopping_patience,
        "seed": args.seed,
        "optimizer": optimizer_cls.__name__,
        "lr_scheduler": args.lr_scheduler,
        "min_lr": args.min_lr,
        "loss": "CrossEntropyLoss" if args.label_mode == "single" else "BCEWithLogitsLoss",
        "manifest": str(args.manifest.resolve()),
        "manifest_sha256": manifest_hash,
        "classes_file_sha256": sha256_file(args.classes_file.resolve()),
        "split_sha256": summary["split_sha256"],
        "summary": summary,
        "device_requested": args.device,
        "device": str(device),
        "gpu_name": gpu_name,
        "gpu_memory_gib": gpu_memory_gib,
        "deterministic_algorithms": True,
        "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
        "torch_version": torch.__version__,
        "torchvision_version": torchvision_version,
    }
    (output_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    history: list[dict[str, Any]] = []
    best_macro_f1 = -1.0
    best_epoch = 0
    epochs_without_improvement = 0
    switched_to_finetune = args.head_epochs == 0
    scheduler = None
    if args.lr_scheduler == "cosine" and switched_to_finetune:
        optimizer.param_groups[0]["lr"] = args.finetune_lr
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=args.epochs,
            eta_min=args.min_lr
        )

    print("\n=== TRAINING CONFIGURATION ===")
    print(f"Model: {args.model} | classes: {len(classes)} | label_mode: {args.label_mode}")
    print(f"Manifest: {args.manifest.resolve()}")
    print(f"Manifest SHA-256: {manifest_hash}")
    print("Split sizes: " + ", ".join(
        f"{name}={summary['split_counts'].get(name, 0)}" for name in ("train", "val", "test")
    ))
    print(f"Device: requested={args.device}, used={device}, GPU={gpu_name or 'none'}")
    if gpu_memory_gib is not None:
        print(f"GPU memory: {gpu_memory_gib:.2f} GiB")
    print(f"PyTorch={torch.__version__} | torchvision={torchvision_version} | CUDA runtime={torch.version.cuda}")
    print(
        "Determinism: torch.use_deterministic_algorithms=True | "
        f"CUBLAS_WORKSPACE_CONFIG={os.environ.get('CUBLAS_WORKSPACE_CONFIG', 'not set')}"
    )
    print(f"Optimizer={optimizer_cls.__name__} | loss={type(train_criterion).__name__}")
    print(f"Training label smoothing={args.label_smoothing:g} | evaluation smoothing=0")
    print(f"LR scheduler={args.lr_scheduler} | min_lr={args.min_lr:g}")
    print(f"Epochs: max={args.epochs}, head-only={args.head_epochs}, patience={args.early_stopping_patience}")
    print(f"Learning rates: head={args.head_lr:g}, fine-tune={args.finetune_lr:g} | weight_decay={args.weight_decay:g}")
    print(f"Batch size={args.batch_size} | image size={args.image_size}x{args.image_size} | workers={args.num_workers}")
    print(f"Pretrained={args.pretrained} ({config['weights_source']}) | seed={args.seed}")
    if args.augmentation:
        print(
            "Train augmentation: enabled | flip_probability="
            f"{args.horizontal_flip_probability:g} | rotation=±{args.rotation_degrees:g}° | "
            f"brightness={args.brightness_jitter:g}, contrast={args.contrast_jitter:g}, "
            f"saturation={args.saturation_jitter:g}"
        )
    else:
        print("Train augmentation: disabled")
    print(f"Normalization: mean={mean}, std={std} | validation/test augmentation=disabled")
    print(f"Output directory: {output_dir}")
    print("Artifacts: config.json, history.csv, best_model.pt, best_validation.json, final_metrics.json")
    print("=== TRAINING START ===", flush=True)
    training_started = time.perf_counter()
    for epoch in range(1, args.epochs + 1):
        if epoch == args.head_epochs + 1 and not switched_to_finetune:
            trainable = set_trainable(model, head_only=False)
            optimizer = optimizer_cls(trainable, lr=args.finetune_lr, weight_decay=args.weight_decay)
            switched_to_finetune = True
            if args.lr_scheduler == "cosine":
                scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                    optimizer,
                    T_max=args.epochs - args.head_epochs,
                    eta_min=args.min_lr
                )
            print(f"Epoch {epoch}: unfreezing backbone; LR={args.finetune_lr:g}")
        epoch_started = time.perf_counter()
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
        model.train()
        train_loss_sum = 0.0
        for batch, (images, labels) in enumerate(loaders["train"], start=1):
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = train_criterion(logits, labels)
            loss_value = float(loss.item())
            if not math.isfinite(loss_value):
                raise RuntimeError(f"Non-finite training loss at epoch {epoch}, batch {batch}")
            loss.backward()
            optimizer.step()
            train_loss_sum += loss_value * images.size(0)
        train_loss = train_loss_sum / max(len(datasets["train"]), 1)
        train_metrics = collect_predictions(model, train_eval_loader, criterion)
        val_metrics = collect_predictions(model, loaders["val"], criterion)
        record = {"epoch": epoch, "train_loss": train_loss, "train_eval_loss": train_metrics["loss"],
                  "learning_rate": optimizer.param_groups[0]["lr"],
                  "train_accuracy": train_metrics.get("accuracy", train_metrics.get("subset_accuracy")),
                  "train_macro_f1": train_metrics["macro_f1"],
                  **{f"val_{key}": value for key, value in val_metrics.items()}}
        record["epoch_seconds"] = time.perf_counter() - epoch_started
        if device.type == "cuda":
            record["cuda_peak_allocated_mib"] = torch.cuda.max_memory_allocated(device) / (1024 ** 2)
            record["cuda_peak_reserved_mib"] = torch.cuda.max_memory_reserved(device) / (1024 ** 2)
        history.append(record)
        with (output_dir / "history.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(history[0]))
            writer.writeheader()
            writer.writerows(history)
        score = val_metrics["macro_f1"]
        accuracy = val_metrics.get("accuracy", val_metrics.get("subset_accuracy"))
        accuracy_name = "accuracy" if "accuracy" in val_metrics else "subset_accuracy"
        print(
            f"Epoch {epoch:02d}/{args.epochs} | phase={'head' if epoch <= args.head_epochs else 'fine-tune'} "
            f"| lr={optimizer.param_groups[0]['lr']:g} | train_loss={train_loss:.4f} "
            f"| train_eval_loss={train_metrics['loss']:.4f} | train_accuracy={record['train_accuracy']:.4f} "
            f"| train_macro_f1={train_metrics['macro_f1']:.4f} "
            f"| val_loss={val_metrics['loss']:.4f} | val_{accuracy_name}={accuracy:.4f} "
            f"| val_macro_precision={val_metrics['macro_precision']:.4f} "
            f"| val_macro_recall={val_metrics['macro_recall']:.4f} "
            f"| val_macro_f1={score:.4f} | time={record['epoch_seconds']:.1f}s",
            flush=True,
        )
        if device.type == "cuda":
            print(f"  CUDA peak: allocated={record['cuda_peak_allocated_mib']:.1f} MiB "
                  f"reserved={record['cuda_peak_reserved_mib']:.1f} MiB", flush=True)
        if score > best_macro_f1:
            best_macro_f1, best_epoch, epochs_without_improvement = score, epoch, 0
            torch.save({
                "model": args.model,
                "label_mode": args.label_mode,
                "classes": classes,
                "class_to_index": class_to_index,
                "image_size": args.image_size,
                "normalization": {"mean": mean, "std": std},
                "state_dict": model.state_dict(),
                "best_epoch": best_epoch,
                "val_metrics": val_metrics,
            }, output_dir / "best_model.pt")
            (output_dir / "best_validation.json").write_text(json.dumps(val_metrics, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  New best checkpoint: epoch={best_epoch}, val_macro_f1={best_macro_f1:.4f}")
        else:
            epochs_without_improvement += 1
        if scheduler is not None:
            scheduler.step()
        if epochs_without_improvement >= args.early_stopping_patience:
            print(f"Early stopping after epoch {epoch}; best epoch was {best_epoch}.")
            break

    training_seconds = time.perf_counter() - training_started
    checkpoint = torch.load(output_dir / "best_model.pt", map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["state_dict"])
    results = {"best_epoch": best_epoch, "best_val_macro_f1": best_macro_f1,
               "epochs_completed": len(history), "training_seconds": training_seconds,
               "checkpoint_size_bytes": (output_dir / "best_model.pt").stat().st_size}
    if device.type == "cuda":
        for key in ("cuda_peak_allocated_mib", "cuda_peak_reserved_mib"):
            results[key] = max(record[key] for record in history)
    if args.skip_test:
        results["test_skipped"] = True
    else:
        results["test_metrics"] = collect_predictions(model, loaders["test"], criterion)
    (output_dir / "final_metrics.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== TRAINING COMPLETE ===")
    print(f"Best checkpoint: epoch={best_epoch}, validation macro-F1={best_macro_f1:.4f}")
    print_metrics("BEST VALIDATION", checkpoint["val_metrics"])
    if args.skip_test:
        print("TEST skipped (--skip-test).")
    else:
        print_metrics("TEST", results["test_metrics"])
    print("Output files:")
    for filename in ("config.json", "history.csv", "best_model.pt", "best_validation.json", "final_metrics.json"):
        print(f"  {output_dir / filename}")


def main() -> int:
    args = parse_args()
    if args.lr_scheduler == "cosine":
        if not 0 <= args.min_lr < args.finetune_lr:
            raise SystemExit("min-lr must be >= 0 and below finetune-lr")
    if not 0.0 <= args.label_smoothing <= 1.0:
        raise SystemExit("label-smoothing must be between 0 and 1")
    if args.label_mode != "single" and args.label_smoothing != 0.0:
        raise SystemExit("Label smoothing requires single-label mode")
    if args.manifest is None or args.classes_file is None:
        print("Set CONFIG['manifest'] and CONFIG['classes_file'] near the top of train_model.py, or pass --manifest and --classes-file.", file=sys.stderr)
        return 2
    if args.epochs < 1 or args.head_epochs < 0 or args.batch_size < 1 or args.image_size < 32 or args.num_workers < 0:
        print("epochs, batch-size, and image-size must be positive; head-epochs and num-workers cannot be negative", file=sys.stderr)
        return 2
    if args.head_epochs >= args.epochs:
        print("head-epochs must be less than epochs so at least one fine-tuning epoch runs", file=sys.stderr)
        return 2
    if args.early_stopping_patience < 1 or args.head_lr <= 0 or args.finetune_lr <= 0 or args.weight_decay < 0:
        print("learning rates and early-stopping-patience must be positive; weight-decay cannot be negative", file=sys.stderr)
        return 2
    if (
        not 0.0 <= args.horizontal_flip_probability <= 1.0
        or args.rotation_degrees < 0
        or min(args.brightness_jitter, args.contrast_jitter, args.saturation_jitter) < 0
    ):
        print("augmentation probability must be in [0, 1]; rotation and color-jitter values cannot be negative", file=sys.stderr)
        return 2
    if not 0.0 <= args.multilabel_threshold <= 1.0:
        print("multilabel-threshold must be in [0, 1]", file=sys.stderr)
        return 2
    try:
        classes = load_classes(args.classes_file)
        rows, summary = validate_manifest(args.manifest, args.image_root, classes, args.label_mode)
        print_summary(summary, classes)
        if args.dry_run:
            print("Dry-run only: no PyTorch import, output directory, checkpoint, or training was started.")
            return 0
        if os.name == "nt":
            import msvcrt

            lock_path = PROJECT_ROOT / "ml_workspace" / "runs" / "training.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            with lock_path.open("a+b") as lock:
                lock.seek(0)
                if not lock.read(1):
                    lock.write(b"0")
                    lock.flush()
                lock.seek(0)
                try:
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    raise RuntimeError("Đã có một lượt train đang chạy trên máy này.") from exc
                try:
                    train(args, rows, classes, summary)
                finally:
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            train(args, rows, classes, summary)
        return 0
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
