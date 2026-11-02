"""Validate images and run predictions with the latest compatible local checkpoint."""
import json
import subprocess
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from services.project_data import active_run, display_class, torch_python


ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 10 * 1024 * 1024
WORKER = ROOT / "services" / "inference_worker.py"


def _current_run():
    return active_run()


def inspect_image(path):
    p = Path(path)
    if not p.is_file() or p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
        raise ValueError("Chọn ảnh JPG, PNG hoặc WEBP hợp lệ.")
    count = p.stat().st_size
    if not 0 < count <= MAX_BYTES:
        raise ValueError("Ảnh phải có dung lượng tối đa 10 MB.")
    try:
        with Image.open(p) as im:
            if im.format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError("Định dạng ảnh không hỗ trợ.")
            width, height = im.size
            im.verify()
    except (UnidentifiedImageError, OSError) as ex:
        raise ValueError("Không thể mở ảnh; file có thể đã bị hỏng.") from ex
    return {"name": p.name, "path": str(p), "bytes": count, "width": width, "height": height}


def labels():
    run = _current_run()
    if not run:
        raise FileNotFoundError("Chưa tìm thấy lần train có checkpoint và báo cáo đầy đủ.")
    names = run["config"].get("classes", [])
    if not names or not all(isinstance(name, str) and name for name in names):
        raise ValueError("config.json của lần train không có danh sách lớp hợp lệ.")
    return names


def model_ready():
    run = _current_run()
    return bool(run and run["checkpoint"].is_file() and run["config"].get("classes"))


def model_status():
    run = _current_run()
    python = torch_python()
    return {
        "ready": model_ready(),
        "run": run,
        "python": python,
        "runtime_ready": bool(python),
    }


def predict(path):
    """Run the matching model in the training environment and return actual scores."""
    info = inspect_image(path)
    run = _current_run()
    if not run:
        return {
            "mode": "unavailable", "label": None, "confidence": None, "scores": [],
            "message": "Không tìm thấy checkpoint và báo cáo train hoàn chỉnh.",
        }
    python = torch_python()
    if not python:
        raise RuntimeError(
            "Không tìm thấy Python có PyTorch và TorchVision. Kiểm tra môi trường .venv của PigSkinResearchStudio."
        )

    command = [
        str(python), str(WORKER), str(info["path"]),
        str(run["checkpoint"]), str(run["config_path"]),
    ]
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=180,
    )
    if completed.returncode:
        message = completed.stderr.strip() or completed.stdout.strip() or "Không thể chạy mô hình."
        raise RuntimeError(message[-1800:])
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Tiến trình mô hình trả về dữ liệu không hợp lệ.") from exc
    if result.get("mode") != "ai" or not result.get("scores"):
        raise RuntimeError(result.get("message", "Mô hình không trả về dự đoán."))
    result["display_label"] = display_class(result["label"])
    result["info"] = info
    result["message"] = "Kết quả suy luận từ checkpoint train cục bộ; cần người có chuyên môn xác minh."
    return result
