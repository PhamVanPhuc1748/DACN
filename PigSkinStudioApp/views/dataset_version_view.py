"""views/dataset_version_view.py — Phiên bản dataset, phân bổ lớp × split và Importer 6 bước."""
from __future__ import annotations

from pathlib import Path

import flet as ft

import config
from components import fmt_int, panel, safe_update, section_title, toast
from components.status_badge import StatusBadge
from database.db_manager import DBManager
from database.seed_importer import ImportOptions, run_import


class DatasetVersionView(ft.Column):
    def __init__(self, page: ft.Page, db: DBManager, on_data_changed=None):
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=16)
        self._page = page
        self.db = db
        self.on_data_changed = on_data_changed
        self.selected_dataset_id: int | None = None
        self._pick_target: ft.TextField | None = None
        self._running = False

        # FilePicker dùng chung cho mọi ô đường dẫn
        self.picker = ft.FilePicker(on_result=self._on_pick)
        page.overlay.append(self.picker)

        # ---------------- Bảng phiên bản ----------------
        self.versions_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(t, weight=ft.FontWeight.W_600), numeric=n) for t, n in (
                ("Tên", False), ("Version", False), ("Ảnh", True), ("Run", True), ("Seed", True),
                ("manifest_path", False), ("manifest_sha256", False), ("Tạo lúc", False))],
            rows=[], column_spacing=20, heading_row_height=40, data_row_min_height=44, show_checkbox_column=False,
        )

        # ---------------- Biểu đồ ----------------
        self.chart = ft.BarChart(
            bar_groups=[], max_y=10, interactive=True, expand=True,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            horizontal_grid_lines=ft.ChartGridLines(color=ft.Colors.OUTLINE_VARIANT, width=1, dash_pattern=[3, 3]),
            left_axis=ft.ChartAxis(labels_size=44, title=ft.Text("Số ảnh", size=11), title_size=18),
            bottom_axis=ft.ChartAxis(labels_size=56),
            tooltip_bgcolor=ft.Colors.with_opacity(0.92, ft.Colors.SURFACE),
        )
        self.chart_title = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.class_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(t, weight=ft.FontWeight.W_600), numeric=n) for t, n in (
                ("Lớp", False), ("train", True), ("val", True), ("test", True), ("Tổng", True))],
            rows=[], column_spacing=18, heading_row_height=36, data_row_min_height=34, data_row_max_height=38,
        )

        # ---------------- Importer ----------------
        s = config.load_settings()
        tf = dict(dense=True, border_radius=8, text_size=12, expand=True, text_style=ft.TextStyle(font_family=config.MONO_FONT))
        self.in_manifest = ft.TextField(label="manifest.csv", value=str(config.DEFAULT_MANIFEST), **tf)
        self.in_classes = ft.TextField(label="classes.json", value=str(config.DEFAULT_CLASSES), **tf)
        self.in_root = ft.TextField(label="Thư mục ảnh gốc (ghép với relative_path)", value=s["image_root"], **tf)
        self.in_run = ft.TextField(label="Thư mục training run (tùy chọn)", value=str(config.DEFAULT_RUN_DIR), **tf)
        self.cb_hash = ft.Checkbox(label="Tính SHA-256 và kích thước ảnh (chậm hơn, nên bật)", value=True)
        self.cb_reset = ft.Checkbox(label="Xóa toàn bộ dữ liệu hiện có (kể cả dữ liệu mẫu) trước khi nạp", value=False)
        self.btn_import = ft.FilledButton("Chạy nạp dữ liệu", icon=ft.Icons.PLAY_ARROW, on_click=self._start_import,
                                          style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
        self.btn_save_root = ft.TextButton("Lưu thư mục ảnh gốc", icon=ft.Icons.SAVE_OUTLINED, on_click=self._save_root)
        self.progress = ft.ProgressBar(value=0, bar_height=8, border_radius=4)
        self.progress_text = ft.Text("Sẵn sàng.", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.log = ft.ListView(height=150, spacing=2, auto_scroll=True)

        def path_row(field: ft.TextField, mode: str, exts: list[str] | None = None) -> ft.Control:
            def pick(e):
                self._pick_target = field
                if mode == "dir":
                    self.picker.get_directory_path(dialog_title=field.label)
                else:
                    self.picker.pick_files(dialog_title=field.label, allow_multiple=False,
                                           allowed_extensions=exts, file_type=ft.FilePickerFileType.CUSTOM)
            return ft.Row([field, ft.IconButton(ft.Icons.FOLDER_OPEN if mode == "dir" else ft.Icons.UPLOAD_FILE,
                                                tooltip="Chọn…", on_click=pick)], spacing=4)

        importer = panel(ft.Column([
            section_title("Importer 6 bước", "classes.json → dataset_versions → images/items/labels → training_runs → "
                                             "run_class_metrics → đối chiếu manifest", ft.Icons.UPLOAD_FILE),
            path_row(self.in_manifest, "file", ["csv"]),
            path_row(self.in_classes, "file", ["json"]),
            path_row(self.in_root, "dir"),
            path_row(self.in_run, "dir"),
            ft.Row([self.cb_hash], wrap=True),
            ft.Row([self.cb_reset], wrap=True),
            ft.Container(
                content=ft.Row([ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.PRIMARY),
                                ft.Text("Nhãn từ manifest luôn vào trạng thái 'pending'. Nhãn đã được người duyệt trước đó "
                                        "được giữ nguyên. 'valid' được đổi thành 'val'.", size=11, expand=True)],
                               spacing=8),
                padding=10, border_radius=8, bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
            ),
            ft.Row([self.btn_import, self.btn_save_root], spacing=12),
            self.progress,
            self.progress_text,
            ft.Container(self.log, border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=8, padding=8),
        ], spacing=10))

        legend = ft.Row([
            ft.Row([ft.Container(width=12, height=12, border_radius=3, bgcolor=config.SPLIT_COLORS[s_]),
                    ft.Text(s_, size=12)], spacing=6, tight=True) for s_ in config.SPLITS
        ], spacing=16)

        self.controls = [
            ft.Row([
                ft.Column([ft.Text("Phiên bản Dataset & Importer", size=24, weight=ft.FontWeight.W_700),
                           ft.Text("Bảng dataset_versions · bấm vào một dòng để xem phân bổ lớp.", size=12,
                                   color=ft.Colors.ON_SURFACE_VARIANT)], spacing=2, expand=True),
                ft.OutlinedButton("Làm mới", icon=ft.Icons.REFRESH, on_click=lambda e: self.load()),
            ]),
            panel(ft.Row([self.versions_table], scroll=ft.ScrollMode.AUTO)),
            ft.ResponsiveRow([
                self._with_col(panel(ft.Column([
                    ft.Row([section_title("Phân bổ ảnh theo lớp × split", icon=ft.Icons.BAR_CHART), legend],
                           alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
                    self.chart_title,
                    ft.Container(self.chart, height=340),
                ], spacing=8)), {"xs": 12, "xl": 8}),
                self._with_col(panel(ft.Column([section_title("Bảng số liệu"),
                                                ft.Column([self.class_table], scroll=ft.ScrollMode.AUTO, height=380)],
                                               spacing=8)), {"xs": 12, "xl": 4}),
            ], spacing=16, run_spacing=16),
            importer,
        ]

    @staticmethod
    def _with_col(ctrl: ft.Control, col: dict) -> ft.Control:
        ctrl.col = col
        return ctrl

    # ------------------------------------------------------------------
    def load(self) -> None:
        self._page.run_thread(self._load_worker)

    def _load_worker(self) -> None:
        try:
            versions = self.db.get_dataset_versions()
        except Exception as e:  # noqa: BLE001
            toast(self._page, f"Lỗi đọc CSDL: {e}", "error")
            return
        if versions and self.selected_dataset_id not in {v["dataset_id"] for v in versions}:
            self.selected_dataset_id = versions[0]["dataset_id"]
        self.versions_table.rows = [
            ft.DataRow(
                selected=v["dataset_id"] == self.selected_dataset_id,
                on_select_changed=lambda e, did=v["dataset_id"]: self._select(did),
                cells=[
                    ft.DataCell(ft.Row([ft.Text(v["name"], weight=ft.FontWeight.W_600),
                                        StatusBadge("mock", compact=True) if self.db.parse_notes(v["notes"]).get("mock")
                                        else ft.Container()], spacing=8)),
                    ft.DataCell(ft.Text(v["version"])),
                    ft.DataCell(ft.Text(fmt_int(v["n_items"]))),
                    ft.DataCell(ft.Text(str(v["n_runs"]))),
                    ft.DataCell(ft.Text("—" if v["seed"] is None else str(v["seed"]))),
                    ft.DataCell(ft.Text(v["manifest_path"], size=11, font_family=config.MONO_FONT,
                                        tooltip=v["manifest_path"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                        width=260)),
                    ft.DataCell(ft.Text((v["manifest_sha256"] or "—")[:16] + ("…" if v["manifest_sha256"] else ""),
                                        size=11, font_family=config.MONO_FONT, tooltip=v["manifest_sha256"],
                                        selectable=True)),
                    ft.DataCell(ft.Text(v["created_at"], size=12)),
                ],
            )
            for v in versions
        ]
        safe_update(self.versions_table)
        self._render_distribution()

    def _select(self, dataset_id: int) -> None:
        self.selected_dataset_id = dataset_id
        for r in self.versions_table.rows:
            r.selected = False
        safe_update(self.versions_table)
        self._page.run_thread(self._load_worker)

    def _render_distribution(self) -> None:
        if not self.selected_dataset_id:
            self.chart.bar_groups = []
            self.chart_title.value = "Chưa có phiên bản dataset."
            safe_update(self)
            return
        dist = self.db.class_split_distribution(self.selected_dataset_id)
        max_v = max([max(d["train"], d["val"], d["test"]) for d in dist] or [10])
        self.chart.max_y = int(max_v * 1.15) + 1
        self.chart.bar_groups = [
            ft.BarChartGroup(
                x=i, bars_space=3,
                bar_rods=[
                    ft.BarChartRod(from_y=0, to_y=d[s], width=11, color=config.SPLIT_COLORS[s],
                                   border_radius=ft.border_radius.only(top_left=3, top_right=3),
                                   tooltip=f"{d['name_vi']}\n{s}: {d[s]}")
                    for s in config.SPLITS
                ],
            )
            for i, d in enumerate(dist)
        ]
        self.chart.bottom_axis.labels = [
            ft.ChartAxisLabel(value=i, label=ft.Container(
                ft.Text(d["code"][:12], size=10, text_align=ft.TextAlign.CENTER, tooltip=d["name_vi"]),
                padding=ft.padding.only(top=6), width=70, rotate=ft.Rotate(-0.45)))
            for i, d in enumerate(dist)
        ]
        step = max(10, round(max_v / 5, -1))
        self.chart.left_axis.labels = [ft.ChartAxisLabel(value=v, label=ft.Text(str(v), size=10))
                                       for v in range(0, self.chart.max_y + 1, int(step))]
        totals = {s: sum(d[s] for d in dist) for s in config.SPLITS}
        self.chart_title.value = " · ".join(f"{s}: {fmt_int(totals[s])}" for s in config.SPLITS) + \
            f" · Tổng {fmt_int(sum(totals.values()))}"
        self.class_table.rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(d["name_vi"], size=12, tooltip=d["code"])),
                *[ft.DataCell(ft.Text(str(d[s]), size=12)) for s in config.SPLITS],
                ft.DataCell(ft.Text(str(d["train"] + d["val"] + d["test"]), size=12, weight=ft.FontWeight.W_600)),
            ]) for d in dist
        ]
        safe_update(self)

    # ------------------------------------------------------------------
    # Importer
    # ------------------------------------------------------------------
    def _on_pick(self, e: ft.FilePickerResultEvent) -> None:
        if not self._pick_target:
            return
        if e.path:
            self._pick_target.value = e.path
        elif e.files:
            self._pick_target.value = e.files[0].path
        safe_update(self._pick_target)

    def _save_root(self, e) -> None:
        config.save_settings(image_root=self.in_root.value.strip())
        toast(self._page, "Đã lưu thư mục ảnh gốc.", "ok")

    def _log(self, text: str, color=None) -> None:
        self.log.controls.append(ft.Text(text, size=11, font_family=config.MONO_FONT, color=color, selectable=True))
        safe_update(self.log)

    def _start_import(self, e) -> None:
        if self._running:
            return
        if self.cb_reset.value:
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Xóa dữ liệu hiện có?"),
                content=ft.Text("Toàn bộ ảnh, nhãn (kể cả nhãn đã duyệt), run và lịch sử dự đoán sẽ bị xóa khỏi pig_skin.db "
                                "trước khi nạp. File ảnh trên ổ đĩa không bị ảnh hưởng."),
                actions=[ft.TextButton("Hủy", on_click=lambda ev: self._page.close(dlg)),
                         ft.FilledButton("Xóa và nạp", style=ft.ButtonStyle(bgcolor="#C62828"),
                                         on_click=lambda ev: (self._page.close(dlg), self._launch()))],
            )
            self._page.open(dlg)
        else:
            self._launch()

    def _launch(self) -> None:
        run_dir = self.in_run.value.strip()
        opts = ImportOptions(
            manifest_path=Path(self.in_manifest.value.strip()),
            classes_path=Path(self.in_classes.value.strip()),
            image_root=Path(self.in_root.value.strip()),
            run_dir=Path(run_dir) if run_dir else None,
            compute_hash=bool(self.cb_hash.value),
            reset_existing=bool(self.cb_reset.value),
        )
        self._running = True
        self.btn_import.disabled = True
        self.progress.value = 0
        self.log.controls.clear()
        safe_update(self)
        self._page.run_thread(self._import_worker, opts)

    def _import_worker(self, opts: ImportOptions) -> None:
        last = {"msg": None}

        def progress(frac: float, msg: str) -> None:
            self.progress.value = frac
            self.progress_text.value = f"{frac * 100:5.1f}% · {msg}"
            if msg.split(" ")[0:2] != (last["msg"] or "").split(" ")[0:2]:
                self._log(msg)
            last["msg"] = msg
            safe_update(self.progress, self.progress_text)

        try:
            rep = run_import(self.db, opts, progress)
        except Exception as ex:  # noqa: BLE001 — mọi lỗi đều rollback trong transaction
            self._log(f"LỖI: {ex}", "#D9534F")
            self.progress_text.value = "Nạp thất bại — CSDL đã được rollback, không thay đổi."
            toast(self._page, f"Nạp thất bại: {ex}", "error")
        else:
            config.save_settings(image_root=str(opts.image_root))
            self._log(f"✓ {rep.rows} dòng manifest · {rep.images_new} ảnh mới · {rep.images_existing} ảnh đã có · "
                      f"{rep.labels_new} nhãn mới · {rep.labels_kept} nhãn giữ nguyên", "#2E9E6A")
            if rep.run_name:
                self._log(f"✓ Run {rep.run_name} · {rep.run_metrics_rows} dòng run_class_metrics", "#2E9E6A")
            for c in rep.checks:
                self._log(f"[{c['status'].upper()}] {c['title']}: {c['detail']}",
                          config.STATUS_STYLES[c["status"]][1])
            for w in rep.warnings:
                self._log(f"⚠ {w}", "#E0A030")
            for d in rep.duplicate_sha[:20]:
                self._log(f"  trùng: {d}", "#E0A030")
            self.selected_dataset_id = rep.dataset_id
            toast(self._page, "Nạp dữ liệu hoàn tất." if rep.ok else "Nạp xong nhưng có hạng mục đối chiếu chưa đạt.",
                  "ok" if rep.ok else "warn")
            if self.on_data_changed:
                self.on_data_changed()
            self._load_worker()
        finally:
            self._running = False
            self.btn_import.disabled = False
            safe_update(self)
