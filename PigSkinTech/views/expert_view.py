"""Expert Role View (/expert - Chuyên gia thú y): Review Queue, Relabeling, Dataset Curation, Batch Inference."""
import asyncio

import flet as ft

from services.auth_service import (
    build_role_shell,
    create_file_picker,
    ensure_flet_compat,
    export_inspections_csv,
    export_vet_report_html,
    generate_lesion_heatmap,
    header_stat_pill,
    is_dark_mode,
    kpi_stat_card,
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
from services.clinical_widgets import (
    build_clinical_charts_section,
    build_disease_catalog_crud_card,
    open_disease_editor_modal,
)
from services.inference import predict_batch
from services.project_data import (
    active_run,
    display_class,
    get_class_info,
    list_class_keys,
    list_model_runs,
    load_classes_config,
)
from services.store import (
    approve_for_dataset,
    get_sample_gallery,
    get_system_stats,
    list_curated_candidates,
    list_review_queue,
    recent,
    submit_expert_review,
)
from theme import css_input


def _conf_color(conf: float) -> str:
    if conf >= 0.75:
        return "#10B981"
    if conf >= 0.60:
        return "#F59E0B"
    return "#EF4444"


def _case_code(case: dict | None) -> str:
    """Mã hồ sơ chuẩn: ưu tiên case_id, nếu rỗng sinh PS-xxxxxx từ id hoặc dùng animal_id."""
    case = case or {}
    return (str(case.get("case_id") or "").strip()) or (
        f"PS-{int(case['id']):06d}" if case.get("id") else (case.get("animal_id") or "PS-000001")
    )


REVIEW_PANEL_HEIGHT = 560


def build_expert_view(page: ft.Page, user: dict) -> ft.Control:
    ensure_flet_compat(page)
    batch_picker = create_file_picker(page)
    nav_ref = {"switch_tab": None}
    state = {
        "selected_case": None,
        "queue_filter": "all",
        "batch_paths": [],
        "batch_results": [],
        "expert_heatmap_mode": False,
    }

    def select_case_and_open_tab2(rec: dict):
        state["selected_case"] = rec
        state["expert_heatmap_mode"] = False
        if nav_ref.get("switch_tab"):
            nav_ref["switch_tab"](1)

    def _build_empty_state_card(
        title_text: str = "Hàng đợi thẩm định hiện đang trống",
        desc_text: str = (
            "Tất cả các ca bệnh do người chăn nuôi gửi lên đều đã được Chuyên gia xử lý hoàn tất, "
            "hoặc hiện chưa có yêu cầu hội chẩn mới."
        ),
        icon_name: object = ft.Icons.FACT_CHECK_ROUNDED,
        on_refresh=None,
        secondary_label: str = "Xem Kho Dataset chuẩn",
        secondary_icon: object = ft.Icons.DATASET_LINKED_ROUNDED,
        secondary_tab_idx: int = 2,
    ) -> ft.Container:
        cur_t = theme_tokens(page)
        dark = is_dark_mode(page)

        def _handle_refresh(e):
            if callable(on_refresh):
                on_refresh(e)
            elif nav_ref.get("switch_tab"):
                nav_ref["switch_tab"](1)
            show_snack(page, "Đã làm mới dữ liệu từ SQL Database!", "#059669")

        def _handle_secondary(e):
            if nav_ref.get("switch_tab"):
                nav_ref["switch_tab"](secondary_tab_idx)

        card = tech_card(
            page=page,
            padding=40,
            border_radius=20,
            bgcolor=cur_t["SURFACE"],
            border_color=cur_t["BORDER"],
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=14,
                tight=True,
                controls=[
                    ft.Container(
                        width=76,
                        height=76,
                        border_radius=38,
                        bgcolor=cur_t["EMERALD_SOFT"] if dark else "#ECFDF5",
                        alignment=ft.alignment.center,
                        content=ft.Icon(icon_name, size=40, color="#10B981"),
                    ),
                    ft.Text(
                        title_text,
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=cur_t["TEXT"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        desc_text,
                        size=14,
                        color=cur_t["MUTED"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=12,
                        wrap=True,
                        controls=[
                            ft.FilledButton(
                                "Làm mới danh sách",
                                icon=ft.Icons.REFRESH_ROUNDED,
                                on_click=_handle_refresh,
                            ),
                            ft.OutlinedButton(
                                secondary_label,
                                icon=secondary_icon,
                                on_click=_handle_secondary,
                            ),
                        ],
                    ),
                ],
            ),
        )
        card.width = 520
        return ft.Container(
            expand=True,
            alignment=ft.alignment.center,
            padding=ft.padding.symmetric(vertical=28),
            content=card,
        )

    # Tab 1: Review Queue
    def build_queue_tab():
        t = theme_tokens(page)
        all_items = list_review_queue(confidence_threshold=0.75)
        all_records = recent("")
        if state["selected_case"] is None and all_items:
            state["selected_case"] = all_items[0]

        pending_count = sum(1 for r in all_items if r.get("review_status") != "reviewed")
        low_conf_count = sum(1 for r in all_items if float(r.get("confidence") or 0.0) < 0.75)
        reviewed_total = sum(1 for r in all_records if r.get("review_status") == "reviewed")
        agreed_total = sum(
            1
            for r in all_records
            if r.get("review_status") == "reviewed" and int(r.get("agreed_with_ai") or 0) == 1
        )
        agreed_badge = f"Đồng thuận AI {agreed_total}/{reviewed_total}" if reviewed_total else "Chưa duyệt"

        header_pills = [
            header_stat_pill("Chờ thẩm định", str(pending_count), ft.Icons.PENDING_ACTIONS_ROUNDED, "#D97706", t["AMBER_SOFT"], "", page=page),
            header_stat_pill("Độ tin cậy thấp", str(low_conf_count), ft.Icons.WARNING_AMBER_ROUNDED, "#DC2626", t["RED_SOFT"], "Ưu tiên", page=page),
            header_stat_pill("Đã thẩm định", str(reviewed_total), ft.Icons.VERIFIED_ROUNDED, "#059669", t["EMERALD_SOFT"], agreed_badge, page=page),
        ]

        search_input = css_input(
            label="Tìm theo mã hồ sơ, người gửi hoặc trang trại...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            expand=True,
            page=page,
        )
        filter_chips_row = ft.Row(spacing=8, wrap=True)
        queue_col = ft.Column(spacing=14)

        filter_defs = [
            ("all", f"Tất cả ({len(all_items)})", ft.Icons.ALL_INBOX_ROUNDED),
            ("pending", f"Chờ duyệt ({pending_count})", ft.Icons.HOURGLASS_TOP_ROUNDED),
            ("low_conf", f"Độ tin cậy < 75% ({low_conf_count})", ft.Icons.SPEED_ROUNDED),
            ("reviewed", f"Đã duyệt ({len(all_items) - pending_count})", ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED),
        ]

        def set_queue_filter(key: str):
            state["queue_filter"] = key
            render_queue_items()
            page.update()

        def render_queue_items(e=None):
            cur_t = theme_tokens(page)
            cur_f = state["queue_filter"]
            q_str = (search_input.value or "").strip().lower()
            filter_chips_row.controls.clear()
            for f_key, f_label, f_icon in filter_defs:
                active = cur_f == f_key
                filter_chips_row.controls.append(
                    ft.Container(
                        bgcolor="#059669" if active else cur_t["SUB_SURFACE"],
                        border=ft.border.all(1, "#059669" if active else cur_t["BORDER"]),
                        padding=ft.padding.symmetric(horizontal=14, vertical=8),
                        border_radius=18,
                        ink=True,
                        on_click=lambda e, k=f_key: set_queue_filter(k),
                        content=ft.Row(
                            [
                                ft.Icon(f_icon, size=16, color="#FFFFFF" if active else cur_t["MUTED"]),
                                ft.Text(
                                    f_label,
                                    size=13,
                                    color="#FFFFFF" if active else cur_t["TEXT"],
                                    weight=ft.FontWeight.W_600,
                                ),
                            ],
                            spacing=6,
                            tight=True,
                        ),
                    )
                )

            filtered = all_items
            if cur_f == "pending":
                filtered = [r for r in all_items if r.get("review_status") != "reviewed"]
            elif cur_f == "low_conf":
                filtered = [r for r in all_items if float(r.get("confidence") or 0.0) < 0.75]
            elif cur_f == "reviewed":
                filtered = [r for r in all_items if r.get("review_status") == "reviewed"]
            if q_str:
                filtered = [
                    r
                    for r in filtered
                    if q_str in f"{r.get('case_id','')} {r.get('user_name','')} {r.get('farm_name','')} {r.get('animal_id','')}".lower()
                ]

            queue_col.controls.clear()
            if not filtered:
                queue_col.controls.append(
                    _build_empty_state_card(
                        title_text="Hàng đợi thẩm định hiện đang trống",
                        desc_text=(
                            "Tất cả các ca bệnh do người chăn nuôi gửi lên đều đã được Chuyên gia xử lý hoàn tất, "
                            "hoặc hiện chưa có yêu cầu hội chẩn mới khớp bộ lọc đã chọn."
                        ),
                        icon_name=ft.Icons.FACT_CHECK_ROUNDED,
                        on_refresh=lambda e: (nav_ref["switch_tab"](0) if nav_ref.get("switch_tab") else render_queue_items()),
                        secondary_label="Quản lý Danh mục Bệnh lý",
                        secondary_icon=ft.Icons.MEDICAL_SERVICES_ROUNDED,
                        secondary_tab_idx=3,
                    )
                )
                return

            for rec in filtered:
                conf = float(rec.get("confidence") or 0.0)
                c_color = _conf_color(conf)
                low_conf = conf < 0.75
                is_reviewed = rec.get("review_status") == "reviewed"
                reason_badges = []
                if int(rec.get("requested_review") or 0) == 1:
                    reason_badges.append(
                        ft.Container(
                            bgcolor="#0284C7",
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                            border_radius=10,
                            content=ft.Text("User gửi yêu cầu", size=12.5, color="#FFFFFF", weight=ft.FontWeight.W_600),
                        )
                    )
                if low_conf:
                    reason_badges.append(
                        ft.Container(
                            bgcolor="#DC2626",
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                            border_radius=10,
                            content=ft.Text(f"Độ tin cậy thấp ({conf*100:.1f}% < 75%)", size=12.5, color="#FFFFFF", weight=ft.FontWeight.W_600),
                        )
                    )
                status_chip = ft.Container(
                    bgcolor="#059669" if is_reviewed else "#D97706",
                    padding=ft.padding.symmetric(horizontal=12, vertical=5),
                    border_radius=10,
                    content=ft.Text(
                        "Đã thẩm định" if is_reviewed else "Chờ thẩm định",
                        size=12.5,
                        color="#FFFFFF",
                        weight=ft.FontWeight.W_600,
                    ),
                )

                queue_col.controls.append(
                    tech_card(
                        page=page,
                        padding=20,
                        hover_lift=True,
                        content=ft.Row(
                            [
                                preview_thumbnail_with_zoom(
                                    page,
                                    rec.get("image_path"),
                                    f"Ảnh bệnh án {rec.get('case_id')} • {display_class(rec.get('predicted_class'))}",
                                    width=88,
                                    height=88,
                                    border_radius=10,
                                ),
                                ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Text(
                                                    f"{rec.get('case_id')} • Người gửi: {rec.get('user_name')} ({rec.get('user_email')})",
                                                    size=15,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=cur_t["TEXT"],
                                                    expand=True,
                                                ),
                                                *reason_badges,
                                                status_chip,
                                            ],
                                            spacing=8,
                                        ),
                                        ft.Text(
                                            f"Cơ sở: {rec.get('farm_name') or '—'} • Cá thể: {rec.get('animal_id') or '—'} • Vị trí: {rec.get('body_site') or '—'}",
                                            size=13.5,
                                            color=cur_t["SECONDARY"],
                                        ),
                                        ft.Row(
                                            [
                                                ft.Text(
                                                    f"AI dự đoán: {rec.get('predicted_label') or display_class(rec.get('predicted_class'))} ({rec.get('predicted_class')})",
                                                    size=14,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=cur_t["CYAN"],
                                                    expand=True,
                                                ),
                                                ft.Text(
                                                    f"Độ tự tin: {conf*100:.1f}%",
                                                    size=14,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=c_color,
                                                ),
                                            ]
                                        ),
                                        ft.ProgressBar(value=conf, bar_height=7, color=c_color, bgcolor=cur_t["BORDER"]),
                                        ft.Text(
                                            f"Triệu chứng User mô tả: {rec.get('symptoms') or 'Không có ghi chú'}",
                                            size=13.5,
                                            color=cur_t["TEXT"],
                                        ),
                                    ],
                                    spacing=6,
                                    expand=True,
                                ),
                                ft.FilledButton(
                                    "Thẩm định ca này",
                                    icon=ft.Icons.RATE_REVIEW_ROUNDED,
                                    on_click=lambda e, r=rec: select_case_and_open_tab2(r),
                                ),
                            ],
                            spacing=16,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                )

        search_input.on_change = render_queue_items
        render_queue_items()
        sys_stats = get_system_stats()

        expert_kpi_row = ft.ResponsiveRow(
            [
                kpi_stat_card(
                    "Ca chờ thẩm định",
                    str(pending_count),
                    "Hàng đợi ưu tiên",
                    ft.Icons.PENDING_ACTIONS_ROUNDED,
                    accent="#D97706",
                    soft_bg=t["AMBER_SOFT"],
                    page=page,
                    col={"xs": 12, "sm": 6, "lg": 3},
                ),
                kpi_stat_card(
                    "Ca độ tin cậy < 75%",
                    str(low_conf_count),
                    "Cần hội chẩn kỹ",
                    ft.Icons.WARNING_AMBER_ROUNDED,
                    accent="#DC2626",
                    soft_bg=t["RED_SOFT"],
                    page=page,
                    col={"xs": 12, "sm": 6, "lg": 3},
                ),
                kpi_stat_card(
                    "Đã thẩm định lâm sàng",
                    str(reviewed_total),
                    agreed_badge,
                    ft.Icons.VERIFIED_ROUNDED,
                    accent="#059669",
                    soft_bg=t["EMERALD_SOFT"],
                    page=page,
                    col={"xs": 12, "sm": 6, "lg": 3},
                ),
                kpi_stat_card(
                    "Ảnh Dataset chuẩn",
                    str(sys_stats.get("curated_count", 0)),
                    "Chuẩn hóa huấn luyện",
                    ft.Icons.DATASET_LINKED_ROUNDED,
                    accent="#0284C7",
                    soft_bg=t["CYAN_SOFT"],
                    page=page,
                    col={"xs": 12, "sm": 6, "lg": 3},
                ),
            ],
            run_spacing=16,
            spacing=16,
        )

        return [
            tech_banner(
                "Tổng quan & Hàng đợi Thẩm định Chuyên gia",
                "Giám sát thống kê dịch tễ, rà soát các ca bệnh do Người chăn nuôi gửi lên và kê phác đồ điều trị thú y",
                pills=header_pills,
                page=page,
            ),
            expert_kpi_row,
            build_clinical_charts_section(page, sys_stats),
            tech_card(
                page=page,
                padding=18,
                content=ft.Row(
                    [
                        search_input,
                        filter_chips_row,
                        ft.OutlinedButton(
                            "📥 Xuất Báo cáo CSV",
                            icon=ft.Icons.DOWNLOAD_ROUNDED,
                            on_click=lambda e: export_inspections_csv(page, all_items, "BaoCao_ThamDinh_Expert"),
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
            ft.Container(padding=ft.padding.only(bottom=90), content=queue_col),
        ]

    # Tab 2: Diagnosis & Relabeling
    def build_relabel_tab():
        t = theme_tokens(page)
        queue_items = list_review_queue(confidence_threshold=0.75)
        rec = state["selected_case"] or (queue_items[0] if queue_items else None)
        if not rec:
            empty_pills = [
                header_stat_pill(
                    "Mã hồ sơ",
                    "Trống",
                    ft.Icons.FOLDER_SHARED_ROUNDED,
                    "#0284C7",
                    t["CYAN_SOFT"],
                    "0 ca chờ",
                    page=page,
                ),
                header_stat_pill(
                    "Độ tin cậy AI",
                    "100%",
                    ft.Icons.AUTO_GRAPH_ROUNDED,
                    "#10B981",
                    t["EMERALD_SOFT"],
                    "Đã xử lý hết",
                    page=page,
                ),
                header_stat_pill(
                    "Trạng thái",
                    "Hoàn tất",
                    ft.Icons.VERIFIED_ROUNDED,
                    "#059669",
                    t["EMERALD_SOFT"],
                    "Hội chẩn chuyên khoa",
                    page=page,
                ),
            ]
            return [
                tech_banner(
                    "Chi tiết Thẩm định & Gán nhãn",
                    "Xác nhận hoặc hiệu chỉnh nhãn bệnh của AI và kê phác đồ điều trị trả về cho chủ trại",
                    pills=empty_pills,
                    page=page,
                ),
                _build_empty_state_card(
                    title_text="Hàng đợi thẩm định hiện đang trống",
                    desc_text=(
                        "Tất cả các ca bệnh do người chăn nuôi gửi lên đều đã được Chuyên gia xử lý hoàn tất, "
                        "hoặc hiện chưa có yêu cầu hội chẩn mới."
                    ),
                    icon_name=ft.Icons.FACT_CHECK_ROUNDED,
                    on_refresh=lambda e: nav_ref["switch_tab"](1) if nav_ref.get("switch_tab") else None,
                    secondary_label="Xem Kho Dataset chuẩn",
                    secondary_icon=ft.Icons.DATASET_LINKED_ROUNDED,
                    secondary_tab_idx=2,
                ),
            ]
        state["selected_case"] = rec
        case_code = _case_code(rec)

        case_options = [
            (
                str(it["id"]),
                f"{_case_code(it)} - {it.get('predicted_label') or display_class(it.get('predicted_class'))} ({it.get('predicted_class')}) ({float(it.get('confidence') or 0)*100:.1f}%)",
            )
            for it in queue_items
        ]

        def on_switch_case(e):
            chosen_id = int(case_selector.value or rec["id"])
            found = next((x for x in queue_items if int(x["id"]) == chosen_id), None)
            if found:
                state["selected_case"] = found
                state["expert_heatmap_mode"] = False
                if nav_ref.get("switch_tab"):
                    nav_ref["switch_tab"](1)

        case_selector = make_dropdown(
            "Chọn hồ sơ cần thẩm định",
            str(rec["id"]),
            case_options,
            on_change=on_switch_case,
            width=440,
            page=page,
        )

        conf = float(rec.get("confidence") or 0.0)
        c_color = _conf_color(conf)
        pred_code = rec.get("predicted_class") or "Healthy"
        initial_agreed = "agree" if (rec.get("agreed_with_ai") in (None, 1)) else "relabel"
        initial_label = rec.get("expert_label") or pred_code
        default_tx = rec.get("expert_note") or get_class_info(initial_label).get("treatment", "")

        class_options = [(code, f"{display_class(code)} ({code})") for code in list_class_keys()]
        relabel_dropdown = make_dropdown(
            "Chọn nhãn bệnh lý chuẩn hóa",
            initial_label,
            class_options,
            expand=True,
            page=page,
        )
        relabel_dropdown.disabled = initial_agreed == "agree"

        treatment_note = css_input(
            label="Ghi chú phác đồ điều trị & Lời khuyên dùng thuốc gửi trả về cho Người chăn nuôi",
            value=default_tx,
            multiline=True,
            min_lines=3,
            max_lines=5,
            expand=True,
            page=page,
        )

        def on_decision_change(e):
            is_agree = decision_group.value == "agree"
            relabel_dropdown.disabled = is_agree
            target_cls = pred_code if is_agree else (relabel_dropdown.value or pred_code)
            if not treatment_note.value.strip():
                treatment_note.value = get_class_info(target_cls).get("treatment", "")
            page.update()

        decision_group = ft.RadioGroup(
            value=initial_agreed,
            on_change=on_decision_change,
            content=ft.Row(
                [
                    ft.Radio(
                        value="agree",
                        label=f"Đồng ý với AI ({rec.get('predicted_label') or display_class(pred_code)})",
                    ),
                    ft.Radio(value="relabel", label="Sửa lại nhãn bệnh (Relabel)"),
                ],
                spacing=24,
            ),
        )

        def handle_submit_review(e):
            is_agree = decision_group.value == "agree"
            chosen_label = pred_code if is_agree else (relabel_dropdown.value or pred_code)
            submit_expert_review(
                record_id=int(rec["id"]),
                agreed_with_ai=is_agree,
                expert_label=chosen_label,
                expert_note=treatment_note.value or "",
                expert_email=user.get("email", "bs.thuy.pigskin@gmail.com"),
            )
            refreshed = list_review_queue(confidence_threshold=0.75)
            state["selected_case"] = next((x for x in refreshed if int(x["id"]) == int(rec["id"])), rec)
            show_snack(
                page,
                f"Đã lưu kết quả thẩm định hồ sơ {case_code} và gửi phác đồ về cho User!",
                "#059669",
            )
            if nav_ref.get("switch_tab"):
                nav_ref["switch_tab"](1)

        queue_thumb_row = ft.Row(
            [
                ft.Container(
                    padding=3,
                    border_radius=10,
                    border=ft.border.all(2 if int(it["id"]) == int(rec["id"]) else 1, "#10B981" if int(it["id"]) == int(rec["id"]) else t["BORDER"]),
                    ink=True,
                    tooltip=f"Chuyển sang {_case_code(it)} ({display_class(it.get('predicted_class'))})",
                    on_click=lambda e, item=it: select_case_and_open_tab2(item),
                    content=make_image(it.get("image_path") or "", width=60, height=60, border_radius=8),
                )
                for it in queue_items[:12]
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
        )

        # Khung hiển thị ảnh DUY NHẤT (height=300) — bật Heatmap cập nhật trực tiếp lên chính khung này
        image_preview_host = ft.Container(
            height=300,
            border_radius=12,
            padding=6,
            alignment=ft.alignment.center,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ink=True,
            tooltip="Nhấn để phóng to ảnh",
        )
        heatmap_toggle_host = ft.Container()

        def render_expert_image_preview():
            cur_t = theme_tokens(page)
            is_hm = bool(state.get("expert_heatmap_mode"))
            orig_path = rec.get("image_path") or ""
            shown_path = generate_lesion_heatmap(orig_path) if is_hm else orig_path
            image_preview_host.bgcolor = cur_t["SUB_SURFACE"] if is_dark_mode(page) else "#F8FAFC"
            image_preview_host.border = ft.border.all(1.5 if is_hm else 1, "#D97706" if is_hm else cur_t["BORDER"])
            image_preview_host.on_click = lambda e: open_image_zoom_dialog(
                page,
                shown_path,
                f"Hồ sơ {case_code}{' • AI Heatmap' if is_hm else ''}",
            )
            image_preview_host.content = make_image(
                shown_path,
                width=None,
                height=288,
                border_radius=10,
                fit=ft.ImageFit.CONTAIN,
            )
            heatmap_toggle_host.content = ft.Container(
                bgcolor="#D97706" if is_hm else cur_t["EMERALD_SOFT"],
                border=ft.border.all(1, "#D97706" if is_hm else "#10B981"),
                padding=ft.padding.symmetric(horizontal=10, vertical=7),
                border_radius=10,
                ink=True,
                on_click=toggle_expert_heatmap,
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.THERMOSTAT_AUTO_ROUNDED if is_hm else ft.Icons.BIOTECH_ROUNDED,
                            size=16,
                            color="#FFFFFF" if is_hm else cur_t["EMERALD"],
                        ),
                        ft.Text(
                            "Đang bật Heatmap (Tắt)" if is_hm else "Soi vùng tổn thương AI",
                            size=12.5,
                            weight=ft.FontWeight.W_600,
                            color="#FFFFFF" if is_hm else cur_t["EMERALD"],
                            no_wrap=True,
                        ),
                    ],
                    spacing=6,
                    tight=True,
                ),
            )

        def toggle_expert_heatmap(e):
            state["expert_heatmap_mode"] = not bool(state.get("expert_heatmap_mode"))
            render_expert_image_preview()
            if state["expert_heatmap_mode"]:
                show_snack(page, "🔬 Đã bật chế độ soi vùng tổn thương AI cho chuyên gia thú y.", "#D97706")
            page.update()

        def handle_export_expert_report(e):
            is_agree = decision_group.value == "agree"
            chosen_label = pred_code if is_agree else (relabel_dropdown.value or pred_code)
            cls_meta = get_class_info(chosen_label)
            scores = rec.get("scores_json") or {pred_code: conf}
            export_vet_report_html(
                page,
                {
                    "case_id": case_code,
                    "created_at": rec.get("created_at") or "",
                    "farm_name": rec.get("farm_name") or "Trang trại chăn nuôi",
                    "animal_id": rec.get("animal_id") or "Chưa gán thẻ",
                    "pig_age": rec.get("pig_age") or "—",
                    "body_site": rec.get("body_site") or "Toàn thân",
                    "symptoms": rec.get("symptoms") or "Không có ghi chú",
                    "image_path": rec.get("image_path") or "",
                    "predicted_class": chosen_label,
                    "confidence": conf,
                    "danger_level": cls_meta.get("danger_level", "Trung bình"),
                    "scores": scores if isinstance(scores, dict) else {pred_code: conf},
                    "expert_label": chosen_label,
                    "expert_note": (treatment_note.value or "").strip() or cls_meta.get("treatment", ""),
                    "reviewed_by": user.get("email", "bs.thuy.pigskin@gmail.com"),
                },
            )

        render_expert_image_preview()

        left_panel = tech_card(
            page=page,
            padding=20,
            content=ft.Column(
                [
                    # 1. Header nhỏ: Icon + Tiêu đề + 2 nút thao tác nằm gọn bên phải
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.IMAGE_SEARCH_ROUNDED, color=t["CYAN"], size=22),
                            ft.Text(
                                "Hình ảnh Lâm sàng Cần Thẩm định",
                                size=16.5,
                                weight=ft.FontWeight.BOLD,
                                color=t["TEXT"],
                                expand=True,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            heatmap_toggle_host,
                            ft.OutlinedButton(
                                "Phóng to ảnh (Zoom)",
                                icon=ft.Icons.ZOOM_IN_ROUNDED,
                                on_click=lambda e: open_image_zoom_dialog(page, rec.get("image_path"), f"Hồ sơ {case_code}"),
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    # 2. Khung ảnh chính duy nhất (height=300, CONTAIN, nền #F8FAFC)
                    image_preview_host,
                    # 3. Thumbnails hàng đợi + Thông tin hồ sơ
                    ft.Text("Chuyển nhanh qua ảnh thật trong hàng đợi (click ảnh để thẩm định):", size=12.5, weight=ft.FontWeight.W_600, color=t["SECONDARY"]),
                    queue_thumb_row,
                    ft.Text(f"Mã hồ sơ: {case_code} • Thời gian gửi: {rec.get('created_at') or '—'}", size=14, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                    ft.Text(f"Người chăn nuôi: {rec.get('user_name') or '—'} ({rec.get('user_email') or '—'})", size=13.5, color=t["CYAN"], weight=ft.FontWeight.W_600),
                    ft.Text(f"Trang trại: {rec.get('farm_name') or '—'} • Mã cá thể: {rec.get('animal_id') or '—'}", size=13, color=t["SECONDARY"]),
                    ft.Text(f"Triệu chứng ghi nhận: {rec.get('symptoms') or 'Không có'}", size=13.5, color=t["TEXT"]),
                ],
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
            ),
        )
        left_panel.height = REVIEW_PANEL_HEIGHT

        right_panel = tech_card(
            page=page,
            padding=20,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.FACT_CHECK_ROUNDED, color="#10B981", size=22),
                            ft.Text("Kết quả AI & Quyết định của Chuyên gia", size=18, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                        ],
                        spacing=8,
                    ),
                    ft.Container(
                        bgcolor=t["SUB_SURFACE"],
                        padding=16,
                        border_radius=12,
                        border=ft.border.all(1, c_color),
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text("AI dự đoán:", size=14, color=t["SECONDARY"]),
                                        ft.Column(
                                            [
                                                ft.Text(
                                                    rec.get("predicted_label") or display_class(pred_code),
                                                    size=16.5,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=t["CYAN"],
                                                ),
                                                ft.Text(f"Mã lớp: {pred_code}", size=12.5, color=t["SECONDARY"]),
                                            ],
                                            spacing=2,
                                            expand=True,
                                        ),
                                        ft.Text(f"{conf*100:.1f}%", size=17, weight=ft.FontWeight.BOLD, color=c_color),
                                    ],
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.ProgressBar(value=conf, bar_height=9, color=c_color, bgcolor=t["BORDER"]),
                            ],
                            spacing=6,
                        ),
                    ),
                    ft.Text("1. Đánh giá nhãn chẩn đoán (Human-in-the-Loop):", size=14.5, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                    decision_group,
                    ft.Row([relabel_dropdown]),
                    ft.Text("2. Phác đồ điều trị & Lời khuyên dùng thuốc gửi User:", size=14.5, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                    ft.Row([treatment_note]),
                    ft.Row(
                        [
                            ft.FilledButton(
                                "Xác nhận Thẩm định & Gửi Phác đồ cho User",
                                icon=ft.Icons.VERIFIED_ROUNDED,
                                on_click=handle_submit_review,
                            ),
                            ft.OutlinedButton(
                                "🖨️ Xuất Phiếu Khám",
                                icon=ft.Icons.PRINT_ROUNDED,
                                on_click=handle_export_expert_report,
                            ),
                        ],
                        spacing=10,
                        wrap=True,
                    ),
                ],
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
            ),
        )
        right_panel.height = REVIEW_PANEL_HEIGHT

        relabel_pills = [
            header_stat_pill(
                "Mã hồ sơ",
                case_code,
                ft.Icons.FOLDER_SHARED_ROUNDED,
                "#0284C7",
                t["CYAN_SOFT"],
                rec.get("animal_id") or "Cá thể",
                page=page,
            ),
            header_stat_pill(
                "Độ tin cậy AI",
                f"{conf*100:.1f}%",
                ft.Icons.AUTO_GRAPH_ROUNDED,
                c_color,
                t["EMERALD_SOFT"] if conf >= 0.75 else t["AMBER_SOFT"],
                display_class(pred_code),
                page=page,
            ),
            header_stat_pill(
                "Trạng thái",
                "Đã duyệt" if rec.get("review_status") == "reviewed" else "Chờ duyệt",
                ft.Icons.FACT_CHECK_ROUNDED,
                "#059669" if rec.get("review_status") == "reviewed" else "#D97706",
                t["EMERALD_SOFT"] if rec.get("review_status") == "reviewed" else t["AMBER_SOFT"],
                "Hội chẩn chuyên khoa",
                page=page,
            ),
        ]

        return [
            tech_banner(
                "Chi tiết Thẩm định & Gán nhãn",
                "Xác nhận hoặc hiệu chỉnh nhãn bệnh của AI và kê phác đồ điều trị trả về cho chủ trại",
                pills=relabel_pills,
                page=page,
            ),
            tech_card(
                page=page,
                padding=12,
                content=ft.Row(
                    [ft.Text("Chuyển nhanh hồ sơ:", size=14.5, weight=ft.FontWeight.BOLD, color=t["TEXT"]), case_selector],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
            # 2 cột Trái (Hình ảnh) & Phải (Kết quả AI & Quyết định) ngang bằng nhau, căn trên, cùng chiều cao
            ft.ResponsiveRow(
                [
                    ft.Container(col={"xs": 12, "lg": 6}, content=left_panel),
                    ft.Container(col={"xs": 12, "lg": 6}, content=right_panel),
                ],
                run_spacing=18,
                spacing=18,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
        ]

    # Tab 3: Dataset Curation
    def build_curation_tab():
        list_col = ft.Column(spacing=14)
        dist_host = ft.Container()
        curation_header_host = ft.Container()

        def refresh_curation(e=None):
            t = theme_tokens(page)
            candidates = list_curated_candidates()
            classes_cfg = load_classes_config()
            class_counts = {k: 0 for k in classes_cfg.keys()}
            for c in candidates:
                if int(c.get("in_dataset") or 0) == 1:
                    lbl = c.get("expert_label") or c.get("predicted_class") or "Healthy"
                    class_counts[lbl] = class_counts.get(lbl, 0) + 1
            curated_sum = sum(class_counts.values())
            total_curated = max(1, curated_sum)
            agreed_sum = sum(1 for c in candidates if int(c.get("agreed_with_ai") or 0) == 1)

            curation_pills = [
                header_stat_pill(
                    "Ca đã thẩm định",
                    str(len(candidates)),
                    ft.Icons.FACT_CHECK_ROUNDED,
                    "#0284C7",
                    t["CYAN_SOFT"],
                    "Hồ sơ chuyên gia",
                    page=page,
                ),
                header_stat_pill(
                    "Đã đưa vào Dataset",
                    str(curated_sum),
                    ft.Icons.DATASET_LINKED_ROUNDED,
                    "#059669",
                    t["EMERALD_SOFT"],
                    f"{len(classes_cfg)} nhóm bệnh",
                    page=page,
                ),
                header_stat_pill(
                    "Đồng thuận AI",
                    f"{agreed_sum}/{len(candidates)}",
                    ft.Icons.VERIFIED_ROUNDED,
                    "#D97706",
                    t["AMBER_SOFT"],
                    "Chuẩn lâm sàng",
                    page=page,
                ),
            ]
            curation_header_host.content = tech_banner(
                "Đóng góp Dataset Chuẩn Lâm sàng",
                "Danh sách các ca bệnh đã được Chuyên gia chuẩn hóa nhãn để huấn luyện nâng cao cho Trí tuệ nhân tạo PigSkin AI",
                pills=curation_pills,
                page=page,
            )

            dist_bars = []
            for code, info in list(classes_cfg.items())[:6]:
                cnt = class_counts.get(code, 0)
                ratio = cnt / total_curated if curated_sum > 0 else 0.0
                dist_bars.append(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(f"{info.get('name_vi', code)} ({code})", size=14, weight=ft.FontWeight.W_600, color=t["TEXT"], expand=True),
                                    ft.Text(f"{cnt} ảnh chuẩn ({ratio*100:.0f}%)", size=13, weight=ft.FontWeight.BOLD, color=t["EMERALD"]),
                                ]
                            ),
                            ft.ProgressBar(value=ratio, bar_height=7, color=t["EMERALD"], bgcolor=t["BORDER"]),
                        ],
                        spacing=4,
                    )
                )

            dist_host.content = tech_card(
                page=page,
                padding=22,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.PIE_CHART_ROUNDED, color=t["EMERALD"], size=22),
                                ft.Text(
                                    f"Phân bố mẫu chuẩn hóa theo {len(classes_cfg)} nhóm bệnh lý",
                                    size=18,
                                    weight=ft.FontWeight.BOLD,
                                    color=t["TEXT"],
                                    expand=True,
                                ),
                                ft.Text(f"Đã duyệt: {curated_sum}/{len(candidates)} ca", size=14, weight=ft.FontWeight.BOLD, color=t["CYAN"]),
                            ]
                        ),
                        *dist_bars,
                    ],
                    spacing=10,
                ),
            )

            list_col.controls.clear()
            if not candidates:
                list_col.controls.append(
                    _build_empty_state_card(
                        title_text="Chưa có ca bệnh nào được thẩm định vào Dataset",
                        desc_text=(
                            "Khi Chuyên gia hoàn tất thẩm định các ca bệnh từ hàng đợi, hồ sơ chuẩn hóa nhãn "
                            "sẽ hiển thị tại đây để duyệt đưa vào bộ dữ liệu huấn luyện AI."
                        ),
                        icon_name=ft.Icons.VERIFIED_ROUNDED,
                        on_refresh=refresh_curation,
                        secondary_label="Quản lý Danh mục Bệnh lý",
                        secondary_icon=ft.Icons.MEDICAL_SERVICES_ROUNDED,
                        secondary_tab_idx=3,
                    )
                )
                page.update()
                return
            for item in candidates:
                in_ds = int(item.get("in_dataset") or 0) == 1
                final_cls = item.get("expert_label") or item.get("predicted_class")
                agreed = int(item.get("agreed_with_ai") or 0) == 1
                conf = float(item.get("confidence") or 0.0)
                list_col.controls.append(
                    tech_card(
                        page=page,
                        padding=20,
                        content=ft.Row(
                            [
                                preview_thumbnail_with_zoom(
                                    page,
                                    item.get("image_path"),
                                    f"Dataset {item.get('case_id')} • {display_class(final_cls)}",
                                    width=88,
                                    height=88,
                                    border_radius=10,
                                ),
                                ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Text(
                                                    f"{item.get('case_id')} • Nhãn chuẩn hóa: {display_class(final_cls)} ({final_cls})",
                                                    size=15,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=t["TEXT"],
                                                    expand=True,
                                                ),
                                                ft.Container(
                                                    bgcolor="#059669" if agreed else "#D97706",
                                                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                                                    border_radius=10,
                                                    content=ft.Text(
                                                        "Đồng ý với AI" if agreed else f"Đã sửa từ: {display_class(item.get('predicted_class'))}",
                                                        size=12.5,
                                                        color="#FFFFFF",
                                                        weight=ft.FontWeight.W_600,
                                                    ),
                                                ),
                                            ]
                                        ),
                                        ft.Text(
                                            f"Thẩm định bởi: {item.get('reviewed_by')} lúc {item.get('reviewed_at')} • Độ tin cậy AI: {conf*100:.1f}%",
                                            size=13.5,
                                            color=t["SECONDARY"],
                                        ),
                                        ft.ProgressBar(value=conf, bar_height=7, color=_conf_color(conf), bgcolor=t["BORDER"]),
                                        ft.Text(f"Ghi chú chuyên môn: {item.get('expert_note')}", size=13.5, color=t["TEXT"]),
                                    ],
                                    spacing=6,
                                    expand=True,
                                ),
                                (
                                    ft.Container(
                                        bgcolor=t["EMERALD_SOFT"],
                                        border=ft.border.all(1, "#10B981"),
                                        padding=ft.padding.symmetric(horizontal=14, vertical=9),
                                        border_radius=10,
                                        content=ft.Row(
                                            [
                                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=t["EMERALD"], size=18),
                                                ft.Text("Đã đưa vào Dataset chuẩn", size=13, color=t["EMERALD"], weight=ft.FontWeight.BOLD),
                                            ],
                                            spacing=6,
                                        ),
                                    )
                                    if in_ds
                                    else ft.FilledButton(
                                        "Duyệt vào Dataset chuẩn",
                                        icon=ft.Icons.DATASET_LINKED_ROUNDED,
                                        on_click=lambda e, rid=item["id"]: (
                                            approve_for_dataset(rid, True),
                                            refresh_curation(),
                                            show_snack(page, f"Đã lưu ảnh ca PS-{rid:06d} vào bộ dữ liệu chuẩn lâm sàng!", "#059669"),
                                        ),
                                    )
                                ),
                            ],
                            spacing=16,
                        ),
                    )
                )
            page.update()

        refresh_curation()
        return [
            curation_header_host,
            build_clinical_charts_section(page, get_system_stats()),
            dist_host,
            ft.Container(padding=ft.padding.only(bottom=90), content=list_col),
        ]

    # Tab 4: Batch Inference
    def build_batch_tab():
        t = theme_tokens(page)
        runs = list_model_runs()
        cur_r = active_run() or {}
        default_run = state.get("batch_run") or cur_r.get("name") or (runs[0]["name"] if runs else "")
        state["batch_run"] = default_run

        batch_model_dd = make_dropdown(
            label="Kiến trúc mô hình kiểm thử",
            value=default_run,
            options=[
                (r["name"], f"{r.get('model_label', r['model'])} ({r['name']})")
                for r in runs
            ]
            or [("default", "MobileNetV2")],
            on_change=lambda e: state.update({"batch_run": e.control.value}),
            width=290,
            page=page,
        )

        status_text = ft.Text(
            f"Đã chọn {len(state['batch_paths'])} ảnh để kiểm thử." if state["batch_paths"] else "Chưa chọn lô ảnh kiểm thử.",
            size=14,
            color=t["SECONDARY"],
        )
        progress = ft.ProgressBar(visible=False, color="#0284C7")
        summary_row = ft.ResponsiveRow(run_spacing=16, spacing=16)
        results_col = ft.Column(spacing=14)
        batch_header_host = ft.Container()

        def refresh_batch_header():
            cur_t = theme_tokens(page)
            results = state["batch_results"]
            valid = [r for r in results if r.get("mode") == "ai"]
            avg_conf = (sum(float(r.get("confidence") or 0) for r in valid) / len(valid) * 100.0) if valid else 0.0
            batch_pills = [
                header_stat_pill(
                    "Ảnh đã chọn",
                    str(len(state["batch_paths"])),
                    ft.Icons.COLLECTIONS_ROUNDED,
                    "#0284C7",
                    cur_t["CYAN_SOFT"],
                    "Sẵn sàng phân tích",
                    page=page,
                ),
                header_stat_pill(
                    "Đã phân tích",
                    str(len(results)),
                    ft.Icons.BOLT_ROUNDED,
                    "#059669",
                    cur_t["EMERALD_SOFT"],
                    "Xử lý hàng loạt",
                    page=page,
                ),
                header_stat_pill(
                    "Độ tin cậy TB",
                    f"{avg_conf:.1f}%",
                    ft.Icons.ANALYTICS_ROUNDED,
                    "#D97706",
                    cur_t["AMBER_SOFT"],
                    "Tensor Softmax",
                    page=page,
                ),
            ]
            batch_header_host.content = tech_banner(
                "Phân tích Hàng loạt & Kiểm thử Chuyên sâu",
                "Tải nhiều ảnh cùng lúc để phân tích hàng loạt và đánh giá độ nhạy của Trí tuệ nhân tạo PigSkin AI",
                pills=batch_pills,
                page=page,
            )

        def render_batch_results():
            cur_t = theme_tokens(page)
            refresh_batch_header()
            summary_row.controls.clear()
            results_col.controls.clear()
            results = state["batch_results"]
            if not results:
                return
            valid = [r for r in results if r.get("mode") == "ai"]
            avg_conf = (sum(float(r.get("confidence") or 0) for r in valid) / len(valid) * 100.0) if valid else 0.0
            low_sens = sum(1 for r in valid if float(r.get("confidence") or 0) < 0.75)

            summary_row.controls.extend(
                [
                    kpi_stat_card(
                        "Tổng số ảnh đã phân tích",
                        str(len(results)),
                        "Kiểm thử song song",
                        ft.Icons.COLLECTIONS_ROUNDED,
                        "#0284C7",
                        cur_t["CYAN_SOFT"],
                        page=page,
                        col={"xs": 12, "sm": 6, "lg": 4},
                    ),
                    kpi_stat_card(
                        "Độ tự tin trung bình",
                        f"{avg_conf:.1f}%",
                        "Độ tin cậy Softmax",
                        ft.Icons.ANALYTICS_ROUNDED,
                        "#059669",
                        cur_t["EMERALD_SOFT"],
                        page=page,
                        col={"xs": 12, "sm": 6, "lg": 4},
                    ),
                    kpi_stat_card(
                        "Số ca dưới ngưỡng nhạy 75%",
                        str(low_sens),
                        "Cần hội chẩn chuyên khoa",
                        ft.Icons.WARNING_AMBER_ROUNDED,
                        "#DC2626",
                        cur_t["RED_SOFT"],
                        page=page,
                        col={"xs": 12, "sm": 6, "lg": 4},
                    ),
                ]
            )

            for idx, r in enumerate(results, start=1):
                conf = float(r.get("confidence") or 0.0)
                c_col = _conf_color(conf)
                img_path = (r.get("info") or {}).get("path")
                img_name = (r.get("info") or {}).get("name", f"Image #{idx}")
                arch = r.get("architecture") or r.get("model_label") or "MobileNetV2"
                ms = r.get("inference_ms", "-")
                top3 = r.get("top3") or (r.get("scores") or [])[:3]
                top3_txt = " • ".join(
                    f"{display_class(s.get('label'))}: {float(s.get('confidence') or 0)*100:.1f}%"
                    for s in top3
                )
                results_col.controls.append(
                    tech_card(
                        page=page,
                        padding=18,
                        content=ft.Row(
                            [
                                preview_thumbnail_with_zoom(page, img_path, img_name, width=88, height=88, border_radius=10),
                                ft.Column(
                                    [
                                        ft.Text(
                                            f"#{idx} • {img_name} ({arch} • {ms} ms)",
                                            size=14.5,
                                            weight=ft.FontWeight.BOLD,
                                            color=cur_t["TEXT"],
                                        ),
                                        ft.Text(
                                            f"AI dự đoán: {r.get('display_label')} ({r.get('label')})",
                                            size=14,
                                            color=cur_t["CYAN"],
                                            weight=ft.FontWeight.W_600,
                                        ),
                                        ft.Text(
                                            f"Top-3 Softmax: {top3_txt}",
                                            size=12.5,
                                            color=cur_t["SECONDARY"],
                                        ),
                                        ft.ProgressBar(value=conf, bar_height=7, color=c_col, bgcolor=cur_t["BORDER"]),
                                    ],
                                    spacing=5,
                                    expand=True,
                                ),
                                ft.Text(f"{conf*100:.1f}%", size=17, weight=ft.FontWeight.BOLD, color=c_col),
                            ],
                            spacing=16,
                        ),
                    )
                )

        def on_batch_picked(paths: list[str]):
            state["batch_paths"] = paths
            status_text.value = f"Đã nạp {len(paths)} ảnh: {', '.join(p.split('/')[-1].split(chr(92))[-1] for p in paths[:5])}"
            refresh_batch_header()
            page.update()

        def handle_load_sample_batch(e):
            sample_paths = [s["image_path"] for s in get_sample_gallery() if s.get("exists")]
            on_batch_picked(sample_paths)
            show_snack(page, f"Đã nạp bộ {len(sample_paths)} ảnh mẫu lâm sàng!", "#0284C7")

        async def handle_pick_batch(e):
            await pick_image_files(batch_picker, allow_multiple=True, on_picked=on_batch_picked)

        async def handle_run_batch(e):
            if not state["batch_paths"]:
                show_snack(page, "Vui lòng chọn ít nhất 1 ảnh để phân tích hàng loạt.", "#DC2626")
                return
            progress.visible = True
            status_text.value = "Đang phân tích hàng loạt bằng Trí tuệ nhân tạo PigSkin AI..."
            page.update()
            try:
                res = await asyncio.to_thread(predict_batch, state["batch_paths"], state.get("batch_run"))
                state["batch_results"] = res
                status_text.value = f"Hoàn tất kiểm thử {len(res)} ảnh!"
                render_batch_results()
                show_snack(page, f"Đã phân tích xong {len(res)} ảnh!", "#059669")
            finally:
                progress.visible = False
                page.update()

        render_batch_results()
        return [
            batch_header_host,
            tech_card(
                page=page,
                padding=20,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                batch_model_dd,
                                ft.OutlinedButton("Chọn nhiều ảnh (Batch)", icon=ft.Icons.COLLECTIONS_ROUNDED, on_click=handle_pick_batch),
                                ft.OutlinedButton("Nạp bộ 5 ảnh mẫu lâm sàng", icon=ft.Icons.AUTO_AWESOME_MOTION_ROUNDED, on_click=handle_load_sample_batch),
                                ft.FilledButton("Chạy Phân tích Hàng loạt", icon=ft.Icons.BOLT_ROUNDED, on_click=handle_run_batch),
                                status_text,
                            ],
                            spacing=12,
                            wrap=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        progress,
                    ],
                    spacing=10,
                ),
            ),
            summary_row,
            ft.Container(padding=ft.padding.only(bottom=90), content=results_col),
        ]

    # Tab 5: Danh mục Bệnh lý & Phác đồ (Expert Clinical Catalog CRUD)
    def build_catalog_tab():
        catalog_header_host = ft.Container()

        def refresh_catalog_header():
            cur_t = theme_tokens(page)
            latest = load_classes_config()
            urgent_cnt = sum(1 for v in latest.values() if v.get("danger_level") in ("Cao", "Khẩn cấp"))
            safe_cnt = sum(1 for k, v in latest.items() if v.get("danger_level") in ("An toàn", "Thấp") or k == "Healthy")
            catalog_pills = [
                header_stat_pill(
                    "Nhóm bệnh lý chuẩn",
                    str(len(latest)),
                    ft.Icons.MEDICAL_SERVICES_ROUNDED,
                    "#059669",
                    cur_t["EMERALD_SOFT"],
                    "Đồng bộ classes.json & SQL",
                    page=page,
                ),
                header_stat_pill(
                    "Mức nguy hiểm cao",
                    str(urgent_cnt),
                    ft.Icons.WARNING_AMBER_ROUNDED,
                    "#DC2626",
                    cur_t["RED_SOFT"],
                    "Cần cách ly khẩn",
                    page=page,
                ),
                header_stat_pill(
                    "Nhóm an toàn / nhẹ",
                    str(safe_cnt),
                    ft.Icons.HEALTH_AND_SAFETY_ROUNDED,
                    "#0284C7",
                    cur_t["CYAN_SOFT"],
                    "Theo dõi định kỳ",
                    page=page,
                ),
            ]
            catalog_header_host.content = tech_banner(
                "Quản lý Danh mục Bệnh lý & Phác đồ Điều trị",
                "Chuyên gia Thú y thêm mới lớp bệnh, cập nhật triệu chứng nhận diện, biện pháp phòng ngừa và phác đồ điều trị chuẩn",
                pills=catalog_pills,
                page=page,
            )

        refresh_catalog_header()
        crud_card = build_disease_catalog_crud_card(
            page=page,
            title_text="Quản lý Danh mục Bệnh lý & Phác đồ Điều trị Mặc định",
            on_changed=refresh_catalog_header,
        )
        return [
            catalog_header_host,
            crud_card,
        ]

    destinations = [
        ("Hàng đợi thẩm định", ft.Icons.PENDING_ACTIONS_OUTLINED, ft.Icons.PENDING_ACTIONS_ROUNDED),
        ("Thẩm định & Gán nhãn", ft.Icons.FACT_CHECK_OUTLINED, ft.Icons.FACT_CHECK_ROUNDED),
        ("Đóng góp Dataset", ft.Icons.DATASET_OUTLINED, ft.Icons.DATASET_ROUNDED),
        ("Danh mục Bệnh lý & Phác đồ", ft.Icons.MEDICAL_INFORMATION_OUTLINED, ft.Icons.MEDICAL_INFORMATION_ROUNDED),
        ("Test chuyên sâu (Batch)", ft.Icons.SCIENCE_OUTLINED, ft.Icons.SCIENCE_ROUNDED),
    ]

    return build_role_shell(
        page=page,
        user=user,
        title="Không gian Chuyên Gia Thú Y",
        destinations=destinations,
        tab_builders=[build_queue_tab, build_relabel_tab, build_curation_tab, build_catalog_tab, build_batch_tab],
        external_nav_ref=nav_ref,
    )
