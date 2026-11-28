from __future__ import annotations

from datetime import datetime
import sys
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import get_settings, save_env_settings
from .database import init_db, save_record

# Allow importing PigSkinTech real inference, chatbot and store pipelines
PIGSKIN_DIR = Path(__file__).resolve().parents[2] / "PigSkinTech"
if str(PIGSKIN_DIR) not in sys.path:
    sys.path.insert(0, str(PIGSKIN_DIR))

from services.auth_service import authenticate_local
from services.chatbot_service import ask_vet_ai
from services.inference import predict as run_real_predict
from services.project_data import load_classes_config
from services.store import (
    create_user_account,
    initialize as init_store,
    list_users,
    save as save_inspection,
    save_chat_message,
)

app = FastAPI(title="PigSkinTech API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    init_store()


class AuthRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = "user"


class ChatMessageItem(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessageItem] = []
    user_id: Optional[int] = None
    user_email: Optional[str] = "nongdan.pigskin@gmail.com"
    context: Optional[dict] = None


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


def _require_admin(request: Request) -> dict:
    username = (request.headers.get("X-Admin-Username") or "").strip().lower()
    if not username:
        raise HTTPException(status_code=403, detail="Thiếu thông tin xác thực quản trị viên")
    for u in list_users("admin", username):
        if username in (str(u.get("username") or "").lower(), str(u.get("email") or "").lower()):
            return u
    raise HTTPException(status_code=403, detail="Chỉ quản trị viên mới có quyền truy cập mục này")


@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/auth/register")
def register(payload: AuthRequest):
    email = payload.username if "@" in payload.username else f"{payload.username}@pigskintech.com"
    role = payload.role if payload.role in {"user", "admin", "expert"} else "user"
    try:
        user = create_user_account(email=email, full_name=payload.username, role=role, password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": user["id"], "username": user["username"], "email": user["email"], "role": user["role"]}


@app.post("/auth/login")
def login(payload: AuthRequest):
    try:
        user = authenticate_local(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"id": user["id"], "username": user["username"], "email": user["email"], "role": user["role"]}


@app.get("/diseases")
def list_diseases(search: Optional[str] = None):
    catalog = load_classes_config()
    q = (search or "").strip().lower()
    items = []
    for idx, (code, info) in enumerate(catalog.items(), start=1):
        name_vi = info.get("name_vi", code)
        if q and q not in code.lower() and q not in name_vi.lower():
            continue
        items.append(
            {
                "id": idx,
                "code": code,
                "name_vi": name_vi,
                "danger_level": info.get("danger_level", "Trung bình"),
                "symptoms": info.get("symptoms", ""),
                "treatment": info.get("treatment", ""),
                "prevention": info.get("prevention", ""),
            }
        )
    return items


@app.post("/predict")
async def predict_disease(
    file: UploadFile = File(...),
    user_id: Optional[int] = Form(default=None),
    model_run: Optional[str] = Form(default=None),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    suffix = Path(file.filename or "upload.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        pred = run_real_predict(tmp_path, run_name=model_run)
        if not pred.get("ok"):
            raise HTTPException(status_code=400, detail=pred.get("message", "Inference error"))
        row_id = save_inspection(
            pred["info"],
            pred,
            case={"user_id": user_id or 1},
            source_image=tmp_path,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    predicted_code = pred["label"]
    confidence = float(pred["confidence"])
    disease_info = pred.get("disease", {})
    save_record(
        {
            "id": f"PS-{row_id:06d}",
            "filename": file.filename or "uploaded_image.jpg",
            "disease_code": predicted_code,
            "disease_name": disease_info.get("name_vi", predicted_code),
            "confidence": confidence,
            "treatment_summary": disease_info.get("drugs", ""),
        }
    )

    return {
        "prediction_id": row_id,
        "case_id": f"PS-{row_id:06d}",
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
        "created_at": datetime.now().isoformat(),
    }


@app.get("/admin/settings")
def get_admin_settings(request: Request):
    _require_admin(request)
    cfg = get_settings()
    return {
        "database_engine": cfg.database_backend,
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
def update_admin_settings(payload: AdminSettingsPayload, request: Request):
    _require_admin(request)
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
    return {"status": "saved"}


@app.post("/chat")
def chat_with_ai(payload: ChatRequest):
    user_msg = (payload.message or "").strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Tin nhắn không được để trống")

    email = (payload.user_email or "nongdan.pigskin@gmail.com").strip().lower()
    history_dicts = [{"role": m.role, "content": m.content} for m in payload.history]
    save_chat_message(user_email=email, role="user", content=user_msg, user_id=payload.user_id, model_name="user")
    reply, used_model = ask_vet_ai(user_msg, history_dicts, payload.context)
    save_chat_message(user_email=email, role="assistant", content=reply, user_id=payload.user_id, model_name=used_model)
    return {"reply": reply, "model": used_model}
