"""
config.py — Cấu hình chung cho PigSkinResearchStudio Desktop (Flet + SQLite).

Có thể ghi đè đường dẫn gốc bằng biến môi trường:
    PIGSKIN_ROOT        thư mục gốc dự án (mặc định E:\\code\\PigSkinResearchStudio)
    PIGSKIN_DB          đường dẫn file pig_skin.db
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Đường dẫn
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(os.environ.get("PIGSKIN_ROOT", r"E:\code\PigSkinResearchStudio"))

# Nếu chạy trên máy không có ổ E:\ (ví dụ máy khác/CI) thì DB nằm cạnh app.
_DEFAULT_DB_DIR = PROJECT_ROOT if PROJECT_ROOT.exists() else APP_DIR
DB_PATH = Path(os.environ.get("PIGSKIN_DB", str(_DEFAULT_DB_DIR / "pig_skin.db")))
SETTINGS_PATH = DB_PATH.with_name("pig_skin_app_settings.json")

DATASET_NAME = "pig_skin_single_label_v4"
SPLIT_DIR = PROJECT_ROOT / "data" / "splits" / DATASET_NAME
DEFAULT_MANIFEST = SPLIT_DIR / "manifest.csv"
DEFAULT_CLASSES = SPLIT_DIR / "classes.json"
DEFAULT_RUN_DIR = PROJECT_ROOT / "ml_workspace" / "runs" / "20261028_190505"
# Thư mục gốc để ghép với images.relative_path (đổi được trong màn hình Importer).
DEFAULT_IMAGE_ROOT = PROJECT_ROOT / "data"

# ---------------------------------------------------------------------------
# 2. Số liệu chuẩn của manifest hiện tại (dùng cho checklist bàn giao)
# ---------------------------------------------------------------------------
EXPECTED_NUM_CLASSES = 10
EXPECTED_SPLITS = {"train": 1576, "val": 240, "test": 201}
EXPECTED_TOTAL_IMAGES = 2017
IMAGE_SIZE = 224
SPLITS = ("train", "val", "test")

# ---------------------------------------------------------------------------
# 3. Ngưỡng hiển thị
# ---------------------------------------------------------------------------
WEAK_METRIC_THRESHOLD = 0.55      # F1 hoặc Recall < ngưỡng → tô cảnh báo
CLOSE_SCORE_MARGIN = 0.10         # top1 - top2 < margin → cảnh báo "model phân vân"
IMAGES_PER_PAGE = 48

IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "bmp", "webp"]
VIDEO_EXTENSIONS = ["mp4", "avi", "mov", "mkv"]

# ---------------------------------------------------------------------------
# 4. Bảng màu "Scientific Studio"
# ---------------------------------------------------------------------------
MONO_FONT = "Consolas"

THEME_SEED = "#1F8A8A"  # teal phòng thí nghiệm

DARK_PALETTE = {
    "primary": "#4FD1C5",
    "on_primary": "#00201D",
    "primary_container": "#0E3F3B",
    "on_primary_container": "#B2F5EA",
    "secondary": "#9DB4C0",
    "surface": "#0F1417",
    "on_surface": "#E3E8EB",
    "on_surface_variant": "#9AA7AE",
    "surface_container_highest": "#1B2328",
    "outline": "#3A464D",
    "outline_variant": "#273138",
    "error": "#FF6B6B",
}

LIGHT_PALETTE = {
    "primary": "#13756F",
    "on_primary": "#FFFFFF",
    "primary_container": "#C9F1EC",
    "on_primary_container": "#00332F",
    "secondary": "#4D6470",
    "surface": "#F6F8F8",
    "on_surface": "#141B1F",
    "on_surface_variant": "#53616A",
    "surface_container_highest": "#FFFFFF",
    "outline": "#C2CCD1",
    "outline_variant": "#DDE4E7",
    "error": "#C62828",
}

# Màu cho 3 tập train / val / test (đủ tương phản trên cả 2 nền)
SPLIT_COLORS = {"train": "#3B82C4", "val": "#E0A030", "test": "#2BA88F"}

# Trạng thái → (nhãn tiếng Việt, màu)
STATUS_STYLES = {
    # image_labels.review_status
    "pending": ("Chờ duyệt", "#8A94A0"),
    "approved": ("Đã duyệt", "#2E9E6A"),
    "rejected": ("Loại bỏ", "#D9534F"),
    "needs_review": ("Cần xem lại", "#E0A030"),
    # predictions.review_status
    "unreviewed": ("Chưa xác nhận", "#8A94A0"),
    "confirmed": ("Đúng", "#2E9E6A"),
    "incorrect": ("Sai", "#D9534F"),
    "uncertain": ("Không chắc", "#E0A030"),
    # training_runs.status
    "running": ("Đang chạy", "#3B82C4"),
    "completed": ("Hoàn tất", "#2E9E6A"),
    "failed": ("Lỗi", "#D9534F"),
    "cancelled": ("Đã hủy", "#8A94A0"),
    # checklist
    "pass": ("Đạt", "#2E9E6A"),
    "warn": ("Lưu ý", "#E0A030"),
    "fail": ("Chưa đạt", "#D9534F"),
    # nguồn dữ liệu
    "mock": ("Dữ liệu mẫu", "#8B5CF6"),
    "demo": ("Chế độ demo", "#8B5CF6"),
}

WARN_BG = "#E0A030"     # dùng with_opacity khi tô nền
DANGER_BG = "#D9534F"


# ---------------------------------------------------------------------------
# 5. Settings nhỏ lưu ngoài CSDL (thư mục ảnh gốc, theme…)
# ---------------------------------------------------------------------------
def load_settings() -> dict:
    defaults = {
        "image_root": str(DEFAULT_IMAGE_ROOT),
        "theme_mode": "dark",
        "reviewer": "",
    }
    try:
        if SETTINGS_PATH.exists():
            defaults.update(json.loads(SETTINGS_PATH.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        pass
    return defaults


def save_settings(**kwargs) -> None:
    data = load_settings()
    data.update(kwargs)
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
