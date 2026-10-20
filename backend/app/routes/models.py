"""Màn hình 4 — Model registry & benchmark."""
import json

from fastapi import APIRouter, Depends

from ..auth import ALL_ROLES, require
from ..db import ROOT, audit, get_db, rows

router = APIRouter(prefix="/api")
MODELS_DIR = ROOT / "ml_workspace" / "models"
EXP_DIR = ROOT / "ml_workspace" / "experiments"
ENGINEER = ("AI_ENGINEER", "ADMIN")


@router.get("/models")
def list_models(user=Depends(require(*ALL_ROLES)), db=Depends(get_db)):
    out = rows(db.execute("""SELECT m.*, d.version AS dataset_version FROM model_versions m
                             LEFT JOIN dataset_versions d ON d.id = m.dataset_version_id ORDER BY m.id"""))
    for m in out:
        m["metrics"] = json.loads(m["metrics"] or "{}")
        m["config"] = json.loads(m["config"] or "{}")
        m["artifact_exists"] = bool(m["artifact_uri"]) and (ROOT / m["artifact_uri"]).is_file()
    return out


@router.post("/models/{model_id}/default")
def set_default(model_id: int, user=Depends(require(*ENGINEER)), db=Depends(get_db)):
    db.execute("UPDATE model_versions SET is_default = (id = ?)", (model_id,))
    audit(db, user, "SET_DEFAULT_MODEL", f"model #{model_id}")
    db.commit()
    return {"ok": True}


@router.post("/models/scan")
def scan(user=Depends(require(*ENGINEER)), db=Depends(get_db)):
    """Đăng ký các file trọng số mới trong ml_workspace/models (chưa có metrics → điền sau)."""
    known = {r[0] for r in db.execute("SELECT artifact_uri FROM model_versions")}
    added = []
    for p in sorted(MODELS_DIR.glob("*")) if MODELS_DIR.is_dir() else []:
        rel = p.relative_to(ROOT).as_posix()
        if p.suffix in (".pt", ".pth", ".onnx") and rel not in known:
            task = "detection" if p.stem.lower().startswith("yolo") else "classification"
            db.execute("INSERT OR IGNORE INTO model_versions(name, architecture, task, artifact_uri, metrics, latency_ms)"
                       " VALUES(?,?,?,?, '{}', 10)", (p.stem, p.stem, task, rel))
            added.append(rel)
    audit(db, user, "SCAN_MODELS", f"{len(added)} model mới")
    db.commit()
    return {"added": added}


@router.get("/experiments")
def experiments(user=Depends(require(*ENGINEER))):
    if not EXP_DIR.is_dir():
        return {"dir": "ml_workspace/experiments", "files": []}
    files = [{"name": p.relative_to(EXP_DIR).as_posix(), "url": f"/files/experiments/{p.relative_to(EXP_DIR).as_posix()}",
              "kind": "image" if p.suffix.lower() in (".png", ".jpg", ".svg") else "file"}
             for p in sorted(EXP_DIR.rglob("*")) if p.is_file()]
    return {"dir": "ml_workspace/experiments", "files": files}
