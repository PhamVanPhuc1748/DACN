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


def build(output: Path) -> dict:
    from services.store import list_curated_candidates

    classes = set(json.loads(CLASSES.read_text(encoding="utf-8")))
    rows = []
    hashes: dict[str, str] = {}
    with BASE.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            path = (IMAGE_ROOT / row["relative_path"]).resolve()
            if not path.is_file():
                raise ValueError(f"Ảnh gốc không còn tồn tại: {path}")
            hashes[digest(path)] = row["split"]
            rows.append({
                "relative_path": path.relative_to(ROOT).as_posix(),
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
        if label not in classes or not path.is_file() or ROOT not in path.parents:
            skipped_invalid += 1
            continue
        image_hash = digest(path)
        if image_hash in hashes:
            skipped_duplicate += 1
            continue
        hashes[image_hash] = "train"
        rows.append({
            "relative_path": path.relative_to(ROOT).as_posix(),
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
        "base_manifest": str(BASE),
        "base_manifest_sha256": digest(BASE),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "base_images": len(rows) - added,
        "expert_images_added_to_train": added,
        "duplicates_skipped": skipped_duplicate,
        "invalid_cases_skipped": skipped_invalid,
        "image_root": str(ROOT),
        "limitations": "group_id của ca chuyên gia là case ID; chưa chứng minh độc lập theo trang trại/con heo/phiên chụp. Cần rà soát near-duplicate trước khi công bố kết quả.",
    }
    output.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output), ensure_ascii=False, indent=2))
