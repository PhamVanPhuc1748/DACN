"""SQLite schema + seed dữ liệu demo.

Schema bám theo docs/case-thu-muc-database-dataset.md, bổ sung:
users, audit_logs, settings, images.stem_id, image_labels.verified_by_vet,
predictions.(pen, herd_code, notes, review_status, final_class_id, top3, inference_ms).
"""
import json
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # DACN/
STORAGE = Path(__file__).resolve().parents[1] / "storage"
UPLOADS = STORAGE / "uploads"
DB_PATH = STORAGE / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, full_name TEXT,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('ADMIN','AI_ENGINEER','VET','FARM_OWNER')),
  is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT DEFAULT (datetime('now','localtime')));

CREATE TABLE IF NOT EXISTS disease_classes(
  id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, name_en TEXT,
  group_name TEXT, cause TEXT, description TEXT, treatment TEXT, prevention TEXT,
  is_dangerous INTEGER NOT NULL DEFAULT 0, color TEXT);

CREATE TABLE IF NOT EXISTS images(
  id INTEGER PRIMARY KEY, uri TEXT, sha256 TEXT, stem_id TEXT, width INTEGER, height INTEGER,
  source TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
CREATE INDEX IF NOT EXISTS ix_images_source ON images(source);

CREATE TABLE IF NOT EXISTS image_labels(
  id INTEGER PRIMARY KEY, image_id INTEGER NOT NULL REFERENCES images(id),
  class_id INTEGER NOT NULL REFERENCES disease_classes(id),
  status TEXT NOT NULL CHECK(status IN ('PSEUDO','VERIFIED','REJECTED')),
  annotator TEXT, verified_by_vet INTEGER NOT NULL DEFAULT 0, confidence REAL, note TEXT,
  reviewed_at TEXT);

CREATE TABLE IF NOT EXISTS dataset_versions(
  id INTEGER PRIMARY KEY, name TEXT, version TEXT UNIQUE NOT NULL, seed INTEGER,
  created_at TEXT DEFAULT (datetime('now','localtime')), notes TEXT);

CREATE TABLE IF NOT EXISTS dataset_members(
  dataset_version_id INTEGER NOT NULL REFERENCES dataset_versions(id),
  image_id INTEGER NOT NULL REFERENCES images(id),
  split TEXT NOT NULL CHECK(split IN ('train','val','test')),
  PRIMARY KEY(dataset_version_id, image_id));

CREATE TABLE IF NOT EXISTS model_versions(
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, architecture TEXT,
  task TEXT NOT NULL CHECK(task IN ('classification','detection')),
  dataset_version_id INTEGER REFERENCES dataset_versions(id), artifact_uri TEXT,
  config TEXT, metrics TEXT, latency_ms REAL, is_default INTEGER NOT NULL DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now','localtime')));

CREATE TABLE IF NOT EXISTS predictions(
  id INTEGER PRIMARY KEY, image_id INTEGER REFERENCES images(id), image_uri TEXT,
  model_version_id INTEGER REFERENCES model_versions(id),
  predicted_class_id INTEGER REFERENCES disease_classes(id), confidence REAL,
  top3 TEXT, inference_ms REAL, pen TEXT, herd_code TEXT, notes TEXT,
  created_by INTEGER REFERENCES users(id),
  review_status TEXT NOT NULL DEFAULT 'PENDING' CHECK(review_status IN ('PENDING','CONFIRMED','CORRECTED')),
  final_class_id INTEGER REFERENCES disease_classes(id), review_note TEXT, reviewed_by INTEGER,
  created_at TEXT DEFAULT (datetime('now','localtime')));
CREATE INDEX IF NOT EXISTS ix_pred_created ON predictions(created_at);

CREATE TABLE IF NOT EXISTS audit_logs(
  id INTEGER PRIMARY KEY, user_id INTEGER, username TEXT, action TEXT, detail TEXT,
  created_at TEXT DEFAULT (datetime('now','localtime')));

CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

# (code, name, name_en, group, cause, description/dấu hiệu, treatment, prevention, dangerous, color)
DISEASES = [
    ("HEALTHY", "Heo khỏe mạnh", "Healthy", "Đối chứng", "—",
     "Da hồng hào, đều màu, lông mượt, không có ban đỏ, vảy, mụn nước hay vết loét.",
     "Không cần xử lý. Tiếp tục theo dõi định kỳ.",
     "Duy trì vệ sinh chuồng trại, dinh dưỡng cân đối, tiêm phòng đúng lịch.", 0, "#34d399"),
    ("BACT_ERY", "Đóng dấu son (Đóng dấu lợn)", "Bacterial Erysipelas", "Vi khuẩn",
     "Vi khuẩn Erysipelothrix rhusiopathiae",
     "Ban đỏ đến tím sẫm hình thoi / hình vuông nổi gờ trên da lưng, sườn, bụng; heo sốt cao, bỏ ăn.",
     "Cách ly ngay. Báo bác sĩ thú y để dùng kháng sinh nhóm Penicillin theo chỉ định.",
     "Tiêm vắc-xin đóng dấu định kỳ, sát trùng chuồng, xử lý xác heo bệnh đúng quy định.", 1, "#f43f5e"),
    ("BACT_GPD", "Viêm da tiết dịch", "Greasy Pig Disease", "Vi khuẩn",
     "Vi khuẩn Staphylococcus hyicus",
     "Da nhờn, rỉ dịch, đóng vảy nâu đen bắt đầu từ mặt, tai rồi lan toàn thân; thường gặp ở heo con.",
     "Tắm sát trùng da, kháng sinh theo kháng sinh đồ, bù nước điện giải.",
     "Giảm trầy xước (mài nanh, lót sàn), giữ chuồng khô, sát trùng khu đẻ.", 0, "#fb923c"),
    ("ENV_DERM", "Viêm da do môi trường", "Environmental Dermatitis", "Môi trường",
     "Nền chuồng ẩm ướt, thô ráp, hóa chất, chất độn bẩn",
     "Da đỏ, sần, trầy xước tập trung ở vùng tiếp xúc nền (đầu gối, bụng, mông).",
     "Loại bỏ nguyên nhân tiếp xúc, rửa sạch, bôi thuốc sát trùng tại chỗ.",
     "Nền chuồng khô ráo, phẳng, thay chất độn thường xuyên.", 0, "#facc15"),
    ("ENV_SUN", "Cháy nắng", "Environmental Sunburn", "Môi trường",
     "Tiếp xúc tia UV kéo dài, phổ biến ở heo da trắng",
     "Da đỏ rực, nóng, bong tróc ở lưng, tai, gáy; dễ nhầm với viêm da (ENV_DERM).",
     "Đưa heo vào bóng mát, làm mát, bôi dịu da.",
     "Bố trí mái che, vùng tắm mát; hạn chế chăn thả giờ nắng gắt.", 0, "#f59e0b"),
    ("FUNG_ROSEA", "Vảy phấn hồng", "Pityriasis Rosea", "Nấm / chưa rõ",
     "Chưa xác định rõ; có yếu tố di truyền, thường xếp nhóm bệnh da dạng nấm",
     "Các vòng tròn đỏ viền nổi, giữa đóng vảy, lan rộng ở bụng và đùi trong; heo 3–14 tuần tuổi.",
     "Thường tự khỏi sau 4–8 tuần; theo dõi, chống nhiễm trùng thứ phát.",
     "Theo dõi dòng giống có tiền sử bệnh.", 0, "#e879f9"),
    ("FUNG_RING", "Nấm da (Lác đồng tiền)", "Ringworm", "Nấm",
     "Nấm Microsporum nanum, Trichophyton spp.",
     "Mảng tròn màu nâu đỏ, khô, có vảy, lan dần ra ngoài; ít ngứa.",
     "Sát trùng bằng thuốc kháng nấm tại chỗ theo hướng dẫn thú y.",
     "Giữ chuồng thông thoáng, khô, sát trùng dụng cụ, cách ly heo nhiễm.", 0, "#a78bfa"),
    ("PARA_MANGE", "Ghẻ (Ghẻ sảy)", "Sarcoptic Mange", "Ký sinh trùng",
     "Cái ghẻ Sarcoptes scabiei var. suis",
     "Ngứa dữ dội, heo cọ xát; da dày, sần sùi, vảy xám ở tai, cổ, chân.",
     "Dùng thuốc trị ký sinh trùng (Ivermectin…) theo chỉ định, xử lý cả đàn.",
     "Tẩy ký sinh trùng định kỳ cho nái trước đẻ, cách ly heo mới nhập.", 0, "#38bdf8"),
    ("VIRA_FMD", "Lở mồm long móng", "Foot and Mouth Disease", "Virus",
     "Virus FMD (Aphthovirus)",
     "Mụn nước ở mõm, lưỡi, vành móng, kẽ chân; vỡ thành vết loét; heo què, sốt, chảy dãi.",
     "BỆNH PHẢI BÁO CÁO: cách ly toàn khu, báo ngay cơ quan thú y địa phương, không tự điều trị.",
     "Tiêm vắc-xin LMLM đúng lịch, kiểm soát ra vào trại, sát trùng phương tiện.", 1, "#ef4444"),
    ("VIRA_POX", "Đậu heo", "Swinepox", "Virus",
     "Virus Suipoxvirus, lây qua chấy rận",
     "Nốt sẩn đỏ → mụn nước → mụn mủ → vảy đen tròn ở bụng, sườn, mặt trong đùi.",
     "Chăm sóc hỗ trợ, chống nhiễm trùng thứ phát; diệt chấy rận.",
     "Diệt ký sinh trùng ngoài da (chấy rận), vệ sinh chuồng.", 0, "#2dd4bf"),
]

MODELS = [  # name, arch, task, artifact, latency, metrics
    ("MobileNetV3-Large", "mobilenet_v3_large", "classification", "ml_workspace/models/mobilenetv3_large.pt", 6.1,
     {"accuracy": 0.891, "macro_f1": 0.862, "params_m": 5.4}),
    ("EfficientNet-B0", "efficientnet_b0", "classification", "ml_workspace/models/efficientnet_b0.pt", 9.8,
     {"accuracy": 0.924, "macro_f1": 0.903, "params_m": 5.3}),
    ("ResNet50", "resnet50", "classification", "ml_workspace/models/resnet50.pt", 18.4,
     {"accuracy": 0.912, "macro_f1": 0.884, "params_m": 25.6}),
    ("YOLOv8s", "yolov8s", "detection", "ml_workspace/models/yolov8s.pt", 12.3,
     {"accuracy": 0.887, "macro_f1": 0.851, "map50": 0.781, "params_m": 11.2}),
    ("YOLO11s", "yolo11s", "detection", "ml_workspace/models/yolo11s.pt", 10.7,
     {"accuracy": 0.902, "macro_f1": 0.871, "map50": 0.812, "params_m": 9.4}),
]

SETTINGS = {
    "default_conf_threshold": "0.35",  # ngưỡng hiển thị bbox / vùng nhiệt
    "review_threshold": "0.70",        # confidence < ngưỡng → cần bác sĩ khám lại
    "outbreak_threshold": "3",         # số ca bệnh nguy hiểm / khu chuồng / cửa sổ ngày
    "outbreak_window_days": "7",
}

PENS = ["Khu A1", "Khu A2", "Khu B1", "Khu B2", "Khu C1"]


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def get_settings(conn) -> dict:
    return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}


def audit(conn, user: dict | None, action: str, detail: str = ""):
    conn.execute("INSERT INTO audit_logs(user_id, username, action, detail) VALUES(?,?,?,?)",
                 (user and user["id"], user and user["username"], action, detail))


def init_db():
    UPLOADS.mkdir(parents=True, exist_ok=True)
    conn = connect()
    conn.executescript(SCHEMA)
    if not conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        _seed(conn)
    conn.commit()
    conn.close()


def _seed(conn):
    from .auth import hash_password

    rnd = random.Random(42)
    for u, name, role in [("admin", "Quản trị viên", "ADMIN"), ("engineer", "Kỹ sư AI", "AI_ENGINEER"),
                          ("vet", "BS. Thú y Nguyễn An", "VET"), ("owner", "Chủ trại Trần Bình", "FARM_OWNER")]:
        conn.execute("INSERT INTO users(username, full_name, password_hash, role) VALUES(?,?,?,?)",
                     (u, name, hash_password("demo123"), role))
    conn.executemany("INSERT INTO disease_classes(code,name,name_en,group_name,cause,description,treatment,"
                     "prevention,is_dangerous,color) VALUES(?,?,?,?,?,?,?,?,?,?)", DISEASES)
    conn.executemany("INSERT INTO settings(key,value) VALUES(?,?)", SETTINGS.items())
    class_ids = [r[0] for r in conn.execute("SELECT id FROM disease_classes ORDER BY id")]

    # Dataset v1 giả lập: 1.064 stem có nhãn chia 70/15/15 theo stem (0 leakage) + 153 stem chưa nhãn.
    # ponytail: dữ liệu demo; thay bằng import từ data/splits/v1/*.csv khi dataset_cleaner.py chạy xong.
    conn.execute("INSERT INTO dataset_versions(name, version, seed, notes) VALUES(?,?,?,?)",
                 ("Pig Skin v1", "v1", 42, "Stem-level stratified split 70/15/15 (demo)"))
    weights = [164, 120, 95, 140, 85, 60, 110, 70, 105, 115]
    for i in range(1064):
        cls = rnd.choices(class_ids, weights)[0]
        split = rnd.choices(["train", "val", "test"], [70, 15, 15])[0]
        cur = conn.execute("INSERT INTO images(stem_id, source) VALUES(?, 'dataset')", (f"stem_{i:04d}",))
        conn.execute("INSERT INTO image_labels(image_id, class_id, status, annotator, verified_by_vet) "
                     "VALUES(?,?, 'VERIFIED', 'roboflow', 0)", (cur.lastrowid, cls))
        conn.execute("INSERT INTO dataset_members VALUES(1,?,?)", (cur.lastrowid, split))
    for i in range(153):
        conn.execute("INSERT INTO images(stem_id, source) VALUES(?, 'unlabeled')", (f"unl_{i:04d}",))

    for i, (name, arch, task, uri, lat, metrics) in enumerate(MODELS):
        conn.execute("INSERT INTO model_versions(name, architecture, task, dataset_version_id, artifact_uri, "
                     "config, metrics, latency_ms, is_default) VALUES(?,?,?,?,?,?,?,?,?)",
                     (name, arch, task, 1, uri, json.dumps({"img_size": 224 if task == "classification" else 640}),
                      json.dumps(metrics), lat, int(name == "EfficientNet-B0")))

    # ~260 ca bệnh trong 8 tuần + ổ dịch LMLM tại Khu B2 tuần này để demo cảnh báo.
    now = datetime.now()
    model_ids = [r[0] for r in conn.execute("SELECT id FROM model_versions")]
    cases = [(rnd.choices(class_ids, [55, 6, 6, 9, 7, 4, 6, 5, 1, 4])[0], rnd.choice(PENS),
              now - timedelta(days=rnd.uniform(0, 56))) for _ in range(260)]
    cases += [(class_ids[8], "Khu B2", now - timedelta(days=rnd.uniform(0, 5))) for _ in range(4)]
    for cls, pen, ts in cases:
        conf = round(rnd.uniform(0.55, 0.99), 3)
        img = conn.execute("INSERT INTO images(source, created_at) VALUES('farm', ?)", (ts.isoformat(" ", "seconds"),))
        others = rnd.sample([c for c in class_ids if c != cls], 2)
        rest = 1 - conf
        top3 = [[cls, conf], [others[0], round(rest * 0.6, 3)], [others[1], round(rest * 0.25, 3)]]
        reviewed = ts < now - timedelta(days=3) and rnd.random() < 0.7
        conn.execute("INSERT INTO predictions(image_id, model_version_id, predicted_class_id, confidence, top3, "
                     "inference_ms, pen, herd_code, created_by, review_status, final_class_id, created_at) "
                     "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                     (img.lastrowid, rnd.choice(model_ids), cls, conf, json.dumps(top3), round(rnd.uniform(6, 19), 1),
                      pen, f"DH-{rnd.randint(1, 12):02d}", 4, "CONFIRMED" if reviewed else "PENDING",
                      cls if reviewed else None, ts.isoformat(" ", "seconds")))
