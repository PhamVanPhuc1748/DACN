"""
Shared Clinical Analytics Charts & Disease Catalog CRUD Components for Admin and Expert Views.
"""
from __future__ import annotations

import math
from typing import Callable

import flet as ft
import flet.canvas as cv

from services.project_data import (
    delete_class_info,
    display_class,
    load_classes_config,
    upsert_class_info,
)
from theme import PRIMARY, css_input, make_smooth_animation


def _empty_chart_box(t: dict, icon_name: object) -> ft.Control:
    """Hiển thị trạng thái Empty State thanh lịch khi SQL Database có 0 ca khám."""
    return ft.Container(
        height=220,
        bgcolor=t["SUB_SURFACE"],
        border=ft.border.all(1, t["BORDER"]),
        border_radius=12,
        padding=20,
        alignment=ft.alignment.center,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            tight=True,
            controls=[
                ft.Icon(icon_name, size=36, color=t["MUTED"]),
                ft.Text(
                    "Chưa có dữ liệu ca khám để hiển thị biểu đồ",
                    size=13.5,
                    weight=ft.FontWeight.W_700,
                    color=t["MUTED"],
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    "Dữ liệu thống kê thực tế từ SQL Database sẽ hiển thị tại đây ngay khi có ca khám mới.",
                    size=12,
                    color=t["SECONDARY"],
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
        ),
    )


def _build_donut_canvas(slices: list[tuple[str, int, str]], total: int, center_top: str, center_sub: str, t: dict) -> ft.Control:
    size = 148
    stroke = 20
    margin = stroke / 2 + 4
    arc_size = size - 2 * margin

    shapes: list[cv.Shape] = [
        cv.Arc(
            margin,
            margin,
            arc_size,
            arc_size,
            0,
            2 * math.pi,
            False,
            ft.Paint(color=t["BORDER"], stroke_width=stroke, style=ft.PaintingStyle.STROKE),
        )
    ]

    start_angle = -math.pi / 2
    safe_total = max(1, total)
    for _, count, color in slices:
        if count <= 0:
            continue
        sweep = (count / safe_total) * (2 * math.pi)
        # Để tránh lỗi render khi sweep đúng 2*pi trên một số driver canvas
        if sweep >= 2 * math.pi - 0.001:
            sweep = 2 * math.pi - 0.002
        shapes.append(
            cv.Arc(
                margin,
                margin,
                arc_size,
                arc_size,
                start_angle,
                sweep,
                False,
                ft.Paint(
                    color=color,
                    stroke_width=stroke,
                    style=ft.PaintingStyle.STROKE,
                    stroke_cap=ft.StrokeCap.BUTT,
                ),
            )
        )
        start_angle += sweep

    return ft.Stack(
        width=size,
        height=size,
        controls=[
            cv.Canvas(shapes=shapes, width=size, height=size),
            ft.Container(
                width=size,
                height=size,
                alignment=ft.alignment.center,
                content=ft.Column(
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=1,
                    tight=True,
                    controls=[
                        ft.Text(center_top, size=18, weight=ft.FontWeight.W_800, color=t["TEXT"]),
                        ft.Text(center_sub, size=11, weight=ft.FontWeight.W_600, color=t["SECONDARY"]),
                    ],
                ),
            ),
        ],
    )


def build_clinical_charts_section(page: ft.Page, stats: dict) -> ft.Control:
    """
    Hệ thống 3 Biểu đồ Trực quan truy vấn trực tiếp từ SQL Database cho Admin & Chuyên gia:
    1. Biểu đồ Phân bố Các nhóm Bệnh lý phát hiện (BarChart / Thanh tiến trình ngang tỷ lệ %)
    2. Biểu đồ Tỷ lệ Đồng thuận AI vs Chuyên gia & Trạng thái thẩm định (PieChart / Donut)
    3. Biểu đồ Xu hướng Ca khám & Mức độ Nguy hiểm (An toàn / Cảnh báo / Nguy hiểm cao)
    """
    from services.auth_service import tech_card, theme_tokens

    t = theme_tokens(page)
    total_ins = int(stats.get("total_inspections") or 0)
    dist: dict = stats.get("distribution") or {}
    agreed = int(stats.get("agreed_count") or 0)
    reviewed = int(stats.get("reviewed_count") or 0)
    relabeled = int(stats.get("relabeled_count") if "relabeled_count" in stats else max(0, reviewed - agreed))
    pending = int(stats.get("pending_count") or 0)
    sev = stats.get("severity_counts") or {"safe": 0, "warning": 0, "danger": 0}
    daily_trend: list[dict] = stats.get("daily_trend") or []

    # --- 1. Biểu đồ Phân bố Các nhóm Bệnh lý phát hiện ---
    if total_ins == 0 or not dist:
        chart1_body = _empty_chart_box(t, ft.Icons.BAR_CHART_ROUNDED)
    else:
        palette_bars = ["#10B981", "#0284C7", "#7C3AED", "#D97706", "#EF4444", "#0D9488", "#6366F1"]
        bar_rows = []
        for idx, (cls_code, count) in enumerate(sorted(dist.items(), key=lambda x: x[1], reverse=True)[:6]):
            ratio = count / max(1, total_ins)
            b_col = palette_bars[idx % len(palette_bars)]
            bar_rows.append(
                ft.Column(
                    spacing=4,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(
                                    f"{display_class(cls_code)}",
                                    size=13,
                                    weight=ft.FontWeight.W_600,
                                    color=t["TEXT"],
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True,
                                ),
                                ft.Text(
                                    f"{count} ca ({ratio * 100:.1f}%)",
                                    size=12.5,
                                    weight=ft.FontWeight.BOLD,
                                    color=b_col,
                                ),
                            ],
                        ),
                        ft.ProgressBar(
                            value=ratio,
                            bar_height=9,
                            color=b_col,
                            bgcolor=t["BORDER"],
                            border_radius=5,
                        ),
                    ],
                )
            )
        chart1_body = ft.Column(bar_rows, spacing=10)

    chart1_card = ft.Container(
        col={"xs": 12, "lg": 4},
        content=tech_card(
            page=page,
            padding=22,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.BAR_CHART_ROUNDED, color="#10B981", size=22),
                            ft.Text(
                                "Phân bố Nhóm Bệnh lý Phát hiện",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=t["TEXT"],
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True,
                            ),
                        ],
                    ),
                    ft.Text(
                        f"Thống kê thực tế trên {total_ins} ca quét từ mô hình Deep Learning",
                        size=12.5,
                        color=t["SECONDARY"],
                    ),
                    ft.Divider(height=6, color=t["BORDER"]),
                    chart1_body,
                ],
            ),
        ),
    )

    # --- 2. Biểu đồ Tỷ lệ Đồng thuận AI vs Chuyên gia & Trạng thái thẩm định (PieChart / Donut) ---
    if total_ins == 0:
        chart2_body = _empty_chart_box(t, ft.Icons.PIE_CHART_OUTLINE_ROUNDED)
    else:
        slices = [
            ("Chuyên gia đồng ý với AI", agreed, "#10B981"),
            ("Chuyên gia hiệu chỉnh nhãn", relabeled, "#F59E0B"),
            ("Ca đang chờ duyệt", pending, "#0284C7"),
        ]
        donut_ctrl = _build_donut_canvas(
            slices=slices,
            total=max(1, agreed + relabeled + pending),
            center_top=f"{total_ins} ca",
            center_sub=f"Đồng thuận {stats.get('ai_accuracy_vs_expert', 0.0):.0f}%",
            t=t,
        )
        legend_items = []
        denom = max(1, agreed + relabeled + pending)
        for lbl, cnt, col_hex in slices:
            pct = cnt / denom * 100.0
            legend_items.append(
                ft.Container(
                    bgcolor=t["SUB_SURFACE"],
                    border=ft.border.all(1, t["BORDER"]),
                    border_radius=10,
                    padding=ft.padding.symmetric(horizontal=10, vertical=7),
                    content=ft.Row(
                        spacing=8,
                        controls=[
                            ft.Container(width=10, height=10, border_radius=5, bgcolor=col_hex),
                            ft.Text(
                                lbl,
                                size=12.5,
                                weight=ft.FontWeight.W_600,
                                color=t["TEXT"],
                                expand=True,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text(
                                f"{cnt} ca ({pct:.0f}%)",
                                size=12.5,
                                weight=ft.FontWeight.BOLD,
                                color=col_hex,
                            ),
                        ],
                    ),
                )
            )
        chart2_body = ft.Column(
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                donut_ctrl,
                ft.Column(legend_items, spacing=6),
            ],
        )

    chart2_card = ft.Container(
        col={"xs": 12, "lg": 4},
        content=tech_card(
            page=page,
            padding=22,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.DONUT_LARGE_ROUNDED, color="#7C3AED", size=22),
                            ft.Text(
                                "Đồng thuận AI vs Chuyên gia",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=t["TEXT"],
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True,
                            ),
                        ],
                    ),
                    ft.Text(
                        f"So sánh kết quả duyệt lâm sàng ({reviewed} đã duyệt / {pending} chờ duyệt)",
                        size=12.5,
                        color=t["SECONDARY"],
                    ),
                    ft.Divider(height=6, color=t["BORDER"]),
                    chart2_body,
                ],
            ),
        ),
    )

    # --- 3. Biểu đồ Xu hướng Ca khám & Mức độ Nguy hiểm (An toàn / Cảnh báo / Nguy hiểm cao) ---
    if total_ins == 0:
        chart3_body = _empty_chart_box(t, ft.Icons.TIMELINE_ROUNDED)
    else:
        sev_rows = []
        sev_defs = [
            ("An toàn (Khỏe mạnh / Thấp)", int(sev.get("safe") or 0), "#10B981"),
            ("Cảnh báo (Trung bình)", int(sev.get("warning") or 0), "#F59E0B"),
            ("Nguy hiểm cao (Cần cách ly gấp)", int(sev.get("danger") or 0), "#EF4444"),
        ]
        for s_lbl, s_cnt, s_col in sev_defs:
            s_ratio = s_cnt / max(1, total_ins)
            sev_rows.append(
                ft.Column(
                    spacing=3,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row(
                                    spacing=6,
                                    controls=[
                                        ft.Container(width=9, height=9, border_radius=5, bgcolor=s_col),
                                        ft.Text(s_lbl, size=12.5, weight=ft.FontWeight.W_600, color=t["TEXT"]),
                                    ],
                                ),
                                ft.Text(f"{s_cnt} ca ({s_ratio * 100:.0f}%)", size=12.5, weight=ft.FontWeight.BOLD, color=s_col),
                            ],
                        ),
                        ft.ProgressBar(value=s_ratio, bar_height=8, color=s_col, bgcolor=t["BORDER"], border_radius=4),
                    ],
                )
            )

        max_day_cnt = max([int(d.get("count") or 0) for d in daily_trend] or [1])
        trend_bars = []
        for item in daily_trend[-7:]:
            d_str = str(item.get("date") or "")[-5:]  # MM-DD
            c_val = int(item.get("count") or 0)
            bar_h = max(10, int((c_val / max(1, max_day_cnt)) * 56))
            trend_bars.append(
                ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.END,
                    spacing=3,
                    expand=True,
                    controls=[
                        ft.Text(str(c_val), size=11, weight=ft.FontWeight.BOLD, color=t["CYAN"]),
                        ft.Container(
                            width=22,
                            height=bar_h,
                            border_radius=6,
                            bgcolor="#0284C7",
                        ),
                        ft.Text(d_str, size=10.5, color=t["SECONDARY"]),
                    ],
                )
            )

        trend_box = ft.Container(
            bgcolor=t["SUB_SURFACE"],
            border=ft.border.all(1, t["BORDER"]),
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Text("Xu hướng số ca khám theo ngày gần nhất:", size=12, weight=ft.FontWeight.W_600, color=t["SECONDARY"]),
                    ft.Row(
                        controls=trend_bars,
                        alignment=ft.MainAxisAlignment.SPACE_AROUND,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                        height=92,
                    ),
                ],
            ),
        )
        chart3_body = ft.Column([ft.Column(sev_rows, spacing=8), trend_box], spacing=10)

    chart3_card = ft.Container(
        col={"xs": 12, "lg": 4},
        content=tech_card(
            page=page,
            padding=22,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.HEALTH_AND_SAFETY_ROUNDED, color="#EF4444", size=22),
                            ft.Text(
                                "Xu hướng Ca khám & Mức độ Nguy hiểm",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=t["TEXT"],
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True,
                            ),
                        ],
                    ),
                    ft.Text(
                        "Phân tầng nguy cơ dịch tễ (An toàn / Cảnh báo / Nguy hiểm cao)",
                        size=12.5,
                        color=t["SECONDARY"],
                    ),
                    ft.Divider(height=6, color=t["BORDER"]),
                    chart3_body,
                ],
            ),
        ),
    )

    return ft.ResponsiveRow(
        run_spacing=16,
        spacing=16,
        controls=[chart1_card, chart2_card, chart3_card],
    )


def _normalize_danger_level(raw_level: str) -> str:
    lvl = (raw_level or "Trung bình").strip()
    if lvl in ("An toàn", "Thấp"):
        return "An toàn"
    if lvl in ("Cao", "Khẩn cấp"):
        return "Cao"
    return "Trung bình"


DANGER_COLORS = {
    "Cao": "#EF4444",
    "Trung bình": "#F59E0B",
    "An toàn": "#10B981",
}


def open_disease_editor_modal(
    page: ft.Page,
    disease_item: dict | None = None,
    on_saved: Callable[[dict], None] | None = None,
) -> ft.AlertDialog:
    """
    Mở hộp thoại Modal Dialog rộng 860px (padding 28, bo góc 20) ở giữa màn hình để
    Chỉnh sửa hoặc Thêm mới Nhóm Bệnh lý & Phác đồ Điều trị.
    Mỗi ô nhập có hàng tiêu đề riêng (Icon nghiệp vụ thú y màu chuyên biệt + chữ 14px W600)
    và chữ bên trong ô 15px, dễ đọc trên cả Light Mode & Dark Mode.
    """
    from services.auth_service import close_dialog, is_dark_mode, open_dialog, show_snack, theme_tokens

    t = theme_tokens(page)
    dark = is_dark_mode(page)
    is_edit = bool(disease_item and disease_item.get("code"))
    item = disease_item or {}

    label_color = "#F8FAFC" if dark else "#1E293B"
    sub_color = "#94A3B8" if dark else "#64748B"
    field_bg = t["SUB_SURFACE"] if dark else "#FFFFFF"
    field_border = t["BORDER"] if dark else "#CBD5E1"
    field_text_color = "#F8FAFC" if dark else "#0F172A"
    input_text_style = ft.TextStyle(size=15, weight=ft.FontWeight.W_500, height=1.45, color=field_text_color)
    input_padding = ft.padding.symmetric(horizontal=16, vertical=14)

    def _field_label(icon: object, text: str, color: str) -> tuple[ft.Row, ft.Icon]:
        icon_ctrl = ft.Icon(icon, color=color, size=20)
        row = ft.Row(
            [
                ft.Container(
                    width=30,
                    height=30,
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.12, color),
                    alignment=ft.alignment.center,
                    content=icon_ctrl,
                ),
                ft.Text(text, size=14, weight=ft.FontWeight.W_600, color=label_color),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return row, icon_ctrl

    def _text_input(
        value: str,
        hint: str,
        multiline: bool = False,
        prefix_icon: object = None,
        width: int | None = 800,
    ) -> ft.TextField:
        return ft.TextField(
            value=value,
            hint_text=hint,
            multiline=multiline,
            min_lines=3 if multiline else None,
            max_lines=5 if multiline else 1,
            prefix_icon=prefix_icon,
            width=width,
            expand=True,
            text_style=input_text_style,
            hint_style=ft.TextStyle(size=14, color=sub_color),
            content_padding=input_padding,
            bgcolor=field_bg,
            filled=True,
            fill_color=field_bg,
            border_color=field_border,
            border_width=1,
            focused_border_color="#10B981",
            focused_border_width=2,
            border_radius=12,
            cursor_color="#10B981",
        )

    def _field_block(
        label_row: ft.Control,
        field: ft.Control,
        expand: int | None = None,
        wrap_row: bool = True,
    ) -> ft.Column:
        field_ctrl = ft.Row([field]) if wrap_row else field
        return ft.Column(
            [label_row, field_ctrl],
            spacing=8,
            expand=expand,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    # 1. Mã lớp bệnh (Class Key) — Xanh dương #2563EB
    code_label, _ = _field_label(ft.Icons.QR_CODE_2_ROUNDED, "Mã lớp bệnh (Class Key)", "#2563EB")
    code_field = _text_input(
        item.get("code", ""),
        "VD: Infected_Bacterial_Erysipelas",
        prefix_icon=ft.Icons.TERMINAL_ROUNDED,
        width=600,
    )

    # 2. Mức độ nguy hiểm — Icon đổi màu động theo mức độ
    init_level = _normalize_danger_level(item.get("danger_level", "Trung bình"))
    danger_label, danger_label_icon = _field_label(
        ft.Icons.WARNING_AMBER_ROUNDED, "Mức độ nguy hiểm", DANGER_COLORS[init_level]
    )
    danger_label_box = danger_label.controls[0]

    def on_danger_select(e):
        lvl = _normalize_danger_level(danger_dropdown.value or "Trung bình")
        col = DANGER_COLORS[lvl]
        danger_label_icon.color = col
        danger_label_box.bgcolor = ft.Colors.with_opacity(0.12, col)
        danger_dropdown.leading_icon = ft.Icon(ft.Icons.HEALTH_AND_SAFETY_OUTLINED, color=col)
        page.update()

    danger_dropdown = ft.Dropdown(
        value=init_level,
        options=[ft.DropdownOption(key=k, text=k) for k in ("An toàn", "Trung bình", "Cao")],
        leading_icon=ft.Icon(ft.Icons.HEALTH_AND_SAFETY_OUTLINED, color=DANGER_COLORS[init_level]),
        text_style=input_text_style,
        content_padding=input_padding,
        bgcolor=field_bg,
        filled=True,
        fill_color=field_bg,
        border_color=field_border,
        border_width=1,
        focused_border_color="#10B981",
        focused_border_width=2,
        border_radius=12,
        width=300,
        expand=True,
        on_select=on_danger_select,
    )

    # 3. Tên bệnh hiển thị — Xanh ngọc #0D9488
    name_label, _ = _field_label(
        ft.Icons.MEDICAL_INFORMATION_ROUNDED, "Tên bệnh hiển thị (Tiếng Việt & Tên khoa học)", "#0D9488"
    )
    name_vi_field = _text_input(
        item.get("name_vi", ""),
        "VD: Bệnh đóng dấu lợn (Erysipelas)",
        prefix_icon=ft.Icons.LOCAL_HOSPITAL_ROUNDED,
        width=800,
    )

    # 4. Triệu chứng nhận diện lâm sàng — Tím y sinh #7C3AED
    symptoms_label, _ = _field_label(ft.Icons.BIOTECH_ROUNDED, "Triệu chứng nhận diện lâm sàng (Clinical Symptoms)", "#7C3AED")
    symptoms_field = _text_input(
        item.get("symptoms", ""),
        "Mô tả tổn thương da: mảng đỏ, mụn nước, đóng vảy, rụng lông, sốt...",
        multiline=True,
        width=800,
    )

    # 5. Phòng ngừa & An toàn sinh học — Xanh lam #0284C7
    prevention_label, _ = _field_label(
        ft.Icons.SHIELD_ROUNDED, "Biện pháp phòng ngừa & An toàn sinh học (Prevention & Biosecurity)", "#0284C7"
    )
    prevention_field = _text_input(
        item.get("prevention", ""),
        "Cách ly, sát trùng chuồng trại, lịch tiêm vắc-xin...",
        multiline=True,
        width=800,
    )

    # 6. Phác đồ điều trị & Thuốc khuyến nghị — Xanh lục y tế #16A34A
    treatment_label, _ = _field_label(
        ft.Icons.MEDICATION_ROUNDED, "Phác đồ điều trị & Thuốc khuyến nghị (Treatment Protocol)", "#16A34A"
    )
    treatment_field = _text_input(
        item.get("treatment", ""),
        "Thuốc đặc trị, liều lượng (mg/kg TT), liệu trình, chăm sóc hồi phục...",
        multiline=True,
        width=800,
    )

    err_text = ft.Text("", size=13.5, color="#DC2626", weight=ft.FontWeight.W_600, visible=False)

    dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=20),
        bgcolor=t["SURFACE"],
        content_padding=0,
        actions_padding=ft.padding.only(left=28, right=28, bottom=24, top=4),
        actions_alignment=ft.MainAxisAlignment.END,
        scrollable=True,
    )

    def handle_save_modal(ev):
        try:
            saved = upsert_class_info(
                code=code_field.value or "",
                name_vi=name_vi_field.value or "",
                danger_level=danger_dropdown.value or "Trung bình",
                symptoms=symptoms_field.value or "",
                prevention=prevention_field.value or "",
                treatment=treatment_field.value or "",
            )
            close_dialog(page, dlg)
            if on_saved:
                on_saved(saved)
            show_snack(
                page,
                f"Đã lưu cập nhật '{saved['name_vi']}' vào models/classes.json & SQL Database!",
                "#059669",
            )
        except ValueError as err:
            err_text.value = str(err)
            err_text.visible = True
            page.update()

    header_title = "Chỉnh sửa Thông tin Bệnh lý & Phác đồ" if is_edit else "Thêm mới Nhóm Bệnh lý"
    header_icon = ft.Icons.EDIT_NOTE_ROUNDED if is_edit else ft.Icons.ADD_MODERATOR_ROUNDED

    header = ft.Row(
        vertical_alignment=ft.CrossAxisAlignment.START,
        controls=[
            ft.Container(
                width=48,
                height=48,
                border_radius=12,
                bgcolor=t["EMERALD_SOFT"],
                alignment=ft.alignment.center,
                content=ft.Icon(header_icon, color=PRIMARY, size=26),
            ),
            ft.Column(
                [
                    ft.Text(header_title, size=22, weight=ft.FontWeight.BOLD, color=label_color),
                    ft.Text(
                        "Cập nhật triệu chứng lâm sàng, an toàn sinh học và phác đồ điều trị chuẩn",
                        size=13,
                        color=sub_color,
                    ),
                ],
                spacing=2,
                tight=True,
                expand=True,
            ),
            ft.IconButton(
                icon=ft.Icons.CLOSE_ROUNDED,
                icon_color=sub_color,
                icon_size=24,
                tooltip="Đóng hộp thoại",
                on_click=lambda ev: close_dialog(page, dlg),
            ),
        ],
        spacing=14,
    )

    dlg.content = ft.Container(
        width=860,
        padding=ft.padding.all(28),
        border_radius=20,
        content=ft.Column(
            spacing=18,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                header,
                ft.Divider(height=1, color=t["BORDER"]),
                # Hàng 1: Mã lớp bệnh (~65%, expand=2) + Mức độ nguy hiểm (~35%, expand=1)
                ft.Row(
                    [
                        _field_block(code_label, code_field, expand=2),
                        _field_block(danger_label, danger_dropdown, expand=1),
                    ],
                    spacing=20,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                # Hàng 2: Tên bệnh hiển thị
                _field_block(name_label, name_vi_field),
                # Hàng 3, 4, 5: Triệu chứng, Phòng ngừa & An toàn sinh học, Phác đồ điều trị
                _field_block(symptoms_label, symptoms_field),
                _field_block(prevention_label, prevention_field),
                _field_block(treatment_label, treatment_field),
                err_text,
            ],
        ),
    )

    dlg.actions = [
        ft.OutlinedButton(
            "Hủy bỏ",
            icon=ft.Icons.CLOSE_ROUNDED,
            height=44,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=22),
                text_style=ft.TextStyle(size=14, weight=ft.FontWeight.W_600),
                shape=ft.RoundedRectangleBorder(radius=10),
                color=label_color,
            ),
            on_click=lambda ev: close_dialog(page, dlg),
        ),
        ft.FilledButton(
            "Lưu thay đổi",
            icon=ft.Icons.SAVE_ROUNDED,
            height=44,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=26),
                text_style=ft.TextStyle(size=15, weight=ft.FontWeight.BOLD),
                bgcolor="#0F766E",
                color="#FFFFFF",
                icon_color="#FFFFFF",
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
            on_click=handle_save_modal,
        ),
    ]

    open_dialog(page, dlg)
    return dlg


def build_disease_catalog_crud_card(
    page: ft.Page,
    title_text: str = "2. Quản lý Danh mục Bệnh lý & Phác đồ Điều trị Mặc định",
    on_changed: Callable[[], None] | None = None,
) -> ft.Control:
    """
    Mặt trang Quản lý Danh mục Bệnh lý & Phác đồ Điều trị Mặc định (dùng chung cho Admin & Expert):
    - Đã xóa bỏ hoàn toàn 6 ô nhập liệu tĩnh trên mặt trang.
    - Chỉ hiển thị thanh tiêu đề kèm nút 'Tạo lớp bệnh mới' (icon ADD) bên phải và Danh sách các bệnh lý bên dưới.
    - Khi bấm trực tiếp vào một dòng bệnh, bấm nút 'Sửa', hoặc bấm 'Tạo lớp bệnh mới',
      mở hộp thoại Modal Dialog `open_disease_editor_modal(disease_item=...)` rộng 680px.
    """
    from services.auth_service import show_snack, tech_card, theme_tokens

    t = theme_tokens(page)
    classes_list_col = ft.Column(spacing=10)

    def handle_open_modal(disease_item: dict | None = None):
        open_disease_editor_modal(
            page=page,
            disease_item=disease_item,
            on_saved=lambda _saved: refresh_classes_list(),
        )

    def handle_delete_class(code: str):
        if delete_class_info(code):
            refresh_classes_list()
            show_snack(page, f"Đã xóa lớp bệnh '{code}' khỏi danh mục.", "#DC2626")

    def refresh_classes_list():
        cur_t = theme_tokens(page)
        if on_changed:
            on_changed()
        latest = load_classes_config()
        classes_list_col.controls.clear()
        for code, raw_item in latest.items():
            item = dict(raw_item)
            item["code"] = code
            lvl = item.get("danger_level", "Trung bình")
            lvl_col = (
                "#EF4444"
                if lvl in ("Cao", "Khẩn cấp")
                else ("#10B981" if lvl in ("An toàn", "Thấp") else "#D97706")
            )
            classes_list_col.controls.append(
                ft.Container(
                    padding=16,
                    bgcolor=cur_t["SUB_SURFACE"],
                    border_radius=12,
                    border=ft.border.all(1, cur_t["BORDER"]),
                    animate=make_smooth_animation(180),
                    ink=True,
                    tooltip="Nhấn để mở hộp thoại chỉnh sửa thông tin bệnh lý & phác đồ",
                    on_click=lambda e, it=item: handle_open_modal(it),
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(
                                                f"{item.get('name_vi')} ({code})",
                                                size=15,
                                                weight=ft.FontWeight.BOLD,
                                                color=cur_t["TEXT"],
                                                expand=True,
                                            ),
                                            ft.Container(
                                                bgcolor=ft.Colors.with_opacity(0.14, lvl_col),
                                                border=ft.border.all(1, lvl_col),
                                                padding=ft.padding.symmetric(horizontal=10, vertical=3),
                                                border_radius=10,
                                                content=ft.Text(
                                                    f"Mức độ: {lvl}",
                                                    size=12,
                                                    weight=ft.FontWeight.W_600,
                                                    color=lvl_col,
                                                ),
                                            ),
                                        ],
                                        spacing=8,
                                    ),
                                    ft.Text(
                                        f"Triệu chứng: {item.get('symptoms')}",
                                        size=13,
                                        color=cur_t["SECONDARY"],
                                        max_lines=2,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(
                                        f"Phác đồ mặc định: {item.get('treatment')}",
                                        size=13.5,
                                        color=cur_t["EMERALD"],
                                        weight=ft.FontWeight.W_600,
                                    ),
                                ],
                                spacing=4,
                                expand=True,
                            ),
                            ft.OutlinedButton(
                                "Sửa",
                                icon=ft.Icons.EDIT_OUTLINED,
                                on_click=lambda e, it=item: handle_open_modal(it),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_color="#DC2626",
                                tooltip="Xóa lớp bệnh",
                                on_click=lambda e, c=code: handle_delete_class(c),
                            ),
                        ],
                        spacing=10,
                    ),
                )
            )
        page.update()

    refresh_classes_list()

    return tech_card(
        page=page,
        padding=24,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.TUNE_ROUNDED, color=t["CYAN"], size=22),
                        ft.Text(
                            title_text,
                            size=18,
                            weight=ft.FontWeight.BOLD,
                            color=t["TEXT"],
                            expand=True,
                        ),
                        ft.FilledButton(
                            "Tạo lớp bệnh mới",
                            icon=ft.Icons.ADD_ROUNDED,
                            on_click=lambda e: handle_open_modal(None),
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(
                    "Nhấn trực tiếp vào dòng bệnh bất kỳ hoặc bấm nút 'Sửa' để mở hộp thoại chỉnh sửa phác đồ:",
                    size=13.5,
                    color=t["SECONDARY"],
                ),
                ft.Divider(height=10, color=t["BORDER"]),
                ft.Container(
                    padding=ft.padding.only(bottom=90),
                    content=classes_list_col,
                ),
            ],
            spacing=12,
        ),
    )
