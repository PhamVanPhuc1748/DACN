"""
database/seed_importer.py — Đồng bộ dữ liệu thật vào pig_skin.db theo quy trình 6 bước (mục 6 tài liệu):

 1. classes.json      → disease_classes (giữ nguyên code)
 2. manifest.csv      → dataset_versions (SHA-256 thật của manifest)
 3. từng dòng CSV     → images (+SHA-256, kích thước), image_labels ('pending'), dataset_items, dataset_item_labels
 4. config.json + final_metrics.json → training_runs
 5. best_validation.json + final_metrics.json → run_class_metrics
 6. Đối chiếu số dòng theo split và theo lớp với manifest

Nguyên tắc:
- KHÔNG gán image_labels.review_status = 'approved'. Nhãn nguồn luôn vào 'pending';
  nếu nhãn đã tồn tại (đã được người duyệt) thì giữ nguyên trạng thái cũ.
- 'valid' / 'validation' trong manifest được chuẩn hóa thành 'val'.
- relative_path lưu dạng tương đối với dấu '/', không lưu đường dẫn máy như E:\\...

Hàm chính `run_import()` là hàm đồng bộ, chạy được trong thread nền và báo tiến trình qua callback.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any, Callable

import config
from database.db_manager import DBManager, file_sha256

try:  # Pillow là tùy chọn — chỉ để đọc width/height
    from PIL import Image as _PILImage
except ImportError:  # pragma: no cover
    _PILImage = None

ProgressCB = Callable[[float, str], None]

SPLIT_ALIASES = {"train": "train", "training": "train", "val": "val", "valid": "val",
                 "validation": "val", "test": "test", "testing": "test"}


@dataclass
class ImportOptions:
    manifest_path: Path
    classes_path: Path
    image_root: Path
    run_dir: Path | None = None
    compute_hash: bool = True
    reset_existing: bool = False
    dataset_name: str | None = None
    dataset_version: str | None = None


@dataclass
class ImportReport:
    classes: int = 0
    rows: int = 0
    images_new: int = 0
    images_existing: int = 0
    labels_new: int = 0
    labels_kept: int = 0
    missing_files: int = 0
    duplicate_sha: list[str] = field(default_factory=list)
    split_counts: dict[str, int] = field(default_factory=dict)
    run_name: str | None = None
    run_metrics_rows: int = 0
    warnings: list[str] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)
    dataset_id: int | None = None

    @property
    def ok(self) -> bool:
        return all(c["status"] != "fail" for c in self.checks)


class ImportError_(Exception):
    """Lỗi nghiệp vụ khi nạp (tránh trùng tên với builtin ImportError)."""


# ----------------------------------------------------------------------
# Tiện ích đọc file
# ----------------------------------------------------------------------
def _read_json(path: Path | None) -> Any:
    if not path or not Path(path).exists():
        return None
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def parse_classes_json(data: Any) -> list[dict]:
    """Chấp nhận các dạng phổ biến của classes.json, trả về [{index, code, name_vi, description}] theo thứ tự index.

    - ["a", "b", ...]
    - {"classes": [...]} / {"class_names": [...]}
    - {"a": 0, "b": 1} (code → index)  hoặc  {"0": "a", "1": "b"} (index → code)
    - [{"code"/"name"/"label": "a", "name_vi": "...", "index"/"id": 0}, ...]
    """
    if isinstance(data, dict):
        for key in ("classes", "class_names", "labels", "class_map", "idx_to_class", "class_to_idx"):
            if key in data:
                return parse_classes_json(data[key])
        if data and all(isinstance(v, int) for v in data.values()):          # code → index
            items = sorted(data.items(), key=lambda kv: kv[1])
            return [{"index": i, "code": str(k), "name_vi": None, "description": None} for k, i in items]
        if data and all(str(k).lstrip("-").isdigit() for k in data):        # index → code
            items = sorted(data.items(), key=lambda kv: int(kv[0]))
            out = []
            for k, v in items:
                if isinstance(v, dict):
                    out.append(_class_from_dict(v, int(k)))
                else:
                    out.append({"index": int(k), "code": str(v), "name_vi": None, "description": None})
            return out
        raise ImportError_("Không nhận dạng được cấu trúc classes.json.")
    if isinstance(data, list):
        out = []
        for i, item in enumerate(data):
            if isinstance(item, str):
                out.append({"index": i, "code": item, "name_vi": None, "description": None})
            elif isinstance(item, dict):
                out.append(_class_from_dict(item, i))
            else:
                raise ImportError_(f"Phần tử lớp không hợp lệ ở vị trí {i}: {item!r}")
        return sorted(out, key=lambda c: c["index"])
    raise ImportError_("classes.json phải là list hoặc dict.")


def _class_from_dict(d: dict, default_index: int) -> dict:
    code = d.get("code") or d.get("name") or d.get("label") or d.get("class")
    if not code:
        raise ImportError_(f"Lớp ở vị trí {default_index} thiếu 'code'/'name'.")
    idx = d.get("index", d.get("id", d.get("class_index", default_index)))
    return {"index": int(idx), "code": str(code),
            "name_vi": d.get("name_vi") or d.get("vi") or d.get("display_name_vi"),
            "description": d.get("description") or d.get("name_en")}


def normalize_split(value: str) -> str:
    key = (value or "").strip().lower()
    if key not in SPLIT_ALIASES:
        raise ImportError_(f"Giá trị split không hợp lệ: '{value}'")
    return SPLIT_ALIASES[key]


def normalize_relative_path(raw: str, image_root: Path) -> str:
    """Đưa về đường dẫn tương đối dạng 'a/b/c.jpg'. Đường dẫn tuyệt đối được cắt theo image_root."""
    raw = (raw or "").strip().strip('"')
    if not raw:
        raise ImportError_("relative_path rỗng.")
    win = PureWindowsPath(raw)
    if win.is_absolute() or Path(raw).is_absolute():
        root = PureWindowsPath(str(image_root))
        try:
            return win.relative_to(root).as_posix()
        except ValueError:
            raise ImportError_(f"Đường dẫn tuyệt đối không nằm trong thư mục ảnh gốc: {raw}")
    path = raw.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if path.startswith("../") or "/../" in path:
        raise ImportError_(f"relative_path không được chứa '..': {raw}")
    return path


def split_labels(value: str) -> list[str]:
    value = (value or "").strip()
    if not value:
        return []
    if value.startswith("["):
        try:
            return [str(v).strip() for v in json.loads(value) if str(v).strip()]
        except json.JSONDecodeError:
            pass
    return [p.strip() for p in re.split(r"[;|,]", value) if p.strip()]


def _find_key(d: Any, names: tuple[str, ...]) -> Any:
    """Tìm đệ quy giá trị đầu tiên có khóa thuộc names (không phân biệt hoa thường)."""
    lowered = {n.lower() for n in names}
    if isinstance(d, dict):
        for k, v in d.items():
            if str(k).lower() in lowered and not isinstance(v, (dict, list)):
                return v
        for v in d.values():
            found = _find_key(v, names)
            if found is not None:
                return found
    return None


def _section(d: Any, names: tuple[str, ...]) -> Any:
    if isinstance(d, dict):
        for k, v in d.items():
            if str(k).lower() in names and isinstance(v, dict):
                return v
    return None


def extract_per_class(d: Any, codes: list[str]) -> dict[str, dict]:
    """Tìm chỉ số từng lớp ở nhiều định dạng: dict {code: {...}} (kể cả classification_report),
    hoặc list [{class/code/name: .., precision: ..}]."""
    code_set = set(codes)
    result: dict[str, dict] = {}

    def norm(m: dict) -> dict | None:
        lower = {str(k).lower().replace("-", "_"): v for k, v in m.items()}
        f1 = lower.get("f1", lower.get("f1_score"))
        p, r = lower.get("precision"), lower.get("recall")
        if f1 is None and p is None and r is None:
            return None
        return {"precision": p, "recall": r, "f1": f1, "support": lower.get("support")}

    def walk(node: Any) -> None:
        if result:
            return
        if isinstance(node, dict):
            hits = {k: v for k, v in node.items() if k in code_set and isinstance(v, dict)}
            if len(hits) >= max(1, len(code_set) // 2):
                for k, v in hits.items():
                    m = norm(v)
                    if m:
                        result[k] = m
                if result:
                    return
            for v in node.values():
                walk(v)
        elif isinstance(node, list) and node and all(isinstance(x, dict) for x in node):
            for x in node:
                code = x.get("class") or x.get("code") or x.get("name") or x.get("label")
                if code in code_set:
                    m = norm(x)
                    if m:
                        result[code] = m
            if not result:
                for x in node:
                    walk(x)

    walk(d)
    return result


def _parse_run_time(run_name: str) -> str | None:
    try:
        return datetime.strptime(run_name, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------
# Quy trình chính
# ----------------------------------------------------------------------
def run_import(db: DBManager, opts: ImportOptions, progress: ProgressCB | None = None) -> ImportReport:
    def step(frac: float, msg: str) -> None:
        if progress:
            progress(max(0.0, min(1.0, frac)), msg)

    rep = ImportReport()
    manifest_path, classes_path, image_root = Path(opts.manifest_path), Path(opts.classes_path), Path(opts.image_root)
    if not manifest_path.exists():
        raise ImportError_(f"Không tìm thấy manifest: {manifest_path}")
    if not classes_path.exists():
        raise ImportError_(f"Không tìm thấy classes.json: {classes_path}")
    if not image_root.exists():
        rep.warnings.append(f"Thư mục ảnh gốc không tồn tại: {image_root} — sẽ không tính được SHA-256/kích thước.")

    # Đọc trước toàn bộ file ngoài transaction (nhanh, phát hiện lỗi sớm)
    step(0.01, "Đọc classes.json")
    classes = parse_classes_json(_read_json(classes_path))
    codes = [c["code"] for c in classes]
    if len(set(codes)) != len(codes):
        raise ImportError_("classes.json có mã lớp trùng nhau.")
    if len(codes) != config.EXPECTED_NUM_CLASSES:
        rep.warnings.append(f"classes.json có {len(codes)} lớp (chuẩn {config.EXPECTED_NUM_CLASSES}).")

    step(0.03, "Đọc manifest.csv")
    with open(manifest_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = {h.strip().lower(): h for h in (reader.fieldnames or [])}
        for col in ("relative_path", "labels", "split"):
            if col not in header:
                raise ImportError_(f"manifest.csv thiếu cột bắt buộc '{col}'. Cột hiện có: {reader.fieldnames}")
        rows = [{k.strip().lower(): (v or "") for k, v in r.items() if k} for r in reader]
    if not rows:
        raise ImportError_("manifest.csv không có dòng dữ liệu.")

    manifest_sha = file_sha256(manifest_path)
    run_dir = Path(opts.run_dir) if opts.run_dir else None
    run_cfg = _read_json(run_dir / "config.json") if run_dir else None
    best_val = _read_json(run_dir / "best_validation.json") if run_dir else None
    final = _read_json(run_dir / "final_metrics.json") if run_dir else None
    seed = _find_key(run_cfg, ("seed",)) if run_cfg else None

    name = opts.dataset_name or manifest_path.parent.name
    m = re.search(r"_(v\d+)$", name)
    version = opts.dataset_version or (m.group(1) if m else "v1")

    # Chuẩn hóa toàn bộ dòng trước khi ghi → lỗi dữ liệu không để lại DB nửa vời
    parsed: list[dict] = []
    manifest_counts = {s: 0 for s in config.SPLITS}
    manifest_class_counts: dict[str, int] = {c: 0 for c in codes}
    seen_paths: set[str] = set()
    for i, r in enumerate(rows, start=2):
        try:
            rel = normalize_relative_path(r["relative_path"], image_root)
            split = normalize_split(r["split"])
            labels = split_labels(r["labels"])
        except ImportError_ as e:
            raise ImportError_(f"Dòng {i}: {e}") from None
        if not labels:
            raise ImportError_(f"Dòng {i}: không có nhãn.")
        unknown = [lb for lb in labels if lb not in manifest_class_counts]
        if unknown:
            raise ImportError_(f"Dòng {i}: nhãn {unknown} không có trong classes.json.")
        if rel in seen_paths:
            raise ImportError_(f"Dòng {i}: ảnh '{rel}' xuất hiện nhiều lần trong manifest.")
        seen_paths.add(rel)
        manifest_counts[split] += 1
        for lb in labels:
            manifest_class_counts[lb] += 1
        parsed.append({"rel": rel, "split": split, "labels": labels, "group_id": r.get("group_id") or None})

    total = len(parsed)
    rep.rows = total

    with db.transaction() as conn:
        if opts.reset_existing:
            step(0.05, "Xóa dữ liệu cũ (bao gồm dữ liệu mẫu)")
            db.reset_all_data(conn)

        # ---- Bước 1: disease_classes
        step(0.06, "Bước 1/6 · Nạp danh mục lớp")
        class_ids: dict[str, int] = {}
        for c in classes:
            existing = conn.execute("SELECT class_id, name_vi FROM disease_classes WHERE code = ?", (c["code"],)).fetchone()
            if existing:
                class_ids[c["code"]] = existing["class_id"]
                if c["name_vi"] and existing["name_vi"] == c["code"]:
                    conn.execute("UPDATE disease_classes SET name_vi = ? WHERE class_id = ?",
                                 (c["name_vi"], existing["class_id"]))
            else:
                cur = conn.execute(
                    "INSERT INTO disease_classes (code, name_vi, description) VALUES (?, ?, ?)",
                    # name_vi tạm = code nếu classes.json chưa có tên tiếng Việt (nhóm xác nhận sau)
                    (c["code"], c["name_vi"] or c["code"], c["description"]),
                )
                class_ids[c["code"]] = cur.lastrowid
        rep.classes = len(class_ids)

        # ---- Bước 2: dataset_versions
        step(0.08, "Bước 2/6 · Tạo phiên bản dataset")
        notes = {
            "mock": False,
            "label_source": f"manifest:{manifest_path.name}",
            "manifest_counts": manifest_counts,
            "class_counts": manifest_class_counts,
            "image_root": str(image_root),
            "imported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        ds = conn.execute("SELECT dataset_id, manifest_sha256 FROM dataset_versions WHERE name = ? AND version = ?",
                          (name, version)).fetchone()
        if ds:
            dataset_id = ds["dataset_id"]
            if ds["manifest_sha256"] and ds["manifest_sha256"] != manifest_sha:
                rep.warnings.append("Manifest đã thay đổi so với lần nạp trước nhưng vẫn dùng cùng tên/phiên bản — "
                                    "nên tạo phiên bản dataset mới để giữ lịch sử.")
            # Nạp lại idempotent: làm mới items của phiên bản này
            conn.execute("""DELETE FROM dataset_item_labels WHERE dataset_item_id IN
                            (SELECT dataset_item_id FROM dataset_items WHERE dataset_id = ?)""", (dataset_id,))
            conn.execute("DELETE FROM dataset_items WHERE dataset_id = ?", (dataset_id,))
            conn.execute("UPDATE dataset_versions SET manifest_path = ?, manifest_sha256 = ?, seed = ?, notes = ? "
                         "WHERE dataset_id = ?",
                         (str(manifest_path), manifest_sha, seed, json.dumps(notes, ensure_ascii=False), dataset_id))
        else:
            cur = conn.execute(
                """INSERT INTO dataset_versions (name, version, manifest_path, manifest_sha256, seed, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, version, str(manifest_path), manifest_sha, seed, json.dumps(notes, ensure_ascii=False)),
            )
            dataset_id = cur.lastrowid
        rep.dataset_id = dataset_id

        # ---- Bước 3: images, image_labels, dataset_items, dataset_item_labels
        source = f"manifest:{name}"
        for n, item in enumerate(parsed, start=1):
            rel = item["rel"]
            row = conn.execute("SELECT image_id FROM images WHERE relative_path = ?", (rel,)).fetchone()
            if row:
                image_id = row["image_id"]
                rep.images_existing += 1
            else:
                sha, w, h = None, None, None
                abs_path = image_root / rel
                if abs_path.exists():
                    if opts.compute_hash:
                        sha = file_sha256(abs_path)
                        dup = conn.execute("SELECT relative_path FROM images WHERE sha256 = ?", (sha,)).fetchone()
                        if dup:
                            rep.duplicate_sha.append(f"{rel} trùng nội dung với {dup['relative_path']}")
                            sha = None  # cột sha256 UNIQUE → để trống và báo cáo để nhóm xử lý
                    if _PILImage is not None:
                        try:
                            with _PILImage.open(abs_path) as im:
                                w, h = im.size
                        except Exception:  # noqa: BLE001 — ảnh hỏng vẫn được ghi, chỉ thiếu kích thước
                            rep.warnings.append(f"Không đọc được kích thước: {rel}")
                else:
                    rep.missing_files += 1
                cur = conn.execute(
                    "INSERT INTO images (relative_path, sha256, width, height, source) VALUES (?, ?, ?, ?, ?)",
                    (rel, sha, w, h, source),
                )
                image_id = cur.lastrowid
                rep.images_new += 1

            cur = conn.execute(
                "INSERT INTO dataset_items (dataset_id, image_id, split, group_id) VALUES (?, ?, ?, ?)",
                (dataset_id, image_id, item["split"], item["group_id"]),
            )
            item_id = cur.lastrowid
            for lb in item["labels"]:
                cid = class_ids[lb]
                conn.execute("INSERT INTO dataset_item_labels (dataset_item_id, class_id) VALUES (?, ?)", (item_id, cid))
                # Nhãn nguồn → 'pending'. INSERT OR IGNORE giữ nguyên trạng thái đã được người duyệt trước đó.
                cur = conn.execute(
                    "INSERT OR IGNORE INTO image_labels (image_id, class_id, review_status) VALUES (?, ?, 'pending')",
                    (image_id, cid),
                )
                if cur.rowcount:
                    rep.labels_new += 1
                else:
                    rep.labels_kept += 1
            if n % 25 == 0 or n == total:
                step(0.10 + 0.75 * n / total, f"Bước 3/6 · Nạp ảnh {n}/{total}")

        # ---- Bước 4: training_runs
        run_id = None
        if run_dir:
            step(0.87, "Bước 4/6 · Nạp training run")
            if not run_dir.exists():
                rep.warnings.append(f"Không tìm thấy thư mục run: {run_dir}")
            elif run_cfg is None:
                rep.warnings.append("Thiếu config.json trong thư mục run — bỏ qua bước 4–5.")
            else:
                run_id = _upsert_run(conn, dataset_id, run_dir, run_cfg, best_val, final, rep)

        # ---- Bước 5: run_class_metrics
        if run_id is not None:
            step(0.92, "Bước 5/6 · Nạp chỉ số từng lớp")
            conn.execute("DELETE FROM run_class_metrics WHERE run_id = ?", (run_id,))
            val_src = best_val if best_val is not None else _section(final, ("val", "valid", "validation"))
            test_src = _section(final, ("test", "testing")) or final
            for split, src in (("val", val_src), ("test", test_src)):
                per = extract_per_class(src, codes) if src is not None else {}
                if not per:
                    rep.warnings.append(f"Không tìm thấy chỉ số từng lớp cho tập {split}.")
                    continue
                for code, mt in per.items():
                    conn.execute(
                        """INSERT INTO run_class_metrics (run_id, split, class_id, precision, recall, f1, support)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (run_id, split, class_ids[code], _num(mt["precision"]), _num(mt["recall"]),
                         _num(mt["f1"]), int(mt["support"]) if _num(mt["support"]) is not None else None),
                    )
                    rep.run_metrics_rows += 1

    # ---- Bước 6: kiểm tra đối chiếu (sau khi commit)
    step(0.96, "Bước 6/6 · Đối chiếu với manifest")
    rep.split_counts = db.split_counts(dataset_id)
    rep.checks.append({
        "title": "Số ảnh theo split khớp manifest",
        "status": "pass" if rep.split_counts == manifest_counts else "fail",
        "detail": " · ".join(f"{s}: {rep.split_counts.get(s, 0)}/{manifest_counts[s]}" for s in config.SPLITS),
    })
    db_class = {r["code"]: r["train"] + r["val"] + r["test"] for r in db.class_split_distribution(dataset_id)}
    mismatched = [c for c in codes if db_class.get(c, 0) != manifest_class_counts[c]]
    rep.checks.append({
        "title": "Số ảnh theo lớp khớp manifest",
        "status": "pass" if not mismatched else "fail",
        "detail": "Tất cả lớp khớp." if not mismatched else f"Lệch: {', '.join(mismatched)}",
    })
    if config.EXPECTED_SPLITS != manifest_counts:
        rep.warnings.append(f"Manifest có {manifest_counts}, khác số chuẩn {config.EXPECTED_SPLITS} trong tài liệu.")
    if rep.missing_files:
        rep.warnings.append(f"{rep.missing_files} ảnh không tồn tại dưới {image_root}.")
    if rep.duplicate_sha:
        rep.warnings.append(f"{len(rep.duplicate_sha)} ảnh trùng nội dung (SHA-256) — xem chi tiết trong báo cáo.")
    step(1.0, "Hoàn tất")
    return rep


def _upsert_run(conn, dataset_id: int, run_dir: Path, run_cfg: dict, best_val: Any, final: Any,
                rep: ImportReport) -> int:
    run_name = run_dir.name
    model_code = str(_find_key(run_cfg, ("architecture", "arch", "model", "model_name", "backbone")) or "mobilenet_v2")
    test_sec = _section(final, ("test", "testing")) or final or {}
    best_epoch = _find_key(best_val, ("best_epoch", "epoch")) if best_val else None
    if best_epoch is None:
        best_epoch = _find_key(final, ("best_epoch",))
    best_val_f1 = _find_key(best_val, ("macro_f1", "val_macro_f1", "f1_macro")) if best_val else None
    if best_val_f1 is None:
        best_val_f1 = _find_key(final, ("best_val_macro_f1",))
    if best_val_f1 is None and isinstance(best_val, dict) and isinstance(best_val.get("macro avg"), dict):
        best_val_f1 = best_val["macro avg"].get("f1-score")
    test_acc = _find_key(test_sec, ("accuracy", "acc", "test_accuracy"))
    test_f1 = _find_key(test_sec, ("macro_f1", "test_macro_f1", "f1_macro"))
    if test_f1 is None and isinstance(test_sec, dict) and isinstance(test_sec.get("macro avg"), dict):
        test_f1 = test_sec["macro avg"].get("f1-score")

    ckpt = next((run_dir / n for n in ("best_model.pt", "best_model.pth", "model.pt") if (run_dir / n).exists()),
                run_dir / "best_model.pt")
    if not ckpt.exists():
        rep.warnings.append(f"Không thấy checkpoint trong {run_dir}")
    status = "completed" if final is not None else "running"
    finished = datetime.fromtimestamp((run_dir / "final_metrics.json").stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S") \
        if (run_dir / "final_metrics.json").exists() else None

    values = (dataset_id, model_code, status, json.dumps(run_cfg, ensure_ascii=False, indent=2), str(ckpt),
              int(best_epoch) if _num(best_epoch) is not None else None, _num(best_val_f1), _num(test_acc),
              _num(test_f1), _parse_run_time(run_name), finished)
    row = conn.execute("SELECT run_id FROM training_runs WHERE run_name = ?", (run_name,)).fetchone()
    if row:
        conn.execute(
            """UPDATE training_runs SET dataset_id=?, model_code=?, status=?, config_json=?, checkpoint_path=?,
                   best_epoch=?, best_val_macro_f1=?, test_accuracy=?, test_macro_f1=?, started_at=?, finished_at=?
               WHERE run_id = ?""", (*values, row["run_id"]))
        run_id = row["run_id"]
    else:
        cur = conn.execute(
            """INSERT INTO training_runs (dataset_id, model_code, status, config_json, checkpoint_path, best_epoch,
                   best_val_macro_f1, test_accuracy, test_macro_f1, started_at, finished_at, run_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (*values, run_name))
        run_id = cur.lastrowid
    rep.run_name = run_name
    for label, v in (("best_epoch", best_epoch), ("best_val_macro_f1", best_val_f1),
                     ("test_accuracy", test_acc), ("test_macro_f1", test_f1)):
        if v is None:
            rep.warnings.append(f"Không tìm thấy {label} trong file JSON của run.")
    return run_id
