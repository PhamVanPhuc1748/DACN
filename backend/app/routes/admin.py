"""Màn hình 6 — Cẩm nang thú y & quản trị hệ thống."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import ALL_ROLES, hash_password, require
from ..db import audit, get_db, get_settings, rows

router = APIRouter(prefix="/api")
admin = require("ADMIN")


@router.get("/diseases")
def diseases(user=Depends(require(*ALL_ROLES)), db=Depends(get_db)):
    return rows(db.execute("SELECT * FROM disease_classes ORDER BY id"))


@router.get("/settings")
def read_settings(user=Depends(require(*ALL_ROLES)), db=Depends(get_db)):
    return get_settings(db)


LIMITS = {"default_conf_threshold": (0, 1), "review_threshold": (0, 1),
          "outbreak_threshold": (1, 1000), "outbreak_window_days": (1, 90)}


@router.put("/settings")
def write_settings(body: dict[str, float], user=Depends(admin), db=Depends(get_db)):
    for k, v in body.items():
        if k not in LIMITS:
            raise HTTPException(400, f"Không có cấu hình {k}")
        lo, hi = LIMITS[k]
        if not lo <= v <= hi:
            raise HTTPException(400, f"{k} phải nằm trong [{lo}, {hi}]")
        db.execute("UPDATE settings SET value=? WHERE key=?", (str(v if hi == 1 else int(v)), k))
    audit(db, user, "UPDATE_SETTINGS", ", ".join(f"{k}={v}" for k, v in body.items()))
    db.commit()
    return get_settings(db)


@router.get("/admin/users")
def users(user=Depends(admin), db=Depends(get_db)):
    return rows(db.execute("SELECT id, username, full_name, role, is_active, created_at FROM users ORDER BY id"))


class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    full_name: str = ""
    password: str = Field(min_length=6)
    role: str


class UserPatch(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=6)


@router.post("/admin/users")
def create_user(body: UserIn, user=Depends(admin), db=Depends(get_db)):
    if body.role not in ALL_ROLES:
        raise HTTPException(400, "Role không hợp lệ")
    if db.execute("SELECT 1 FROM users WHERE username=?", (body.username,)).fetchone():
        raise HTTPException(400, "Tên đăng nhập đã tồn tại")
    db.execute("INSERT INTO users(username, full_name, password_hash, role) VALUES(?,?,?,?)",
               (body.username, body.full_name, hash_password(body.password), body.role))
    audit(db, user, "CREATE_USER", f"{body.username} ({body.role})")
    db.commit()
    return {"ok": True}


@router.patch("/admin/users/{user_id}")
def update_user(user_id: int, body: UserPatch, user=Depends(admin), db=Depends(get_db)):
    if body.role and body.role not in ALL_ROLES:
        raise HTTPException(400, "Role không hợp lệ")
    if user_id == user["id"] and (body.is_active is False or (body.role and body.role != "ADMIN")):
        raise HTTPException(400, "Không thể tự khóa hoặc tự hạ quyền tài khoản đang đăng nhập")
    sets = {k: v for k, v in body.model_dump(exclude_none=True).items() if k != "password"}
    if body.password:
        sets["password_hash"] = hash_password(body.password)
    if sets:
        db.execute(f"UPDATE users SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?", (*sets.values(), user_id))
    audit(db, user, "UPDATE_USER", f"#{user_id}: {', '.join(k for k in sets if k != 'password_hash') or 'password'}")
    db.commit()
    return {"ok": True}


@router.get("/admin/audit")
def audit_log(user=Depends(admin), db=Depends(get_db)):
    return rows(db.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 300"))
