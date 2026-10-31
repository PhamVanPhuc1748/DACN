"""views/training_runs_view.py — Lịch sử huấn luyện, chỉ số từng lớp và cấu hình run."""
from __future__ import annotations

import json

import flet as ft

import config
from components import fmt_num, panel, safe_update, section_title, toast
from components.status_badge import StatusBadge
from database.db_manager import DBManager

SORT_COLUMNS = [  # (cột CSDL, tiêu đề, numeric)
    ("run_name", "Run", False),
    ("best_epoch", "Best epoch", True),
    ("best_val_macro_f1", "Val macro-F1", True),
    ("test_macro_f1", "Test macro-F1", True),
    ("test_accuracy", "Test accuracy", True),
    ("started_at", "Bắt đầu", False),
]

KEY_PARAMS = [  # (nhãn, các khóa có thể có trong config_json)
    ("Kiến trúc", ("architecture", "arch", "model", "model_name")),
    ("Pretrained", ("pretrained", "weights")),
    ("Chế độ nhãn", ("label_mode",)),
    ("Image size", ("image_size", "img_size", "input_size")),
    ("Epochs", ("epochs", "num_epochs")),
    ("Head epochs", ("head_epochs",)),
    ("Batch size", ("batch_size",)),
    ("Learning rate", ("learning_rate", "lr")),
    ("Weight decay", ("weight_decay",)),
    ("Seed", ("seed",)),
    ("Device", ("device",)),
    ("PyTorch", ("torch_version",)),
]


def _lookup(d, keys):
    if isinstance(d, dict):
        for k, v in d.items():
            if k in keys:
                return v
        for v in d.values():
            r = _lookup(v, keys)
            if r is not None:
                return r
    return None


class TrainingRunsView(ft.Column):
    def __init__(self, page: ft.Page, db: DBManager):
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=16)
        self._page = page
        self.db = db
        self.sort_col = "best_val_macro_f1"
        self.sort_desc = True
        self.selected_run: dict | None = None
        self.metric_split = "val"
        self.runs: list[dict] = []

        self.f_status = ft.Dropdown(
            label="Trạng thái", value="", dense=True, width=170, border_radius=8, text_size=13,
            options=[ft.dropdown.Option("", "Tất cả")] + [ft.dropdown.Option(s, config.STATUS_STYLES[s][0])
                                                          for s in ("completed", "running", "failed", "cancelled")],
            on_change=lambda e: self.load(),
        )
        self.f_sort = ft.Dropdown(
            label="Sắp xếp theo", value=self.sort_col, dense=True, width=200, border_radius=8, text_size=13,
            options=[ft.dropdown.Option(c, t) for c, t, n in SORT_COLUMNS if c != "run_name"],
            on_change=self._on_sort_dropdown,
        )
        self.btn_dir = ft.IconButton(ft.Icons.ARROW_DOWNWARD, tooltip="Giảm dần", on_click=self._toggle_dir)

        self.runs_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(t, weight=ft.FontWeight.W_600), numeric=n,
                                   on_sort=self._on_sort_header) for c, t, n in SORT_COLUMNS]
                    + [ft.DataColumn(ft.Text("Model", weight=ft.FontWeight.W_600)),
                       ft.DataColumn(ft.Text("Trạng thái", weight=ft.FontWeight.W_600)),
                       ft.DataColumn(ft.Text("Dataset", weight=ft.FontWeight.W_600))],
            rows=[], column_spacing=22, heading_row_height=42, data_row_min_height=44,
            sort_column_index=2, sort_ascending=False, show_checkbox_column=False,
        )

        # Chi tiết
        self.detail_title = ft.Text("Chọn một run để xem chỉ số từng lớp", size=16, weight=ft.FontWeight.W_600)
        self.split_switch = ft.SegmentedButton(
            selected={"val"}, allow_multiple_selection=False, show_selected_icon=False,
            segments=[ft.Segment(value="val", label=ft.Text("Validation")),
                      ft.Segment(value="test", label=ft.Text("Test"))],
            on_change=self._on_split_change,
        )
        self.metrics_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(t, weight=ft.FontWeight.W_600), numeric=n) for t, n in (
                ("Lớp", False), ("Precision", True), ("Recall", True), ("F1", True), ("Support", True), ("", False))],
            rows=[], column_spacing=20, heading_row_height=40, data_row_min_height=38, data_row_max_height=44,
        )
        self.weak_summary = ft.Text("", size=12)
        self.params_grid = ft.ResponsiveRow(spacing=10, run_spacing=10)
        self.config_text = ft.Text("", size=12, font_family=config.MONO_FONT, selectable=True)
        self.config_box = ft.Container(
            visible=False, height=320, padding=12, border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            content=ft.Column([self.config_text], scroll=ft.ScrollMode.AUTO),
        )
        self.btn_toggle_json = ft.TextButton("Xem config_json đầy đủ", icon=ft.Icons.DATA_OBJECT,
                                             on_click=self._toggle_json)
        self.meta_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, selectable=True)

        legend = ft.Row([
            ft.Container(width=14, height=14, border_radius=3, bgcolor=ft.Colors.with_opacity(0.28, config.DANGER_BG)),
            ft.Text(f"F1 và Recall < {config.WEAK_METRIC_THRESHOLD}", size=11),
            ft.Container(width=14, height=14, border_radius=3, bgcolor=ft.Colors.with_opacity(0.22, config.WARN_BG)),
            ft.Text(f"F1 hoặc Recall < {config.WEAK_METRIC_THRESHOLD}", size=11),
        ], spacing=6, wrap=True)

        metrics_panel = panel(ft.Column([
            ft.Row([section_title("Chỉ số từng lớp", "run_class_metrics", ft.Icons.TABLE_CHART_OUTLINED),
                    self.split_switch], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
            legend,
            ft.Row([self.metrics_table], scroll=ft.ScrollMode.AUTO),
            self.weak_summary,
        ], spacing=10))
        metrics_panel.col = {"xs": 12, "xl": 7}

        config_panel = panel(ft.Column([
            ft.Row([section_title("Cấu hình huấn luyện", "training_runs.config_json", ft.Icons.TUNE),
                    ft.IconButton(ft.Icons.CONTENT_COPY, tooltip="Sao chép JSON", on_click=self._copy_json)],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            self.meta_text,
            self.params_grid,
            self.btn_toggle_json,
            self.config_box,
        ], spacing=10))
        config_panel.col = {"xs": 12, "xl": 5}

        self.controls = [
            ft.Row([
                ft.Column([ft.Text("Lịch sử huấn luyện", size=24, weight=ft.FontWeight.W_700),
                           ft.Text("Không chọn model chỉ bằng accuracy — xem macro-F1, recall từng lớp và confusion matrix.",
                                   size=12, color=ft.Colors.ON_SURFACE_VARIANT)], spacing=2, expand=True),
                self.f_status, self.f_sort, self.btn_dir,
                ft.IconButton(ft.Icons.REFRESH, tooltip="Làm mới", on_click=lambda e: self.load()),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, wrap=True),
            panel(ft.Row([self.runs_table], scroll=ft.ScrollMode.AUTO)),
            self.detail_title,
            ft.ResponsiveRow([metrics_panel, config_panel], spacing=16, run_spacing=16),
        ]

    # ------------------------------------------------------------------
    def load(self) -> None:
        self._page.run_thread(self._load_worker)

    def _load_worker(self) -> None:
        try:
            self.runs = self.db.list_runs(self.sort_col, self.sort_desc, self.f_status.value or None)
        except Exception as e:  # noqa: BLE001
            toast(self._page, f"Lỗi đọc CSDL: {e}", "error")
            return
        ids = {r["run_id"] for r in self.runs}
        if self.runs and (not self.selected_run or self.selected_run["run_id"] not in ids):
            self.selected_run = self.runs[0]
        elif not self.runs:
            self.selected_run = None
        self._render_runs()
        self._render_detail()

    def _render_runs(self) -> None:
        sel = self.selected_run["run_id"] if self.selected_run else None
        best_val = max((r["best_val_macro_f1"] or 0 for r in self.runs), default=None)
        self.runs_table.sort_column_index = next(i for i, (c, _, _) in enumerate(SORT_COLUMNS) if c == self.sort_col) \
            if self.sort_col in [c for c, _, _ in SORT_COLUMNS] else None
        self.runs_table.sort_ascending = not self.sort_desc
        self.runs_table.rows = []
        for r in self.runs:
            is_best = r["best_val_macro_f1"] is not None and r["best_val_macro_f1"] == best_val
            self.runs_table.rows.append(ft.DataRow(
                selected=r["run_id"] == sel,
                on_select_changed=lambda e, run=r: self._select(run),
                cells=[
                    ft.DataCell(ft.Row([ft.Text(r["run_name"], font_family=config.MONO_FONT, weight=ft.FontWeight.W_600),
                                        ft.Icon(ft.Icons.STAR, size=14, color="#E0A030", tooltip="Best val macro-F1")
                                        if is_best else ft.Container()], spacing=6)),
                    ft.DataCell(ft.Text("—" if r["best_epoch"] is None else str(r["best_epoch"]))),
                    ft.DataCell(ft.Text(fmt_num(r["best_val_macro_f1"]), weight=ft.FontWeight.W_600)),
                    ft.DataCell(ft.Text(fmt_num(r["test_macro_f1"]))),
                    ft.DataCell(ft.Text(fmt_num(r["test_accuracy"]))),
                    ft.DataCell(ft.Text(r["started_at"] or "—", size=12)),
                    ft.DataCell(ft.Text(r["model_code"])),
                    ft.DataCell(StatusBadge(r["status"], compact=True)),
                    ft.DataCell(ft.Text(f"{r['dataset_name']} · {r['dataset_version']}", size=12)),
                ],
            ))
        if not self.runs:
            self.runs_table.rows = [ft.DataRow(cells=[ft.DataCell(ft.Text("Chưa có training run.", italic=True))]
                                               + [ft.DataCell(ft.Text("")) for _ in range(8)])]
        safe_update(self.runs_table)

    def _render_detail(self) -> None:
        r = self.selected_run
        if not r:
            self.detail_title.value = "Chưa có run để hiển thị"
            self.metrics_table.rows = []
            safe_update(self)
            return
        self.detail_title.value = f"Run {r['run_name']} · {r['model_code']}"
        rows = self.db.get_run_metrics(r["run_id"], self.metric_split)
        thr = config.WEAK_METRIC_THRESHOLD
        weak = []
        self.metrics_table.rows = []
        for m in rows:
            f1, rec = m["f1"], m["recall"]
            low_f1 = f1 is not None and f1 < thr
            low_rec = rec is not None and rec < thr
            if low_f1 and low_rec:
                bg = ft.Colors.with_opacity(0.28, config.DANGER_BG)
            elif low_f1 or low_rec:
                bg = ft.Colors.with_opacity(0.22, config.WARN_BG)
            else:
                bg = None
            if low_f1 or low_rec:
                weak.append(m["name_vi"])

            def cell(v, low=False):
                return ft.DataCell(ft.Text(fmt_num(v), font_family=config.MONO_FONT,
                                           weight=ft.FontWeight.W_700 if low else None,
                                           color=config.DANGER_BG if low else None))

            self.metrics_table.rows.append(ft.DataRow(color=bg, cells=[
                ft.DataCell(ft.Column([ft.Text(m["name_vi"], size=13),
                                       ft.Text(m["code"], size=10, color=ft.Colors.ON_SURFACE_VARIANT,
                                               font_family=config.MONO_FONT)], spacing=0)),
                cell(m["precision"]), cell(rec, low_rec), cell(f1, low_f1),
                ft.DataCell(ft.Text("—" if m["support"] is None else str(m["support"]))),
                ft.DataCell(ft.Icon(ft.Icons.WARNING_AMBER, size=16, color=config.WARN_BG,
                                    tooltip="Lớp nhận diện kém") if (low_f1 or low_rec) else ft.Container()),
            ]))
        f1s = [m["f1"] for m in rows if m["f1"] is not None]
        if not f1s:
            self.weak_summary.value = f"Chưa có chỉ số từng lớp cho tập {self.metric_split}."
            self.weak_summary.color = ft.Colors.ON_SURFACE_VARIANT
        else:
            macro = sum(f1s) / len(f1s)
            self.weak_summary.value = (f"Macro-F1 tính lại từ bảng: {macro:.4f}. "
                                       + (f"{len(weak)} lớp cần cải thiện: {', '.join(weak)}." if weak
                                          else "Không có lớp nào dưới ngưỡng."))
            self.weak_summary.color = config.WARN_BG if weak else "#2E9E6A"

        try:
            cfg = json.loads(r["config_json"] or "{}")
        except json.JSONDecodeError:
            cfg = {"_raw": r["config_json"]}
        self.config_text.value = json.dumps(cfg, ensure_ascii=False, indent=2)
        self.meta_text.value = (f"checkpoint: {r['checkpoint_path'] or '—'}\n"
                                f"{r['started_at'] or '—'} → {r['finished_at'] or '—'}"
                                + (f"\nGhi chú: {r['notes']}" if r.get("notes") else ""))
        tiles = []
        for label, keys in KEY_PARAMS:
            v = _lookup(cfg, keys)
            if v is None:
                continue
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)
            tiles.append(ft.Container(
                col={"xs": 6, "md": 4}, padding=10, border_radius=8,
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                content=ft.Column([ft.Text(label, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                   ft.Text(str(v), size=12, weight=ft.FontWeight.W_600, max_lines=2,
                                           overflow=ft.TextOverflow.ELLIPSIS, tooltip=str(v))], spacing=2),
            ))
        self.params_grid.controls = tiles or [ft.Text("Không tìm thấy tham số chuẩn trong config_json.", size=12)]
        safe_update(self)

    # ------------------------------------------------------------------
    def _select(self, run: dict) -> None:
        self.selected_run = run
        for row in self.runs_table.rows:
            row.selected = False
        self._page.run_thread(lambda: (self._render_runs(), self._render_detail()))

    def _on_split_change(self, e) -> None:
        self.metric_split = next(iter(e.control.selected))
        self._page.run_thread(self._render_detail)

    def _on_sort_dropdown(self, e) -> None:
        self.sort_col = self.f_sort.value
        self.load()

    def _on_sort_header(self, e: ft.DataColumnSortEvent) -> None:
        self.sort_col = SORT_COLUMNS[e.column_index][0]
        self.sort_desc = not e.ascending
        if self.sort_col in {o.key for o in self.f_sort.options}:
            self.f_sort.value = self.sort_col
        self.btn_dir.icon = ft.Icons.ARROW_DOWNWARD if self.sort_desc else ft.Icons.ARROW_UPWARD
        safe_update(self.f_sort, self.btn_dir)
        self.load()

    def _toggle_dir(self, e) -> None:
        self.sort_desc = not self.sort_desc
        self.btn_dir.icon = ft.Icons.ARROW_DOWNWARD if self.sort_desc else ft.Icons.ARROW_UPWARD
        self.btn_dir.tooltip = "Giảm dần" if self.sort_desc else "Tăng dần"
        safe_update(self.btn_dir)
        self.load()

    def _toggle_json(self, e) -> None:
        self.config_box.visible = not self.config_box.visible
        self.btn_toggle_json.text = "Ẩn config_json" if self.config_box.visible else "Xem config_json đầy đủ"
        safe_update(self.config_box, self.btn_toggle_json)

    def _copy_json(self, e) -> None:
        if self.config_text.value:
            self._page.set_clipboard(self.config_text.value)
            toast(self._page, "Đã sao chép config_json.", "ok")
