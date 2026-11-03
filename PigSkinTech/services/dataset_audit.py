"""Local image-dataset structure and integrity checks."""
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, UnidentifiedImageError

IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp'}
SPLIT_NAMES = {
    'train': 'train',
    'training': 'train',
    'val': 'validation',
    'valid': 'validation',
    'validation': 'validation',
    'test': 'test',
    'testing': 'test',
}
UNASSIGNED = '(chưa gán lớp)'
EXAMPLE_LIMIT = 20


def _walk_error(error):
    raise error


def _image_paths(folder):
    for current, _, filenames in os.walk(folder, onerror=_walk_error, followlinks=False):
        for filename in filenames:
            path = Path(current) / filename
            if path.suffix.lower() in IMAGE_SUFFIXES and not path.is_symlink():
                yield path


def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as image_file:
        for chunk in iter(lambda: image_file.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def audit_dataset(directory):
    """Scan a class-folder or split/class-folder dataset without changing its files."""
    root = Path(directory).expanduser()
    if not root.is_dir():
        raise ValueError('Hãy chọn một thư mục dataset đang tồn tại.')
    root = root.resolve()

    dataset_version = None
    manifest = root / 'dataset_manifest.json'
    if manifest.is_file() and manifest.stat().st_size <= 1024 * 1024:
        try:
            metadata = json.loads(manifest.read_text(encoding='utf-8'))
            version = metadata.get('version') if isinstance(metadata, dict) else None
            if isinstance(version, str) and 0 < len(version.strip()) <= 100:
                dataset_version = version.strip()
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass

    split_folders = [
        (folder, SPLIT_NAMES[folder.name.casefold()])
        for folder in root.iterdir()
        if folder.is_dir() and folder.name.casefold() in SPLIT_NAMES
    ]
    layout = 'split/class/image' if split_folders else 'class/image'
    candidates = []
    empty_classes = []

    if split_folders:
        for split_folder, split_name in split_folders:
            class_folders = [item for item in split_folder.iterdir() if item.is_dir()]
            empty_classes.extend(
                f'{split_folder.name}/{folder.name}'
                for folder in class_folders
                if not any(_image_paths(folder))
            )
            for path in _image_paths(split_folder):
                relative = path.relative_to(split_folder)
                class_name = relative.parts[0] if len(relative.parts) > 1 else UNASSIGNED
                candidates.append((path, split_name, class_name))
    else:
        class_folders = [item for item in root.iterdir() if item.is_dir()]
        empty_classes.extend(
            folder.name for folder in class_folders if not any(_image_paths(folder))
        )
        for path in _image_paths(root):
            relative = path.relative_to(root)
            class_name = relative.parts[0] if len(relative.parts) > 1 else UNASSIGNED
            candidates.append((path, 'unspecified', class_name))

    class_counts = Counter()
    split_counts = Counter()
    split_class_counts = defaultdict(Counter)
    corrupt_files = []
    digest_files = defaultdict(list)
    valid_count = 0

    for path, split_name, class_name in candidates:
        relative_path = path.relative_to(root).as_posix()
        try:
            with Image.open(path) as image:
                image.verify()
        except (
            UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError,
            Image.DecompressionBombError,
        ):
            corrupt_files.append(relative_path)
            continue

        valid_count += 1
        class_counts[class_name] += 1
        split_counts[split_name] += 1
        split_class_counts[split_name][class_name] += 1
        digest_files[_sha256(path)].append({
            'path': relative_path,
            'split': split_name,
            'class': class_name,
        })

    duplicate_groups = [files for files in digest_files.values() if len(files) > 1]
    cross_split_groups = [
        files for files in duplicate_groups
        if len({item['split'] for item in files}) > 1
    ]
    duplicate_extras = sum(len(files) - 1 for files in duplicate_groups)
    class_sizes = [count for name, count in class_counts.items() if name != UNASSIGNED]
    imbalance_ratio = (
        max(class_sizes) / min(class_sizes) if class_sizes and min(class_sizes) else 0
    )

    warnings = []
    if not candidates:
        warnings.append('Không tìm thấy ảnh JPG, PNG hoặc WEBP trong thư mục đã chọn.')
    if not split_folders:
        warnings.append('Không tìm thấy thư mục train/validation/test; chỉ kiểm tra theo lớp.')
    if class_counts.get(UNASSIGNED):
        warnings.append(f'{class_counts[UNASSIGNED]} ảnh nằm ngoài thư mục lớp.')
    if corrupt_files:
        warnings.append(f'Có {len(corrupt_files)} ảnh không đọc/kiểm tra được.')
    if duplicate_extras:
        warnings.append(f'Có {duplicate_extras} ảnh trùng nội dung ({len(duplicate_groups)} nhóm).')
    if cross_split_groups:
        warnings.append(
            f'{len(cross_split_groups)} nhóm ảnh trùng xuất hiện ở nhiều split; '
            'cần kiểm tra nguy cơ rò rỉ dữ liệu.'
        )
    if imbalance_ratio >= 5:
        warnings.append(
            f'Mất cân bằng lớp đáng chú ý: lớp nhiều nhất gấp {imbalance_ratio:.1f} lần lớp ít nhất.'
        )
    if empty_classes:
        warnings.append(f'Có {len(empty_classes)} thư mục lớp không chứa ảnh được hỗ trợ.')

    return {
        'root': str(root),
        'dataset_version': dataset_version,
        'layout': layout,
        'image_files': len(candidates),
        'valid_images': valid_count,
        'corrupt_images': len(corrupt_files),
        'class_counts': dict(sorted(class_counts.items())),
        'split_counts': dict(sorted(split_counts.items())),
        'split_class_counts': {
            split: dict(sorted(counts.items()))
            for split, counts in sorted(split_class_counts.items())
        },
        'duplicate_groups': len(duplicate_groups),
        'duplicate_extras': duplicate_extras,
        'cross_split_duplicate_groups': len(cross_split_groups),
        'corrupt_examples': corrupt_files[:EXAMPLE_LIMIT],
        'empty_classes': empty_classes[:EXAMPLE_LIMIT],
        'class_imbalance_ratio': imbalance_ratio,
        'warnings': warnings,
    }
