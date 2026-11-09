"""SQLite persistence for users, RBAC roles, diagnosis history, expert reviews, and dataset curation."""
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw

from services.project_data import get_class_info


DB = Path(__file__).resolve().parents[1] / "pigskin_history.db"
IMAGE_DIR = Path(__file__).resolve().parents[1] / "case_images"
CURATED_DIR = Path(__file__).resolve().parents[1] / "curated_dataset"

CASE_COLUMNS = {
    "case_id": "TEXT NOT NULL DEFAULT ''",
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

MOCK_GOOGLE_ACCOUNTS = [
    {
        "email": "nongdan.pigskin@gmail.com",
        "username": "nongdan",
        "full_name": "Nguyễn Văn Nông (Chủ trại)",
        "role": "user",
        "auth_provider": "google",
        "avatar_url": "https://ui-avatars.com/api/?name=Nguyen+Nong&background=2E7D32&color=fff",
    },
    {
        "email": "bs.thuy.pigskin@gmail.com",
        "username": "bsthuy",
        "full_name": "BS. Trần Thị Thúy (Thú y)",
        "role": "expert",
        "auth_provider": "google",
        "avatar_url": "https://ui-avatars.com/api/?name=BS+Thuy&background=1565C0&color=fff",
    },
    {
        "email": "admin.pigskin@gmail.com",
        "username": "admin",
        "full_name": "Quản trị viên PigSkinTech",
        "role": "admin",
        "auth_provider": "google",
        "avatar_url": "https://ui-avatars.com/api/?name=Admin+PigSkin&background=AD1457&color=fff",
    },
    {
        "email": "traiheo.local@pigskin.vn",
        "username": "traiheo",
        "full_name": "Trại Heo Hòa Bình (Local)",
        "role": "user",
        "auth_provider": "local",
        "avatar_url": "https://ui-avatars.com/api/?name=Trai+Heo&background=546E7A&color=fff",
    },
]


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def _ensure_demo_image(filename: str, color: tuple[int, int, int], spot_color: tuple[int, int, int]) -> str:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    target = IMAGE_DIR / filename
    if not target.is_file():
        img = Image.new("RGB", (320, 240), color)
        draw = ImageDraw.Draw(img)
        draw.ellipse((70, 50, 170, 140), fill=spot_color, outline=(120, 60, 60), width=3)
        draw.ellipse((150, 95, 245, 185), fill=spot_color, outline=(120, 60, 60), width=2)
        img.save(target, format="JPEG", quality=85)
    return str(target)


def initialize():
    with conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL DEFAULT '',
                password_hash TEXT NOT NULL DEFAULT '',
                full_name TEXT NOT NULL DEFAULT '',
                avatar_url TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'user',
                auth_provider TEXT NOT NULL DEFAULT 'google',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                size_bytes INTEGER NOT NULL,
                mode TEXT NOT NULL,
                predicted_class TEXT,
                confidence REAL,
                created_at TEXT NOT NULL
            )"""
        )
        existing = {row["name"] for row in c.execute("PRAGMA table_info(inspections)")}
        for name, definition in CASE_COLUMNS.items():
            if name not in existing:
                c.execute(f"ALTER TABLE inspections ADD COLUMN {name} {definition}")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        default_pw = _hash_password("123456")
        for acc in MOCK_GOOGLE_ACCOUNTS:
            c.execute(
                """INSERT OR IGNORE INTO users
                (email, username, password_hash, full_name, avatar_url, role, auth_provider, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
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

        count_rows = c.execute("SELECT COUNT(*) AS cnt FROM inspections").fetchone()["cnt"]
        if count_rows == 0:
            _seed_mock_inspections(c)
        else:
            for item in SAMPLE_GALLERY_CASES:
                real_file = IMAGE_DIR / item["filename"]
                if real_file.is_file():
                    c.execute(
                        "UPDATE inspections SET image_path=?, size_bytes=? WHERE filename=?",
                        (str(real_file), real_file.stat().st_size, item["filename"]),
                    )


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


def get_sample_gallery() -> list[dict]:
    """Return the 5 real sample images from PigSkinTech/case_images/ for quick testing."""
    items = []
    for sample in SAMPLE_GALLERY_CASES:
        p = IMAGE_DIR / sample["filename"]
        items.append({**sample, "path": str(p), "image_path": str(p), "exists": p.is_file()})
    return items


def _seed_mock_inspections(c: sqlite3.Connection):
    samples = [
        {
            "filename": "heo_dong_dau_01.jpg",
            "bg": (232, 185, 178),
            "spot": (185, 52, 62),
            "predicted_class": "Infected_Bacterial_Erysipelas",
            "confidence": 0.892,
            "created_at": "2026-11-01 08:30:00",
            "animal_id": "PIG-101",
            "farm_name": "Trại An Phú - Khu A",
            "body_site": "Vùng lưng và hông",
            "symptoms": "Mảng đỏ hình thoi nổi rõ trên da lưng, heo sốt 41.2°C.",
            "review_status": "needs_review",
            "requested_review": 1,
            "agreed_with_ai": None,
            "expert_label": "",
            "expert_note": "",
            "reviewed_by": "",
            "reviewed_at": "",
            "in_dataset": 0,
            "user_email": "nongdan.pigskin@gmail.com",
            "user_name": "Nguyễn Văn Nông (Chủ trại)",
        },
        {
            "filename": "heo_nghi_ghe_02.jpg",
            "bg": (222, 196, 180),
            "spot": (140, 118, 98),
            "predicted_class": "Infected_Parasitic_Mange",
            "confidence": 0.645,
            "created_at": "2026-11-02 14:15:00",
            "animal_id": "PIG-108",
            "farm_name": "Trại An Phú - Khu B",
            "body_site": "Vành tai và cổ",
            "symptoms": "Da đóng vảy xám dày, heo cọ sát vào vách chuồng liên tục.",
            "review_status": "needs_review",
            "requested_review": 0,
            "agreed_with_ai": None,
            "expert_label": "",
            "expert_note": "",
            "reviewed_by": "",
            "reviewed_at": "",
            "in_dataset": 0,
            "user_email": "nongdan.pigskin@gmail.com",
            "user_name": "Nguyễn Văn Nông (Chủ trại)",
        },
        {
            "filename": "heo_viem_da_tiet_dich_03.jpg",
            "bg": (215, 175, 160),
            "spot": (95, 65, 50),
            "predicted_class": "Infected_Bacterial_Greasy_Pig_Disease",
            "confidence": 0.918,
            "created_at": "2026-10-30 09:45:00",
            "animal_id": "PIG-089",
            "farm_name": "Trại An Phú - Khu A",
            "body_site": "Quanh mặt và cổ",
            "symptoms": "Da rỉ dịch nhờn nâu đen, đóng vảy nứt nẻ ở heo con cai sữa.",
            "review_status": "reviewed",
            "requested_review": 1,
            "agreed_with_ai": 1,
            "expert_label": "Infected_Bacterial_Greasy_Pig_Disease",
            "expert_note": "Xác nhận viêm da tiết dịch. Tắm Iodine 1% ngày 1 lần, tiêm Amoxicillin LA 15mg/kg TT trong 4 ngày và bổ sung điện giải.",
            "reviewed_by": "bs.thuy.pigskin@gmail.com",
            "reviewed_at": "2026-10-30 11:20:00",
            "in_dataset": 1,
            "user_email": "nongdan.pigskin@gmail.com",
            "user_name": "Nguyễn Văn Nông (Chủ trại)",
        },
        {
            "filename": "heo_nam_da_04.jpg",
            "bg": (228, 192, 175),
            "spot": (165, 110, 82),
            "predicted_class": "Infected_Environmental_Dermatitis",
            "confidence": 0.682,
            "created_at": "2026-10-31 16:10:00",
            "animal_id": "PIG-094",
            "farm_name": "Trại Hòa Bình",
            "body_site": "Vùng vai trái",
            "symptoms": "Vết tròn rụng lông, viền đỏ nhẹ có vảy trắng mịn.",
            "review_status": "reviewed",
            "requested_review": 1,
            "agreed_with_ai": 0,
            "expert_label": "Infected_Fungal_Ringworm",
            "expert_note": "AI nhầm với viêm da môi trường. Tổn thương hình đồng xu điển hình của Nấm da (Ringworm). Bôi cồn Iodine 3% hoặc Ketoconazole 2 lần/ngày trong 7 ngày.",
            "reviewed_by": "bs.thuy.pigskin@gmail.com",
            "reviewed_at": "2026-11-01 08:05:00",
            "in_dataset": 0,
            "user_email": "nongdan.pigskin@gmail.com",
            "user_name": "Nguyễn Văn Nông (Chủ trại)",
        },
        {
            "filename": "heo_khoe_manh_05.jpg",
            "bg": (242, 205, 198),
            "spot": (236, 198, 190),
            "predicted_class": "Healthy",
            "confidence": 0.974,
            "created_at": "2026-11-02 10:00:00",
            "animal_id": "PIG-112",
            "farm_name": "Trại An Phú - Khu C",
            "body_site": "Toàn thân",
            "symptoms": "Da hồng hào, ăn uống bình thường.",
            "review_status": "reviewed",
            "requested_review": 0,
            "agreed_with_ai": 1,
            "expert_label": "Healthy",
            "expert_note": "Da heo khỏe mạnh bình thường, tiếp tục duy trì lịch tiêm phòng.",
            "reviewed_by": "bs.thuy.pigskin@gmail.com",
            "reviewed_at": "2026-11-02 11:00:00",
            "in_dataset": 1,
            "user_email": "nongdan.pigskin@gmail.com",
            "user_name": "Nguyễn Văn Nông (Chủ trại)",
        },
    ]
    for idx, s in enumerate(samples, start=1):
        img_path = _ensure_demo_image(s["filename"], s["bg"], s["spot"])
        cls_meta = get_class_info(s["predicted_class"])
        scores = [
            {"label": s["predicted_class"], "confidence": s["confidence"]},
            {"label": "Healthy", "confidence": round(max(0.01, 1.0 - s["confidence"]), 3)},
        ]
        c.execute(
            """INSERT INTO inspections (
                filename, width, height, size_bytes, mode, predicted_class, confidence,
                created_at, image_path, case_id, animal_id, farm_name, body_site, symptoms,
                onset_date, entered_at, review_status, review_note, scores_json, model_info,
                user_id, user_email, user_name, requested_review, agreed_with_ai,
                expert_label, expert_note, reviewed_by, reviewed_at, in_dataset,
                danger_level, recommendation
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                s["filename"],
                320,
                240,
                14200,
                "ai",
                s["predicted_class"],
                s["confidence"],
                s["created_at"],
                img_path,
                f"PS-{idx:06d}",
                s["animal_id"],
                s["farm_name"],
                s["body_site"],
                s["symptoms"],
                s["created_at"][:10],
                s["created_at"],
                s["review_status"],
                s["expert_note"],
                json.dumps(scores, ensure_ascii=False),
                "mobilenet_v2 | 20261029_161050 | CPU",
                1,
                s["user_email"],
                s["user_name"],
                s["requested_review"],
                s["agreed_with_ai"],
                s["expert_label"],
                s["expert_note"],
                s["reviewed_by"],
                s["reviewed_at"],
                s["in_dataset"],
                cls_meta.get("danger_level", "Trung bình"),
                cls_meta.get("treatment", ""),
            ),
        )


def save(info, result, case=None, source_image=None):
    initialize()
    case = case or {}
    case_id = case.get("case_id", "").strip()
    archived_path = ""
    if source_image:
        source = Path(source_image)
        if not source.is_file() or source.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            raise ValueError("Không thể lưu ảnh hồ sơ không hợp lệ.")
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        destination = IMAGE_DIR / f"{uuid4().hex}{source.suffix.lower()}"
        shutil.copy2(source, destination)
        archived_path = str(destination)
    label = result.get("label")
    cls_meta = get_class_info(label)
    danger_level = result.get("danger_level") or cls_meta.get("danger_level", "Trung bình")
    recommendation = result.get("recommendation") or cls_meta.get("treatment", "")
    try:
        with conn() as c:
            cur = c.execute(
                """INSERT INTO inspections
                (filename,width,height,size_bytes,mode,predicted_class,confidence,created_at,image_path,
                 case_id,animal_id,farm_name,body_site,symptoms,onset_date,entered_at,review_status,
                 review_note,scores_json,model_info,user_id,user_email,user_name,requested_review,
                 danger_level,recommendation)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    info["name"],
                    info["width"],
                    info["height"],
                    info["bytes"],
                    result["mode"],
                    label,
                    result.get("confidence"),
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
                    result.get("model_info", ""),
                    int(case.get("user_id") or 1),
                    case.get("user_email", "nongdan.pigskin@gmail.com").strip(),
                    case.get("user_name", "Người chăn nuôi").strip(),
                    int(case.get("requested_review") or 0),
                    danger_level,
                    recommendation,
                ),
            )
            if not case_id:
                case_id = f"PS-{cur.lastrowid:06d}"
                c.execute("UPDATE inspections SET case_id=? WHERE id=?", (case_id, cur.lastrowid))
            return cur.lastrowid
    except Exception:
        if archived_path:
            Path(archived_path).unlink(missing_ok=True)
        raise


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
        return [dict(r) for r in rows]


def list_user_inspections(user_email: str, date_filter: str = "", disease_filter: str = "all") -> list[dict]:
    initialize()
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM inspections WHERE LOWER(user_email)=LOWER(?) ORDER BY id DESC",
            (user_email.strip(),),
        ).fetchall()
    items = [dict(r) for r in rows]
    if date_filter.strip():
        q = date_filter.strip()
        items = [it for it in items if q in (it.get("created_at") or "")]
    if disease_filter and disease_filter != "all":
        items = [
            it for it in items
            if (it.get("expert_label") or it.get("predicted_class")) == disease_filter
        ]
    return items


def request_expert_review(record_id: int) -> None:
    initialize()
    with conn() as c:
        c.execute(
            "UPDATE inspections SET requested_review=1, review_status='needs_review' WHERE id=?",
            (record_id,),
        )


def list_review_queue(confidence_threshold: float = 0.75) -> list[dict]:
    """Return cases sent by User for review OR where AI confidence < 75%."""
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
    return [dict(r) for r in rows]


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
        c.execute(
            """UPDATE inspections
            SET review_status='reviewed',
                agreed_with_ai=?,
                expert_label=?,
                expert_note=?,
                review_note=?,
                reviewed_by=?,
                reviewed_at=?
            WHERE id=?""",
            (
                1 if agreed_with_ai else 0,
                final_label,
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
    return [dict(r) for r in rows]


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
    initialize()
    with conn() as c:
        total_users = c.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"]
        rows = [dict(r) for r in c.execute("SELECT * FROM inspections").fetchall()]
    total_inspections = len(rows)
    reviewed = [r for r in rows if r.get("review_status") == "reviewed" and r.get("agreed_with_ai") is not None]
    agreed = sum(1 for r in reviewed if int(r.get("agreed_with_ai") or 0) == 1)
    ai_accuracy_vs_expert = (agreed / len(reviewed) * 100.0) if reviewed else 0.0
    pending_count = sum(1 for r in rows if r.get("review_status") != "reviewed")
    curated_count = sum(1 for r in rows if int(r.get("in_dataset") or 0) == 1)
    distribution = {}
    for r in rows:
        lbl = r.get("expert_label") or r.get("predicted_class")
        if lbl:
            distribution[lbl] = distribution.get(lbl, 0) + 1
    return {
        "total_users": total_users,
        "total_inspections": total_inspections,
        "reviewed_count": len(reviewed),
        "agreed_count": agreed,
        "ai_accuracy_vs_expert": ai_accuracy_vs_expert,
        "pending_count": pending_count,
        "curated_count": curated_count,
        "distribution": distribution,
    }


def list_users(role_filter: str = "all", search_query: str = "") -> list[dict]:
    initialize()
    with conn() as c:
        if role_filter and role_filter != "all":
            rows = c.execute("SELECT * FROM users WHERE role=? ORDER BY id ASC", (role_filter,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
    items = [dict(r) for r in rows]
    q = (search_query or "").strip().lower()
    if q:
        items = [
            u for u in items
            if q in (u.get("full_name") or "").lower()
            or q in (u.get("email") or "").lower()
            or q in (u.get("username") or "").lower()
        ]
    return items


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
            (email, username, password_hash, full_name, avatar_url, role, auth_provider, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
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
    with conn() as c:
        c.execute(
            "UPDATE inspections SET review_status=?,review_note=? WHERE id=?",
            (status, note.strip(), record_id),
        )


def update_case(record_id, case):
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


initialize()
