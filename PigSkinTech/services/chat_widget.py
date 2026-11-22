"""Veterinary AI Chatbot Widget & Sidebar Tab for PigSkinTech (Modern Medical Dashboard, Light & Dark Mode)."""
from __future__ import annotations

import asyncio
import re
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
    is_social_greeting,
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
    "is_social_greeting",
    "refresh_all_chat_views",
    "build_chat_panel",
    "build_chat_overlay",
]

_DISCLAIMER_SPLIT_RE = re.compile(
    r"(?:\n|\r|\s)*(⚠️\s*Lưu ý:\s*Câu trả lời từ Chatbox AI chỉ mang tính chất tham khảo bước đầu.*)$",
    flags=re.IGNORECASE | re.DOTALL,
)


def _overlay_width(page: ft.Page) -> int:
    return min(560, max(420, int((page.width or 1440) * 0.43)))


def _overlay_height(page: ft.Page) -> int:
    # Reserve room for the floating button and margins, including at 720px window height.
    return max(480, min(740, int(page.height or 900) - 120))


def _chat_viewport_height(page: ft.Page) -> int:
    """Explicit bounded height for full-tab chat inside scrolling Role Shell (prevents unbounded height crash)."""
    page_h = int(getattr(page, "height", None) or 900)
    return max(520, min(640, page_h - 330))


def _split_body_and_disclaimer(text: str) -> tuple[str, str]:
    """Separate main clinical Markdown body from mandatory disclaimer for clean visual hierarchy."""
    ensured = ensure_disclaimer(text)
    m = _DISCLAIMER_SPLIT_RE.search(ensured)
    if not m:
        return ensured, MANDATORY_DISCLAIMER
    body = ensured[: m.start()].strip()
    disclaimer = m.group(1).strip()
    return (body or ensured), disclaimer


def _format_short_timestamp(ts: str) -> str:
    raw = (ts or "").strip()
    if not raw:
        return ""
    # "2026-11-22 14:35:10" -> "14:35 · 22/11"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}:\d{2})", raw)
    if m:
        return f"{m.group(4)} · {m.group(3)}/{m.group(2)}"
    return raw


def build_chat_panel(
    page: ft.Page,
    user: dict,
    get_diagnosis_context: Callable[[], dict | None] | None = None,
    compact: bool = False,
) -> tuple[ft.Control, Callable[[str | None], None]]:
    """
    Khung Chatbox Tư vấn Thú y AI chuẩn Modern Medical Dashboard (Light & Dark Mode từ theme.py).
    - Không lặp tiêu đề lớn bên trong card; header gọn gàng với Avatar Bot + tên + badge xanh.
    - Bong bóng tin nhắn hiện đại: User tự co theo độ dài chữ (tối đa ~65%), Bot có Avatar tròn 32x32 + divider tách disclaimer.
    - Đồng bộ tức thì 100% lịch sử tin nhắn giữa Tab chính và Popup góc phải qua `refresh_all_chat_views(page)`.
    """
    pal = get_theme_palette(page)
    user_email = (user or {}).get("email", "nongdan.pigskin@gmail.com")
    user_id = (user or {}).get("user_id") or (user or {}).get("id")

    messages_list = ft.Column(
        spacing=14,
        scroll=ft.ScrollMode.AUTO,
        auto_scroll=True,
        expand=True,
    )
    context_banner_box = ft.Container()
    status_badge_text = ft.Text(
        "Gemini AI • SQL Sync",
        size=11.5,
        weight=ft.FontWeight.W_600,
        color=pal["PROTOCOL_HEAD"],
        no_wrap=True,
    )
    status_badge_dot = ft.Container(
        width=7,
        height=7,
        border_radius=4,
        bgcolor="#10B981",
    )
    status_badge_pill = ft.Container(
        bgcolor=pal["SOFT_EMERALD"],
        border=ft.border.all(1, pal["PROTOCOL_BORDER"]),
        border_radius=20,
        padding=ft.padding.symmetric(horizontal=10, vertical=3),
        content=ft.Row(
            [status_badge_dot, status_badge_text],
            spacing=6,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    chat_input = css_input(
        hint_text="Hỏi về triệu chứng da heo, phác đồ chăm sóc hoặc giải thích kết quả AI...",
        expand=True,
        page=page,
    )
    chat_input.border_radius = 24
    chat_input.text_size = 14
    chat_input.content_padding = ft.padding.symmetric(horizontal=18, vertical=13)

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
        dark = bool(cur_pal["IS_DARK"])
        is_user = role == "user"
        short_ts = _format_short_timestamp(timestamp)

        avail_w = (
            (_overlay_width(page) - 68)
            if compact
            else max(560, min(1060, int(getattr(page, "width", None) or 1440) - 360))
        )

        if is_user:
            # User bubble: auto-shrinks to text length, capped at ~65% of chat container width
            user_max_w = int(avail_w * (0.76 if compact else 0.65))
            lines = (content or "").splitlines() or [""]
            longest_chars = max(len(ln) for ln in lines)
            estimated_w = longest_chars * 9.4 + 34
            bubble_w = None if estimated_w <= user_max_w else user_max_w

            bubble = ft.Container(
                width=bubble_w,
                bgcolor="#0F766E",
                border_radius=ft.border_radius.only(
                    top_left=16,
                    top_right=16,
                    bottom_left=16,
                    bottom_right=4,
                ),
                padding=ft.padding.symmetric(horizontal=15, vertical=10),
                shadow=css_shadow(0.14 if dark else 0.06, 12, 3),
                content=ft.Text(
                    content,
                    size=14,
                    color="#FFFFFF",
                    selectable=True,
                ),
            )
            col_items: list[ft.Control] = [bubble]
            if short_ts:
                col_items.append(
                    ft.Text(
                        short_ts,
                        size=11,
                        color=cur_pal["TEXT_MUTED"],
                    )
                )
            return ft.Row(
                alignment=ft.MainAxisAlignment.END,
                controls=[
                    ft.Column(
                        controls=col_items,
                        horizontal_alignment=ft.CrossAxisAlignment.END,
                        spacing=4,
                        tight=True,
                    )
                ],
            )

        # Bot bubble (left): 32x32 circular avatar + themed bubble with symmetric corner + thin divider before disclaimer
        main_body, disclaimer_txt = _split_body_and_disclaimer(content)
        text_col = cur_pal["TEXT_PRIMARY"]
        md_style = ft.MarkdownStyleSheet(
            p_text_style=ft.TextStyle(size=14, color=text_col, height=1.45),
            strong_text_style=ft.TextStyle(size=14, weight=ft.FontWeight.BOLD, color=text_col, height=1.45),
            list_bullet_text_style=ft.TextStyle(size=14, color=text_col, height=1.45),
            code_text_style=ft.TextStyle(size=13, color="#10B981" if dark else "#0F766E"),
        )
        body_md = ft.Markdown(
            value=main_body,
            selectable=True,
            soft_line_break=True,
            md_style_sheet=md_style,
        )

        bot_avatar = ft.Container(
            width=32,
            height=32,
            border_radius=16,
            bgcolor=cur_pal["SOFT_EMERALD"],
            border=ft.border.all(1, cur_pal["PROTOCOL_BORDER"]),
            alignment=ft.alignment.center,
            content=ft.Icon(
                ft.Icons.MEDICAL_SERVICES_ROUNDED,
                size=16,
                color="#34D399" if dark else "#0F766E",
            ),
        )

        bot_max_w = int(avail_w * (0.82 if compact else 0.72))
        bot_bubble = ft.Container(
            width=None if compact else min(720, bot_max_w),
            bgcolor=cur_pal["BG_CARD"],
            border=ft.border.all(1, cur_pal["BORDER_LIGHT"]),
            border_radius=ft.border_radius.only(
                top_left=16,
                top_right=16,
                bottom_left=4,
                bottom_right=16,
            ),
            padding=ft.padding.symmetric(horizontal=15, vertical=12),
            shadow=css_shadow(0.16 if dark else 0.04, 14, 3),
            content=ft.Column(
                spacing=6,
                tight=True,
                controls=[
                    body_md,
                    ft.Divider(height=8, thickness=1, color=cur_pal["BORDER_LIGHT"]),
                    ft.Text(
                        disclaimer_txt,
                        size=12,
                        color=cur_pal["TEXT_MUTED"],
                    ),
                ],
            ),
        )

        meta_parts = [model_name or "BS. Thú y AI"]
        if short_ts:
            meta_parts.append(short_ts)
        meta_line = ft.Text(
            " · ".join(meta_parts),
            size=11,
            color=cur_pal["TEXT_MUTED"],
        )

        bot_col = ft.Column(
            controls=[bot_bubble, meta_line],
            horizontal_alignment=ft.CrossAxisAlignment.START,
            spacing=4,
            tight=True,
            expand=compact,
        )

        return ft.Row(
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=10,
            controls=[bot_avatar, bot_col],
        )

    def refresh_context_banner() -> None:
        cur_pal = get_theme_palette(page)
        scan = _get_active_scan()
        if scan and scan.get("label"):
            lbl = scan.get("display_label") or display_class(scan.get("label"))
            conf = f"{float(scan.get('confidence') or 0.0) * 100:.1f}%"
            arch = scan.get("architecture") or scan.get("model_label") or "MobileNetV2"
            ms = scan.get("inference_ms", "-")
            context_banner_box.visible = True
            context_banner_box.content = ft.Container(
                bgcolor=cur_pal["SOFT_EMERALD"],
                border=ft.border.all(1, cur_pal["PROTOCOL_BORDER"]),
                border_radius=10,
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.BIOTECH_ROUNDED, size=18, color=PRIMARY),
                        ft.Text(
                            f"Đang liên kết kết quả quét: {lbl} ({conf} · {arch} · {ms}ms)",
                            size=12.5,
                            weight=ft.FontWeight.W_600,
                            color=cur_pal["PROTOCOL_HEAD"],
                            expand=True,
                        ),
                    ],
                ),
            )
        else:
            context_banner_box.visible = False
            context_banner_box.content = None

    def reload_history() -> None:
        refresh_context_banner()
        messages_list.controls.clear()
        rows = list_chat_messages(user_email=user_email, limit=50)
        if not rows:
            welcome_msg = (
                "Xin chào! Tôi là **BS. Thú y AI — PigSkinTech**.\n\n"
                "Bạn có thể hỏi trực tiếp về:\n"
                "• **Các bệnh ngoài da ở heo** (nổi mẩn đỏ, mụn nước, đóng vảy, ghẻ, nấm, cách ly, vệ sinh chuồng trại, phác đồ chăm sóc bước đầu).\n"
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
            await asyncio.sleep(0.06)
            try:
                if getattr(messages_list, "page", None) is not None:
                    messages_list.scroll_to(delta=1_000_000, duration=180)
            except (AttributeError, RuntimeError):
                pass

        if hasattr(page, "run_task"):
            page.run_task(scroll_after_render)

    register_chat_refresher(page, reload_history)

    sending_state = {"busy": False}

    async def _send_async(prefill_text: str | None = None) -> None:
        if sending_state["busy"]:
            return
        question = (prefill_text if prefill_text is not None else (chat_input.value or "")).strip()
        if not question:
            return
        sending_state["busy"] = True
        if prefill_text is None:
            chat_input.value = ""

        try:
            scan = _get_active_scan()
            case_code = str(scan.get("label") or "") if (scan and scan.get("is_valid_pig", True)) else ""

            save_chat_message(
                user_email=user_email,
                role="user",
                content=question,
                user_id=user_id,
                case_id=case_code,
                model_name="user",
            )
            status_badge_dot.bgcolor = "#F59E0B"
            status_badge_text.value = "Đang phân tích..."
            refresh_all_chat_views(page)

            history_rows = list_chat_messages(user_email=user_email, limit=12)
            valid_scan = scan if (scan and scan.get("is_valid_pig", True)) else None
            raw_reply, used_model = await asyncio.to_thread(ask_vet_ai, question, history_rows, valid_scan)
            final_reply = ensure_disclaimer(raw_reply)

            save_chat_message(
                user_email=user_email,
                role="assistant",
                content=final_reply,
                user_id=user_id,
                case_id=case_code,
                model_name=used_model,
            )
            status_badge_dot.bgcolor = "#10B981"
            status_badge_text.value = "Gemini AI • SQL Sync"
            refresh_all_chat_views(page)
        except Exception as exc:
            status_badge_dot.bgcolor = "#EF4444"
            status_badge_text.value = f"Lỗi xử lý: {str(exc)[:36]}"
            page.update()
        finally:
            sending_state["busy"] = False

    def send_message(prefill: str | None = None) -> None:
        page.run_task(_send_async, prefill)

    chat_input.on_submit = lambda e: send_message(None)

    def clear_history_click(e=None) -> None:
        clear_chat_messages(user_email)
        status_badge_dot.bgcolor = "#10B981"
        status_badge_text.value = "Gemini AI • SQL Sync"
        refresh_all_chat_views(page)

    quick_questions = [
        (
            ft.Icons.MEDICATION_OUTLINED,
            "Chăm sóc & Liều thuốc",
            "Cho tôi phác đồ chăm sóc bước đầu và liều lượng thuốc tham khảo cho kết quả bệnh mô hình vừa quét?",
        ),
        (
            ft.Icons.CLEANING_SERVICES_OUTLINED,
            "Cách ly & Vệ sinh chuồng",
            "Cần cách ly heo bệnh và vệ sinh sát trùng chuồng trại như thế nào cho kết quả vừa quét?",
        ),
        (
            ft.Icons.PSYCHOLOGY_OUTLINED,
            "Giải thích mô hình AI",
            "Giải thích kết quả chẩn đoán từ mô hình Deep Learning (MobileNetV2, EfficientNet-B0) và độ tự tin Softmax?",
        ),
        (
            ft.Icons.HELP_OUTLINE_ROUNDED,
            "Hướng dẫn dùng ứng dụng",
            "Hướng dẫn sử dụng ứng dụng PigSkinTech để quét ảnh, gửi thẩm định chuyên gia và in phiếu khám?",
        ),
    ]

    def _on_chip_hover(e) -> None:
        cur_pal = get_theme_palette(page)
        hovered = str(getattr(e, "data", "")).lower() == "true"
        e.control.bgcolor = cur_pal["SOFT_EMERALD"] if hovered else cur_pal["BG_SUB"]
        e.control.border = ft.border.all(1, PRIMARY if hovered else cur_pal["BORDER_LIGHT"])
        e.control.update()

    chips_row = ft.Row(
        spacing=8,
        run_spacing=8,
        wrap=True,
        controls=[
            ft.Container(
                bgcolor=pal["BG_SUB"],
                border=ft.border.all(1, pal["BORDER_LIGHT"]),
                border_radius=20,
                padding=ft.padding.symmetric(horizontal=13, vertical=7),
                animate=make_smooth_animation(150),
                ink=True,
                on_hover=_on_chip_hover,
                on_click=lambda e, q=q_txt: send_message(q),
                content=ft.Row(
                    [
                        ft.Icon(ic, size=15, color="#10B981" if pal["IS_DARK"] else "#0F766E"),
                        ft.Text(lbl, size=12.5, weight=ft.FontWeight.W_600, color=pal["TEXT_PRIMARY"]),
                    ],
                    spacing=6,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
            for ic, lbl, q_txt in quick_questions
        ],
    )

    reload_history()

    # Compact card header (no duplicated large page title)
    header_avatar = ft.Container(
        width=36,
        height=36,
        border_radius=18,
        bgcolor="#0F766E",
        alignment=ft.alignment.center,
        content=ft.Icon(ft.Icons.MEDICAL_SERVICES_ROUNDED, color="#FFFFFF", size=19),
    )
    bot_title = ft.Text(
        "BS. Thú y AI — PigSkinTech",
        size=14.5 if compact else 15.5,
        weight=ft.FontWeight.BOLD,
        color=pal["TEXT_PRIMARY"],
        no_wrap=True,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    if compact:
        header_identity: ft.Control = ft.Column(
            [bot_title, status_badge_pill],
            spacing=3,
            tight=True,
            expand=True,
        )
    else:
        header_identity = ft.Row(
            [bot_title, status_badge_pill],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )

    header_bar = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
                controls=[header_avatar, header_identity],
            ),
            ft.IconButton(
                icon=ft.Icons.DELETE_SWEEP_ROUNDED,
                icon_size=20,
                icon_color=pal["TEXT_MUTED"],
                tooltip="Xóa lịch sử trò chuyện",
                on_click=clear_history_click,
            ),
        ],
    )

    send_btn = ft.FilledButton(
        "Gửi",
        icon=ft.Icons.SEND_ROUNDED,
        height=48,
        style=ft.ButtonStyle(
            bgcolor="#0F766E",
            color="#FFFFFF",
            icon_color="#FFFFFF",
            padding=ft.padding.symmetric(horizontal=20, vertical=0),
            shape=ft.RoundedRectangleBorder(radius=24),
            text_style=ft.TextStyle(size=14, weight=ft.FontWeight.W_600),
        ),
        on_click=lambda e: send_message(None),
    )

    messages_viewport = ft.Container(
        height=None if compact else _chat_viewport_height(page),
        expand=compact,
        data="theme_chat_messages",
        bgcolor=pal["BG_MAIN"],
        border=ft.border.all(1, pal["BORDER_LIGHT"]),
        border_radius=14,
        padding=ft.padding.symmetric(horizontal=16, vertical=14),
        content=messages_list,
    )

    card = css_card(
        page=page,
        padding=16 if compact else 20,
        border_radius=16,
        content=ft.Column(
            spacing=12,
            expand=compact,
            tight=not compact,
            controls=[
                header_bar,
                ft.Divider(height=1, thickness=1, color=pal["BORDER_LIGHT"]),
                context_banner_box,
                messages_viewport,
                chips_row,
                ft.Row(
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[chat_input, send_btn],
                ),
            ],
        ),
    )
    card.data = "theme_chat_card"
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
        width=_overlay_width(page),
        height=_overlay_height(page),
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
            drawer_container.width = _overlay_width(page)
            drawer_container.height = _overlay_height(page)
            refresh_all_chat_views(page)
        else:
            page.update()

    def open_and_ask(prefill: str | None = None) -> None:
        overlay_root.visible = True
        floating_chat_btn.visible = True
        drawer_container.visible = True
        drawer_container.width = _overlay_width(page)
        drawer_container.height = _overlay_height(page)
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
