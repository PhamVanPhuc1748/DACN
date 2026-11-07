"""Authentication service, Tech Emerald & Cyber Slate Design System, and Custom Sidebar Shell."""
import base64
import inspect
import os
from datetime import datetime
from pathlib import Path
import urllib.parse

import flet as ft

try:
    from flet.auth.providers import GoogleOAuthProvider
except ImportError:  # pragma: no cover
    GoogleOAuthProvider = getattr(ft, "GoogleOAuthProvider", None)

if GoogleOAuthProvider and not hasattr(ft, "GoogleOAuthProvider"):
    ft.GoogleOAuthProvider = GoogleOAuthProvider

from services.inference import model_ready
from services.project_data import active_run, load_classes_config
from services.store import MOCK_GOOGLE_ACCOUNTS, _hash_password, conn, initialize
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
    make_smooth_animation,
)


REDIRECT_URL = "http://localhost:8550/api/oauth/redirect"

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
        "BG": BG_MAIN,
        "SURFACE": BG_CARD,
        "SUB_SURFACE": BG_MAIN,
        "SIDEBAR_BG": BG_SIDEBAR,
        "SIDEBAR_HOVER": "#1E293B",
        "SIDEBAR_TEXT": TEXT_MUTED,
        "SIDEBAR_ACTIVE_TEXT": "#FFFFFF",
        "SIDEBAR_BORDER": "#1E293B",
        "BORDER": BORDER_LIGHT,
        "TEXT": TEXT_PRIMARY,
        "SECONDARY": TEXT_SECONDARY,
        "MUTED": TEXT_MUTED,
        "EMERALD": PRIMARY_DARK,
        "EMERALD_LIGHT": PRIMARY,
        "EMERALD_SOFT": "#ECFDF5",
        "CYAN": "#0284C7",
        "CYAN_SOFT": "#EFF6FF",
        "AMBER": "#D97706",
        "AMBER_SOFT": "#FFFBEB",
        "RED": "#DC2626",
        "RED_SOFT": "#FEE2E2",
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
        return False
    mode = session_get(page, "theme_mode")
    if mode:
        return mode == "dark"
    return getattr(page, "theme_mode", ft.ThemeMode.LIGHT) == ft.ThemeMode.DARK


def theme_tokens(page: ft.Page | None = None) -> dict:
    return THEMES["dark" if is_dark_mode(page) else "light"]


def toggle_theme_mode(page: ft.Page):
    new_mode = "light" if is_dark_mode(page) else "dark"
    session_set(page, "theme_mode", new_mode)
    page.theme_mode = ft.ThemeMode.DARK if new_mode == "dark" else ft.ThemeMode.LIGHT
    t = theme_tokens(page)
    page.bgcolor = t["BG"]
    current_route = getattr(page, "route", "/login") or "/login"
    if hasattr(page, "go"):
        page.go(current_route)
    else:
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
    )


def header_stat_pill(
    label: str,
    value: str,
    icon: object,
    accent: str = PRIMARY_DARK,
    soft_bg: str = "#ECFDF5",
    badge_text: str = "Hoạt động tốt",
    page: ft.Page | None = None,
) -> ft.Container:
    """Modern SaaS KPI Stat Card placed at the top of the page."""
    t = theme_tokens(page)
    return ft.Container(
        bgcolor=t["SURFACE"],
        border=ft.border.all(1, t["BORDER"]),
        border_radius=16,
        padding=ft.padding.symmetric(horizontal=18, vertical=14),
        shadow=card_shadow(),
        animate=make_smooth_animation(200),
        content=ft.Row(
            [
                ft.Container(
                    width=48,
                    height=48,
                    bgcolor=soft_bg if not is_dark_mode(page) else ft.Colors.with_opacity(0.2, accent),
                    border_radius=12,
                    alignment=ft.alignment.center,
                    content=ft.Icon(icon, color=accent, size=24),
                ),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(label, size=12, color=TEXT_SECONDARY if not is_dark_mode(page) else t["MUTED"], weight=ft.FontWeight.W_600),
                                ft.Container(
                                    bgcolor=soft_bg if not is_dark_mode(page) else ft.Colors.with_opacity(0.2, accent),
                                    padding=ft.padding.symmetric(horizontal=8, vertical=2),
                                    border_radius=12,
                                    content=ft.Text(badge_text, size=10, color=accent, weight=ft.FontWeight.BOLD),
                                ),
                            ],
                            spacing=8,
                            tight=True,
                        ),
                        ft.Text(value, size=26, color=t["TEXT"], weight=ft.FontWeight.W_800),
                    ],
                    spacing=2,
                    tight=True,
                ),
            ],
            spacing=12,
            tight=True,
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
    """Minimalist Clean SaaS Page Header on light background with right-aligned KPI stat cards."""
    t = theme_tokens(page)
    right_items: list[ft.Control] = []
    if pills:
        right_items.extend(pills)
    elif badge_text:
        right_items.append(
            ft.Container(
                bgcolor=t["SURFACE"],
                border=ft.border.all(1, t["BORDER"]),
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                border_radius=20,
                content=ft.Row(
                    [
                        ft.Container(width=8, height=8, bgcolor=PRIMARY, border_radius=4),
                        ft.Text(badge_text, size=11, color=t["TEXT"], weight=ft.FontWeight.W_600),
                    ],
                    spacing=6,
                    tight=True,
                ),
            )
        )

    title_col_items = [ft.Text(title, size=24, weight=ft.FontWeight.W_800, color=t["TEXT"])]
    if subtitle:
        title_col_items.append(ft.Text(subtitle, size=13, color=TEXT_SECONDARY if not is_dark_mode(page) else t["MUTED"]))

    return ft.Container(
        padding=ft.padding.only(bottom=2),
        content=ft.Row(
            [
                ft.Column(title_col_items, spacing=3, expand=True),
                ft.Row(right_items, spacing=12, wrap=True),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def kpi_stat_card(
    title: str,
    value: str,
    subtitle: str,
    icon: object,
    accent: str = PRIMARY_DARK,
    soft_bg: str = "#ECFDF5",
    page: ft.Page | None = None,
) -> ft.Container:
    t = theme_tokens(page)
    return tech_card(
        page=page,
        padding=20,
        expand=1,
        border_radius=16,
        content=ft.Row(
            [
                ft.Container(
                    width=48,
                    height=48,
                    bgcolor=soft_bg if not is_dark_mode(page) else ft.Colors.with_opacity(0.2, accent),
                    border_radius=12,
                    alignment=ft.alignment.center,
                    content=ft.Icon(icon, color=accent, size=24),
                ),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(title, size=12, color=TEXT_SECONDARY if not is_dark_mode(page) else t["MUTED"], weight=ft.FontWeight.W_600, expand=True),
                                ft.Container(
                                    bgcolor=soft_bg if not is_dark_mode(page) else ft.Colors.with_opacity(0.2, accent),
                                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                                    border_radius=12,
                                    content=ft.Text(subtitle, size=10, color=accent, weight=ft.FontWeight.BOLD),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Text(value, size=26, color=t["TEXT"], weight=ft.FontWeight.W_800),
                    ],
                    spacing=4,
                    expand=True,
                ),
            ],
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
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


def is_real_oauth_configured() -> bool:
    return bool(
        os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        and os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    )


def build_google_oauth_provider():
    """Return configured ft.GoogleOAuthProvider instance."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip() or "mock-google-client-id"
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip() or "mock-google-client-secret"
    return ft.GoogleOAuthProvider(
        client_id=client_id,
        client_secret=client_secret,
        redirect_url=REDIRECT_URL,
    )


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


def authenticate_google(email: str, full_name: str | None = None, avatar_url: str | None = None) -> dict:
    """Verify Google email in DB or auto-provision a new account with default role 'user'."""
    initialize()
    clean_email = (email or "").strip().lower()
    if not clean_email or "@" not in clean_email:
        raise ValueError("Vui lòng nhập địa chỉ email Google hợp lệ (ví dụ: tenban@gmail.com).")
    with conn() as c:
        row = c.execute("SELECT * FROM users WHERE LOWER(email)=?", (clean_email,)).fetchone()
        if not row:
            local_part = clean_email.split("@")[0]
            derived_name = (full_name or "").strip() or local_part.replace(".", " ").replace("_", " ").title()
            encoded_name = urllib.parse.quote(derived_name)
            derived_avatar = avatar_url or f"https://ui-avatars.com/api/?name={encoded_name}&background=059669&color=fff"
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur = c.execute(
                """INSERT INTO users
                (email, username, password_hash, full_name, avatar_url, role, auth_provider, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 'user', 'google', 1, ?)""",
                (
                    clean_email,
                    local_part,
                    _hash_password("123456"),
                    derived_name,
                    derived_avatar,
                    now_str,
                ),
            )
            row = c.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
    if int(row["is_active"]) == 0:
        raise ValueError("Tài khoản Google này đang bị khóa bởi Quản trị viên.")
    return dict(row)


def get_mock_google_accounts() -> list[dict]:
    """Return the 3 canonical Google mock accounts enriched with current DB role."""
    initialize()
    emails = [
        "nongdan.pigskin@gmail.com",
        "bs.thuy.pigskin@gmail.com",
        "admin.pigskin@gmail.com",
    ]
    out = []
    with conn() as c:
        for em in emails:
            row = c.execute("SELECT * FROM users WHERE LOWER(email)=?", (em,)).fetchone()
            if row:
                out.append(dict(row))
    return out or [acc for acc in MOCK_GOOGLE_ACCOUNTS if acc["auth_provider"] == "google"]


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
):
    return css_dropdown(
        label=label,
        value=value,
        options=options,
        on_change=on_change,
        width=width,
        expand=expand,
        content_padding=content_padding,
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
    Consolidates User Profile, Role Badge, Dark Mode & Logout into the 250px Left Sidebar.
    """
    ensure_flet_compat(page)
    t = theme_tokens(page)
    page.bgcolor = t["BG"]
    page.appbar = None

    body_host = ft.Container(
        expand=True,
        padding=24,
        bgcolor=t["BG"],
        content=ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=20),
    )

    active_state = {"index": initial_index}
    menu_items_controls: list[ft.Container] = []

    def style_menu_item(item_container: ft.Container, idx: int, is_hovered: bool = False):
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

    def switch_tab(idx: int):
        active_state["index"] = idx
        for i, ctrl in enumerate(menu_items_controls):
            style_menu_item(ctrl, i, is_hovered=False)
        controls = tab_builders[idx]()
        body_host.content = ft.Column(
            controls=controls if isinstance(controls, list) else [controls],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=20,
        )
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

    switch_tab(initial_index)

    return ft.Row(
        [
            custom_sidebar,
            body_host,
        ],
        expand=True,
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
    )


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
    Build fixed 250px Custom Sidebar using ft.Column.
    Includes Brand Header, Navigation Items (26px aligned icon column), User Profile Card, Theme Toggle & Logout.
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
        icon_widget = ft.Icon(icon_norm, size=19, color=t["SIDEBAR_TEXT"])
        icon_col = ft.Container(
            width=26,
            height=26,
            alignment=ft.alignment.center,
            content=icon_widget,
        )
        label_widget = ft.Text(
            lbl,
            size=13,
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
            padding=ft.padding.symmetric(horizontal=10, vertical=10),
            border_radius=10,
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

    avatar = ft.CircleAvatar(
        bgcolor=role_color,
        radius=16,
        content=ft.Text(initials, color="#FFFFFF", size=11, weight=ft.FontWeight.BOLD),
    )

    def handle_logout(e):
        logout_user(page)
        page.go("/login")

    profile_and_footer = ft.Container(
        padding=12,
        border_radius=12,
        bgcolor="#1E293B",
        border=ft.border.all(1, "#334155"),
        content=ft.Column(
            [
                # User Profile + Role Badge
                ft.Row(
                    [
                        avatar,
                        ft.Column(
                            [
                                ft.Text(
                                    user.get("full_name") or "Người dùng",
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color="#FFFFFF",
                                    no_wrap=True,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    role_label,
                                    size=10,
                                    color="#34D399",
                                    weight=ft.FontWeight.W_600,
                                ),
                            ],
                            spacing=1,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.LIGHT_MODE_ROUNDED if dark else ft.Icons.DARK_MODE_ROUNDED,
                            icon_size=16,
                            icon_color="#FBBF24" if dark else "#94A3B8",
                            tooltip="Đổi giao diện Sáng / Tối",
                            on_click=lambda e: toggle_theme_mode(page),
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(height=8, color="#334155"),
                # Human-friendly AI Status
                ft.Row(
                    [
                        ft.Text("🟢" if ready else "🟡", size=10),
                        ft.Text(
                            "Trí tuệ nhân tạo PigSkin AI" if ready else "PigSkin AI đang khởi động",
                            size=11,
                            color="#CBD5E1",
                            expand=True,
                        ),
                    ],
                    spacing=6,
                ),
                # Clean Logout Button
                ft.Container(
                    margin=ft.margin.only(top=4),
                    padding=ft.padding.symmetric(horizontal=10, vertical=7),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.12, "#EF4444"),
                    border=ft.border.all(1, ft.Colors.with_opacity(0.3, "#EF4444")),
                    ink=True,
                    on_click=handle_logout,
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.LOGOUT_ROUNDED, size=14, color="#FCA5A5"),
                            ft.Text("Đăng xuất tài khoản", size=11, weight=ft.FontWeight.W_600, color="#FCA5A5"),
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
        width=250,
        bgcolor=t["SIDEBAR_BG"],
        border=ft.border.only(right=ft.BorderSide(1, t["SIDEBAR_BORDER"])),
        padding=ft.padding.symmetric(horizontal=12, vertical=18),
        content=ft.Column(
            [
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=8, vertical=6),
                    content=ft.Row(
                        [
                            ft.Container(
                                width=36,
                                height=36,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.18, "#10B981"),
                                alignment=ft.alignment.center,
                                content=ft.Text("🐷", size=18),
                            ),
                            ft.Column(
                                [
                                    ft.Text("PigSkinTech AI", size=14, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                                    ft.Text("Phòng khám Thú y Số", size=10, color="#34D399"),
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
                    content=ft.Text("DANH MỤC CHỨC NĂNG", size=10, weight=ft.FontWeight.BOLD, color="#64748B"),
                ),
                ft.Column(menu_items_controls, spacing=6),
                ft.Container(expand=True),
                profile_and_footer,
            ],
            expand=True,
            spacing=6,
        ),
    )
