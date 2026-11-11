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

APP_MODEL_NAMES = {
    "mobilenet_v2": "MobileNetV2",
    "efficientnet_b0": "EfficientNet-B0",
    "mobilenet_v3_large": "MobileNetV3-Large",
}

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
    try:
        from services.store import sync_disease_catalog_to_sql

        sync_disease_catalog_to_sql(data)
    except Exception:
        pass


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
    """Return unique available training runs with best_model.pt checkpoints."""
    active = active_run()
    active_ckpt = str(active["checkpoint"].resolve()) if active else ""
    items = []
    seen_checkpoints = set()
    for folder in _run_candidates():
        ckpt = folder / "best_model.pt"
        try:
            fingerprint = hashlib.sha256(ckpt.read_bytes()).hexdigest()
            cfg = json.loads((folder / "config.json").read_text(encoding="utf-8"))
            metrics = json.loads((folder / "final_metrics.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if fingerprint in seen_checkpoints:
            if str(ckpt.resolve()) != active_ckpt:
                continue
            items = [item for item in items if item.get("fingerprint") != fingerprint]
        seen_checkpoints.add(fingerprint)
        model_code = cfg.get("model", "mobilenet_v2")
        display_arch = APP_MODEL_NAMES.get(model_code, model_code)
        items.append({
            "name": folder.name,
            "run_name": folder.name,
            "directory": str(folder),
            "checkpoint": str(ckpt),
            "model": model_code,
            "model_label": display_arch,
            "display_name": f"{display_arch} ({folder.name})",
            "fingerprint": fingerprint,
            "classes_count": len(cfg.get("classes", [])),
            "val_f1": metrics.get("best_val_macro_f1"),
            "test_acc": metrics.get("test_metrics", {}).get("accuracy"),
            "test_macro_f1": metrics.get("test_metrics", {}).get("macro_f1"),
            "best_epoch": metrics.get("best_epoch"),
            "is_active": str(ckpt.resolve()) == active_ckpt,
        })
    return items


def available_model_runs() -> list[dict]:
    """Return available runs sorted with MobileNetV2 and EfficientNet-B0 first (merged from DACN-devP)."""
    runs = []
    seen_models = set()
    for folder in _run_candidates():
        try:
            config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
            metrics = json.loads((folder / "final_metrics.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        model_name = str(config.get("model", "")).strip()
        if model_name not in APP_MODEL_NAMES or model_name in seen_models:
            continue
        seen_models.add(model_name)
        runs.append({
            "run_name": folder.name,
            "name": folder.name,
            "model": model_name,
            "model_label": APP_MODEL_NAMES[model_name],
            "directory": folder,
            "checkpoint": folder / "best_model.pt",
            "config_path": folder / "config.json",
            "metrics_path": folder / "final_metrics.json",
            "history_path": folder / "history.csv",
            "config": config,
            "metrics": metrics,
        })
    order = {"mobilenet_v2": 0, "efficientnet_b0": 1, "mobilenet_v3_large": 2}
    return sorted(runs, key=lambda item: (order.get(item["model"], 99), item["run_name"]))


def read_checkpoint_details(checkpoint_path: str | Path) -> dict:
    """Read model architecture, class list, training settings, and metrics beside a checkpoint."""
    p = Path(checkpoint_path)
    if p.is_dir():
        p = p / "best_model.pt"
    if not p.is_file():
        # Try matching by run_name or model code in _run_candidates
        for cand in _run_candidates():
            if cand.name.lower() == str(checkpoint_path).strip().lower():
                p = cand / "best_model.pt"
                break
    if not p.is_file():
        raise FileNotFoundError(f"Không tìm thấy trọng số mô hình tại: {p}")
    config_path = p.parent / "config.json"
    metrics_path = p.parent / "final_metrics.json"
    if not config_path.is_file() or not metrics_path.is_file():
        raise ValueError("Run model cần có best_model.pt, config.json và final_metrics.json.")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Không đọc được config.json hoặc final_metrics.json của model đã chọn.") from exc
    if not isinstance(config, dict) or not isinstance(metrics, dict):
        raise ValueError("Thông tin model trong các file cấu hình không đúng định dạng.")
    classes = config.get("classes")
    if not isinstance(classes, list) or not classes or not all(isinstance(x, str) for x in classes) or config.get("model") not in {
        "mobilenet_v2", "mobilenet_v3_large", "efficientnet_b0"
    }:
        raise ValueError("Model đã chọn thiếu danh sách lớp hoặc kiến trúc chưa được hỗ trợ.")
    test_metrics = metrics.get("test_metrics", {})
    if not isinstance(test_metrics, dict):
        test_metrics = {}
    return {
        "checkpoint": p.resolve(),
        "run_name": p.parent.name,
        "model": config["model"],
        "classes": classes,
        "image_size": config.get("image_size"),
        "epochs": config.get("epochs"),
        "batch_size": config.get("batch_size"),
        "best_epoch": metrics.get("best_epoch"),
        "val_macro_f1": metrics.get("best_val_macro_f1"),
        "test_accuracy": test_metrics.get("accuracy"),
        "test_macro_f1": test_metrics.get("macro_f1"),
        "config": config,
        "metrics": metrics,
    }


def set_active_checkpoint(checkpoint_path: str) -> dict:
    details = read_checkpoint_details(checkpoint_path)
    p = details["checkpoint"]
    ACTIVE_MODEL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_MODEL_STATE_PATH.write_text(
        json.dumps(
            {"checkpoint": str(p), "run_name": p.parent.name},
            ensure_ascii=False,
            indent=2,
        ),
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


def _enrich_metrics(metrics: dict) -> dict:
    """Ensure metrics dict exposes both raw test_metrics.per_class and normalized per_class_f1 / accuracy from real evaluation."""
    if not isinstance(metrics, dict):
        return {}
    out = dict(metrics)
    test_m = out.get("test_metrics") or {}
    per_cls = test_m.get("per_class") or {}
    if per_cls and "per_class_f1" not in out:
        out["per_class_f1"] = {
            cls_code: float(vals.get("f1", 0.0)) if isinstance(vals, dict) else float(vals)
            for cls_code, vals in per_cls.items()
        }
    if "accuracy" not in out and "accuracy" in test_m:
        out["accuracy"] = float(test_m["accuracy"])
    if "macro_f1" not in out:
        out["macro_f1"] = float(test_m.get("macro_f1") or out.get("best_val_macro_f1") or 0.0)
    return out


def active_run(run_name: str | None = None):
    """Return the selected or newest complete local run and counts read from its manifest."""
    candidates = _run_candidates()
    if not candidates:
        return None
    folder = None
    if run_name:
        target = str(run_name).strip().lower()
        for item in candidates:
            if item.name.lower() == target:
                folder = item
                break
        if folder is None:
            for item in candidates:
                try:
                    cfg = json.loads((item / "config.json").read_text(encoding="utf-8"))
                    m_code = str(cfg.get("model", "")).lower()
                    m_lbl = APP_MODEL_NAMES.get(m_code, m_code).lower()
                    if target in (m_code, m_lbl):
                        folder = item
                        break
                except Exception:
                    pass

    if folder is None and ACTIVE_MODEL_STATE_PATH.is_file():
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
        metrics = _enrich_metrics(json.loads((folder / "final_metrics.json").read_text(encoding="utf-8")))
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

    model_code = config.get("model", "mobilenet_v2")
    return {
        "name": folder.name,
        "run_name": folder.name,
        "model": model_code,
        "model_label": APP_MODEL_NAMES.get(model_code, model_code),
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
