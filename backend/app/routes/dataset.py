"""Màn hình 3 — Quản lý dataset & hàng đợi gán nhãn bán giám sát."""
import csv

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import inference
from ..auth import require
from ..db import ROOT, audit, get_db, rows
from .diagnose import load_classes, load_model

router = APIRouter(prefix="/api/datasets")
UNLABELED_CSV = ROOT / "data" / "splits" / "v1" / "unlabeled.csv"
CAN_VIEW = ("AI_ENGINEER", "VET", "ADMIN")


@router.get("")
def versions(user=Depends(require(*CAN_VIEW)), db=Depends(get_db)):
    out = []
    for v in rows(db.execute("SELECT * FROM dataset_versions ORDER BY id")):
        dist = rows(db.execute("""
            SELECT c.code, c.color, m.split, COUNT(DISTINCT i.stem_id) AS n
            FROM dataset_members m JOIN images i ON i.id = m.image_id
            JOIN image_labels l ON l.image_id = i.id AND l.status = 'VERIFIED'
            JOIN disease_classes c ON c.id = l.class_id
            WHERE m.dataset_version_id = ? GROUP BY c.code, m.split ORDER BY c.id""", (v["id"],)))
        splits = {r["split"]: r["n"] for r in db.execute("""
            SELECT m.split, COUNT(DISTINCT i.stem_id) AS n FROM dataset_members m
            JOIN images i ON i.id = m.image_id WHERE m.dataset_version_id = ? GROUP BY m.split""", (v["id"],))}
        leaked = db.execute("""
            SELECT COUNT(*) FROM (SELECT i.stem_id FROM dataset_members m JOIN images i ON i.id = m.image_id
            WHERE m.dataset_version_id = ? GROUP BY i.stem_id HAVING COUNT(DISTINCT m.split) > 1)""",
                            (v["id"],)).fetchone()[0]
        out.append({**v, "splits": splits, "total_stems": sum(splits.values()), "leaked_stems": leaked,
                    "distribution": dist})
    return out


@router.get("/unlabeled")
def unlabeled(user=Depends(require(*CAN_VIEW)), db=Depends(get_db)):
    items = rows(db.execute("""
        SELECT i.id, i.stem_id, i.uri, l.id AS label_id, c.code AS pseudo_code, c.name AS pseudo_name,
               l.confidence AS pseudo_conf
        FROM images i
        LEFT JOIN image_labels l ON l.image_id = i.id AND l.status = 'PSEUDO'
        LEFT JOIN disease_classes c ON c.id = l.class_id
        WHERE i.source = 'unlabeled'
          AND NOT EXISTS (SELECT 1 FROM image_labels x WHERE x.image_id = i.id AND x.status IN ('VERIFIED','REJECTED'))
        ORDER BY l.confidence DESC NULLS LAST, i.id"""))
    approved = db.execute("""SELECT COUNT(*) FROM images i JOIN image_labels l ON l.image_id = i.id
        WHERE i.source='unlabeled' AND l.status='VERIFIED'
        AND i.id NOT IN (SELECT image_id FROM dataset_members)""").fetchone()[0]
    return {"items": items, "approved_pending_release": approved, "csv_found": UNLABELED_CSV.exists(),
            "csv_path": str(UNLABELED_CSV.relative_to(ROOT))}


@router.post("/unlabeled/import-csv")
def import_csv(user=Depends(require("AI_ENGINEER", "ADMIN")), db=Depends(get_db)):
    if not UNLABELED_CSV.exists():
        raise HTTPException(404, f"Chưa có file {UNLABELED_CSV.relative_to(ROOT)} — chạy dataset_cleaner.py trước")
    existing = {r[0] for r in db.execute("SELECT stem_id FROM images WHERE source='unlabeled'")}
    n = 0
    with UNLABELED_CSV.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            stem = r.get("stem_id") or r.get("image_id")
            if stem and stem not in existing:
                db.execute("INSERT INTO images(stem_id, uri, sha256, source) VALUES(?,?,?, 'unlabeled')",
                           (stem, r.get("file_path") or r.get("relative_path"), r.get("sha256")))
                existing.add(stem)
                n += 1
    audit(db, user, "IMPORT_UNLABELED", f"{n} ảnh")
    db.commit()
    return {"imported": n}


class PseudoIn(BaseModel):
    model_id: int | None = None


@router.post("/unlabeled/pseudo-label")
def pseudo_label(body: PseudoIn, user=Depends(require("AI_ENGINEER", "ADMIN")), db=Depends(get_db)):
    model, classes = load_model(db, body.model_id), load_classes(db)
    by_code = {c["code"]: c["id"] for c in classes}
    todo = rows(db.execute("""SELECT i.id, i.stem_id, i.uri FROM images i WHERE i.source='unlabeled'
        AND NOT EXISTS (SELECT 1 FROM image_labels l WHERE l.image_id = i.id)"""))
    for img in todo:
        path = ROOT / img["uri"] if img["uri"] else None
        data = path.read_bytes() if path and path.is_file() else img["stem_id"].encode()
        r = inference.predict(data, model, classes)
        db.execute("INSERT INTO image_labels(image_id, class_id, status, annotator, confidence) "
                   "VALUES(?,?, 'PSEUDO', ?, ?)", (img["id"], by_code[r["predicted_code"]], model["name"],
                                                   r["confidence"]))
    audit(db, user, "PSEUDO_LABEL", f"{len(todo)} ảnh · {model['name']}")
    db.commit()
    return {"labeled": len(todo), "model": model["name"]}


class LabelReviewIn(BaseModel):
    action: str             # approve | reject
    class_code: str | None = None


@router.post("/labels/{label_id}/review")
def review_label(label_id: int, body: LabelReviewIn, user=Depends(require(*CAN_VIEW)), db=Depends(get_db)):
    if body.action not in ("approve", "reject"):
        raise HTTPException(400, "action phải là approve hoặc reject")
    lbl = db.execute("SELECT * FROM image_labels WHERE id=? AND status='PSEUDO'", (label_id,)).fetchone()
    if not lbl:
        raise HTTPException(404, "Nhãn không tồn tại hoặc đã duyệt")
    class_id = lbl["class_id"]
    if body.class_code:
        c = db.execute("SELECT id FROM disease_classes WHERE code=?", (body.class_code,)).fetchone()
        if not c:
            raise HTTPException(400, "Mã lớp bệnh không hợp lệ")
        class_id = c["id"]
    db.execute("UPDATE image_labels SET status=?, class_id=?, annotator=?, verified_by_vet=?, "
               "reviewed_at=datetime('now','localtime') WHERE id=?",
               ("VERIFIED" if body.action == "approve" else "REJECTED", class_id, user["username"],
                int(user["role"] == "VET"), label_id))
    audit(db, user, "LABEL_" + body.action.upper(), f"label #{label_id}")
    db.commit()
    return {"ok": True}


class VersionIn(BaseModel):
    version: str
    notes: str = ""


@router.post("/versions")
def create_version(body: VersionIn, user=Depends(require("AI_ENGINEER", "ADMIN")), db=Depends(get_db)):
    """Phiên bản mới = phiên bản gần nhất + ảnh unlabeled đã duyệt (chỉ thêm vào train, giữ test đóng băng)."""
    if db.execute("SELECT 1 FROM dataset_versions WHERE version=?", (body.version,)).fetchone():
        raise HTTPException(400, "Phiên bản đã tồn tại")
    prev = db.execute("SELECT id, seed FROM dataset_versions ORDER BY id DESC LIMIT 1").fetchone()
    cur = db.execute("INSERT INTO dataset_versions(name, version, seed, notes) VALUES(?,?,?,?)",
                     (f"Pig Skin {body.version}", body.version, prev["seed"], body.notes))
    vid = cur.lastrowid
    db.execute("INSERT INTO dataset_members SELECT ?, image_id, split FROM dataset_members WHERE dataset_version_id=?",
               (vid, prev["id"]))
    added = db.execute("""INSERT INTO dataset_members SELECT DISTINCT ?, i.id, 'train' FROM images i
        JOIN image_labels l ON l.image_id = i.id AND l.status='VERIFIED'
        WHERE i.source='unlabeled' AND i.id NOT IN (SELECT image_id FROM dataset_members)""", (vid,)).rowcount
    audit(db, user, "CREATE_DATASET_VERSION", f"{body.version} (+{added} ảnh train)")
    db.commit()
    return {"id": vid, "added": added}
