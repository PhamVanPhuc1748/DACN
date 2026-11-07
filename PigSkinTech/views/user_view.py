"""User Role View (/user - Người chăn nuôi): Modern SaaS / Shadcn-UI & Tailwind Style Veterinary Clinic."""
import asyncio

import flet as ft

from services.auth_service import (
    build_role_shell,
    create_file_picker,
    ensure_flet_compat,
    header_stat_pill,
    make_dropdown,
    make_image,
    open_image_zoom_dialog,
    pick_image_files,
    preview_thumbnail_with_zoom,
    show_snack,
    tech_banner,
    tech_card,
    theme_tokens,
)
from services.inference import inspect_image, predict
from services.project_data import display_class, get_class_info, list_class_keys, load_classes_config
from services.store import (
    get_sample_gallery,
    list_user_inspections,
    request_expert_review,
    save,
)
from theme import (
    BG_CARD,
    BG_MAIN,
    BORDER_LIGHT,
    PRIMARY,
    PRIMARY_DARK,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    css_card,
    css_input,
    css_shadow,
    make_smooth_animation,
)


DANGER_COLORS = {
    "An toàn": PRIMARY_DARK,
    "Thấp": "#0284C7",
    "Trung bình": "#D97706",
    "Cao": "#DC2626",
    "Khẩn cấp": "#DC2626",
}

SHORT_SAMPLE_LABELS = [
    "Mẫu 1: Đóng dấu",
    "Mẫu 2: Ghẻ",
    "Mẫu 3: Viêm da",
    "Mẫu 4: Nấm",
    "Mẫu 5: Khỏe mạnh",
]

QUICK_SYMPTOM_CHIPS = [
    ("🔥 Sốt cao, bỏ ăn", "Sốt cao, bỏ ăn"),
    ("🐾 Ngứa, cọ vách chuồng", "Ngứa, cọ vách chuồng"),
    ("🔴 Nổi mảng đỏ hình thoi", "Nổi mảng đỏ hình thoi"),
    ("💧 Da rỉ dịch nhờn", "Da rỉ dịch nhờn"),
    ("⚪ Đóng vảy trắng", "Đóng vảy trắng"),
]

TOP3_BAR_COLORS = [PRIMARY_DARK, "#0284C7", "#D97706"]


def _danger_badge_spec(danger_level: str) -> tuple[str, str, str]:
    """Return (badge_text, text_color, bg_color) for the clinical danger badge."""
    if danger_level in ("An toàn", "Thấp"):
        return ("🟢 An toàn", PRIMARY_DARK, "#ECFDF5")
    if danger_level == "Trung bình":
        return ("🟠 Cảnh báo", "#D97706", "#FFFBEB")
    return ("🔴 Nguy hiểm - Cần cách ly", "#DC2626", "#FEE2E2")


def _confidence_color(conf: float) -> str:
    if conf >= 0.80:
        return PRIMARY_DARK
    if conf >= 0.60:
        return "#D97706"
    return "#DC2626"


def build_user_view(page: ft.Page, user: dict) -> ft.Control:
    ensure_flet_compat(page)
    t = theme_tokens(page)
    picker = create_file_picker(page)
    state = {
        "image_path": None,
        "image_info": None,
        "result": None,
        "record_id": None,
        "sent_to_expert": False,
        "wiki_triage": "all",
    }

    animal_field = css_input(
        label="Mã đàn / cá thể",
        hint_text="VD: PIG-101",
        prefix_icon=ft.Icons.PETS_ROUNDED,
        expand=True,
    )
    farm_field = css_input(
        label="Khu chuồng",
        hint_text="VD: Khu A - Chuồng 02",
        prefix_icon=ft.Icons.HOME_WORK_OUTLINED,
        expand=True,
    )
    symptoms_field = css_input(
        label="Triệu chứng ghi nhận",
        hint_text="Chọn nhanh các biểu hiện bên trên hoặc nhập mô tả chi tiết...",
        multiline=True,
        min_lines=2,
        max_lines=2,
        expand=True,
    )

    header_host = ft.Container()
    dropzone_host = ft.Container()
    sample_gallery_host = ft.Container()
    symptom_chips_row = ft.Row(spacing=6, wrap=True)
    loading_bar = ft.ProgressBar(visible=False, color=PRIMARY)
    right_card_host = ft.Container(expand=1)

    def refresh_page_header():
        records = list_user_inspections(user.get("email", ""))
        total_scans = len(records)
        confs = [float(r["confidence"]) for r in records if r.get("confidence") is not None]
        avg_conf = (sum(confs) / len(confs) * 100.0) if confs else 0.0
        sent_expert = sum(
            1 for r in records if int(r.get("requested_review") or 0) == 1 or r.get("review_status") == "reviewed"
        )
        pills = [
            header_stat_pill(
                "Tổng lượt khám",
                str(total_scans),
                ft.Icons.QR_CODE_SCANNER_ROUNDED,
                accent=PRIMARY_DARK,
                soft_bg="#ECFDF5",
                badge_text="+12% hôm nay",
                page=page,
            ),
            header_stat_pill(
                "Độ tin cậy AI",
                f"{avg_conf:.1f}%",
                ft.Icons.AUTO_GRAPH_ROUNDED,
                accent="#0284C7",
                soft_bg="#EFF6FF",
                badge_text="Hoạt động tốt",
                page=page,
            ),
            header_stat_pill(
                "Gửi Bác sĩ Thú y",
                str(sent_expert),
                ft.Icons.MEDICAL_SERVICES_ROUNDED,
                accent="#D97706",
                soft_bg="#FFFBEB",
                badge_text="Hội chẩn nhanh",
                page=page,
            ),
        ]
        header_host.content = tech_banner(
            "Chẩn đoán Bệnh Da Heo",
            "Phân tích hình ảnh tổn thương da bằng Trí tuệ nhân tạo PigSkin AI & nhận phác đồ thú y",
            pills=pills,
            page=page,
        )

    def append_symptom_chip(symptom_text: str):
        current = (symptoms_field.value or "").strip()
        if not current:
            symptoms_field.value = symptom_text
        elif symptom_text.lower() not in current.lower():
            sep = ", " if not current.endswith((",", ".", ";")) else " "
            symptoms_field.value = f"{current}{sep}{symptom_text}"
        render_symptom_chips()
        page.update()

    def render_symptom_chips():
        current_lower = (symptoms_field.value or "").lower()
        symptom_chips_row.controls.clear()
        for chip_label, phrase in QUICK_SYMPTOM_CHIPS:
            active = phrase.lower() in current_lower
            symptom_chips_row.controls.append(
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    border_radius=16,
                    bgcolor="#ECFDF5" if active else BG_MAIN,
                    border=ft.border.all(1, PRIMARY if active else BORDER_LIGHT),
                    ink=True,
                    on_click=lambda e, p=phrase: append_symptom_chip(p),
                    content=ft.Text(
                        chip_label,
                        size=11,
                        weight=ft.FontWeight.W_600 if active else ft.FontWeight.W_500,
                        color=PRIMARY_DARK if active else TEXT_PRIMARY,
                    ),
                )
            )

    def render_dropzone():
        info = state["image_info"]
        if state["image_path"] and info:
            dropzone_host.content = ft.Container(
                height=220,
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                    colors=["#F0FDF4", "#ECFDF5"],
                ),
                border=ft.border.all(1.5, "#86EFAC"),
                border_radius=16,
                padding=6,
                alignment=ft.alignment.center,
                animate=make_smooth_animation(200),
                content=ft.Stack(
                    expand=True,
                    controls=[
                        ft.Container(
                            alignment=ft.alignment.center,
                            content=make_image(
                                state["image_path"],
                                width=480,
                                height=204,
                                border_radius=12,
                                fit=getattr(ft.ImageFit, "COVER", None),
                            ),
                        ),
                        ft.Container(
                            right=10,
                            top=10,
                            content=ft.Row(
                                [
                                    ft.Container(
                                        bgcolor=ft.Colors.with_opacity(0.92, BG_CARD),
                                        border=ft.border.all(1, BORDER_LIGHT),
                                        border_radius=8,
                                        padding=ft.padding.symmetric(horizontal=10, vertical=6),
                                        ink=True,
                                        on_click=handle_choose_file,
                                        content=ft.Row(
                                            [
                                                ft.Icon(ft.Icons.CHANGE_CIRCLE_OUTLINED, size=15, color=TEXT_PRIMARY),
                                                ft.Text("Đổi ảnh khác", size=11, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600),
                                            ],
                                            spacing=4,
                                            tight=True,
                                        ),
                                    ),
                                    ft.Container(
                                        bgcolor=ft.Colors.with_opacity(0.88, TEXT_PRIMARY),
                                        border_radius=8,
                                        padding=ft.padding.symmetric(horizontal=10, vertical=6),
                                        ink=True,
                                        on_click=lambda e: open_image_zoom_dialog(page, state["image_path"], info["name"]),
                                        content=ft.Row(
                                            [
                                                ft.Icon(ft.Icons.ZOOM_IN_ROUNDED, size=15, color="#34D399"),
                                                ft.Text("Phóng to", size=11, color="#FFFFFF", weight=ft.FontWeight.W_600),
                                            ],
                                            spacing=4,
                                            tight=True,
                                        ),
                                    ),
                                ],
                                spacing=6,
                                tight=True,
                            ),
                        ),
                    ],
                ),
            )
        else:
            upload_icon_box = ft.Container(
                width=54,
                height=54,
                bgcolor="#FFFFFF",
                border_radius=27,
                border=ft.border.all(1, "#A7F3D0"),
                alignment=ft.alignment.center,
                scale=1.0,
                animate_scale=make_smooth_animation(200),
                shadow=css_shadow(0.06, 12, 3),
                content=ft.Icon(ft.Icons.ADD_A_PHOTO_OUTLINED, size=26, color=PRIMARY_DARK),
            )

            def on_dropzone_hover(e):
                hovered = str(getattr(e, "data", "")).lower() == "true"
                e.control.gradient = ft.LinearGradient(
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                    colors=["#DCFCE7", "#D1FAE5"] if hovered else ["#F0FDF4", "#ECFDF5"],
                )
                e.control.border = ft.border.all(2 if hovered else 1.5, PRIMARY if hovered else "#86EFAC")
                upload_icon_box.scale = 1.12 if hovered else 1.0
                e.control.update()

            dropzone_host.content = ft.Container(
                height=220,
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                    colors=["#F0FDF4", "#ECFDF5"],
                ),
                border=ft.border.all(1.5, "#86EFAC"),
                border_radius=16,
                alignment=ft.alignment.center,
                animate=make_smooth_animation(200),
                ink=True,
                on_click=handle_choose_file,
                on_hover=on_dropzone_hover,
                content=ft.Column(
                    [
                        upload_icon_box,
                        ft.Text("Nhấn để tải ảnh vùng da heo cần kiểm tra", size=14, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                        ft.Text("Hỗ trợ ảnh chụp rõ nét từ điện thoại hoặc máy ảnh (JPG, PNG, WEBP)", size=12, color=TEXT_SECONDARY),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
            )

    def load_sample_case(sample: dict):
        try:
            info = inspect_image(sample["path"])
            state.update(image_path=sample["path"], image_info=info, result=None, record_id=None, sent_to_expert=False)
            animal_field.value = sample.get("animal_id", "PIG-101")
            farm_field.value = sample.get("farm_name", "Trại An Phú - Khu A")
            symptoms_field.value = sample.get("symptoms", "")
            render_dropzone()
            render_sample_gallery()
            render_symptom_chips()
            render_right_card()
            page.update()
        except Exception as err:
            show_snack(page, str(err), "#DC2626")

    def render_sample_gallery():
        samples = get_sample_gallery()
        thumbs = []

        def on_sample_hover(e, is_sel: bool):
            hovered = str(getattr(e, "data", "")).lower() == "true"
            active = hovered or is_sel
            e.control.border = ft.border.all(2 if active else 1, PRIMARY if active else BORDER_LIGHT)
            e.control.shadow = css_shadow(0.10, 18, 4) if active else None
            e.control.update()

        for idx, s in enumerate(samples[:5]):
            short_title = SHORT_SAMPLE_LABELS[idx] if idx < len(SHORT_SAMPLE_LABELS) else s["title"]
            is_selected = state["image_path"] == s["path"]
            thumbs.append(
                ft.Container(
                    width=105,
                    padding=6,
                    bgcolor=BG_CARD,
                    border=ft.border.all(2 if is_selected else 1, PRIMARY if is_selected else BORDER_LIGHT),
                    border_radius=12,
                    shadow=css_shadow(0.10, 18, 4) if is_selected else None,
                    animate=make_smooth_animation(200),
                    ink=True,
                    tooltip=s["title"],
                    on_click=lambda e, item=s: load_sample_case(item),
                    on_hover=lambda e, sel=is_selected: on_sample_hover(e, sel),
                    content=ft.Column(
                        [
                            make_image(s["path"], width=91, height=56, border_radius=8, fit=ft.ImageFit.COVER),
                            ft.Text(
                                short_title,
                                size=10,
                                weight=ft.FontWeight.W_600,
                                color=PRIMARY_DARK if is_selected else TEXT_PRIMARY,
                                no_wrap=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=4,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        tight=True,
                    ),
                )
            )
        sample_gallery_host.content = ft.Column(
            [
                ft.Text("Hoặc chọn nhanh mẫu thử:", size=12, weight=ft.FontWeight.W_600, color=TEXT_SECONDARY),
                ft.Row(thumbs, spacing=8, wrap=True),
            ],
            spacing=6,
            tight=True,
        )

    def handle_send_to_expert(e):
        if not state["record_id"]:
            show_snack(page, "Vui lòng phân tích ảnh trước khi gửi Bác sĩ Thú y.", "#DC2626")
            return
        request_expert_review(state["record_id"])
        state["sent_to_expert"] = True
        refresh_page_header()
        render_right_card()
        show_snack(page, f"Đã gửi hồ sơ PS-{state['record_id']:06d} tới Bác sĩ Thú y thẩm định!", "#0284C7")
        page.update()

    def _build_recent_3_list() -> list[ft.Control]:
        records = list_user_inspections(user.get("email", ""))[:3]
        if not records:
            return [ft.Text("Chưa có lịch sử khám gần đây.", size=12, color=TEXT_MUTED)]
        rows = []
        for rec in records:
            conf = float(rec.get("confidence") or 0.0)
            final_cls = rec.get("expert_label") or rec.get("predicted_class")
            is_rev = rec.get("review_status") == "reviewed"
            rows.append(
                ft.Container(
                    padding=10,
                    bgcolor=BG_MAIN,
                    border_radius=12,
                    border=ft.border.all(1, BORDER_LIGHT),
                    content=ft.Row(
                        [
                            preview_thumbnail_with_zoom(
                                page,
                                rec.get("image_path"),
                                f"{rec.get('case_id')} • {display_class(final_cls)}",
                                width=48,
                                height=48,
                                border_radius=8,
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        display_class(final_cls),
                                        size=12,
                                        weight=ft.FontWeight.BOLD,
                                        color=TEXT_PRIMARY,
                                        no_wrap=True,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(
                                        f"Mã đàn: {rec.get('animal_id') or '—'} • Độ tin cậy: {conf*100:.1f}%",
                                        size=11,
                                        color=TEXT_SECONDARY,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Container(
                                bgcolor="#ECFDF5" if is_rev else "#FFFBEB",
                                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                border_radius=8,
                                content=ft.Text(
                                    "Đã thẩm định" if is_rev else "Chờ duyệt",
                                    size=10,
                                    color=PRIMARY_DARK if is_rev else "#D97706",
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ),
                        ],
                        spacing=10,
                    ),
                )
            )
        return rows

    def render_right_card():
        res = state["result"]

        # STANDBY STATE: Clean centered Hero + 3 steps + 3 recent inspections in 1 cohesive Card
        if not res:
            step_items = [
                ("1. Tải ảnh", "Chọn ảnh vùng da heo hoặc bấm vào mẫu thử"),
                ("2. Chọn triệu chứng", "Ghi nhận biểu hiện lâm sàng tại chuồng"),
                ("3. Nhận phác đồ", "Xem kết quả AI & hướng xử lý thú y"),
            ]
            steps_row = ft.Row(
                [
                    ft.Container(
                        expand=True,
                        padding=12,
                        bgcolor=BG_MAIN,
                        border_radius=12,
                        border=ft.border.all(1, BORDER_LIGHT),
                        content=ft.Column(
                            [
                                ft.Text(st_title, size=12, weight=ft.FontWeight.BOLD, color=PRIMARY_DARK),
                                ft.Text(st_desc, size=11, color=TEXT_SECONDARY),
                            ],
                            spacing=3,
                            tight=True,
                        ),
                    )
                    for st_title, st_desc in step_items
                ],
                spacing=10,
            )

            right_card_host.content = css_card(
                padding=24,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.MEDICAL_INFORMATION_ROUNDED, color=PRIMARY_DARK, size=20),
                                ft.Text("Kết quả Phân tích & Phác đồ Thú y", size=16, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY, expand=True),
                            ],
                            spacing=8,
                        ),
                        ft.Container(
                            padding=ft.padding.symmetric(vertical=22, horizontal=16),
                            bgcolor=BG_MAIN,
                            border_radius=14,
                            border=ft.border.all(1, BORDER_LIGHT),
                            alignment=ft.alignment.center,
                            content=ft.Column(
                                [
                                    ft.Container(
                                        width=60,
                                        height=60,
                                        border_radius=30,
                                        bgcolor="#ECFDF5",
                                        alignment=ft.alignment.center,
                                        content=ft.Icon(ft.Icons.BIOTECH_ROUNDED, size=32, color=PRIMARY_DARK),
                                    ),
                                    ft.Text(
                                        "Sẵn sàng phân tích mẫu da heo",
                                        size=17,
                                        weight=ft.FontWeight.BOLD,
                                        color=TEXT_PRIMARY,
                                    ),
                                    ft.Text(
                                        "Trí tuệ nhân tạo PigSkin AI sẽ đánh giá tổn thương da và gợi ý hướng xử lý tức thì.",
                                        size=12,
                                        color=TEXT_SECONDARY,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=6,
                                tight=True,
                            ),
                        ),
                        steps_row,
                        ft.Text("3 lần khám gần nhất", size=13, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                        *_build_recent_3_list(),
                    ],
                    spacing=14,
                ),
            )
            return

        # RESULT STATE: Danger badge + Disease title + Top-3 Probability Bars + 2-part Protocol Box + Vet CTA
        danger = res.get("danger_level", "Trung bình")
        badge_label, badge_fg, badge_bg = _danger_badge_spec(danger)
        disease_name = res.get("display_label") or display_class(res.get("label"))
        cls_info = get_class_info(res.get("label"))
        isolation_guide = cls_info.get("prevention") or "Cách ly cá thể nghi nhiễm, vệ sinh sát trùng chuồng trại và theo dõi thân nhiệt."
        treatment_guide = res.get("recommendation") or cls_info.get("treatment") or "Tham khảo ý kiến Bác sĩ Thú y trước khi dùng kháng sinh đặc hiệu."

        top3_bars = []
        for idx, s in enumerate((res.get("scores") or [])[:3]):
            s_conf = float(s.get("confidence") or 0.0)
            bar_color = TOP3_BAR_COLORS[idx] if idx < len(TOP3_BAR_COLORS) else TEXT_SECONDARY
            top3_bars.append(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    f"#{idx + 1}  {display_class(s['label'])}",
                                    size=12,
                                    weight=ft.FontWeight.BOLD if idx == 0 else ft.FontWeight.W_500,
                                    color=TEXT_PRIMARY,
                                    expand=True,
                                ),
                                ft.Text(
                                    f"{s_conf * 100:.1f}%",
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=bar_color,
                                ),
                            ]
                        ),
                        ft.ProgressBar(value=s_conf, bar_height=8, color=bar_color, bgcolor=BORDER_LIGHT),
                    ],
                    spacing=4,
                )
            )

        expert_cta = (
            ft.Container(
                bgcolor="#EFF6FF",
                border=ft.border.all(1, "#38BDF8"),
                padding=12,
                border_radius=12,
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color="#0284C7", size=18),
                        ft.Text(
                            f"Đã gửi hồ sơ PS-{state['record_id']:06d} tới Bác sĩ Thú y thẩm định.",
                            size=12,
                            color="#0284C7",
                            weight=ft.FontWeight.BOLD,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                ),
            )
            if state["sent_to_expert"]
            else ft.Container(
                width=float("inf"),
                height=46,
                border_radius=12,
                bgcolor="#0284C7",
                alignment=ft.alignment.center,
                ink=True,
                on_click=handle_send_to_expert,
                content=ft.Text(
                    "👨‍⚕️ Gửi Bác sĩ Thú y thẩm định ca này",
                    size=14,
                    weight=ft.FontWeight.BOLD,
                    color="#FFFFFF",
                ),
            )
        )

        right_card_host.content = css_card(
            padding=24,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.MEDICAL_INFORMATION_ROUNDED, color=PRIMARY_DARK, size=20),
                            ft.Text("Kết quả Phân tích & Phác đồ Thú y", size=16, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY, expand=True),
                            ft.Container(
                                bgcolor=badge_bg,
                                border=ft.border.all(1, badge_fg),
                                padding=ft.padding.symmetric(horizontal=12, vertical=5),
                                border_radius=20,
                                content=ft.Text(badge_label, size=11, color=badge_fg, weight=ft.FontWeight.BOLD),
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Column(
                        [
                            ft.Text("Kết luận chẩn đoán từ Trí tuệ nhân tạo PigSkin AI:", size=12, color=TEXT_SECONDARY),
                            ft.Text(disease_name, size=22, weight=ft.FontWeight.BOLD, color=badge_fg),
                        ],
                        spacing=2,
                    ),
                    ft.Container(
                        padding=14,
                        bgcolor=BG_MAIN,
                        border_radius=12,
                        border=ft.border.all(1, BORDER_LIGHT),
                        content=ft.Column(
                            [
                                ft.Text("Biểu đồ Top-3 Khả năng:", size=12, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                                *top3_bars,
                            ],
                            spacing=8,
                        ),
                    ),
                    ft.Container(
                        padding=14,
                        bgcolor="#ECFDF5",
                        border_radius=12,
                        border=ft.border.all(1, "#A7F3D0"),
                        content=ft.Column(
                            [
                                ft.Text("🛡️ Cách xử lý & Cách ly tại chuồng", size=13, weight=ft.FontWeight.BOLD, color="#065F46"),
                                ft.Text(isolation_guide, size=12, color="#064E3B"),
                                ft.Text("💊 Gợi ý điều trị / Thuốc tham khảo", size=13, weight=ft.FontWeight.BOLD, color="#065F46"),
                                ft.Text(treatment_guide, size=12, color="#064E3B"),
                            ],
                            spacing=6,
                        ),
                    ),
                    expert_cta,
                ],
                spacing=14,
            ),
        )

    def on_files_selected(paths: list[str]):
        if not paths:
            return
        p = paths[0]
        try:
            info = inspect_image(p)
            state.update(image_path=p, image_info=info, result=None, record_id=None, sent_to_expert=False)
            render_dropzone()
            render_sample_gallery()
            render_right_card()
            page.update()
        except Exception as err:
            show_snack(page, str(err), "#DC2626")

    async def handle_choose_file(e):
        await pick_image_files(picker, allow_multiple=False, on_picked=on_files_selected)

    async def handle_run_predict(e):
        if not state["image_path"]:
            show_snack(page, "Vui lòng tải ảnh da heo hoặc chọn 1 mẫu thử bên dưới.", "#DC2626")
            return
        loading_bar.visible = True
        page.update()
        try:
            res = await asyncio.to_thread(predict, state["image_path"])
            info = state["image_info"] or inspect_image(state["image_path"])
            auto_review = 1 if float(res.get("confidence") or 0.0) < 0.75 else 0
            rid = save(
                info,
                res,
                case={
                    "animal_id": animal_field.value or "PIG-NEW",
                    "farm_name": farm_field.value or "Trại chăn nuôi",
                    "symptoms": symptoms_field.value or "",
                    "user_id": user.get("user_id", 1),
                    "user_email": user.get("email", ""),
                    "user_name": user.get("full_name", ""),
                    "requested_review": auto_review,
                },
                source_image=state["image_path"],
            )
            state.update(result=res, record_id=rid, sent_to_expert=bool(auto_review))
            refresh_page_header()
            render_right_card()
        except Exception as err:
            show_snack(page, f"Không thể phân tích ảnh: {err}", "#DC2626")
        finally:
            loading_bar.visible = False
            page.update()

    # Tab 1: Predict (2 balanced 5:5 cards fitting neatly in 1 screen)
    def build_predict_tab():
        refresh_page_header()
        render_dropzone()
        render_sample_gallery()
        render_symptom_chips()
        render_right_card()

        cta_analyze_btn = ft.Container(
            width=float("inf"),
            height=50,
            border_radius=12,
            bgcolor=PRIMARY_DARK,
            alignment=ft.alignment.center,
            ink=True,
            on_click=handle_run_predict,
            shadow=ft.BoxShadow(
                blur_radius=16,
                color=ft.Colors.with_opacity(0.24, PRIMARY_DARK),
                offset=ft.Offset(0, 4),
            ),
            content=ft.Text(
                "⚡ Phân tích Chẩn đoán AI",
                size=15,
                weight=ft.FontWeight.BOLD,
                color="#FFFFFF",
            ),
        )

        left_card = css_card(
            expand=1,
            padding=24,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CAMERA_ENHANCE_ROUNDED, color=PRIMARY_DARK, size=20),
                            ft.Text("Thu thập Hình ảnh & Triệu chứng", size=16, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY, expand=True),
                        ],
                        spacing=8,
                    ),
                    dropzone_host,
                    sample_gallery_host,
                    ft.Row([animal_field, farm_field], spacing=12),
                    ft.Column(
                        [
                            ft.Text("Chọn nhanh biểu hiện lâm sàng:", size=12, weight=ft.FontWeight.W_600, color=TEXT_SECONDARY),
                            symptom_chips_row,
                        ],
                        spacing=6,
                        tight=True,
                    ),
                    symptoms_field,
                    loading_bar,
                    cta_analyze_btn,
                ],
                spacing=12,
            ),
        )

        return [
            header_host,
            ft.Row(
                [
                    left_card,
                    right_card_host,
                ],
                spacing=20,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
        ]

    # Tab 2: History
    def build_history_tab():
        date_input = css_input(
            label="Tìm theo ngày khám (YYYY-MM-DD)",
            hint_text="VD: 2026-11",
            prefix_icon=ft.Icons.CALENDAR_TODAY_ROUNDED,
            width=260,
        )
        disease_options = [("all", "Tất cả nhóm bệnh lý")] + [
            (code, display_class(code)) for code in list_class_keys()
        ]
        list_host = ft.Column(spacing=16)

        def refresh_history(e=None):
            d_val = disease_dropdown.value or "all"
            records = list_user_inspections(user.get("email", ""), date_input.value or "", d_val)
            list_host.controls.clear()
            if not records:
                list_host.controls.append(
                    css_card(
                        padding=24,
                        content=ft.Text("Không có lịch sử khám nào khớp bộ lọc.", size=13, color=TEXT_MUTED),
                    )
                )
            for rec in records:
                is_reviewed = rec.get("review_status") == "reviewed"
                status_text = "Đã được Bác sĩ Thú y xác nhận" if is_reviewed else "Đang chờ duyệt"
                status_color = PRIMARY_DARK if is_reviewed else "#D97706"
                final_code = rec.get("expert_label") or rec.get("predicted_class")
                conf = float(rec.get("confidence") or 0.0)
                conf_col = _confidence_color(conf)

                expert_feedback = (
                    ft.Container(
                        bgcolor="#ECFDF5",
                        border=ft.border.all(1, "#A7F3D0"),
                        padding=12,
                        border_radius=10,
                        content=ft.Column(
                            [
                                ft.Text(
                                    f"Kết luận Bác sĩ Thú y ({rec.get('reviewed_by') or 'BS. Thú y'}): {display_class(final_code)}",
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=PRIMARY_DARK,
                                ),
                                ft.Text(
                                    f"Phác đồ điều trị: {rec.get('expert_note') or rec.get('recommendation')}",
                                    size=12,
                                    color="#064E3B",
                                ),
                            ],
                            spacing=4,
                        ),
                    )
                    if is_reviewed
                    else ft.Row(
                        [
                            ft.Text(
                                f"Hướng xử lý sơ bộ: {rec.get('recommendation') or 'Theo dõi thêm'}",
                                size=12,
                                color=TEXT_SECONDARY,
                                expand=True,
                            ),
                            ft.OutlinedButton(
                                "Đã gửi Bác sĩ Thú y" if rec.get("requested_review") else "Nhờ Bác sĩ Thú y duyệt",
                                icon=ft.Icons.SEND_ROUNDED,
                                disabled=bool(rec.get("requested_review")),
                                on_click=lambda e, rid=rec["id"]: (
                                    request_expert_review(rid),
                                    refresh_history(),
                                    show_snack(page, f"Đã gửi hồ sơ PS-{rid:06d} tới Bác sĩ Thú y!", "#0284C7"),
                                ),
                            ),
                        ]
                    )
                )

                list_host.controls.append(
                    css_card(
                        padding=24,
                        content=ft.Row(
                            [
                                preview_thumbnail_with_zoom(
                                    page,
                                    rec.get("image_path"),
                                    f"{rec.get('case_id')} • {display_class(final_code)}",
                                    width=88,
                                    height=88,
                                ),
                                ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Text(
                                                    f"{rec.get('case_id')} • {rec.get('animal_id') or 'Heo'} ({rec.get('farm_name') or 'Trang trại'})",
                                                    size=14,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=TEXT_PRIMARY,
                                                    expand=True,
                                                ),
                                                ft.Container(
                                                    bgcolor=status_color,
                                                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                                                    border_radius=12,
                                                    content=ft.Text(status_text, size=11, color="#FFFFFF", weight=ft.FontWeight.BOLD),
                                                ),
                                            ]
                                        ),
                                        ft.Row(
                                            [
                                                ft.Text(
                                                    f"Kết quả PigSkin AI: {display_class(rec.get('predicted_class'))} ({conf*100:.1f}%)",
                                                    size=12,
                                                    weight=ft.FontWeight.W_600,
                                                    color=conf_col,
                                                    expand=True,
                                                ),
                                                ft.Text(f"Ngày khám: {rec.get('created_at')}", size=11, color=TEXT_MUTED),
                                            ]
                                        ),
                                        ft.ProgressBar(value=conf, bar_height=6, color=conf_col, bgcolor=BORDER_LIGHT),
                                        expert_feedback,
                                    ],
                                    spacing=6,
                                    expand=True,
                                ),
                            ],
                            spacing=16,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                    )
                )
            page.update()

        disease_dropdown = make_dropdown(
            "Lọc theo nhóm bệnh",
            "all",
            disease_options,
            on_change=refresh_history,
            width=280,
        )
        date_input.on_change = refresh_history
        refresh_history()

        return [
            tech_banner(
                "Lịch sử Khám & Phác đồ Thú y",
                "Theo dõi kết quả thẩm định từ Bác sĩ Thú y cho từng cá thể trong đàn",
                badge_text="Hồ sơ phòng khám",
                page=page,
            ),
            css_card(
                padding=20,
                content=ft.Row(
                    [
                        date_input,
                        disease_dropdown,
                        ft.OutlinedButton("Làm mới", icon=ft.Icons.REFRESH_ROUNDED, on_click=refresh_history),
                    ],
                    spacing=12,
                ),
            ),
            list_host,
        ]

    # Tab 3: Wiki (Human-friendly Veterinary Knowledge Base)
    def build_wiki_tab():
        search_box = css_input(
            label="Tìm kiếm tên bệnh, triệu chứng hoặc hướng điều trị...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            expand=True,
        )
        triage_chips_row = ft.Row(spacing=8, wrap=True)
        cards_col = ft.Column(spacing=16)

        triage_defs = [
            ("all", "Tất cả bệnh lý", PRIMARY_DARK),
            ("urgent", "Nguy hiểm - Cần cách ly", "#DC2626"),
            ("medium", "Cảnh báo trung bình", "#D97706"),
            ("low", "An toàn / Nhẹ", "#0284C7"),
        ]

        def set_triage(key: str):
            state["wiki_triage"] = key
            render_wiki()

        def render_wiki(e=None):
            q = (search_box.value or "").strip().lower()
            cur_t = state["wiki_triage"]
            triage_chips_row.controls.clear()
            for t_key, t_label, t_col in triage_defs:
                active = cur_t == t_key
                triage_chips_row.controls.append(
                    ft.Container(
                        bgcolor=t_col if active else BG_CARD,
                        border=ft.border.all(1, t_col if active else BORDER_LIGHT),
                        padding=ft.padding.symmetric(horizontal=12, vertical=7),
                        border_radius=18,
                        ink=True,
                        on_click=lambda ev, k=t_key: set_triage(k),
                        content=ft.Text(
                            t_label,
                            size=11,
                            color="#FFFFFF" if active else TEXT_PRIMARY,
                            weight=ft.FontWeight.BOLD if active else ft.FontWeight.W_500,
                        ),
                    )
                )

            cfg = load_classes_config()
            cards_col.controls.clear()
            for code, info in cfg.items():
                danger = info.get("danger_level", "Trung bình")
                if cur_t == "urgent" and danger not in ("Khẩn cấp", "Cao"):
                    continue
                if cur_t == "medium" and danger != "Trung bình":
                    continue
                if cur_t == "low" and danger not in ("Thấp", "An toàn"):
                    continue
                haystack = f"{info.get('name_vi','')} {info.get('symptoms','')} {info.get('prevention','')} {info.get('treatment','')}".lower()
                if q and q not in haystack:
                    continue
                badge_label, badge_fg, badge_bg = _danger_badge_spec(danger)
                cards_col.controls.append(
                    css_card(
                        padding=24,
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, color=badge_fg, size=22),
                                        ft.Text(info.get("name_vi", code), size=16, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY, expand=True),
                                        ft.Container(
                                            bgcolor=badge_bg,
                                            border=ft.border.all(1, badge_fg),
                                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                                            border_radius=14,
                                            content=ft.Text(badge_label, size=11, color=badge_fg, weight=ft.FontWeight.BOLD),
                                        ),
                                    ]
                                ),
                                ft.Text(f"• Triệu chứng nhận biết: {info.get('symptoms', '')}", size=13, color=TEXT_PRIMARY),
                                ft.Text(f"• Cách xử lý & Cách ly tại chuồng: {info.get('prevention', '')}", size=13, color="#0284C7"),
                                ft.Text(f"• Phác đồ điều trị tham khảo: {info.get('treatment', '')}", size=13, color=PRIMARY_DARK, weight=ft.FontWeight.W_600),
                            ],
                            spacing=6,
                        ),
                    )
                )
            page.update()

        search_box.on_change = render_wiki
        render_wiki()

        return [
            tech_banner(
                "Cẩm nang Bệnh lý Da Heo",
                "Cơ sở dữ liệu bệnh lý thú y giúp nhận diện triệu chứng sớm và cách phòng ngừa tại trang trại",
                badge_text="Cơ sở dữ liệu bệnh lý",
                page=page,
            ),
            css_card(
                padding=20,
                content=ft.Row([search_box, triage_chips_row], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ),
            cards_col,
        ]

    destinations = [
        ("Chẩn đoán bệnh", ft.Icons.IMAGE_SEARCH_OUTLINED, ft.Icons.IMAGE_SEARCH_ROUNDED),
        ("Lịch sử khám", ft.Icons.HISTORY_OUTLINED, ft.Icons.HISTORY_ROUNDED),
        ("Cẩm nang bệnh lý", ft.Icons.MENU_BOOK_OUTLINED, ft.Icons.MENU_BOOK_ROUNDED),
    ]

    return build_role_shell(
        page=page,
        user=user,
        title="Không gian Người Chăn Nuôi",
        destinations=destinations,
        tab_builders=[build_predict_tab, build_history_tab, build_wiki_tab],
    )
