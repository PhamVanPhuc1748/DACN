"""
Explainable AI (Grad-CAM / Saliency Heatmap) & Dual-Model Benchmark Service for PigSkinTech.
Extracts real convolutional feature maps & gradients from PyTorch MobileNetV2 / EfficientNet-B0
and orchestrates side-by-side Dual-Model consensus benchmarking.
"""
from __future__ import annotations

from pathlib import Path
import threading
import time

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageOps

from services.inference import (
    clear_model_cache,
    ensure_cached_model,
    inspect_image,
    model_ready,
    model_status,
    predict,
    predict_batch,
)
from services.project_data import active_run, available_model_runs, display_class

__all__ = [
    "clear_model_cache",
    "inspect_image",
    "model_ready",
    "model_status",
    "predict",
    "predict_batch",
    "generate_gradcam_heatmap",
    "predict_dual_benchmark",
]

_GRADCAM_LOCK = threading.Lock()
HEATMAP_CACHE_DIR = Path(__file__).resolve().parents[1] / "case_images" / "heatmap_cache"


def _apply_jet_colormap(cam_uint8: np.ndarray) -> np.ndarray:
    """Map single-channel uint8 activation [0..255] to RGB JET thermal heatmap."""
    try:
        import cv2

        bgr = cv2.applyColorMap(cam_uint8, cv2.COLORMAP_JET)
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    except Exception:
        # Pure-NumPy JET colormap fallback when OpenCV is unavailable
        x = cam_uint8.astype(np.float32) / 255.0
        r = np.clip(1.5 - np.abs(4.0 * x - 3.0), 0.0, 1.0)
        g = np.clip(1.5 - np.abs(4.0 * x - 2.0), 0.0, 1.0)
        b = np.clip(1.5 - np.abs(4.0 * x - 1.0), 0.0, 1.0)
        return (np.stack([r, g, b], axis=-1) * 255.0).astype(np.uint8)


def _pil_erythema_fallback(src_path: Path, out_path: Path) -> str:
    """Fast C-level PIL lesion contrast fallback if PyTorch Grad-CAM cannot run."""
    with Image.open(src_path) as raw:
        rgb = ImageOps.exif_transpose(raw).convert("RGB")
        contrast_img = ImageEnhance.Sharpness(ImageEnhance.Contrast(rgb).enhance(1.85)).enhance(1.5)
        r_ch, g_ch, b_ch = rgb.split()
        r_lut = r_ch.point(lambda v: min(255, int(v * 1.45) + 60))
        g_lut = g_ch.point(lambda v: int(v * 0.55))
        b_lut = b_ch.point(lambda v: int(v * 0.45))
        erythema = ImageOps.autocontrast(ImageChops.subtract(ImageChops.subtract(r_lut, g_lut), b_lut), cutoff=2)
        thermal = ImageOps.colorize(erythema, black="#0F172A", mid="#F59E0B", white="#EF4444")
        blended = Image.blend(contrast_img, thermal, alpha=0.44)
        blended.save(out_path, format="JPEG", quality=92)
    return str(out_path.resolve())


def generate_gradcam_heatmap(
    image_path: str | Path,
    run_name: str | None = None,
    target_class_idx: int | None = None,
    alpha: float = 0.45,
) -> str:
    """
    Generate a real Explainable AI Grad-CAM heatmap from the final convolutional feature map
    of the active PyTorch checkpoint (MobileNetV2 / EfficientNet-B0 / MobileNetV3-Large),
    blended transparently over the original pig skin lesion photo.
    """
    src_path = Path(image_path or "")
    if not src_path.is_file():
        return str(image_path or "")

    HEATMAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    run = active_run(run_name)
    run_slug = (run.get("name") if run else "fallback") or "fallback"
    cls_slug = f"c{target_class_idx}" if target_class_idx is not None else "top1"
    out_path = HEATMAP_CACHE_DIR / f"gradcam_{run_slug}_{cls_slug}_{src_path.stem}.jpg"

    if not run:
        try:
            return _pil_erythema_fallback(src_path, out_path)
        except Exception:
            return str(src_path.resolve())

    try:
        import torch

        entry = ensure_cached_model(run)
        if entry is None:
            return _pil_erythema_fallback(src_path, out_path)

        model = entry["model"]
        device = entry["device"]
        transform = entry["transform"]
        target_layer = model.features[-1]

        with Image.open(src_path) as raw:
            rgb = ImageOps.exif_transpose(raw).convert("RGB")
            orig_w, orig_h = rgb.size
            orig_np = np.asarray(rgb, dtype=np.float32)
            cpu_tensor = transform(rgb).unsqueeze(0)

        activations: list[torch.Tensor] = []
        gradients: list[torch.Tensor] = []

        def _fwd_hook(_module, _inp, output):
            activations.append(output.detach())

        def _bwd_hook(_module, _grad_in, grad_out):
            if grad_out and grad_out[0] is not None:
                gradients.append(grad_out[0].detach())

        # Serialize Grad-CAM backward pass since PyTorch hooks mutate shared model state briefly
        with _GRADCAM_LOCK:
            h_fwd = target_layer.register_forward_hook(_fwd_hook)
            h_bwd = target_layer.register_full_backward_hook(_bwd_hook)
            try:
                with torch.enable_grad():
                    try:
                        x = cpu_tensor.to(device).requires_grad_(True)
                        model.zero_grad(set_to_none=True)
                        logits = model(x)
                    except RuntimeError:
                        device = torch.device("cpu")
                        entry["device"] = device
                        model.to(device).eval()
                        activations.clear()
                        gradients.clear()
                        x = cpu_tensor.to(device).requires_grad_(True)
                        model.zero_grad(set_to_none=True)
                        logits = model(x)

                    cls_idx = int(target_class_idx) if target_class_idx is not None else int(logits.argmax(dim=1).item())
                    cls_idx = max(0, min(cls_idx, logits.shape[1] - 1))
                    score = logits[0, cls_idx]
                    score.backward()
                    model.zero_grad(set_to_none=True)
            finally:
                h_fwd.remove()
                h_bwd.remove()

        if not activations or not gradients:
            return _pil_erythema_fallback(src_path, out_path)

        act = activations[0][0]   # [C, H_f, W_f]
        grad = gradients[0][0]    # [C, H_f, W_f]
        weights = grad.mean(dim=(1, 2), keepdim=True)  # Global average pooled gradients [C, 1, 1]
        cam = torch.relu((weights * act).sum(dim=0)).cpu().numpy()

        cam_max = float(cam.max())
        if cam_max > 1e-8:
            cam = (cam - float(cam.min())) / (cam_max - float(cam.min()) + 1e-8)
        else:
            # Saliency fallback if ReLU Grad-CAM map is flat
            cam = np.abs(act.mean(dim=0).cpu().numpy())
            cam = (cam - float(cam.min())) / (float(cam.max()) - float(cam.min()) + 1e-8)

        cam_uint8 = (np.clip(cam, 0.0, 1.0) * 255.0).astype(np.uint8)
        cam_resized = np.asarray(
            Image.fromarray(cam_uint8).resize((orig_w, orig_h), Image.Resampling.BILINEAR),
            dtype=np.uint8,
        )
        heat_rgb = _apply_jet_colormap(cam_resized).astype(np.float32)

        # Transparent adaptive blending: keep background crisp, emphasize hot lesion regions
        weight_map = (cam_resized.astype(np.float32) / 255.0)[..., None]
        adaptive_alpha = np.clip(alpha * (0.28 + 0.72 * weight_map), 0.10, 0.72)
        blended_np = np.clip((1.0 - adaptive_alpha) * orig_np + adaptive_alpha * heat_rgb, 0, 255).astype(np.uint8)
        blended_img = Image.fromarray(blended_np, mode="RGB")

        # Draw subtle emerald focus brackets around peak Grad-CAM hotspot (cam >= 0.65)
        hot_mask = cam_resized >= 166
        if hot_mask.any():
            ys, xs = np.where(hot_mask)
            x0, x1 = int(xs.min()), int(xs.max())
            y0, y1 = int(ys.min()), int(ys.max())
            pad_x = max(6, int((x1 - x0) * 0.08))
            pad_y = max(6, int((y1 - y0) * 0.08))
            bx0, by0 = max(2, x0 - pad_x), max(2, y0 - pad_y)
            bx1, by1 = min(orig_w - 3, x1 + pad_x), min(orig_h - 3, y1 + pad_y)
            corner = max(12, min(bx1 - bx0, by1 - by0) // 5)
            draw = ImageDraw.Draw(blended_img)
            col = (52, 211, 153)
            for cx, cy, dx, dy in (
                (bx0, by0, 1, 1),
                (bx1, by0, -1, 1),
                (bx0, by1, 1, -1),
                (bx1, by1, -1, -1),
            ):
                draw.line([(cx, cy), (cx + dx * corner, cy)], fill=col, width=3)
                draw.line([(cx, cy), (cx, cy + dy * corner)], fill=col, width=3)

        blended_img.save(out_path, format="JPEG", quality=92)
        return str(out_path.resolve())
    except Exception:
        try:
            return _pil_erythema_fallback(src_path, out_path)
        except Exception:
            return str(src_path.resolve())


def predict_dual_benchmark(image_path: str | Path) -> dict:
    """
    Run Dual-Model Benchmark comparing MobileNetV2 and EfficientNet-B0 on the same pig skin image.
    Returns side-by-side predictions, latencies (ms), and a clinical Consensus Badge evaluation.
    """
    runs = available_model_runs()
    mnet_run = next((r for r in runs if r.get("model") == "mobilenet_v2"), None)
    eff_run = next((r for r in runs if r.get("model") == "efficientnet_b0"), None)

    selected_runs = [r for r in (mnet_run, eff_run) if r is not None]
    if not selected_runs:
        cur = active_run()
        if cur:
            selected_runs = [cur]
        else:
            return {
                "ok": False,
                "is_valid_pig": False,
                "models": [],
                "primary": None,
                "consensus": {
                    "status": "unavailable",
                    "badge": "Thiếu mô hình",
                    "color": "#DC2626",
                    "summary": "Không tìm thấy checkpoint MobileNetV2 hoặc EfficientNet-B0 trong models/runs/.",
                },
            }

    t_total0 = time.perf_counter()
    results: list[dict] = []
    for r_cfg in selected_runs:
        res = predict(image_path, run_name=r_cfg["name"])
        results.append(res)
        # If Layer 0/1 already rejected non-pig image on the first model, skip redundant run
        if res.get("is_valid_pig") is False and not res.get("scores"):
            break
    total_ms = round((time.perf_counter() - t_total0) * 1000.0, 2)

    valid_results = [r for r in results if r.get("mode") == "ai" and r.get("is_valid_pig") is not False]
    if not valid_results:
        first_res = results[0]
        return {
            "ok": False,
            "is_valid_pig": False,
            "total_ms": total_ms,
            "models": results,
            "primary": first_res,
            "consensus": {
                "status": "invalid",
                "badge": "Ảnh không hợp lệ",
                "color": "#DC2626",
                "summary": first_res.get("validation_reason") or first_res.get("message") or "Ảnh không phải vùng da heo hợp lệ.",
            },
        }

    # Pick highest-confidence valid model as primary clinical output
    primary = max(valid_results, key=lambda r: float(r.get("confidence") or 0.0))

    if len(valid_results) >= 2:
        r1, r2 = valid_results[0], valid_results[1]
        same_label = r1.get("label") == r2.get("label")
        avg_conf = (float(r1.get("confidence") or 0.0) + float(r2.get("confidence") or 0.0)) / 2.0
        if same_label and avg_conf >= 0.75:
            consensus = {
                "status": "high_consensus",
                "agreed": True,
                "badge": "Đồng thuận cao (2/2 mô hình khớp)",
                "color": "#059669",
                "avg_confidence": avg_conf,
                "summary": (
                    f"Cả {r1.get('architecture')} và {r2.get('architecture')} đều kết luận "
                    f"'{display_class(r1.get('label'))}' (độ tin cậy TB {avg_conf * 100:.1f}%)."
                ),
            }
        elif same_label:
            consensus = {
                "status": "moderate_consensus",
                "agreed": True,
                "badge": "Đồng thuận trung bình (Khớp nhãn)",
                "color": "#0284C7",
                "avg_confidence": avg_conf,
                "summary": (
                    f"2/2 mô hình cùng chọn '{display_class(r1.get('label'))}' nhưng độ tin cậy TB "
                    f"chỉ đạt {avg_conf * 100:.1f}% — nên gửi Bác sĩ Thú y kiểm tra thêm."
                ),
            }
        else:
            consensus = {
                "status": "divergent",
                "agreed": False,
                "badge": "Bất đồng giữa 2 mô hình (Cần hội chẩn BS)",
                "color": "#D97706",
                "avg_confidence": avg_conf,
                "summary": (
                    f"{r1.get('architecture')} chọn '{display_class(r1.get('label'))}' ({float(r1.get('confidence') or 0)*100:.1f}%) "
                    f"trong khi {r2.get('architecture')} chọn '{display_class(r2.get('label'))}' ({float(r2.get('confidence') or 0)*100:.1f}%). "
                    "Khuyến nghị gửi Chuyên gia Thú y thẩm định."
                ),
            }
    else:
        r1 = valid_results[0]
        consensus = {
            "status": "single_model",
            "agreed": True,
            "badge": f"Chỉ có 1 mô hình ({r1.get('architecture')})",
            "color": "#0284C7",
            "avg_confidence": float(r1.get("confidence") or 0.0),
            "summary": f"Chạy trên {r1.get('architecture')} ({r1.get('run_name')}).",
        }

    return {
        "ok": True,
        "is_valid_pig": True,
        "total_ms": total_ms,
        "models": results,
        "primary": primary,
        "consensus": consensus,
    }
