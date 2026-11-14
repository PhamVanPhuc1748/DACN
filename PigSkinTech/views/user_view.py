"""User Role View (/user - Người chăn nuôi): Modern SaaS / Shadcn-UI & Tailwind Style Veterinary Clinic."""
import asyncio

import flet as ft

from services.auth_service import (
    build_role_shell,
    create_file_picker,
    ensure_flet_compat,
    export_vet_report_html,
    generate_lesion_heatmap,
    header_stat_pill,
    make_dropdown,
    make_image,
    open_image_zoom_dialog,
    pick_image_files,
    preview_thumbnail_with_zoom,
    show_snack,
    tech_banner,
)
from services.chat_widget import build_chat_panel
from services.inference import inspect_image, predict
from services.project_data import (
    active_run,
    display_class,
    get_class_info,
    list_class_keys,
    load_classes_config,
)
from services.store import (
    get_sample_gallery,
    list_user_inspections,
    request_expert_review,
    save,
)
from theme import (
    PRIMARY,
    PRIMARY_DARK,
    css_card,
    css_input,
    css_shadow,
    get_theme_palette,
    make_smooth_animation,
)


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

TOP3_BAR_COLORS = [PRIMARY, "#38BDF8", "#F59E0B"]


def _danger_badge_spec(danger_level: str, pal: dict) -> tuple[str, str, str]:
    """Return (badge_text, text_color, bg_color) for the clinical danger badge in Light/Dark mode."""
    dark = pal["IS_DARK"]
    if danger_level in ("An toàn", "Thấp"):
        return ("🟢 An toàn", "#34D399" if dark else PRIMARY_DARK, pal["SOFT_EMERALD"])
    if danger_level == "Trung bình":
        return ("🟠 Cảnh báo", "#FBBF24" if dark else "#D97706", pal["SOFT_AMBER"])
    return ("🔴 Nguy hiểm - Cần cách ly", "#F87171" if dark else "#DC2626", pal["SOFT_RED"])


def _confidence_color(conf: float, dark: bool = False) -> str:
    if conf >= 0.80:
        return "#34D399" if dark else PRIMARY_DARK
    if conf >= 0.60:
        return "#FBBF24" if dark else "#D97706"
    return "#F87171" if dark else "#DC2626"


def build_user_view(page: ft.Page, user: dict) -> ft.Control:
    ensure_flet_compat(page)
    picker = create_file_picker(page)
    cur_run = active_run() or {}
    state = {
        "image_path": None,
        "heatmap_path": None,
        "heatmap_mode": False,
        "scanning": False,
        "scan_status": "🔍 Đang tiền xử lý & tách nền da heo...",
        "image_info": None,
        "result": None,
        "record_id": None,
        "sent_to_expert": False,
        "wiki_triage": "all",
    }

    model_status_text = ft.Text(
        f"Model đang dùng: {cur_run['model_label']} ({cur_run['name']})"
        if cur_run else "Admin chưa kích hoạt model AI.",
        size=13,
        color=PRIMARY_DARK if cur_run else "#DC2626",
    )

    animal_field = css_input(
        label="Mã đàn / cá thể",
        hint_text="VD: PIG-101",
        prefix_icon=ft.Icons.PETS_ROUNDED,
        expand=True,
        page=page,
    )
    farm_field = css_input(
        label="Khu chuồng",
        hint_text="VD: Khu A - Chuồng 02",
        prefix_icon=ft.Icons.HOME_WORK_OUTLINED,
        expand=True,
        page=page,
    )
    symptoms_field = css_input(
        label="Triệu chứng ghi nhận",
        hint_text="Chọn nhanh các biểu hiện bên trên hoặc nhập mô tả chi tiết...",
        multiline=True,
        min_lines=2,
        max_lines=2,
        expand=True,
        page=page,
    )

    header_host = ft.Container()
    dropzone_host = ft.Container()
    sample_gallery_host = ft.Container()
    symptom_chips_row = ft.Row(spacing=8, wrap=True)
    loading_bar = ft.ProgressBar(visible=False, color=PRIMARY)
    right_card_host = ft.Container(
        expand=1,
        opacity=1.0,
        animate_opacity=make_smooth_animation(250),
    )

    def refresh_page_header():
        p = get_theme_palette(page)
        records = list_user_inspections(user.get("email", ""))
        total_scans = len(records)
        confs = [float(r["confidence"]) for r in records if r.get("confidence") is not None]
        avg_conf = (sum(confs) / len(confs) * 100.0) if confs else 0.0
        sent_expert = sum(
            1 for r in records if int(r.get("requested_review") or 0) == 1 or r.get("review_status") == "reviewed"
        )
        reviewed_by_expert = sum(1 for r in records if r.get("review_status") == "reviewed")
        pills = [
            header_stat_pill(
                "Tổng lượt khám",
                f"{total_scans} ca",
                ft.Icons.QR_CODE_SCANNER_ROUNDED,
                accent="#10B981" if p["IS_DARK"] else PRIMARY_DARK,
                soft_bg=p["SOFT_EMERALD"],
                badge_text="Dữ liệu SQL thật" if total_scans > 0 else "Chưa có ca khám",
                page=page,
                col={"xs": 12, "sm": 6, "lg": 3},
            ),
            header_stat_pill(
                "Độ tin cậy AI",
                f"{avg_conf:.1f}%",
                ft.Icons.AUTO_GRAPH_ROUNDED,
                accent="#38BDF8" if p["IS_DARK"] else "#0284C7",
                soft_bg=p["SOFT_BLUE"],
                badge_text="Softmax trung bình" if total_scans > 0 else "0 ca",
                page=page,
                col={"xs": 12, "sm": 6, "lg": 3},
            ),
            header_stat_pill(
                "Gửi Bác sĩ Thú y",
                f"{sent_expert} ca",
                ft.Icons.MEDICAL_SERVICES_ROUNDED,
                accent="#F59E0B" if p["IS_DARK"] else "#D97706",
                soft_bg=p["SOFT_AMBER"],
                badge_text="Hội chẩn chuyên gia",
                page=page,
                col={"xs": 12, "sm": 6, "lg": 3},
            ),
            header_stat_pill(
                "Đã có phác đồ BS",
                f"{reviewed_by_expert} ca",
                ft.Icons.VERIFIED_ROUNDED,
                accent="#7C3AED",
                soft_bg=p["SOFT_BLUE"],
                badge_text="Chuyên gia đã duyệt",
                page=page,
                col={"xs": 12, "sm": 6, "lg": 3},
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
        p = get_theme_palette(page)
        current_lower = (symptoms_field.value or "").lower()
        symptom_chips_row.controls.clear()
        for chip_label, phrase in QUICK_SYMPTOM_CHIPS:
            active = phrase.lower() in current_lower
            symptom_chips_row.controls.append(
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=12, vertical=7),
                    border_radius=18,
                    bgcolor=p["SOFT_EMERALD"] if active else p["BG_SUB"],
                    border=ft.border.all(1.5 if active else 1, PRIMARY if active else p["BORDER_LIGHT"]),
                    ink=True,
                    on_click=lambda e, ph=phrase: append_symptom_chip(ph),
                    content=ft.Text(
                        chip_label,
                        size=13,
                        weight=ft.FontWeight.W_600,
                        color=("#34D399" if p["IS_DARK"] else PRIMARY_DARK) if active else p["TEXT_PRIMARY"],
                    ),
                )
            )

    def toggle_heatmap_view(e=None):
        if not state["image_path"]:
            return
        state["heatmap_mode"] = not state["heatmap_mode"]
        if state["heatmap_mode"] and not state["heatmap_path"]:
            state["heatmap_path"] = generate_lesion_heatmap(state["image_path"])
        render_dropzone()
        page.update()

    def render_dropzone():
        p = get_theme_palette(page)
        info = state["image_info"]
        if state["image_path"] and info:
            display_img_path = (
                state["heatmap_path"]
                if (state["heatmap_mode"] and state["heatmap_path"])
                else state["image_path"]
            )
            preview_image = make_image(
                display_img_path,
                width=None,
                height=None,
                border_radius=12,
                fit=getattr(ft.ImageFit, "CONTAIN", None),
            )
            preview_image.expand = True
            stack_children: list[ft.Control] = [
                ft.Container(
                    left=0,
                    right=0,
                    top=0,
                    bottom=0,
                    alignment=ft.alignment.center,
                    content=preview_image,
                ),
                ft.Container(
                    right=10,
                    top=10,
                    content=ft.Row(
                        [
                            ft.Container(
                                bgcolor="#059669" if state["heatmap_mode"] else ft.Colors.with_opacity(0.92, p["BG_CARD"]),
                                border=ft.border.all(1, "#34D399" if state["heatmap_mode"] else p["BORDER_LIGHT"]),
                                border_radius=8,
                                padding=ft.padding.symmetric(horizontal=11, vertical=7),
                                ink=True,
                                on_click=toggle_heatmap_view,
                                tooltip="Bật/tắt chế độ Bản đồ nhiệt & tăng tương phản vùng tổn thương AI",
                                content=ft.Row(
                                    [
                                        ft.Icon(
                                            ft.Icons.THERMOSTAT_AUTO_ROUNDED if state["heatmap_mode"] else ft.Icons.BIOTECH_ROUNDED,
                                            size=16,
                                            color="#FFFFFF" if state["heatmap_mode"] else PRIMARY,
                                        ),
                                        ft.Text(
                                            "Ảnh gốc" if state["heatmap_mode"] else "🔬 Soi vùng tổn thương AI",
                                            size=12.5,
                                            color="#FFFFFF" if state["heatmap_mode"] else p["TEXT_PRIMARY"],
                                            weight=ft.FontWeight.W_600,
                                        ),
                                    ],
                                    spacing=5,
                                    tight=True,
                                ),
                            ),
                            ft.Container(
                                bgcolor=ft.Colors.with_opacity(0.92, p["BG_CARD"]),
                                border=ft.border.all(1, p["BORDER_LIGHT"]),
                                border_radius=8,
                                padding=ft.padding.symmetric(horizontal=11, vertical=7),
                                ink=True,
                                on_click=handle_choose_file,
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.CHANGE_CIRCLE_OUTLINED, size=16, color=p["TEXT_PRIMARY"]),
                                        ft.Text("Đổi ảnh khác", size=12.5, color=p["TEXT_PRIMARY"], weight=ft.FontWeight.W_600),
                                    ],
                                    spacing=5,
                                    tight=True,
                                ),
                            ),
                            ft.Container(
                                bgcolor=ft.Colors.with_opacity(0.88, "#0F172A"),
                                border_radius=8,
                                padding=ft.padding.symmetric(horizontal=11, vertical=7),
                                ink=True,
                                on_click=lambda e: open_image_zoom_dialog(page, display_img_path, info["name"]),
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.ZOOM_IN_ROUNDED, size=16, color="#34D399"),
                                        ft.Text("Phóng to", size=12.5, color="#FFFFFF", weight=ft.FontWeight.W_600),
                                    ],
                                    spacing=5,
                                    tight=True,
                                ),
                            ),
                        ],
                        spacing=6,
                        tight=True,
                    ),
                ),
            ]

            if state["heatmap_mode"] and not state["scanning"]:
                stack_children.append(
                    ft.Container(
                        left=12,
                        bottom=10,
                        bgcolor=ft.Colors.with_opacity(0.86, "#0F172A"),
                        border=ft.border.all(1, "#34D399"),
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=10, vertical=5),
                        content=ft.Text(
                            "🔥 Chế độ Bản đồ Nhiệt & Tăng Tương Phản Tổn Thương AI",
                            size=12.5,
                            weight=ft.FontWeight.W_600,
                            color="#34D399",
                        ),
                    )
                )

            if state["scanning"]:
                stack_children.append(
                    ft.Container(
                        expand=True,
                        border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.72, "#0F172A"),
                        border=ft.border.all(2, "#10B981"),
                        alignment=ft.alignment.center,
                        animate=make_smooth_animation(180),
                        content=ft.Column(
                            [
                                ft.Container(
                                    width=360,
                                    height=3,
                                    bgcolor="#34D399",
                                    border_radius=2,
                                    shadow=ft.BoxShadow(blur_radius=14, color="#10B981", offset=ft.Offset(0, 0)),
                                ),
                                ft.Row(
                                    [
                                        ft.ProgressRing(width=20, height=20, stroke_width=2.5, color="#34D399"),
                                        ft.Text(
                                            state["scan_status"],
                                            size=14.5,
                                            weight=ft.FontWeight.BOLD,
                                            color="#FFFFFF",
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    spacing=10,
                                ),
                                ft.Text(
                                    "AI Laser Scanner đang quét viền tổn thương biểu bì...",
                                    size=12.5,
                                    color="#A7F3D0",
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                        ),
                    )
                )

            dropzone_host.content = ft.Container(
                height=340,
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                    colors=p["DROPZONE_GRADIENT"],
                ),
                border=ft.border.all(2 if state["scanning"] else 1.5, "#10B981" if state["scanning"] else p["DROPZONE_BORDER"]),
                border_radius=16,
                padding=6,
                alignment=ft.alignment.center,
                animate=make_smooth_animation(200),
                content=ft.Stack(
                    expand=True,
                    controls=stack_children,
                ),
            )
        else:
            upload_icon_box = ft.Container(
                width=56,
                height=56,
                bgcolor=p["BG_CARD"],
                border_radius=28,
                border=ft.border.all(1, p["DROPZONE_BORDER"]),
                alignment=ft.alignment.center,
                scale=1.0,
                animate_scale=make_smooth_animation(200),
                shadow=css_shadow(0.12 if p["IS_DARK"] else 0.06, 12, 3),
                content=ft.Icon(ft.Icons.ADD_A_PHOTO_OUTLINED, size=26, color=PRIMARY),
            )

            def on_dropzone_hover(e):
                cur_p = get_theme_palette(page)
                hovered = str(getattr(e, "data", "")).lower() == "true"
                e.control.gradient = ft.LinearGradient(
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                    colors=cur_p["DROPZONE_HOVER_GRADIENT"] if hovered else cur_p["DROPZONE_GRADIENT"],
                )
                e.control.border = ft.border.all(2 if hovered else 1.5, PRIMARY if hovered else cur_p["DROPZONE_BORDER"])
                upload_icon_box.scale = 1.12 if hovered else 1.0
                e.control.update()

            dropzone_host.content = ft.Container(
                height=220,
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                    colors=p["DROPZONE_GRADIENT"],
                ),
                border=ft.border.all(1.5, p["DROPZONE_BORDER"]),
                border_radius=16,
                alignment=ft.alignment.center,
                animate=make_smooth_animation(200),
                ink=True,
                on_click=handle_choose_file,
                on_hover=on_dropzone_hover,
                content=ft.Column(
                    [
                        upload_icon_box,
                        ft.Text("Nhấn để tải ảnh vùng da heo cần kiểm tra", size=15, weight=ft.FontWeight.BOLD, color=p["TEXT_PRIMARY"]),
                        ft.Text("Hỗ trợ ảnh chụp rõ nét từ điện thoại hoặc máy ảnh (JPG, PNG, WEBP)", size=13, color=p["TEXT_SECONDARY"]),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
            )

    def load_sample_case(sample: dict):
        try:
            info = inspect_image(sample["path"])
            state.update(
                image_path=sample["path"],
                heatmap_path=None,
                heatmap_mode=False,
                scanning=False,
                image_info=info,
                result=None,
                record_id=None,
                sent_to_expert=False,
            )
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
        p = get_theme_palette(page)
        samples = get_sample_gallery()
        thumbs = []

        def on_sample_hover(e, is_sel: bool):
            cur_p = get_theme_palette(page)
            hovered = str(getattr(e, "data", "")).lower() == "true"
            active = hovered or is_sel
            e.control.border = ft.border.all(2 if active else 1, PRIMARY if active else cur_p["BORDER_LIGHT"])
            e.control.shadow = css_shadow(0.14, 18, 4) if active else None
            e.control.update()

        for idx, s in enumerate(samples[:5]):
            short_title = SHORT_SAMPLE_LABELS[idx] if idx < len(SHORT_SAMPLE_LABELS) else s["title"]
            is_selected = state["image_path"] == s["path"]
            thumbs.append(
                ft.Container(
                    expand=1,
                    padding=7,
                    bgcolor=p["SOFT_EMERALD"] if is_selected else p["BG_SUB"],
                    border=ft.border.all(2 if is_selected else 1, PRIMARY if is_selected else p["BORDER_LIGHT"]),
                    border_radius=12,
                    shadow=css_shadow(0.12, 18, 4) if is_selected else None,
                    animate=make_smooth_animation(200),
                    ink=True,
                    tooltip=s["title"],
                    on_click=lambda e, item=s: load_sample_case(item),
                    on_hover=lambda e, sel=is_selected: on_sample_hover(e, sel),
                    content=ft.Column(
                        [
                            make_image(s["path"], width=160, height=68, border_radius=8, fit=ft.ImageFit.COVER),
                            ft.Text(
                                short_title,
                                size=12.5,
                                weight=ft.FontWeight.W_600,
                                color=("#34D399" if p["IS_DARK"] else PRIMARY_DARK) if is_selected else p["TEXT_PRIMARY"],
                                no_wrap=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=6,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        tight=True,
                    ),
                )
            )
        sample_gallery_host.content = ft.Column(
            [
                ft.Text("Hoặc chọn nhanh mẫu thử lâm sàng:", size=13.5, weight=ft.FontWeight.W_600, color=p["TEXT_SECONDARY"]),
                ft.Row(thumbs, spacing=10),
            ],
            spacing=8,
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

    def handle_export_report(e):
        res = state["result"]
        if not res:
            show_snack(page, "Vui lòng phân tích chẩn đoán trước khi xuất Phiếu Khám.", "#DC2626")
            return
        cls_info = get_class_info(res.get("label"))
        export_vet_report_html(
            page,
            case_data={
                "record_id": state["record_id"] or 1,
                "case_id": f"PS-{int(state['record_id'] or 1):06d}",
                "image_path": state["image_path"],
                "disease_name": res.get("display_label") or display_class(res.get("label")),
                "danger_level": res.get("danger_level", "Trung bình"),
                "confidence": float(res.get("confidence") or 0.0),
                "scores": res.get("scores") or [],
                "animal_id": animal_field.value or "PIG-101",
                "farm_name": farm_field.value or "Trại chăn nuôi",
                "user_name": user.get("full_name", "Người chăn nuôi"),
                "symptoms": symptoms_field.value or "",
                "isolation_guide": cls_info.get("prevention") or "",
                "treatment_guide": res.get("recommendation") or cls_info.get("treatment") or "",
            },
        )

    def _build_recent_3_list() -> list[ft.Control]:
        p = get_theme_palette(page)
        records = list_user_inspections(user.get("email", ""))[:3]
        if not records:
            return [ft.Text("Chưa có lịch sử khám gần đây.", size=13.5, color=p["TEXT_MUTED"])]
        rows = []
        for rec in records:
            conf = float(rec.get("confidence") or 0.0)
            final_cls = rec.get("expert_label") or rec.get("predicted_class")
            is_rev = rec.get("review_status") == "reviewed"
            is_requested = int(rec.get("requested_review") or 0) == 1
            review_label = ("Đã thẩm định" if is_rev else "Chờ duyệt" if is_requested
                            else "Nên gửi bác sĩ" if conf < 0.75 else "Chưa gửi thẩm định")
            rows.append(
                ft.Container(
                    padding=12,
                    bgcolor=p["BG_SUB"],
                    border_radius=12,
                    border=ft.border.all(1, p["BORDER_LIGHT"]),
                    content=ft.Row(
                        [
                            preview_thumbnail_with_zoom(
                                page,
                                rec.get("image_path"),
                                f"{rec.get('case_id')} • {display_class(final_cls)}",
                                width=56,
                                height=56,
                                border_radius=10,
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        display_class(final_cls),
                                        size=14,
                                        weight=ft.FontWeight.BOLD,
                                        color=p["TEXT_PRIMARY"],
                                        no_wrap=True,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(
                                        f"Mã đàn: {rec.get('animal_id') or '—'} • Độ tin cậy: {conf*100:.1f}%",
                                        size=12.5,
                                        color=p["TEXT_SECONDARY"],
                                    ),
                                ],
                                spacing=3,
                                expand=True,
                            ),
                            ft.Container(
                                bgcolor=p["SOFT_EMERALD"] if is_rev else p["SOFT_AMBER"],
                                padding=ft.padding.symmetric(horizontal=10, vertical=5),
                                border_radius=10,
                                content=ft.Text(
                                    review_label,
                                    size=12.5,
                                    color=("#34D399" if p["IS_DARK"] else PRIMARY_DARK) if is_rev else ("#FBBF24" if p["IS_DARK"] else "#D97706"),
                                    weight=ft.FontWeight.W_600,
                                ),
                            ),
                        ],
                        spacing=12,
                    ),
                )
            )
        return rows

    top3_progress_refs: list[tuple[ft.ProgressBar, ft.Text, float]] = []
    main_conf_ref: list[tuple[ft.Text, float]] = []

    def render_right_card(zero_bars_first: bool = False):
        p = get_theme_palette(page)
        res = state["result"]
        top3_progress_refs.clear()
        main_conf_ref.clear()

        # STANDBY STATE: Clean centered Hero + 3 steps + 3 recent inspections in 1 cohesive Card
        if not res:
            step_items = [
                (ft.Icons.ADD_A_PHOTO_ROUNDED, "1. Tải ảnh", "Chọn ảnh vùng da heo hoặc bấm vào mẫu thử"),
                (ft.Icons.FACT_CHECK_ROUNDED, "2. Chọn triệu chứng", "Ghi nhận biểu hiện lâm sàng tại chuồng"),
                (ft.Icons.MEDICAL_SERVICES_ROUNDED, "3. Nhận phác đồ", "Xem kết quả AI & hướng xử lý thú y"),
            ]
            steps_row = ft.Row(
                [
                    ft.Container(
                        expand=True,
                        padding=14,
                        bgcolor=p["BG_SUB"],
                        border_radius=12,
                        border=ft.border.all(1, p["BORDER_LIGHT"]),
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Container(
                                            width=28,
                                            height=28,
                                            border_radius=14,
                                            bgcolor=p["SOFT_EMERALD"],
                                            alignment=ft.alignment.center,
                                            content=ft.Icon(st_icon, size=15, color="#34D399" if p["IS_DARK"] else PRIMARY_DARK),
                                        ),
                                        ft.Text(
                                            st_title,
                                            size=14,
                                            weight=ft.FontWeight.BOLD,
                                            color="#34D399" if p["IS_DARK"] else PRIMARY_DARK,
                                            expand=True,
                                        ),
                                    ],
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Text(st_desc, size=12.5, color=p["TEXT_SECONDARY"]),
                            ],
                            spacing=6,
                            tight=True,
                        ),
                    )
                    for st_icon, st_title, st_desc in step_items
                ],
                spacing=10,
            )

            right_card_host.content = css_card(
                padding=24,
                page=page,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.MEDICAL_INFORMATION_ROUNDED, color=PRIMARY, size=22),
                                ft.Text("Kết quả Phân tích & Phác đồ Thú y", size=18, weight=ft.FontWeight.BOLD, color=p["TEXT_PRIMARY"], expand=True),
                            ],
                            spacing=8,
                        ),
                        ft.Container(
                            padding=ft.padding.symmetric(vertical=24, horizontal=18),
                            bgcolor=p["BG_SUB"],
                            border_radius=14,
                            border=ft.border.all(1, p["BORDER_LIGHT"]),
                            alignment=ft.alignment.center,
                            content=ft.Column(
                                [
                                    ft.Container(
                                        width=64,
                                        height=64,
                                        border_radius=32,
                                        bgcolor=p["SOFT_EMERALD"],
                                        alignment=ft.alignment.center,
                                        content=ft.Icon(ft.Icons.BIOTECH_ROUNDED, size=34, color=PRIMARY),
                                    ),
                                    ft.Text(
                                        "Sẵn sàng phân tích mẫu da heo",
                                        size=18,
                                        weight=ft.FontWeight.BOLD,
                                        color=p["TEXT_PRIMARY"],
                                    ),
                                    ft.Text(
                                        "Trí tuệ nhân tạo PigSkin AI sẽ đánh giá tổn thương da và gợi ý hướng xử lý tức thì.",
                                        size=14,
                                        color=p["TEXT_SECONDARY"],
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=6,
                                tight=True,
                            ),
                        ),
                        steps_row,
                        ft.Text("3 lần khám gần nhất", size=15, weight=ft.FontWeight.BOLD, color=p["TEXT_PRIMARY"]),
                        *_build_recent_3_list(),
                    ],
                    spacing=14,
                ),
            )
            return

        # RESULT STATE: Danger badge + Disease title + Top-3 Probability Bars + 2-part Protocol Box + Vet CTA + Print Report
        danger = res.get("danger_level", "Trung bình")
        badge_label, badge_fg, badge_bg = _danger_badge_spec(danger, p)
        disease_name = res.get("display_label") or display_class(res.get("label"))
        main_conf = float(res.get("confidence") or 0.0)
        cls_info = get_class_info(res.get("label"))
        isolation_guide = cls_info.get("prevention") or "Cách ly cá thể nghi nhiễm, vệ sinh sát trùng chuồng trại và theo dõi thân nhiệt."
        treatment_guide = res.get("recommendation") or cls_info.get("treatment") or "Tham khảo ý kiến Bác sĩ Thú y trước khi dùng kháng sinh đặc hiệu."

        main_conf_text = ft.Text(
            f"0.0%" if zero_bars_first else f"{main_conf * 100:.1f}%",
            size=20,
            weight=ft.FontWeight.W_800,
            color="#34D399" if p["IS_DARK"] else PRIMARY_DARK,
        )
        main_conf_ref.append((main_conf_text, main_conf))

        top3_bars = []
        for idx, s in enumerate((res.get("scores") or [])[:3]):
            s_conf = float(s.get("confidence") or 0.0)
            bar_color = TOP3_BAR_COLORS[idx] if idx < len(TOP3_BAR_COLORS) else p["TEXT_SECONDARY"]
            pbar = ft.ProgressBar(
                value=0.0 if zero_bars_first else s_conf,
                bar_height=8,
                color=bar_color,
                bgcolor=p["BORDER_LIGHT"],
            )
            pct_txt = ft.Text(
                "0.0%" if zero_bars_first else f"{s_conf * 100:.1f}%",
                size=14,
                weight=ft.FontWeight.BOLD,
                color=bar_color,
            )
            top3_progress_refs.append((pbar, pct_txt, s_conf))
            top3_bars.append(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    f"#{idx + 1}  {display_class(s['label'])}",
                                    size=14,
                                    weight=ft.FontWeight.BOLD if idx == 0 else ft.FontWeight.W_500,
                                    color=p["TEXT_PRIMARY"],
                                    expand=True,
                                ),
                                pct_txt,
                            ]
                        ),
                        pbar,
                    ],
                    spacing=5,
                )
            )

        expert_btn = (
            ft.Container(
                expand=2,
                bgcolor=p["SOFT_BLUE"],
                border=ft.border.all(1, "#38BDF8"),
                padding=14,
                border_radius=12,
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color="#38BDF8" if p["IS_DARK"] else "#0284C7", size=20),
                        ft.Text(
                            f"Đã gửi hồ sơ PS-{state['record_id']:06d} tới Bác sĩ Thú y",
                            size=14,
                            color="#38BDF8" if p["IS_DARK"] else "#0284C7",
                            weight=ft.FontWeight.BOLD,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                ),
            )
            if state["sent_to_expert"]
            else ft.Container(
                expand=2,
                height=52,
                border_radius=12,
                bgcolor="#0284C7",
                alignment=ft.alignment.center,
                ink=True,
                on_click=handle_send_to_expert,
                content=ft.Text(
                    "👨‍⚕️ Gửi Bác sĩ Thú y thẩm định ca này",
                    size=14.5,
                    weight=ft.FontWeight.BOLD,
                    color="#FFFFFF",
                ),
            )
        )

        print_report_btn = ft.Container(
            expand=1,
            height=52,
            border_radius=12,
            bgcolor=p["BG_SUB"],
            border=ft.border.all(1.5, PRIMARY),
            alignment=ft.alignment.center,
            ink=True,
            on_click=handle_export_report,
            tooltip="Xuất Phiếu Kết Quả Chẩn Đoán Thú Y ra file HTML/PDF để lưu trữ hoặc in ấn",
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.PRINT_ROUNDED, size=18, color="#34D399" if p["IS_DARK"] else PRIMARY_DARK),
                    ft.Text(
                        "🖨️ Xuất Phiếu Khám",
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color="#34D399" if p["IS_DARK"] else PRIMARY_DARK,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
                tight=True,
            ),
        )

        def handle_ask_chatbot(e=None):
            if not isinstance(getattr(page, "data", None), dict):
                page.data = {}
            page.data["active_scan_result"] = res
            opener = page.data.get("open_vet_chat")
            prompt = (
                f"Mô hình {res.get('architecture', 'AI')} vừa chẩn đoán '{disease_name}' "
                f"(độ tin cậy Softmax {main_conf*100:.1f}%). "
                "Hãy tư vấn chi tiết triệu chứng, liều lượng thuốc điều trị và cách ly cho ca này?"
            )
            if callable(opener):
                opener(prompt)

        ask_ai_btn = ft.Container(
            expand=1,
            height=52,
            border_radius=12,
            bgcolor=PRIMARY_DARK,
            alignment=ft.alignment.center,
            ink=True,
            on_click=handle_ask_chatbot,
            tooltip="Hỏi trực tiếp Trợ lý AI Thú y (Chatbot) về triệu chứng, liều lượng thuốc và cách ly của ca vừa quét",
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.SMART_TOY_ROUNDED, size=18, color="#FFFFFF"),
                    ft.Text(
                        "💬 Hỏi AI Thú y",
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color="#FFFFFF",
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
                tight=True,
            ),
        )

        actions_row = ft.Row([expert_btn, ask_ai_btn, print_report_btn], spacing=10)

        arch_txt = res.get("architecture") or res.get("model_label") or "MobileNetV2"
        run_txt = res.get("run_name") or ""
        ms_txt = res.get("inference_ms", "-")

        right_card_host.content = css_card(
            padding=24,
            page=page,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.MEDICAL_INFORMATION_ROUNDED, color=PRIMARY, size=22),
                            ft.Text("Kết quả Phân tích & Phác đồ Thú y", size=18, weight=ft.FontWeight.BOLD, color=p["TEXT_PRIMARY"], expand=True),
                            ft.Container(
                                bgcolor=badge_bg,
                                border=ft.border.all(1, badge_fg),
                                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                                border_radius=20,
                                content=ft.Text(badge_label, size=12.5, color=badge_fg, weight=ft.FontWeight.W_600),
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                f"Kết luận từ Tensor Softmax ({arch_txt} • {run_txt} • {ms_txt} ms):",
                                size=13,
                                weight=ft.FontWeight.W_600,
                                color=p["TEXT_SECONDARY"],
                            ),
                            ft.Row(
                                [
                                    ft.Text(disease_name, size=22, weight=ft.FontWeight.BOLD, color=badge_fg, expand=True),
                                    ft.Container(
                                        padding=ft.padding.symmetric(horizontal=12, vertical=5),
                                        border_radius=12,
                                        bgcolor=p["SOFT_EMERALD"],
                                        border=ft.border.all(1, PRIMARY),
                                        content=ft.Row(
                                            [
                                                ft.Text("Độ tin cậy:", size=12.5, weight=ft.FontWeight.W_600, color=p["TEXT_SECONDARY"]),
                                                main_conf_text,
                                            ],
                                            spacing=6,
                                            tight=True,
                                        ),
                                    ),
                                ],
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ],
                        spacing=2,
                    ),
                    ft.Container(
                        padding=14,
                        bgcolor=p["BG_SUB"],
                        border_radius=12,
                        border=ft.border.all(1, p["BORDER_LIGHT"]),
                        content=ft.Column(
                            [
                                ft.Text("Biểu đồ Top-3 Khả năng:", size=14, weight=ft.FontWeight.BOLD, color=p["TEXT_PRIMARY"]),
                                *top3_bars,
                            ],
                            spacing=8,
                        ),
                    ),
                    ft.Container(
                        padding=16,
                        bgcolor=p["SOFT_EMERALD"],
                        border_radius=12,
                        border=ft.border.all(1, p["PROTOCOL_BORDER"]),
                        content=ft.Column(
                            [
                                ft.Text("🛡️ Cách xử lý & Cách ly tại chuồng", size=14.5, weight=ft.FontWeight.BOLD, color=p["PROTOCOL_HEAD"]),
                                ft.Text(isolation_guide, size=14, color=p["PROTOCOL_TEXT"]),
                                ft.Text("💊 Gợi ý điều trị / Thuốc tham khảo", size=14.5, weight=ft.FontWeight.BOLD, color=p["PROTOCOL_HEAD"]),
                                ft.Text(treatment_guide, size=14, color=p["PROTOCOL_TEXT"]),
                            ],
                            spacing=6,
                        ),
                    ),
                    ft.Text(
                        "Điểm AI còn thấp. Bạn nên gửi ca này để Bác sĩ Thú y thẩm định.",
                        size=13.5,
                        color="#FBBF24" if p["IS_DARK"] else "#92400E",
                        visible=main_conf < 0.75 and not state["sent_to_expert"],
                    ),
                    actions_row,
                    ft.Divider(height=12, color=p["BORDER_LIGHT"]),
                    ft.Text("3 lần khám gần nhất", size=15, weight=ft.FontWeight.BOLD, color=p["TEXT_PRIMARY"]),
                    *_build_recent_3_list(),
                ],
                spacing=14,
            ),
        )

    def handle_reset_case(e=None):
        state.update(
            image_path=None,
            heatmap_path=None,
            heatmap_mode=False,
            scanning=False,
            image_info=None,
            result=None,
            record_id=None,
            sent_to_expert=False,
        )
        animal_field.value = ""
        farm_field.value = ""
        symptoms_field.value = ""
        render_dropzone()
        render_sample_gallery()
        render_symptom_chips()
        render_right_card()
        page.update()

    def on_files_selected(paths: list[str]):
        if not paths:
            return
        p_path = paths[0]
        try:
            info = inspect_image(p_path)
            state.update(
                image_path=p_path,
                heatmap_path=None,
                heatmap_mode=False,
                scanning=False,
                image_info=info,
                result=None,
                record_id=None,
                sent_to_expert=False,
            )
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

        configured_run = active_run()
        model_status_text.value = (
            f"Model đang dùng: {configured_run['model_label']} ({configured_run['name']})"
            if configured_run else "Admin chưa kích hoạt model AI."
        )
        model_status_text.color = PRIMARY_DARK if configured_run else "#DC2626"
        if not configured_run:
            page.update()
            show_snack(page, "Admin chưa kích hoạt model AI để phân tích ảnh.", "#DC2626")
            return

        loading_bar.visible = True
        state["scanning"] = True
        scan_steps = [
            "🔍 Đang tiền xử lý & tách nền da heo...",
            "🧠 Đang trích xuất đặc trưng qua mạng Deep Learning...",
            "📊 Đang tổng hợp phác đồ thú y...",
        ]

        try:
            # Start AI inference in background thread while running the 0.9s AI Laser Scanner sequence
            pred_task = asyncio.create_task(
                asyncio.to_thread(predict, state["image_path"])
            )
            for msg in scan_steps:
                state["scan_status"] = msg
                render_dropzone()
                page.update()
                await asyncio.sleep(0.3)

            res = await pred_task
            if res.get("mode") != "ai":
                raise RuntimeError(res.get("message") or "Admin chưa kích hoạt model AI.")
            if not isinstance(getattr(page, "data", None), dict):
                page.data = {}
            page.data["active_scan_result"] = res
            info = state["image_info"] or inspect_image(state["image_path"])
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
                    "requested_review": 0,
                },
                source_image=state["image_path"],
            )
            state.update(result=res, record_id=rid, sent_to_expert=False, scanning=False)
            refresh_page_header()
            render_dropzone()

            # Fade-in right card & animate confidence counter + Top-3 progress bars from 0% -> target in 0.5s
            right_card_host.opacity = 0.2
            render_right_card(zero_bars_first=True)
            page.update()
            await asyncio.sleep(0.04)
            right_card_host.opacity = 1.0
            steps = 16
            for step_i in range(1, steps + 1):
                ratio = step_i / steps
                for m_txt, m_target in main_conf_ref:
                    m_txt.value = f"{(m_target * ratio) * 100:.1f}%"
                for pbar, pct_txt, target_val in top3_progress_refs:
                    cur_val = target_val * ratio
                    pbar.value = cur_val
                    pct_txt.value = f"{cur_val * 100:.1f}%"
                page.update()
                await asyncio.sleep(0.03)
        except Exception as err:
            state["scanning"] = False
            render_dropzone()
            show_snack(page, f"Không thể phân tích ảnh: {err}", "#DC2626")
        finally:
            loading_bar.visible = False
            page.update()

    # Tab 1: Predict (2 balanced 5:5 cards fitting neatly in 1 screen)
    def build_predict_tab():
        p = get_theme_palette(page)
        for tf_ctrl in (animal_field, farm_field, symptoms_field):
            tf_ctrl.fill_color = p["BG_SUB"]
            tf_ctrl.border_color = p["BORDER_LIGHT"]
            tf_ctrl.color = p["TEXT_PRIMARY"]
            tf_ctrl.label_style = ft.TextStyle(color=p["TEXT_SECONDARY"], size=13.5)
            tf_ctrl.hint_style = ft.TextStyle(color=p["TEXT_MUTED"], size=13.5)

        refresh_page_header()
        render_dropzone()
        render_sample_gallery()
        render_symptom_chips()
        render_right_card()

        def on_cta_hover(e):
            hovered = str(getattr(e, "data", "")).lower() == "true"
            e.control.bgcolor = PRIMARY if hovered else PRIMARY_DARK
            e.control.shadow = ft.BoxShadow(
                blur_radius=24 if hovered else 16,
                color=ft.Colors.with_opacity(0.34 if hovered else 0.24, PRIMARY if hovered else PRIMARY_DARK),
                offset=ft.Offset(0, 6 if hovered else 4),
            )
            e.control.update()

        cta_analyze_btn = ft.Container(
            width=float("inf"),
            height=52,
            border_radius=12,
            bgcolor=PRIMARY_DARK,
            alignment=ft.alignment.center,
            animate=make_smooth_animation(180),
            ink=True,
            on_click=handle_run_predict,
            on_hover=on_cta_hover,
            shadow=ft.BoxShadow(
                blur_radius=16,
                color=ft.Colors.with_opacity(0.24, PRIMARY_DARK),
                offset=ft.Offset(0, 4),
            ),
            content=ft.Text(
                "⚡ Phân tích Chẩn đoán AI",
                size=16,
                weight=ft.FontWeight.BOLD,
                color="#FFFFFF",
            ),
        )

        reset_case_btn = ft.Container(
            padding=ft.padding.symmetric(horizontal=12, vertical=7),
            border_radius=10,
            bgcolor=p["BG_SUB"],
            border=ft.border.all(1, p["BORDER_LIGHT"]),
            ink=True,
            on_click=handle_reset_case,
            tooltip="Xóa nhanh ảnh và triệu chứng cũ để khám ca mới",
            content=ft.Text(
                "🔄 Làm mới / Khám ca tiếp theo",
                size=12.5,
                weight=ft.FontWeight.W_600,
                color=p["TEXT_SECONDARY"],
            ),
        )

        left_card = css_card(
            expand=1,
            padding=24,
            page=page,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CAMERA_ENHANCE_ROUNDED, color=PRIMARY, size=22),
                            ft.Text("Thu thập Hình ảnh & Triệu chứng", size=18, weight=ft.FontWeight.BOLD, color=p["TEXT_PRIMARY"], expand=True),
                            reset_case_btn,
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    dropzone_host,
                    sample_gallery_host,
                    ft.Row([model_status_text]),
                    ft.Row([animal_field, farm_field], spacing=12),
                    ft.Column(
                        [
                            ft.Text("Chọn nhanh biểu hiện lâm sàng:", size=13.5, weight=ft.FontWeight.W_600, color=p["TEXT_SECONDARY"]),
                            symptom_chips_row,
                        ],
                        spacing=6,
                        tight=True,
                    ),
                    ft.Row([symptoms_field]),
                    loading_bar,
                    cta_analyze_btn,
                ],
                spacing=12,
            ),
        )

        return [
            header_host,
            ft.ResponsiveRow(
                [
                    ft.Container(col={"xs": 12, "lg": 6}, content=left_card),
                    ft.Container(col={"xs": 12, "lg": 6}, content=right_card_host),
                ],
                run_spacing=20,
                spacing=20,
            ),
        ]

    # Tab 2: History
    def build_history_tab():
        date_input = css_input(
            label="Tìm theo ngày khám (YYYY-MM-DD)",
            hint_text="VD: 2026-11",
            prefix_icon=ft.Icons.CALENDAR_TODAY_ROUNDED,
            width=280,
            page=page,
        )
        disease_options = [("all", "Tất cả nhóm bệnh lý")] + [
            (code, display_class(code)) for code in list_class_keys()
        ]
        list_host = ft.Column(spacing=16)

        def refresh_history(e=None):
            cur_p = get_theme_palette(page)
            d_val = disease_dropdown.value or "all"
            records = list_user_inspections(user.get("email", ""), date_input.value or "", d_val)
            list_host.controls.clear()
            if not records:
                list_host.controls.append(
                    css_card(
                        padding=24,
                        page=page,
                        content=ft.Text("Không có lịch sử khám nào khớp bộ lọc.", size=14, color=cur_p["TEXT_MUTED"]),
                    )
                )
            for rec in records:
                is_reviewed = rec.get("review_status") == "reviewed"
                is_requested = int(rec.get("requested_review") or 0) == 1
                conf = float(rec.get("confidence") or 0.0)
                status_text = ("Đã được Bác sĩ Thú y xác nhận" if is_reviewed else
                               "Đang chờ duyệt" if is_requested else
                               "Nên gửi Bác sĩ Thú y" if conf < 0.75 else "Chưa gửi thẩm định")
                status_color = PRIMARY_DARK if is_reviewed else "#D97706" if is_requested or conf < 0.75 else "#64748B"
                final_code = rec.get("expert_label") or rec.get("predicted_class")
                conf_col = _confidence_color(conf, cur_p["IS_DARK"])

                expert_feedback = (
                    ft.Container(
                        bgcolor=cur_p["SOFT_EMERALD"],
                        border=ft.border.all(1, cur_p["PROTOCOL_BORDER"]),
                        padding=14,
                        border_radius=12,
                        content=ft.Column(
                            [
                                ft.Text(
                                    f"Kết luận Bác sĩ Thú y ({rec.get('reviewed_by') or 'BS. Thú y'}): {display_class(final_code)}",
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                    color=cur_p["PROTOCOL_HEAD"],
                                ),
                                ft.Text(
                                    f"Phác đồ điều trị: {rec.get('expert_note') or rec.get('recommendation')}",
                                    size=13.5,
                                    color=cur_p["PROTOCOL_TEXT"],
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
                                size=13.5,
                                color=cur_p["TEXT_SECONDARY"],
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
                        page=page,
                        hover_lift=True,
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
                                                    size=16,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=cur_p["TEXT_PRIMARY"],
                                                    expand=True,
                                                ),
                                                ft.Container(
                                                    bgcolor=status_color,
                                                    padding=ft.padding.symmetric(horizontal=12, vertical=5),
                                                    border_radius=12,
                                                    content=ft.Text(status_text, size=12.5, color="#FFFFFF", weight=ft.FontWeight.W_600),
                                                ),
                                            ]
                                        ),
                                        ft.Row(
                                            [
                                                ft.Text(
                                                    f"Kết quả PigSkin AI: {display_class(rec.get('predicted_class'))} ({conf*100:.1f}%)",
                                                    size=14,
                                                    weight=ft.FontWeight.W_600,
                                                    color=conf_col,
                                                    expand=True,
                                                ),
                                                ft.Text(f"Ngày khám: {rec.get('created_at')}", size=13, color=cur_p["TEXT_MUTED"]),
                                            ]
                                        ),
                                        ft.ProgressBar(value=conf, bar_height=7, color=conf_col, bgcolor=cur_p["BORDER_LIGHT"]),
                                        expert_feedback,
                                    ],
                                    spacing=8,
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
            width=300,
            page=page,
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
                page=page,
                content=ft.Row(
                    [
                        date_input,
                        disease_dropdown,
                        ft.OutlinedButton("Làm mới", icon=ft.Icons.REFRESH_ROUNDED, on_click=refresh_history),
                    ],
                    spacing=12,
                ),
            ),
            ft.Container(padding=ft.padding.only(bottom=90), content=list_host),
        ]

    # Tab 3: Wiki (3-Column Structured Sub-cards per Disease Card)
    def build_wiki_tab():
        search_box = css_input(
            label="Tìm kiếm tên bệnh, triệu chứng hoặc hướng điều trị...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            expand=True,
            page=page,
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
            cur_p = get_theme_palette(page)
            q = (search_box.value or "").strip().lower()
            cur_t = state["wiki_triage"]
            triage_chips_row.controls.clear()
            for t_key, t_label, t_col in triage_defs:
                active = cur_t == t_key
                triage_chips_row.controls.append(
                    ft.Container(
                        bgcolor=t_col if active else cur_p["BG_SUB"],
                        border=ft.border.all(1, t_col if active else cur_p["BORDER_LIGHT"]),
                        padding=ft.padding.symmetric(horizontal=14, vertical=8),
                        border_radius=18,
                        ink=True,
                        on_click=lambda ev, k=t_key: set_triage(k),
                        content=ft.Text(
                            t_label,
                            size=13,
                            color="#FFFFFF" if active else cur_p["TEXT_PRIMARY"],
                            weight=ft.FontWeight.W_600,
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
                badge_label, badge_fg, badge_bg = _danger_badge_spec(danger, cur_p)

                box_symptoms = ft.Container(
                    expand=1,
                    padding=14,
                    border_radius=12,
                    bgcolor=cur_p["BG_SUB"],
                    border=ft.border.all(1, cur_p["BORDER_LIGHT"]),
                    content=ft.Column(
                        [
                            ft.Text("🔍 Triệu chứng nhận biết", size=14, weight=ft.FontWeight.BOLD, color=cur_p["TEXT_PRIMARY"]),
                            ft.Text(info.get("symptoms", ""), size=13.5, color=cur_p["TEXT_SECONDARY"]),
                        ],
                        spacing=6,
                    ),
                )

                box_isolation = ft.Container(
                    expand=1,
                    padding=14,
                    border_radius=12,
                    bgcolor=cur_p["SOFT_BLUE"],
                    border=ft.border.all(1, "#38BDF8" if cur_p["IS_DARK"] else "#93C5FD"),
                    content=ft.Column(
                        [
                            ft.Text("🛡️ Cách xử lý & Cách ly", size=14, weight=ft.FontWeight.BOLD, color="#38BDF8" if cur_p["IS_DARK"] else "#0369A1"),
                            ft.Text(info.get("prevention", ""), size=13.5, color=cur_p["TEXT_PRIMARY"]),
                        ],
                        spacing=6,
                    ),
                )

                box_treatment = ft.Container(
                    expand=1,
                    padding=14,
                    border_radius=12,
                    bgcolor=cur_p["SOFT_EMERALD"],
                    border=ft.border.all(1, cur_p["PROTOCOL_BORDER"]),
                    content=ft.Column(
                        [
                            ft.Text("💊 Phác đồ điều trị tham khảo", size=14, weight=ft.FontWeight.BOLD, color=cur_p["PROTOCOL_HEAD"]),
                            ft.Text(info.get("treatment", ""), size=13.5, weight=ft.FontWeight.W_600, color=cur_p["PROTOCOL_TEXT"]),
                        ],
                        spacing=6,
                    ),
                )

                cards_col.controls.append(
                    css_card(
                        padding=24,
                        page=page,
                        hover_lift=True,
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, color=badge_fg, size=22),
                                        ft.Text(info.get("name_vi", code), size=18, weight=ft.FontWeight.BOLD, color=cur_p["TEXT_PRIMARY"], expand=True),
                                        ft.Container(
                                            bgcolor=badge_bg,
                                            border=ft.border.all(1, badge_fg),
                                            padding=ft.padding.symmetric(horizontal=12, vertical=5),
                                            border_radius=14,
                                            content=ft.Text(badge_label, size=12.5, color=badge_fg, weight=ft.FontWeight.W_600),
                                        ),
                                    ],
                                    spacing=10,
                                ),
                                ft.Row(
                                    [
                                        box_symptoms,
                                        box_isolation,
                                        box_treatment,
                                    ],
                                    spacing=14,
                                    vertical_alignment=ft.CrossAxisAlignment.START,
                                ),
                            ],
                            spacing=14,
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
                page=page,
                content=ft.Row([search_box, triage_chips_row], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ),
            ft.Container(padding=ft.padding.only(bottom=90), content=cards_col),
        ]

    # Tab 4: Trợ lý AI Thú y (Chatbot) — khởi tạo sẵn để đồng bộ 100% với Popup Chat góc phải
    main_chat_card, _ = build_chat_panel(
        page=page,
        user=user,
        get_diagnosis_context=lambda: state.get("result"),
        compact=False,
    )

    def build_chatbot_tab():
        from services.chatbot_service import refresh_all_chat_views

        refresh_all_chat_views(page)
        return [
            tech_banner(
                "Trợ lý AI Thú y (Chatbot)",
                "Chỉ giải đáp chuyên môn: Bệnh ngoài da ở heo, kết quả chẩn đoán mô hình Deep Learning (MobileNetV2, EfficientNet-B0) & hướng dẫn sử dụng PigSkinTech",
                badge_text="Domain Guardrail Active",
                page=page,
            ),
            main_chat_card,
        ]

    destinations = [
        ("Chẩn đoán bệnh", ft.Icons.IMAGE_SEARCH_OUTLINED, ft.Icons.IMAGE_SEARCH_ROUNDED),
        ("Lịch sử khám", ft.Icons.HISTORY_OUTLINED, ft.Icons.HISTORY_ROUNDED),
        ("Cẩm nang bệnh lý", ft.Icons.MENU_BOOK_OUTLINED, ft.Icons.MENU_BOOK_ROUNDED),
        ("Trợ lý AI Thú y (Chatbot)", ft.Icons.SMART_TOY_OUTLINED, ft.Icons.SMART_TOY_ROUNDED),
    ]

    return build_role_shell(
        page=page,
        user=user,
        title="Không gian Người Chăn Nuôi",
        destinations=destinations,
        tab_builders=[build_predict_tab, build_history_tab, build_wiki_tab, build_chatbot_tab],
    )
