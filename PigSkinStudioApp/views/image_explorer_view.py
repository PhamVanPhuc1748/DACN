"""views/image_explorer_view.py — Kho ảnh & duyệt nhãn Ground Truth (bảng image_labels)."""
from __future__ import annotations

import os
from pathlib import Path

import flet as ft

import config
from components import fmt_int, panel, safe_update, section_title, toast
from components.status_badge import StatusBadge
from database.db_manager import IMAGE_REVIEW_STATUSES, DBManager

ALL = "__all__"


def _opt(key: str, text: str) -> ft.dropdown.Option:
    return ft.dropdown.Option(key=key, text=text)


class ImageExplorerView(ft.Row):
    def __init__(self, page: ft.Page, db: DBManager):
        super().__init__(expand=True, spacing=16, vertical_alignment=ft.CrossAxisAlignment.START)
        self._page = page
        self.db = db
        self.page_index = 0
        self.total = 0
        self.rows: list[dict] = []
        self.selected: dict | None = None
        self.image_root = Path(config.load_settings()["image_root"])

        # ---------------- Bộ lọc ----------------
        dd = dict(dense=True, width=230, border_radius=8, text_size=13)
        self.f_class = ft.Dropdown(label="Lớp bệnh", value=ALL, options=[_opt(ALL, "Tất cả")], on_change=self._on_filter, **dd)
        self.f_source = ft.Dropdown(label="Nguồn ảnh", value=ALL, options=[_opt(ALL, "Tất cả")], on_change=self._on_filter, **dd)
        self.f_status = ft.Dropdown(
            label="Trạng thái duyệt", value=ALL, on_change=self._on_filter,
            options=[_opt(ALL, "Tất cả")] + [_opt(s, config.STATUS_STYLES[s][0]) for s in IMAGE_REVIEW_STATUSES], **dd)
        self.f_split = ft.Dropdown(
            label="Split", value=ALL, on_change=self._on_filter,
            options=[_opt(ALL, "Tất cả")] + [_opt(s, s) for s in config.SPLITS], **dd)
        self.f_search = ft.TextField(label="Tìm theo đường dẫn", dense=True, width=230, border_radius=8, text_size=13,
                                     prefix_icon=ft.Icons.SEARCH, on_submit=self._on_filter)
        self.root_text = ft.Text(str(self.image_root), size=11, color=ft.Colors.ON_SURFACE_VARIANT, selectable=True)

        filters = panel(ft.Column([
            section_title("Bộ lọc", icon=ft.Icons.FILTER_ALT_OUTLINED),
            self.f_class, self.f_source, self.f_status, self.f_split, self.f_search,
            ft.TextButton("Xóa bộ lọc", icon=ft.Icons.FILTER_ALT_OFF_OUTLINED, on_click=self._reset_filters),
            ft.Divider(height=1),
            ft.Text("Thư mục ảnh gốc", size=12, weight=ft.FontWeight.W_600),
            self.root_text,
            ft.Text("Đổi thư mục gốc trong màn hình Dataset & Importer.", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
        ], spacing=12, scroll=ft.ScrollMode.AUTO), width=262)

        # ---------------- Lưới ảnh ----------------
        self.grid = ft.GridView(expand=True, max_extent=170, child_aspect_ratio=0.82, spacing=10, run_spacing=10,
                                padding=4)
        self.count_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.page_text = ft.Text("", size=12)
        self.btn_prev = ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=lambda e: self._go(-1), tooltip="Trang trước")
        self.btn_next = ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=lambda e: self._go(1), tooltip="Trang sau")
        self.loading = ft.ProgressBar(visible=False, bar_height=2)

        grid_panel = panel(ft.Column([
            ft.Row([
                ft.Column([ft.Text("Kho ảnh", size=20, weight=ft.FontWeight.W_700), self.count_text], spacing=0),
                ft.Row([self.btn_prev, self.page_text, self.btn_next], spacing=0),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            self.loading,
            self.grid,
        ], spacing=8, expand=True), expand=True, padding=12)

        # ---------------- Panel chi tiết ----------------
        self.preview = ft.InteractiveViewer(
            min_scale=1, max_scale=8, boundary_margin=ft.margin.all(40),
            content=self._placeholder("Chọn một ảnh"),
        )
        self.d_badge = StatusBadge("pending")
        self.d_class = ft.Text("—", size=16, weight=ft.FontWeight.W_700)
        self.d_info = ft.Column(spacing=6)
        self.annotator = ft.TextField(label="Người duyệt (annotator)", value=config.load_settings().get("reviewer", ""),
                                      dense=True, border_radius=8, text_size=13, prefix_icon=ft.Icons.PERSON_OUTLINE,
                                      on_blur=lambda e: config.save_settings(reviewer=self.annotator.value.strip()))
        self.review_buttons = ft.Column([
            ft.Row([
                self._review_btn("approved", "Duyệt", ft.Icons.CHECK_CIRCLE),
                self._review_btn("needs_review", "Cần xem lại", ft.Icons.HELP_OUTLINE),
            ], spacing=8),
            ft.Row([
                self._review_btn("rejected", "Loại bỏ", ft.Icons.CANCEL),
                self._review_btn("pending", "Đặt lại", ft.Icons.UNDO),
            ], spacing=8),
        ], spacing=8)

        self.detail = panel(ft.Column([
            ft.Stack([
                ft.Container(self.preview, height=290, border_radius=10, clip_behavior=ft.ClipBehavior.HARD_EDGE,
                             bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                ft.Container(
                    ft.IconButton(ft.Icons.OPEN_IN_FULL, tooltip="Phóng to để soi tổn thương", on_click=self._open_zoom,
                                  icon_size=18, bgcolor=ft.Colors.with_opacity(0.6, ft.Colors.SURFACE)),
                    right=6, top=6),
            ]),
            ft.Text("Cuộn chuột / pinch để zoom · kéo để di chuyển", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Row([self.d_class, self.d_badge], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
            self.d_info,
            ft.Divider(height=1),
            section_title("Cập nhật nhãn ground truth", "Ghi vào image_labels.review_status"),
            self.annotator,
            self.review_buttons,
        ], spacing=10, scroll=ft.ScrollMode.AUTO), width=370)

        self.controls = [filters, grid_panel, self.detail]
        self._set_review_enabled(False)

    # ------------------------------------------------------------------
    # Helpers UI
    # ------------------------------------------------------------------
    def _review_btn(self, status: str, text: str, icon: str) -> ft.Control:
        color = config.STATUS_STYLES[status][1]
        return ft.OutlinedButton(
            text, icon=icon, expand=True, data=status, on_click=self._on_review,
            style=ft.ButtonStyle(color=color, side=ft.BorderSide(1, ft.Colors.with_opacity(0.6, color)),
                                 shape=ft.RoundedRectangleBorder(radius=8)),
        )

    def _set_review_enabled(self, enabled: bool) -> None:
        for row in self.review_buttons.controls:
            for b in row.controls:
                b.disabled = not enabled

    @staticmethod
    def _placeholder(text: str, icon: str = ft.Icons.IMAGE_OUTLINED) -> ft.Control:
        return ft.Container(
            alignment=ft.alignment.center, expand=True,
            content=ft.Column([ft.Icon(icon, size=36, color=ft.Colors.ON_SURFACE_VARIANT),
                               ft.Text(text, size=11, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER)],
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER,
                              spacing=4),
        )

    def _abs_path(self, row: dict) -> Path:
        return self.image_root / row["relative_path"]

    def _image_or_placeholder(self, row: dict, fit=ft.ImageFit.COVER, cache_width: int | None = None) -> ft.Control:
        p = self._abs_path(row)
        if p.exists():
            return ft.Image(src=str(p), fit=fit, cache_width=cache_width, gapless_playback=True,
                            error_content=self._placeholder("Lỗi đọc ảnh", ft.Icons.BROKEN_IMAGE_OUTLINED))
        return self._placeholder(f"Không có file\n{row.get('class_code') or ''}", ft.Icons.IMAGE_NOT_SUPPORTED)

    # ------------------------------------------------------------------
    # Load dữ liệu
    # ------------------------------------------------------------------
    def load(self) -> None:
        self.image_root = Path(config.load_settings()["image_root"])
        self.root_text.value = str(self.image_root)
        self._page.run_thread(self._load_filters_then_images)

    def _load_filters_then_images(self) -> None:
        try:
            classes = self.db.get_classes()
            sources = self.db.get_image_sources()
        except Exception as e:  # noqa: BLE001
            toast(self._page, f"Lỗi đọc CSDL: {e}", "error")
            return
        keep_c, keep_s = self.f_class.value, self.f_source.value
        self.f_class.options = [_opt(ALL, "Tất cả")] + [_opt(str(c["class_id"]), f"{c['name_vi']} · {c['code']}") for c in classes]
        self.f_source.options = [_opt(ALL, "Tất cả")] + [_opt(s, s) for s in sources]
        self.f_class.value = keep_c if keep_c in {o.key for o in self.f_class.options} else ALL
        self.f_source.value = keep_s if keep_s in {o.key for o in self.f_source.options} else ALL
        safe_update(self.f_class, self.f_source, self.root_text)
        self._load_images()

    def _filters(self) -> dict:
        v = lambda dd: None if dd.value in (None, ALL) else dd.value  # noqa: E731
        return {
            "dataset_id": self.db.get_latest_dataset_id(),
            "class_id": int(v(self.f_class)) if v(self.f_class) else None,
            "source": v(self.f_source),
            "review_status": v(self.f_status),
            "split": v(self.f_split),
            "search": (self.f_search.value or "").strip() or None,
        }

    def _load_images(self) -> None:
        self.loading.visible = True
        safe_update(self.loading)
        try:
            self.rows, self.total = self.db.list_images(**self._filters(), limit=config.IMAGES_PER_PAGE,
                                                        offset=self.page_index * config.IMAGES_PER_PAGE)
        except Exception as e:  # noqa: BLE001
            self.loading.visible = False
            safe_update(self.loading)
            toast(self._page, f"Lỗi truy vấn ảnh: {e}", "error")
            return
        n_pages = max(1, -(-self.total // config.IMAGES_PER_PAGE))
        self.page_index = min(self.page_index, n_pages - 1)
        self.count_text.value = f"{fmt_int(self.total)} ảnh khớp bộ lọc"
        self.page_text.value = f"Trang {self.page_index + 1}/{n_pages}"
        self.btn_prev.disabled = self.page_index == 0
        self.btn_next.disabled = self.page_index >= n_pages - 1
        self.grid.controls = [self._tile(r) for r in self.rows]
        if not self.rows:
            self.grid.controls = [self._placeholder("Không có ảnh nào khớp bộ lọc", ft.Icons.SEARCH_OFF)]
        self.loading.visible = False
        safe_update(self)

    def _tile(self, row: dict) -> ft.Control:
        selected = self.selected is not None and self.selected["image_label_id"] == row["image_label_id"] \
            and self.selected["image_id"] == row["image_id"]
        color = config.STATUS_STYLES.get(row.get("review_status") or "pending", ("", "#8A94A0"))[1]
        return ft.Container(
            data=row,
            on_click=self._on_tile_click,
            border_radius=10,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
            border=ft.border.all(2 if selected else 1, ft.Colors.PRIMARY if selected else ft.Colors.OUTLINE_VARIANT),
            ink=True,
            content=ft.Column([
                ft.Container(self._image_or_placeholder(row, cache_width=240), expand=True),
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=8, vertical=6),
                    content=ft.Column([
                        ft.Row([
                            ft.Container(width=8, height=8, border_radius=4, bgcolor=color,
                                         tooltip=config.STATUS_STYLES.get(row.get("review_status") or "", ("—",))[0]),
                            ft.Text(row.get("class_name") or "—", size=11, weight=ft.FontWeight.W_600,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                        ], spacing=6),
                        ft.Text(f"{row.get('split') or '—'} · #{row['image_id']}", size=10,
                                color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=2),
                ),
            ], spacing=0),
        )

    # ------------------------------------------------------------------
    # Sự kiện
    # ------------------------------------------------------------------
    def _on_filter(self, e=None) -> None:
        self.page_index = 0
        self._page.run_thread(self._load_images)

    def _reset_filters(self, e) -> None:
        for dd in (self.f_class, self.f_source, self.f_status, self.f_split):
            dd.value = ALL
        self.f_search.value = ""
        safe_update(self)
        self._on_filter()

    def _go(self, delta: int) -> None:
        self.page_index = max(0, self.page_index + delta)
        self._page.run_thread(self._load_images)

    def _on_tile_click(self, e: ft.ControlEvent) -> None:
        self.selected = e.control.data
        self._show_detail()
        for t in self.grid.controls:
            if isinstance(t.data, dict):
                is_sel = t.data["image_id"] == self.selected["image_id"]
                t.border = ft.border.all(2 if is_sel else 1, ft.Colors.PRIMARY if is_sel else ft.Colors.OUTLINE_VARIANT)
        safe_update(self.grid)

    def _show_detail(self) -> None:
        r = self.selected
        if not r:
            return
        self.preview.content = self._image_or_placeholder(r, fit=ft.ImageFit.CONTAIN)
        self.d_class.value = f"{r.get('class_name') or '—'}"
        self.d_badge.set_status(r.get("review_status"))

        def info(label: str, value, mono: bool = False) -> ft.Control:
            return ft.Column([
                ft.Text(label, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text("—" if value in (None, "") else str(value), size=12, selectable=True,
                        font_family=config.MONO_FONT if mono else None),
            ], spacing=1)

        p = self._abs_path(r)
        self.d_info.controls = [
            info("relative_path", r["relative_path"], True),
            info("sha256", r.get("sha256"), True),
            ft.Row([info("Mã lớp", r.get("class_code"), True), info("Split", r.get("split")),
                    info("Kích thước", f"{r['width']}×{r['height']}" if r.get("width") else None)], spacing=18),
            ft.Row([info("Nguồn", r.get("source")), info("group_id", r.get("group_id"), True)], spacing=18),
            ft.Row([info("Annotator", r.get("annotator")), info("Duyệt lúc", r.get("reviewed_at"))], spacing=18),
            ft.Text("✓ File tồn tại" if p.exists() else f"✗ Không tìm thấy file tại {p}", size=11,
                    color="#2E9E6A" if p.exists() else "#D9534F"),
        ]
        self._set_review_enabled(r.get("image_label_id") is not None)
        safe_update(self.detail)

    def _open_zoom(self, e) -> None:
        if not self.selected:
            return
        dlg = ft.AlertDialog(
            title=ft.Text(self.selected["relative_path"], size=13, font_family=config.MONO_FONT),
            content=ft.Container(
                width=900, height=640, bgcolor=ft.Colors.BLACK, border_radius=8,
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                content=ft.InteractiveViewer(min_scale=1, max_scale=12, boundary_margin=ft.margin.all(80),
                                             content=self._image_or_placeholder(self.selected, fit=ft.ImageFit.CONTAIN)),
            ),
            actions=[ft.TextButton("Đóng", on_click=lambda ev: self._page.close(dlg))],
        )
        self._page.open(dlg)

    def _on_review(self, e: ft.ControlEvent) -> None:
        status = e.control.data
        r = self.selected
        if not r or r.get("image_label_id") is None:
            return
        annotator = (self.annotator.value or "").strip()
        if status in ("approved", "rejected") and not annotator:
            toast(self._page, "Nhập tên người duyệt trước khi duyệt/loại bỏ nhãn.", "warn")
            self.annotator.focus()
            return

        def do_update(ev=None):
            if ev is not None:
                self._page.close(confirm)
            try:
                self.db.update_image_label_status(r["image_label_id"], status, annotator)
                config.save_settings(reviewer=annotator)
            except Exception as ex:  # noqa: BLE001
                toast(self._page, str(ex), "error")
                return
            toast(self._page, f"Ảnh #{r['image_id']} → {config.STATUS_STYLES[status][0]}", "ok")
            selected_id = r["image_id"]
            self._page.run_thread(self._reload_keep_selection, selected_id)

        if status == "approved":
            confirm = ft.AlertDialog(
                modal=True,
                title=ft.Text("Xác nhận duyệt nhãn"),
                content=ft.Text(f"Bạn ({annotator}) xác nhận ảnh #{r['image_id']} thuộc lớp “{r.get('class_name')}” "
                                f"sau khi đã xem kỹ ảnh?\nNhãn 'approved' sẽ được dùng làm ground truth."),
                actions=[ft.TextButton("Hủy", on_click=lambda ev: self._page.close(confirm)),
                         ft.FilledButton("Duyệt", icon=ft.Icons.CHECK, on_click=do_update)],
            )
            self._page.open(confirm)
        else:
            do_update()

    def _reload_keep_selection(self, image_id: int) -> None:
        self._load_images()
        match = next((x for x in self.rows if x["image_id"] == image_id), None)
        if match:
            self.selected = match
            self._show_detail()
