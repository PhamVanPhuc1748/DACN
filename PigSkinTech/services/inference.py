"""Validate images and run predictions with the selected local checkpoint (best_model.pt)."""
import json
import subprocess
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from services.project_data import active_run, display_class, get_class_info, torch_python


ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 10 * 1024 * 1024
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
WORKER = ROOT / "services" / "inference_worker.py"


def _current_run(run_name=None):
    return active_run(run_name)


def inspect_image(path):
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Tập tin không tồn tại: {path}")
    if p.suffix.lower() not in EXTENSIONS:
        raise ValueError("Định dạng không được hỗ trợ. Chỉ nhận JPG, PNG, WEBP.")
    size = p.stat().st_size
    if size > MAX_BYTES:
        raise ValueError("Kích thước tệp vượt quá 10MB.")
    try:
        with Image.open(p) as img:
            img.verify()
        with Image.open(p) as img:
            return {
                "name": p.name, "path": str(p), "size_bytes": size,
                "width": img.width, "height": img.height, "mode": img.mode,
            }
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Ảnh bị hỏng hoặc không thể đọc.") from exc


def labels(run_name=None):
    run = _current_run(run_name)
    names = run["config"].get("classes", []) if run else []
    return names


def model_ready(run_name=None):
    run = _current_run(run_name)
    return bool(run and run["checkpoint"].is_file() and run["config"].get("classes"))


def model_status(run_name=None):
    run = _current_run(run_name)
    return {
        "ready": model_ready(run_name),
        "run_name": run["name"] if run else None,
        "classes_count": len(run["config"].get("classes", [])) if run else 0,
        "weights": str(run["checkpoint"]) if run else None,
    }


def predict(path, run_name=None):
    """Run the matching model in the training environment and return actual scores."""
    info = inspect_image(path)
    run = _current_run(run_name)
    if not run:
        return {
            "mode": "unavailable", "label": None, "confidence": None, "scores": [],
            "info": info, "message": "Chưa tìm thấy checkpoint huấn luyện hợp lệ.",
        }

    python_bin = torch_python()
    cmd = [python_bin, str(WORKER), str(run["checkpoint"]), str(info["path"])]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=60,
            cwd=str(ROOT),
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(stderr or f"Lỗi suy luận ({exc.returncode})") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Tiến trình suy luận quá thời gian (60s).") from exc

    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Tiến trình mô hình trả về dữ liệu không hợp lệ.") from exc
    if result.get("mode") != "ai" or not result.get("scores"):
        raise RuntimeError(result.get("message", "Mô hình không trả về dự đoán."))

    cls_meta = get_class_info(result["label"])
    result["display_label"] = display_class(result["label"])
    result["danger_level"] = cls_meta.get("danger_level", "Trung bình")
    result["recommendation"] = cls_meta.get("treatment", "")
    result["symptoms_ref"] = cls_meta.get("symptoms", "")
    result["info"] = info
    result["message"] = "Kết quả suy luận từ checkpoint train cục bộ; cần người có chuyên môn xác minh."
    return result


def predict_batch(paths: list[str], run_name=None) -> list[dict]:
    """Run batch inference across multiple image paths."""
    results = []
    for p in paths:
        try:
            results.append(predict(p, run_name=run_name))
        except Exception as exc:
            results.append({
                "mode": "error",
                "label": None,
                "display_label": "Lỗi đọc/xử lý ảnh",
                "confidence": 0.0,
                "scores": [],
                "info": {"name": Path(p).name, "path": str(p)},
                "message": str(exc),
            })
    return results
