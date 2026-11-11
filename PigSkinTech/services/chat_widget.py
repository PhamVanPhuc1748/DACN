"""Veterinary AI Chatbot Widget & Sidebar Tab for PigSkinTech (Light & Dark Mode synchronized via theme.py)."""
from __future__ import annotations

import asyncio
from typing import Callable

import flet as ft

from services.chatbot_service import (
    MANDATORY_DISCLAIMER,
    NON_CLINICAL_PIG_REMINDER,
    OFF_TOPIC_REFUSAL,
    ask_vet_ai,
    ensure_disclaimer,
    format_diagnosis_context,
    is_in_domain,
    is_non_clinical_pig_question,
    refresh_all_chat_views,
    register_chat_refresher,
)
from services.project_data import display_class
from services.store import clear_chat_messages, list_chat_messages, save_chat_message
from theme import (
    PRIMARY,
    PRIMARY_DARK,
    css_card,
    css_input,
    css_shadow,
    get_theme_palette,
    make_smooth_animation,
)

__all__ = [
    "MANDATORY_DISCLAIMER",
    "NON_CLINICAL_PIG_REMINDER",
    "OFF_TOPIC_REFUSAL",
    "ask_vet_ai",
    "ensure_disclaimer",
    "format_diagnosis_context",
    "is_in_domain",
    "is_non_clinical_pig_question",
    "refresh_all_chat_views",
    "build_chat_panel",
    "build_chat_overlay",
]


def build_chat_panel(
    page: ft.Page,
    user: dict,
    get_diagnosis_context: Callable[[], dict | None] | None = None,
    compact: bool = False,
) -> tuple[ft.Control, Callable[[str | None], None]]:
    """
    Khung Chatbox Tư vấn Thú y AI theo chuẩn theme.py (đồng bộ cả Light Mode & Dark Mode).
    - Hiển thị định dạng Markdown (`ft.Markdown`) thay vì in dấu `**` thô.
    - Đồng bộ tức thì 100% lịch sử tin nhắn giữa Tab chính và Popup góc phải qua `refresh_all_chat_views(page)`.
    """
    pal = get_theme_palette(page)
    user_email = (user or {}).get("email", "nongdan.pigskin@gmail.com")
    user_id = (user or {}).get("user_id") or (user or {}).get("id")

    messages_list = ft.Column(
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        auto_scroll=True,
        expand=True,
    )
    context_banner_box = ft.Container()
    status_label = ft.Text(
        "Gemini AI • Đồng bộ trực tiếp với bảng ChatMessages (SQL Database)",
        size=11.5,
        color=pal["TEXT_MUTED"],
    )

    chat_input = css_input(
        hint_text="Mô tả triệu chứng trên da heo, hỏi phác đồ chăm sóc hoặc giải thích kết quả AI...",
        expand=True,
        page=page,
    )

    def _get_active_scan() -> dict | None:
        if get_diagnosis_context is not None:
            ctx = get_diagnosis_context()
            if ctx:
                return ctx
        if isinstance(getattr(page, "data", None), dict):
            return page.data.get("active_scan_result")
        return None

    def _render_message_bubble(role: str, content: str, timestamp: str = "", model_name: str = "") -> ft.Control:
        cur_pal = get_theme_palette(page)
        is_user = role == "user"
        final_text = content if is_user else ensure_disclaimer(content)
        bubble_bg = PRIMARY_DARK if is_user else cur_pal["BG_SUB"]
        text_col = "#FFFFFF" if is_user else cur_pal["TEXT_PRIMARY"]
        meta_col = "#A7F3D0" if is_user else cur_pal["TEXT_MUTED"]
        who = "Bạn" if is_user else f"BS. Thú y AI ({model_name or 'PigSkinTech'})"
        if timestamp:
            who = f"{who} • {timestamp}"

        body_ctrl: ft.Control
        if is_user:
            body_ctrl = ft.Text(final_text, size=13.5, color=text_col, selectable=True)
        else:
            md_style = ft.MarkdownStyleSheet(
                p_text_style=ft.TextStyle(size=13.5, color=text_col),
                strong_text_style=ft.TextStyle(size=13.5, weight=ft.FontWeight.BOLD, color=text_col),
                list_bullet_text_style=ft.TextStyle(size=13.5, color=text_col),
            )
            body_ctrl = ft.Markdown(
                value=final_text,
                selectable=True,
                soft_line_break=True,
                md_style_sheet=md_style,
            )

        return ft.Row(
            alignment=ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START,
            controls=[
                ft.Container(
                    width=345 if compact else 680,
                    bgcolor=bubble_bg,
                    border=None if is_user else ft.border.all(1, cur_pal["BORDER_LIGHT"]),
                    border_radius=14,
                    padding=ft.padding.symmetric(horizontal=14, vertical=10),
                    content=ft.Column(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Text(who, size=11, weight=ft.FontWeight.W_700, color=meta_col),
                            body_ctrl,
                        ],
                    ),
                )
            ],
        )

    def refresh_context_banner() -> None:
        cur_pal = get_theme_palette(page)
        scan = _get_active_scan()
        if scan and scan.get("label"):
            lbl = scan.get("display_label") or display_class(scan.get("label"))
            conf = f"{float(scan.get('confidence') or 0.0) * 100:.1f}%"
            arch = scan.get("architecture") or scan.get("model_label") or "MobileNetV2"
            ms = scan.get("inference_ms", "-")
            context_banner_box.content = ft.Container(
                bgcolor=cur_pal["SOFT_EMERALD"],
                border=ft.border.all(1, cur_pal["PROTOCOL_BORDER"]),
                border_radius=10,
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                content=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.BIOTECH_ROUNDED, size=18, color=PRIMARY),
                        ft.Text(
                            f"Đang liên kết kết quả quét: {lbl} ({conf} • {arch} • {ms}ms)",
                            size=12.5,
                            weight=ft.FontWeight.W_700,
                            color=cur_pal["PROTOCOL_HEAD"],
                            expand=True,
                        ),
                    ],
                ),
            )
        else:
            context_banner_box.content = ft.Container(
                bgcolor=cur_pal["BG_SUB"],
                border=ft.border.all(1, cur_pal["BORDER_LIGHT"]),
                border_radius=10,
                padding=ft.padding.symmetric(horizontal=12, vertical=7),
                content=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.VERIFIED_USER_OUTLINED, size=16, color=PRIMARY),
                        ft.Text(
                            "Chuyên biệt cho PigSkinTech: Hỗ trợ hỏi đáp bệnh ngoài da ở heo, giải thích mô hình Deep Learning & cách dùng ứng dụng.",
                            size=12,
                            color=cur_pal["TEXT_SECONDARY"],
                            expand=True,
                        ),
                    ],
                ),
            )

    def reload_history() -> None:
        refresh_context_banner()
        messages_list.controls.clear()
        rows = list_chat_messages(user_email=user_email, limit=50)
        if not rows:
            welcome_msg = ensure_disclaimer(
                "👋 **Xin chào! Tôi là Chatbox chuyên biệt của PigSkinTech.**\n\n"
                "Bạn có thể hỏi trực tiếp về:\n"
                "• **Các bệnh ngoài da ở heo** (triệu chứng nổi mẩn đỏ, mụn nước, đóng vảy, ghẻ, nấm, cách ly, vệ sinh chuồng trại, phác đồ chăm sóc bước đầu).\n"
                "• **Giải thích kết quả chẩn đoán** từ mô hình Deep Learning (`MobileNetV2`, `EfficientNet-B0`).\n"
                "• **Hướng dẫn sử dụng** ứng dụng PigSkinTech."
            )
            messages_list.controls.append(
                _render_message_bubble(
                    "assistant",
                    welcome_msg,
                    model_name="PigSkinTech AI",
                )
            )
        else:
            for r in rows:
                messages_list.controls.append(
                    _render_message_bubble(
                        r["role"],
                        r["content"],
                        timestamp=r.get("timestamp", ""),
                        model_name=r.get("model_name", ""),
                    )
                )

        async def scroll_after_render() -> None:
            # Wait for the refreshed bubbles to participate in layout before
            # moving the inner conversation viewport to its newest message.
            await asyncio.sleep(0.06)
            try:
                if getattr(messages_list, "page", None) is not None:
                    messages_list.scroll_to(delta=1_000_000, duration=180)
            except (AttributeError, RuntimeError):
                pass

        if hasattr(page, "run_task"):
            page.run_task(scroll_after_render)

    register_chat_refresher(page, reload_history)

    async def _send_async(prefill_text: str | None = None) -> None:
        question = (prefill_text if prefill_text is not None else (chat_input.value or "")).strip()
        if not question:
            return
        if prefill_text is None:
            chat_input.value = ""

        scan = _get_active_scan()
        case_code = str(scan.get("label") or "") if scan else ""

        save_chat_message(
            user_email=user_email,
            role="user",
            content=question,
            user_id=user_id,
            case_id=case_code,
            model_name="user",
        )
        status_label.value = "Đang phân tích triệu chứng & phác đồ thú y..."
        refresh_all_chat_views(page)

        history_rows = list_chat_messages(user_email=user_email, limit=12)
        raw_reply, used_model = await asyncio.to_thread(ask_vet_ai, question, history_rows, scan)
        final_reply = ensure_disclaimer(raw_reply)

        save_chat_message(
            user_email=user_email,
            role="assistant",
            content=final_reply,
            user_id=user_id,
            case_id=case_code,
            model_name=used_model,
        )
        status_label.value = f"Đã đồng bộ bảng ChatMessages (SQL) • {used_model}"
        refresh_all_chat_views(page)

    def send_message(prefill: str | None = None) -> None:
        page.run_task(_send_async, prefill)

    chat_input.on_submit = lambda e: send_message(None)

    def clear_history_click(e=None) -> None:
        clear_chat_messages(user_email)
        refresh_all_chat_views(page)

    quick_questions = [
        ("💊 Chăm sóc & Liều thuốc", "Cho tôi phác đồ chăm sóc bước đầu và liều lượng thuốc tham khảo cho kết quả bệnh mô hình vừa quét?"),
        ("🚧 Cách ly & Vệ sinh chuồng", "Cần cách ly heo bệnh và vệ sinh sát trùng chuồng trại như thế nào cho kết quả vừa quét?"),
        ("🧠 Giải thích mô hình AI", "Giải thích kết quả chẩn đoán từ mô hình Deep Learning (MobileNetV2, EfficientNet-B0) và độ tự tin Softmax?"),
        ("📱 Hướng dẫn dùng ứng dụng", "Hướng dẫn sử dụng ứng dụng PigSkinTech để quét ảnh, gửi thẩm định chuyên gia và in phiếu khám?"),
    ]

    chips_row = ft.Row(
        spacing=8,
        wrap=True,
        controls=[
            ft.Container(
                bgcolor=pal["BG_SUB"],
                border=ft.border.all(1, pal["BORDER_LIGHT"]),
                border_radius=20,
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                ink=True,
                on_click=lambda e, q=q_txt: send_message(q),
                content=ft.Text(lbl, size=12, weight=ft.FontWeight.W_600, color=pal["TEXT_PRIMARY"]),
            )
            for lbl, q_txt in quick_questions
        ],
    )

    reload_history()

    card = css_card(
        page=page,
        padding=16 if compact else 24,
        border_radius=16,
        content=ft.Column(
            spacing=10,
            expand=True,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.Container(
                                    width=40,
                                    height=40,
                                    border_radius=12,
                                    bgcolor=PRIMARY_DARK,
                                    alignment=ft.alignment.center,
                                    content=ft.Icon(ft.Icons.SMART_TOY_ROUNDED, color="#FFFFFF", size=22),
                                ),
                                ft.Column(
                                    spacing=2,
                                    tight=True,
                                    controls=[
                                        ft.Text(
                                            "Trợ lý AI Thú y (Chatbot)",
                                            size=16 if compact else 18,
                                            weight=ft.FontWeight.W_800,
                                            color=pal["TEXT_PRIMARY"],
                                        ),
                                        status_label,
                                    ],
                                ),
                            ],
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_SWEEP_ROUNDED,
                            icon_color=pal["TEXT_MUTED"],
                            tooltip="Xóa lịch sử chat trong SQL Database",
                            on_click=clear_history_click,
                        ),
                    ],
                ),
                context_banner_box,
                chips_row,
                ft.Container(
                    height=210 if compact else 410,
                    bgcolor=pal["BG_MAIN"],
                    border=ft.border.all(1, pal["BORDER_LIGHT"]),
                    border_radius=12,
                    padding=12,
                    content=messages_list,
                ),
                ft.Row(
                    spacing=8,
                    controls=[
                        chat_input,
                        ft.FilledButton(
                            "Gửi",
                            icon=ft.Icons.SEND_ROUNDED,
                            height=48,
                            style=ft.ButtonStyle(
                                bgcolor=PRIMARY_DARK,
                                color="#FFFFFF",
                                shape=ft.RoundedRectangleBorder(radius=10),
                            ),
                            on_click=lambda e: send_message(None),
                        ),
                    ],
                ),
            ],
        ),
    )
    return card, send_message


def build_chat_overlay(
    page: ft.Page,
    user: dict,
    get_diagnosis_context: Callable[[], dict | None] | None = None,
) -> ft.Control:
    """
    Circular Floating Icon Button & Popup Chat Drawer nổi góc dưới bên phải màn hình.
    Tự động ẩn hoàn toàn khi người dùng đang mở tab 'Trợ lý AI Thú y (Chatbot)' trên Sidebar.
    """
    pal = get_theme_palette(page)
    panel_ctrl, send_fn = build_chat_panel(
        page=page,
        user=user,
        get_diagnosis_context=get_diagnosis_context,
        compact=True,
    )

    drawer_container = ft.Container(
        visible=False,
        width=420,
        height=560,
        shadow=css_shadow(0.28 if pal["IS_DARK"] else 0.14, 32, 10),
        animate=make_smooth_animation(200),
        content=panel_ctrl,
    )

    fab_icon = ft.Icon(ft.Icons.SMART_TOY_ROUNDED, size=28, color=ft.Colors.WHITE)
    online_dot = ft.Container(
        width=12,
        height=12,
        border_radius=6,
        bgcolor="#22C55E",
        border=ft.border.all(2, "#FFFFFF"),
        right=2,
        top=2,
    )

    floating_chat_btn = ft.Container(
        width=58,
        height=58,
        border_radius=29,
        bgcolor=PRIMARY,
        border=ft.border.all(1.5, "#6EE7B7"),
        shadow=ft.BoxShadow(blur_radius=16, color="#4010B981", offset=ft.Offset(0, 6)),
        alignment=ft.alignment.center,
        ink=True,
        tooltip="Trợ lý AI Thú y (Hỏi đáp chuyên môn bệnh heo)",
        animate=make_smooth_animation(180),
        content=ft.Stack(
            width=58,
            height=58,
            controls=[
                ft.Container(
                    width=58,
                    height=58,
                    alignment=ft.alignment.center,
                    content=fab_icon,
                ),
                online_dot,
            ],
        ),
    )

    overlay_root = ft.Container(
        right=24,
        bottom=24,
        visible=True,
        content=ft.Column(
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.END,
            tight=True,
            controls=[drawer_container, floating_chat_btn],
        ),
    )

    def _set_fab_icon(ic_val: object) -> None:
        if hasattr(fab_icon, "icon"):
            fab_icon.icon = ic_val
        else:
            fab_icon.name = ic_val

    def toggle_drawer(e=None) -> None:
        drawer_container.visible = not drawer_container.visible
        _set_fab_icon(ft.Icons.CLOSE_ROUNDED if drawer_container.visible else ft.Icons.SMART_TOY_ROUNDED)
        if drawer_container.visible:
            refresh_all_chat_views(page)
        else:
            page.update()

    def open_and_ask(prefill: str | None = None) -> None:
        overlay_root.visible = True
        floating_chat_btn.visible = True
        drawer_container.visible = True
        _set_fab_icon(ft.Icons.CLOSE_ROUNDED)
        refresh_all_chat_views(page)
        if prefill:
            send_fn(prefill)

    def set_floating_chat_visible(show: bool) -> None:
        """
        Khi mở Tab 'Trợ lý AI Thú y (Chatbot)' trên Sidebar -> show=False:
        tự động đóng Popup Chat nổi và đặt floating_chat_btn.visible = False.
        Khi chuyển sang các tab khác -> show=True: hiện lại nút tròn Floating Chat.
        """
        if not show:
            drawer_container.visible = False
            _set_fab_icon(ft.Icons.SMART_TOY_ROUNDED)
        floating_chat_btn.visible = show
        overlay_root.visible = show

    floating_chat_btn.on_click = toggle_drawer

    if not isinstance(getattr(page, "data", None), dict):
        page.data = {}
    page.data["open_vet_chat"] = open_and_ask
    page.data["floating_chat_btn"] = floating_chat_btn
    page.data["set_floating_chat_visible"] = set_floating_chat_visible

    return overlay_root
