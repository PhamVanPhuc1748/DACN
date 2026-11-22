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


def _empty_chart_box(
    t: dict,
    icon_name: object,
    title: str = "Chưa có dữ liệu ca khám để hiển thị biểu đồ",
    subtitle: str = "Dữ liệu thống kê thực tế từ SQL Database sẽ hiển thị tại đây ngay khi có ca khám mới.",
) -> ft.Control:
    """Hiển thị trạng thái Empty State thanh lịch căn giữa khi danh sách hoặc biểu đồ trống."""
    return ft.Container(
        height=220,
        width=float("inf"),
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
                    title,
                    size=13.5,
                    weight=ft.FontWeight.W_700,
                    color=t["MUTED"],
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    subtitle,
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
        width: int | None = None,
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
        wrap_row: bool = False,
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

    import inspect

    dd_params = inspect.signature(ft.Dropdown.__init__).parameters
    opt_cls = getattr(ft, "DropdownOption", ft.dropdown.Option)
    dd_kwargs = {
        "value": init_level,
        "options": [opt_cls(key=k, text=k) for k in ("An toàn", "Trung bình", "Cao")],
        "leading_icon": ft.Icon(ft.Icons.HEALTH_AND_SAFETY_OUTLINED, color=DANGER_COLORS[init_level]),
        "text_style": input_text_style,
        "content_padding": input_padding,
        "bgcolor": field_bg,
        "filled": True,
        "fill_color": field_bg,
        "border_color": field_border,
        "border_width": 1,
        "focused_border_color": "#10B981",
        "focused_border_width": 2,
        "border_radius": 12,
        "expand": True,
    }
    dd_kwargs = {k: v for k, v in dd_kwargs.items() if k in dd_params}
    if "on_select" in dd_params:
        dd_kwargs["on_select"] = on_danger_select
    elif "on_change" in dd_params:
        dd_kwargs["on_change"] = on_danger_select
    danger_dropdown = ft.Dropdown(**dd_kwargs)

    # 3. Tên bệnh hiển thị — Xanh ngọc #0D9488
    name_label, _ = _field_label(
        ft.Icons.MEDICAL_INFORMATION_ROUNDED, "Tên bệnh hiển thị (Tiếng Việt & Tên khoa học)", "#0D9488"
    )
    name_vi_field = _text_input(
        item.get("name_vi", ""),
        "VD: Bệnh đóng dấu lợn (Erysipelas)",
        prefix_icon=ft.Icons.LOCAL_HOSPITAL_ROUNDED,
    )

    # 4. Triệu chứng nhận diện lâm sàng — Tím y sinh #7C3AED
    symptoms_label, _ = _field_label(ft.Icons.BIOTECH_ROUNDED, "Triệu chứng nhận diện lâm sàng (Clinical Symptoms)", "#7C3AED")
    symptoms_field = _text_input(
        item.get("symptoms", ""),
        "Mô tả tổn thương da: mảng đỏ, mụn nước, đóng vảy, rụng lông, sốt...",
        multiline=True,
    )

    # 5. Phòng ngừa & An toàn sinh học — Xanh lam #0284C7
    prevention_label, _ = _field_label(
        ft.Icons.SHIELD_ROUNDED, "Biện pháp phòng ngừa & An toàn sinh học (Prevention & Biosecurity)", "#0284C7"
    )
    prevention_field = _text_input(
        item.get("prevention", ""),
        "Cách ly, sát trùng chuồng trại, lịch tiêm vắc-xin...",
        multiline=True,
    )

    # 6. Phác đồ điều trị & Thuốc khuyến nghị — Xanh lục y tế #16A34A
    treatment_label, _ = _field_label(
        ft.Icons.MEDICATION_ROUNDED, "Phác đồ điều trị & Thuốc khuyến nghị (Treatment Protocol)", "#16A34A"
    )
    treatment_field = _text_input(
        item.get("treatment", ""),
        "Thuốc đặc trị, liều lượng (mg/kg TT), liệu trình, chăm sóc hồi phục...",
        multiline=True,
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
        from services.auth_service import session_get

        try:
            sess_user = session_get(page, "current_user") or {}
            actor = str(sess_user.get("email") or sess_user.get("full_name") or "").strip()
            saved = upsert_class_info(
                code=code_field.value or "",
                name_vi=name_vi_field.value or "",
                danger_level=danger_dropdown.value or "Trung bình",
                symptoms=symptoms_field.value or "",
                prevention=prevention_field.value or "",
                treatment=treatment_field.value or "",
                updated_by=actor,
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
        from services.auth_service import session_get

        sess_user = session_get(page, "current_user") or {}
        actor = str(sess_user.get("email") or sess_user.get("full_name") or "").strip()
        if delete_class_info(code, updated_by=actor):
            refresh_classes_list()
            show_snack(page, f"Đã xóa lớp bệnh '{code}' khỏi danh mục.", "#DC2626")

    def refresh_classes_list():
        cur_t = theme_tokens(page)
        if on_changed:
            on_changed()
        latest = load_classes_config()
        classes_list_col.controls.clear()
        if not latest:
            classes_list_col.controls.append(
                _empty_chart_box(
                    cur_t,
                    ft.Icons.MEDICAL_INFORMATION_OUTLINED,
                    title="Danh mục bệnh lý hiện đang trống",
                    subtitle="Nhấn nút 'Tạo lớp bệnh mới' ở góc phải để thêm nhóm bệnh lý và phác đồ điều trị.",
                )
            )
            page.update()
            return
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


# --- Smart Dosage Calculator (Tính Liều lượng Thuốc theo Cân nặng & Số lượng đàn) ---

DISEASE_DOSAGE_RULES: dict[str, dict] = {
    "Healthy": {
        "drug_name": "Vitamin C + Điện giải Gluco-KC (Phòng bệnh & tăng đề kháng)",
        "route": "Pha nước uống / Trộn thức ăn",
        "mode": "per_kg",
        "rate": 0.1,  # 1 g / 10 kg TT/ngày
        "unit": "g",
        "duration": "3–5 ngày định kỳ / tháng",
        "disinfectant": "Iodine 10% hoặc BKC 80% (Sát trùng định kỳ)",
        "conc_ml_per_l": 5.0,
        "water_l_per_pig": 0.5,
    },
    "Infected_Bacterial_Erysipelas": {
        "drug_name": "Amoxicillin LA 15% hoặc Penicillin G + Streptomycin",
        "route": "Tiêm bắp sâu (IM)",
        "mode": "per_kg",
        "rate": 0.1,  # 1 ml / 10 kg TT/ngày
        "unit": "ml",
        "duration": "3–5 ngày liên tục",
        "disinfectant": "Virkon S / Iodine 10% (Phun diệt Erysipelothrix)",
        "conc_ml_per_l": 10.0,
        "water_l_per_pig": 0.8,
    },
    "Infected_Bacterial_Greasy_Pig_Disease": {
        "drug_name": "Amoxicillin 15% hoặc Ceftiofur 5% (kết hợp tắm Chlorhexidine 1%)",
        "route": "Tiêm bắp (IM) + Sát khuẩn da",
        "mode": "per_kg",
        "rate": 0.1,  # 1 ml / 10 kg TT/ngày
        "unit": "ml",
        "duration": "3–5 ngày liên tục",
        "disinfectant": "Povidone-Iodine 10% / Glutaraldehyde",
        "conc_ml_per_l": 10.0,
        "water_l_per_pig": 0.6,
    },
    "Infected_Environmental_Dermatitis": {
        "drug_name": "Amoxicillin 15% + Kháng viêm (hoặc bôi Kẽm Oxit vùng viêm)",
        "route": "Tiêm bắp (IM) / Bôi tại chỗ",
        "mode": "per_kg",
        "rate": 0.067,  # ~1 ml / 15 kg TT/ngày
        "unit": "ml",
        "duration": "3 ngày + vệ sinh nền chuồng khô thoáng",
        "disinfectant": "BKC 80% (Khử khuẩn nền chuồng ẩm ướt)",
        "conc_ml_per_l": 5.0,
        "water_l_per_pig": 0.7,
    },
    "Infected_Environmental_Sunburn": {
        "drug_name": "Kem Kẽm Oxit / Panthenol làm dịu da (+ Điện giải Vitamin C)",
        "route": "Bôi ngoài da vùng đỏ rát",
        "mode": "per_head",
        "rate": 3.0,  # 3 g / con / ngày
        "unit": "g",
        "duration": "3–5 ngày + che mát chuồng nuôi",
        "disinfectant": "Iodine 10% loãng (Sát trùng nhẹ chống bội nhiễm)",
        "conc_ml_per_l": 5.0,
        "water_l_per_pig": 0.5,
    },
    "Infected_Fungal_Pityriasis_Rosea": {
        "drug_name": "Dung dịch Povidone-Iodine 10% (Bôi tổn thương + Kẽm hữu cơ)",
        "route": "Bôi ngoài da ngày 1–2 lần",
        "mode": "per_head",
        "rate": 4.0,  # 4 ml / con / ngày
        "unit": "ml",
        "duration": "5–7 ngày theo dõi tự hồi phục",
        "disinfectant": "Iodine 10% / Virkon S",
        "conc_ml_per_l": 8.0,
        "water_l_per_pig": 0.6,
    },
    "Infected_Fungal_Ringworm": {
        "drug_name": "Dung dịch kháng nấm Ketoconazole / Enilconazole / Iodine 10%",
        "route": "Bôi / Phun trực tiếp lên mảng nấm",
        "mode": "per_head",
        "rate": 5.0,  # 5 ml / con / ngày
        "unit": "ml",
        "duration": "7–10 ngày liên tục",
        "disinfectant": "Virkon S / Formalin loãng (Diệt bào tử nấm trên vách)",
        "conc_ml_per_l": 10.0,
        "water_l_per_pig": 0.8,
    },
    "Infected_Parasitic_Mange": {
        "drug_name": "Ivermectin 1% (Liều chuẩn 1 ml / 33 kg TT)",
        "route": "Tiêm dưới da (SC) — nhắc lại sau 10–14 ngày",
        "mode": "per_kg",
        "rate": 1.0 / 33.0,  # 1 ml / 33 kg TT
        "unit": "ml",
        "duration": "2 mũi cách nhau 10–14 ngày",
        "disinfectant": "Amitraz 12.5% (Phun diệt ve ghẻ trên thân & vách chuồng)",
        "conc_ml_per_l": 2.0,
        "water_l_per_pig": 0.8,
    },
    "Infected_Viral_Foot_and_Mouth_Disease": {
        "drug_name": "Amoxicillin LA 15% chống bội nhiễm (+ Rửa vết loét Acid Citric 1%)",
        "route": "Tiêm bắp (IM) hỗ trợ — KHÔNG có thuốc diệt virus đặc hiệu",
        "mode": "per_kg",
        "rate": 0.1,  # 1 ml / 10 kg TT/ngày
        "unit": "ml",
        "duration": "3–5 ngày + cách ly nghiêm ngặt & báo Thú y",
        "disinfectant": "Virkon S / Acid Citric 2% / NaOH 2% (Sát trùng khẩn cấp)",
        "conc_ml_per_l": 15.0,
        "water_l_per_pig": 1.2,
    },
    "Infected_Viral_Swinepox": {
        "drug_name": "Oxytetracycline LA 20% chống bội nhiễm (+ Chấm mụn Xanh Methylen)",
        "route": "Tiêm bắp sâu (IM) cách 48 giờ",
        "mode": "per_kg",
        "rate": 0.1,  # 1 ml / 10 kg TT
        "unit": "ml",
        "duration": "2–3 mũi + diệt ruồi muỗi, chấy rận trung gian",
        "disinfectant": "Iodine 10% kết hợp Permethrin diệt côn trùng",
        "conc_ml_per_l": 10.0,
        "water_l_per_pig": 0.8,
    },
}


def calculate_smart_dosage(disease_code: str, avg_weight_kg: float, head_count: int) -> dict:
    """
    Tính liều lượng thuốc điều trị/hỗ trợ và lượng thuốc sát trùng chuồng nuôi theo cân nặng trung bình (kg/con)
    và số lượng heo (con) ứng với đúng nhóm bệnh vừa phát hiện.
    """
    w = float(avg_weight_kg)
    n = int(head_count)
    if w <= 0 or w > 500:
        raise ValueError("Trọng lượng trung bình phải nằm trong khoảng 0.5 – 500 kg/con.")
    if n <= 0 or n > 10000:
        raise ValueError("Số lượng heo phải từ 1 – 10,000 con.")

    rule = DISEASE_DOSAGE_RULES.get(str(disease_code or "").strip()) or DISEASE_DOSAGE_RULES["Infected_Environmental_Dermatitis"]
    total_weight_kg = round(w * n, 1)
    if rule["mode"] == "per_kg":
        per_pig = round(w * float(rule["rate"]), 2)
    else:
        per_pig = round(float(rule["rate"]), 2)
    total_daily = round(per_pig * n, 2)

    water_l = round(float(rule["water_l_per_pig"]) * n, 1)
    disinfectant_ml = round(water_l * float(rule["conc_ml_per_l"]), 1)

    return {
        "disease_code": str(disease_code or ""),
        "disease_name": display_class(disease_code),
        "avg_weight_kg": round(w, 1),
        "head_count": n,
        "total_weight_kg": total_weight_kg,
        "drug_name": rule["drug_name"],
        "route": rule["route"],
        "unit": rule["unit"],
        "duration": rule["duration"],
        "dose_per_pig": per_pig,
        "dose_total_daily": total_daily,
        "disinfectant_name": rule["disinfectant"],
        "disinfectant_concentrate_ml": disinfectant_ml,
        "disinfectant_water_liters": water_l,
        "conc_ml_per_l": rule["conc_ml_per_l"],
    }


def build_smart_dosage_calculator(page: ft.Page, disease_code: str) -> ft.Control:
    """
    Widget Công cụ Tính Liều lượng Thuốc theo Cân nặng (Smart Dosage Calculator) đặt bên dưới Phác đồ điều trị.
    Cho phép nhập Trọng lượng trung bình (kg/con) & Số lượng heo (con) và cập nhật tự động lượng thuốc & sát trùng.
    """
    from services.auth_service import is_dark_mode, theme_tokens

    t = theme_tokens(page)
    dark = is_dark_mode(page)
    accent = "#0EA5E9" if dark else "#0284C7"
    soft_bg = t["CYAN_SOFT"] if dark else "#F0F9FF"
    card_border = "#38BDF8" if dark else "#BAE6FD"

    weight_field = css_input(
        label="Trọng lượng TB (kg/con)",
        value="25",
        hint_text="VD: 25",
        prefix_icon=ft.Icons.MONITOR_WEIGHT_OUTLINED,
        expand=True,
        page=page,
    )
    count_field = css_input(
        label="Số lượng heo (con)",
        value="10",
        hint_text="VD: 10",
        prefix_icon=ft.Icons.NUMBERS_ROUNDED,
        expand=True,
        page=page,
    )
    weight_field.keyboard_type = ft.KeyboardType.NUMBER
    count_field.keyboard_type = ft.KeyboardType.NUMBER

    output_host = ft.Container()

    def _metric_tile(title: str, value: str, sub: str, color: str) -> ft.Control:
        return ft.Container(
            expand=True,
            padding=ft.padding.symmetric(horizontal=10, vertical=9),
            border_radius=10,
            bgcolor=t["SURFACE"],
            border=ft.border.all(1, t["BORDER"]),
            content=ft.Column(
                [
                    ft.Text(title, size=11.5, weight=ft.FontWeight.W_600, color=t["SECONDARY"]),
                    ft.Text(value, size=15.5, weight=ft.FontWeight.W_800, color=color),
                    ft.Text(sub, size=11.5, color=t["MUTED"]),
                ],
                spacing=2,
                tight=True,
            ),
        )

    def _recalc(e=None):
        try:
            w_val = float((weight_field.value or "").replace(",", ".").strip())
            n_val = int(float((count_field.value or "").replace(",", ".").strip()))
            calc = calculate_smart_dosage(disease_code, w_val, n_val)
            u = calc["unit"]
            output_host.content = ft.Column(
                [
                    ft.Row(
                        [
                            _metric_tile(
                                "Tổng khối lượng đàn",
                                f"{calc['total_weight_kg']:.1f} kg",
                                f"{calc['head_count']} con × {calc['avg_weight_kg']:.1f} kg",
                                t["TEXT"],
                            ),
                            _metric_tile(
                                f"Tổng thuốc / ngày ({u})",
                                f"{calc['dose_total_daily']:.1f} {u}",
                                f"≈ {calc['dose_per_pig']:.2f} {u}/con",
                                "#10B981" if dark else "#059669",
                            ),
                            _metric_tile(
                                "Sát trùng chuồng nuôi",
                                f"{calc['disinfectant_concentrate_ml']:.0f} ml",
                                f"Pha {calc['disinfectant_water_liters']:.1f} L nước ({calc['conc_ml_per_l']:.0f} ml/L)",
                                accent,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Text(
                        f"• Thuốc gợi ý: {calc['drug_name']} • Đường dùng: {calc['route']} • Liệu trình: {calc['duration']}",
                        size=12.5,
                        weight=ft.FontWeight.W_600,
                        color=t["TEXT"],
                    ),
                    ft.Text(
                        f"• Sát trùng: {calc['disinfectant_name']}. Lưu ý: Số liệu mang tính tham khảo kỹ thuật — luôn kiểm tra nồng độ nhãn thuốc và xác nhận với Bác sĩ Thú y.",
                        size=12,
                        color=t["SECONDARY"],
                    ),
                ],
                spacing=8,
                tight=True,
            )
        except Exception as err:
            msg = str(err) if isinstance(err, ValueError) else "Vui lòng nhập số hợp lệ cho Trọng lượng (kg) và Số lượng heo (con)."
            output_host.content = ft.Text(f"⚠️ {msg}", size=12.5, color="#DC2626", weight=ft.FontWeight.W_600)
        if e is not None:
            page.update()

    weight_field.on_change = _recalc
    count_field.on_change = _recalc
    _recalc()

    return ft.Container(
        padding=14,
        border_radius=12,
        bgcolor=soft_bg,
        border=ft.border.all(1, card_border),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CALCULATE_ROUNDED, color=accent, size=20),
                        ft.Text(
                            f"🧮 Tính Liều lượng Thuốc & Sát trùng ({display_class(disease_code)})",
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color=accent,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row([weight_field, count_field], spacing=10),
                output_host,
            ],
            spacing=10,
            tight=True,
        ),
    )


def build_dual_benchmark_card(page: ft.Page, benchmark: dict) -> ft.Control:
    """
    Bảng đối chiếu Chế độ Hội chẩn Kép 2 Mô hình (Dual-Model Benchmark):
    So sánh song song MobileNetV2 & EfficientNet-B0 (Nhãn dự đoán, Độ tin cậy %, Thời gian ms) + Huy hiệu Đồng thuận.
    """
    from services.auth_service import theme_tokens

    t = theme_tokens(page)
    cons = benchmark.get("consensus") or {}
    badge_text = cons.get("badge") or "Kết quả Hội chẩn kép"
    badge_col = cons.get("color") or "#0284C7"
    summary_text = cons.get("summary") or ""
    total_ms = benchmark.get("total_ms", 0.0)
    models = benchmark.get("models") or []

    rows_ui: list[ft.Control] = [
        ft.Container(
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            border_radius=8,
            bgcolor=t["SURFACE"],
            content=ft.Row(
                [
                    ft.Text("Mô hình AI", size=12, weight=ft.FontWeight.BOLD, color=t["SECONDARY"], expand=2),
                    ft.Text("Nhãn dự đoán", size=12, weight=ft.FontWeight.BOLD, color=t["SECONDARY"], expand=3),
                    ft.Text("Độ tin cậy", size=12, weight=ft.FontWeight.BOLD, color=t["SECONDARY"], width=86, text_align=ft.TextAlign.RIGHT),
                    ft.Text("Thời gian", size=12, weight=ft.FontWeight.BOLD, color=t["SECONDARY"], width=74, text_align=ft.TextAlign.RIGHT),
                ],
                spacing=8,
            ),
        )
    ]

    for item in models:
        arch = item.get("architecture") or item.get("model_label") or "PyTorch CNN"
        run_id = item.get("run_name") or ""
        lbl = item.get("display_label") or (display_class(item.get("label")) if item.get("label") else "Không hợp lệ")
        conf = float(item.get("confidence") or 0.0)
        ms = item.get("inference_ms", 0.0)
        c_col = "#10B981" if conf >= 0.75 else ("#F59E0B" if conf >= 0.55 else "#EF4444")
        rows_ui.append(
            ft.Container(
                padding=ft.padding.symmetric(horizontal=10, vertical=8),
                border_radius=8,
                bgcolor=t["SURFACE"],
                border=ft.border.all(1, t["BORDER"]),
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(str(arch), size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                                ft.Text(str(run_id), size=11, color=t["MUTED"]),
                            ],
                            spacing=1,
                            expand=2,
                        ),
                        ft.Text(
                            str(lbl),
                            size=13,
                            weight=ft.FontWeight.W_600,
                            color=t["CYAN"],
                            expand=3,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            f"{conf * 100:.1f}%",
                            size=13.5,
                            weight=ft.FontWeight.BOLD,
                            color=c_col,
                            width=86,
                            text_align=ft.TextAlign.RIGHT,
                        ),
                        ft.Text(
                            f"{float(ms or 0):.1f} ms",
                            size=12.5,
                            weight=ft.FontWeight.W_600,
                            color=t["SECONDARY"],
                            width=74,
                            text_align=ft.TextAlign.RIGHT,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )

    return ft.Container(
        padding=14,
        border_radius=12,
        bgcolor=t["SUB_SURFACE"],
        border=ft.border.all(1.5, badge_col),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.COMPARE_ARROWS_ROUNDED, color=badge_col, size=20),
                        ft.Text(
                            f"⚖️ Hội chẩn Kép 2 Mô hình ({total_ms:.0f} ms)",
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color=t["TEXT"],
                            expand=True,
                        ),
                        ft.Container(
                            bgcolor=badge_col,
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                            border_radius=12,
                            content=ft.Text(
                                badge_text,
                                size=11.5,
                                weight=ft.FontWeight.BOLD,
                                color="#FFFFFF",
                            ),
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                *rows_ui,
                *(
                    [ft.Text(summary_text, size=12.5, color=t["SECONDARY"], weight=ft.FontWeight.W_500)]
                    if summary_text
                    else []
                ),
            ],
            spacing=8,
            tight=True,
        ),
    )


# --- Model Evaluation Lab (Benchmark Table, 10x10 Confusion Matrix Heatmap & Learning Curves) ---

SHORT_CLASS_LABELS_VI: dict[str, str] = {
    "Healthy": "Khỏe",
    "Infected_Bacterial_Erysipelas": "Đóng dấu",
    "Infected_Bacterial_Greasy_Pig_Disease": "Tiết dịch",
    "Infected_Environmental_Dermatitis": "VD môi tr.",
    "Infected_Environmental_Sunburn": "Cháy nắng",
    "Infected_Fungal_Pityriasis_Rosea": "Vảy phấn",
    "Infected_Fungal_Ringworm": "Nấm da",
    "Infected_Parasitic_Mange": "Ghẻ",
    "Infected_Viral_Foot_and_Mouth_Disease": "LMLM",
    "Infected_Viral_Swinepox": "Đậu heo",
}


def render_learning_curves_png(
    history: list[dict],
    best_epoch: int | None = None,
    dark: bool = False,
) -> tuple[bytes | None, bytes | None]:
    """
    Render 2 biểu đồ Learning Curves (PNG bytes) bằng Matplotlib (thread-safe FigureCanvasAgg):
      1. train_loss vs val_loss theo Epoch (kèm đường kẻ dọc tại best_epoch — Early Stopping)
      2. val_accuracy & val_macro_f1 (%) theo Epoch
    """
    if not history:
        return None, None
    try:
        from io import BytesIO
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except Exception:
        return None, None

    epochs = [int(r["epoch"]) for r in history]
    train_loss = [float(r["train_loss"]) for r in history]
    val_loss = [float(r["val_loss"]) for r in history]
    val_acc = [float(r["val_accuracy"]) * 100.0 for r in history]
    val_f1 = [float(r["val_macro_f1"]) * 100.0 for r in history]

    fig_bg = "#1E293B" if dark else "#FFFFFF"
    ax_bg = "#0F172A" if dark else "#F8FAFC"
    fg = "#F1F5F9" if dark else "#0F172A"
    muted = "#94A3B8" if dark else "#64748B"
    grid_col = "#334155" if dark else "#E2E8F0"

    def _style_ax(ax, title: str, ylabel: str):
        ax.set_facecolor(ax_bg)
        ax.set_title(title, fontsize=11, fontweight="bold", color=fg, pad=10)
        ax.set_xlabel("Epoch", fontsize=9.5, color=muted)
        ax.set_ylabel(ylabel, fontsize=9.5, color=muted)
        ax.tick_params(colors=muted, labelsize=8.5)
        for spine in ax.spines.values():
            spine.set_color(grid_col)
        ax.grid(True, linestyle="--", alpha=0.55, color=grid_col)

    def _to_png(fig: Figure) -> bytes:
        buf = BytesIO()
        FigureCanvasAgg(fig).print_png(buf)
        return buf.getvalue()

    # Chart 1: Train Loss vs Val Loss
    fig1 = Figure(figsize=(5.8, 3.3), dpi=135, facecolor=fig_bg)
    ax1 = fig1.add_subplot(111)
    _style_ax(ax1, "Loss theo Epoch (Train vs Validation)", "Cross-Entropy Loss")
    ax1.plot(epochs, train_loss, color="#38BDF8" if dark else "#0284C7", marker="o", markersize=3.5, linewidth=2.0, label="Train Loss")
    ax1.plot(epochs, val_loss, color="#FB923C" if dark else "#EA580C", marker="s", markersize=3.5, linewidth=2.0, label="Val Loss")
    if best_epoch and best_epoch in epochs:
        ax1.axvline(
            best_epoch,
            color="#10B981",
            linestyle="--",
            linewidth=1.6,
            label=f"Best Epoch #{best_epoch} (Early Stop)",
        )
    leg1 = ax1.legend(frameon=True, facecolor=fig_bg, edgecolor=grid_col, fontsize=8.5, loc="upper right")
    for txt in leg1.get_texts():
        txt.set_color(fg)
    fig1.tight_layout()
    loss_png = _to_png(fig1)

    # Chart 2: Val Accuracy & Val Macro-F1 (%)
    fig2 = Figure(figsize=(5.8, 3.3), dpi=135, facecolor=fig_bg)
    ax2 = fig2.add_subplot(111)
    _style_ax(ax2, "Hiệu năng Validation theo Epoch (%)", "Tỷ lệ (%)")
    ax2.plot(epochs, val_acc, color="#A78BFA" if dark else "#7C3AED", marker="o", markersize=3.5, linewidth=2.0, label="Val Accuracy (%)")
    ax2.plot(epochs, val_f1, color="#34D399" if dark else "#059669", marker="s", markersize=3.5, linewidth=2.2, label="Val Macro-F1 (%)")
    if best_epoch and best_epoch in epochs:
        idx_b = epochs.index(best_epoch)
        ax2.axvline(
            best_epoch,
            color="#F59E0B",
            linestyle="--",
            linewidth=1.6,
            label=f"Best Epoch #{best_epoch} (F1: {val_f1[idx_b]:.1f}%)",
        )
        ax2.scatter([best_epoch], [val_f1[idx_b]], color="#F59E0B", s=45, zorder=5)
    ax2.set_ylim(max(0.0, min(min(val_acc), min(val_f1)) - 6.0), min(100.0, max(max(val_acc), max(val_f1)) + 8.0))
    leg2 = ax2.legend(frameon=True, facecolor=fig_bg, edgecolor=grid_col, fontsize=8.5, loc="lower right")
    for txt in leg2.get_texts():
        txt.set_color(fg)
    fig2.tight_layout()
    metrics_png = _to_png(fig2)

    return loss_png, metrics_png


def build_model_evaluation_lab_card(page: ft.Page) -> ft.Control:
    """
    Phòng Thí nghiệm Đánh giá & Đối chứng Mô hình (Model Evaluation Lab):
      1. Bảng Benchmark So sánh tất cả các Checkpoint trong models/runs/*/
      2. Ma trận nhầm lẫn 10x10 (Confusion Matrix Heatmap) + Top 3 cặp bệnh dễ nhầm lẫn nhất
      3. Biểu đồ Learning Curves từ history.csv (train_loss vs val_loss & val_accuracy vs val_macro_f1)
    """
    from services.auth_service import is_dark_mode, make_dropdown, make_image, tech_card, theme_tokens
    from services.project_data import list_model_runs, load_run_evaluation

    t = theme_tokens(page)
    dark = is_dark_mode(page)
    runs = list_model_runs()
    if not runs:
        return tech_card(
            page=page,
            padding=24,
            content=_empty_chart_box(
                t,
                ft.Icons.ANALYTICS_OUTLINED,
                title="Chưa tìm thấy run huấn luyện nào trong models/runs/",
                subtitle="Hãy kiểm tra thư mục PigSkinTech/models/runs/ có đủ best_model.pt, config.json và final_metrics.json.",
            ),
        )

    active_item = next((r for r in runs if r.get("is_active")), runs[0])
    selected_run_state = {"name": active_item["run_name"]}

    # --- 1. Bảng Benchmark so sánh các Checkpoint ---
    bench_rows: list[ft.DataRow] = []
    for r in runs:
        is_act = bool(r.get("is_active"))
        vf1 = r.get("val_f1")
        tacc = r.get("test_acc")
        tf1 = r.get("test_macro_f1")
        status_chip = ft.Container(
            bgcolor=t["EMERALD_SOFT"] if is_act else t["SUB_SURFACE"],
            border=ft.border.all(1, "#10B981" if is_act else t["BORDER"]),
            padding=ft.padding.symmetric(horizontal=10, vertical=4),
            border_radius=12,
            content=ft.Text(
                "Đang kích hoạt" if is_act else "Dự phòng",
                size=12,
                weight=ft.FontWeight.BOLD,
                color=t["EMERALD"] if is_act else t["SECONDARY"],
            ),
        )
        bench_rows.append(
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(r.get("run_name") or ""), size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
                    ft.DataCell(ft.Text(str(r.get("model_label") or r.get("model")), size=13, weight=ft.FontWeight.W_600, color=t["CYAN"])),
                    ft.DataCell(ft.Text(str(r.get("seed") if r.get("seed") is not None else "—"), size=13, color=t["TEXT"])),
                    ft.DataCell(ft.Text(f"#{r.get('best_epoch')}" if r.get("best_epoch") else "—", size=13, color=t["TEXT"])),
                    ft.DataCell(ft.Text(f"{vf1 * 100:.2f}%" if isinstance(vf1, (int, float)) else "—", size=13, weight=ft.FontWeight.BOLD, color=t["EMERALD"])),
                    ft.DataCell(ft.Text(f"{tacc * 100:.2f}%" if isinstance(tacc, (int, float)) else "—", size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
                    ft.DataCell(ft.Text(f"{tf1 * 100:.2f}%" if isinstance(tf1, (int, float)) else "—", size=13, weight=ft.FontWeight.BOLD, color=t["CYAN"])),
                    ft.DataCell(ft.Text(f"{float(r.get('size_mb') or 0):.2f} MB", size=13, color=t["SECONDARY"])),
                    ft.DataCell(status_chip),
                ]
            )
        )

    benchmark_table = ft.DataTable(
        column_spacing=20,
        horizontal_margin=14,
        heading_row_height=46,
        data_row_min_height=48,
        data_row_max_height=56,
        heading_row_color=t["SUB_SURFACE"],
        columns=[
            ft.DataColumn(ft.Text("Run ID", size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
            ft.DataColumn(ft.Text("Kiến trúc", size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
            ft.DataColumn(ft.Text("Seed", size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
            ft.DataColumn(ft.Text("Best Epoch", size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
            ft.DataColumn(ft.Text("Val Macro-F1", size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
            ft.DataColumn(ft.Text("Test Accuracy", size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
            ft.DataColumn(ft.Text("Test Macro-F1", size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
            ft.DataColumn(ft.Text("Dung lượng .pt", size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
            ft.DataColumn(ft.Text("Trạng thái", size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
        ],
        rows=bench_rows,
    )

    detail_host = ft.Container()

    def _cell_style(val: int, is_diag: bool, row_total: int, max_off: int) -> tuple[str, str]:
        if is_diag:
            ratio = val / max(1, row_total)
            if ratio >= 0.80:
                return ("#059669", "#FFFFFF")
            if ratio >= 0.60:
                return ("#10B981", "#FFFFFF")
            if ratio >= 0.40:
                return ("#34D399" if not dark else "#047857", "#064E3B" if not dark else "#ECFDF5")
            return ("#A7F3D0" if not dark else "#065F46", "#064E3B" if not dark else "#D1FAE5")
        if val <= 0:
            return (t["SUB_SURFACE"], t["MUTED"])
        err_ratio = val / max(1, max_off)
        if err_ratio >= 0.65:
            return ("#DC2626", "#FFFFFF")
        if err_ratio >= 0.35:
            return ("#F97316", "#FFFFFF")
        return ("#FFEDD5" if not dark else "#7C2D12", "#9A3412" if not dark else "#FED7AA")

    def render_selected_run(e=None):
        cur_t = theme_tokens(page)
        cur_dark = is_dark_mode(page)
        ev = load_run_evaluation(selected_run_state["name"])
        if not ev:
            detail_host.content = _empty_chart_box(
                cur_t,
                ft.Icons.ERROR_OUTLINE_ROUNDED,
                title="Không đọc được dữ liệu đánh giá của Run này",
                subtitle="Kiểm tra file final_metrics.json trong thư mục run.",
            )
            if e is not None:
                page.update()
            return

        classes = ev.get("classes") or []
        cm = ev.get("confusion_matrix") or []
        top_confusions = ev.get("top_confusions") or []
        max_off = max((c["count"] for c in top_confusions), default=1)

        # --- 2. Ma trận nhầm lẫn 10x10 ---
        header_cells: list[ft.Control] = [
            ft.Container(
                width=104,
                height=38,
                alignment=ft.alignment.center_left,
                padding=ft.padding.symmetric(horizontal=6),
                content=ft.Text("Thực tế \\ Dự đoán", size=11, weight=ft.FontWeight.BOLD, color=cur_t["SECONDARY"]),
            )
        ]
        for idx, code in enumerate(classes):
            short_lbl = SHORT_CLASS_LABELS_VI.get(code, code[:8])
            header_cells.append(
                ft.Container(
                    width=72,
                    height=38,
                    alignment=ft.alignment.center,
                    tooltip=f"Dự đoán: {display_class(code)} ({code})",
                    bgcolor=cur_t["SUB_SURFACE"],
                    border_radius=6,
                    content=ft.Text(
                        short_lbl,
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=cur_t["TEXT"],
                        text_align=ft.TextAlign.CENTER,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                )
            )

        matrix_rows: list[ft.Control] = [ft.Row(header_cells, spacing=4)]
        for i, code in enumerate(classes):
            row_vals = cm[i] if i < len(cm) and isinstance(cm[i], list) else []
            row_total = sum(int(v or 0) for v in row_vals)
            short_lbl = SHORT_CLASS_LABELS_VI.get(code, code[:10])
            row_ctrls: list[ft.Control] = [
                ft.Container(
                    width=104,
                    height=34,
                    alignment=ft.alignment.center_left,
                    padding=ft.padding.symmetric(horizontal=6),
                    bgcolor=cur_t["SUB_SURFACE"],
                    border_radius=6,
                    tooltip=f"Nhãn thực tế: {display_class(code)} ({code}) • Tổng {row_total} ảnh test",
                    content=ft.Text(
                        short_lbl,
                        size=11.5,
                        weight=ft.FontWeight.BOLD,
                        color=cur_t["TEXT"],
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                )
            ]
            for j in range(len(classes)):
                val = int(row_vals[j] or 0) if j < len(row_vals) else 0
                bg_hex, fg_hex = _cell_style(val, i == j, row_total, max_off)
                pred_name = display_class(classes[j])
                true_name = display_class(code)
                row_ctrls.append(
                    ft.Container(
                        width=72,
                        height=34,
                        alignment=ft.alignment.center,
                        bgcolor=bg_hex,
                        border_radius=6,
                        border=ft.border.all(1.5, "#059669") if i == j else ft.border.all(0.5, cur_t["BORDER"]),
                        tooltip=f"Thực tế: {true_name} → AI đoán: {pred_name}: {val} ca",
                        content=ft.Text(
                            str(val),
                            size=12.5,
                            weight=ft.FontWeight.BOLD if (i == j or val > 0) else ft.FontWeight.NORMAL,
                            color=fg_hex,
                        ),
                    )
                )
            matrix_rows.append(ft.Row(row_ctrls, spacing=4))

        # Top-3 cặp bệnh dễ nhầm lẫn nhất
        top3_items = top_confusions[:3]
        if top3_items:
            top3_box = ft.Container(
                padding=14,
                border_radius=12,
                bgcolor=cur_t["AMBER_SOFT"] if cur_dark else "#FFF7ED",
                border=ft.border.all(1.2, "#F97316"),
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.TROUBLESHOOT_ROUNDED, color="#EA580C", size=20),
                                ft.Text(
                                    "🔍 Top 3 cặp bệnh dễ nhầm lẫn nhất (tập Test thực tế)",
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                    color="#FDBA74" if cur_dark else "#9A3412",
                                    expand=True,
                                ),
                            ],
                            spacing=8,
                        ),
                        ft.Row(
                            [
                                ft.Container(
                                    expand=True,
                                    padding=10,
                                    border_radius=10,
                                    bgcolor=cur_t["SURFACE"],
                                    border=ft.border.all(1, cur_t["BORDER"]),
                                    content=ft.Column(
                                        [
                                            ft.Text(
                                                f"#{idx} • {pair['count']} ca nhầm",
                                                size=13,
                                                weight=ft.FontWeight.W_800,
                                                color="#DC2626" if idx == 1 else "#D97706",
                                            ),
                                            ft.Text(
                                                f"{pair['true_name']} → {pair['pred_name']}",
                                                size=12.5,
                                                weight=ft.FontWeight.W_600,
                                                color=cur_t["TEXT"],
                                            ),
                                        ],
                                        spacing=2,
                                        tight=True,
                                    ),
                                )
                                for idx, pair in enumerate(top3_items, start=1)
                            ],
                            spacing=10,
                        ),
                    ],
                    spacing=8,
                    tight=True,
                ),
            )
        else:
            top3_box = ft.Text("Không ghi nhận cặp nhầm lẫn nào trên tập Test.", size=13, color=cur_t["EMERALD"])

        # --- 3. Biểu đồ Learning Curves (history.csv) ---
        if ev.get("has_history"):
            loss_png, met_png = render_learning_curves_png(ev["history"], ev.get("best_epoch"), dark=cur_dark)
            if loss_png and met_png:
                curves_content: ft.Control = ft.ResponsiveRow(
                    [
                        ft.Container(
                            col={"xs": 12, "lg": 6},
                            padding=10,
                            border_radius=12,
                            bgcolor=cur_t["SUB_SURFACE"],
                            border=ft.border.all(1, cur_t["BORDER"]),
                            content=ft.Column(
                                [
                                    ft.Text("Biểu đồ 1: Train Loss vs Validation Loss (Early Stopping)", size=13.5, weight=ft.FontWeight.BOLD, color=cur_t["TEXT"]),
                                    make_image(loss_png, width=None, height=290, border_radius=8, fit=ft.ImageFit.CONTAIN),
                                ],
                                spacing=6,
                                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                            ),
                        ),
                        ft.Container(
                            col={"xs": 12, "lg": 6},
                            padding=10,
                            border_radius=12,
                            bgcolor=cur_t["SUB_SURFACE"],
                            border=ft.border.all(1, cur_t["BORDER"]),
                            content=ft.Column(
                                [
                                    ft.Text("Biểu đồ 2: Validation Accuracy & Validation Macro-F1 (%)", size=13.5, weight=ft.FontWeight.BOLD, color=cur_t["TEXT"]),
                                    make_image(met_png, width=None, height=290, border_radius=8, fit=ft.ImageFit.CONTAIN),
                                ],
                                spacing=6,
                                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                            ),
                        ),
                    ],
                    spacing=14,
                    run_spacing=14,
                )
            else:
                curves_content = _empty_chart_box(
                    cur_t,
                    ft.Icons.SHOW_CHART_ROUNDED,
                    title="Không thể render biểu đồ Learning Curves",
                    subtitle="Kiểm tra cài đặt thư viện matplotlib trong môi trường Python.",
                )
        else:
            curves_content = _empty_chart_box(
                cur_t,
                ft.Icons.HISTORY_TOGGLE_OFF_ROUNDED,
                title=f"Run '{ev['run_name']}' không có tệp history.csv theo từng epoch",
                subtitle="Hãy chọn Run 20261103_125653 (MobileNetV2) hoặc 20261103_125004 (EfficientNet-B0) ở hộp chọn phía trên để xem đầy đủ Learning Curves.",
            )

        detail_host.content = ft.Column(
            [
                tech_card(
                    page=page,
                    padding=20,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.GRID_ON_ROUNDED, color="#10B981", size=22),
                                    ft.Text(
                                        f"2. Ma trận Nhầm lẫn 10×10 — {ev['model_label']} ({ev['run_name']})",
                                        size=17,
                                        weight=ft.FontWeight.BOLD,
                                        color=cur_t["TEXT"],
                                        expand=True,
                                    ),
                                    ft.Text(
                                        f"Test Acc: {(ev.get('test_accuracy') or 0)*100:.2f}% • Macro-F1: {(ev.get('test_macro_f1') or 0)*100:.2f}%",
                                        size=13,
                                        weight=ft.FontWeight.BOLD,
                                        color=cur_t["EMERALD"],
                                    ),
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Text(
                                "Ô đường chéo chính màu xanh lá biểu thị số ca dự đoán đúng; ô ngoài đường chéo màu cam/đỏ làm nổi bật các cặp bệnh dễ bị nhầm lẫn (rê chuột lên từng ô để xem tên bệnh đầy đủ).",
                                size=12.5,
                                color=cur_t["SECONDARY"],
                            ),
                            ft.Row([ft.Column(matrix_rows, spacing=4)], scroll=ft.ScrollMode.AUTO),
                            top3_box,
                        ],
                        spacing=12,
                    ),
                ),
                tech_card(
                    page=page,
                    padding=20,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.SHOW_CHART_ROUNDED, color="#0284C7", size=22),
                                    ft.Text(
                                        f"3. Biểu đồ Learning Curves theo Epoch (history.csv) — {ev['model_label']} ({ev['run_name']})",
                                        size=17,
                                        weight=ft.FontWeight.BOLD,
                                        color=cur_t["TEXT"],
                                        expand=True,
                                    ),
                                    ft.Text(
                                        f"{len(ev.get('history') or [])} epochs • Best Epoch #{ev.get('best_epoch') or '—'}",
                                        size=13,
                                        weight=ft.FontWeight.BOLD,
                                        color=cur_t["CYAN"],
                                    ),
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            curves_content,
                        ],
                        spacing=12,
                    ),
                ),
            ],
            spacing=16,
        )
        if e is not None:
            page.update()

    def on_run_select(e):
        selected_run_state["name"] = run_selector.value or active_item["run_name"]
        render_selected_run(e)

    run_selector = make_dropdown(
        label="Chọn Run để phân tích Ma trận Nhầm lẫn & Learning Curves",
        value=selected_run_state["name"],
        options=[
            (
                r["run_name"],
                f"{r['run_name']} • {r['model_label']} (Seed {r.get('seed')}) • Test Acc {(r.get('test_acc') or 0)*100:.1f}%"
                + (" [Active]" if r.get("is_active") else "")
                + ("" if r.get("has_history") else " • Không có history.csv"),
            )
            for r in runs
        ],
        on_change=on_run_select,
        expand=True,
        page=page,
    )

    render_selected_run()

    return ft.Column(
        [
            tech_card(
                page=page,
                padding=20,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.TABLE_CHART_ROUNDED, color=t["CYAN"], size=22),
                                ft.Text(
                                    f"1. Bảng Benchmark So sánh các Checkpoint ({len(runs)} runs thực tế trong models/runs/)",
                                    size=17,
                                    weight=ft.FontWeight.BOLD,
                                    color=t["TEXT"],
                                    expand=True,
                                ),
                            ],
                            spacing=8,
                        ),
                        ft.Row([benchmark_table], scroll=ft.ScrollMode.AUTO),
                        ft.Divider(height=8, color=t["BORDER"]),
                        ft.Row([run_selector]),
                    ],
                    spacing=12,
                ),
            ),
            detail_host,
        ],
        spacing=16,
    )


# Re-export A4 Report & QR Code helpers for convenient clinical module imports
from services.auth_service import (  # noqa: E402, F401
    build_qr_payload,
    build_vet_report_html_doc,
    export_vet_report_html,
    generate_qr_png_base64,
    save_vet_report_with_picker,
)
