"""Authentication service, Tech Emerald & Cyber Slate Design System, and Custom Sidebar Shell."""
import base64
import csv
import hashlib
import html
import inspect
import os
from datetime import datetime
from pathlib import Path
import urllib.parse
import webbrowser

import flet as ft
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

try:
    from flet.auth.providers import GoogleOAuthProvider
except ImportError:  # pragma: no cover
    GoogleOAuthProvider = getattr(ft, "GoogleOAuthProvider", None)

if GoogleOAuthProvider and not hasattr(ft, "GoogleOAuthProvider"):
    ft.GoogleOAuthProvider = GoogleOAuthProvider

from http.server import BaseHTTPRequestHandler, HTTPServer
import secrets
import threading
import time
from urllib.parse import parse_qs, urlencode, urlparse
import requests

from services.config_store import read_settings, save_settings
from services.inference import model_ready
from services.project_data import active_run, display_class, get_class_info, load_classes_config
from services.store import _hash_password, conn, initialize, recent
from theme import (
    BG_CARD,
    BG_MAIN,
    BG_SIDEBAR,
    BORDER_LIGHT,
    PRIMARY,
    PRIMARY_DARK,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    css_card,
    css_dropdown,
    css_input,
    css_kpi_card,
    css_shadow,
    get_theme_palette,
    make_smooth_animation,
    set_theme_page_context,
)


GOOGLE_CALLBACK_HOST = "127.0.0.1"
GOOGLE_CALLBACK_PORT = 8765
REDIRECT_URL = f"http://{GOOGLE_CALLBACK_HOST}:{GOOGLE_CALLBACK_PORT}/callback"
GOOGLE_REDIRECT_URI = REDIRECT_URL
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"

ROLE_LABELS = {
    "user": "Người chăn nuôi",
    "expert": "Bác sĩ Thú y",
    "admin": "Quản trị viên",
}

ROLE_COLORS = {
    "user": "#059669",
    "expert": "#0284C7",
    "admin": "#9333EA",
}

ROLE_ROUTES = {
    "user": "/user",
    "expert": "/expert",
    "admin": "/admin",
}

THEMES = {
    "light": {
        "BG": "#F8FAFC",
        "SURFACE": "#FFFFFF",
        "SUB_SURFACE": "#F1F5F9",
        "SIDEBAR_BG": "#0F172A",
        "SIDEBAR_HOVER": "#1E293B",
        "SIDEBAR_TEXT": "#94A3B8",
        "SIDEBAR_ACTIVE_TEXT": "#FFFFFF",
        "SIDEBAR_BORDER": "#1E293B",
        "BORDER": "#E2E8F0",
        "TEXT": "#0F172A",
        "SECONDARY": "#475569",
        "MUTED": "#64748B",
        "EMERALD": PRIMARY_DARK,
        "EMERALD_LIGHT": PRIMARY,
        "EMERALD_SOFT": "#ECFDF5",
        "CYAN": "#0284C7",
        "CYAN_SOFT": "#EFF6FF",
        "AMBER": "#D97706",
        "AMBER_SOFT": "#FFFBEB",
        "RED": "#DC2626",
        "RED_SOFT": "#FEF2F2",
        "PURPLE": "#7C3AED",
        "PURPLE_SOFT": "#F3E8FF",
    },
    "dark": {
        "BG": "#0B1120",
        "SURFACE": "#1E293B",
        "SUB_SURFACE": "#0F172A",
        "SIDEBAR_BG": "#090E1A",
        "SIDEBAR_HOVER": "#1E293B",
        "SIDEBAR_TEXT": "#94A3B8",
        "SIDEBAR_ACTIVE_TEXT": "#FFFFFF",
        "SIDEBAR_BORDER": "#1E293B",
        "BORDER": "#334155",
        "TEXT": "#F8FAFC",
        "SECONDARY": "#CBD5E1",
        "MUTED": "#94A3B8",
        "EMERALD": "#10B981",
        "EMERALD_LIGHT": "#34D399",
        "EMERALD_SOFT": "#064E3B",
        "CYAN": "#38BDF8",
        "CYAN_SOFT": "#0C4A6E",
        "AMBER": "#F59E0B",
        "AMBER_SOFT": "#78350F",
        "RED": "#F87171",
        "RED_SOFT": "#7F1D1D",
        "PURPLE": "#A855F7",
        "PURPLE_SOFT": "#4C1D95",
    },
}


def ensure_flet_compat(page: ft.Page | None = None):
    """Ensure Flet 0.28.x and Flet 1.0.x APIs work identically."""
    if page is not None:
        set_theme_page_context(page)
    if hasattr(ft, "Alignment") and hasattr(ft, "alignment"):
        for name in (
            "center",
            "top_left",
            "top_right",
            "bottom_left",
            "bottom_right",
            "center_left",
            "center_right",
            "top_center",
            "bottom_center",
        ):
            if not hasattr(ft.alignment, name) and hasattr(ft.Alignment, name.upper()):
                setattr(ft.alignment, name, getattr(ft.Alignment, name.upper()))
    if hasattr(ft, "Padding") and hasattr(ft, "padding"):
        for name in ("all", "symmetric", "only", "zero"):
            if not hasattr(ft.padding, name) and hasattr(ft.Padding, name):
                setattr(ft.padding, name, getattr(ft.Padding, name))
    if hasattr(ft, "Margin") and hasattr(ft, "margin"):
        for name in ("all", "symmetric", "only", "zero"):
            if not hasattr(ft.margin, name) and hasattr(ft.Margin, name):
                setattr(ft.margin, name, getattr(ft.Margin, name))
    if hasattr(ft, "Border") and hasattr(ft, "border"):
        for name in ("all", "only", "symmetric"):
            if not hasattr(ft.border, name) and hasattr(ft.Border, name):
                setattr(ft.border, name, getattr(ft.Border, name))
    if not hasattr(ft, "ElevatedButton") and hasattr(ft, "FilledButton"):
        ft.ElevatedButton = ft.FilledButton
    if not hasattr(ft, "ImageFit") and hasattr(ft, "BoxFit"):
        ft.ImageFit = ft.BoxFit
    if not hasattr(ft, "BoxFit") and hasattr(ft, "ImageFit"):
        ft.BoxFit = ft.ImageFit
    if not hasattr(ft, "colors") and hasattr(ft, "Colors"):
        ft.colors = ft.Colors
    if not hasattr(ft, "icons") and hasattr(ft, "Icons"):
        ft.icons = ft.Icons
    if not hasattr(ft, "app") and hasattr(ft, "run"):
        ft.app = lambda target=None, **kw: ft.run(target, **kw)

    if page is not None:
        if hasattr(page, "session") and hasattr(page.session, "store") and not hasattr(page.session, "set"):
            store = page.session.store
            page.session.set = store.set
            page.session.get = store.get
            page.session.clear = store.clear
            page.session.contains_key = store.contains_key
            page.session.remove = store.remove


def session_set(page: ft.Page, key: str, value):
    ensure_flet_compat(page)
    store = getattr(page.session, "store", page.session)
    if hasattr(store, "set"):
        store.set(key, value)
    else:
        store[key] = value


def session_get(page: ft.Page, key: str):
    ensure_flet_compat(page)
    store = getattr(page.session, "store", page.session)
    return store.get(key)


def session_clear(page: ft.Page):
    ensure_flet_compat(page)
    store = getattr(page.session, "store", page.session)
    store.clear()


def is_dark_mode(page: ft.Page | None = None) -> bool:
    if page is None:
        return get_theme_palette(None)["IS_DARK"]
    set_theme_page_context(page)
    mode = session_get(page, "theme_mode")
    if mode:
        return mode == "dark"
    return getattr(page, "theme_mode", ft.ThemeMode.LIGHT) == ft.ThemeMode.DARK


def theme_tokens(page: ft.Page | None = None) -> dict:
    if page is not None:
        set_theme_page_context(page)
    return THEMES["dark" if is_dark_mode(page) else "light"]


def _rgb_color(value, inherited=None):
    """Resolve a Flet color (including #AARRGGBB) against its parent."""
    if not isinstance(value, str):
        return inherited
    color = value.strip().lower()
    if color in ("transparent", "none"):
        return inherited
    color = {"white": "#ffffff", "black": "#000000"}.get(color, color)
    if not color.startswith("#"):
        return inherited
    raw = color[1:]
    if len(raw) == 3:
        raw = "".join(char * 2 for char in raw)
    try:
        if len(raw) == 8:
            alpha = int(raw[:2], 16) / 255
            rgb = tuple(int(raw[index:index + 2], 16) for index in (2, 4, 6))
            if inherited is not None:
                return tuple(round(alpha * channel + (1 - alpha) * base) for channel, base in zip(rgb, inherited))
            return rgb
        if len(raw) == 6:
            return tuple(int(raw[index:index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        pass
    return inherited


def _luminance(rgb):
    channels = [channel / 255 for channel in rgb]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def apply_theme_text_contrast(root, background=None, palette=None):
    """Repair unreadable text after an in-place theme change or tab rebuild."""
    seen = set()

    def visit(control, parent_bg):
        if id(control) in seen:
            return
        seen.add(id(control))
        surface = getattr(control, "data", None)
        if palette is not None and surface in ("theme_chat_card", "theme_chat_messages"):
            control.bgcolor = palette["BG_CARD" if surface == "theme_chat_card" else "BG_MAIN"]
        if isinstance(control, (ft.TextField, ft.Dropdown)) and palette is not None:
            current_fill = getattr(control, "fill_color", None)
            theme_fills = {THEMES["light"]["SUB_SURFACE"], THEMES["dark"]["SUB_SURFACE"]}
            if current_fill in theme_fills:
                control.fill_color = palette["BG_SUB"]
        own_bg = _rgb_color(getattr(control, "bgcolor", None), parent_bg)
        if isinstance(control, (ft.TextField, ft.Dropdown)) and getattr(control, "filled", False):
            own_bg = _rgb_color(getattr(control, "fill_color", None), own_bg)
        gradient = getattr(control, "gradient", None)
        if gradient is not None and getattr(gradient, "colors", None):
            colors = [_rgb_color(color, own_bg) for color in gradient.colors]
            colors = [color for color in colors if color is not None]
            if colors:
                own_bg = tuple(round(sum(color[i] for color in colors) / len(colors)) for i in range(3))
        if own_bg is None:
            own_bg = (255, 255, 255)
        foreground = "#FFFFFF" if _luminance(own_bg) < 0.18 else "#0F172A"

        def fix_color(value):
            rgb = _rgb_color(value)
            if rgb is None:
                return foreground
            light, dark = sorted((_luminance(rgb), _luminance(own_bg)))
            return foreground if (dark + 0.05) / (light + 0.05) < 4.5 else value

        if isinstance(control, (ft.Text, ft.TextField, ft.Dropdown, ft.Markdown)):
            if isinstance(control, ft.Markdown):
                sheet = getattr(control, "md_style_sheet", None)
                if sheet is not None:
                    for name in ("p_text_style", "strong_text_style", "list_bullet_text_style", "em_text_style", "h1_text_style", "h2_text_style", "h3_text_style", "blockquote_text_style", "code_text_style"):
                        style = getattr(sheet, name, None)
                        if style is not None:
                            style.color = fix_color(getattr(style, "color", None))
            else:
                control.color = fix_color(getattr(control, "color", None))
                if isinstance(control, (ft.TextField, ft.Dropdown)):
                    for name in ("label_style", "hint_style"):
                        style = getattr(control, name, None)
                        if style is not None:
                            style.color = fix_color(getattr(style, "color", None))
        for child in control._get_children():
            child_bg = own_bg
            if isinstance(control, ft.DataTable) and isinstance(child, ft.DataColumn):
                child_bg = _rgb_color(getattr(control, "heading_row_color", None), own_bg)
            visit(child, child_bg)

    visit(root, background)


def toggle_theme_mode(page: ft.Page):
    old_theme = theme_tokens(page)
    old_palette = get_theme_palette(page)
    new_mode = "light" if is_dark_mode(page) else "dark"
    session_set(page, "theme_mode", new_mode)
    page.theme_mode = ft.ThemeMode.DARK if new_mode == "dark" else ft.ThemeMode.LIGHT
    set_theme_page_context(page)
    new_theme = theme_tokens(page)
    new_palette = get_theme_palette(page)

    background_keys = (
        "BG", "SURFACE", "SUB_SURFACE", "SIDEBAR_BG", "SIDEBAR_HOVER",
        "EMERALD_SOFT", "CYAN_SOFT", "AMBER_SOFT", "RED_SOFT", "PURPLE_SOFT",
        "BG_MAIN", "BG_CARD", "BG_SUB", "BG_SIDEBAR", "SOFT_EMERALD",
        "SOFT_BLUE", "SOFT_AMBER", "SOFT_RED", "SOFT_PURPLE",
    )
    foreground_keys = (
        "TEXT", "SECONDARY", "MUTED", "SIDEBAR_TEXT", "SIDEBAR_ACTIVE_TEXT",
        "TEXT_PRIMARY", "TEXT_SECONDARY", "TEXT_MUTED", "PROTOCOL_HEAD", "PROTOCOL_TEXT",
        "EMERALD", "EMERALD_LIGHT", "CYAN", "AMBER", "RED", "PURPLE",
    )

    def color_map(keys):
        result = {}
        for before, after in ((old_theme, new_theme), (old_palette, new_palette)):
            for key in keys:
                source, target = before.get(key), after.get(key)
                if isinstance(source, str) and isinstance(target, str) and source != target:
                    result[source.lower()] = target
        return result

    backgrounds = color_map(background_keys)
    foregrounds = color_map(foreground_keys)
    borders = color_map(("BORDER", "BORDER_LIGHT", "DROPZONE_BORDER", "PROTOCOL_BORDER"))

    def mapped(value, palette):
        return palette.get(value.lower(), value) if isinstance(value, str) else value

    visited = set()

    def recolor(control):
        if id(control) in visited:
            return
        visited.add(id(control))
        for attr, palette in (
            ("bgcolor", backgrounds), ("fill_color", backgrounds),
            ("heading_row_color", backgrounds), ("color", foregrounds),
            ("icon_color", foregrounds), ("border_color", borders),
            ("focused_border_color", borders),
        ):
            if attr == "bgcolor" and getattr(control, "data", None) == "fixed_dark_sidebar_card":
                continue
            value = getattr(control, attr, None)
            changed = mapped(value, palette)
            if changed != value:
                setattr(control, attr, changed)
        border = getattr(control, "border", None)
        if border is not None:
            for side_name in ("top", "right", "bottom", "left"):
                side = getattr(border, side_name, None)
                if side is not None:
                    side.color = mapped(side.color, borders)
        gradient = getattr(control, "gradient", None)
        if gradient is not None and getattr(gradient, "colors", None):
            gradient.colors = [mapped(color, backgrounds) for color in gradient.colors]
        if getattr(control, "data", None) == "theme_toggle":
            control.icon = ft.Icons.LIGHT_MODE_ROUNDED if new_mode == "dark" else ft.Icons.DARK_MODE_ROUNDED
            control.icon_color = "#FBBF24" if new_mode == "dark" else "#CBD5E1"
        for child in control._get_children():
            recolor(child)

    roots = [*page.controls, *getattr(page, "overlay", [])]
    for extra in (getattr(page, "dialog", None), getattr(page, "appbar", None)):
        if extra is not None:
            roots.append(extra)
    for root in roots:
        recolor(root)
    page.bgcolor = new_theme["BG"]
    page_bg = _rgb_color(page.bgcolor)
    for root in roots:
        apply_theme_text_contrast(root, page_bg, new_palette)
    page.update()


def card_shadow() -> ft.BoxShadow:
    return css_shadow(0.04, 24, 6)


def tech_card(
    content: ft.Control,
    page: ft.Page | None = None,
    padding: int = 24,
    expand: int | bool | None = None,
    border_radius: int = 16,
    gradient: ft.LinearGradient | None = None,
    bgcolor: str | None = None,
    border_color: str | None = None,
    hover_lift: bool = False,
) -> ft.Container:
    t = theme_tokens(page)
    return css_card(
        content=content,
        padding=padding,
        expand=expand,
        border_radius=border_radius,
        bgcolor=bgcolor or t["SURFACE"],
        border_color=border_color or t["BORDER"],
        gradient=gradient,
        page=page,
        hover_lift=hover_lift,
    )


def header_stat_pill(
    label: str,
    value: str,
    icon: object,
    accent: str = PRIMARY_DARK,
    soft_bg: str = "#ECFDF5",
    badge_text: str = "Hoạt động tốt",
    page: ft.Page | None = None,
    col: dict | None = None,
) -> ft.Container:
    """Modern SaaS KPI Stat Card with height=None, padding=16 and 3-row Column layout inside ResponsiveRow."""
    t = theme_tokens(page)
    dark = is_dark_mode(page)
    box_bg = ft.Colors.with_opacity(0.22, accent) if dark else soft_bg
    return ft.Container(
        col=col or {"xs": 12, "sm": 6, "lg": 4},
        height=None,
        bgcolor=t["SURFACE"],
        border=ft.border.all(1, t["BORDER"]),
        border_radius=16,
        padding=16,
        shadow=css_shadow(0.18 if dark else 0.04, 24, 6),
        animate=make_smooth_animation(200),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            width=42,
                            height=42,
                            bgcolor=box_bg,
                            border_radius=12,
                            alignment=ft.alignment.center,
                            content=ft.Icon(icon, color=accent, size=22),
                        ),
                        *(
                            [
                                ft.Container(
                                    bgcolor=box_bg,
                                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                                    border_radius=12,
                                    content=ft.Text(
                                        str(badge_text),
                                        size=12,
                                        color=accent,
                                        weight=ft.FontWeight.W_600,
                                    ),
                                )
                            ]
                            if badge_text
                            else []
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        ft.Text(
                            str(label),
                            size=14.5,
                            color=t["TEXT"],
                            weight=ft.FontWeight.W_700,
                            expand=True,
                        )
                    ]
                ),
                ft.Row(
                    [
                        ft.Text(
                            str(value),
                            size=26,
                            color=t["TEXT"],
                            weight=ft.FontWeight.W_800,
                        )
                    ]
                ),
            ],
            spacing=8,
        ),
    )


def tech_banner(
    title: str,
    subtitle: str = "",
    icon: object = None,
    badge_text: str = "",
    colors: list[str] | None = None,
    pills: list[ft.Control] | None = None,
    page: ft.Page | None = None,
) -> ft.Container:
    """Minimalist Clean SaaS Page Header with ResponsiveRow KPI stat cards."""
    t = theme_tokens(page)
    title_col_items = [ft.Text(title, size=26, weight=ft.FontWeight.W_800, color=t["TEXT"])]
    if subtitle:
        title_col_items.append(ft.Text(subtitle, size=14, color=t["SECONDARY"]))

    badge_ctrl = None
    if badge_text and not pills:
        badge_ctrl = ft.Container(
            bgcolor=t["SURFACE"],
            border=ft.border.all(1, t["BORDER"]),
            padding=ft.padding.symmetric(horizontal=14, vertical=7),
            border_radius=20,
            content=ft.Row(
                [
                    ft.Container(width=8, height=8, bgcolor=PRIMARY, border_radius=4),
                    ft.Text(badge_text, size=13, color=t["TEXT"], weight=ft.FontWeight.W_600),
                ],
                spacing=6,
                tight=True,
            ),
        )

    top_row_controls: list[ft.Control] = [ft.Column(title_col_items, spacing=4, expand=True)]
    if badge_ctrl is not None:
        top_row_controls.append(badge_ctrl)

    banner_children: list[ft.Control] = [
        ft.Row(
            top_row_controls,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    ]

    if pills:
        lg_span = 3 if len(pills) >= 4 else 4
        for p_ctrl in pills:
            if isinstance(p_ctrl, ft.Container):
                p_ctrl.col = {"xs": 12, "sm": 6, "lg": lg_span}
        banner_children.append(
            ft.ResponsiveRow(
                controls=list(pills),
                run_spacing=16,
                spacing=16,
            )
        )

    return ft.Container(
        padding=ft.padding.only(bottom=4),
        content=ft.Column(banner_children, spacing=14, tight=True),
    )


def kpi_stat_card(
    title: str,
    value: str,
    subtitle: str,
    icon: object,
    accent: str = PRIMARY_DARK,
    soft_bg: str = "#ECFDF5",
    page: ft.Page | None = None,
    col: dict | None = None,
) -> ft.Container:
    """
    Thẻ KPI chuẩn ResponsiveRow (col={'xs': 12, 'sm': 6, 'lg': 3}, height=None, padding=16):
    Bên trong dùng ft.Column 3 hàng:
      - Hàng 1: Icon bên trái + Badge ngắn gọn bên phải
      - Hàng 2: Tiêu đề thẻ
      - Hàng 3: Con số thống kê lớn
    """
    t = theme_tokens(page)
    dark = is_dark_mode(page)
    box_bg = ft.Colors.with_opacity(0.22, accent) if dark else soft_bg
    card_inner = tech_card(
        page=page,
        padding=16,
        border_radius=16,
        hover_lift=True,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            width=44,
                            height=44,
                            bgcolor=box_bg,
                            border_radius=12,
                            alignment=ft.alignment.center,
                            content=ft.Icon(icon, color=accent, size=23),
                        ),
                        ft.Container(
                            bgcolor=box_bg,
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                            border_radius=12,
                            content=ft.Text(
                                str(subtitle),
                                size=12,
                                color=accent,
                                weight=ft.FontWeight.W_600,
                            ),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        ft.Text(
                            str(title),
                            size=14.5,
                            color=t["TEXT"],
                            weight=ft.FontWeight.W_700,
                            expand=True,
                        )
                    ]
                ),
                ft.Row(
                    [
                        ft.Text(
                            str(value),
                            size=26,
                            color=t["TEXT"],
                            weight=ft.FontWeight.W_800,
                        )
                    ]
                ),
            ],
            spacing=8,
        ),
    )
    card_inner.height = None
    return ft.Container(
        col=col or {"xs": 12, "sm": 6, "lg": 3},
        height=None,
        content=card_inner,
    )


def save_session_user(page: ft.Page, user: dict):
    """Save required user fields into page.session for RBAC route guards."""
    payload = {
        "user_id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "avatar_url": user.get("avatar_url", ""),
        "role": user["role"],
        "auth_provider": user.get("auth_provider", "google"),
        "google_sub": user.get("google_sub", ""),
    }
    for k, v in payload.items():
        session_set(page, k, v)
    session_set(page, "current_user", payload)
    return payload


def get_session_user(page: ft.Page) -> dict | None:
    user = session_get(page, "current_user")
    if not user:
        return None
    initialize()
    with conn() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (user["user_id"],)).fetchone()
        if not row or int(row["is_active"]) == 0:
            return None
        updated = {
            "user_id": row["id"],
            "email": row["email"],
            "full_name": row["full_name"],
            "avatar_url": row["avatar_url"],
            "role": row["role"],
            "auth_provider": row["auth_provider"],
            "google_sub": row["google_sub"],
        }
        session_set(page, "current_user", updated)
        session_set(page, "role", row["role"])
        return updated


def logout_user(page: ft.Page):
    mode = session_get(page, "theme_mode")
    session_clear(page)
    if mode:
        session_set(page, "theme_mode", mode)


def role_home_route(role: str) -> str:
    return ROLE_ROUTES.get(role, "/user")


def get_google_oauth_config() -> dict[str, str]:
    cfg = read_settings()
    return {
        "client_id": (cfg.get("GOOGLE_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID", "")).strip(),
        "client_secret": (cfg.get("GOOGLE_CLIENT_SECRET") or os.environ.get("GOOGLE_CLIENT_SECRET", "")).strip(),
        "redirect_uri": GOOGLE_REDIRECT_URI,
    }


def save_google_oauth_config(client_id: str, client_secret: str) -> None:
    save_settings({
        "GOOGLE_CLIENT_ID": client_id.strip(),
        "GOOGLE_CLIENT_SECRET": client_secret.strip(),
        "GOOGLE_REDIRECT_URI": GOOGLE_REDIRECT_URI,
    })


def is_real_oauth_configured() -> bool:
    cfg = get_google_oauth_config()
    return bool(cfg["client_id"] and cfg["client_secret"])


def build_google_oauth_provider():
    """Return configured ft.GoogleOAuthProvider instance."""
    cfg = get_google_oauth_config()
    return ft.GoogleOAuthProvider(
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        redirect_url=GOOGLE_REDIRECT_URI,
    )


def build_google_auth_url(client_id: str, redirect_uri: str = GOOGLE_REDIRECT_URI, state: str = "") -> str:
    params = {
        "client_id": client_id.strip(),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    if state:
        params["state"] = state
    return f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"


def exchange_code_for_tokens(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str = GOOGLE_REDIRECT_URI,
) -> dict:
    """Gọi POST tới https://oauth2.googleapis.com/token để đổi Authorization Code lấy access_token & id_token."""
    resp = requests.post(
        GOOGLE_TOKEN_ENDPOINT,
        data={
            "code": code,
            "client_id": client_id.strip(),
            "client_secret": client_secret.strip(),
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Google Token API ({resp.status_code}): {resp.text[:240]}")
    return resp.json()


def fetch_google_userinfo(access_token: str) -> dict:
    """Gọi GET tới https://www.googleapis.com/oauth2/v3/userinfo để lấy email, name, picture, sub thật."""
    resp = requests.get(
        GOOGLE_USERINFO_ENDPOINT,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Google UserInfo API ({resp.status_code}): {resp.text[:240]}")
    return resp.json()


def authenticate_local(identifier: str, password: str) -> dict:
    """Authenticate by email or username and password."""
    initialize()
    ident = (identifier or "").strip().lower()
    pw = (password or "").strip()
    if not ident or not pw:
        raise ValueError("Vui lòng nhập đầy đủ Email/Username và Mật khẩu.")
    pw_hash = _hash_password(pw)
    with conn() as c:
        row = c.execute(
            """SELECT * FROM users
            WHERE (LOWER(email)=? OR LOWER(username)=?) AND password_hash=?""",
            (ident, ident, pw_hash),
        ).fetchone()
    if not row:
        raise ValueError("Thông tin đăng nhập không chính xác (Mật khẩu mặc định tài khoản mẫu: 123456).")
    if int(row["is_active"]) == 0:
        raise ValueError("Tài khoản này đã bị Quản trị viên khóa.")
    return dict(row)


def authenticate_google(
    email: str,
    full_name: str | None = None,
    avatar_url: str | None = None,
    google_sub: str | None = None,
) -> dict:
    """Verify Google email in SQL Database or auto-provision/update account with real Google profile."""
    initialize()
    clean_email = (email or "").strip().lower()
    if not clean_email or "@" not in clean_email:
        raise ValueError("Vui lòng nhập địa chỉ email Google hợp lệ (ví dụ: tenban@gmail.com).")
    with conn() as c:
        clean_sub = (google_sub or "").strip()
        row = None
        if clean_sub:
            row = c.execute("SELECT * FROM users WHERE google_sub=?", (clean_sub,)).fetchone()
        if not row:
            row = c.execute("SELECT * FROM users WHERE LOWER(email)=?", (clean_email,)).fetchone()
        if not row:
            local_part = clean_email.split("@")[0]
            derived_name = (full_name or "").strip() or local_part.replace(".", " ").replace("_", " ").title()
            encoded_name = urllib.parse.quote(derived_name)
            derived_avatar = avatar_url or f"https://ui-avatars.com/api/?name={encoded_name}&background=059669&color=fff"
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur = c.execute(
                """INSERT INTO users
                (email, username, password_hash, full_name, avatar_url, google_sub, role, auth_provider, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'user', 'google', 1, ?)""",
                (
                    clean_email,
                    local_part,
                    _hash_password("123456"),
                    derived_name,
                    derived_avatar,
                    clean_sub,
                    now_str,
                ),
            )
            row = c.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
        else:
            new_name = (full_name or "").strip() or row["full_name"]
            stored_avatar = str(row["avatar_url"] or "").replace("\\", "/")
            new_avatar = (
                row["avatar_url"]
                if stored_avatar.startswith("profile_avatars/")
                else ((avatar_url or "").strip() or row["avatar_url"])
            )
            new_sub = clean_sub or row.get("google_sub", "")
            c.execute(
                """UPDATE users
                SET full_name=?, avatar_url=?, google_sub=?, auth_provider='google'
                WHERE id=?""",
                (new_name, new_avatar, new_sub, row["id"]),
            )
            row = c.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
    if int(row["is_active"]) == 0:
        raise ValueError("Tài khoản Google này đang bị khóa bởi Quản trị viên.")
    return dict(row)


class _ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True


def run_google_oauth_desktop_flow(timeout: int = 120) -> dict:
    """
    Luồng Google OAuth 2.0 Authorization Code Flow thực tế cho Desktop App:
    1. Khởi tạo Local HTTP Callback Server tạm thời tại http://127.0.0.1:8765/callback
    2. Mở trình duyệt tới https://accounts.google.com/o/oauth2/v2/auth?response_type=code&scope=openid%20email%20profile...
    3. Bắt tham số ?code=... trả về tại cổng local, gọi POST https://oauth2.googleapis.com/token đổi code lấy access_token & id_token
    4. Gọi https://www.googleapis.com/oauth2/v3/userinfo lấy email, name, picture, sub thật và lưu vào bảng Users trong SQL Database.
    """
    initialize()
    cfg = get_google_oauth_config()
    client_id = cfg["client_id"]
    client_secret = cfg["client_secret"]
    redirect_uri = GOOGLE_REDIRECT_URI

    if not client_id or not client_secret:
        return {
            "ok": False,
            "needs_credentials": True,
            "error": (
                "Chưa cấu hình GOOGLE_CLIENT_ID và GOOGLE_CLIENT_SECRET trong file .env. "
                "Hãy nhập Client ID & Client Secret để mở xác thực Google OAuth 2.0."
            ),
        }

    state_token = secrets.token_urlsafe(16)
    callback_data: dict[str, str] = {}
    done_event = threading.Event()

    class _OAuthCallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path not in ("/callback", "/"):
                self.send_response(404)
                self.end_headers()
                return

            qs = parse_qs(parsed.query)
            if "error" in qs:
                callback_data["error"] = qs["error"][0]
            if "code" in qs:
                callback_data["code"] = qs["code"][0]
            if "state" in qs:
                callback_data["state"] = qs["state"][0]

            ok = "code" in callback_data and "error" not in callback_data
            title = "Đăng nhập Google thành công!" if ok else "Đăng nhập Google thất bại"
            msg = (
                "Đã nhận Authorization Code & xác thực tài khoản thành công. Bạn có thể đóng tab trình duyệt này và quay lại ứng dụng PigSkinTech AI."
                if ok
                else f"Lỗi xác thực từ Google: {callback_data.get('error', 'Không nhận được Authorization Code.')}"
            )
            color = "#10B981" if ok else "#EF4444"
            html_resp = f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8"><title>{title}</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: #0F172A; color: #F8FAFC; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
  .card {{ background: #1E293B; border: 1px solid #334155; border-radius: 16px; padding: 32px; max-width: 440px; text-align: center; box-shadow: 0 12px 30px rgba(0,0,0,0.4); }}
  .badge {{ width: 52px; height: 52px; border-radius: 99px; background: {color}; color: white; font-size: 26px; line-height: 52px; margin: 0 auto 14px auto; font-weight: bold; }}
</style></head>
<body><div class="card"><div class="badge">{'✓' if ok else '!'}</div><h2>{title}</h2><p style="color:#CBD5E1;font-size:14px;">{msg}</p></div>
<script>setTimeout(function(){{ window.close(); }}, 2500);</script></body></html>"""
            body_bytes = html_resp.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)
            done_event.set()

    try:
        server = _ReusableHTTPServer((GOOGLE_CALLBACK_HOST, GOOGLE_CALLBACK_PORT), _OAuthCallbackHandler)
    except OSError as exc:
        return {"ok": False, "error": f"Không thể mở cổng callback {redirect_uri}: {exc}"}

    server.timeout = 1.0

    def _serve():
        deadline = time.time() + timeout
        while not done_event.is_set() and time.time() < deadline:
            server.handle_request()
        try:
            server.server_close()
        except Exception:
            pass

    threading.Thread(target=_serve, daemon=True).start()
    auth_url = build_google_auth_url(client_id=client_id, redirect_uri=redirect_uri, state=state_token)
    webbrowser.open(auth_url)

    finished = done_event.wait(timeout=timeout)
    try:
        server.server_close()
    except Exception:
        pass

    if not finished:
        return {"ok": False, "error": "Hết thời gian chờ đăng nhập Google trên trình duyệt (120 giây)."}
    if "error" in callback_data:
        return {"ok": False, "error": f"Google OAuth trả về lỗi: {callback_data['error']}"}

    code = callback_data.get("code", "").strip()
    if not code:
        return {"ok": False, "error": "Không nhận được Authorization Code (?code=...) tại cổng callback."}

    try:
        tokens = exchange_code_for_tokens(code, client_id, client_secret, redirect_uri)
        access_token = tokens.get("access_token", "")
        if not access_token:
            return {"ok": False, "error": "Google Token API không trả về access_token hợp lệ."}
        userinfo = fetch_google_userinfo(access_token)
        email = (userinfo.get("email") or "").strip().lower()
        if not email:
            return {"ok": False, "error": "Tài khoản Google không cung cấp địa chỉ email."}
        user_record = authenticate_google(
            email=email,
            full_name=userinfo.get("name") or "",
            avatar_url=userinfo.get("picture") or "",
            google_sub=userinfo.get("sub") or "",
        )
        return {"ok": True, "user": user_record, "profile": userinfo}
    except Exception as exc:
        return {"ok": False, "error": f"Lỗi xác thực Google OAuth 2.0: {exc}"}


# --- Shared Flet UI compatibility helpers ---

def open_dialog(page: ft.Page, dialog: ft.AlertDialog):
    if hasattr(page, "show_dialog"):
        if dialog in getattr(page, "_dialogs", ft.Row()).controls:
            dialog.open = True
            page.update()
        else:
            page.show_dialog(dialog)
    elif hasattr(page, "open"):
        page.open(dialog)
    else:
        page.dialog = dialog
        dialog.open = True
        page.update()


def close_dialog(page: ft.Page, dialog: ft.AlertDialog | None = None):
    if hasattr(page, "pop_dialog"):
        page.pop_dialog()
    elif hasattr(page, "close") and dialog is not None:
        page.close(dialog)
    elif dialog is not None:
        dialog.open = False
        page.update()


def show_snack(page: ft.Page, message: str, bgcolor: str = "#059669"):
    snack = ft.SnackBar(content=ft.Text(message, color="#FFFFFF", weight=ft.FontWeight.W_500), bgcolor=bgcolor)
    if hasattr(page, "show_dialog"):
        page.show_dialog(snack)
    elif hasattr(page, "open"):
        page.open(snack)
    else:
        page.snack_bar = snack
        page.snack_bar.open = True
        page.update()


def make_dropdown(
    label: str,
    value: str,
    options: list[tuple[str, str]],
    on_change=None,
    width: int | None = None,
    expand: bool = False,
    content_padding=None,
    page: ft.Page | None = None,
):
    return css_dropdown(
        label=label,
        value=value,
        options=options,
        on_change=on_change,
        width=width,
        expand=expand,
        content_padding=content_padding,
        page=page,
    )


def make_image(path_or_bytes, width: int = 88, height: int = 88, border_radius: int = 10, fit=None):
    ensure_flet_compat()
    params = inspect.signature(ft.Image.__init__).parameters
    fit_val = fit if fit is not None else getattr(ft.ImageFit, "COVER", None)
    if isinstance(path_or_bytes, (str, Path)):
        p = Path(path_or_bytes)
        if p.is_file():
            if "src_base64" in params:
                b64 = base64.b64encode(p.read_bytes()).decode("ascii")
                return ft.Image(src_base64=b64, fit=fit_val, width=width, height=height, border_radius=border_radius)
            return ft.Image(src=str(p.resolve()), fit=fit_val, width=width, height=height, border_radius=border_radius)
    elif isinstance(path_or_bytes, (bytes, bytearray)) and path_or_bytes:
        raw_bytes = bytes(path_or_bytes)
        if "src_base64" in params:
            b64 = base64.b64encode(raw_bytes).decode("ascii")
            return ft.Image(src_base64=b64, fit=fit_val, width=width, height=height, border_radius=border_radius)
        return ft.Image(src=raw_bytes, fit=fit_val, width=width, height=height, border_radius=border_radius)
    return ft.Container(
        width=width,
        height=height,
        bgcolor="#F1F5F9",
        border_radius=border_radius,
        alignment=ft.alignment.center,
        content=ft.Icon(ft.Icons.IMAGE_NOT_SUPPORTED_OUTLINED, size=28, color="#64748B"),
    )


def open_image_zoom_dialog(page: ft.Page, image_path: str, title: str = "Xem chi tiết ảnh bệnh án"):
    p = Path(image_path or "")
    if not p.is_file():
        show_snack(page, "Không tìm thấy file ảnh gốc trên thiết bị.", "#DC2626")
        return
    dlg = ft.AlertDialog(modal=True)
    dlg.title = ft.Row(
        [
            ft.Icon(ft.Icons.ZOOM_IN_ROUNDED, color="#059669"),
            ft.Text(title, size=16, weight=ft.FontWeight.BOLD, expand=True),
        ],
        spacing=8,
    )
    dlg.content = ft.Container(
        width=680,
        height=460,
        bgcolor="#0F172A",
        border_radius=12,
        padding=8,
        alignment=ft.alignment.center,
        content=make_image(p, width=660, height=440, border_radius=8, fit=getattr(ft.ImageFit, "CONTAIN", None)),
    )
    dlg.actions = [
        ft.FilledButton("Đóng cửa sổ", icon=ft.Icons.CLOSE_ROUNDED, on_click=lambda e: close_dialog(page, dlg))
    ]
    open_dialog(page, dlg)


def preview_thumbnail_with_zoom(
    page: ft.Page, image_path: str, title: str, width: int = 88, height: int = 88, border_radius: int = 10
) -> ft.Control:
    """Modern rounded 88x88 real pig skin image preview frame with corner zoom button overlay."""
    return ft.Container(
        width=width,
        height=height,
        border_radius=border_radius,
        border=ft.border.all(1.5, "#CBD5E1"),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        ink=True,
        tooltip="Nhấn để phóng to (Zoom) xem rõ vết bệnh",
        on_click=lambda e: open_image_zoom_dialog(page, image_path, title),
        content=ft.Stack(
            width=width,
            height=height,
            controls=[
                make_image(image_path, width=width, height=height, border_radius=border_radius, fit=ft.ImageFit.COVER),
                ft.Container(
                    right=4,
                    bottom=4,
                    width=24,
                    height=24,
                    bgcolor=ft.Colors.with_opacity(0.78, "#0F172A"),
                    border_radius=7,
                    alignment=ft.alignment.center,
                    content=ft.Icon(ft.Icons.ZOOM_IN_ROUNDED, size=15, color="#34D399"),
                ),
            ],
        ),
    )


def create_file_picker(page: ft.Page) -> ft.FilePicker:
    picker = ft.FilePicker()
    if hasattr(page, "services"):
        if picker not in page.services:
            page.services.append(picker)
    elif hasattr(page, "overlay"):
        if picker not in page.overlay:
            page.overlay.append(picker)
    return picker


async def pick_image_files(picker: ft.FilePicker, allow_multiple: bool, on_picked):
    """Cross-version FilePicker helper supporting Flet 0.28 callback and Flet 1.0 coroutine."""
    exts = ["jpg", "jpeg", "png", "webp"]
    if inspect.iscoroutinefunction(picker.pick_files):
        files = await picker.pick_files(
            allow_multiple=allow_multiple,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=exts,
        )
        paths = [f.path for f in (files or []) if getattr(f, "path", None)]
        if paths:
            res = on_picked(paths)
            if inspect.iscoroutine(res):
                await res
    else:
        def _cb(e):
            paths = [f.path for f in (e.files or []) if getattr(f, "path", None)]
            if paths:
                on_picked(paths)
        picker.on_result = _cb
        picker.pick_files(
            allow_multiple=allow_multiple,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=exts,
        )


def generate_lesion_heatmap(image_path: str) -> str:
    """
    Generate an AI Lesion Contrast & Thermal Heatmap overlay from the original pig skin image
    using PIL, save to PigSkinTech/case_images/heatmap_cache/, and return its path.
    """
    src_path = Path(image_path or "")
    if not src_path.is_file():
        return str(image_path or "")

    cache_dir = Path(__file__).resolve().parent.parent / "case_images" / "heatmap_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / f"heatmap_{src_path.stem}.jpg"

    try:
        with Image.open(src_path) as raw:
            rgb = raw.convert("RGB")
            w, h = rgb.size
            contrast_img = ImageEnhance.Contrast(rgb).enhance(2.05)
            contrast_img = ImageEnhance.Sharpness(contrast_img).enhance(1.85)

            r_ch, g_ch, b_ch = rgb.split()
            # Erythema / inflammation index emphasizing reddish & warm skin lesions
            erythema = Image.eval(
                Image.merge(
                    "RGB",
                    (
                        r_ch,
                        g_ch,
                        b_ch,
                    ),
                ).convert("L"),
                lambda x: x,
            )
            r_bytes = r_ch.tobytes()
            g_bytes = g_ch.tobytes()
            b_bytes = b_ch.tobytes()
            heat_vals = bytearray(len(r_bytes))
            for i in range(len(r_bytes)):
                score = int(r_bytes[i] * 1.45 - 0.55 * g_bytes[i] - 0.45 * b_bytes[i]) + 60
                heat_vals[i] = 255 if score > 255 else (0 if score < 0 else score)
            erythema = Image.frombytes("L", (w, h), bytes(heat_vals))
            erythema = ImageOps.autocontrast(erythema, cutoff=2)

            thermal = ImageOps.colorize(
                erythema,
                black="#0F172A",
                mid="#F59E0B",
                white="#EF4444",
            )
            blended = Image.blend(contrast_img, thermal, alpha=0.46)

            draw = ImageDraw.Draw(blended)
            pad_x, pad_y = int(w * 0.14), int(h * 0.14)
            box = (pad_x, pad_y, w - pad_x, h - pad_y)
            corner = max(18, min(w, h) // 10)
            col = (52, 211, 153)
            # Corner brackets for AI lesion focus
            for x0, y0, dx, dy in (
                (box[0], box[1], 1, 1),
                (box[2], box[1], -1, 1),
                (box[0], box[3], 1, -1),
                (box[2], box[3], -1, -1),
            ):
                draw.line([(x0, y0), (x0 + dx * corner, y0)], fill=col, width=3)
                draw.line([(x0, y0), (x0, y0 + dy * corner)], fill=col, width=3)

            blended.save(out_path, format="JPEG", quality=92)
        return str(out_path.resolve())
    except Exception:
        return str(src_path.resolve())


def build_outbreak_alert_banner(records: list[dict], page: ft.Page | None = None) -> ft.Control | None:
    """
    Check the 10 most recent inspections: if >= 2 belong to 'Cao' or 'Khẩn cấp' danger level,
    return an Epidemic Outbreak Warning Banner.
    """
    recent_10 = (records or [])[:10]
    urgent_cases = []
    for r in recent_10:
        cls_code = r.get("expert_label") or r.get("predicted_class") or ""
        info = get_class_info(cls_code)
        danger = info.get("danger_level", "Trung bình")
        if danger in ("Cao", "Khẩn cấp"):
            urgent_cases.append((r, display_class(cls_code), danger))

    if len(urgent_cases) < 2:
        return None

    pal = get_theme_palette(page)
    dark = pal["IS_DARK"]
    diseases_set = list(dict.fromkeys(d_name for _, d_name, _ in urgent_cases))
    farms_set = list(dict.fromkeys((r.get("farm_name") or "Khu chuồng") for r, _, _ in urgent_cases))

    return ft.Container(
        padding=ft.padding.symmetric(horizontal=20, vertical=14),
        border_radius=14,
        bgcolor=pal["SOFT_RED"],
        border=ft.border.all(1.5, "#F87171" if dark else "#FCA5A5"),
        animate=make_smooth_animation(220),
        content=ft.Row(
            [
                ft.Container(
                    width=44,
                    height=44,
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.18, "#EF4444"),
                    alignment=ft.alignment.center,
                    content=ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color="#F87171" if dark else "#DC2626", size=26),
                ),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    f"🚨 Cảnh báo Dịch tễ Sớm: Phát hiện {len(urgent_cases)}/10 ca khám gần nhất thuộc nhóm Nguy hiểm cao",
                                    size=15,
                                    weight=ft.FontWeight.BOLD,
                                    color="#FCA5A5" if dark else "#991B1B",
                                    expand=True,
                                ),
                                ft.Container(
                                    bgcolor="#DC2626",
                                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                                    border_radius=12,
                                    content=ft.Text(
                                        "CẦN CÁCH LY & SÁT TRÙNG",
                                        size=12.5,
                                        weight=ft.FontWeight.BOLD,
                                        color="#FFFFFF",
                                    ),
                                ),
                            ],
                            spacing=8,
                        ),
                        ft.Text(
                            f"Bệnh lý ghi nhận: {', '.join(diseases_set[:3])} • Khu vực: {', '.join(farms_set[:3])}. "
                            "Khuyến nghị: Tách đàn cách ly ngay các cá thể nghi nhiễm, phun sát trùng chuồng trại và kiểm tra thân nhiệt toàn đàn.",
                            size=13.5,
                            color="#FECACA" if dark else "#7F1D1D",
                        ),
                    ],
                    spacing=4,
                    expand=True,
                ),
            ],
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _img_to_data_uri(img_path: str | None) -> str:
    if not img_path:
        return ""
    p = Path(img_path)
    if not p.is_file():
        return ""
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{b64}"


def _build_inline_svg_barcode(case_id: str) -> str:
    """Generate a compact deterministic inline SVG QR + Barcode graphic for the veterinary report header."""
    seed_bytes = hashlib.md5(case_id.encode("utf-8")).digest()
    bars = []
    x = 4
    for idx, b in enumerate(seed_bytes[:14]):
        w = 2 if (b % 3 == 0) else (3 if (b % 2 == 0) else 1.5)
        bars.append(f'<rect x="{x:.1f}" y="4" width="{w}" height="24" rx="0.5" fill="#0F172A"/>')
        x += w + (1.5 if idx % 2 == 0 else 2.0)
    return (
        f'<svg width="{int(x + 4)}" height="32" viewBox="0 0 {int(x + 4)} 32" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block;background:#F8FAFC;border:1px solid #CBD5E1;border-radius:6px;">'
        + "".join(bars)
        + "</svg>"
    )


def export_vet_report_html(page: ft.Page, case_data: dict, open_browser: bool = True) -> str:
    """
    Export a styled 1-Page A4 Veterinary Clinical Diagnostic Report HTML file into PigSkinTech/exports/
    and open it in the browser for instant viewing or Ctrl+P PDF printing (without file:/// URLs).
    """
    exports_dir = Path(__file__).resolve().parent.parent / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    case_id = str(case_data.get("case_id") or f"PS-{int(case_data.get('record_id') or 1):06d}")
    ts_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = exports_dir / f"PhieuKham_{case_id}_{ts_slug}.html"

    img_path = case_data.get("image_path") or ""
    orig_uri = _img_to_data_uri(img_path)
    heat_path = generate_lesion_heatmap(img_path) if img_path else ""
    heat_uri = _img_to_data_uri(heat_path)

    raw_disease = case_data.get("disease_name") or (
        display_class(case_data.get("predicted_class")) if case_data.get("predicted_class") else "Chưa xác định"
    )
    disease_name = html.escape(str(raw_disease))
    danger_level = html.escape(str(case_data.get("danger_level") or "Trung bình"))
    confidence_pct = float(case_data.get("confidence") or 0.0) * 100.0
    animal_id = html.escape(str(case_data.get("animal_id") or "PIG-101"))
    farm_name = html.escape(str(case_data.get("farm_name") or "Trang trại chăn nuôi"))
    user_name = html.escape(str(case_data.get("user_name") or "Người chăn nuôi"))
    symptoms = html.escape(str(case_data.get("symptoms") or "Không có ghi chú triệu chứng"))
    isolation = html.escape(str(case_data.get("isolation_guide") or "Cách ly cá thể nghi nhiễm và sát trùng chuồng trại."))
    treatment = html.escape(str(case_data.get("treatment_guide") or "Tham khảo phác đồ Bác sĩ Thú y."))
    expert_note = html.escape(str(case_data.get("expert_note") or "Đang chờ hoặc theo phác đồ khuyến nghị chuẩn."))
    reviewed_by = html.escape(str(case_data.get("reviewed_by") or "Hệ thống Trí tuệ nhân tạo PigSkin AI & BS. Thú y"))
    created_at = html.escape(str(case_data.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    svg_barcode = _build_inline_svg_barcode(case_id)

    raw_scores = case_data.get("scores") or []
    if isinstance(raw_scores, dict):
        scores = [
            {"label": k, "confidence": float(v or 0.0)}
            for k, v in sorted(raw_scores.items(), key=lambda item: float(item[1] or 0.0), reverse=True)
        ]
    elif isinstance(raw_scores, list):
        scores = raw_scores
    else:
        scores = []
    scores_html = ""
    for idx, sc in enumerate(scores[:3], start=1):
        lbl = html.escape(display_class(sc.get("label") or sc.get("class") or ""))
        pct = float(sc.get("confidence") or 0.0) * 100.0
        bar_col = "#059669" if idx == 1 else ("#0284C7" if idx == 2 else "#D97706")
        scores_html += f"""
        <div style="margin-bottom:6px;">
          <div style="display:flex;justify-content:space-between;font-size:12.5px;font-weight:600;margin-bottom:2px;">
            <span>#{idx}. {lbl}</span>
            <span style="color:{bar_col};">{pct:.1f}%</span>
          </div>
          <div style="height:7px;background:#E2E8F0;border-radius:4px;overflow:hidden;">
            <div style="width:{min(100.0, max(2.0, pct)):.1f}%;height:100%;background:{bar_col};"></div>
          </div>
        </div>
        """
    if not scores_html:
        scores_html = f"""
        <div style="font-size:13px;font-weight:600;color:#059669;">
          Kết quả dự đoán chính: {disease_name} ({confidence_pct:.1f}%)
        </div>
        """

    if orig_uri:
        images_html = f"""
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <div style="border:1px solid #E2E8F0;border-radius:10px;padding:8px;text-align:center;background:#F8FAFC;">
            <div style="font-weight:700;font-size:11.5px;color:#475569;margin-bottom:5px;">Ảnh gốc tại chuồng</div>
            <img src="{orig_uri}" style="width:100%;height:135px;object-fit:cover;border-radius:8px;display:block;" />
          </div>
          <div style="border:1px solid #E2E8F0;border-radius:10px;padding:8px;text-align:center;background:#F8FAFC;">
            <div style="font-weight:700;font-size:11.5px;color:#059669;margin-bottom:5px;">Ảnh soi vùng tổn thương AI</div>
            <img src="{heat_uri or orig_uri}" style="width:100%;height:135px;object-fit:cover;border-radius:8px;display:block;" />
          </div>
        </div>
        """
    else:
        images_html = """
        <div style="border:1px dashed #CBD5E1;border-radius:10px;height:155px;display:flex;align-items:center;justify-content:center;color:#64748B;font-size:12px;">
          Không có hình ảnh đính kèm
        </div>
        """

    html_doc = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <title>Phiếu Kết Quả Chẩn Đoán Thú Y - {case_id}</title>
  <style>
    @page {{
        size: A4 portrait;
        margin: 0mm !important; /* CỰC KỲ QUAN TRỌNG: Ép margin = 0 ở @page để trình duyệt Chrome/Edge tự động ẩn hoàn toàn đường dẫn ổ đĩa file:///C:/... ở chân trang và ngày giờ ở đầu trang */
    }}
    html, body {{
        width: 210mm;
        height: 296mm;
        margin: 0 auto !important;
        padding: 0 !important;
        overflow: hidden;
        background: #FFFFFF;
        color: #0F172A;
        font-family: 'Plus Jakarta Sans', 'Segoe UI', sans-serif;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
    }}
    .a4-sheet {{
        box-sizing: border-box;
        width: 210mm;
        height: 296mm;
        max-height: 296mm;
        padding: 12mm 14mm; /* Dùng padding của khung .a4-sheet thay cho margin của @page */
        page-break-after: avoid;
        page-break-inside: avoid;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        background: #FFFFFF;
    }}
    .header-bar {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 2px solid #10B981;
        padding-bottom: 10px;
    }}
    .brand-row {{
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .logo-box {{
        width: 38px;
        height: 38px;
        border-radius: 10px;
        background: linear-gradient(135deg, #10B981, #059669);
        color: #FFFFFF;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-size: 18px;
    }}
    .info-image-row {{
        display: grid;
        grid-template-columns: 45% 53%;
        gap: 2%;
        align-items: stretch;
    }}
    .info-table {{
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 10px 12px;
        font-size: 12.5px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }}
    .info-line {{
        margin-bottom: 5px;
        line-height: 1.4;
    }}
    .ai-box {{
        background: #ECFDF5;
        border: 1px solid #A7F3D0;
        border-radius: 10px;
        padding: 10px 14px;
    }}
    .protocol-grid {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
    }}
    .protocol-card {{
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 10px 12px;
        background: #FFFFFF;
    }}
    .footer-sign {{
        border: 1px solid #CBD5E1;
        background: #F8FAFC;
        border-radius: 10px;
        padding: 10px 14px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 14px;
    }}
    .print-toolbar {{
        position: fixed;
        top: 12px;
        right: 16px;
        z-index: 999;
    }}
    .print-btn {{
        background: #059669;
        color: #FFFFFF;
        border: none;
        padding: 9px 16px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 13px;
        cursor: pointer;
        box-shadow: 0 4px 14px rgba(5, 150, 105, 0.3);
    }}
    @media print {{
        .no-print {{ display: none !important; }}
    }}
  </style>
</head>
<body>
  <div class="no-print print-toolbar">
    <button class="print-btn" onclick="window.print()">🖨️ In Phiếu A4 / Lưu PDF (Ctrl + P)</button>
  </div>

  <div class="a4-sheet">
    <!-- 1. HEADER -->
    <div class="header-bar">
      <div class="brand-row">
        <div class="logo-box">🐖</div>
        <div>
          <div style="font-size:11px;font-weight:800;color:#059669;letter-spacing:0.8px;">HỆ THỐNG CHẨN ĐOÁN THÚ Y THÔNG MINH</div>
          <div style="font-size:16px;font-weight:800;color:#0F172A;margin-top:2px;">PIGSKINTECH AI — PHIẾU KẾT QUẢ CHẨN ĐOÁN THÚ Y</div>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:10px;text-align:right;">
        <div>
          <div style="font-size:12.5px;font-weight:800;color:#059669;">Mã hồ sơ: {case_id}</div>
          <div style="font-size:11px;color:#64748B;margin-top:2px;">Thời gian: {created_at}</div>
        </div>
        {svg_barcode}
      </div>
    </div>

    <!-- 2. THÔNG TIN & HÌNH ẢNH (45% / 55%) -->
    <div class="info-image-row">
      <div class="info-table">
        <div>
          <div style="font-size:12px;font-weight:800;color:#0F172A;text-transform:uppercase;margin-bottom:6px;border-bottom:1px solid #E2E8F0;padding-bottom:4px;">
            📋 Thông tin Hồ sơ &amp; Lâm sàng
          </div>
          <div class="info-line"><strong>Chủ trại / Người gửi:</strong> {user_name}</div>
          <div class="info-line"><strong>Khu chuồng / Cơ sở:</strong> {farm_name}</div>
          <div class="info-line"><strong>Mã cá thể / Đàn:</strong> {animal_id}</div>
          <div class="info-line"><strong>Mức cảnh báo:</strong> <span style="color:#DC2626;font-weight:700;">{danger_level}</span></div>
          <div class="info-line" style="margin-bottom:0;"><strong>Triệu chứng lâm sàng:</strong> {symptoms}</div>
        </div>
      </div>
      <div>
        {images_html}
      </div>
    </div>

    <!-- 3. KẾT LUẬN AI & TOP-3 KHẢ NĂNG -->
    <div class="ai-box">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <div>
          <div style="font-size:11px;color:#065F46;font-weight:800;letter-spacing:0.5px;">KẾT LUẬN CHẨN ĐOÁN TỪ TRÍ TUỆ NHÂN TẠO PIGSKIN AI</div>
          <div style="font-size:18px;font-weight:800;color:#059669;margin-top:2px;">{disease_name}</div>
        </div>
        <div style="background:#059669;color:#FFFFFF;padding:5px 12px;border-radius:16px;font-size:13px;font-weight:800;">
          Độ tin cậy: {confidence_pct:.1f}%
        </div>
      </div>
      {scores_html}
    </div>

    <!-- 4. PHÁC ĐỒ 2 CỘT NGANG -->
    <div class="protocol-grid">
      <div class="protocol-card">
        <div style="font-size:13px;font-weight:800;color:#0369A1;margin-bottom:6px;">🛡️ Biện pháp Cách ly &amp; An toàn Sinh học</div>
        <div style="font-size:12.5px;line-height:1.48;color:#1E293B;">{isolation}</div>
      </div>
      <div class="protocol-card">
        <div style="font-size:13px;font-weight:800;color:#059669;margin-bottom:6px;">💊 Phác đồ Điều trị &amp; Thuốc Thú y Tham khảo</div>
        <div style="font-size:12.5px;line-height:1.48;color:#1E293B;">{treatment}</div>
      </div>
    </div>

    <!-- 5. NHẬN XÉT BÁC SĨ THÚ Y & CHỮ KÝ SỐ Ở ĐÁY TRANG A4 -->
    <div class="footer-sign">
      <div style="flex:1;">
        <div style="font-size:12.5px;font-weight:800;color:#0F172A;margin-bottom:4px;">
          👨‍⚕️ Nhận xét &amp; Thẩm định của Bác sĩ Thú y ({reviewed_by})
        </div>
        <div style="font-size:12px;line-height:1.45;color:#334155;">{expert_note}</div>
      </div>
      <div style="min-width:165px;text-align:center;border-left:1px dashed #CBD5E1;padding-left:14px;">
        <div style="font-size:10.5px;font-weight:700;color:#64748B;">XÁC THỰC CHỮ KÝ SỐ</div>
        <div style="margin:4px auto;display:inline-block;padding:3px 10px;border:1.5px solid #059669;border-radius:6px;color:#059669;font-size:11px;font-weight:800;">
          ✓ PIGSKINTECH VERIFIED
        </div>
        <div style="font-size:10.5px;color:#475569;font-weight:600;">{created_at[:10]}</div>
      </div>
    </div>
  </div>
</body>
</html>
"""
    out_file.write_text(html_doc, encoding="utf-8")
    resolved = str(out_file.resolve())
    if open_browser:
        try:
            webbrowser.open(out_file.resolve().as_uri())
        except Exception:
            pass
    show_snack(page, f"Đã xuất Phiếu Khám Thú Y chuẩn 1 trang A4 ({case_id})!", "#059669")
    return resolved


def export_inspections_csv(
    page: ft.Page,
    records: list[dict] | None = None,
    filename_prefix: str = "BaoCao_HoSoBenhAn",
) -> str:
    """Export inspection records to a UTF-8-SIG CSV file in PigSkinTech/exports/ for Excel."""
    exports_dir = Path(__file__).resolve().parent.parent / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    rows = records if records is not None else recent("")
    ts_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = exports_dir / f"{filename_prefix}_{ts_slug}.csv"

    fieldnames = [
        "Mã Hồ Sơ",
        "Ngày Khám",
        "Người Chăn Nuôi",
        "Email",
        "Trang Trại / Khu Chuồng",
        "Mã Đàn / Cá Thể",
        "Triệu Chứng",
        "AI Dự Đoán",
        "Độ Tin Cậy AI (%)",
        "Trạng Thái Thẩm Định",
        "Nhãn Chuẩn Chuyên Gia",
        "Bác Sĩ Thú Y Duyệt",
        "Phác Đồ / Ghi Chú Chuyên Gia",
        "Đưa Vào Dataset Chuẩn",
    ]

    with out_file.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            conf_pct = round(float(r.get("confidence") or 0.0) * 100.0, 1)
            pred_cls = r.get("predicted_class") or ""
            exp_cls = r.get("expert_label") or ""
            writer.writerow(
                {
                    "Mã Hồ Sơ": r.get("case_id") or f"PS-{int(r.get('id') or 0):06d}",
                    "Ngày Khám": r.get("created_at") or "",
                    "Người Chăn Nuôi": r.get("user_name") or "",
                    "Email": r.get("user_email") or "",
                    "Trang Trại / Khu Chuồng": r.get("farm_name") or "",
                    "Mã Đàn / Cá Thể": r.get("animal_id") or "",
                    "Triệu Chứng": r.get("symptoms") or "",
                    "AI Dự Đoán": f"{display_class(pred_cls)} ({pred_cls})" if pred_cls else "",
                    "Độ Tin Cậy AI (%)": f"{conf_pct:.1f}",
                    "Trạng Thái Thẩm Định": (
                        "Đã thẩm định" if r.get("review_status") == "reviewed"
                        else "Chờ duyệt" if r.get("requested_review") else "Chưa gửi"
                    ),
                    "Nhãn Chuẩn Chuyên Gia": f"{display_class(exp_cls)} ({exp_cls})" if exp_cls else "",
                    "Bác Sĩ Thú Y Duyệt": r.get("reviewed_by") or "",
                    "Phác Đồ / Ghi Chú Chuyên Gia": r.get("expert_note") or r.get("recommendation") or "",
                    "Đưa Vào Dataset Chuẩn": "Có" if int(r.get("in_dataset") or 0) == 1 else "Chưa",
                }
            )

    show_snack(page, f"Đã xuất {len(rows)} hồ sơ ra file Excel CSV: exports/{out_file.name}", "#059669")
    return str(out_file.resolve())


def build_role_shell(
    page: ft.Page,
    user: dict,
    title: str,
    destinations: list[tuple[str, object, object]],
    tab_builders: list,
    initial_index: int = 0,
    external_nav_ref: dict | None = None,
) -> ft.Control:
    """
    Build Clean SaaS Global Shell without top AppBar:
    Consolidates User Profile, Role Badge, Dark Mode & Logout into the 270px Left Sidebar.
    Wraps tab content in an animated opacity container for smooth tab transitions.
    """
    ensure_flet_compat(page)
    set_theme_page_context(page)
    t = theme_tokens(page)
    page.bgcolor = t["BG"]
    page.appbar = None

    # Profile and account security are shared across all three role workspaces.
    from views.profile_view import build_profile_view

    destinations = [
        *destinations,
        ("Hồ sơ cá nhân", ft.Icons.ACCOUNT_CIRCLE_OUTLINED, ft.Icons.ACCOUNT_CIRCLE_ROUNDED),
    ]
    tab_builders = [*tab_builders, lambda: build_profile_view(page, user)]

    route_key = f"active_tab_{getattr(page, 'route', '') or title}"
    saved_idx = session_get(page, route_key)
    start_index = saved_idx if isinstance(saved_idx, int) and 0 <= saved_idx < len(tab_builders) else initial_index

    tab_anim_wrapper = ft.Container(
        expand=True,
        opacity=1.0,
        animate_opacity=make_smooth_animation(220),
        content=ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=20),
    )

    body_host = ft.Container(
        expand=True,
        padding=24,
        bgcolor=t["BG"],
        content=tab_anim_wrapper,
    )

    active_state = {"index": start_index}
    menu_items_controls: list[ft.Container] = []

    def style_menu_item(item_container: ft.Container, idx: int, is_hovered: bool = False):
        t = theme_tokens(page)
        is_active = idx == active_state["index"]
        indicator: ft.Container = item_container.data["indicator"]
        icon_ctrl: ft.Icon = item_container.data["icon_ctrl"]
        label_ctrl: ft.Text = item_container.data["label_ctrl"]
        icon_normal, icon_selected = item_container.data["icons"]

        indicator.bgcolor = "#34D399" if is_active else "transparent"
        icon_ctrl.icon = icon_selected if is_active else icon_normal
        icon_ctrl.color = "#34D399" if is_active else ("#E2E8F0" if is_hovered else t["SIDEBAR_TEXT"])
        label_ctrl.color = t["SIDEBAR_ACTIVE_TEXT"] if (is_active or is_hovered) else t["SIDEBAR_TEXT"]
        label_ctrl.weight = ft.FontWeight.BOLD if is_active else ft.FontWeight.W_500

        if is_active:
            item_container.gradient = ft.LinearGradient(
                begin=ft.alignment.center_left,
                end=ft.alignment.center_right,
                colors=[ft.Colors.with_opacity(0.24, "#10B981"), ft.Colors.with_opacity(0.04, "#059669")],
            )
            item_container.bgcolor = None
        else:
            item_container.gradient = None
            item_container.bgcolor = t["SIDEBAR_HOVER"] if is_hovered else "transparent"

    from services.chat_widget import build_chat_overlay
    from services.chatbot_service import refresh_all_chat_views

    chat_overlay_ctrl = build_chat_overlay(page=page, user=user)

    def switch_tab(idx: int):
        active_state["index"] = idx
        session_set(page, route_key, idx)
        set_theme_page_context(page)
        for i, ctrl in enumerate(menu_items_controls):
            style_menu_item(ctrl, i, is_hovered=False)

        dest_label = destinations[idx][0] if 0 <= idx < len(destinations) else ""
        is_chatbot_tab = any(k in dest_label.lower() for k in ("chatbot", "trợ lý ai"))

        controls = tab_builders[idx]()
        body_host.bgcolor = theme_tokens(page)["BG"]
        tab_anim_wrapper.opacity = 1.0
        raw_controls = controls if isinstance(controls, list) else [controls]
        tab_anim_wrapper.content = ft.Column(
            controls=[*raw_controls, ft.Container(padding=ft.padding.only(bottom=90))],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=20,
        )
        apply_theme_text_contrast(body_host, _rgb_color(page.bgcolor), get_theme_palette(page))

        # Ẩn nút Floating Chat & đóng Popup khi đang mở Tab Chatbot chính; hiện lại ở các tab khác
        if isinstance(getattr(page, "data", None), dict):
            vis_fn = page.data.get("set_floating_chat_visible")
            if callable(vis_fn):
                vis_fn(not is_chatbot_tab)
        if is_chatbot_tab:
            refresh_all_chat_views(page)
        page.update()

    if external_nav_ref is not None:
        external_nav_ref["switch_tab"] = switch_tab

    custom_sidebar = build_sidebar(
        page=page,
        destinations=destinations,
        active_state=active_state,
        on_select_tab=switch_tab,
        menu_items_controls=menu_items_controls,
        style_menu_item=style_menu_item,
        user=user,
    )

    switch_tab(start_index)

    main_row = ft.Row(
        [
            custom_sidebar,
            body_host,
        ],
        expand=True,
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
    )
    shell = ft.Stack(
        expand=True,
        controls=[
            main_row,
            chat_overlay_ctrl,
        ],
    )
    apply_theme_text_contrast(shell, _rgb_color(page.bgcolor), get_theme_palette(page))
    return shell


def build_sidebar(
    page: ft.Page,
    destinations: list[tuple[str, object, object]],
    active_state: dict,
    on_select_tab,
    menu_items_controls: list[ft.Container],
    style_menu_item,
    user: dict | None = None,
) -> ft.Container:
    """
    Build fixed 270px Custom Sidebar using ft.Column.
    Includes Brand Header, Navigation Items (26px aligned icon column, 14.5px text), User Profile Card, Theme Toggle & Logout.
    """
    t = theme_tokens(page)
    dark = is_dark_mode(page)
    user = user or {}
    menu_items_controls.clear()

    def on_item_hover(e, idx: int):
        hovered = str(getattr(e, "data", "")).lower() == "true"
        style_menu_item(e.control, idx, is_hovered=hovered)
        e.control.update()

    for idx, (lbl, icon_norm, icon_sel) in enumerate(destinations):
        indicator_bar = ft.Container(width=4, height=24, border_radius=2, bgcolor="transparent")
        icon_widget = ft.Icon(icon_norm, size=20, color=t["SIDEBAR_TEXT"])
        icon_col = ft.Container(
            width=26,
            height=26,
            alignment=ft.alignment.center,
            content=icon_widget,
        )
        label_widget = ft.Text(
            lbl,
            size=14.5,
            color=t["SIDEBAR_TEXT"],
            weight=ft.FontWeight.W_500,
            no_wrap=True,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True,
        )
        item_row = ft.Row(
            [indicator_bar, icon_col, label_widget],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        )
        item_box = ft.Container(
            padding=ft.padding.symmetric(horizontal=10, vertical=11),
            border_radius=10,
            animate=make_smooth_animation(180),
            ink=True,
            on_click=lambda e, i=idx: on_select_tab(i),
            on_hover=lambda e, i=idx: on_item_hover(e, i),
            content=item_row,
            data={
                "indicator": indicator_bar,
                "icon_ctrl": icon_widget,
                "label_ctrl": label_widget,
                "icons": (icon_norm, icon_sel),
            },
        )
        menu_items_controls.append(item_box)

    ready = model_ready()
    role = user.get("role", "user")
    role_label = ROLE_LABELS.get(role, "Người chăn nuôi")
    role_color = ROLE_COLORS.get(role, "#059669")
    initials = "".join(part[0].upper() for part in (user.get("full_name") or "U").split()[:2]) or "U"

    avatar_source = (user.get("avatar_url") or "").strip()
    if avatar_source and not avatar_source.startswith(("https://", "http://")):
        local_avatar = Path(avatar_source)
        if not local_avatar.is_absolute():
            local_avatar = Path(__file__).resolve().parent.parent / local_avatar
        avatar_source = str(local_avatar.resolve()) if local_avatar.is_file() else ""

    if avatar_source and Path(avatar_source).is_file():
        avatar = ft.Container(
            width=36,
            height=36,
            border_radius=18,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=make_image(Path(avatar_source), width=36, height=36, border_radius=18),
        )
    else:
        avatar = ft.CircleAvatar(
            bgcolor=role_color,
            radius=18,
            foreground_image_src=avatar_source or None,
            content=ft.Text(initials, color="#FFFFFF", size=12.5, weight=ft.FontWeight.BOLD),
        )

    role_badge_pill = ft.Container(
        padding=ft.padding.symmetric(horizontal=9, vertical=3),
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.22, role_color),
        border=ft.border.all(1, ft.Colors.with_opacity(0.45, role_color)),
        content=ft.Text(
            role_label,
            size=12.5,
            color="#34D399" if role == "user" else ("#38BDF8" if role == "expert" else "#C084FC"),
            weight=ft.FontWeight.W_600,
        ),
    )

    def handle_logout(e):
        logout_user(page)
        page.go("/login")

    def on_logout_hover(e):
        hovered = str(getattr(e, "data", "")).lower() == "true"
        e.control.bgcolor = ft.Colors.with_opacity(0.24 if hovered else 0.12, "#EF4444")
        e.control.border = ft.border.all(1, ft.Colors.with_opacity(0.55 if hovered else 0.3, "#EF4444"))
        e.control.update()

    profile_and_footer = ft.Container(
        data="fixed_dark_sidebar_card",
        padding=14,
        border_radius=14,
        bgcolor="#1E293B",
        border=ft.border.all(1, "#334155"),
        content=ft.Column(
            [
                # User Profile + Full Name + Role Badge
                ft.Row(
                    [
                        avatar,
                        ft.Column(
                            [
                                ft.Text(
                                    user.get("full_name") or "Người dùng",
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                    color="#FFFFFF",
                                ),
                                ft.Row(
                                    [
                                        role_badge_pill,
                                        ft.IconButton(
                                            icon=ft.Icons.LIGHT_MODE_ROUNDED if dark else ft.Icons.DARK_MODE_ROUNDED,
                                            icon_size=18,
                                            icon_color="#FBBF24" if dark else "#CBD5E1",
                                            tooltip="Đổi giao diện Sáng / Tối",
                                            on_click=lambda e: toggle_theme_mode(page),
                                            data="theme_toggle",
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ],
                            spacing=3,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(height=8, color="#334155"),
                # Human-friendly AI Status
                ft.Row(
                    [
                        ft.Text("🟢" if ready else "🟡", size=12.5),
                        ft.Text(
                            "Trí tuệ nhân tạo PigSkin AI" if ready else "PigSkin AI đang khởi động",
                            size=12.5,
                            color="#CBD5E1",
                            expand=True,
                        ),
                    ],
                    spacing=6,
                ),
                # Clean Logout Button
                ft.Container(
                    margin=ft.margin.only(top=4),
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.12, "#EF4444"),
                    border=ft.border.all(1, ft.Colors.with_opacity(0.3, "#EF4444")),
                    animate=make_smooth_animation(180),
                    ink=True,
                    on_click=handle_logout,
                    on_hover=on_logout_hover,
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.LOGOUT_ROUNDED, size=16, color="#FCA5A5"),
                            ft.Text("Đăng xuất tài khoản", size=13, weight=ft.FontWeight.W_600, color="#FCA5A5"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=6,
                    ),
                ),
            ],
            spacing=6,
            tight=True,
        ),
    )

    return ft.Container(
        width=270,
        bgcolor=t["SIDEBAR_BG"],
        border=ft.border.only(right=ft.BorderSide(1, t["SIDEBAR_BORDER"])),
        padding=ft.padding.symmetric(horizontal=14, vertical=18),
        content=ft.Column(
            [
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=8, vertical=6),
                    content=ft.Row(
                        [
                            ft.Container(
                                width=38,
                                height=38,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.18, "#10B981"),
                                alignment=ft.alignment.center,
                                content=ft.Text("🐷", size=19),
                            ),
                            ft.Column(
                                [
                                    ft.Text("PigSkinTech AI", size=15, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                                    ft.Text("Phòng khám Thú y Số", size=12.5, color="#34D399"),
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=10,
                    ),
                ),
                ft.Divider(height=16, color="#1E293B"),
                ft.Container(
                    padding=ft.padding.only(left=10, bottom=4),
                    content=ft.Text("DANH MỤC CHỨC NĂNG", size=12, weight=ft.FontWeight.BOLD, color="#94A3B8"),
                ),
                ft.Column(menu_items_controls, spacing=6),
                ft.Container(expand=True),
                profile_and_footer,
            ],
            expand=True,
            spacing=6,
        ),
    )
