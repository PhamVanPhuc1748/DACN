"""Create a new manifest with expert-approved cases in train only."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "PigSkinTech"
sys.path.insert(0, str(APP))

BASE = ROOT / "ml_workspace" / "manifests" / "pig_skin_single_label_v4" / "manifest.csv"
CLASSES = ROOT / "ml_workspace" / "manifests" / "pig_skin_single_label_v4" / "classes.json"
IMAGE_ROOT = ROOT / "data" / "raw" / "Pig Skin Disease Single Label v4.v1-class-test.folder"
FIELDS = ("relative_path", "split", "labels", "group_id")


def digest(path: Path) -> str:
    hash_value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hash_value.update(chunk)
    return hash_value.hexdigest()


def build(output: Path, base: Path = BASE, classes_file: Path = CLASSES,
          base_image_root: Path = IMAGE_ROOT, image_root: Path = ROOT) -> dict:
    from services.store import list_curated_candidates

    from train_model import load_classes

    image_root = image_root.resolve()
    base_image_root = base_image_root.resolve()
    classes = set(load_classes(classes_file))
    rows = []
    hashes: dict[str, str] = {}
    with base.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            path = (base_image_root / row["relative_path"]).resolve()
            if not path.is_relative_to(base_image_root) or not path.is_relative_to(image_root):
                raise ValueError(f"Ảnh gốc nằm ngoài thư mục ảnh được khai báo: {path}")
            if not path.is_file():
                raise ValueError(f"Ảnh gốc không còn tồn tại: {path}")
            hashes[digest(path)] = row["split"]
            rows.append({
                "relative_path": path.relative_to(image_root).as_posix(),
                "split": row["split"],
                "labels": row["labels"],
                "group_id": "base:" + row["group_id"],
            })

    added = skipped_duplicate = skipped_invalid = 0
    for case in list_curated_candidates():
        if int(case.get("in_dataset") or 0) != 1:
            continue
        label = (case.get("expert_label") or "").strip()
        path = Path(case.get("image_path") or "").resolve()
        if label not in classes or not path.is_file() or not path.is_relative_to(image_root):
            skipped_invalid += 1
            continue
        image_hash = digest(path)
        if image_hash in hashes:
            skipped_duplicate += 1
            continue
        hashes[image_hash] = "train"
        rows.append({
            "relative_path": path.relative_to(image_root).as_posix(),
            "split": "train",
            "labels": label,
            "group_id": "expert-case:" + str(case["id"]),
        })
        added += 1

    if added == 0:
        raise ValueError(
            f"Chưa có ảnh mới đủ điều kiện (trùng: {skipped_duplicate}, thiếu ảnh/nhãn: {skipped_invalid}). "
            "Chuyên gia cần duyệt và chọn 'Đưa vào Dataset' trước."
        )
    output.parent.mkdir(parents=True, exist_ok=False)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "base_manifest": str(base.resolve()),
        "base_manifest_sha256": digest(base),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "base_images": len(rows) - added,
        "expert_images_added_to_train": added,
        "duplicates_skipped": skipped_duplicate,
        "invalid_cases_skipped": skipped_invalid,
        "image_root": str(image_root),
        "limitations": "group_id của ca chuyên gia là case ID; chưa chứng minh độc lập theo trang trại/con heo/phiên chụp. Cần rà soát near-duplicate trước khi công bố kết quả.",
    }
    output.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-manifest", type=Path, default=BASE)
    parser.add_argument("--classes-file", type=Path, default=CLASSES)
    parser.add_argument("--base-image-root", type=Path, default=IMAGE_ROOT)
    parser.add_argument("--image-root", type=Path, default=ROOT, help="Common root of base and expert images")
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.output, args.base_manifest, args.classes_file,
                               args.base_image_root, args.image_root), ensure_ascii=False, indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f"ERROR: {error}\n")
