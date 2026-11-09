"""Application settings for SQL Server and an AI chat provider.

Settings are read from environment variables or ``backend/.env``. This module
only describes configuration; database.py still uses SQLite until its storage
implementation is deliberately migrated to SQL Server.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Allow environment-variable configuration without the extra package.
    load_dotenv = None


BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"

if load_dotenv:
    load_dotenv(ENV_FILE, override=False)
elif ENV_FILE.is_file():
    # Keep local development working before the optional dotenv dependency is installed.
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            os.environ[key] = value


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _odbc_value(value: str) -> str:
    """Escape a value for an ODBC connection string."""
    return "{" + value.replace("}", "}}") + "}"


def _sqlite_path() -> Path:
    configured_path = Path(os.getenv("PIGSKIN_SQLITE_PATH", "pigskin.db"))
    return configured_path if configured_path.is_absolute() else BACKEND_DIR / configured_path


@dataclass(frozen=True)
class Settings:
    # Keep SQLite as the active default until database.py supports SQL Server.
    database_backend: str = os.getenv("PIGSKIN_DATABASE_BACKEND", "sqlite").strip().lower()
    sqlite_path: Path = field(default_factory=_sqlite_path)

    sqlserver_host: str = os.getenv("SQLSERVER_HOST", "localhost")
    sqlserver_port: int = int(os.getenv("SQLSERVER_PORT", "1433"))
    sqlserver_database: str = os.getenv("SQLSERVER_DATABASE", "PigSkinDB")
    sqlserver_username: str = os.getenv("SQLSERVER_USERNAME", "")
    sqlserver_password: str = field(default_factory=lambda: os.getenv("SQLSERVER_PASSWORD", ""), repr=False)
    sqlserver_driver: str = os.getenv("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server")
    sqlserver_trusted_connection: bool = _env_bool("SQLSERVER_TRUSTED_CONNECTION", False)
    sqlserver_encrypt: bool = _env_bool("SQLSERVER_ENCRYPT", True)
    sqlserver_trust_server_certificate: bool = _env_bool("SQLSERVER_TRUST_SERVER_CERTIFICATE", False)
    sqlserver_timeout_seconds: int = int(os.getenv("SQLSERVER_TIMEOUT_SECONDS", "30"))

    ai_provider: str = os.getenv("AI_PROVIDER", "openai_compatible").strip().lower()
    ai_base_url: str = os.getenv("AI_BASE_URL", "").rstrip("/")
    ai_api_key: str = field(default_factory=lambda: os.getenv("AI_API_KEY", ""), repr=False)
    ai_model: str = os.getenv("AI_MODEL", "")
    ai_timeout_seconds: int = int(os.getenv("AI_TIMEOUT_SECONDS", "45"))
    ai_max_tokens: int = int(os.getenv("AI_MAX_TOKENS", "700"))
    ai_system_prompt: str = os.getenv("AI_SYSTEM_PROMPT") or (
        "Bạn là trợ lý thông tin cho đồ án nghiên cứu bệnh da heo. Trả lời bằng tiếng Việt, "
        "nêu rõ giới hạn của thông tin từ ảnh, không khẳng định chẩn đoán và không kê đơn "
        "hay liều thuốc. Khuyến nghị người dùng liên hệ bác sĩ thú y để xác minh."
    )

    @property
    def sqlserver_connection_string(self) -> str:
        """Build a pyodbc connection string; install the Microsoft ODBC driver separately."""
        server = self.sqlserver_host
        if self.sqlserver_port:
            server = f"{server},{self.sqlserver_port}"

        parts = [
            f"DRIVER={_odbc_value(self.sqlserver_driver)}",
            f"SERVER={_odbc_value(server)}",
            f"DATABASE={_odbc_value(self.sqlserver_database)}",
            f"Encrypt={'yes' if self.sqlserver_encrypt else 'no'}",
            f"TrustServerCertificate={'yes' if self.sqlserver_trust_server_certificate else 'no'}",
            f"Connection Timeout={self.sqlserver_timeout_seconds}",
        ]
        if self.sqlserver_trusted_connection:
            parts.append("Trusted_Connection=yes")
        else:
            parts.extend(
                [
                    f"UID={_odbc_value(self.sqlserver_username)}",
                    f"PWD={_odbc_value(self.sqlserver_password)}",
                ]
            )
        return ";".join(parts) + ";"

    @property
    def sqlserver_missing_settings(self) -> list[str]:
        missing = []
        if not self.sqlserver_host:
            missing.append("SQLSERVER_HOST")
        if not self.sqlserver_database:
            missing.append("SQLSERVER_DATABASE")
        if not self.sqlserver_trusted_connection:
            if not self.sqlserver_username:
                missing.append("SQLSERVER_USERNAME")
            if not self.sqlserver_password:
                missing.append("SQLSERVER_PASSWORD")
        return missing

    @property
    def ai_is_configured(self) -> bool:
        if not self.ai_model or not self.ai_base_url:
            return False
        # Local Ollama endpoints usually do not require an API key.
        return self.ai_provider == "ollama" or bool(self.ai_api_key)


settings = Settings()
