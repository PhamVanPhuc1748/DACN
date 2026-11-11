from __future__ import annotations

from datetime import datetime
import json
import sys
import tempfile
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .config import get_settings, save_env_settings
from .database import Base, ChatHistory, Disease, PredictionHistory, User, engine, get_db, get_engine
from .diseases_data import DISEASES_SEED

# Allow importing PigSkinTech real inference pipeline
PIGSKIN_DIR = Path(__file__).resolve().parents[2] / "PigSkinTech"
if str(PIGSKIN_DIR) not in sys.path:
    sys.path.insert(0, str(PIGSKIN_DIR))

app = FastAPI(title="PigSkinTech API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def seed_initial_data(db: Session) -> None:
    if db.query(Disease).count() > 0:
        return
    for item in DISEASES_SEED:
        db.add(Disease(**item))
    db.commit()


@app.on_event("startup")
def on_startup() -> None:
    active_engine = get_engine()
    Base.metadata.create_all(bind=active_engine)
    db = next(get_db())
    try:
        seed_initial_data(db)
    finally:
        db.close()


class AuthRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = "farmer"


class ChatMessageItem(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessageItem] = []
    user_id: Optional[int] = None
    context: Optional[str] = None


class AdminSettingsPayload(BaseModel):
    database_engine: str = "sqlserver"
    sqlserver_host: str = "localhost"
    sqlserver_port: int = 1433
    sqlserver_database: str = "PigSkinTechDB"
    sqlserver_username: str = ""
    sqlserver_password: str = ""
    sqlserver_driver: str = "ODBC Driver 17 for SQL Server"
    sqlserver_trusted_connection: bool = True
    ai_provider: str = "openai_compatible"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_system_prompt: str = (
        "Bạn là bác sĩ thú y AI chuyên về bệnh ngoài da ở heo của hệ thống PigSkinTech. "
        "Hãy trả lời ngắn gọn, dễ hiểu, thực tế về triệu chứng, cách xử lý ban đầu, "
        "an toàn sinh học và khi nào cần gọi bác sĩ thú y."
    )


def _require_admin(request: Request, db: Session) -> User:
    username = (request.headers.get("X-Admin-Username") or "").strip()
    if not username:
        raise HTTPException(status_code=403, detail="Thiếu thông tin xác thực quản trị viên")
    user = db.query(User).filter(User.username == username).first()
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên mới có quyền truy cập mục này")
    return user


@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/auth/register")
def register(payload: AuthRequest, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.username == payload.username).first()
    if exists:
        raise HTTPException(status_code=400, detail="Username already exists")

    role = payload.role if payload.role in {"farmer", "admin", "expert"} else "farmer"
    user = User(username=payload.username, password=payload.password, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username, "role": user.role}


@app.post("/auth/login")
def login(payload: AuthRequest, db: Session = Depends(get_db)):
    user = (
        db.query(User)
        .filter(User.username == payload.username, User.password == payload.password)
        .first()
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"id": user.id, "username": user.username, "role": user.role}


@app.get("/diseases")
def list_diseases(search: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Disease)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter((Disease.name_vi.ilike(pattern)) | (Disease.code.ilike(pattern)))

    items = query.order_by(Disease.name_vi.asc()).all()
    return [
        {
            "id": d.id,
            "code": d.code,
            "name_vi": d.name_vi,
            "symptoms": d.symptoms,
            "treatment": d.treatment,
            "prevention": d.prevention,
            "reference_image": d.reference_image,
        }
        for d in items
    ]


@app.post("/predict")
async def predict_disease(
    file: UploadFile = File(...),
    user_id: Optional[int] = Form(default=None),
    model_run: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    suffix = Path(file.filename or "upload.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        from services.inference import predict as run_real_predict

        pred = run_real_predict(tmp_path, run_name=model_run)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

    if not pred.get("ok"):
        raise HTTPException(status_code=400, detail=pred.get("error", "Inference error"))

    predicted_code = pred["label"]
    confidence = float(pred["confidence"])
    disease_info = pred.get("disease", {})

    record = PredictionHistory(
        user_id=user_id,
        image_name=file.filename or "uploaded_image.jpg",
        predicted_code=predicted_code,
        confidence=confidence,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "prediction_id": record.id,
        "predicted_code": predicted_code,
        "confidence": confidence,
        "inference_ms": pred.get("inference_ms", 0.0),
        "architecture": pred.get("architecture", ""),
        "scores": pred.get("scores", []),
        "top3": pred.get("top3", []),
        "disease": {
            "code": predicted_code,
            "name_vi": disease_info.get("name_vi", predicted_code),
            "symptoms": disease_info.get("symptoms", ""),
            "treatment": disease_info.get("drugs", ""),
            "prevention": disease_info.get("isolation", ""),
        },
        "created_at": record.created_at.isoformat(),
    }


@app.get("/admin/settings")
def get_admin_settings(request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    cfg = get_settings()
    return {
        "database_engine": cfg.database_engine,
        "sqlserver_host": cfg.sqlserver_host,
        "sqlserver_port": cfg.sqlserver_port,
        "sqlserver_database": cfg.sqlserver_database,
        "sqlserver_username": cfg.sqlserver_username,
        "sqlserver_password": cfg.sqlserver_password,
        "sqlserver_driver": cfg.sqlserver_driver,
        "sqlserver_trusted_connection": cfg.sqlserver_trusted_connection,
        "ai_provider": cfg.ai_provider,
        "ai_base_url": cfg.ai_base_url,
        "ai_api_key": cfg.ai_api_key,
        "ai_model": cfg.ai_model,
        "ai_system_prompt": cfg.ai_system_prompt,
    }


@app.put("/admin/settings")
def update_admin_settings(payload: AdminSettingsPayload, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    save_env_settings(
        {
            "DATABASE_ENGINE": payload.database_engine,
            "SQLSERVER_HOST": payload.sqlserver_host,
            "SQLSERVER_PORT": str(payload.sqlserver_port),
            "SQLSERVER_DATABASE": payload.sqlserver_database,
            "SQLSERVER_USERNAME": payload.sqlserver_username,
            "SQLSERVER_PASSWORD": payload.sqlserver_password,
            "SQLSERVER_DRIVER": payload.sqlserver_driver,
            "SQLSERVER_TRUSTED_CONNECTION": "true" if payload.sqlserver_trusted_connection else "false",
            "AI_PROVIDER": payload.ai_provider,
            "AI_BASE_URL": payload.ai_base_url,
            "AI_API_KEY": payload.ai_api_key,
            "AI_MODEL": payload.ai_model,
            "AI_SYSTEM_PROMPT": payload.ai_system_prompt,
        }
    )
    active_engine = get_engine()
    Base.metadata.create_all(bind=active_engine)
    return {"status": "saved"}


@app.post("/chat")
def chat_with_ai(payload: ChatRequest, db: Session = Depends(get_db)):
    from services.chatbot_service import (
        STRICT_DOMAIN_SYSTEM_PROMPT,
        build_refusal_response,
        ensure_disclaimer,
        is_in_domain,
    )

    user_msg = (payload.message or "").strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Tin nhắn không được để trống")

    # Kiểm soát nội dung nghiêm ngặt (Strict Domain Guardrail)
    if not is_in_domain(user_msg):
        refusal = build_refusal_response()
        db.add(ChatHistory(user_id=payload.user_id, role="user", message=user_msg))
        db.add(ChatHistory(user_id=payload.user_id, role="assistant", message=refusal))
        db.commit()
        return {"reply": refusal, "model": "PigSkinTech Domain Guardrail"}

    cfg = get_settings()
    base_url = cfg.ai_base_url.rstrip("/")
    endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"

    system_prompt = f"{STRICT_DOMAIN_SYSTEM_PROMPT}\n\n{cfg.ai_system_prompt}"
    if payload.context:
        system_prompt += f"\n\nNgữ cảnh ca chẩn đoán hiện tại:\n{payload.context}"

    messages = [{"role": "system", "content": system_prompt}]
    for item in payload.history[-10:]:
        if item.role in {"user", "assistant"} and item.content.strip():
            messages.append({"role": item.role, "content": item.content.strip()})
    messages.append({"role": "user", "content": user_msg})

    headers = {"Content-Type": "application/json"}
    if cfg.ai_api_key:
        headers["Authorization"] = f"Bearer {cfg.ai_api_key}"

    req_body = json.dumps(
        {
            "model": cfg.ai_model,
            "messages": messages,
            "temperature": 0.25,
        }
    ).encode("utf-8")

    try:
        req = UrlRequest(endpoint, data=req_body, headers=headers, method="POST")
        with urlopen(req, timeout=45) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        err_text = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(status_code=502, detail=f"AI API trả lỗi ({exc.code}): {err_text[:240]}") from exc
    except URLError as exc:
        raise HTTPException(status_code=502, detail=f"Không kết nối được tới AI server ({endpoint}): {exc.reason}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi gọi AI: {exc}") from exc

    reply = ""
    choices = resp_data.get("choices") or []
    if choices:
        reply = (choices[0].get("message") or {}).get("content") or ""
    if not reply and isinstance(resp_data.get("message"), dict):
        reply = resp_data["message"].get("content") or ""
    if not reply:
        reply = "Không nhận được phản hồi văn bản từ mô hình AI."

    reply = ensure_disclaimer(reply)

    db.add(ChatHistory(user_id=payload.user_id, role="user", message=user_msg))
    db.add(ChatHistory(user_id=payload.user_id, role="assistant", message=reply))
    db.commit()

    return {"reply": reply, "model": cfg.ai_model}
