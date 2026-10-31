"""components/metric_card.py — Thẻ KPI có icon, giá trị lớn, phụ đề và dải màu nhấn."""
from __future__ import annotations

import flet as ft


class MetricCard(ft.Container):
    def __init__(self, title: str, value: str = "—", subtitle: str = "", icon: str = ft.Icons.INSIGHTS,
                 accent: str = ft.Colors.PRIMARY, extra: ft.Control | None = None, col=None):
        self._title = ft.Text(title, size=12, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE_VARIANT)
        self._value = ft.Text(value, size=28, weight=ft.FontWeight.W_700)
        self._subtitle = ft.Text(subtitle, size=12, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=2,
                                 overflow=ft.TextOverflow.ELLIPSIS)
        self._extra_holder = ft.Container(content=extra)
        icon_box = ft.Container(
            content=ft.Icon(icon, size=20, color=accent),
            width=36, height=36, border_radius=10, alignment=ft.alignment.center,
            bgcolor=ft.Colors.with_opacity(0.14, accent),
        )
        super().__init__(
            col=col or {"xs": 12, "sm": 6, "lg": 3},
            padding=ft.padding.only(left=16, right=16, top=14, bottom=14),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.border.only(
                left=ft.BorderSide(4, accent),
                top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            ),
            border_radius=12,
            content=ft.Column(
                [
                    ft.Row([self._title, icon_box], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self._value,
                    self._subtitle,
                    self._extra_holder,
                ],
                spacing=4,
            ),
            animate=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
        )

    def set(self, value: str | None = None, subtitle: str | None = None, extra: ft.Control | None = None) -> None:
        if value is not None:
            self._value.value = value
        if subtitle is not None:
            self._subtitle.value = subtitle
        if extra is not None:
            self._extra_holder.content = extra
