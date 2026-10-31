"""
database/db_manager.py — Lớp truy cập SQLite an toàn cho PigSkinResearchStudio.

Nguyên tắc:
- Mỗi thao tác mở một kết nối riêng (an toàn khi gọi từ nhiều thread của Flet),
  luôn bật PRAGMA foreign_keys = ON, commit khi thành công, rollback khi lỗi, đóng kết nối.
- Chỉ dùng tham số "?" — không ghép chuỗi giá trị vào SQL.
- Nhãn con người (image_labels / predictions.actual_class_id) tách khỏi dự đoán của model.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

import config
from database.schema import init_schema, verify_schema

IMAGE_REVIEW_STATUSES = ("pending", "approved", "rejected", "needs_review")
PREDICTION_REVIEW_STATUSES = ("unreviewed", "confirmed", "incorrect", "uncertain")
RUN_SORTABLE_COLUMNS = ("best_val_macro_f1", "test_macro_f1", "test_accuracy", "started_at", "run_name", "best_epoch")


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class DBManager:
    def __init__(self, db_path: str | Path = config.DB_PATH):
        self.db_path = Path(db_path)
        self._write_lock = threading.Lock()   # tuần tự hóa các lệnh ghi từ nhiều thread

    # ------------------------------------------------------------------
    # Kết nối
    # ------------------------------------------------------------------
    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Kết nối ghi có khóa — dùng cho importer/seeder/cập nhật nhãn."""
        with self._write_lock:
            with self.connect() as conn:
                yield conn

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
            return dict(row) if row else None

    def scalar(self, sql: str, params: Iterable[Any] = (), default: Any = None) -> Any:
        with self.connect() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
            return row[0] if row and row[0] is not None else default

    # ------------------------------------------------------------------
    # Khởi tạo
    # ------------------------------------------------------------------
    def initialize(self) -> list[str]:
        with self.transaction() as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            init_schema(conn)
            return verify_schema(conn)

    def is_empty(self) -> bool:
        return self.scalar("SELECT COUNT(*) FROM disease_classes", default=0) == 0

    def is_mock(self) -> bool:
        return self.scalar(
            "SELECT COUNT(*) FROM dataset_versions WHERE notes LIKE '%\"mock\": true%'", default=0
        ) > 0

    def reset_all_data(self, conn: sqlite3.Connection | None = None) -> None:
        """Xóa toàn bộ dữ liệu (giữ schema). Thứ tự xóa tôn trọng khóa ngoại."""
        order = (
            "prediction_scores", "predictions", "run_class_metrics", "training_runs",
            "dataset_item_labels", "dataset_items", "dataset_versions",
            "image_labels", "images", "disease_classes",
        )
        if conn is not None:
            for t in order:
                conn.execute(f"DELETE FROM {t}")
            return
        with self.transaction() as c:
            for t in order:
                c.execute(f"DELETE FROM {t}")

    # ------------------------------------------------------------------
    # Danh mục lớp
    # ------------------------------------------------------------------
    def get_classes(self) -> list[dict]:
        return self.query("SELECT class_id, code, name_vi, description FROM disease_classes ORDER BY class_id")

    def class_label(self, row: dict | None) -> str:
        if not row:
            return "—"
        return f"{row['name_vi']} ({row['code']})" if row.get("name_vi") != row.get("code") else row["code"]

    # ------------------------------------------------------------------
    # Dataset versions
    # ------------------------------------------------------------------
    def get_dataset_versions(self) -> list[dict]:
        return self.query(
            """
            SELECT d.*,
                   (SELECT COUNT(*) FROM dataset_items di WHERE di.dataset_id = d.dataset_id) AS n_items,
                   (SELECT COUNT(*) FROM training_runs r WHERE r.dataset_id = d.dataset_id) AS n_runs
            FROM dataset_versions d ORDER BY d.created_at DESC, d.dataset_id DESC
            """
        )

    def get_latest_dataset_id(self) -> int | None:
        return self.scalar("SELECT dataset_id FROM dataset_versions ORDER BY created_at DESC, dataset_id DESC LIMIT 1")

    def split_counts(self, dataset_id: int) -> dict[str, int]:
        rows = self.query(
            "SELECT split, COUNT(*) AS n FROM dataset_items WHERE dataset_id = ? GROUP BY split", (dataset_id,)
        )
        out = {s: 0 for s in config.SPLITS}
        out.update({r["split"]: r["n"] for r in rows})
        return out

    def class_split_distribution(self, dataset_id: int) -> list[dict]:
        """Mỗi lớp: số ảnh train/val/test theo bản chụp nhãn dataset_item_labels."""
        rows = self.query(
            """
            SELECT c.class_id, c.code, c.name_vi, di.split, COUNT(*) AS n
            FROM dataset_item_labels dil
            JOIN dataset_items di ON di.dataset_item_id = dil.dataset_item_id
            JOIN disease_classes c ON c.class_id = dil.class_id
            WHERE di.dataset_id = ?
            GROUP BY c.class_id, di.split
            """,
            (dataset_id,),
        )
        by_class: dict[int, dict] = {}
        for c in self.get_classes():
            by_class[c["class_id"]] = {**c, "train": 0, "val": 0, "test": 0}
        for r in rows:
            by_class[r["class_id"]][r["split"]] = r["n"]
        return list(by_class.values())

    @staticmethod
    def parse_notes(notes: str | None) -> dict:
        if not notes:
            return {}
        try:
            data = json.loads(notes)
            return data if isinstance(data, dict) else {"text": notes}
        except json.JSONDecodeError:
            return {"text": notes}

    # ------------------------------------------------------------------
    # Tổng quan + checklist bàn giao
    # ------------------------------------------------------------------
    def get_best_run(self, dataset_id: int | None = None) -> dict | None:
        sql = "SELECT * FROM training_runs WHERE status = 'completed'"
        params: tuple = ()
        if dataset_id is not None:
            sql += " AND dataset_id = ?"
            params = (dataset_id,)
        sql += " ORDER BY best_val_macro_f1 DESC NULLS LAST, test_macro_f1 DESC LIMIT 1"
        return self.query_one(sql, params)

    def get_overview(self, dataset_id: int | None = None) -> dict:
        dataset_id = dataset_id or self.get_latest_dataset_id()
        ds = self.query_one("SELECT * FROM dataset_versions WHERE dataset_id = ?", (dataset_id,)) if dataset_id else None
        splits = self.split_counts(dataset_id) if dataset_id else {s: 0 for s in config.SPLITS}
        label_status = {r["review_status"]: r["n"] for r in self.query(
            "SELECT review_status, COUNT(*) AS n FROM image_labels GROUP BY review_status")}
        return {
            "dataset": ds,
            "dataset_id": dataset_id,
            "splits": splits,
            "total_items": sum(splits.values()),
            "total_images": self.scalar("SELECT COUNT(*) FROM images", default=0),
            "num_classes": self.scalar("SELECT COUNT(*) FROM disease_classes", default=0),
            "best_run": self.get_best_run(dataset_id),
            "num_runs": self.scalar("SELECT COUNT(*) FROM training_runs", default=0),
            "num_predictions": self.scalar("SELECT COUNT(*) FROM predictions", default=0),
            "label_status": label_status,
            "is_mock": self.is_mock(),
        }

    def run_integrity_checks(self, dataset_id: int | None = None, image_root: str | None = None) -> list[dict]:
        """Checklist mục 9 của tài liệu thiết kế. status ∈ pass / warn / fail."""
        checks: list[dict] = []

        def add(title: str, status: str, detail: str) -> None:
            checks.append({"title": title, "status": status, "detail": detail})

        dataset_id = dataset_id or self.get_latest_dataset_id()
        ds = self.query_one("SELECT * FROM dataset_versions WHERE dataset_id = ?", (dataset_id,)) if dataset_id else None
        notes = self.parse_notes(ds["notes"]) if ds else {}
        expected_splits = notes.get("manifest_counts") or config.EXPECTED_SPLITS
        expected_total = sum(expected_splits.values())

        # 1. Đủ 10 lớp, mã duy nhất
        n_cls = self.scalar("SELECT COUNT(*) FROM disease_classes", default=0)
        n_codes = self.scalar("SELECT COUNT(DISTINCT code) FROM disease_classes", default=0)
        add("Đủ 10 mã lớp, mỗi mã duy nhất",
            "pass" if n_cls == config.EXPECTED_NUM_CLASSES and n_codes == n_cls else "fail",
            f"{n_cls} lớp, {n_codes} mã khác nhau (chuẩn: {config.EXPECTED_NUM_CLASSES}).")

        # 2. Không trùng SHA-256
        n_img = self.scalar("SELECT COUNT(*) FROM images", default=0)
        n_null = self.scalar("SELECT COUNT(*) FROM images WHERE sha256 IS NULL", default=0)
        n_dup = self.scalar(
            "SELECT COUNT(*) FROM (SELECT sha256 FROM images WHERE sha256 IS NOT NULL GROUP BY sha256 HAVING COUNT(*) > 1)",
            default=0)
        if n_dup:
            add("Không trùng SHA-256", "fail", f"{n_dup} giá trị SHA-256 bị lặp.")
        elif n_null:
            add("Không trùng SHA-256", "warn",
                f"Không có trùng lặp, nhưng {n_null}/{n_img} ảnh chưa có SHA-256 (chưa băm hoặc trùng nội dung đã bị bỏ qua).")
        else:
            add("Không trùng SHA-256", "pass", f"{n_img} ảnh, tất cả có SHA-256 duy nhất.")

        # 3. Đường dẫn ảnh tồn tại
        if image_root and Path(image_root).exists() and n_img:
            paths = [r["relative_path"] for r in self.query("SELECT relative_path FROM images")]
            missing = sum(1 for p in paths if not (Path(image_root) / p).exists())
            add("Đường dẫn ảnh tồn tại", "pass" if missing == 0 else ("warn" if missing < len(paths) else "fail"),
                f"{len(paths) - missing}/{len(paths)} ảnh tìm thấy dưới {image_root}.")
        else:
            add("Đường dẫn ảnh tồn tại", "warn", f"Chưa kiểm tra được: thư mục ảnh gốc không tồn tại ({image_root}).")

        if not dataset_id:
            add("Có phiên bản dataset", "fail", "Chưa có dòng nào trong dataset_versions.")
            return checks

        # 4. Mỗi ảnh chỉ thuộc 1 split trong 1 phiên bản
        n_multi = self.scalar(
            "SELECT COUNT(*) FROM (SELECT image_id FROM dataset_items WHERE dataset_id = ? GROUP BY image_id HAVING COUNT(DISTINCT split) > 1)",
            (dataset_id,), default=0)
        add("Mỗi ảnh chỉ thuộc một split", "pass" if n_multi == 0 else "fail",
            "Không có ảnh nằm ở nhiều split." if n_multi == 0 else f"{n_multi} ảnh nằm ở nhiều split.")

        # 5. Khớp số lượng split
        actual = self.split_counts(dataset_id)
        ok = all(actual.get(s, 0) == expected_splits.get(s, 0) for s in config.SPLITS)
        add("Số ảnh train/val/test khớp manifest", "pass" if ok else "fail",
            " · ".join(f"{s}: {actual.get(s, 0):,}/{expected_splits.get(s, 0):,}" for s in config.SPLITS).replace(",", "."))

        # 6. Tổng ảnh
        total = sum(actual.values())
        add(f"Tổng số ảnh bằng {expected_total:,}".replace(",", "."), "pass" if total == expected_total else "fail",
            f"Thực tế {total:,} ảnh trong phiên bản {ds['name']} / {ds['version']}.".replace(",", "."))

        # 7. Mỗi item đúng 1 nhãn (bài toán đơn nhãn)
        n_bad = self.scalar(
            """SELECT COUNT(*) FROM dataset_items di
               WHERE di.dataset_id = ? AND (SELECT COUNT(*) FROM dataset_item_labels l
                                            WHERE l.dataset_item_id = di.dataset_item_id) <> 1""",
            (dataset_id,), default=0)
        add("Mỗi ảnh có đúng một nhãn snapshot", "pass" if n_bad == 0 else "fail",
            "Đơn nhãn hợp lệ." if n_bad == 0 else f"{n_bad} item có 0 hoặc >1 nhãn.")

        # 8. Run đủ thông tin
        runs = self.query("SELECT * FROM training_runs WHERE dataset_id = ?", (dataset_id,))
        if not runs:
            add("Run có hash, cấu hình, checkpoint, metric", "warn", "Chưa có training run cho phiên bản này.")
        else:
            missing_info = []
            for r in runs:
                lack = [k for k in ("config_json", "checkpoint_path", "best_epoch", "test_macro_f1", "test_accuracy")
                        if r.get(k) in (None, "", "{}")]
                if not ds.get("manifest_sha256"):
                    lack.append("manifest_sha256")
                if lack:
                    missing_info.append(f"{r['run_name']}: thiếu {', '.join(lack)}")
            add("Run có hash, cấu hình, checkpoint, metric", "pass" if not missing_info else "warn",
                f"{len(runs)} run đầy đủ." if not missing_info else "; ".join(missing_info))

        # 9. Tách nhãn thật và dự đoán
        n_leak = self.scalar(
            "SELECT COUNT(*) FROM predictions WHERE actual_class_id IS NOT NULL AND review_status = 'unreviewed'", default=0)
        n_conf_bad = self.scalar(
            """SELECT COUNT(*) FROM predictions WHERE
               (review_status = 'confirmed' AND (actual_class_id IS NULL OR actual_class_id <> predicted_class_id))
               OR (review_status = 'incorrect' AND (actual_class_id IS NULL OR actual_class_id = predicted_class_id))""",
            default=0)
        n_appr_anon = self.scalar(
            "SELECT COUNT(*) FROM image_labels WHERE review_status = 'approved' AND (annotator IS NULL OR reviewed_at IS NULL)",
            default=0)
        problems = []
        if n_leak:
            problems.append(f"{n_leak} dự đoán có actual_class_id nhưng chưa được xác nhận")
        if n_conf_bad:
            problems.append(f"{n_conf_bad} dự đoán có trạng thái không khớp actual_class_id")
        if n_appr_anon:
            problems.append(f"{n_appr_anon} nhãn 'approved' thiếu người duyệt/thời điểm duyệt")
        add("Nhãn thật tách biệt với dự đoán", "pass" if not problems else "fail",
            "actual_class_id chỉ có khi đã được người duyệt xác nhận." if not problems else "; ".join(problems))
        return checks

    # ------------------------------------------------------------------
    # Kho ảnh & duyệt nhãn
    # ------------------------------------------------------------------
    def get_image_sources(self) -> list[str]:
        return [r["source"] for r in self.query("SELECT DISTINCT source FROM images WHERE source IS NOT NULL ORDER BY source")]

    def list_images(self, *, dataset_id: int | None = None, class_id: int | None = None, source: str | None = None,
                    review_status: str | None = None, split: str | None = None, search: str | None = None,
                    limit: int = 48, offset: int = 0) -> tuple[list[dict], int]:
        where, params = ["1 = 1"], []
        if class_id is not None:
            where.append("il.class_id = ?"); params.append(class_id)
        if source:
            where.append("i.source = ?"); params.append(source)
        if review_status:
            where.append("il.review_status = ?"); params.append(review_status)
        if split:
            where.append("di.split = ?"); params.append(split)
        if search:
            where.append("i.relative_path LIKE ?"); params.append(f"%{search}%")
        di_join = "LEFT JOIN dataset_items di ON di.image_id = i.image_id" + (" AND di.dataset_id = ?" if dataset_id else "")
        join_params = [dataset_id] if dataset_id else []
        base = f"""
            FROM images i
            LEFT JOIN image_labels il ON il.image_id = i.image_id
            LEFT JOIN disease_classes c ON c.class_id = il.class_id
            {di_join}
            WHERE {' AND '.join(where)}
        """
        total = self.scalar(f"SELECT COUNT(*) {base}", join_params + params, default=0)
        rows = self.query(
            f"""SELECT i.*, il.image_label_id, il.class_id, il.review_status, il.annotator, il.reviewed_at,
                       c.code AS class_code, c.name_vi AS class_name, di.split, di.group_id
                {base} ORDER BY i.image_id LIMIT ? OFFSET ?""",
            join_params + params + [limit, offset],
        )
        return rows, total

    def update_image_label_status(self, image_label_id: int, status: str, annotator: str | None) -> None:
        if status not in IMAGE_REVIEW_STATUSES:
            raise ValueError(f"review_status không hợp lệ: {status}")
        annotator = (annotator or "").strip() or None
        if status in ("approved", "rejected") and not annotator:
            raise ValueError("Cần nhập tên người duyệt trước khi duyệt hoặc loại bỏ nhãn.")
        reviewed_at = None if status == "pending" else now_iso()
        with self.transaction() as conn:
            conn.execute(
                "UPDATE image_labels SET review_status = ?, annotator = ?, reviewed_at = ? WHERE image_label_id = ?",
                (status, annotator, reviewed_at, image_label_id),
            )

    def find_image_by_relative_path(self, relative_path: str) -> dict | None:
        return self.query_one("SELECT * FROM images WHERE relative_path = ?", (relative_path.replace("\\", "/"),))

    # ------------------------------------------------------------------
    # Training runs
    # ------------------------------------------------------------------
    def list_runs(self, order_by: str = "best_val_macro_f1", descending: bool = True,
                  status: str | None = None) -> list[dict]:
        if order_by not in RUN_SORTABLE_COLUMNS:
            order_by = "best_val_macro_f1"
        direction = "DESC" if descending else "ASC"
        sql = """SELECT r.*, d.name AS dataset_name, d.version AS dataset_version
                 FROM training_runs r JOIN dataset_versions d ON d.dataset_id = r.dataset_id"""
        params: list = []
        if status:
            sql += " WHERE r.status = ?"; params.append(status)
        sql += f" ORDER BY r.{order_by} {direction} NULLS LAST, r.run_id DESC"
        return self.query(sql, params)

    def get_run(self, run_id: int) -> dict | None:
        return self.query_one("SELECT * FROM training_runs WHERE run_id = ?", (run_id,))

    def get_run_metrics(self, run_id: int, split: str) -> list[dict]:
        return self.query(
            """SELECT c.class_id, c.code, c.name_vi, m.precision, m.recall, m.f1, m.support
               FROM disease_classes c
               LEFT JOIN run_class_metrics m ON m.class_id = c.class_id AND m.run_id = ? AND m.split = ?
               ORDER BY c.class_id""",
            (run_id, split),
        )

    # ------------------------------------------------------------------
    # Predictions
    # ------------------------------------------------------------------
    def create_prediction(self, *, run_id: int, scores: dict[int, float], input_uri: str | None,
                          input_kind: str = "image", frame_time_seconds: float | None = None,
                          image_id: int | None = None) -> int:
        if not scores:
            raise ValueError("Không có điểm số để lưu.")
        clean = {int(k): min(1.0, max(0.0, float(v))) for k, v in scores.items()}
        top_cls = max(clean, key=clean.get)
        with self.transaction() as conn:
            cur = conn.execute(
                """INSERT INTO predictions (run_id, image_id, input_uri, input_kind, frame_time_seconds,
                                            predicted_class_id, top_score, actual_class_id, review_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 'unreviewed')""",
                (run_id, image_id, input_uri, input_kind,
                 frame_time_seconds if input_kind == "video_frame" else None, top_cls, clean[top_cls]),
            )
            pid = cur.lastrowid
            conn.executemany(
                "INSERT INTO prediction_scores (prediction_id, class_id, score) VALUES (?, ?, ?)",
                [(pid, cid, s) for cid, s in clean.items()],
            )
        return pid

    def update_prediction_review(self, prediction_id: int, review_status: str, actual_class_id: int | None) -> None:
        """Ghi xác nhận của chuyên gia. KHÔNG bao giờ tự lấy predicted_class_id làm actual_class_id."""
        if review_status not in PREDICTION_REVIEW_STATUSES:
            raise ValueError(f"review_status không hợp lệ: {review_status}")
        pred = self.query_one("SELECT predicted_class_id FROM predictions WHERE prediction_id = ?", (prediction_id,))
        if not pred:
            raise ValueError("Không tìm thấy dự đoán.")
        predicted = pred["predicted_class_id"]
        if review_status == "unreviewed" and actual_class_id is not None:
            raise ValueError("Trạng thái 'Chưa xác nhận' không được kèm nhãn thật.")
        if review_status == "confirmed":
            if actual_class_id is None:
                raise ValueError("Hãy tự chọn nhãn thật (actual_class_id) trước khi xác nhận 'Đúng'.")
            if actual_class_id != predicted:
                raise ValueError("Nhãn thật khác lớp model dự đoán — hãy chọn trạng thái 'Sai'.")
        if review_status == "incorrect":
            if actual_class_id is None:
                raise ValueError("Trạng thái 'Sai' cần chọn nhãn thật đúng.")
            if actual_class_id == predicted:
                raise ValueError("Nhãn thật trùng lớp dự đoán — hãy chọn trạng thái 'Đúng'.")
        with self.transaction() as conn:
            conn.execute(
                "UPDATE predictions SET review_status = ?, actual_class_id = ? WHERE prediction_id = ?",
                (review_status, actual_class_id, prediction_id),
            )

    def list_predictions(self, run_id: int | None = None, limit: int = 30) -> list[dict]:
        sql = """SELECT p.*, r.run_name, pc.code AS predicted_code, pc.name_vi AS predicted_name,
                        ac.code AS actual_code, ac.name_vi AS actual_name
                 FROM predictions p
                 JOIN training_runs r ON r.run_id = p.run_id
                 LEFT JOIN disease_classes pc ON pc.class_id = p.predicted_class_id
                 LEFT JOIN disease_classes ac ON ac.class_id = p.actual_class_id"""
        params: list = []
        if run_id:
            sql += " WHERE p.run_id = ?"; params.append(run_id)
        sql += " ORDER BY p.prediction_id DESC LIMIT ?"
        params.append(limit)
        return self.query(sql, params)

    def get_prediction(self, prediction_id: int) -> dict | None:
        return self.query_one("SELECT * FROM predictions WHERE prediction_id = ?", (prediction_id,))

    def get_prediction_scores(self, prediction_id: int) -> list[dict]:
        return self.query(
            """SELECT c.class_id, c.code, c.name_vi, s.score FROM prediction_scores s
               JOIN disease_classes c ON c.class_id = s.class_id
               WHERE s.prediction_id = ? ORDER BY s.score DESC""",
            (prediction_id,),
        )

    # ------------------------------------------------------------------
    # Mock Seeder
    # ------------------------------------------------------------------
    def seed_mock_data(self, progress_cb=None) -> dict:
        """Tạo dữ liệu mẫu bám sát số liệu thực tế. Chỉ dùng để demo giao diện.

        Tên lớp ở đây là GIẢ ĐỊNH — khi chạy Importer với classes.json thật,
        hãy tick "Xóa dữ liệu hiện có" để thay toàn bộ dữ liệu mẫu.
        """
        rnd = random.Random(20261028)
        report = {"classes": 0, "images": 0, "runs": 0}
        with self.transaction() as conn:
            if conn.execute("SELECT COUNT(*) FROM disease_classes").fetchone()[0]:
                return {"skipped": True}

            # Bước 1: lớp bệnh
            conn.executemany(
                "INSERT INTO disease_classes (class_id, code, name_vi, description) VALUES (?, ?, ?, ?)",
                [(i + 1, code, name, f"[MOCK] {desc}") for i, (code, name, desc) in enumerate(MOCK_CLASSES)],
            )
            report["classes"] = len(MOCK_CLASSES)

            # Bước 2: dataset version
            notes = {"mock": True, "label_source": "mock_seed",
                     "manifest_counts": dict(config.EXPECTED_SPLITS),
                     "text": "Dữ liệu mẫu do seeder tạo — thay bằng Importer khi có file thật."}
            manifest_path = str(config.DEFAULT_MANIFEST)
            cur = conn.execute(
                """INSERT INTO dataset_versions (name, version, manifest_path, manifest_sha256, seed, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (config.DATASET_NAME, "v4", manifest_path,
                 hashlib.sha256(b"mock-manifest-v4").hexdigest(), 42, json.dumps(notes, ensure_ascii=False)),
            )
            dataset_id = cur.lastrowid

            # Bước 3: ảnh + split (đúng 1.576 / 240 / 201)
            weights = [0.16, 0.13, 0.11, 0.12, 0.10, 0.09, 0.08, 0.08, 0.07, 0.06]
            per_split = {s: _largest_remainder(weights, n) for s, n in config.EXPECTED_SPLITS.items()}
            counter = 0
            total = config.EXPECTED_TOTAL_IMAGES
            support = {"val": {}, "test": {}}
            for split in config.SPLITS:
                for ci, n in enumerate(per_split[split]):
                    code = MOCK_CLASSES[ci][0]
                    class_id = ci + 1
                    if split in support:
                        support[split][class_id] = n
                    for k in range(n):
                        counter += 1
                        rel = f"raw/{code}/{split}_{code}_{k + 1:04d}.jpg"
                        source = rnd.choice(["farm_A_camera", "farm_B_phone", "public_dataset"])
                        w, h = rnd.choice([(640, 480), (1024, 768), (1280, 960), (800, 800)])
                        cur = conn.execute(
                            "INSERT INTO images (relative_path, sha256, width, height, source) VALUES (?, ?, ?, ?, ?)",
                            (rel, hashlib.sha256(f"mock:{rel}".encode()).hexdigest(), w, h, source),
                        )
                        image_id = cur.lastrowid
                        # Nhãn nguồn: luôn 'pending' (vài ảnh 'needs_review'), KHÔNG 'approved'
                        status = "needs_review" if rnd.random() < 0.04 else "pending"
                        conn.execute(
                            "INSERT INTO image_labels (image_id, class_id, review_status) VALUES (?, ?, ?)",
                            (image_id, class_id, status),
                        )
                        cur = conn.execute(
                            "INSERT INTO dataset_items (dataset_id, image_id, split, group_id) VALUES (?, ?, ?, ?)",
                            (dataset_id, image_id, split, f"grp_{code}_{k // 4:03d}"),
                        )
                        conn.execute(
                            "INSERT INTO dataset_item_labels (dataset_item_id, class_id) VALUES (?, ?)",
                            (cur.lastrowid, class_id),
                        )
                        if progress_cb and counter % 100 == 0:
                            progress_cb(counter / total, f"Tạo ảnh mẫu {counter}/{total}")
            report["images"] = counter

            # Bước 4: training run
            run_cfg = {
                "_mock": True,
                "architecture": "mobilenet_v2",
                "pretrained": "imagenet",
                "label_mode": "single_label",
                "classes": [c[0] for c in MOCK_CLASSES],
                "image_size": config.IMAGE_SIZE,
                "normalization": {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]},
                "augmentation": ["random_resized_crop", "horizontal_flip", "color_jitter(0.2)"],
                "epochs": 20, "head_epochs": 3, "batch_size": 32,
                "learning_rate": {"head": 1e-3, "backbone": 1e-4}, "weight_decay": 1e-4, "seed": 42,
                "device": "cuda", "torch_version": "unknown (mock)", "torchvision_version": "unknown (mock)",
                "manifest_path": manifest_path, "manifest_sha256": hashlib.sha256(b"mock-manifest-v4").hexdigest(),
                "split_counts": dict(config.EXPECTED_SPLITS),
            }
            run_dir = config.DEFAULT_RUN_DIR
            cur = conn.execute(
                """INSERT INTO training_runs (dataset_id, run_name, model_code, status, config_json, checkpoint_path,
                       best_epoch, best_val_macro_f1, test_accuracy, test_macro_f1, started_at, finished_at, notes)
                   VALUES (?, ?, ?, 'completed', ?, ?, 12, 0.7100, 0.6219, 0.6125, ?, ?, ?)""",
                (dataset_id, "20261028_190505", "mobilenet_v2", json.dumps(run_cfg, ensure_ascii=False, indent=2),
                 str(run_dir / "best_model.pt"), "2026-10-28 19:05:05", "2026-10-28 20:41:37",
                 "[MOCK] Chỉ số tổng lấy từ run thật; chỉ số từng lớp là giả lập."),
            )
            run_id = cur.lastrowid
            report["runs"] = 1

            # Bước 5: chỉ số từng lớp (giả lập, trung bình khớp macro-F1 thật)
            val_f1 = _f1_profile(0.7100, [0.84, 0.78, 0.81, 0.70, 0.62, 0.74, 0.52, 0.66, 0.79, 0.64])
            test_f1 = _f1_profile(0.6125, [0.76, 0.69, 0.72, 0.60, 0.49, 0.66, 0.41, 0.58, 0.71, 0.5])
            for split, f1s in (("val", val_f1), ("test", test_f1)):
                for ci, f1 in enumerate(f1s):
                    p, r = _split_f1(f1, rnd)
                    conn.execute(
                        """INSERT INTO run_class_metrics (run_id, split, class_id, precision, recall, f1, support)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (run_id, split, ci + 1, round(p, 4), round(r, 4), round(f1, 4), support[split][ci + 1]),
                    )
        if progress_cb:
            progress_cb(1.0, "Hoàn tất dữ liệu mẫu")
        return report


# ----------------------------------------------------------------------
# Dữ liệu mẫu (GIẢ ĐỊNH — danh mục thật phải lấy từ classes.json)
# ----------------------------------------------------------------------
MOCK_CLASSES = [
    ("healthy", "Da khỏe mạnh", "Không có tổn thương"),
    ("exudative_epidermitis", "Viêm da tiết dịch", "Greasy pig disease"),
    ("swine_pox", "Đậu heo", "Swinepox"),
    ("sarcoptic_mange", "Ghẻ Sarcoptes", "Sarcoptic mange"),
    ("ringworm", "Nấm da", "Dermatophytosis"),
    ("erysipelas", "Đóng dấu son", "Swine erysipelas"),
    ("pdns", "Viêm da – thận (PDNS)", "Porcine dermatitis and nephropathy syndrome"),
    ("pityriasis_rosea", "Vảy phấn hồng", "Pityriasis rosea"),
    ("sunburn", "Cháy nắng", "Sunburn"),
    ("bite_wound", "Vết cắn / trầy xước", "Bite or abrasion wound"),
]


def _largest_remainder(weights: list[float], total: int) -> list[int]:
    raw = [w / sum(weights) * total for w in weights]
    base = [math.floor(x) for x in raw]
    rest = total - sum(base)
    for i in sorted(range(len(raw)), key=lambda i: raw[i] - base[i], reverse=True)[:rest]:
        base[i] += 1
    return base


def _f1_profile(target_mean: float, shape: list[float]) -> list[float]:
    shift = target_mean - sum(shape) / len(shape)
    return [min(0.98, max(0.05, s + shift)) for s in shape]


def _split_f1(f1: float, rnd: random.Random) -> tuple[float, float]:
    """Chọn precision quanh f1 rồi tính recall để trung bình điều hòa đúng bằng f1."""
    for _ in range(20):
        p = min(0.99, max(f1 / 2 + 0.02, f1 + rnd.uniform(-0.09, 0.09)))
        r = f1 * p / (2 * p - f1)
        if 0 < r <= 1:
            return p, r
    return f1, f1


def file_sha256(path: str | os.PathLike, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()
