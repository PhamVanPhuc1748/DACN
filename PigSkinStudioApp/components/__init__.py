"""components — custom control tái sử dụng + tiện ích UI nhỏ."""
from __future__ import annotations

import flet as ft


def safe_update(*controls: ft.Control) -> None:
    """Gọi update() chỉ khi control đang nằm trên page (tránh lỗi khi người dùng đã chuyển trang
    trong lúc thread nền còn chạy)."""
    for c in controls:
        if c is not None and c.page is not None:
            try:
                c.update()
            except AssertionError:
                pass


def toast(page: ft.Page, message: str, kind: str = "info") -> None:
    colors = {"info": ft.Colors.PRIMARY, "ok": "#2E9E6A", "warn": "#B7791F", "error": "#C62828"}
    page.open(ft.SnackBar(
        content=ft.Text(message, color=ft.Colors.WHITE),
        bgcolor=colors.get(kind, ft.Colors.PRIMARY),
        behavior=ft.SnackBarBehavior.FLOATING,
        show_close_icon=True,
        duration=4000,
    ))


def section_title(text: str, subtitle: str | None = None, icon: str | None = None) -> ft.Control:
    row = [ft.Icon(icon, size=20, color=ft.Colors.PRIMARY)] if icon else []
    row.append(ft.Text(text, size=16, weight=ft.FontWeight.W_600))
    items: list[ft.Control] = [ft.Row(row, spacing=8)]
    if subtitle:
        items.append(ft.Text(subtitle, size=12, color=ft.Colors.ON_SURFACE_VARIANT))
    return ft.Column(items, spacing=2)


def panel(content: ft.Control, *, padding: int = 16, expand: bool | int | None = None,
          width: float | None = None, height: float | None = None) -> ft.Container:
    """Khung "card" thống nhất cho toàn app."""
    return ft.Container(
        content=content,
        padding=padding,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
        border_radius=12,
        expand=expand,
        width=width,
        height=height,
    )


def fmt_num(value, digits: int = 4) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def fmt_int(value) -> str:
    """Định dạng số nguyên kiểu Việt Nam: 2.017"""
    if value is None:
        return "—"
    return f"{int(value):,}".replace(",", ".")
