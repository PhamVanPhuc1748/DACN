"""views/inference_view.py — Dự đoán & đối chiếu chuyên gia.

Tách biệt tuyệt đối:
- Khung "Kết quả model" chỉ hiển thị predicted_class_id + prediction_scores.
- Khung "Xác nhận của chuyên gia" ghi review_status + actual_class_id. Ô nhãn thật luôn bắt đầu TRỐNG;
  người duyệt phải tự chọn — ứng dụng không bao giờ chép predicted_class_id sang actual_class_id.
"""
from __future__ import annotations

from pathlib import Path

import flet as ft

import config
from components import fmt_num, panel, safe_update, section_title, toast
from components.confidence_bars import ConfidenceBars
from components.status_badge import StatusBadge
from database.db_manager import PREDICTION_REVIEW_STATUSES, DBManager
from services.predictor import Predictor, extract_video_frame, torch_available

NONE_KEY = "__none__"


class InferenceView(ft.Row):
    def __init__(self, page: ft.Page, db: DBManager):
        super().__init__(expand=True, spacing=16, vertical_alignment=ft.CrossAxisAlignment.START)
        self._page = page
        self.db = db
        self.predictor = Predictor()
        self.classes: list[dict] = []
        self.current_prediction: dict | None = None
        self._busy = False
        self._has_torch = torch_available()

        self.picker = ft.FilePicker(on_result=self._on_pick)
        page.overlay.append(self.picker)

        # ---------------- Cột trái: đầu vào ----------------
        self.dd_run = ft.Dropdown(label="Model run (run_id)", dense=True, border_radius=8, text_size=13, expand=True)
        self.mode = ft.SegmentedButton(
            selected={"image"}, allow_multiple_selection=False, show_selected_icon=False,
            segments=[ft.Segment(value="image", label=ft.Text("Ảnh lẻ"), icon=ft.Icon(ft.Icons.IMAGE_OUTLINED)),
                      ft.Segment(value="video_frame", label=ft.Text("Khung hình video"),
                                 icon=ft.Icon(ft.Icons.MOVIE_OUTLINED))],
            on_change=self._on_mode,
        )
        self.in_path = ft.TextField(label="Đường dẫn ảnh", dense=True, border_radius=8, text_size=12, expand=True,
                                    text_style=ft.TextStyle(font_family=config.MONO_FONT))
        self.in_time = ft.TextField(label="frame_time_seconds", value="0", dense=True, border_radius=8, width=170,
                                    text_size=13, suffix_text="giây", visible=False,
                                    input_filter=ft.InputFilter(regex_string=r"^[0-9]*\.?[0-9]*$", allow=True))
        self.cb_save = ft.Checkbox(label="Lưu kết quả vào CSDL (predictions)", value=self._has_torch)
        self.btn_run = ft.FilledButton("Chạy dự đoán", icon=ft.Icons.PLAY_ARROW, on_click=self._run,
                                       style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), height=44)
        self.busy = ft.ProgressRing(width=20, height=20, stroke_width=2, visible=False)
        self.engine = ft.Container(content=StatusBadge(
            "completed" if self._has_torch else "demo",
            label="PyTorch sẵn sàng" if self._has_torch else "Chưa có PyTorch → chế độ demo"))
        self.preview = ft.InteractiveViewer(min_scale=1, max_scale=8, boundary_margin=ft.margin.all(40),
                                            content=self._placeholder("Chưa có ảnh"))

        left = panel(ft.Column([
            section_title("Đầu vào", icon=ft.Icons.INPUT),
            ft.Row([self.dd_run]),
            self.mode,
            ft.Row([self.in_path, ft.IconButton(ft.Icons.FOLDER_OPEN, tooltip="Chọn file", on_click=self._pick)],
                   spacing=4),
            self.in_time,
            self.cb_save,
            ft.Row([self.btn_run, self.busy], spacing=12),
            self.engine,
            ft.Container(self.preview, height=260, border_radius=10, clip_behavior=ft.ClipBehavior.HARD_EDGE,
                         bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
            ft.Text("Zoom/kéo để soi vùng tổn thương.", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
        ], spacing=12, scroll=ft.ScrollMode.AUTO), width=360)

        # ---------------- Cột giữa: kết quả model ----------------
        self.bars = ConfidenceBars(track_width=330)
        self.result_title = ft.Text("—", size=22, weight=ft.FontWeight.W_700)
        self.result_meta = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, selectable=True)
        self.result_warn = ft.Column(spacing=4)
        self.history = ft.Column(spacing=4)

        center = ft.Column([
            panel(ft.Column([
                section_title("Kết quả model", "prediction_scores · đây là DỰ ĐOÁN, không phải chẩn đoán", ft.Icons.INSIGHTS),
                ft.Text("Lớp đứng đầu (predicted_class_id)", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                self.result_title,
                self.result_meta,
                self.result_warn,
                ft.Divider(height=1),
                self.bars,
            ], spacing=8)),
            panel(ft.Column([
                section_title("Dự đoán gần đây", "Bấm để mở lại và xác nhận", ft.Icons.HISTORY),
                self.history,
            ], spacing=8)),
        ], spacing=16, expand=True, scroll=ft.ScrollMode.AUTO)

        # ---------------- Cột phải: xác nhận chuyên gia ----------------
        self.rv_info = ft.Text("Chưa có dự đoán đã lưu để xác nhận.", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.rv_badge = StatusBadge("unreviewed")
        self.rv_status = ft.RadioGroup(
            value="unreviewed", on_change=self._on_review_status,
            content=ft.Column([
                ft.Radio(value=s, label=config.STATUS_STYLES[s][0] + {
                    "unreviewed": " — chưa xem", "confirmed": " — model dự đoán đúng",
                    "incorrect": " — model dự đoán sai", "uncertain": " — chưa đủ căn cứ"}[s])
                for s in PREDICTION_REVIEW_STATUSES
            ], spacing=0),
        )
        self.rv_actual = ft.Dropdown(label="Nhãn thật (actual_class_id)", dense=True, border_radius=8, text_size=13,
                                     value=NONE_KEY, disabled=True)
        self.rv_hint = ft.Text("", size=11, color=ft.Colors.ON_SURFACE_VARIANT)
        self.rv_save = ft.FilledButton("Lưu xác nhận", icon=ft.Icons.VERIFIED, on_click=self._save_review,
                                       disabled=True, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))

        right = ft.Container(
            width=340,
            padding=16,
            border_radius=12,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.border.all(2, ft.Colors.with_opacity(0.55, "#8B5CF6")),
            content=ft.Column([
                ft.Row([ft.Icon(ft.Icons.GAVEL, color="#8B5CF6"),
                        ft.Text("Xác nhận của chuyên gia", size=16, weight=ft.FontWeight.W_700)], spacing=8),
                ft.Text("Khu vực ground truth — tách biệt với kết quả model. Chỉ người có thẩm quyền điền.",
                        size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Divider(height=1),
                ft.Row([self.rv_info, self.rv_badge], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
                ft.Text("review_status", size=12, weight=ft.FontWeight.W_600),
                self.rv_status,
                self.rv_actual,
                self.rv_hint,
                self.rv_save,
            ], spacing=10, scroll=ft.ScrollMode.AUTO),
        )

        self.controls = [left, center, right]

    # ------------------------------------------------------------------
    @staticmethod
    def _placeholder(text: str) -> ft.Control:
        return ft.Container(alignment=ft.alignment.center, expand=True,
                            content=ft.Column([ft.Icon(ft.Icons.IMAGE_SEARCH, size=40, color=ft.Colors.ON_SURFACE_VARIANT),
                                               ft.Text(text, size=12, color=ft.Colors.ON_SURFACE_VARIANT)],
                                              horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                              alignment=ft.MainAxisAlignment.CENTER))

    def load(self) -> None:
        self._page.run_thread(self._load_worker)

    def _load_worker(self) -> None:
        try:
            runs = self.db.list_runs("best_val_macro_f1", True)
            self.classes = self.db.get_classes()
        except Exception as e:  # noqa: BLE001
            toast(self._page, f"Lỗi đọc CSDL: {e}", "error")
            return
        keep = self.dd_run.value
        self.dd_run.options = [
            ft.dropdown.Option(str(r["run_id"]),
                               f"#{r['run_id']} · {r['run_name']} · {r['model_code']} · val F1 {fmt_num(r['best_val_macro_f1'])}")
            for r in runs
        ]
        keys = {o.key for o in self.dd_run.options}
        self.dd_run.value = keep if keep in keys else (self.dd_run.options[0].key if self.dd_run.options else None)
        self.rv_actual.options = [ft.dropdown.Option(NONE_KEY, "— Chưa chọn —")] + [
            ft.dropdown.Option(str(c["class_id"]), f"{c['name_vi']} · {c['code']}") for c in self.classes]
        safe_update(self.dd_run, self.rv_actual)
        self._render_history()

    # ------------------------------------------------------------------
    # Đầu vào
    # ------------------------------------------------------------------
    def _on_mode(self, e) -> None:
        is_video = "video_frame" in self.mode.selected
        self.in_time.visible = is_video
        self.in_path.label = "Đường dẫn video" if is_video else "Đường dẫn ảnh"
        safe_update(self.in_time, self.in_path)

    def _pick(self, e) -> None:
        is_video = "video_frame" in self.mode.selected
        self.picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.CUSTOM,
                               allowed_extensions=config.VIDEO_EXTENSIONS if is_video else config.IMAGE_EXTENSIONS,
                               dialog_title="Chọn video" if is_video else "Chọn ảnh da heo")

    def _on_pick(self, e: ft.FilePickerResultEvent) -> None:
        if e.files:
            self.in_path.value = e.files[0].path
            safe_update(self.in_path)
            if "image" in self.mode.selected:
                self.preview.content = ft.Image(src=e.files[0].path, fit=ft.ImageFit.CONTAIN)
                safe_update(self.preview)

    # ------------------------------------------------------------------
    # Dự đoán
    # ------------------------------------------------------------------
    def _run(self, e) -> None:
        if self._busy:
            return
        if not self.dd_run.value:
            toast(self._page, "Chưa có training run nào.", "warn")
            return
        path = (self.in_path.value or "").strip().strip('"')
        if not path or not Path(path).exists():
            toast(self._page, "Hãy chọn file đầu vào tồn tại.", "warn")
            return
        kind = "video_frame" if "video_frame" in self.mode.selected else "image"
        t = None
        if kind == "video_frame":
            try:
                t = float(self.in_time.value or 0)
            except ValueError:
                toast(self._page, "frame_time_seconds không hợp lệ.", "warn")
                return
        self._busy = True
        self.btn_run.disabled = True
        self.busy.visible = True
        safe_update(self.btn_run, self.busy)
        self._page.run_thread(self._predict_worker, int(self.dd_run.value), path, kind, t, bool(self.cb_save.value))

    def _predict_worker(self, run_id: int, path: str, kind: str, t: float | None, save: bool) -> None:
        try:
            run = self.db.get_run(run_id)
            image_path = extract_video_frame(path, t) if kind == "video_frame" else path
            if kind == "video_frame":
                self.preview.content = ft.Image(src=image_path, fit=ft.ImageFit.CONTAIN)
                safe_update(self.preview)
            code_to_cls = {c["code"]: c for c in self.classes}
            result = self.predictor.predict(run, image_path, [c["code"] for c in self.classes])
            scores = [{"class_id": code_to_cls[c]["class_id"], "code": c, "name_vi": code_to_cls[c]["name_vi"],
                       "score": s} for c, s in result.scores.items()]

            # Liên kết với bảng images nếu file nằm trong thư mục ảnh gốc
            image_id = None
            if kind == "image":
                root = Path(config.load_settings()["image_root"])
                try:
                    rel = Path(path).resolve().relative_to(root.resolve()).as_posix()
                    img = self.db.find_image_by_relative_path(rel)
                    image_id = img["image_id"] if img else None
                except ValueError:
                    pass

            top = max(scores, key=lambda s: s["score"])
            self.result_title.value = f"{top['name_vi']}  ·  {top['score'] * 100:.1f}%"
            self.result_meta.value = (f"Run #{run_id} {run['run_name']} · {kind}"
                                      + (f" @ {t:.2f}s" if t is not None else "")
                                      + (f" · image_id {image_id}" if image_id else " · ảnh ngoài kho")
                                      + f"\n{path}")
            self.result_warn.controls = [
                ft.Text(f"⚠ {w}", size=11, color="#E0A030") for w in result.warnings
            ]
            safe_update(self.result_title, self.result_meta, self.result_warn)
            self.bars.set_scores(scores)

            if save:
                pid = self.db.create_prediction(
                    run_id=run_id, scores={s["class_id"]: s["score"] for s in scores}, input_uri=path,
                    input_kind=kind, frame_time_seconds=t, image_id=image_id)
                self._open_review(self.db.get_prediction(pid))
                toast(self._page, f"Đã lưu dự đoán #{pid} (review_status = unreviewed).", "ok")
                self._render_history()
            else:
                self.current_prediction = None
                self._reset_review("Kết quả chưa được lưu nên chưa thể xác nhận. Bật “Lưu kết quả vào CSDL”.")
        except Exception as ex:  # noqa: BLE001
            toast(self._page, f"Dự đoán thất bại: {ex}", "error")
        finally:
            self._busy = False
            self.btn_run.disabled = False
            self.busy.visible = False
            safe_update(self.btn_run, self.busy)

    # ------------------------------------------------------------------
    # Xác nhận chuyên gia
    # ------------------------------------------------------------------
    def _cls_name(self, class_id: int | None) -> str:
        c = next((c for c in self.classes if c["class_id"] == class_id), None)
        return f"{c['name_vi']} ({c['code']})" if c else "—"

    def _reset_review(self, msg: str) -> None:
        self.rv_info.value = msg
        self.rv_badge.set_status("unreviewed")
        self.rv_status.value = "unreviewed"
        self.rv_actual.value = NONE_KEY
        self.rv_actual.disabled = True
        self.rv_save.disabled = True
        self.rv_hint.value = ""
        safe_update(self.rv_info, self.rv_badge, self.rv_status, self.rv_actual, self.rv_save, self.rv_hint)

    def _open_review(self, pred: dict | None) -> None:
        self.current_prediction = pred
        if not pred:
            self._reset_review("Chưa có dự đoán đã lưu để xác nhận.")
            return
        self.rv_info.value = (f"Dự đoán #{pred['prediction_id']} · model nói: "
                              f"{self._cls_name(pred['predicted_class_id'])} ({fmt_num(pred['top_score'], 3)})")
        self.rv_badge.set_status(pred["review_status"])
        self.rv_status.value = pred["review_status"]
        # Hiển thị nhãn thật ĐÃ LƯU (nếu có). Không bao giờ điền sẵn từ predicted_class_id.
        self.rv_actual.value = str(pred["actual_class_id"]) if pred["actual_class_id"] else NONE_KEY
        self.rv_actual.disabled = pred["review_status"] == "unreviewed"
        self.rv_save.disabled = False
        self._update_hint()
        safe_update(self.rv_info, self.rv_badge, self.rv_status, self.rv_actual, self.rv_save, self.rv_hint)

    def _update_hint(self) -> None:
        s = self.rv_status.value
        self.rv_hint.value = {
            "unreviewed": "Không có nhãn thật ở trạng thái này.",
            "confirmed": "Tự chọn lớp bạn xác nhận ở trên (phải trùng lớp model dự đoán).",
            "incorrect": "Chọn lớp đúng theo đánh giá chuyên môn (khác lớp model dự đoán).",
            "uncertain": "Có thể để trống nhãn thật nếu chưa đủ căn cứ.",
        }[s]

    def _on_review_status(self, e) -> None:
        unreviewed = self.rv_status.value == "unreviewed"
        self.rv_actual.disabled = unreviewed
        if unreviewed:
            self.rv_actual.value = NONE_KEY
        self._update_hint()
        safe_update(self.rv_actual, self.rv_hint)

    def _save_review(self, e) -> None:
        pred = self.current_prediction
        if not pred:
            return
        status = self.rv_status.value
        actual = None if self.rv_actual.value in (None, NONE_KEY) else int(self.rv_actual.value)
        try:
            self.db.update_prediction_review(pred["prediction_id"], status, actual)
        except ValueError as ex:
            toast(self._page, str(ex), "warn")
            return
        except Exception as ex:  # noqa: BLE001
            toast(self._page, f"Lỗi lưu: {ex}", "error")
            return
        toast(self._page, f"Đã lưu xác nhận cho dự đoán #{pred['prediction_id']}.", "ok")
        self._open_review(self.db.get_prediction(pred["prediction_id"]))
        self._page.run_thread(self._render_history)

    # ------------------------------------------------------------------
    # Lịch sử
    # ------------------------------------------------------------------
    def _render_history(self) -> None:
        try:
            preds = self.db.list_predictions(limit=12)
        except Exception:  # noqa: BLE001
            return
        if not preds:
            self.history.controls = [ft.Text("Chưa có dự đoán nào được lưu.", size=12, italic=True,
                                             color=ft.Colors.ON_SURFACE_VARIANT)]
        else:
            self.history.controls = [
                ft.Container(
                    data=p["prediction_id"], on_click=self._open_history, ink=True, border_radius=8,
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                    content=ft.Row([
                        ft.Column([
                            ft.Text(f"#{p['prediction_id']} · {p['predicted_name'] or '—'} · {fmt_num(p['top_score'], 3)}",
                                    size=12, weight=ft.FontWeight.W_600),
                            ft.Text(f"{p['created_at']} · {p['input_kind']} · run {p['run_name']}"
                                    + (f" · thật: {p['actual_name']}" if p["actual_name"] else ""),
                                    size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=1, expand=True),
                        StatusBadge(p["review_status"], compact=True),
                    ]),
                ) for p in preds
            ]
        safe_update(self.history)

    def _open_history(self, e) -> None:
        pid = e.control.data

        def worker():
            pred = self.db.get_prediction(pid)
            scores = self.db.get_prediction_scores(pid)
            if not pred:
                return
            top = scores[0] if scores else None
            self.result_title.value = f"{top['name_vi']}  ·  {top['score'] * 100:.1f}%" if top else "—"
            self.result_meta.value = (f"Dự đoán #{pid} · {pred['input_kind']}"
                                      + (f" @ {pred['frame_time_seconds']:.2f}s" if pred["frame_time_seconds"] is not None else "")
                                      + f"\n{pred['input_uri'] or ''}")
            self.result_warn.controls = []
            uri = pred["input_uri"]
            if uri and Path(uri).exists() and pred["input_kind"] == "image":
                self.preview.content = ft.Image(src=uri, fit=ft.ImageFit.CONTAIN)
            safe_update(self.result_title, self.result_meta, self.result_warn, self.preview)
            self.bars.set_scores(scores)
            self._open_review(pred)

        self._page.run_thread(worker)
