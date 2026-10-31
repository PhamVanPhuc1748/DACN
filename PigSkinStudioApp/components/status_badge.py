"""components/status_badge.py — Nhãn trạng thái dạng "pill" dùng chung cho mọi review_status / status."""
from __future__ import annotations

import flet as ft

import config


class StatusBadge(ft.Container):
    def __init__(self, status: str | None, *, compact: bool = False, label: str | None = None):
        self._dot = ft.Container(width=7, height=7, border_radius=4)
        self._text = ft.Text(size=11 if compact else 12, weight=ft.FontWeight.W_600)
        super().__init__(
            content=ft.Row([self._dot, self._text], spacing=6, tight=True),
            padding=ft.padding.symmetric(horizontal=8 if compact else 10, vertical=3 if compact else 4),
            border_radius=20,
        )
        self.set_status(status, label)

    def set_status(self, status: str | None, label: str | None = None) -> None:
        text, color = config.STATUS_STYLES.get(status or "", (status or "—", "#8A94A0"))
        self._dot.bgcolor = color
        self._text.value = label or text
        self._text.color = color
        self.bgcolor = ft.Colors.with_opacity(0.14, color)
        self.border = ft.border.all(1, ft.Colors.with_opacity(0.35, color))
        self.tooltip = status
