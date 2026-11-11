from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
ENV_FILE = APP_DIR / ".env"
ROOT_ENV_FILE = REPO_ROOT / ".env"
BACKEND_ENV_FILE = BACKEND_DIR / ".env"

DEFAULTS = {
    "DB_SERVER": "localhost",
    "DB_NAME": "PigSkinTechDB",
    "DB_USER": "",
    "DB_PASSWORD": "",
    "Trusted_Connection": "yes",
    "DATABASE_ENGINE": "sqlserver",
    "SQLSERVER_HOST": "localhost",
    "SQLSERVER_PORT": "1433",
    "SQLSERVER_DATABASE": "PigSkinTechDB",
    "SQLSERVER_USERNAME": "",
    "SQLSERVER_PASSWORD": "",
    "SQLSERVER_DRIVER": "ODBC Driver 17 for SQL Server",
    "SQLSERVER_TRUSTED_CONNECTION": "true",
    "GOOGLE_CLIENT_ID": "",
    "GOOGLE_CLIENT_SECRET": "",
    "GOOGLE_REDIRECT_URI": "http://127.0.0.1:8765/callback",
    "GEMINI_API_KEY": "",
    "GEMINI_MODEL": "gemini-2.5-flash",
    "API_BASE_URL": "http://127.0.0.1:8000",
    "AI_PROVIDER": "openai_compatible",
    "AI_BASE_URL": "https://api.openai.com/v1",
    "AI_API_KEY": "",
    "AI_MODEL": "gpt-4o-mini",
    "AI_SYSTEM_PROMPT": (
        "Bạn là bác sĩ thú y AI chuyên biệt của ứng dụng PigSkinTech. "
        "CHỈ trả lời câu hỏi về bệnh ngoài da ở heo, giải thích kết quả chẩn đoán mô hình Deep Learning "
        "(MobileNetV2, EfficientNet-B0) và hướng dẫn sử dụng ứng dụng PigSkinTech; từ chối lịch sự mọi câu hỏi ngoài lề."
    ),
}


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        values[key.strip()] = val
    return values


def read_settings() -> dict[str, str]:
    for env_path in (BACKEND_ENV_FILE, ROOT_ENV_FILE, ENV_FILE):
        if env_path.exists():
            load_dotenv(env_path, override=False)

    values = dict(DEFAULTS)
    for env_path in (BACKEND_ENV_FILE, ROOT_ENV_FILE, ENV_FILE):
        values.update(_parse_env_file(env_path))

    for k in list(DEFAULTS.keys()):
        env_val = os.environ.get(k)
        if env_val is not None and env_val != "":
            values[k] = env_val

    # Synchronize aliases between DB_* and SQLSERVER_*
    if values.get("DB_SERVER") and values.get("SQLSERVER_HOST") == DEFAULTS["SQLSERVER_HOST"]:
        values["SQLSERVER_HOST"] = values["DB_SERVER"]
    elif values.get("SQLSERVER_HOST") and values.get("DB_SERVER") == DEFAULTS["DB_SERVER"]:
        values["DB_SERVER"] = values["SQLSERVER_HOST"]

    if values.get("DB_NAME") and values.get("SQLSERVER_DATABASE") == DEFAULTS["SQLSERVER_DATABASE"]:
        values["SQLSERVER_DATABASE"] = values["DB_NAME"]
    elif values.get("SQLSERVER_DATABASE") and values.get("DB_NAME") == DEFAULTS["DB_NAME"]:
        values["DB_NAME"] = values["SQLSERVER_DATABASE"]

    if values.get("DB_USER") and not values.get("SQLSERVER_USERNAME"):
        values["SQLSERVER_USERNAME"] = values["DB_USER"]
    elif values.get("SQLSERVER_USERNAME") and not values.get("DB_USER"):
        values["DB_USER"] = values["SQLSERVER_USERNAME"]

    if values.get("DB_PASSWORD") and not values.get("SQLSERVER_PASSWORD"):
        values["SQLSERVER_PASSWORD"] = values["DB_PASSWORD"]
    elif values.get("SQLSERVER_PASSWORD") and not values.get("DB_PASSWORD"):
        values["DB_PASSWORD"] = values["SQLSERVER_PASSWORD"]

    return values


def save_settings(new_values: dict[str, str]) -> Path:
    settings = read_settings()
    for key, val in new_values.items():
        if val is not None:
            settings[key] = str(val).strip()

    # Keep aliases synced when saving from Admin UI or OAuth dialog
    if "SQLSERVER_HOST" in new_values and "DB_SERVER" not in new_values:
        settings["DB_SERVER"] = settings["SQLSERVER_HOST"]
    elif "DB_SERVER" in new_values and "SQLSERVER_HOST" not in new_values:
        settings["SQLSERVER_HOST"] = settings["DB_SERVER"]

    if "SQLSERVER_DATABASE" in new_values and "DB_NAME" not in new_values:
        settings["DB_NAME"] = settings["SQLSERVER_DATABASE"]
    elif "DB_NAME" in new_values and "SQLSERVER_DATABASE" not in new_values:
        settings["SQLSERVER_DATABASE"] = settings["DB_NAME"]

    if "SQLSERVER_USERNAME" in new_values and "DB_USER" not in new_values:
        settings["DB_USER"] = settings["SQLSERVER_USERNAME"]
    elif "DB_USER" in new_values and "SQLSERVER_USERNAME" not in new_values:
        settings["SQLSERVER_USERNAME"] = settings["DB_USER"]

    if "SQLSERVER_PASSWORD" in new_values and "DB_PASSWORD" not in new_values:
        settings["DB_PASSWORD"] = settings["SQLSERVER_PASSWORD"]
    elif "DB_PASSWORD" in new_values and "SQLSERVER_PASSWORD" not in new_values:
        settings["SQLSERVER_PASSWORD"] = settings["DB_PASSWORD"]

    if "SQLSERVER_TRUSTED_CONNECTION" in new_values and "Trusted_Connection" not in new_values:
        tc = str(settings["SQLSERVER_TRUSTED_CONNECTION"]).lower() in ("true", "yes", "1")
        settings["Trusted_Connection"] = "yes" if tc else "no"
    elif "Trusted_Connection" in new_values and "SQLSERVER_TRUSTED_CONNECTION" not in new_values:
        tc = str(settings["Trusted_Connection"]).lower() in ("true", "yes", "1")
        settings["SQLSERVER_TRUSTED_CONNECTION"] = "true" if tc else "false"

    lines = [
        "# PigSkinTech Environment Configuration",
        "# Tự động lưu từ trang Quản trị hệ thống (Admin)",
        "",
    ]
    for key in DEFAULTS:
        val = str(settings.get(key, DEFAULTS[key])).replace("\r", " ").replace("\n", " ").strip()
        lines.append(f"{key}={val}")
        os.environ[key] = val

    content = "\n".join(lines) + "\n"
    for target in (ENV_FILE, ROOT_ENV_FILE, BACKEND_ENV_FILE):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return ENV_FILE

