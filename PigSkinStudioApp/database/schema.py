"""
database/schema.py — Schema SQLite đúng theo tài liệu THIET_KE_CSDL_CHO_MODEL_PIG_SKIN.md
(10 bảng + 3 index). Dùng IF NOT EXISTS để chạy lại an toàn.
"""
from __future__ import annotations

import sqlite3

TABLES = (
    "disease_classes",
    "images",
    "image_labels",
    "dataset_versions",
    "dataset_items",
    "dataset_item_labels",
    "training_runs",
    "run_class_metrics",
    "predictions",
    "prediction_scores",
)

INDEXES = (
    "idx_dataset_items_split",
    "idx_predictions_run",
    "idx_run_metrics_class",
)

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS disease_classes (
    class_id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name_vi TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS images (
    image_id INTEGER PRIMARY KEY,
    relative_path TEXT NOT NULL UNIQUE,
    sha256 TEXT UNIQUE,
    width INTEGER,
    height INTEGER,
    source TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS image_labels (
    image_label_id INTEGER PRIMARY KEY,
    image_id INTEGER NOT NULL REFERENCES images(image_id),
    class_id INTEGER NOT NULL REFERENCES disease_classes(class_id),
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'approved', 'rejected', 'needs_review')),
    annotator TEXT,
    reviewed_at TEXT,
    UNIQUE (image_id, class_id)
);

CREATE TABLE IF NOT EXISTS dataset_versions (
    dataset_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    manifest_path TEXT NOT NULL,
    manifest_sha256 TEXT,
    seed INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    UNIQUE (name, version)
);

CREATE TABLE IF NOT EXISTS dataset_items (
    dataset_item_id INTEGER PRIMARY KEY,
    dataset_id INTEGER NOT NULL REFERENCES dataset_versions(dataset_id),
    image_id INTEGER NOT NULL REFERENCES images(image_id),
    split TEXT NOT NULL CHECK (split IN ('train', 'val', 'test')),
    group_id TEXT,
    UNIQUE (dataset_id, image_id)
);

CREATE TABLE IF NOT EXISTS dataset_item_labels (
    dataset_item_id INTEGER NOT NULL REFERENCES dataset_items(dataset_item_id),
    class_id INTEGER NOT NULL REFERENCES disease_classes(class_id),
    PRIMARY KEY (dataset_item_id, class_id)
);

CREATE TABLE IF NOT EXISTS training_runs (
    run_id INTEGER PRIMARY KEY,
    dataset_id INTEGER NOT NULL REFERENCES dataset_versions(dataset_id),
    run_name TEXT NOT NULL UNIQUE,
    model_code TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    config_json TEXT NOT NULL,
    checkpoint_path TEXT,
    best_epoch INTEGER,
    best_val_macro_f1 REAL,
    test_accuracy REAL,
    test_macro_f1 REAL,
    started_at TEXT,
    finished_at TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS run_class_metrics (
    run_id INTEGER NOT NULL REFERENCES training_runs(run_id),
    split TEXT NOT NULL CHECK (split IN ('val', 'test')),
    class_id INTEGER NOT NULL REFERENCES disease_classes(class_id),
    precision REAL,
    recall REAL,
    f1 REAL,
    support INTEGER,
    PRIMARY KEY (run_id, split, class_id)
);

CREATE TABLE IF NOT EXISTS predictions (
    prediction_id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES training_runs(run_id),
    image_id INTEGER REFERENCES images(image_id),
    input_uri TEXT,
    input_kind TEXT NOT NULL DEFAULT 'image'
        CHECK (input_kind IN ('image', 'video_frame')),
    frame_time_seconds REAL,
    predicted_class_id INTEGER REFERENCES disease_classes(class_id),
    top_score REAL,
    actual_class_id INTEGER REFERENCES disease_classes(class_id),
    review_status TEXT NOT NULL DEFAULT 'unreviewed'
        CHECK (review_status IN ('unreviewed', 'confirmed', 'incorrect', 'uncertain')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prediction_scores (
    prediction_id INTEGER NOT NULL REFERENCES predictions(prediction_id),
    class_id INTEGER NOT NULL REFERENCES disease_classes(class_id),
    score REAL NOT NULL CHECK (score >= 0 AND score <= 1),
    PRIMARY KEY (prediction_id, class_id)
);

CREATE INDEX IF NOT EXISTS idx_dataset_items_split ON dataset_items(dataset_id, split);
CREATE INDEX IF NOT EXISTS idx_predictions_run ON predictions(run_id, created_at);
CREATE INDEX IF NOT EXISTS idx_run_metrics_class ON run_class_metrics(class_id, split);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Tạo toàn bộ bảng + index (idempotent)."""
    conn.executescript(SCHEMA_SQL)


def verify_schema(conn: sqlite3.Connection) -> list[str]:
    """Trả về danh sách bảng/index còn thiếu (rỗng = đầy đủ)."""
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'index')").fetchall()
    existing = {r[0] for r in rows}
    return [n for n in (*TABLES, *INDEXES) if n not in existing]
