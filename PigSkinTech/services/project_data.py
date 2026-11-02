"""Read the actual training run and manifest used by the PigSkinResearchStudio."""
import csv
import hashlib
import json
import os
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CODE_ROOT = APP_ROOT.parent.parent

CLASS_NAMES_VI = {
    "Healthy": "Khỏe mạnh",
    "Infected_Bacterial_Erysipelas": "Bệnh đóng dấu lợn",
    "Infected_Bacterial_Greasy_Pig_Disease": "Viêm da tiết dịch",
    "Infected_Environmental_Dermatitis": "Viêm da do môi trường",
    "Infected_Environmental_Sunburn": "Cháy nắng",
    "Infected_Fungal_Pityriasis_Rosea": "Vảy phấn hồng",
    "Infected_Fungal_Ringworm": "Nấm da (hắc lào)",
    "Infected_Parasitic_Mange": "Ghẻ",
    "Infected_Viral_Foot_and_Mouth_Disease": "Lở mồm long móng",
    "Infected_Viral_Swinepox": "Đậu heo",
}


def display_class(name):
    """Return a Vietnamese display name while keeping the model's original label."""
    return CLASS_NAMES_VI.get(name, name.replace("_", " "))


def training_roots():
    configured = os.environ.get("PIGSKIN_RESEARCH_ROOT", "").strip()
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend([
        CODE_ROOT / "PigSkinResearchStudio",
        APP_ROOT.parent / "ml_workspace",
    ])
    roots = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_dir() and resolved not in roots:
            roots.append(resolved)
    return roots


def _run_candidates():
    candidates = []
    for root in training_roots():
        runs_dir = root / "ml_workspace" / "runs"
        if not runs_dir.is_dir() and root.name == "ml_workspace":
            runs_dir = root / "runs"
        if not runs_dir.is_dir():
            continue
        for folder in runs_dir.iterdir():
            if not folder.is_dir():
                continue
            required = [folder / "best_model.pt", folder / "config.json", folder / "final_metrics.json"]
            if all(path.is_file() for path in required):
                candidates.append(folder)
    return candidates


def _read_manifest(path):
    split_counts = {"train": 0, "val": 0, "test": 0}
    class_counts = {split: {} for split in split_counts}
    total = 0
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            split = (row.get("split") or "").strip().lower()
            if split not in split_counts:
                continue
            raw_labels = (row.get("labels") or "").strip()
            try:
                labels = json.loads(raw_labels) if raw_labels.startswith("[") else [raw_labels]
            except json.JSONDecodeError:
                labels = [raw_labels]
            labels = [str(name).strip() for name in labels if str(name).strip()]
            if not labels:
                continue
            total += 1
            split_counts[split] += 1
            for name in labels:
                class_counts[split][name] = class_counts[split].get(name, 0) + 1
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "path": path,
        "total": total,
        "split_counts": split_counts,
        "class_counts": class_counts,
        "sha256": digest,
    }


def active_run():
    """Return the newest complete local run and counts read from its manifest."""
    candidates = _run_candidates()
    if not candidates:
        return None
    folder = max(candidates, key=lambda item: item.name)
    try:
        config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        metrics = json.loads((folder / "final_metrics.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    manifest_path = Path(config.get("manifest", ""))
    if not manifest_path.is_absolute():
        manifest_path = (training_roots()[0] / manifest_path).resolve()
    data = None
    if manifest_path.is_file():
        try:
            data = _read_manifest(manifest_path)
            expected = config.get("manifest_sha256")
            data["matches_run"] = not expected or data["sha256"] == expected
        except (OSError, csv.Error):
            data = None

    return {
        "name": folder.name,
        "directory": folder,
        "checkpoint": folder / "best_model.pt",
        "config_path": folder / "config.json",
        "metrics_path": folder / "final_metrics.json",
        "history_path": folder / "history.csv",
        "config": config,
        "metrics": metrics,
        "data": data,
    }


def torch_python():
    """Use the app interpreter when it has Torch; otherwise use the training venv."""
    import importlib.util
    import sys

    if importlib.util.find_spec("torch") and importlib.util.find_spec("torchvision"):
        return Path(sys.executable)
    for root in training_roots():
        candidate = root / ".venv" / "Scripts" / "python.exe"
        if candidate.is_file():
            return candidate
    return None
