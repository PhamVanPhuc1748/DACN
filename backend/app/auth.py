"""JWT auth + RBAC theo 4 role: ADMIN, AI_ENGINEER, VET, FARM_OWNER."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import get_db

# ponytail: secret mặc định chỉ dùng cho dev; đặt biến môi trường JWT_SECRET khi deploy.
SECRET = os.getenv("JWT_SECRET", "dev-only-change-me-pig-skin-dacn")
TOKEN_HOURS = 12
ALL_ROLES = ("ADMIN", "AI_ENGINEER", "VET", "FARM_OWNER")

_bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()
    return f"{salt}${digest}"


def verify_password(pw: str, stored: str) -> bool:
    salt, digest = stored.split("$", 1)
    return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex(), digest)


def create_token(user: dict) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)
    return jwt.encode({"sub": str(user["id"]), "role": user["role"], "exp": exp}, SECRET, algorithm="HS256")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer), db=Depends(get_db)) -> dict:
    if not cred:
        raise HTTPException(401, "Chưa đăng nhập")
    try:
        payload = jwt.decode(cred.credentials, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ hoặc đã hết hạn")
    row = db.execute("SELECT id, username, full_name, role, is_active FROM users WHERE id=?",
                     (int(payload["sub"]),)).fetchone()
    if not row or not row["is_active"]:
        raise HTTPException(401, "Tài khoản không tồn tại hoặc đã bị khóa")
    return dict(row)


def require(*roles: str):
    """Dependency: chỉ cho phép các role được liệt kê (role lấy từ DB, không tin payload)."""
    def dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, "Bạn không có quyền truy cập chức năng này")
        return user
    return dep
