"""Màn hình 2 — Nhật ký ca bệnh & hàng đợi thẩm định của bác sĩ thú y."""
import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..auth import ALL_ROLES, require
from ..db import audit, get_db, get_settings, rows

router = APIRouter(prefix="/api/cases")

BASE = """
SELECT p.id, p.image_uri, p.confidence, p.top3, p.inference_ms, p.pen, p.herd_code, p.notes,
       p.review_status, p.review_note, p.created_at, p.image_id,
       pc.code AS predicted_code, pc.name AS predicted_name, pc.color AS predicted_color,
       fc.code AS final_code, fc.name AS final_name,
       m.name AS model_name, u.full_name AS created_by_name, r.full_name AS reviewed_by_name
FROM predictions p
JOIN disease_classes pc ON pc.id = p.predicted_class_id
LEFT JOIN disease_classes fc ON fc.id = p.final_class_id
LEFT JOIN model_versions m ON m.id = p.model_version_id
LEFT JOIN users u ON u.id = p.created_by
LEFT JOIN users r ON r.id = p.reviewed_by
"""


def query_cases(db, date_from=None, date_to=None, pen=None, class_code=None, low_conf=False, status=None,
                limit=500):
    where, args = [], []
    if date_from:
        where.append("date(p.created_at) >= date(?)"); args.append(date_from)
    if date_to:
        where.append("date(p.created_at) <= date(?)"); args.append(date_to)
    if pen:
        where.append("p.pen = ?"); args.append(pen)
    if class_code:
        where.append("pc.code = ?"); args.append(class_code)
    if low_conf:
        where.append("p.confidence < ?"); args.append(float(get_settings(db)["review_threshold"]))
    if status == "PENDING":
        where.append("p.review_status = 'PENDING'")
    elif status == "REVIEWED":
        where.append("p.review_status != 'PENDING'")
    sql = BASE + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY p.created_at DESC LIMIT ?"
    out = rows(db.execute(sql, (*args, limit)))
    names = {r["id"]: (r["code"], r["name"]) for r in db.execute("SELECT id, code, name FROM disease_classes")}
    for r in out:
        r["top3"] = [{"code": names[c][0], "name": names[c][1], "prob": p} for c, p in json.loads(r["top3"] or "[]")]
    return out


@router.get("")
def list_cases(date_from: str | None = None, date_to: str | None = None, pen: str | None = None,
               class_code: str | None = None, low_conf: bool = False, status: str | None = None,
               user=Depends(require(*ALL_ROLES)), db=Depends(get_db)):
    return {"items": query_cases(db, date_from, date_to, pen, class_code, low_conf, status),
            "pens": [r[0] for r in db.execute("SELECT DISTINCT pen FROM predictions WHERE pen != '' ORDER BY pen")]}


@router.get("/export.csv")
def export_csv(date_from: str | None = None, date_to: str | None = None, pen: str | None = None,
               class_code: str | None = None, low_conf: bool = False, status: str | None = None,
               user=Depends(require(*ALL_ROLES)), db=Depends(get_db)):
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM để Excel hiển thị đúng tiếng Việt
    w = csv.writer(buf)
    w.writerow(["Mã ca", "Thời gian", "Khu chuồng", "Mã đàn", "AI dự đoán", "Độ tin cậy", "Model",
                "Trạng thái", "Kết luận bác sĩ", "Ghi chú BS", "Biểu hiện lâm sàng"])
    for r in query_cases(db, date_from, date_to, pen, class_code, low_conf, status, limit=100_000):
        w.writerow([r["id"], r["created_at"], r["pen"], r["herd_code"], r["predicted_code"],
                    f"{r['confidence']:.1%}", r["model_name"], r["review_status"], r["final_code"] or "",
                    r["review_note"] or "", r["notes"] or ""])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=ca-benh.csv"})


class ReviewIn(BaseModel):
    class_code: str | None = None   # None = xác nhận AI đúng
    note: str = ""


@router.post("/{case_id}/review")
def review(case_id: int, body: ReviewIn, user=Depends(require("VET")), db=Depends(get_db)):
    p = db.execute("SELECT id, image_id, predicted_class_id FROM predictions WHERE id=?", (case_id,)).fetchone()
    if not p:
        raise HTTPException(404, "Không tìm thấy ca bệnh")
    if body.class_code:
        c = db.execute("SELECT id FROM disease_classes WHERE code=?", (body.class_code,)).fetchone()
        if not c:
            raise HTTPException(400, "Mã lớp bệnh không hợp lệ")
        if not body.note.strip():
            raise HTTPException(400, "Cần ghi chú lý do lâm sàng khi hiệu chỉnh")
        class_id = c["id"]
    else:
        class_id = p["predicted_class_id"]
    status = "CONFIRMED" if class_id == p["predicted_class_id"] else "CORRECTED"

    db.execute("UPDATE predictions SET review_status=?, final_class_id=?, review_note=?, reviewed_by=? WHERE id=?",
               (status, class_id, body.note, user["id"], case_id))
    db.execute("DELETE FROM image_labels WHERE image_id=? AND verified_by_vet=1", (p["image_id"],))
    db.execute("INSERT INTO image_labels(image_id, class_id, status, annotator, verified_by_vet, note, reviewed_at) "
               "VALUES(?,?, 'VERIFIED', ?, 1, ?, datetime('now','localtime'))",
               (p["image_id"], class_id, user["username"], body.note))
    audit(db, user, "REVIEW_" + status, f"ca #{case_id} → {body.class_code or 'AI đúng'}")
    db.commit()
    return {"ok": True, "review_status": status}
