"""SQLite persistence for diagnostic records and clinician feedback."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parent.parent / "pigskin.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DB_PATH), timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS diagnostic_records (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL DEFAULT '',
                image_path TEXT NOT NULL DEFAULT '',
                ear_tag TEXT NOT NULL DEFAULT '',
                pen_id TEXT NOT NULL DEFAULT '',
                disease_code TEXT NOT NULL DEFAULT '',
                disease_name TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0,
                urgency_level TEXT NOT NULL DEFAULT 'MODERATE',
                urgency_label TEXT NOT NULL DEFAULT '',
                treatment_summary TEXT NOT NULL DEFAULT '',
                abnormal INTEGER NOT NULL DEFAULT 1,
                detections_json TEXT NOT NULL DEFAULT '[]',
                notes TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS doctor_feedbacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT NOT NULL,
                doctor_status TEXT NOT NULL,
                corrected_disease_code TEXT NOT NULL DEFAULT '',
                corrected_disease_name TEXT NOT NULL DEFAULT '',
                doctor_notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (record_id) REFERENCES diagnostic_records(id)
            );
            CREATE INDEX IF NOT EXISTS idx_records_created_at ON diagnostic_records(created_at);
            CREATE INDEX IF NOT EXISTS idx_records_ear_tag ON diagnostic_records(ear_tag);
            CREATE INDEX IF NOT EXISTS idx_records_pen_id ON diagnostic_records(pen_id);
            """
        )
        # Upgrade databases created by the earlier demo without removing records.
        columns = {row[1] for row in connection.execute("PRAGMA table_info(diagnostic_records)")}
        additions = {
            "image_path": "TEXT NOT NULL DEFAULT ''",
            "urgency_label": "TEXT NOT NULL DEFAULT ''",
            "treatment_summary": "TEXT NOT NULL DEFAULT ''",
        }
        for name, declaration in additions.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE diagnostic_records ADD COLUMN {name} {declaration}")


def save_record(record_data: dict):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO diagnostic_records (
                id, filename, image_path, ear_tag, pen_id, disease_code, disease_name,
                confidence, urgency_level, urgency_label, treatment_summary, abnormal,
                detections_json, notes, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_data["id"], record_data.get("filename", ""), record_data.get("image_path", ""),
                record_data.get("ear_tag", ""), record_data.get("pen_id", ""),
                record_data.get("disease_code", ""), record_data.get("disease_name", ""),
                float(record_data.get("confidence", 0)), record_data.get("urgency_level", "MODERATE"),
                record_data.get("urgency_label", ""), record_data.get("treatment_summary", ""),
                1 if record_data.get("abnormal", True) else 0,
                json.dumps(record_data.get("detections", []), ensure_ascii=False),
                record_data.get("notes", ""), record_data.get("source", "FastAPI"),
                record_data.get("created_at") or datetime.now(timezone.utc).isoformat(),
            ),
        )


def _decode_record(row):
    item = dict(row)
    try:
        item["detections"] = json.loads(item.pop("detections_json", "[]") or "[]")
    except (TypeError, json.JSONDecodeError):
        item["detections"] = []
    item["abnormal"] = bool(item["abnormal"])
    return item


def get_records(
    limit: int = 100,
    pen_id: Optional[str] = None,
    disease_code: Optional[str] = None,
    ear_tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    query: Optional[str] = None,
):
    clauses = ["1=1"]
    params = []
    if pen_id:
        clauses.append("pen_id LIKE ?")
        params.append(f"%{pen_id}%")
    if ear_tag:
        clauses.append("ear_tag LIKE ?")
        params.append(f"%{ear_tag}%")
    if disease_code:
        clauses.append("disease_code = ?")
        params.append(disease_code)
    if start_date:
        clauses.append("date(created_at) >= date(?)")
        params.append(start_date)
    if end_date:
        clauses.append("date(created_at) <= date(?)")
        params.append(end_date)
    if query:
        like = f"%{query}%"
        clauses.append("(id LIKE ? OR filename LIKE ? OR disease_name LIKE ? OR pen_id LIKE ? OR ear_tag LIKE ?)")
        params.extend([like] * 5)
    params.append(limit)
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT * FROM diagnostic_records WHERE {' AND '.join(clauses)} ORDER BY datetime(created_at) DESC LIMIT ?",
            params,
        ).fetchall()
        return [_decode_record(row) for row in rows]


def get_record(record_id: str):
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM diagnostic_records WHERE id = ?", (record_id,)).fetchone()
        return _decode_record(row) if row else None


def save_feedback(feedback_data: dict):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO doctor_feedbacks (
                record_id, doctor_status, corrected_disease_code, corrected_disease_name,
                doctor_notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                feedback_data["record_id"], feedback_data["doctor_status"],
                feedback_data.get("corrected_disease_code", ""), feedback_data.get("corrected_disease_name", ""),
                feedback_data.get("doctor_notes", ""), datetime.now(timezone.utc).isoformat(),
            ),
        )


def get_feedback(record_id: str):
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM doctor_feedbacks WHERE record_id = ? ORDER BY id DESC", (record_id,)
        ).fetchall()
        return [dict(row) for row in rows]


init_db()
