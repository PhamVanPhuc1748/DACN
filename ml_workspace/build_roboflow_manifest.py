"""Build a draft single-label manifest from explicit Roboflow review decisions."""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory

from audit_roboflow import EXTENSIONS, write_csv
from train_model import PROJECT_ROOT, SPLIT_ALIASES, load_classes, validate_manifest

CLASSES = PROJECT_ROOT / "ml_workspace/manifests/pig_skin_single_label_v4/classes.json"
FIELDS = ("relative_path", "split", "labels", "group_id")
SPLIT_PRIORITY = {"train": 0, "val": 1, "test": 2}


def read_csv(path, fields):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not fields.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing CSV columns in {path}: {sorted(fields - set(reader.fieldnames or []))}")
        return list(reader)


def build(root, audit, review, output):
    root, output = root.resolve(), output.resolve()
    if not root.is_dir() or output.is_relative_to(root) or output.exists():
        raise ValueError("Use an existing dataset root and a new output directory outside it")
    classes = load_classes(CLASSES)
    inventory = {}
    for image in sorted(root.rglob("*")):
        if not image.is_file() or image.suffix.lower() not in EXTENSIONS:
            continue
        relative = image.relative_to(root)
        if len(relative.parts) != 3:
            raise ValueError(f"Expected split/class/image: {relative}")
        split, label, _ = relative.parts
        if split not in SPLIT_ALIASES or label not in classes:
            raise ValueError(f"Unknown split or label: {relative}")
        inventory[relative.as_posix()] = (SPLIT_ALIASES[split], label)
    required = {row["path"] for row in read_csv(audit / "group_members.csv", {"path"})}
    required.update(row["path"] for row in read_csv(audit / "unreadable.csv", {"path"}))
    visual = audit / "visual_candidates.csv"
    if visual.is_file():
        required.update(row["path"] for row in read_csv(visual, {"path"}))
    if not required.issubset(inventory):
        raise ValueError("Audit candidates differ from the current dataset")
    decisions = {}
    pending = set(required)
    excluded = []
    for row in read_csv(review, {"path", "disposition", "confirmed_group", "notes"}):
        path = row["path"].strip().replace("\\", "/")
        action, group, notes = (row[key].strip() for key in ("disposition", "confirmed_group", "notes"))
        if path not in inventory or path in decisions:
            raise ValueError(f"Unknown or repeated review path: {path}")
        if action not in {"", "include", "exclude"} or (group and (
                action != "include" or not re.fullmatch(r"[a-zA-Z0-9_.-]+", group))):
            raise ValueError(f"Invalid review decision or group ID: {path}")
        if action == "exclude":
            if not notes:
                raise ValueError(f"Explain why the image was excluded: {path}")
            excluded.append(dict(path=path, notes=notes))
        if action:
            pending.discard(path)
        decisions[path] = (action, group)
    if pending:
        raise ValueError(f"{len(pending)} audit candidates still await review")
    clusters = defaultdict(list)
    for path, (split, label) in inventory.items():
        action, group = decisions.get(path, ("", ""))
        if action == "exclude":
            continue
        group_id = f"reviewed:{group.casefold()}" if group else f"image:{path}"
        clusters[group_id].append((path, split, label))
    rows, moved = [], []
    for group, images in clusters.items():
        if len({label for _, _, label in images}) > 1:
            raise ValueError(f"Confirmed group still contains conflicting labels: {group}")
        split = max((original for _, original, _ in images), key=SPLIT_PRIORITY.__getitem__)
        for path, original, label in images:
            rows.append(dict(relative_path=path, split=split, labels=label, group_id=group))
            if original != split:
                moved.append(dict(path=path, group_id=group, original_split=original, draft_split=split))
    rows.sort(key=lambda row: row["relative_path"])
    with TemporaryDirectory(prefix="roboflow-manifest-") as temporary:
        staged = Path(temporary) / "manifest.csv"
        write_csv(staged, FIELDS, rows)
        _, summary = validate_manifest(staged, root, classes, "single")
    for split, counts in summary["class_counts"].items():
        if any(count == 0 for count in counts.values()):
            raise ValueError(f"Missing class in {split}")
    output.mkdir(parents=True, exist_ok=False)
    manifest = output / "manifest_draft.csv"
    write_csv(manifest, FIELDS, rows)
    write_csv(output / "split_changes.csv", ["path", "group_id", "original_split", "draft_split"], moved)
    write_csv(output / "excluded_from_manifest.csv", ["path", "notes"], excluded)
    (output / "classes.json").write_text(json.dumps(classes, indent=2) + "\n", encoding="utf-8")
    summary.update(status="draft", split_policy="preserve singleton split; keep reviewed clusters together, test > val > train",
                   excluded=len(excluded), changed_splits=len(moved), original_split_counts=dict(Counter(
                       split for split, _ in inventory.values())))
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = build(args.image_root, args.audit, args.review, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"ERROR: {error}\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
