"""Read the actual training run, manifest, and disease class config used by PigSkinTech."""
import csv
import hashlib
import json
import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
CODE_ROOT = APP_ROOT.parent.parent
CLASSES_JSON_PATH = APP_ROOT / "models" / "classes.json"
ACTIVE_MODEL_STATE_PATH = APP_ROOT / "models" / "active_model.json"

CLASS_NAMES_VI = {
    "Healthy": "Khỏe mạnh",
    "Infected_Bacterial_Erysipelas": "Đóng dấu heo",
    "Infected_Bacterial_Exudative_Epidermitis": "Viêm da tiết dịch",
    "Infected_Fungal_Ringworm": "Nấm da",
    "Infected_Parasitic_Scabies": "Ghẻ ngứa",
    "Infected_Viral_African_Swine_Fever": "Dịch tả lợn châu Phi",
    "Infected_Viral_Classical_Swine_Fever": "Dịch tả lợn cổ điển",
    "Infected_Viral_Foot_and_Mouth_Disease": "Lở mồm long móng",
    "Infected_Viral_Porcine_Dermatitis_and_Nephropathy_Syndrome": "Hội chứng PDNS",
    "Infected_Viral_Swinepox": "Đậu heo",
}

APP_MODEL_NAMES = {
    "mobilenet_v2": "MobileNetV2",
    "efficientnet_b0": "EfficientNet-B0",
}
APP_MODEL_MANIFEST_SHA256 = "dba25e5585884d3bcb7039e1e6bd921ab73e123cf53334792e973742efe9ea99"


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
    """Discover candidate roots for training runs and manifests."""
    paths = []
    override = os.environ.get("PIGSKIN_RESEARCH_ROOT")
    if override:
        paths.append(Path(override))
    paths.extend([
        APP_ROOT / "models",
        CODE_ROOT / "PigSkinResearchStudio",
        CODE_ROOT / "PigSkinTech" / "ml_workspace",
        APP_ROOT.parent / "ml_workspace",
    ])
    seen = set()
    ordered = []
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved not in seen and resolved.exists():
            seen.add(resolved)
            ordered.append(resolved)
    return ordered


def _run_candidates():
    candidates = []
    for root in training_roots():
        subfolders = [root / "runs", root / "ml_workspace" / "runs"] if root.is_dir() else []
        for parent in [root, *subfolders]:
            if not parent.is_dir():
                continue
            for folder in parent.iterdir():
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
    if not path or not path.is_file():
        return None
    counts = {"train": 0, "val": 0, "test": 0, "other": 0}
    per_class = {}
    hasher = hashlib.sha256()
    with path.open("rb") as raw:
        while chunk := raw.read(65536):
            hasher.update(chunk)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            split = (row.get("split") or "").strip().lower()
            if split in counts:
                counts[split] += 1
            else:
                counts["other"] += 1
            label = row.get("label") or "unknown"
            per_class[label] = per_class.get(label, 0) + 1
    total = sum(counts.values())
    return {
        "path": path,
        "sha256": hasher.hexdigest(),
        "total": total,
        "counts": counts,
        "per_class": per_class,
    }


def active_run(run_name=None):
    """Return a complete local run, optionally selecting its exact run folder or active checkpoint."""
    candidates = _run_candidates()
    if not candidates:
        return None
    folder = None
    if run_name:
        folder = next((item for item in candidates if item.name == run_name), None)
    elif ACTIVE_MODEL_STATE_PATH.is_file():
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

    manifest_path = Path(config.get("manifest_path", ""))
    manifest_info = None
    if manifest_path.is_file():
        manifest_info = _read_manifest(manifest_path)
    else:
        for root in training_roots():
            candidate = root / "data" / "splits" / "manifest_v4_dedup_leakage_clean.csv"
            if candidate.is_file():
                manifest_info = _read_manifest(candidate)
                break

    return {
        "name": folder.name,
        "directory": folder,
        "checkpoint": folder / "best_model.pt",
        "config": config,
        "metrics": metrics,
        "manifest": manifest_info,
    }


def available_model_runs():
    """Choose one comparable checkpoint per supported architecture by validation macro-F1."""
    best = {}
    for folder in _run_candidates():
        try:
            config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
            model_name = config.get("model")
            if model_name not in APP_MODEL_NAMES:
                continue
            if config.get("manifest_sha256") != APP_MODEL_MANIFEST_SHA256:
                continue
            val_file = folder / "best_validation.json"
            if val_file.is_file():
                validation = json.loads(val_file.read_text(encoding="utf-8"))
                macro_f1 = float(validation.get("macro_f1", 0))
            else:
                final_file = folder / "final_metrics.json"
                final_data = json.loads(final_file.read_text(encoding="utf-8")) if final_file.is_file() else {}
                macro_f1 = float(final_data.get("best_val_macro_f1", 0))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        previous = best.get(model_name)
        if previous is None or (macro_f1, folder.name) > (previous["validation_macro_f1"], previous["name"]):
            run = active_run(folder.name)
            if run:
                run["validation_macro_f1"] = macro_f1
                best[model_name] = run
    return best


def torch_python():
    """Use the app interpreter when it has Torch; otherwise use the training venv."""
    import importlib.util
    if importlib.util.find_spec("torch") is not None:
        return sys.executable
    for root in training_roots():
        for candidate in [
            root / ".venv" / "Scripts" / "python.exe",
            root / "venv" / "Scripts" / "python.exe",
            root.parent / ".venv" / "Scripts" / "python.exe",
        ]:
            if candidate.is_file():
                return str(candidate)
    return sys.executable
