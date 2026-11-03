"""Load and validate an exported experiment-metrics JSON file."""
import json
import math
from pathlib import Path

MAX_REPORT_BYTES = 5 * 1024 * 1024
METRIC_NAMES = {
    'validation_macro_f1': 'Validation Macro-F1',
    'test_macro_f1': 'Test Macro-F1',
    'test_accuracy': 'Test Accuracy',
    'validation_accuracy': 'Validation Accuracy',
    'test_macro_precision': 'Test Macro-Precision',
    'test_macro_recall': 'Test Macro-Recall',
}
PER_CLASS_METRICS = {'precision', 'recall', 'f1'}


def _validate_score(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'Chỉ số {name} phải là số từ 0 đến 1.')
    score = float(value)
    if not math.isfinite(score) or not 0 <= score <= 1:
        raise ValueError(f'Chỉ số {name} phải là số hữu hạn từ 0 đến 1.')
    return score


def load_experiment_metrics(path):
    """Read a normalized JSON report without guessing metrics from unrelated files."""
    report_path = Path(path).expanduser()
    if not report_path.is_file() or report_path.suffix.lower() != '.json':
        raise ValueError('Hãy chọn một file báo cáo thực nghiệm JSON hợp lệ.')
    if report_path.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError('File báo cáo thực nghiệm vượt quá giới hạn 5 MB.')
    try:
        report = json.loads(report_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'Không đọc được JSON báo cáo: {exc}') from exc
    if not isinstance(report, dict):
        raise ValueError('Báo cáo thực nghiệm phải là một đối tượng JSON.')

    metrics = report.get('metrics')
    if not isinstance(metrics, dict):
        raise ValueError('Báo cáo cần có đối tượng "metrics".')
    normalized_metrics = {}
    for metric_name in METRIC_NAMES:
        if metric_name in metrics:
            normalized_metrics[metric_name] = _validate_score(
                metrics[metric_name], metric_name
            )
    if not normalized_metrics:
        raise ValueError(
            'Không tìm thấy validation_macro_f1, test_macro_f1 hoặc test_accuracy.'
        )

    run_id = report.get('run_id', '')
    architecture = report.get('architecture', '')
    source = report.get('source', str(report_path))
    for name, value, limit in (
        ('run_id', run_id, 120),
        ('architecture', architecture, 120),
        ('source', source, 500),
    ):
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f'Trường "{name}" phải là chuỗi tối đa {limit} ký tự.')

    best_epoch = report.get('best_epoch')
    if best_epoch is not None and (
        isinstance(best_epoch, bool) or not isinstance(best_epoch, int) or best_epoch < 1
    ):
        raise ValueError('"best_epoch" phải là số nguyên dương.')

    per_class = report.get('per_class', [])
    if not isinstance(per_class, list) or len(per_class) > 100:
        raise ValueError('"per_class" phải là danh sách tối đa 100 lớp.')
    normalized_classes = []
    seen_classes = set()
    for entry in per_class:
        if not isinstance(entry, dict):
            raise ValueError('Mỗi phần tử trong "per_class" phải là một đối tượng.')
        class_name = entry.get('class_name')
        if not isinstance(class_name, str) or not class_name.strip() or len(class_name) > 120:
            raise ValueError('"class_name" cần là tên lớp không rỗng, tối đa 120 ký tự.')
        class_name = class_name.strip()
        if class_name in seen_classes:
            raise ValueError(f'Lớp "{class_name}" bị lặp trong "per_class".')
        seen_classes.add(class_name)
        class_metrics = {'class_name': class_name}
        for metric_name in PER_CLASS_METRICS:
            if metric_name in entry:
                class_metrics[metric_name] = _validate_score(
                    entry[metric_name], f'{class_name}.{metric_name}'
                )
        normalized_classes.append(class_metrics)

    losses = {}
    for name in ('train_loss', 'validation_loss', 'test_loss'):
        if name in metrics:
            value = metrics[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f'Chỉ số {name} phải là số hữu hạn không âm.')
            losses[name] = float(value)

    confusion = report.get('confusion_matrix')
    if confusion is not None:
        count = len(normalized_classes)
        if not count or not isinstance(confusion, list) or len(confusion) != count or any(
            not isinstance(row, list) or len(row) != count or any(
                isinstance(value, bool) or not isinstance(value, int) or value < 0
                for value in row
            ) for row in confusion
        ):
            raise ValueError('confusion_matrix phải là ma trận vuông số nguyên không âm, khớp per_class.')

    return {
        'path': str(report_path.resolve()),
        'run_id': run_id,
        'architecture': architecture,
        'best_epoch': best_epoch,
        'source': source or str(report_path),
        'metrics': normalized_metrics,
        'losses': losses,
        'per_class': normalized_classes,
        'confusion_matrix': confusion,
    }
