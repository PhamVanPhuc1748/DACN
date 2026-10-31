"""views/overview_view.py — Tổng quan & Checklist kiểm tra bàn giao (mục 9 tài liệu thiết kế)."""
from __future__ import annotations

import flet as ft

import config
from components import fmt_int, fmt_num, panel, safe_update, section_title, toast
from components.metric_card import MetricCard
from components.status_badge import StatusBadge
from database.db_manager import DBManager


class OverviewView(ft.Column):
    def __init__(self, page: ft.Page, db: DBManager):
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=16)
        self._page = page
        self.db = db

        self.card_total = MetricCard("Tổng ảnh trong dataset", "—", "", ft.Icons.PHOTO_LIBRARY_OUTLINED, "#3B82C4")
        self.card_split = MetricCard("Train / Val / Test", "—", "", ft.Icons.PIE_CHART, "#E0A030")
        self.card_classes = MetricCard("Số lớp chuẩn", "—", "", ft.Icons.CATEGORY, "#8B5CF6")
        self.card_run = MetricCard("Best run", "—", "", ft.Icons.MODEL_TRAINING, "#2BA88F")

        self.mock_banner = ft.Container(visible=False)
        self.dataset_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.progress = ft.ProgressRing(width=18, height=18, stroke_width=2, visible=False)
        self.summary_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.label_row = ft.Row(wrap=True, spacing=8)

        self.checklist = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Hạng mục kiểm tra", weight=ft.FontWeight.W_600)),
                ft.DataColumn(ft.Text("Kết quả", weight=ft.FontWeight.W_600)),
                ft.DataColumn(ft.Text("Chi tiết", weight=ft.FontWeight.W_600)),
            ],
            rows=[],
            column_spacing=24,
            heading_row_height=40,
            data_row_min_height=44,
            data_row_max_height=72,
            divider_thickness=0.5,
            expand=True,
        )

        header = ft.Row(
            [
                ft.Column([
                    ft.Text("Tổng quan nghiên cứu", size=24, weight=ft.FontWeight.W_700),
                    self.dataset_text,
                ], spacing=2, expand=True),
                self.progress,
                ft.OutlinedButton("Kiểm tra lại", icon=ft.Icons.REFRESH, on_click=lambda e: self.load()),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.controls = [
            header,
            self.mock_banner,
            ft.ResponsiveRow([self.card_total, self.card_split, self.card_classes, self.card_run], spacing=16,
                             run_spacing=16),
            panel(ft.Column([
                ft.Row([
                    section_title("Data Integrity Checklist", "Đối chiếu với mục 9 “Kiểm tra trước khi bàn giao”.",
                                  ft.Icons.FACT_CHECK_OUTLINED),
                    self.summary_text,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Row([self.checklist], scroll=ft.ScrollMode.AUTO),
            ], spacing=12)),
            panel(ft.Column([
                section_title("Trạng thái duyệt nhãn ground truth", "Bảng image_labels — chỉ người duyệt mới chuyển sang 'approved'.",
                              ft.Icons.VERIFIED),
                self.label_row,
            ], spacing=12)),
        ]

    # ------------------------------------------------------------------
    def load(self) -> None:
        self.progress.visible = True
        safe_update(self.progress)
        self._page.run_thread(self._load_worker)

    def _load_worker(self) -> None:
        try:
            settings = config.load_settings()
            ov = self.db.get_overview()
            checks = self.db.run_integrity_checks(ov["dataset_id"], settings.get("image_root"))
        except Exception as e:  # noqa: BLE001
            self.progress.visible = False
            safe_update(self.progress)
            toast(self._page, f"Lỗi đọc CSDL: {e}", "error")
            return
        self._render(ov, checks)

    def _render(self, ov: dict, checks: list[dict]) -> None:
        sp = ov["splits"]
        total = ov["total_items"]
        ds = ov["dataset"]
        self.dataset_text.value = (f"Dataset: {ds['name']} · {ds['version']} · seed {ds['seed']} · CSDL: {self.db.db_path}"
                                   if ds else f"Chưa có phiên bản dataset · CSDL: {self.db.db_path}")

        self.card_total.set(fmt_int(total), f"{fmt_int(ov['total_images'])} ảnh trong bảng images · chuẩn "
                                            f"{fmt_int(config.EXPECTED_TOTAL_IMAGES)}")
        self.card_split.set(" / ".join(fmt_int(sp[s]) for s in config.SPLITS),
                            " · ".join(f"{s} {sp[s] / total * 100:.1f}%" for s in config.SPLITS) if total else "",
                            extra=self._split_bar(sp, total))
        self.card_classes.set(f"{ov['num_classes']} lớp",
                              "Khớp chuẩn 10 lớp" if ov["num_classes"] == config.EXPECTED_NUM_CLASSES
                              else f"Lệch chuẩn ({config.EXPECTED_NUM_CLASSES})")
        run = ov["best_run"]
        if run:
            self.card_run.set(run["model_code"].replace("mobilenet_v2", "MobileNetV2"),
                              f"Val F1 {fmt_num(run['best_val_macro_f1'])} · Test F1 {fmt_num(run['test_macro_f1'])}\n"
                              f"Acc {fmt_num(run['test_accuracy'])} · epoch {run['best_epoch']} · {run['run_name']}")
        else:
            self.card_run.set("Chưa có", "Chưa có training run hoàn tất")

        if ov["is_mock"]:
            self.mock_banner.content = ft.Row([
                ft.Icon(ft.Icons.SCIENCE, color="#8B5CF6"),
                ft.Text("Đang hiển thị DỮ LIỆU MẪU (tên lớp và chỉ số từng lớp là giả lập; chỉ số tổng của run lấy từ "
                        "run thật). Vào “Dataset & Importer” để nạp manifest/classes.json thật.",
                        size=12, expand=True),
            ], spacing=10)
            self.mock_banner.padding = 12
            self.mock_banner.border_radius = 10
            self.mock_banner.bgcolor = ft.Colors.with_opacity(0.12, "#8B5CF6")
            self.mock_banner.border = ft.border.all(1, ft.Colors.with_opacity(0.4, "#8B5CF6"))
            self.mock_banner.visible = True
        else:
            self.mock_banner.visible = False

        self.checklist.rows = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Row([
                        ft.Icon({"pass": ft.Icons.CHECK_CIRCLE, "warn": ft.Icons.WARNING_AMBER}.get(c["status"], ft.Icons.CANCEL),
                                size=18, color=config.STATUS_STYLES[c["status"]][1]),
                        ft.Text(c["title"], size=13),
                    ], spacing=8)),
                    ft.DataCell(StatusBadge(c["status"], compact=True)),
                    ft.DataCell(ft.Container(ft.Text(c["detail"], size=12, color=ft.Colors.ON_SURFACE_VARIANT), width=520)),
                ],
                color=ft.Colors.with_opacity(0.06, config.STATUS_STYLES[c["status"]][1]) if c["status"] != "pass" else None,
            )
            for c in checks
        ]
        n_pass = sum(c["status"] == "pass" for c in checks)
        self.summary_text.value = f"{n_pass}/{len(checks)} hạng mục đạt"

        ls = ov["label_status"]
        self.label_row.controls = [
            ft.Container(
                content=ft.Row([StatusBadge(s), ft.Text(fmt_int(ls.get(s, 0)), size=18, weight=ft.FontWeight.W_700)],
                               spacing=10, tight=True),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=10,
            )
            for s in ("pending", "needs_review", "approved", "rejected")
        ] + [ft.Text(f"· {fmt_int(ov['num_predictions'])} lượt dự đoán đã lưu · {ov['num_runs']} training run",
                     size=12, color=ft.Colors.ON_SURFACE_VARIANT)]

        self.progress.visible = False
        safe_update(self)

    @staticmethod
    def _split_bar(sp: dict, total: int) -> ft.Control:
        if not total:
            return ft.Container()
        return ft.Container(
            margin=ft.margin.only(top=6),
            border_radius=4,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Row(
                [ft.Container(height=8, expand=max(1, sp[s]), bgcolor=config.SPLIT_COLORS[s], tooltip=f"{s}: {sp[s]}")
                 for s in config.SPLITS],
                spacing=2,
            ),
        )
