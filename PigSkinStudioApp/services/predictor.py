"""
services/predictor.py — Suy luận MobileNetV2 từ checkpoint của training run.

- Nếu có torch + torchvision và file checkpoint tồn tại → chạy model thật.
- Nếu thiếu → chế độ DEMO: điểm số giả lập (ổn định theo nội dung file) để thử giao diện.
  Giao diện luôn hiển thị rõ đang ở chế độ nào và mặc định KHÔNG lưu kết quả demo vào CSDL.

Thứ tự lớp đầu ra lấy từ config_json["classes"] của run (đúng thứ tự lúc train);
nếu không có thì dùng thứ tự class_id trong disease_classes (kèm cảnh báo).
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


@dataclass
class PredictionResult:
    scores: dict[str, float]               # code → score (tổng = 1)
    mode: str                              # "model" | "demo"
    warnings: list[str] = field(default_factory=list)
    preview_path: str | None = None        # ảnh/khung hình đã đưa vào model


def torch_available() -> bool:
    try:
        import torch  # noqa: F401
        import torchvision  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def extract_video_frame(video_path: str, seconds: float) -> str:
    """Cắt khung hình tại thời điểm `seconds`, lưu PNG tạm và trả về đường dẫn."""
    try:
        import cv2
    except ImportError as e:
        raise RuntimeError("Cần cài opencv-python để đọc video: pip install opencv-python") from e
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Không mở được video: {video_path}")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        n_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        duration = n_frames / fps if fps else None
        if duration is not None and seconds > duration:
            raise RuntimeError(f"frame_time_seconds = {seconds}s vượt quá độ dài video ({duration:.1f}s).")
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, seconds) * 1000.0)
        ok, frame = cap.read()
        if not ok or frame is None:
            raise RuntimeError(f"Không đọc được khung hình tại {seconds}s.")
        out = Path(tempfile.gettempdir()) / f"pigskin_frame_{Path(video_path).stem}_{seconds:.2f}.png"
        cv2.imwrite(str(out), frame)
        return str(out)
    finally:
        cap.release()


class Predictor:
    def __init__(self):
        self._cache: dict[int, tuple] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def predict(self, run: dict, image_path: str, db_codes: list[str]) -> PredictionResult:
        cfg = _safe_json(run.get("config_json"))
        warnings: list[str] = []
        codes = cfg.get("classes") if isinstance(cfg.get("classes"), list) else None
        if not codes or not all(isinstance(c, str) for c in codes):
            codes = db_codes
            warnings.append("config_json không có danh sách 'classes' — dùng thứ tự class_id trong CSDL.")
        unknown = [c for c in codes if c not in db_codes]
        if unknown:
            raise RuntimeError(f"Lớp trong config của run không có trong disease_classes: {unknown}")

        ckpt = run.get("checkpoint_path")
        if torch_available() and ckpt and os.path.exists(ckpt):
            try:
                scores = self._predict_torch(run["run_id"], ckpt, cfg, codes, image_path)
                return PredictionResult(scores, "model", warnings, image_path)
            except Exception as e:  # noqa: BLE001
                warnings.append(f"Không chạy được model thật ({e}). Chuyển sang chế độ demo.")
        else:
            reason = "chưa cài torch/torchvision" if not torch_available() else f"không thấy checkpoint {ckpt}"
            warnings.append(f"Chế độ DEMO ({reason}) — điểm số là giả lập, không dùng để kết luận.")
        return PredictionResult(self._demo_scores(run["run_id"], image_path, codes), "demo", warnings, image_path)

    # ------------------------------------------------------------------
    def _load_model(self, run_id: int, ckpt: str, n_classes: int):
        import torch
        from torchvision import models

        with self._lock:
            key = (ckpt, os.path.getmtime(ckpt))
            cached = self._cache.get(run_id)
            if cached and cached[0] == key:
                return cached[1], cached[2]
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            obj = torch.load(ckpt, map_location=device, weights_only=False)
            if isinstance(obj, torch.nn.Module):
                model = obj
            else:
                state = obj
                if isinstance(obj, dict):
                    for k in ("model_state_dict", "state_dict", "model", "weights"):
                        if k in obj and isinstance(obj[k], dict):
                            state = obj[k]
                            break
                state = {k.removeprefix("module."): v for k, v in state.items()}
                model = models.mobilenet_v2(weights=None)
                model.classifier[1] = torch.nn.Linear(model.last_channel, n_classes)
                model.load_state_dict(state, strict=True)
            model.to(device).eval()
            self._cache[run_id] = (key, model, device)
            return model, device

    def _predict_torch(self, run_id: int, ckpt: str, cfg: dict, codes: list[str], image_path: str) -> dict[str, float]:
        import torch
        from torchvision import transforms

        model, device = self._load_model(run_id, ckpt, len(codes))
        size = int(cfg.get("image_size") or 224)
        norm = cfg.get("normalization") if isinstance(cfg.get("normalization"), dict) else {}
        mean = norm.get("mean", [0.485, 0.456, 0.406])
        std = norm.get("std", [0.229, 0.224, 0.225])
        tf = transforms.Compose([
            transforms.Resize((size, size)),
            transforms.ToTensor(),
            transforms.Normalize(mean, std),
        ])
        with Image.open(image_path) as im:
            x = tf(im.convert("RGB")).unsqueeze(0).to(device)
        with torch.no_grad():
            probs = torch.softmax(model(x), dim=1)[0].cpu().tolist()
        if len(probs) != len(codes):
            raise RuntimeError(f"Model trả về {len(probs)} lớp, config có {len(codes)} lớp.")
        return {c: float(p) for c, p in zip(codes, probs)}

    @staticmethod
    def _demo_scores(run_id: int, image_path: str, codes: list[str]) -> dict[str, float]:
        h = hashlib.sha256(f"{run_id}:".encode())
        try:
            with open(image_path, "rb") as f:
                h.update(f.read(1 << 20))
        except OSError:
            h.update(image_path.encode())
        rnd = random.Random(int(h.hexdigest()[:16], 16))
        raw = [rnd.gammavariate(0.6, 1.0) for _ in codes]
        lead = rnd.randrange(len(codes))
        raw[lead] += rnd.uniform(0.3, 2.5)
        total = sum(raw)
        return {c: v / total for c, v in zip(codes, raw)}


def _safe_json(text: str | None) -> dict:
    try:
        data = json.loads(text or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}
