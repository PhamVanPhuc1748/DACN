"""Read the actual training run, manifest, and disease class config used by PigSkinTech."""
import csv
import hashlib
import json
import os
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CODE_ROOT = APP_ROOT.parent.parent
CLASSES_JSON_PATH = APP_ROOT / "models" / "classes.json"
ACTIVE_MODEL_STATE_PATH = APP_ROOT / "models" / "active_model.json"

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


def load_classes_config() -> dict:
    """Load disease class metadata and treatment protocols from models/classes.json."""
    if CLASSES_JSON_PATH.is_file():
        try:
            data = json.loads(CLASSES_JSON_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {
        code: {
            "code": code,
            "name_vi": name_vi,
            "danger_level": "An toàn" if code == "Healthy" else "Trung bình",
            "symptoms": "Triệu chứng tổn thương trên bề mặt da heo.",
            "prevention": "Giữ vệ sinh chuồng trại, tiêm phòng và sát khuẩn định kỳ.",
            "treatment": "Theo dõi lâm sàng và tham khảo ý kiến bác sĩ thú y.",
        }
        for code, name_vi in CLASS_NAMES_VI.items()
    }


def save_classes_config(data: dict) -> None:
    CLASSES_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLASSES_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_class_info(name: str) -> dict:
    if not name:
        return {
            "code": "",
            "name_vi": "Chưa xác định",
            "danger_level": "Chưa rõ",
            "symptoms": "Chưa có dữ liệu triệu chứng.",
            "prevention": "Chưa có khuyến nghị phòng ngừa.",
            "treatment": "Cần chuyên gia thú y thẩm định.",
        }
    cfg = load_classes_config()
    if name in cfg:
        return cfg[name]
    return {
        "code": name,
        "name_vi": CLASS_NAMES_VI.get(name, name.replace("_", " ")),
        "danger_level": "Trung bình",
        "symptoms": "Chưa cập nhật mô tả triệu chứng.",
        "prevention": "Giữ chuồng khô thoáng và cách ly theo dõi.",
        "treatment": "Tham khảo bác sĩ thú y để có phác đồ điều trị.",
    }


def upsert_class_info(code: str, name_vi: str, danger_level: str, symptoms: str, prevention: str, treatment: str) -> dict:
    code = code.strip()
    if not code:
        raise ValueError("Mã lớp bệnh (class code) không được để trống.")
    cfg = load_classes_config()
    cfg[code] = {
        "code": code,
        "name_vi": name_vi.strip() or code,
        "danger_level": danger_level.strip() or "Trung bình",
        "symptoms": symptoms.strip(),
        "prevention": prevention.strip(),
        "treatment": treatment.strip(),
    }
    save_classes_config(cfg)
    return cfg[code]


def delete_class_info(code: str) -> bool:
    cfg = load_classes_config()
    if code not in cfg:
        return False
    del cfg[code]
    save_classes_config(cfg)
    return True


def list_class_keys() -> list[str]:
    cfg = load_classes_config()
    if cfg:
        return list(cfg.keys())
    run = active_run()
    if run and run.get("config", {}).get("classes"):
        return list(run["config"]["classes"])
    return list(CLASS_NAMES_VI.keys())


def display_class(name):
    """Return a Vietnamese display name while keeping the model's original label."""
    if not name:
        return "Chưa xác định"
    cfg = load_classes_config()
    if name in cfg and cfg[name].get("name_vi"):
        return cfg[name]["name_vi"]
    return CLASS_NAMES_VI.get(name, str(name).replace("_", " "))


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
    runs_directories = []
    for root in training_roots():
        runs_dir = root / "ml_workspace" / "runs"
        if not runs_dir.is_dir() and root.name == "ml_workspace":
            runs_dir = root / "runs"
        if runs_dir.is_dir() and runs_dir not in runs_directories:
            runs_directories.append(runs_dir)

    bundled_runs = APP_ROOT / "models" / "runs"
    if bundled_runs.is_dir() and bundled_runs not in runs_directories:
        runs_directories.append(bundled_runs)

    for runs_dir in runs_directories:
        for folder in runs_dir.iterdir():
            if not folder.is_dir():
                continue
            required = [folder / "best_model.pt", folder / "config.json", folder / "final_metrics.json"]
            if all(path.is_file() for path in required):
                candidates.append(folder)
    return sorted(candidates, key=lambda item: item.name, reverse=True)


def list_model_runs() -> list[dict]:
    """Return all available training runs with best_model.pt checkpoints."""
    active = active_run()
    active_ckpt = str(active["checkpoint"].resolve()) if active else ""
    items = []
    for folder in _run_candidates():
        ckpt = folder / "best_model.pt"
        try:
            cfg = json.loads((folder / "config.json").read_text(encoding="utf-8"))
            metrics = json.loads((folder / "final_metrics.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cfg, metrics = {}, {}
        items.append({
            "name": folder.name,
            "directory": str(folder),
            "checkpoint": str(ckpt),
            "model": cfg.get("model", "mobilenet_v2"),
            "classes_count": len(cfg.get("classes", [])),
            "val_f1": metrics.get("best_val_macro_f1"),
            "test_acc": metrics.get("test_metrics", {}).get("accuracy"),
            "is_active": str(ckpt.resolve()) == active_ckpt,
        })
    return items


def set_active_checkpoint(checkpoint_path: str) -> dict:
    p = Path(checkpoint_path)
    if p.is_dir():
        p = p / "best_model.pt"
    if not p.is_file():
        raise FileNotFoundError(f"Không tìm thấy trọng số mô hình tại: {p}")
    ACTIVE_MODEL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_MODEL_STATE_PATH.write_text(
        json.dumps({"checkpoint": str(p.resolve())}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return active_run() or {}


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
    """Return the selected or newest complete local run and counts read from its manifest."""
    candidates = _run_candidates()
    if not candidates:
        return None
    folder = None
    if ACTIVE_MODEL_STATE_PATH.is_file():
        try:
            saved = json.loads(ACTIVE_MODEL_STATE_PATH.read_text(encoding="utf-8"))
            ckpt_path = Path(saved.get("checkpoint", ""))
            if ckpt_path.is_file() and (ckpt_path.parent / "config.json").is_file():
                folder = ckpt_path.parent
        except (OSError, json.JSONDecodeError):
            folder = None
    if folder is None:
        folder = max(candidates, key=lambda item: item.name)
    try:
        config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        metrics = json.loads((folder / "final_metrics.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    manifest_path = Path(config.get("manifest", ""))
    if not manifest_path.is_absolute():
        roots = training_roots()
        manifest_root = roots[0] if roots else folder
        manifest_path = (manifest_root / manifest_path).resolve()
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
