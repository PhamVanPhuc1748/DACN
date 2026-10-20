"""Màn hình 1 — Trung tâm Chẩn đoán + đăng nhập."""
import io
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image
from pydantic import BaseModel

from .. import inference
from ..auth import ALL_ROLES, create_token, current_user, require, verify_password
from ..db import UPLOADS, audit, get_db, rows

router = APIRouter(prefix="/api")
MAX_BYTES = 10 * 1024 * 1024


def load_classes(db) -> list[dict]:
    return rows(db.execute("SELECT * FROM disease_classes ORDER BY id"))


def load_model(db, model_id: int | None = None) -> dict:
    q = "SELECT * FROM model_versions WHERE " + ("id=?" if model_id else "is_default=1")
    row = db.execute(q, (model_id,) if model_id else ()).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy model")
    m = dict(row)
    m["metrics"] = json.loads(m["metrics"] or "{}")
    return m


def read_image(data: bytes) -> tuple[int, int, str]:
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Ảnh vượt quá 10MB")
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
    except Exception:
        raise HTTPException(400, "File không phải ảnh hợp lệ")
    return img.width, img.height, (img.format or "jpeg").lower()


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(body: LoginIn, db=Depends(get_db)):
    row = db.execute("SELECT * FROM users WHERE username=?", (body.username,)).fetchone()
    if not row or not row["is_active"] or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    user = {k: row[k] for k in ("id", "username", "full_name", "role")}
    audit(db, user, "LOGIN")
    db.commit()
    return {"token": create_token(user), "user": user}


@router.get("/auth/me")
def me(user=Depends(current_user)):
    return user


@router.post("/predict")
async def predict(files: list[UploadFile] = File(...), pen: str = Form(""), herd_code: str = Form(""),
                  notes: str = Form(""), model_id: int | None = Form(None),
                  user=Depends(require(*ALL_ROLES)), db=Depends(get_db)):
    model, classes = load_model(db, model_id), load_classes(db)
    by_code = {c["code"]: c for c in classes}
    results = []
    for f in files[:20]:
        data = await f.read()
        w, h, fmt = read_image(data)
        r = inference.predict(data, model, classes)
        name = f"{r['sha256']}.{'jpg' if fmt == 'jpeg' else fmt}"
        (UPLOADS / name).write_bytes(data)
        uri = f"/files/uploads/{name}"
        img = db.execute("INSERT INTO images(uri, sha256, width, height, source) VALUES(?,?,?,?, 'farm')",
                         (uri, r["sha256"], w, h))
        top3 = [[by_code[t["code"]]["id"], t["prob"]] for t in r["top3"]]
        cur = db.execute(
            "INSERT INTO predictions(image_id, image_uri, model_version_id, predicted_class_id, confidence, top3, "
            "inference_ms, pen, herd_code, notes, created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (img.lastrowid, uri, model["id"], by_code[r["predicted_code"]]["id"], r["confidence"],
             json.dumps(top3), r["inference_ms"], pen, herd_code, notes, user["id"]))
        results.append({**r, "prediction_id": cur.lastrowid, "image_url": uri, "filename": f.filename,
                        "width": w, "height": h, "disease": by_code[r["predicted_code"]],
                        "model": {k: model[k] for k in ("id", "name", "task", "architecture")}})
    audit(db, user, "PREDICT", f"{len(results)} ảnh · {model['name']} · {pen}")
    db.commit()
    return results


@router.post("/predict/compare")
async def compare(file: UploadFile = File(...), model_ids: str = Form(...),
                  user=Depends(require("AI_ENGINEER", "ADMIN")), db=Depends(get_db)):
    data = await file.read()
    read_image(data)
    classes = load_classes(db)
    out = []
    for mid in [int(x) for x in model_ids.split(",") if x][:3]:
        m = load_model(db, mid)
        out.append({**inference.predict(data, m, classes),
                    "model": {k: m[k] for k in ("id", "name", "task", "architecture")}})
    return out
