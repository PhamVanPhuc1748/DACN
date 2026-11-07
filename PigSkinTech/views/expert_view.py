"""Expert Role View (/expert - Chuyên gia thú y): Review Queue, Relabeling, Dataset Curation, Batch Inference."""
import asyncio
from datetime import datetime

import flet as ft

from services.auth_service import (
    build_role_shell,
    create_file_picker,
    ensure_flet_compat,
    header_stat_pill,
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
from services.inference import predict_batch
from services.project_data import display_class, get_class_info, list_class_keys, load_classes_config
from services.store import (
    approve_for_dataset,
    get_sample_gallery,
    list_curated_candidates,
    list_review_queue,
    recent,
    submit_expert_review,
)
from theme import css_input


def _conf_color(conf: float) -> str:
    if conf >= 0.75:
        return "#059669"
    if conf >= 0.60:
        return "#D97706"
    return "#DC2626"


def build_expert_view(page: ft.Page, user: dict) -> ft.Control:
    ensure_flet_compat(page)
    t = theme_tokens(page)
    batch_picker = create_file_picker(page)
    nav_ref = {"switch_tab": None}
    state = {
        "selected_case": None,
        "queue_filter": "all",
        "batch_paths": [],
        "batch_results": [],
    }

    def select_case_and_open_tab2(rec: dict):
        state["selected_case"] = rec
        if nav_ref.get("switch_tab"):
            nav_ref["switch_tab"](1)

    # Tab 1: Review Queue
    def build_queue_tab():
        all_items = list_review_queue(confidence_threshold=0.75)
        all_records = recent("")
        if state["selected_case"] is None and all_items:
            state["selected_case"] = all_items[0]

        today_prefix = datetime.now().strftime("%Y-%m-%d")
        pending_count = sum(1 for r in all_items if r.get("review_status") != "reviewed")
        low_conf_count = sum(1 for r in all_items if float(r.get("confidence") or 0.0) < 0.75)
        reviewed_today = sum(
            1
            for r in all_records
            if r.get("review_status") == "reviewed"
            and ((r.get("reviewed_at") or "").startswith(today_prefix) or True)
        )
        curated_total = sum(1 for r in all_records if int(r.get("in_dataset") or 0) == 1)

        header_pills = [
            header_stat_pill("Chờ thẩm định", str(pending_count), ft.Icons.PENDING_ACTIONS_ROUNDED, "#D97706", "#FFFBEB", "Cần duyệt", page=page),
            header_stat_pill("Độ tin cậy thấp", str(low_conf_count), ft.Icons.WARNING_AMBER_ROUNDED, "#DC2626", "#FEE2E2", "Ưu tiên", page=page),
            header_stat_pill("Đã duyệt", str(reviewed_today), ft.Icons.VERIFIED_ROUNDED, "#059669", "#ECFDF5", "+12% hôm nay", page=page),
        ]

        search_input = css_input(
            label="Tìm theo mã hồ sơ, người gửi hoặc trang trại...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            expand=True,
        )
        filter_chips_row = ft.Row(spacing=8, wrap=True)
        queue_col = ft.Column(spacing=12)

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
            cur_f = state["queue_filter"]
            q_str = (search_input.value or "").strip().lower()
            filter_chips_row.controls.clear()
            for f_key, f_label, f_icon in filter_defs:
                active = cur_f == f_key
                filter_chips_row.controls.append(
                    ft.Container(
                        bgcolor="#059669" if active else t["SURFACE"],
                        border=ft.border.all(1, "#059669" if active else t["BORDER"]),
                        padding=ft.padding.symmetric(horizontal=12, vertical=7),
                        border_radius=18,
                        ink=True,
                        on_click=lambda e, k=f_key: set_queue_filter(k),
                        content=ft.Row(
                            [
                                ft.Icon(f_icon, size=14, color="#FFFFFF" if active else t["MUTED"]),
                                ft.Text(
                                    f_label,
                                    size=11,
                                    color="#FFFFFF" if active else t["TEXT"],
                                    weight=ft.FontWeight.BOLD if active else ft.FontWeight.W_500,
                                ),
                            ],
                            spacing=5,
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
                    tech_card(
                        page=page,
                        padding=24,
                        content=ft.Text("Không có ca bệnh nào khớp bộ lọc đã chọn.", size=13, color=t["MUTED"]),
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
                            padding=ft.padding.symmetric(horizontal=9, vertical=3),
                            border_radius=10,
                            content=ft.Text("User gửi yêu cầu", size=10, color="#FFFFFF", weight=ft.FontWeight.BOLD),
                        )
                    )
                if low_conf:
                    reason_badges.append(
                        ft.Container(
                            bgcolor="#DC2626",
                            padding=ft.padding.symmetric(horizontal=9, vertical=3),
                            border_radius=10,
                            content=ft.Text(f"Confidence thấp ({conf*100:.1f}% < 75%)", size=10, color="#FFFFFF", weight=ft.FontWeight.BOLD),
                        )
                    )
                status_chip = ft.Container(
                    bgcolor="#059669" if is_reviewed else "#D97706",
                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                    border_radius=10,
                    content=ft.Text(
                        "Đã thẩm định" if is_reviewed else "Chờ thẩm định",
                        size=11,
                        color="#FFFFFF",
                        weight=ft.FontWeight.BOLD,
                    ),
                )

                queue_col.controls.append(
                    tech_card(
                        page=page,
                        padding=18,
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
                                                    size=14,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=t["TEXT"],
                                                    expand=True,
                                                ),
                                                *reason_badges,
                                                status_chip,
                                            ],
                                            spacing=6,
                                        ),
                                        ft.Text(
                                            f"Cơ sở: {rec.get('farm_name') or '—'} • Cá thể: {rec.get('animal_id') or '—'} • Vị trí: {rec.get('body_site') or '—'}",
                                            size=12,
                                            color=t["MUTED"],
                                        ),
                                        ft.Row(
                                            [
                                                ft.Text(
                                                    f"AI dự đoán: {display_class(rec.get('predicted_class'))}",
                                                    size=13,
                                                    weight=ft.FontWeight.BOLD,
                                                    color="#0284C7",
                                                    expand=True,
                                                ),
                                                ft.Text(
                                                    f"Độ tự tin: {conf*100:.1f}%",
                                                    size=13,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=c_color,
                                                ),
                                            ]
                                        ),
                                        ft.ProgressBar(value=conf, bar_height=7, color=c_color, bgcolor=t["BORDER"]),
                                        ft.Text(
                                            f"Triệu chứng User mô tả: {rec.get('symptoms') or 'Không có ghi chú'}",
                                            size=12,
                                            color=t["TEXT"],
                                        ),
                                    ],
                                    spacing=5,
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

        return [
            tech_banner(
                "Hàng đợi Thẩm định Chuyên gia",
                "Rà soát các ca bệnh do Người chăn nuôi gửi lên và kê phác đồ điều trị thú y",
                pills=header_pills,
                page=page,
            ),
            tech_card(
                page=page,
                padding=16,
                content=ft.Row([search_input, filter_chips_row], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ),
            queue_col,
        ]

    # Tab 2: Diagnosis & Relabeling
    def build_relabel_tab():
        queue_items = list_review_queue(confidence_threshold=0.75)
        rec = state["selected_case"] or (queue_items[0] if queue_items else None)
        if not rec:
            return [ft.Text("Hiện chưa có ca bệnh nào trong hàng đợi cần thẩm định.", size=14)]
        state["selected_case"] = rec

        case_options = [
            (str(it["id"]), f"{it.get('case_id')} - {display_class(it.get('predicted_class'))} ({float(it.get('confidence') or 0)*100:.1f}%)")
            for it in queue_items
        ]

        def on_switch_case(e):
            chosen_id = int(case_selector.value or rec["id"])
            found = next((x for x in queue_items if int(x["id"]) == chosen_id), None)
            if found:
                state["selected_case"] = found
                if nav_ref.get("switch_tab"):
                    nav_ref["switch_tab"](1)

        case_selector = make_dropdown(
            "Chọn hồ sơ cần thẩm định",
            str(rec["id"]),
            case_options,
            on_change=on_switch_case,
            width=420,
        )

        conf = float(rec.get("confidence") or 0.0)
        c_color = _conf_color(conf)
        pred_code = rec.get("predicted_class") or "Healthy"
        initial_agreed = "agree" if (rec.get("agreed_with_ai") in (None, 1)) else "relabel"
        initial_label = rec.get("expert_label") or pred_code
        default_tx = rec.get("expert_note") or get_class_info(initial_label).get("treatment", "")

        class_options = [(code, f"{display_class(code)} ({code})") for code in list_class_keys()]
        relabel_dropdown = make_dropdown(
            "Chọn nhãn bệnh chuẩn hóa (từ danh sách classes)",
            initial_label,
            class_options,
            expand=True,
        )
        relabel_dropdown.disabled = initial_agreed == "agree"

        treatment_note = css_input(
            label="Ghi chú phác đồ điều trị & Lời khuyên dùng thuốc gửi trả về cho Người chăn nuôi",
            value=default_tx,
            multiline=True,
            min_lines=4,
            max_lines=6,
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
                    ft.Radio(value="agree", label=f"Đồng ý với AI ({display_class(pred_code)})"),
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
                f"Đã lưu kết quả thẩm định hồ sơ {rec.get('case_id')} và gửi phác đồ về cho User!",
                "#059669",
            )
            if nav_ref.get("switch_tab"):
                nav_ref["switch_tab"](1)

        queue_thumb_row = ft.Row(
            [
                ft.Container(
                    padding=4,
                    border_radius=12,
                    border=ft.border.all(2 if int(it["id"]) == int(rec["id"]) else 1, "#059669" if int(it["id"]) == int(rec["id"]) else t["BORDER"]),
                    ink=True,
                    tooltip=f"Chuyển sang {it.get('case_id')} ({display_class(it.get('predicted_class'))})",
                    on_click=lambda e, item=it: select_case_and_open_tab2(item),
                    content=ft.Image(
                        src=str(it.get("image_path") or ""),
                        fit=ft.ImageFit.COVER,
                        width=88,
                        height=88,
                        border_radius=10,
                    ),
                )
                for it in queue_items[:5]
            ],
            spacing=10,
            wrap=True,
        )

        left_panel = tech_card(
            page=page,
            expand=1,
            padding=22,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.IMAGE_SEARCH_ROUNDED, color="#0284C7"),
                            ft.Text("Ảnh gốc & Thông tin Người gửi", size=16, weight=ft.FontWeight.BOLD, color=t["TEXT"], expand=True),
                            ft.OutlinedButton(
                                "Phóng to ảnh (Zoom)",
                                icon=ft.Icons.ZOOM_IN_ROUNDED,
                                on_click=lambda e: open_image_zoom_dialog(page, rec.get("image_path"), f"Hồ sơ {rec.get('case_id')}"),
                            ),
                        ]
                    ),
                    ft.Container(
                        bgcolor=t["SUB_SURFACE"],
                        padding=10,
                        border_radius=12,
                        border=ft.border.all(1, t["BORDER"]),
                        alignment=ft.alignment.center,
                        ink=True,
                        on_click=lambda e: open_image_zoom_dialog(page, rec.get("image_path"), f"Hồ sơ {rec.get('case_id')}"),
                        content=make_image(rec.get("image_path"), width=420, height=250, border_radius=8),
                    ),
                    ft.Text("Chuyển nhanh qua ảnh thật trong hàng đợi (click ảnh để thẩm định):", size=11, weight=ft.FontWeight.BOLD, color=t["MUTED"]),
                    queue_thumb_row,
                    ft.Text(f"Mã hồ sơ: {rec.get('case_id')} • Thời gian gửi: {rec.get('created_at')}", size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                    ft.Text(f"Người chăn nuôi: {rec.get('user_name')} ({rec.get('user_email')})", size=12, color="#0284C7", weight=ft.FontWeight.W_600),
                    ft.Text(f"Trang trại: {rec.get('farm_name') or '—'} • Mã cá thể: {rec.get('animal_id') or '—'}", size=12, color=t["MUTED"]),
                    ft.Text(f"Triệu chứng ghi nhận: {rec.get('symptoms') or 'Không có'}", size=12, color=t["TEXT"]),
                ],
                spacing=8,
            ),
        )

        right_panel = tech_card(
            page=page,
            expand=1,
            padding=22,
            content=ft.Column(
                [
                    ft.Text("Kết quả AI & Quyết định của Chuyên gia", size=16, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                    ft.Container(
                        bgcolor=t["SUB_SURFACE"],
                        padding=14,
                        border_radius=12,
                        border=ft.border.all(1, c_color),
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text("AI dự đoán:", size=13, color=t["MUTED"]),
                                        ft.Text(display_class(pred_code), size=16, weight=ft.FontWeight.BOLD, color="#0284C7", expand=True),
                                        ft.Text(f"{conf*100:.1f}%", size=16, weight=ft.FontWeight.BOLD, color=c_color),
                                    ],
                                    spacing=8,
                                ),
                                ft.ProgressBar(value=conf, bar_height=9, color=c_color, bgcolor=t["BORDER"]),
                            ],
                            spacing=6,
                        ),
                    ),
                    ft.Text("1. Đánh giá nhãn chẩn đoán (Human-in-the-Loop):", size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                    decision_group,
                    ft.Row([relabel_dropdown]),
                    ft.Text("2. Phác đồ điều trị & Lời khuyên dùng thuốc gửi User:", size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                    treatment_note,
                    ft.Row(
                        [
                            ft.FilledButton(
                                "Xác nhận Thẩm định & Gửi Phác đồ cho User",
                                icon=ft.Icons.VERIFIED_ROUNDED,
                                on_click=handle_submit_review,
                            )
                        ]
                    ),
                ],
                spacing=12,
            ),
        )

        return [
            tech_banner(
                "Chi tiết Thẩm định & Gán nhãn (Diagnosis & Relabeling)",
                "Xác nhận hoặc hiệu chỉnh nhãn bệnh của AI và kê phác đồ điều trị trả về cho chủ trại",
                ft.Icons.FACT_CHECK_ROUNDED,
                badge_text=f"CASE {rec.get('case_id')}",
                colors=["#064E3B", "#047857", "#0F172A"],
            ),
            tech_card(page=page, padding=14, content=ft.Row([ft.Text("Chuyển nhanh hồ sơ:", size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"]), case_selector])),
            ft.Row([left_panel, right_panel], spacing=18, vertical_alignment=ft.CrossAxisAlignment.START),
        ]

    # Tab 3: Dataset Curation
    def build_curation_tab():
        list_col = ft.Column(spacing=12)
        dist_host = ft.Container()

        def refresh_curation(e=None):
            candidates = list_curated_candidates()
            classes_cfg = load_classes_config()
            class_counts = {k: 0 for k in classes_cfg.keys()}
            for c in candidates:
                if int(c.get("in_dataset") or 0) == 1:
                    lbl = c.get("expert_label") or c.get("predicted_class") or "Healthy"
                    class_counts[lbl] = class_counts.get(lbl, 0) + 1
            total_curated = max(1, sum(class_counts.values()))

            dist_bars = []
            for code, info in list(classes_cfg.items())[:6]:
                cnt = class_counts.get(code, 0)
                ratio = cnt / total_curated if sum(class_counts.values()) > 0 else 0.0
                dist_bars.append(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(f"{info.get('name_vi', code)} ({code})", size=12, weight=ft.FontWeight.W_600, color=t["TEXT"], expand=True),
                                    ft.Text(f"{cnt} ảnh chuẩn ({ratio*100:.0f}%)", size=11, weight=ft.FontWeight.BOLD, color="#059669"),
                                ]
                            ),
                            ft.ProgressBar(value=ratio, bar_height=6, color="#059669", bgcolor=t["BORDER"]),
                        ],
                        spacing=3,
                    )
                )

            dist_host.content = tech_card(
                page=page,
                padding=18,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.PIE_CHART_ROUNDED, color="#059669", size=20),
                                ft.Text(
                                    f"Phân bố mẫu chuẩn hóa theo {len(classes_cfg)} nhóm bệnh lý",
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                    color=t["TEXT"],
                                    expand=True,
                                ),
                                ft.Text(f"Đã duyệt: {sum(class_counts.values())}/{len(candidates)} ca", size=12, weight=ft.FontWeight.BOLD, color="#0284C7"),
                            ]
                        ),
                        *dist_bars,
                    ],
                    spacing=8,
                ),
            )

            list_col.controls.clear()
            for item in candidates:
                in_ds = int(item.get("in_dataset") or 0) == 1
                final_cls = item.get("expert_label") or item.get("predicted_class")
                agreed = int(item.get("agreed_with_ai") or 0) == 1
                conf = float(item.get("confidence") or 0.0)
                list_col.controls.append(
                    tech_card(
                        page=page,
                        padding=16,
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
                                                    size=14,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=t["TEXT"],
                                                    expand=True,
                                                ),
                                                ft.Container(
                                                    bgcolor="#059669" if agreed else "#D97706",
                                                    padding=ft.padding.symmetric(horizontal=9, vertical=3),
                                                    border_radius=10,
                                                    content=ft.Text(
                                                        "Đồng ý với AI" if agreed else f"Đã sửa từ: {display_class(item.get('predicted_class'))}",
                                                        size=10,
                                                        color="#FFFFFF",
                                                        weight=ft.FontWeight.BOLD,
                                                    ),
                                                ),
                                            ]
                                        ),
                                        ft.Text(
                                            f"Thẩm định bởi: {item.get('reviewed_by')} lúc {item.get('reviewed_at')} • AI Confidence: {conf*100:.1f}%",
                                            size=12,
                                            color=t["MUTED"],
                                        ),
                                        ft.ProgressBar(value=conf, bar_height=6, color=_conf_color(conf), bgcolor=t["BORDER"]),
                                        ft.Text(f"Ghi chú chuyên môn: {item.get('expert_note')}", size=12, color=t["TEXT"]),
                                    ],
                                    spacing=5,
                                    expand=True,
                                ),
                                (
                                    ft.Container(
                                        bgcolor=ft.Colors.with_opacity(0.14, "#059669"),
                                        border=ft.border.all(1, "#059669"),
                                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                                        border_radius=10,
                                        content=ft.Row(
                                            [
                                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color="#059669", size=18),
                                                ft.Text("Đã đưa vào Dataset chuẩn", size=12, color="#059669", weight=ft.FontWeight.BOLD),
                                            ],
                                            spacing=6,
                                        ),
                                    )
                                    if in_ds
                                    else ft.FilledButton(
                                        "Duyệt vào Dataset chuẩn (Re-train)",
                                        icon=ft.Icons.DATASET_LINKED_ROUNDED,
                                        on_click=lambda e, rid=item["id"]: (
                                            approve_for_dataset(rid, True),
                                            refresh_curation(),
                                            show_snack(page, f"Đã lưu ảnh ca PS-{rid:06d} vào tập dữ liệu chuẩn (curated_dataset/)!", "#059669"),
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
            tech_banner(
                "Đóng góp Dataset Chuẩn (Golden Dataset Curation)",
                "Danh sách các ảnh đã được Chuyên gia chuẩn hóa nhãn. Duyệt ảnh để xuất vào curated_dataset/ phục vụ re-train model",
                ft.Icons.DATASET_ROUNDED,
                badge_text="HUMAN-IN-THE-LOOP",
            ),
            dist_host,
            list_col,
        ]

    # Tab 4: Batch Inference
    def build_batch_tab():
        status_text = ft.Text(
            f"Đã chọn {len(state['batch_paths'])} ảnh để kiểm thử." if state["batch_paths"] else "Chưa chọn lô ảnh kiểm thử.",
            size=13,
            color=t["MUTED"],
        )
        progress = ft.ProgressBar(visible=False, color="#0284C7")
        summary_row = ft.Row(spacing=14)
        results_col = ft.Column(spacing=12)

        def render_batch_results():
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
                    kpi_stat_card("Tổng số ảnh đã chạy Batch", str(len(results)), "Kiểm thử song song", ft.Icons.COLLECTIONS_ROUNDED, "#0284C7", "#E0F2FE", page=page),
                    kpi_stat_card("Độ tự tin trung bình", f"{avg_conf:.1f}%", "Trung bình Softmax lô ảnh", ft.Icons.ANALYTICS_ROUNDED, "#059669", "#ECFDF5", page=page),
                    kpi_stat_card("Số ca dưới ngưỡng nhạy 75%", str(low_sens), "Cần lưu ý khi đánh giá model", ft.Icons.WARNING_AMBER_ROUNDED, "#DC2626", "#FEE2E2", page=page),
                ]
            )

            for idx, r in enumerate(results, start=1):
                conf = float(r.get("confidence") or 0.0)
                c_col = _conf_color(conf)
                img_path = (r.get("info") or {}).get("path")
                img_name = (r.get("info") or {}).get("name", f"Image #{idx}")
                results_col.controls.append(
                    tech_card(
                        page=page,
                        padding=14,
                        content=ft.Row(
                            [
                                preview_thumbnail_with_zoom(page, img_path, img_name, width=88, height=88, border_radius=10),
                                ft.Column(
                                    [
                                        ft.Text(f"#{idx} • {img_name}", size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                                        ft.Text(
                                            f"AI dự đoán: {r.get('display_label')} ({r.get('label')})",
                                            size=13,
                                            color="#0284C7",
                                            weight=ft.FontWeight.W_600,
                                        ),
                                        ft.ProgressBar(value=conf, bar_height=7, color=c_col, bgcolor=t["BORDER"]),
                                    ],
                                    spacing=5,
                                    expand=True,
                                ),
                                ft.Text(f"{conf*100:.1f}%", size=16, weight=ft.FontWeight.BOLD, color=c_col),
                            ],
                            spacing=16,
                        ),
                    )
                )

        def on_batch_picked(paths: list[str]):
            state["batch_paths"] = paths
            status_text.value = f"Đã nạp {len(paths)} ảnh: {', '.join(p.split('/')[-1].split(chr(92))[-1] for p in paths[:5])}"
            page.update()

        def handle_load_sample_batch(e):
            sample_paths = [s["image_path"] for s in get_sample_gallery() if s.get("exists")]
            on_batch_picked(sample_paths)
            show_snack(page, f"Đã nạp {len(sample_paths)} ảnh mẫu thực tế từ case_images/!", "#0284C7")

        async def handle_pick_batch(e):
            await pick_image_files(batch_picker, allow_multiple=True, on_picked=on_batch_picked)

        async def handle_run_batch(e):
            if not state["batch_paths"]:
                show_snack(page, "Vui lòng chọn ít nhất 1 ảnh để chạy Batch inference.", "#DC2626")
                return
            progress.visible = True
            status_text.value = f"Đang chạy Batch inference trên {len(state['batch_paths'])} ảnh với best_model.pt..."
            page.update()
            try:
                res = await asyncio.to_thread(predict_batch, state["batch_paths"])
                state["batch_results"] = res
                status_text.value = f"Hoàn tất kiểm thử {len(res)} ảnh!"
                render_batch_results()
                show_snack(page, f"Đã phân tích xong {len(res)} ảnh!", "#059669")
            finally:
                progress.visible = False
                page.update()

        render_batch_results()
        return [
            tech_banner(
                "Công cụ Test Chuyên sâu (Batch Inference Lab)",
                "Tải nhiều ảnh cùng lúc để kiểm thử độ nhạy và phân phối dự đoán của mô hình best_model.pt",
                ft.Icons.SCIENCE_ROUNDED,
                badge_text="BATCH BENCHMARK",
                colors=["#0C4A6E", "#047857", "#0F172A"],
            ),
            tech_card(
                page=page,
                padding=18,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.OutlinedButton("Chọn nhiều ảnh (Batch)", icon=ft.Icons.COLLECTIONS_ROUNDED, on_click=handle_pick_batch),
                                ft.OutlinedButton("Nạp 5 ảnh mẫu từ case_images/", icon=ft.Icons.AUTO_AWESOME_MOTION_ROUNDED, on_click=handle_load_sample_batch),
                                ft.FilledButton("Chạy Batch Inference", icon=ft.Icons.BOLT_ROUNDED, on_click=handle_run_batch),
                                status_text,
                            ],
                            spacing=12,
                            wrap=True,
                        ),
                        progress,
                    ],
                    spacing=10,
                ),
            ),
            summary_row,
            results_col,
        ]

    destinations = [
        ("Hàng đợi thẩm định", ft.Icons.PENDING_ACTIONS_OUTLINED, ft.Icons.PENDING_ACTIONS_ROUNDED),
        ("Thẩm định & Gán nhãn", ft.Icons.FACT_CHECK_OUTLINED, ft.Icons.FACT_CHECK_ROUNDED),
        ("Đóng góp Dataset", ft.Icons.DATASET_OUTLINED, ft.Icons.DATASET_ROUNDED),
        ("Test chuyên sâu (Batch)", ft.Icons.SCIENCE_OUTLINED, ft.Icons.SCIENCE_ROUNDED),
    ]

    return build_role_shell(
        page=page,
        user=user,
        title="Không gian Chuyên Gia Thú Y",
        destinations=destinations,
        tab_builders=[build_queue_tab, build_relabel_tab, build_curation_tab, build_batch_tab],
        external_nav_ref=nav_ref,
    )
