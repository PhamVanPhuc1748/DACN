"""SQL Database persistence (SQL Server via pyodbc + Local SQL Engine) for Users, Inspections, and ChatMessages."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import threading
from typing import Any
from uuid import uuid4

try:
    import pyodbc
    pyodbc.pooling = True
except ImportError:
    pyodbc = None

from services.config_store import read_settings
from services.project_data import get_class_info


DB = Path(__file__).resolve().parents[1] / "pigskin_history.db"
IMAGE_DIR = Path(__file__).resolve().parents[1] / "case_images"
CURATED_DIR = Path(__file__).resolve().parents[1] / "curated_dataset"

_ACTIVE_DB_INFO: dict[str, str] = {
    "engine": "SQL Database",
    "server": "localhost",
    "database": "PigSkinTechDB",
    "status": "Đang khởi tạo...",
}

CASE_COLUMNS = {
    "case_id": "TEXT NOT NULL DEFAULT ''",
    "predicted_label": "TEXT NOT NULL DEFAULT ''",
    "expert_display_name": "TEXT NOT NULL DEFAULT ''",
    "inference_ms": "REAL DEFAULT 0.0",
    "animal_id": "TEXT NOT NULL DEFAULT ''",
    "farm_name": "TEXT NOT NULL DEFAULT ''",
    "body_site": "TEXT NOT NULL DEFAULT ''",
    "symptoms": "TEXT NOT NULL DEFAULT ''",
    "onset_date": "TEXT NOT NULL DEFAULT ''",
    "entered_at": "TEXT NOT NULL DEFAULT ''",
    "image_path": "TEXT NOT NULL DEFAULT ''",
    "review_status": "TEXT NOT NULL DEFAULT 'needs_review'",
    "review_note": "TEXT NOT NULL DEFAULT ''",
    "scores_json": "TEXT NOT NULL DEFAULT '[]'",
    "model_info": "TEXT NOT NULL DEFAULT ''",
    "user_id": "INTEGER NOT NULL DEFAULT 1",
    "user_email": "TEXT NOT NULL DEFAULT 'nongdan.pigskin@gmail.com'",
    "user_name": "TEXT NOT NULL DEFAULT 'Nguyễn Văn Nông'",
    "requested_review": "INTEGER NOT NULL DEFAULT 0",
    "agreed_with_ai": "INTEGER DEFAULT NULL",
    "expert_label": "TEXT NOT NULL DEFAULT ''",
    "expert_note": "TEXT NOT NULL DEFAULT ''",
    "reviewed_by": "TEXT NOT NULL DEFAULT ''",
    "reviewed_at": "TEXT NOT NULL DEFAULT ''",
    "in_dataset": "INTEGER NOT NULL DEFAULT 0",
    "danger_level": "TEXT NOT NULL DEFAULT ''",
    "recommendation": "TEXT NOT NULL DEFAULT ''",
}

DEFAULT_RBAC_USERS = [
    {
        "email": "nongdan.pigskin@gmail.com",
        "username": "nongdan",
        "full_name": "Nguyễn Văn Nông (Chủ trại)",
        "role": "user",
        "auth_provider": "local",
        "avatar_url": "https://ui-avatars.com/api/?name=Nguyen+Nong&background=2E7D32&color=fff",
    },
    {
        "email": "bs.thuy.pigskin@gmail.com",
        "username": "bsthuy",
        "full_name": "BS. Trần Thị Thúy (Thú y)",
        "role": "expert",
        "auth_provider": "local",
        "avatar_url": "https://ui-avatars.com/api/?name=BS+Thuy&background=1565C0&color=fff",
    },
    {
        "email": "admin.pigskin@gmail.com",
        "username": "admin",
        "full_name": "Quản trị viên PigSkinTech",
        "role": "admin",
        "auth_provider": "local",
        "avatar_url": "https://ui-avatars.com/api/?name=Admin+PigSkin&background=AD1457&color=fff",
    },
]

SAMPLE_GALLERY_CASES = [
    {
        "filename": "heo_dong_dau_01.jpg",
        "title": "Ca 01 • Đóng dấu lợn",
        "animal_id": "PIG-101",
        "farm_name": "Trại An Phú - Khu A",
        "body_site": "Vùng lưng và hông",
        "symptoms": "Mảng đỏ hình thoi nổi rõ trên da lưng, heo sốt 41.2°C.",
    },
    {
        "filename": "heo_nghi_ghe_02.jpg",
        "title": "Ca 02 • Nghi ghẻ Sarcoptes",
        "animal_id": "PIG-108",
        "farm_name": "Trại An Phú - Khu B",
        "body_site": "Vành tai và cổ",
        "symptoms": "Da đóng vảy xám dày, heo cọ sát vào vách chuồng liên tục.",
    },
    {
        "filename": "heo_viem_da_tiet_dich_03.jpg",
        "title": "Ca 03 • Viêm da tiết dịch",
        "animal_id": "PIG-089",
        "farm_name": "Trại An Phú - Khu A",
        "body_site": "Quanh mặt và cổ",
        "symptoms": "Da rỉ dịch nhờn nâu đen, đóng vảy nứt nẻ ở heo con cai sữa.",
    },
    {
        "filename": "heo_nam_da_04.jpg",
        "title": "Ca 04 • Nấm da / Vảy phấn",
        "animal_id": "PIG-094",
        "farm_name": "Trại Hòa Bình",
        "body_site": "Vùng vai và bụng",
        "symptoms": "Vết tròn rụng lông, viền đỏ nhẹ có vảy trắng mịn.",
    },
    {
        "filename": "heo_khoe_manh_05.jpg",
        "title": "Ca 05 • Da khỏe mạnh",
        "animal_id": "PIG-112",
        "farm_name": "Trại An Phú - Khu C",
        "body_site": "Toàn thân",
        "symptoms": "Da hồng hào, lông mượt, ăn uống bình thường.",
    },
]


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _pick_odbc_driver(preferred: str) -> str:
    if pyodbc is None:
        return preferred
    installed = list(pyodbc.drivers())
    if preferred in installed:
        return preferred
    for cand in (
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
    ):
        if cand in installed:
            return cand
    return preferred


def _build_sqlserver_conn_str(settings: dict[str, str], database: str | None = None) -> str:
    server = (settings.get("DB_SERVER") or settings.get("SQLSERVER_HOST") or "localhost").strip()
    port = (settings.get("SQLSERVER_PORT") or "1433").strip()
    if port and port != "1433" and "," not in server and "\\" not in server:
        server = f"{server},{port}"
    db_name = (database or settings.get("DB_NAME") or settings.get("SQLSERVER_DATABASE") or "PigSkinTechDB").strip()
    user = (settings.get("DB_USER") or settings.get("SQLSERVER_USERNAME") or "").strip()
    password = (settings.get("DB_PASSWORD") or settings.get("SQLSERVER_PASSWORD") or "").strip()
    tc_raw = (settings.get("Trusted_Connection") or settings.get("SQLSERVER_TRUSTED_CONNECTION") or "yes").strip().lower()
    trusted = tc_raw in ("yes", "true", "1", "sspi")
    driver = _pick_odbc_driver(settings.get("SQLSERVER_DRIVER", "ODBC Driver 17 for SQL Server"))

    parts = [f"DRIVER={{{driver}}}", f"SERVER={server}", f"DATABASE={db_name}"]
    if trusted and not user:
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={user}")
        parts.append(f"PWD={password}")
    if "Driver 18" in driver:
        parts.append("TrustServerCertificate=yes")
    return ";".join(parts)


class _DictRow(dict):
    """Row wrapper supporting both row['col'] and row[0] indexing across pyodbc and sqlite3."""

    def __init__(self, columns: list[str], values: tuple | list):
        super().__init__(zip(columns, values))
        self._values = tuple(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        if isinstance(key, str) and key not in self:
            for k in self.keys():
                if k.lower() == key.lower():
                    return super().__getitem__(k)
        return super().__getitem__(key)


class _CursorWrapper:
    def __init__(self, raw_cursor: Any, is_sqlserver: bool, lastrowid: int | None = None):
        self._cur = raw_cursor
        self._is_sqlserver = is_sqlserver
        self.lastrowid = lastrowid if lastrowid is not None else getattr(raw_cursor, "lastrowid", None)
        self.rowcount = getattr(raw_cursor, "rowcount", -1)

    def _wrap(self, row: Any) -> _DictRow | None:
        if row is None:
            return None
        if isinstance(row, sqlite3.Row):
            cols = list(row.keys())
            return _DictRow(cols, [row[k] for k in cols])
        cols = [col[0] for col in (self._cur.description or [])]
        return _DictRow(cols, list(row))

    def fetchone(self) -> _DictRow | None:
        return self._wrap(self._cur.fetchone())

    def fetchall(self) -> list[_DictRow]:
        rows = self._cur.fetchall()
        return [self._wrap(r) for r in rows if r is not None]

    def __iter__(self):
        for r in self.fetchall():
            yield r


_SHARED_CONN_LOCK = threading.RLock()
_SHARED_RAW_CONN: Any = None
_SHARED_ENGINE_TYPE: str | None = None
_SHARED_CONN_STR: str = ""


def _get_shared_connection(force_reconnect: bool = False) -> tuple[Any, bool]:
    """
    Quản lý kết nối chia sẻ (Persistent Connection) kết hợp ODBC Connection Pooling (pyodbc.pooling = True).
    Tự động tái sử dụng kết nối đang mở và tự động kết nối lại (auto-reconnect) nếu bị ngắt.
    """
    global _SHARED_RAW_CONN, _SHARED_ENGINE_TYPE, _SHARED_CONN_STR
    with _SHARED_CONN_LOCK:
        settings = read_settings()
        engine_pref = (settings.get("DATABASE_ENGINE") or "sqlserver").strip().lower()

        if force_reconnect and _SHARED_RAW_CONN is not None:
            try:
                _SHARED_RAW_CONN.close()
            except Exception:
                pass
            _SHARED_RAW_CONN = None

        if pyodbc is not None and engine_pref == "sqlserver":
            conn_str = _build_sqlserver_conn_str(settings)
            # Kiểm tra kết nối SQL Server hiện tại
            if _SHARED_RAW_CONN is not None and _SHARED_ENGINE_TYPE == "sqlserver" and _SHARED_CONN_STR == conn_str:
                try:
                    cur = _SHARED_RAW_CONN.cursor()
                    cur.execute("SELECT 1")
                    cur.fetchone()
                    cur.close()
                    return _SHARED_RAW_CONN, True
                except Exception:
                    try:
                        _SHARED_RAW_CONN.close()
                    except Exception:
                        pass
                    _SHARED_RAW_CONN = None

            # Tạo kết nối SQL Server mới
            try:
                _SHARED_RAW_CONN = pyodbc.connect(conn_str, timeout=3)
                _SHARED_ENGINE_TYPE = "sqlserver"
                _SHARED_CONN_STR = conn_str
                _ACTIVE_DB_INFO.update({
                    "engine": "SQL Server (pyodbc)",
                    "server": settings.get("DB_SERVER") or settings.get("SQLSERVER_HOST") or "localhost",
                    "database": settings.get("DB_NAME") or "PigSkinTechDB",
                    "status": "Đã kết nối SQL Server thực tế (Connection Pooling Active)",
                })
                return _SHARED_RAW_CONN, True
            except Exception:
                try:
                    master_str = _build_sqlserver_conn_str(settings, database="master")
                    m_conn = pyodbc.connect(master_str, timeout=3, autocommit=True)
                    db_name = (settings.get("DB_NAME") or "PigSkinTechDB").replace("]", "")
                    m_conn.execute(f"IF DB_ID(N'{db_name}') IS NULL CREATE DATABASE [{db_name}];")
                    m_conn.close()
                    _SHARED_RAW_CONN = pyodbc.connect(_build_sqlserver_conn_str(settings), timeout=3)
                    _SHARED_ENGINE_TYPE = "sqlserver"
                    _SHARED_CONN_STR = conn_str
                    _ACTIVE_DB_INFO.update({
                        "engine": "SQL Server (pyodbc)",
                        "server": settings.get("DB_SERVER") or settings.get("SQLSERVER_HOST") or "localhost",
                        "database": db_name,
                        "status": f"Đã tự động khởi tạo & kết nối SQL Server ({db_name})",
                    })
                    return _SHARED_RAW_CONN, True
                except Exception as exc:
                    _ACTIVE_DB_INFO["last_error"] = str(exc)

        # Fallback SQLite
        if _SHARED_RAW_CONN is not None and _SHARED_ENGINE_TYPE == "sqlite":
            return _SHARED_RAW_CONN, False

        _SHARED_RAW_CONN = sqlite3.connect(DB, check_same_thread=False)
        _SHARED_RAW_CONN.row_factory = sqlite3.Row
        _SHARED_ENGINE_TYPE = "sqlite"
        _SHARED_CONN_STR = str(DB)
        _ACTIVE_DB_INFO.update({
            "engine": "SQL Database (Local Engine)",
            "server": DB.name,
            "database": settings.get("DB_NAME") or "PigSkinTechDB",
            "status": "Đang dùng SQL Database cục bộ (SQL Server chưa mở dịch vụ tại cổng 1433)",
        })
        return _SHARED_RAW_CONN, False


class _UnifiedConnection:
    """
    Giao diện kết nối SQL thống nhất:
    - Sử dụng kết nối chia sẻ bền vững và ODBC Connection Pooling để tăng tốc độ truy vấn tối đa.
    - Tự động Reconnect nếu mất kết nối giữa chừng mà không làm gián đoạn ứng dụng.
    """

    def __init__(self):
        raw_conn, is_sqlserver = _get_shared_connection()
        self._raw = raw_conn
        self.is_sqlserver = is_sqlserver

    def __enter__(self) -> "_UnifiedConnection":
        _SHARED_CONN_LOCK.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._raw is not None:
                if exc_type is None:
                    self._raw.commit()
                else:
                    self._raw.rollback()
        except Exception:
            pass
        finally:
            _SHARED_CONN_LOCK.release()

    def execute(self, sql: str, params: tuple | list = ()) -> _CursorWrapper:
        query = sql.strip()
        if self.is_sqlserver:
            # Dịch SQLite LIMIT 300 sang TOP 300 của T-SQL nếu có
            if "LIMIT 300" in query:
                query = query.replace("SELECT *", "SELECT TOP 300 *").replace("LIMIT 300", "")

        try:
            cur = self._raw.cursor()
            cur.execute(query, tuple(params))
        except Exception as exc:
            # Tự động reconnect nếu mất kết nối mạng hoặc timeout
            err_msg = str(exc).lower()
            is_conn_lost = self.is_sqlserver and any(
                code in err_msg for code in ("08s01", "08003", "hy000", "communication link", "closed", "connection reset")
            )
            if is_conn_lost:
                raw_conn, is_sqlserver = _get_shared_connection(force_reconnect=True)
                self._raw = raw_conn
                self.is_sqlserver = is_sqlserver
                cur = self._raw.cursor()
                cur.execute(query, tuple(params))
            else:
                raise

        last_id = None
        if self.is_sqlserver and query.upper().startswith("INSERT "):
            try:
                cur.execute("SELECT CAST(COALESCE(SCOPE_IDENTITY(), @@IDENTITY) AS INT)")
                id_row = cur.fetchone()
                if id_row and id_row[0] is not None:
                    last_id = int(id_row[0])
            except Exception:
                pass
        return _CursorWrapper(cur, self.is_sqlserver, lastrowid=last_id)


def conn() -> _UnifiedConnection:
    return _UnifiedConnection()


def get_db_status() -> dict[str, str]:
    initialize()
    return dict(_ACTIVE_DB_INFO)


def test_sqlserver_connection(custom_settings: dict[str, str] | None = None) -> dict[str, Any]:
    if pyodbc is None:
        return {"ok": False, "message": "Chưa cài đặt thư viện pyodbc."}
    cfg = read_settings()
    if custom_settings:
        cfg.update(custom_settings)
    try:
        conn_str = _build_sqlserver_conn_str(cfg, database="master")
        c = pyodbc.connect(conn_str, timeout=3)
        cur = c.cursor()
        cur.execute("SELECT @@VERSION")
        ver = cur.fetchone()[0].splitlines()[0]
        c.close()
        # Reset shared connection để cập nhật cấu hình mới nếu có
        global _SHARED_RAW_CONN
        with _SHARED_CONN_LOCK:
            if _SHARED_RAW_CONN is not None:
                try:
                    _SHARED_RAW_CONN.close()
                except Exception:
                    pass
                _SHARED_RAW_CONN = None
        return {"ok": True, "message": f"Kết nối SQL Server thành công: {ver}"}
    except Exception as exc:
        return {"ok": False, "message": f"Không thể kết nối SQL Server: {exc}"}


def initialize():
    """
    Tự động khởi tạo các bảng Users, Inspections, ChatMessages, DiseaseCatalog
    và View dbo.vw_DashboardKPIs nếu chưa tồn tại.
    Đồng thời đảm bảo tương thích 100% cột case_id và predicted_label.
    """
    with conn() as c:
        if c.is_sqlserver:
            c.execute(
                """
                IF OBJECT_ID(N'dbo.users', N'U') IS NULL
                CREATE TABLE dbo.users (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    email NVARCHAR(255) NOT NULL UNIQUE,
                    username NVARCHAR(128) NOT NULL DEFAULT '',
                    password_hash NVARCHAR(255) NOT NULL DEFAULT '',
                    full_name NVARCHAR(255) NOT NULL DEFAULT '',
                    avatar_url NVARCHAR(1000) NOT NULL DEFAULT '',
                    google_sub NVARCHAR(255) NOT NULL DEFAULT '',
                    role NVARCHAR(64) NOT NULL DEFAULT 'user',
                    auth_provider NVARCHAR(64) NOT NULL DEFAULT 'local',
                    is_active INT NOT NULL DEFAULT 1,
                    created_at NVARCHAR(64) NOT NULL
                );
                """
            )
            c.execute(
                """
                IF OBJECT_ID(N'dbo.inspections', N'U') IS NULL
                CREATE TABLE dbo.inspections (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    filename NVARCHAR(500) NOT NULL,
                    width INT NOT NULL,
                    height INT NOT NULL,
                    size_bytes INT NOT NULL,
                    mode NVARCHAR(64) NOT NULL,
                    predicted_class NVARCHAR(255) NULL,
                    predicted_label NVARCHAR(255) NULL,
                    confidence FLOAT NULL,
                    created_at NVARCHAR(64) NOT NULL,
                    case_id NVARCHAR(64) NOT NULL DEFAULT '',
                    animal_id NVARCHAR(128) NOT NULL DEFAULT '',
                    farm_name NVARCHAR(255) NOT NULL DEFAULT '',
                    body_site NVARCHAR(255) NOT NULL DEFAULT '',
                    symptoms NVARCHAR(MAX) NOT NULL DEFAULT '',
                    onset_date NVARCHAR(64) NOT NULL DEFAULT '',
                    entered_at NVARCHAR(64) NOT NULL DEFAULT '',
                    image_path NVARCHAR(1000) NOT NULL DEFAULT '',
                    review_status NVARCHAR(64) NOT NULL DEFAULT 'needs_review',
                    review_note NVARCHAR(MAX) NOT NULL DEFAULT '',
                    scores_json NVARCHAR(MAX) NOT NULL DEFAULT '[]',
                    model_info NVARCHAR(255) NOT NULL DEFAULT '',
                    user_id INT NOT NULL DEFAULT 1,
                    user_email NVARCHAR(255) NOT NULL DEFAULT 'nongdan.pigskin@gmail.com',
                    user_name NVARCHAR(255) NOT NULL DEFAULT N'Nguyễn Văn Nông',
                    requested_review INT NOT NULL DEFAULT 0,
                    agreed_with_ai INT NULL,
                    expert_label NVARCHAR(255) NOT NULL DEFAULT '',
                    expert_display_name NVARCHAR(255) NULL,
                    expert_note NVARCHAR(MAX) NOT NULL DEFAULT '',
                    reviewed_by NVARCHAR(255) NOT NULL DEFAULT '',
                    reviewed_at NVARCHAR(64) NOT NULL DEFAULT '',
                    in_dataset INT NOT NULL DEFAULT 0,
                    danger_level NVARCHAR(128) NOT NULL DEFAULT '',
                    recommendation NVARCHAR(MAX) NOT NULL DEFAULT '',
                    inference_ms FLOAT NULL
                );
                """
            )
            # Đảm bảo các cột bắt buộc luôn hiện diện trên SQL Server
            c.execute("IF COL_LENGTH('dbo.inspections', 'predicted_label') IS NULL ALTER TABLE dbo.inspections ADD predicted_label NVARCHAR(255) NULL;")
            c.execute("IF COL_LENGTH('dbo.inspections', 'expert_display_name') IS NULL ALTER TABLE dbo.inspections ADD expert_display_name NVARCHAR(255) NULL;")
            c.execute("IF COL_LENGTH('dbo.inspections', 'inference_ms') IS NULL ALTER TABLE dbo.inspections ADD inference_ms FLOAT NULL;")
            c.execute("IF COL_LENGTH('dbo.inspections', 'case_id') IS NULL ALTER TABLE dbo.inspections ADD case_id NVARCHAR(64) NOT NULL DEFAULT '';")

            c.execute(
                """
                IF OBJECT_ID(N'dbo.ChatMessages', N'U') IS NULL
                CREATE TABLE dbo.ChatMessages (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    timestamp NVARCHAR(64) NOT NULL,
                    user_id INT NULL,
                    user_email NVARCHAR(255) NOT NULL,
                    role NVARCHAR(32) NOT NULL,
                    content NVARCHAR(MAX) NOT NULL,
                    case_id NVARCHAR(64) NOT NULL DEFAULT '',
                    model_name NVARCHAR(128) NOT NULL DEFAULT ''
                );
                """
            )
            c.execute(
                """
                IF OBJECT_ID(N'dbo.DiseaseCatalog', N'U') IS NULL
                CREATE TABLE dbo.DiseaseCatalog (
                    code NVARCHAR(128) PRIMARY KEY,
                    name_vi NVARCHAR(255) NOT NULL,
                    danger_level NVARCHAR(64) NOT NULL DEFAULT N'Trung bình',
                    symptoms NVARCHAR(MAX) NOT NULL DEFAULT '',
                    prevention NVARCHAR(MAX) NOT NULL DEFAULT '',
                    treatment NVARCHAR(MAX) NOT NULL DEFAULT '',
                    updated_at NVARCHAR(64) NOT NULL DEFAULT ''
                );
                """
            )
            # Khởi tạo hoặc cập nhật View dbo.vw_DashboardKPIs
            c.execute(
                """
                IF OBJECT_ID(N'dbo.vw_DashboardKPIs', N'V') IS NULL
                EXEC(N'
                CREATE VIEW dbo.vw_DashboardKPIs AS
                SELECT
                    (SELECT COUNT(1) FROM dbo.users WHERE is_active = 1) AS total_users,
                    COUNT(1) AS total_inspections,
                    ISNULL(SUM(CASE WHEN requested_review = 1 AND review_status != ''reviewed'' THEN 1 ELSE 0 END), 0) AS pending_reviews,
                    ISNULL(SUM(CASE WHEN review_status = ''reviewed'' THEN 1 ELSE 0 END), 0) AS reviewed_count,
                    ISNULL(SUM(CASE WHEN review_status = ''reviewed'' AND agreed_with_ai = 1 THEN 1 ELSE 0 END), 0) AS agreed_count,
                    CAST(
                        CASE 
                            WHEN SUM(CASE WHEN review_status = ''reviewed'' THEN 1 ELSE 0 END) > 0 
                            THEN (SUM(CASE WHEN review_status = ''reviewed'' AND agreed_with_ai = 1 THEN 1.0 ELSE 0.0 END) * 100.0) 
                                 / SUM(CASE WHEN review_status = ''reviewed'' THEN 1.0 ELSE 0.0 END)
                            ELSE 0.0 
                        END AS DECIMAL(5,1)
                    ) AS ai_agreement_rate,
                    ISNULL(SUM(CASE WHEN in_dataset = 1 THEN 1 ELSE 0 END), 0) AS dataset_count,
                    ISNULL(AVG(confidence), 0.0) AS avg_confidence,
                    (SELECT COUNT(1) FROM dbo.ChatMessages) AS total_chats
                FROM dbo.inspections;
                ');
                """
            )
        else:
            c.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    username TEXT NOT NULL DEFAULT '',
                    password_hash TEXT NOT NULL DEFAULT '',
                    full_name TEXT NOT NULL DEFAULT '',
                    avatar_url TEXT NOT NULL DEFAULT '',
                    google_sub TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL DEFAULT 'user',
                    auth_provider TEXT NOT NULL DEFAULT 'local',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )"""
            )
            existing_user_cols = {row["name"] for row in c.execute("PRAGMA table_info(users)")}
            if "google_sub" not in existing_user_cols:
                c.execute("ALTER TABLE users ADD COLUMN google_sub TEXT NOT NULL DEFAULT ''")

            c.execute(
                """CREATE TABLE IF NOT EXISTS inspections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    predicted_class TEXT,
                    predicted_label TEXT,
                    confidence REAL,
                    created_at TEXT NOT NULL
                )"""
            )
            existing = {row["name"] for row in c.execute("PRAGMA table_info(inspections)")}
            for name, definition in CASE_COLUMNS.items():
                if name not in existing:
                    c.execute(f"ALTER TABLE inspections ADD COLUMN {name} {definition}")

            c.execute(
                """CREATE TABLE IF NOT EXISTS ChatMessages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    user_id INTEGER,
                    user_email TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    case_id TEXT NOT NULL DEFAULT '',
                    model_name TEXT NOT NULL DEFAULT ''
                )"""
            )
            c.execute(
                """CREATE TABLE IF NOT EXISTS DiseaseCatalog (
                    code TEXT PRIMARY KEY,
                    name_vi TEXT NOT NULL,
                    danger_level TEXT NOT NULL DEFAULT 'Trung bình',
                    symptoms TEXT NOT NULL DEFAULT '',
                    prevention TEXT NOT NULL DEFAULT '',
                    treatment TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )"""
            )
            c.execute(
                """
                CREATE VIEW IF NOT EXISTS vw_DashboardKPIs AS
                SELECT
                    (SELECT COUNT(1) FROM users WHERE is_active = 1) AS total_users,
                    COUNT(1) AS total_inspections,
                    COALESCE(SUM(CASE WHEN requested_review = 1 AND review_status != 'reviewed' THEN 1 ELSE 0 END), 0) AS pending_reviews,
                    COALESCE(SUM(CASE WHEN review_status = 'reviewed' THEN 1 ELSE 0 END), 0) AS reviewed_count,
                    COALESCE(SUM(CASE WHEN review_status = 'reviewed' AND agreed_with_ai = 1 THEN 1 ELSE 0 END), 0) AS agreed_count,
                    CASE 
                        WHEN SUM(CASE WHEN review_status = 'reviewed' THEN 1 ELSE 0 END) > 0 
                        THEN (SUM(CASE WHEN review_status = 'reviewed' AND agreed_with_ai = 1 THEN 1.0 ELSE 0.0 END) * 100.0) 
                             / SUM(CASE WHEN review_status = 'reviewed' THEN 1.0 ELSE 0.0 END)
                        ELSE 0.0 
                    END AS ai_agreement_rate,
                    COALESCE(SUM(CASE WHEN in_dataset = 1 THEN 1 ELSE 0 END), 0) AS dataset_count,
                    COALESCE(AVG(confidence), 0.0) AS avg_confidence,
                    (SELECT COUNT(1) FROM ChatMessages) AS total_chats
                FROM inspections;
                """
            )

        # Backfill case_id nếu có bản ghi cũ bị thiếu mã
        if c.is_sqlserver:
            try:
                c.execute("""
                UPDATE dbo.inspections
                SET case_id = 'PS-' + RIGHT('000000' + CAST(id AS VARCHAR(10)), 6)
                WHERE case_id IS NULL OR case_id = ''
                """)
            except Exception:
                pass
        else:
            try:
                c.execute("""
                UPDATE inspections
                SET case_id = printf('PS-%06d', id)
                WHERE case_id IS NULL OR case_id = ''
                """)
            except Exception:
                pass

        # Backfill predicted_label theo danh mục bệnh
        from services.project_data import load_classes_config
        classes_cfg = load_classes_config()
        for code, info in classes_cfg.items():
            name_vi = info.get("name_vi") or code
            try:
                c.execute(
                    "UPDATE inspections SET predicted_label = ? WHERE predicted_class = ? AND (predicted_label IS NULL OR predicted_label = '')",
                    (name_vi, code),
                )
            except Exception:
                pass

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        default_pw = _hash_password("123456")
        for acc in DEFAULT_RBAC_USERS:
            existing_u = c.execute("SELECT id FROM users WHERE LOWER(email)=?", (acc["email"].lower(),)).fetchone()
            if not existing_u:
                c.execute(
                    """INSERT INTO users
                    (email, username, password_hash, full_name, avatar_url, google_sub, role, auth_provider, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, '', ?, ?, 1, ?)""",
                    (
                        acc["email"],
                        acc["username"],
                        default_pw,
                        acc["full_name"],
                        acc["avatar_url"],
                        acc["role"],
                        acc["auth_provider"],
                        now_str,
                    ),
                )


def get_sample_gallery() -> list[dict]:
    """Return the 5 real pig skin images from PigSkinTech/case_images/ for running real AI model inference."""
    items = []
    for sample in SAMPLE_GALLERY_CASES:
        p = IMAGE_DIR / sample["filename"]
        items.append({**sample, "path": str(p), "image_path": str(p), "exists": p.is_file()})
    return items


def save(info, result, case=None, source_image=None):
    initialize()
    case = case or {}
    case_id = (case.get("case_id") or "").strip()
    archived_path = ""
    if source_image:
        source = Path(source_image)
        if not source.is_file() or source.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            raise ValueError("Không thể lưu ảnh hồ sơ không hợp lệ.")
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        destination = IMAGE_DIR / f"{uuid4().hex}{source.suffix.lower()}"
        shutil.copy2(source, destination)
        archived_path = str(destination)

    label = result.get("label") or ""
    cls_meta = get_class_info(label)
    display_label = (result.get("display_label") or cls_meta.get("name_vi") or str(label)).strip()
    danger_level = result.get("danger_level") or cls_meta.get("danger_level", "Trung bình")
    recommendation = result.get("recommendation") or cls_meta.get("treatment", "")
    inference_ms = float(result.get("inference_ms") or 0.0)

    try:
        with conn() as c:
            # Nếu chưa có case_id, tự động lấy số thứ tự tiếp theo để sinh mã PS-xxxxxx
            if not case_id:
                try:
                    max_row = c.execute("SELECT MAX(id) AS mid FROM inspections").fetchone()
                    next_id = (int(max_row["mid"] or 0)) + 1
                    case_id = f"PS-{next_id:06d}"
                except Exception:
                    case_id = f"PS-{uuid4().hex[:6].upper()}"

            cur = c.execute(
                """INSERT INTO inspections
                (filename,width,height,size_bytes,mode,predicted_class,predicted_label,confidence,created_at,image_path,
                 case_id,animal_id,farm_name,body_site,symptoms,onset_date,entered_at,review_status,
                 review_note,scores_json,model_info,user_id,user_email,user_name,requested_review,
                 danger_level,recommendation,inference_ms)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    info["name"],
                    int(info["width"]),
                    int(info["height"]),
                    int(info["bytes"]),
                    result.get("mode", "production"),
                    label,
                    display_label,
                    float(result.get("confidence") or 0.0),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    archived_path,
                    case_id,
                    case.get("animal_id", "").strip(),
                    case.get("farm_name", "").strip(),
                    case.get("body_site", "").strip(),
                    case.get("symptoms", "").strip(),
                    case.get("onset_date", "").strip(),
                    case.get("entered_at", "").strip(),
                    case.get("review_status", "needs_review"),
                    case.get("review_note", "").strip(),
                    json.dumps(result.get("scores", []), ensure_ascii=False),
                    str(result.get("model_info", "")),
                    int(case.get("user_id") or 1),
                    case.get("user_email", "nongdan.pigskin@gmail.com").strip(),
                    case.get("user_name", "Người chăn nuôi").strip(),
                    int(case.get("requested_review") or 0),
                    danger_level,
                    recommendation,
                    inference_ms,
                ),
            )
            row_id = int(cur.lastrowid or 0)
            if row_id == 0:
                try:
                    last_row = c.execute("SELECT MAX(id) AS mid FROM inspections").fetchone()
                    if last_row and last_row["mid"]:
                        row_id = int(last_row["mid"])
                except Exception:
                    pass

            if row_id > 0:
                actual_code = f"PS-{row_id:06d}"
                if case_id != actual_code:
                    c.execute("UPDATE inspections SET case_id=? WHERE id=?", (actual_code, row_id))
                    case_id = actual_code

            return row_id
    except Exception:
        if archived_path:
            Path(archived_path).unlink(missing_ok=True)
        raise


def ensure_case_code(record: dict) -> dict:
    """Bổ sung mã hồ sơ chuẩn `PS-000001` và tên nhãn tiếng Việt `predicted_label`."""
    if not (record.get("case_id") or "").strip():
        if record.get("id"):
            record["case_id"] = f"PS-{int(record['id']):06d}"
        else:
            record["case_id"] = record.get("animal_id") or "PS-000001"
    if not (record.get("predicted_label") or "").strip():
        pred_cls = record.get("predicted_class") or ""
        cls_info = get_class_info(pred_cls)
        record["predicted_label"] = cls_info.get("name_vi") or pred_cls
    if not (record.get("expert_display_name") or "").strip() and record.get("expert_label"):
        exp_cls = record.get("expert_label") or ""
        cls_info = get_class_info(exp_cls)
        record["expert_display_name"] = cls_info.get("name_vi") or exp_cls
    return record


def recent(keyword=""):
    initialize()
    with conn() as c:
        pattern = "%" + keyword + "%"
        rows = c.execute(
            """SELECT * FROM inspections
            WHERE filename LIKE ? OR case_id LIKE ? OR animal_id LIKE ? OR farm_name LIKE ?
            ORDER BY id DESC LIMIT 300""",
            (pattern, pattern, pattern, pattern),
        ).fetchall()
        return [ensure_case_code(dict(r)) for r in rows]


def list_user_inspections(user_email: str, date_filter: str = "", disease_filter: str = "all") -> list[dict]:
    initialize()
    clauses = ["LOWER(user_email) = LOWER(?)"]
    params: list[Any] = [user_email.strip()]

    if date_filter.strip():
        clauses.append("created_at LIKE ?")
        params.append(f"%{date_filter.strip()}%")
    if disease_filter and disease_filter != "all":
        clauses.append("COALESCE(NULLIF(expert_label, ''), predicted_class) = ?")
        params.append(disease_filter)

    where_sql = " AND ".join(clauses)
    with conn() as c:
        rows = c.execute(
            f"SELECT * FROM inspections WHERE {where_sql} ORDER BY id DESC",
            tuple(params),
        ).fetchall()
    return [ensure_case_code(dict(r)) for r in rows]


def request_expert_review(record_id: int) -> None:
    initialize()
    with conn() as c:
        c.execute(
            "UPDATE inspections SET requested_review=1, review_status='needs_review' WHERE id=?",
            (record_id,),
        )


def list_review_queue(confidence_threshold: float = 0.75) -> list[dict]:
    """Return cases sent by User for review OR where AI confidence < 75% via direct SQL SELECT."""
    initialize()
    with conn() as c:
        rows = c.execute(
            """SELECT * FROM inspections
            WHERE requested_review = 1
               OR (confidence IS NOT NULL AND confidence < ?)
               OR review_status = 'needs_review'
            ORDER BY CASE WHEN review_status='needs_review' THEN 0 ELSE 1 END, id DESC""",
            (confidence_threshold,),
        ).fetchall()
    return [ensure_case_code(dict(r)) for r in rows]


def submit_expert_review(
    record_id: int,
    agreed_with_ai: bool,
    expert_label: str,
    expert_note: str,
    expert_email: str,
) -> None:
    initialize()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with conn() as c:
        row = c.execute("SELECT predicted_class FROM inspections WHERE id=?", (record_id,)).fetchone()
        pred = row["predicted_class"] if row else ""
        final_label = pred if agreed_with_ai else (expert_label or pred)
        expert_cls_meta = get_class_info(final_label)
        expert_display = expert_cls_meta.get("name_vi") or final_label
        c.execute(
            """UPDATE inspections
            SET review_status='reviewed',
                agreed_with_ai=?,
                expert_label=?,
                expert_display_name=?,
                expert_note=?,
                review_note=?,
                reviewed_by=?,
                reviewed_at=?
            WHERE id=?""",
            (
                1 if agreed_with_ai else 0,
                final_label,
                expert_display,
                expert_note.strip(),
                expert_note.strip(),
                expert_email.strip(),
                now_str,
                record_id,
            ),
        )


def list_curated_candidates() -> list[dict]:
    """Return all cases that have been standardized/labeled by an Expert."""
    initialize()
    with conn() as c:
        rows = c.execute(
            """SELECT * FROM inspections
            WHERE review_status='reviewed' AND expert_label != ''
            ORDER BY reviewed_at DESC, id DESC"""
        ).fetchall()
    return [ensure_case_code(dict(r)) for r in rows]


def approve_for_dataset(record_id: int, approved: bool = True) -> str:
    """Mark a standardized expert-reviewed image as included in the clean training dataset."""
    initialize()
    with conn() as c:
        row = c.execute("SELECT * FROM inspections WHERE id=?", (record_id,)).fetchone()
        if not row:
            raise ValueError("Không tìm thấy bản ghi chẩn đoán.")
        c.execute("UPDATE inspections SET in_dataset=? WHERE id=?", (1 if approved else 0, record_id))
        if approved and row["image_path"] and Path(row["image_path"]).is_file():
            label_dir = CURATED_DIR / (row["expert_label"] or row["predicted_class"] or "Unlabeled")
            label_dir.mkdir(parents=True, exist_ok=True)
            dest = label_dir / f"{row['case_id']}_{Path(row['image_path']).name}"
            shutil.copy2(row["image_path"], dest)
            return str(dest)
    return ""


def get_system_stats() -> dict:
    """
    Truy vấn siêu tốc toàn bộ số liệu thống kê KPI chỉ trong 1 lần gọi DB qua View dbo.vw_DashboardKPIs,
    kèm phân bố bệnh và biểu đồ dịch tễ 7 ngày.
    """
    initialize()
    total_users = 0
    total_inspections = 0
    reviewed_count = 0
    agreed_count = 0
    pending_count = 0
    curated_count = 0
    avg_confidence = 0.0
    total_chats = 0
    ai_accuracy_vs_expert = 0.0

    with conn() as c:
        # 1. Truy vấn KPI gộp qua View dbo.vw_DashboardKPIs (1 lần gọi DB duy nhất)
        kpi_row = None
        try:
            view_name = "dbo.vw_DashboardKPIs" if c.is_sqlserver else "vw_DashboardKPIs"
            kpi_row = c.execute(f"SELECT * FROM {view_name}").fetchone()
        except Exception:
            kpi_row = None

        if kpi_row is not None:
            total_users = int(kpi_row.get("total_users") or 0)
            total_inspections = int(kpi_row.get("total_inspections") or 0)
            reviewed_count = int(kpi_row.get("reviewed_count") or 0)
            agreed_count = int(kpi_row.get("agreed_count") or 0)
            pending_count = int(
                kpi_row.get("pending_reviews")
                if kpi_row.get("pending_reviews") is not None
                else (kpi_row.get("pending_count") or max(0, total_inspections - reviewed_count))
            )
            curated_count = int(kpi_row.get("dataset_count") or kpi_row.get("curated_count") or 0)
            ai_accuracy_vs_expert = float(
                kpi_row.get("ai_agreement_rate")
                if kpi_row.get("ai_agreement_rate") is not None
                else ((agreed_count / reviewed_count * 100.0) if reviewed_count > 0 else 0.0)
            )
            avg_confidence = float(kpi_row.get("avg_confidence") or 0.0)
            total_chats = int(kpi_row.get("total_chats") or 0)
        else:
            # Fallback nếu View chưa tồn tại: gộp chung 1 câu SELECT duy nhất
            u_tbl = "dbo.users" if c.is_sqlserver else "users"
            i_tbl = "dbo.inspections" if c.is_sqlserver else "inspections"
            c_tbl = "dbo.ChatMessages" if c.is_sqlserver else "ChatMessages"
            single_sql = f"""
            SELECT
                (SELECT COUNT(1) FROM {u_tbl} WHERE is_active=1) AS total_users,
                (SELECT COUNT(1) FROM {i_tbl}) AS total_inspections,
                (SELECT COUNT(1) FROM {i_tbl} WHERE review_status='reviewed' AND agreed_with_ai IS NOT NULL) AS reviewed_count,
                (SELECT COUNT(1) FROM {i_tbl} WHERE review_status='reviewed' AND agreed_with_ai=1) AS agreed_count,
                (SELECT COUNT(1) FROM {i_tbl} WHERE review_status != 'reviewed') AS pending_count,
                (SELECT COUNT(1) FROM {i_tbl} WHERE in_dataset=1) AS curated_count,
                (SELECT COALESCE(AVG(confidence), 0.0) FROM {i_tbl}) AS avg_confidence,
                (SELECT COUNT(1) FROM {c_tbl}) AS total_chats
            """
            merged_row = c.execute(single_sql).fetchone()
            if merged_row:
                total_users = int(merged_row["total_users"] or 0)
                total_inspections = int(merged_row["total_inspections"] or 0)
                reviewed_count = int(merged_row["reviewed_count"] or 0)
                agreed_count = int(merged_row["agreed_count"] or 0)
                pending_count = int(merged_row["pending_count"] or 0)
                curated_count = int(merged_row["curated_count"] or 0)
                avg_confidence = float(merged_row["avg_confidence"] or 0.0)
                total_chats = int(merged_row["total_chats"] or 0)
                ai_accuracy_vs_expert = (agreed_count / reviewed_count * 100.0) if reviewed_count > 0 else 0.0

        # Nếu chưa có avg_confidence hoặc total_chats mà có inspections
        if avg_confidence == 0.0 and total_inspections > 0:
            try:
                avg_row = c.execute("SELECT AVG(confidence) AS avg_c FROM inspections").fetchone()
                if avg_row and avg_row["avg_c"] is not None:
                    avg_confidence = float(avg_row["avg_c"])
            except Exception:
                pass

        if total_chats == 0:
            try:
                chat_row = c.execute("SELECT COUNT(1) AS cnt FROM ChatMessages").fetchone()
                if chat_row and chat_row["cnt"] is not None:
                    total_chats = int(chat_row["cnt"])
            except Exception:
                pass

        # 2. Phân bố bệnh lý
        dist_rows = c.execute(
            """
            SELECT COALESCE(NULLIF(expert_label, ''), predicted_class) AS lbl, COUNT(*) AS cnt
            FROM inspections
            WHERE COALESCE(NULLIF(expert_label, ''), predicted_class) IS NOT NULL
              AND COALESCE(NULLIF(expert_label, ''), predicted_class) != ''
            GROUP BY COALESCE(NULLIF(expert_label, ''), predicted_class)
            ORDER BY cnt DESC
            """
        ).fetchall()

        # 3. Xu hướng 7 ngày
        date_expr = "LEFT(created_at, 10)" if c.is_sqlserver else "SUBSTR(created_at, 1, 10)"
        trend_rows = c.execute(
            f"""
            SELECT {date_expr} AS d, COUNT(*) AS cnt
            FROM inspections
            WHERE created_at IS NOT NULL AND created_at != ''
            GROUP BY {date_expr}
            ORDER BY d DESC
            """
        ).fetchall()

    distribution = {r["lbl"]: int(r["cnt"]) for r in dist_rows if r.get("lbl")}
    relabeled_count = max(0, reviewed_count - agreed_count)
    ai_accuracy_vs_expert = (agreed_count / reviewed_count * 100.0) if reviewed_count > 0 else 0.0

    # Phân loại mức độ nguy hiểm dịch tễ từ danh mục bệnh chuẩn
    from services.project_data import load_classes_config

    classes_cfg = load_classes_config()
    severity_counts = {"safe": 0, "warning": 0, "danger": 0}
    for cls_code, cnt in distribution.items():
        lvl = str((classes_cfg.get(cls_code) or {}).get("danger_level", "Trung bình")).strip()
        if lvl in ("An toàn", "Thấp") or cls_code == "Healthy":
            severity_counts["safe"] += cnt
        elif lvl in ("Cao", "Khẩn cấp"):
            severity_counts["danger"] += cnt
        else:
            severity_counts["warning"] += cnt

    daily_trend = [
        {"date": str(r["d"]), "count": int(r["cnt"] or 0)}
        for r in reversed(trend_rows[:7])
        if r.get("d")
    ]

    return {
        "total_users": total_users,
        "total_inspections": total_inspections,
        "reviewed_count": reviewed_count,
        "agreed_count": agreed_count,
        "relabeled_count": relabeled_count,
        "ai_accuracy_vs_expert": ai_accuracy_vs_expert,
        "avg_confidence": avg_confidence,
        "pending_count": pending_count,
        "curated_count": curated_count,
        "distribution": distribution,
        "severity_counts": severity_counts,
        "daily_trend": daily_trend,
        "total_chats": total_chats,
        "db_status": dict(_ACTIVE_DB_INFO),
    }


def sync_disease_catalog_to_sql(catalog: dict) -> None:
    """Đồng bộ danh mục bệnh lý & phác đồ điều trị từ models/classes.json vào bảng DiseaseCatalog trong SQL."""
    initialize()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with conn() as c:
        c.execute("DELETE FROM DiseaseCatalog")
        for code, info in (catalog or {}).items():
            if not isinstance(info, dict):
                continue
            c.execute(
                """INSERT INTO DiseaseCatalog (code, name_vi, danger_level, symptoms, prevention, treatment, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(code).strip(),
                    str(info.get("name_vi") or code).strip(),
                    str(info.get("danger_level") or "Trung bình").strip(),
                    str(info.get("symptoms") or "").strip(),
                    str(info.get("prevention") or "").strip(),
                    str(info.get("treatment") or "").strip(),
                    now_str,
                ),
            )


def list_users(role_filter: str = "all", search_query: str = "") -> list[dict]:
    initialize()
    clauses = []
    params: list[Any] = []
    if role_filter and role_filter != "all":
        clauses.append("role = ?")
        params.append(role_filter)
    q = (search_query or "").strip()
    if q:
        like_q = f"%{q}%"
        clauses.append("(LOWER(full_name) LIKE LOWER(?) OR LOWER(email) LIKE LOWER(?) OR LOWER(username) LIKE LOWER(?))")
        params.extend([like_q, like_q, like_q])
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with conn() as c:
        rows = c.execute(f"SELECT * FROM users {where_sql} ORDER BY id ASC", tuple(params)).fetchall()
    return [dict(r) for r in rows]


def create_user_account(
    email: str,
    full_name: str,
    role: str = "user",
    auth_provider: str = "local",
    password: str = "123456",
) -> dict:
    initialize()
    clean_email = (email or "").strip().lower()
    clean_name = (full_name or "").strip()
    if not clean_email or "@" not in clean_email:
        raise ValueError("Email không hợp lệ.")
    if not clean_name:
        clean_name = clean_email.split("@")[0].replace(".", " ").title()
    if role not in ("user", "expert", "admin"):
        role = "user"
    username = clean_email.split("@")[0]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with conn() as c:
        existing = c.execute("SELECT id FROM users WHERE LOWER(email)=?", (clean_email,)).fetchone()
        if existing:
            raise ValueError(f"Email '{clean_email}' đã tồn tại trong hệ thống.")
        cur = c.execute(
            """INSERT INTO users
            (email, username, password_hash, full_name, avatar_url, google_sub, role, auth_provider, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, '', ?, ?, 1, ?)""",
            (
                clean_email,
                username,
                _hash_password(password or "123456"),
                clean_name,
                f"https://ui-avatars.com/api/?name={clean_name.replace(' ', '+')}&background=059669&color=fff",
                role,
                auth_provider,
                now_str,
            ),
        )
        row = c.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(row)


def toggle_user_lock(user_id: int) -> bool:
    initialize()
    with conn() as c:
        row = c.execute("SELECT is_active FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise ValueError("Không tìm thấy người dùng.")
        new_state = 0 if int(row["is_active"]) == 1 else 1
        c.execute("UPDATE users SET is_active=? WHERE id=?", (new_state, user_id))
        return bool(new_state)


def update_user_role(user_id: int, new_role: str) -> None:
    if new_role not in ("user", "expert", "admin"):
        raise ValueError("Role không hợp lệ.")
    initialize()
    with conn() as c:
        c.execute("UPDATE users SET role=? WHERE id=?", (new_role, user_id))


def delete(record_id):
    initialize()
    with conn() as c:
        row = c.execute("SELECT image_path FROM inspections WHERE id=?", (record_id,)).fetchone()
        c.execute("DELETE FROM inspections WHERE id=?", (record_id,))
    if row and row["image_path"]:
        image_file = Path(row["image_path"]).resolve()
        archive_root = IMAGE_DIR.resolve()
        if archive_root in image_file.parents:
            try:
                image_file.unlink(missing_ok=True)
            except OSError:
                pass


def update_review(record_id, status, note=""):
    allowed = {"needs_review", "reviewed", "lab_requested", "closed"}
    if status not in allowed:
        raise ValueError("Trạng thái rà soát không hợp lệ.")
    initialize()
    with conn() as c:
        c.execute(
            "UPDATE inspections SET review_status=?,review_note=? WHERE id=?",
            (status, note.strip(), record_id),
        )


def update_case(record_id, case):
    initialize()
    with conn() as c:
        cur = c.execute(
            """UPDATE inspections SET animal_id=?,farm_name=?,body_site=?,
            symptoms=?,onset_date=?,entered_at=? WHERE id=?""",
            (
                case.get("animal_id", "").strip(),
                case.get("farm_name", "").strip(),
                case.get("body_site", "").strip(),
                case.get("symptoms", "").strip(),
                case.get("onset_date", "").strip(),
                case.get("entered_at", "").strip(),
                record_id,
            ),
        )
        return cur.rowcount > 0


# --- ChatMessages SQL Persistence ---

def save_chat_message(
    user_email: str,
    role: str,
    content: str,
    user_id: int | None = None,
    case_id: str = "",
    model_name: str = "",
) -> int:
    """Ghi trực tiếp tin nhắn hội thoại Chatbot vào bảng ChatMessages trong SQL Database."""
    initialize()
    final_content = (content or "").strip()
    if role == "assistant":
        from services.chatbot_service import ensure_disclaimer

        final_content = ensure_disclaimer(final_content)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_email = (user_email or "nongdan.pigskin@gmail.com").strip().lower()
    with conn() as c:
        cur = c.execute(
            """INSERT INTO ChatMessages (timestamp, user_id, user_email, role, content, case_id, model_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (now_str, user_id, clean_email, role, final_content, str(case_id or ""), str(model_name or "")),
        )
        return int(cur.lastrowid or 0)


def list_chat_messages(user_email: str, limit: int = 60) -> list[dict]:
    """Truy vấn lịch sử chat từ bảng ChatMessages trong SQL Database."""
    initialize()
    from services.chatbot_service import ensure_disclaimer

    clean_email = (user_email or "nongdan.pigskin@gmail.com").strip().lower()
    with conn() as c:
        rows = c.execute(
            "SELECT id, timestamp, user_id, user_email, role, content, case_id, model_name FROM ChatMessages WHERE LOWER(user_email)=? ORDER BY id DESC",
            (clean_email,),
        ).fetchall()
    items = []
    for r in rows[:limit]:
        item = dict(r)
        if item.get("role") == "assistant":
            item["content"] = ensure_disclaimer(str(item.get("content") or ""))
        items.append(item)
    items.reverse()
    return items


def clear_chat_messages(user_email: str) -> None:
    initialize()
    clean_email = (user_email or "nongdan.pigskin@gmail.com").strip().lower()
    with conn() as c:
        c.execute("DELETE FROM ChatMessages WHERE LOWER(user_email)=?", (clean_email,))


initialize()
