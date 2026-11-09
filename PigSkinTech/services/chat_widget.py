"""Floating AI chat widget shared by all PigSkinTech roles."""

from __future__ import annotations

import asyncio
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import flet as ft

from theme import get_theme_palette


CHAT_API_URL = os.getenv("PIGSKIN_CHAT_API_URL", "http://127.0.0.1:8000/chat")


def _send_chat(messages: list[dict[str, str]]) -> str:
    payload = json.dumps({"messages": messages}, ensure_ascii=False).encode("utf-8")
    request = Request(
        CHAT_API_URL,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        try:
            result = json.loads(error.read().decode("utf-8"))
            detail = result.get("detail")
        except (UnicodeDecodeError, json.JSONDecodeError):
            detail = None
        if error.code == 503 and detail:
            raise RuntimeError(str(detail)) from error
        raise RuntimeError("AI chưa thể trả lời lúc này. Hãy thử lại sau.") from error
    except (URLError, TimeoutError, OSError) as error:
        raise RuntimeError(
            "Chưa kết nối được backend. Hãy khởi động PigSkin API rồi thử lại."
        ) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("Backend trả về dữ liệu không đọc được.") from error

    reply = result.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        raise RuntimeError("AI chưa trả về nội dung. Hãy thử lại sau.")
    return reply.strip()


def build_chat_overlay(page: ft.Page) -> ft.Control:
    palette = get_theme_palette(page)
    messages: list[dict[str, str]] = []
    transcript = ft.ListView(expand=True, spacing=10, auto_scroll=True)
    prompt = ft.TextField(
        hint_text="Nhập câu hỏi của bạn...",
        multiline=True,
        min_lines=1,
        max_lines=3,
        expand=True,
        shift_enter=True,
        border_radius=12,
        text_size=14,
        filled=True,
        bgcolor=palette["BG_SUB"],
        border_color=palette["BORDER_LIGHT"],
        focused_border_color=palette["PRIMARY"],
    )
    send_button = ft.FilledButton(
        "Gửi",
        icon=ft.Icons.SEND_ROUNDED,
    )

    def add_bubble(role: str, content: str):
        is_user = role == "user"
        bubble = ft.Container(
            width=300,
            padding=11,
            border_radius=12,
            bgcolor=palette["SOFT_EMERALD"] if is_user else palette["BG_SUB"],
            border=ft.border.all(1, palette["BORDER_LIGHT"]),
            content=ft.Text(
                content,
                size=13.5,
                color=palette["TEXT_PRIMARY"],
                selectable=True,
            ),
        )
        transcript.controls.append(
            ft.Row(
                [bubble],
                alignment=ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START,
            )
        )

    async def send_message(_):
        text = (prompt.value or "").strip()
        if not text or send_button.disabled:
            return

        messages.append({"role": "user", "content": text})
        messages[:] = messages[-12:]
        prompt.value = ""
        add_bubble("user", text)
        prompt.disabled = True
        send_button.disabled = True
        send_button.text = "Đang gửi..."
        page.update()

        try:
            reply = await asyncio.to_thread(_send_chat, messages.copy())
        except RuntimeError as error:
            reply = str(error)
        except Exception:
            reply = "Đã xảy ra lỗi khi liên hệ AI. Hãy thử lại sau."

        messages.append({"role": "assistant", "content": reply})
        messages[:] = messages[-12:]
        add_bubble("assistant", reply)
        prompt.disabled = False
        send_button.disabled = False
        send_button.text = "Gửi"
        page.update()

    send_button.on_click = send_message
    prompt.on_submit = send_message

    panel = ft.Container(
        width=380,
        height=500,
        visible=False,
        padding=16,
        bgcolor=palette["BG_CARD"],
        border=ft.border.all(1, palette["BORDER_LIGHT"]),
        border_radius=18,
        shadow=ft.BoxShadow(
            spread_radius=1,
            blur_radius=24,
            color=ft.Colors.with_opacity(0.18, "#0F172A"),
            offset=ft.Offset(0, 8),
        ),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            width=40,
                            height=40,
                            alignment=ft.alignment.center,
                            border_radius=12,
                            bgcolor=palette["SOFT_EMERALD"],
                            content=ft.Text("🐷", size=23),
                        ),
                        ft.Column(
                            [
                                ft.Text("Trợ lý PigSkin AI", size=15, weight=ft.FontWeight.BOLD, color=palette["TEXT_PRIMARY"]),
                                ft.Text("Hỗ trợ thông tin về da heo", size=11.5, color=palette["TEXT_MUTED"]),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE_ROUNDED,
                            tooltip="Đóng chat",
                            on_click=lambda e: toggle_panel(),
                        ),
                    ],
                    spacing=10,
                ),
                ft.Divider(height=8, color=palette["BORDER_LIGHT"]),
                ft.Container(
                    expand=True,
                    content=transcript,
                ),
                ft.Row([prompt, send_button], spacing=8, vertical_alignment=ft.CrossAxisAlignment.END),
                ft.Text(
                    "Thông tin tham khảo; không thay thế xác nhận của bác sĩ thú y.",
                    size=10.5,
                    color=palette["TEXT_MUTED"],
                ),
            ],
            spacing=9,
            expand=True,
        ),
    )
    add_bubble(
        "assistant",
        "Xin chào! Mình có thể hỗ trợ câu hỏi về dự án và thông tin bệnh da heo. "
        "Câu trả lời chỉ mang tính tham khảo.",
    )

    def toggle_panel():
        panel.visible = not panel.visible
        page.update()

    launcher = ft.FloatingActionButton(
        content=ft.Text("🐷", size=25),
        tooltip="Mở trợ lý PigSkin AI",
        bgcolor=palette["PRIMARY"],
        foreground_color="#FFFFFF",
        on_click=lambda e: toggle_panel(),
    )
    return ft.Container(
        right=22,
        bottom=22,
        content=ft.Column(
            [
                panel,
                launcher,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.END,
            alignment=ft.MainAxisAlignment.END,
            spacing=12,
            tight=True,
        ),
    )
