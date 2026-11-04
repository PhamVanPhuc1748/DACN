"""Safely verify a trusted handoff checkpoint and evaluate a manifest split."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import time


FOCUS_CLASSES = {
    'Infected_Bacterial_Erysipelas',
    'Infected_Bacterial_Greasy_Pig_Disease',
    'Infected_Environmental_Dermatitis',
    'Infected_Parasitic_Mange',
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--image-root', type=Path, required=True)
    parser.add_argument('--classes-file', type=Path, required=True)
    parser.add_argument('--expected-manifest-sha256', required=True)
    parser.add_argument('--split', default='test')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--batch-size', type=int, default=16)
    return parser.parse_args()


def metrics_from_confusion(matrix: list[list[int]], classes: list[str]) -> dict:
    total = sum(sum(row) for row in matrix)
    correct = sum(matrix[index][index] for index in range(len(classes)))
    per_class = {}
    for index, name in enumerate(classes):
        true_positive = matrix[index][index]
        actual = sum(matrix[index])
        predicted = sum(row[index] for row in matrix)
        precision = true_positive / predicted if predicted else 0.0
        recall = true_positive / actual if actual else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[name] = {'precision': precision, 'recall': recall, 'f1': f1,
                           'support': actual}
    return {
        'accuracy': correct / total if total else 0.0,
        'macro_precision': sum(item['precision'] for item in per_class.values()) / len(classes),
        'macro_recall': sum(item['recall'] for item in per_class.values()) / len(classes),
        'macro_f1': sum(item['f1'] for item in per_class.values()) / len(classes),
        'per_class': per_class,
        'confusion_matrix': matrix,
    }


def main() -> int:
    args = parse_args()
    if sha256(args.manifest) != args.expected_manifest_sha256.lower():
        raise ValueError('Manifest SHA-256 does not match the approved handoff hash.')

    import torch
    from PIL import Image, ImageOps
    from torchvision import models, transforms

    classes = json.loads(args.classes_file.read_text(encoding='utf-8'))
    checkpoint = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    required = {'model', 'label_mode', 'classes', 'class_to_index', 'image_size',
                'normalization', 'state_dict', 'best_epoch', 'val_metrics'}
    if not isinstance(checkpoint, dict) or not required.issubset(checkpoint):
        raise ValueError('Checkpoint does not contain the documented trusted schema.')
    if checkpoint['classes'] != classes:
        raise ValueError('Checkpoint class order does not match classes.json.')
    if checkpoint['label_mode'] != 'single':
        raise ValueError('Only the documented single-label checkpoint is supported.')
    if checkpoint['model'] == 'mobilenet_v2':
        model = models.mobilenet_v2(weights=None)
        model.classifier[1] = torch.nn.Linear(model.last_channel, len(classes))
    elif checkpoint['model'] == 'efficientnet_b0':
        model = models.efficientnet_b0(weights=None)
        model.classifier[1] = torch.nn.Linear(model.classifier[1].in_features, len(classes))
    else:
        raise ValueError(f"Unsupported architecture: {checkpoint['model']}")
    model.load_state_dict(checkpoint['state_dict'], strict=True)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device).eval()

    normalization = checkpoint['normalization']
    pipeline = transforms.Compose([
        transforms.Resize((checkpoint['image_size'], checkpoint['image_size'])),
        transforms.ToTensor(),
        transforms.Normalize(normalization['mean'], normalization['std']),
    ])
    class_to_index = {name: index for index, name in enumerate(classes)}
    rows = []
    with args.manifest.open(newline='', encoding='utf-8-sig') as stream:
        for row in csv.DictReader(stream):
            if row['split'] == args.split:
                rows.append(row)
    matrix = [[0 for _ in classes] for _ in classes]
    predictions = []
    started = time.perf_counter()
    with torch.inference_mode():
        for offset in range(0, len(rows), args.batch_size):
            batch_rows = rows[offset:offset + args.batch_size]
            tensors = []
            for row in batch_rows:
                image_path = (args.image_root / row['relative_path']).resolve()
                if not image_path.is_relative_to(args.image_root.resolve()):
                    raise ValueError('Manifest image path escapes the dataset root.')
                with Image.open(image_path) as image:
                    tensors.append(pipeline(ImageOps.exif_transpose(image).convert('RGB')))
            probabilities = torch.softmax(model(torch.stack(tensors).to(device)), dim=1).cpu()
            values, indices = torch.topk(probabilities, k=min(3, len(classes)), dim=1)
            for row, top_values, top_indices in zip(batch_rows, values, indices):
                true_index = class_to_index[row['labels']]
                predicted_index = int(top_indices[0])
                matrix[true_index][predicted_index] += 1
                predictions.append({
                    'relative_path': row['relative_path'],
                    'split': row['split'],
                    'true_label': row['labels'],
                    'predicted_label': classes[predicted_index],
                    'confidence': float(top_values[0]),
                    'top_3': json.dumps([
                        {'label': classes[int(index)], 'confidence': float(value)}
                        for value, index in zip(top_values, top_indices)
                    ], ensure_ascii=False),
                })
    metrics = metrics_from_confusion(matrix, classes)
    metrics.update({
        'split': args.split,
        'images': len(rows),
        'elapsed_seconds': time.perf_counter() - started,
        'device': str(device),
        'checkpoint_sha256': sha256(args.checkpoint),
        'manifest_sha256': sha256(args.manifest),
        'model': checkpoint['model'],
        'best_epoch': checkpoint['best_epoch'],
        'image_size': checkpoint['image_size'],
        'classes': classes,
    })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'evaluation.json').write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    fieldnames = ['relative_path', 'split', 'true_label', 'predicted_label',
                  'confidence', 'top_3']
    errors = [row for row in predictions if row['true_label'] != row['predicted_label']]
    with (args.output_dir / 'misclassified.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(errors)
    focus_errors = [row for row in errors if row['true_label'] in FOCUS_CLASSES
                    or row['predicted_label'] in FOCUS_CLASSES]
    with (args.output_dir / 'focus_review.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(focus_errors)
    print(json.dumps({
        'model': metrics['model'], 'split': metrics['split'], 'images': metrics['images'],
        'accuracy': metrics['accuracy'], 'macro_f1': metrics['macro_f1'],
        'errors': len(errors), 'focus_errors': len(focus_errors),
        'device': metrics['device'], 'output_dir': str(args.output_dir.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
