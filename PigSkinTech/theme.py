"""Modern SaaS / Shadcn-UI & Tailwind Style Design System & CSS Tokens for PigSkinTech."""
import inspect
import flet as ft

if hasattr(ft, "Padding") and hasattr(ft, "padding"):
    for _n in ("all", "symmetric", "only", "zero"):
        if not hasattr(ft.padding, _n) and hasattr(ft.Padding, _n):
            setattr(ft.padding, _n, getattr(ft.Padding, _n))
if hasattr(ft, "Border") and hasattr(ft, "border"):
    for _n in ("all", "only", "symmetric"):
        if not hasattr(ft.border, _n) and hasattr(ft.Border, _n):
            setattr(ft.border, _n, getattr(ft.Border, _n))


# 1. Color Palette Constants (Default Light Tokens + Shared Accents)
BG_MAIN = "#F8FAFC"         # Nền chính toàn trang - Slate 50
BG_CARD = "#FFFFFF"         # Nền các thẻ nội dung
BG_SIDEBAR = "#0F172A"      # Nền Sidebar trái - Slate 900
TEXT_PRIMARY = "#0F172A"    # Chữ tiêu đề đậm - Slate 900
TEXT_SECONDARY = "#475569"  # Chữ mô tả - Slate 600
TEXT_MUTED = "#64748B"      # Chữ phụ/ghi chú - Slate 500
BORDER_LIGHT = "#E2E8F0"    # Viền chuẩn 1px cho mọi Card và Input
PRIMARY = "#10B981"         # Emerald 500
PRIMARY_DARK = "#059669"    # Emerald 600

_CURRENT_PAGE_REF: dict[str, ft.Page | None] = {"page": None}


def set_theme_page_context(page: ft.Page | None):
    if page is not None:
        _CURRENT_PAGE_REF["page"] = page


def _is_page_dark(page: ft.Page | None = None) -> bool:
    p = page or _CURRENT_PAGE_REF.get("page")
    if p is None:
        return False
    if getattr(p, "theme_mode", None) == ft.ThemeMode.DARK:
        return True
    try:
        store = getattr(p.session, "store", getattr(p, "session", None))
        if store is not None and hasattr(store, "get"):
            mode = store.get("theme_mode")
            if mode:
                return mode == "dark"
    except Exception:
        pass
    return False


def get_theme_palette(page: ft.Page | None = None) -> dict:
    """Return dynamic Light / Dark Mode palette synchronized with page.theme_mode."""
    if page is not None:
        _CURRENT_PAGE_REF["page"] = page
    dark = _is_page_dark(page)
    if dark:
        return {
            "IS_DARK": True,
            "BG_MAIN": "#0B1120",
            "BG_CARD": "#1E293B",
            "BG_SUB": "#0F172A",
            "BG_SIDEBAR": "#090E1A",
            "TEXT_PRIMARY": "#F8FAFC",
            "TEXT_SECONDARY": "#CBD5E1",
            "TEXT_MUTED": "#94A3B8",
            "BORDER_LIGHT": "#334155",
            "SOFT_EMERALD": "#064E3B",
            "SOFT_BLUE": "#0C4A6E",
            "SOFT_AMBER": "#78350F",
            "SOFT_RED": "#7F1D1D",
            "SOFT_PURPLE": "#4C1D95",
            "PROTOCOL_HEAD": "#6EE7B7",
            "PROTOCOL_TEXT": "#E2E8F0",
            "PROTOCOL_BORDER": "#059669",
            "DROPZONE_GRADIENT": ["#064E3B", "#0F172A"],
            "DROPZONE_HOVER_GRADIENT": ["#047857", "#1E293B"],
            "DROPZONE_BORDER": "#10B981",
            "PRIMARY": PRIMARY,
            "PRIMARY_DARK": "#10B981",
        }
    return {
        "IS_DARK": False,
        "BG_MAIN": "#F8FAFC",
        "BG_CARD": "#FFFFFF",
        "BG_SUB": "#F1F5F9",
        "BG_SIDEBAR": "#0F172A",
        "TEXT_PRIMARY": "#0F172A",
        "TEXT_SECONDARY": "#475569",
        "TEXT_MUTED": "#64748B",
        "BORDER_LIGHT": "#E2E8F0",
        "SOFT_EMERALD": "#ECFDF5",
        "SOFT_BLUE": "#EFF6FF",
        "SOFT_AMBER": "#FFFBEB",
        "SOFT_RED": "#FEF2F2",
        "SOFT_PURPLE": "#F3E8FF",
        "PROTOCOL_HEAD": "#065F46",
        "PROTOCOL_TEXT": "#064E3B",
        "PROTOCOL_BORDER": "#A7F3D0",
        "DROPZONE_GRADIENT": ["#F0FDF4", "#ECFDF5"],
        "DROPZONE_HOVER_GRADIENT": ["#DCFCE7", "#D1FAE5"],
        "DROPZONE_BORDER": "#86EFAC",
        "PRIMARY": PRIMARY,
        "PRIMARY_DARK": PRIMARY_DARK,
    }


def make_smooth_animation(duration: int = 200):
    """Cross-version helper for ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT)."""
    curve = getattr(ft.AnimationCurve, "EASE_OUT", None)
    if hasattr(ft, "animation") and hasattr(ft.animation, "Animation"):
        return ft.animation.Animation(duration, curve)
    if hasattr(ft, "Animation"):
        return ft.Animation(duration, curve)
    return None


def css_shadow(opacity: float = 0.04, blur: int = 24, y_offset: int = 6) -> ft.BoxShadow:
    """Standardized soft SaaS BoxShadow."""
    return ft.BoxShadow(
        spread_radius=0,
        blur_radius=blur,
        color=ft.Colors.with_opacity(opacity, "#000000"),
        offset=ft.Offset(0, y_offset),
    )


# 2. Chuẩn hóa Card Style (css_card helper function)
def css_card(
    content: ft.Control,
    padding: int = 24,
    expand: int | bool | None = None,
    border_radius: int = 16,
    bgcolor: str | None = None,
    border_color: str | None = None,
    gradient: ft.LinearGradient | None = None,
    width: int | float | None = None,
    height: int | float | None = None,
    page: ft.Page | None = None,
) -> ft.Container:
    """Standardized Shadcn/Tailwind Card supporting Light & Dark Mode."""
    pal = get_theme_palette(page)
    resolved_bg = bgcolor if bgcolor is not None else pal["BG_CARD"]
    resolved_border = border_color if border_color is not None else pal["BORDER_LIGHT"]
    return ft.Container(
        content=content,
        width=width,
        height=height,
        padding=padding,
        expand=expand,
        bgcolor=None if gradient else resolved_bg,
        gradient=gradient,
        border_radius=border_radius,
        border=ft.border.all(1, resolved_border),
        shadow=css_shadow(0.18 if pal["IS_DARK"] else 0.04, 24, 6),
        animate=make_smooth_animation(200),
    )


# 3. Chuẩn hóa Input & Dropdown Style (css_input / css_dropdown)
def css_input(
    label: str = "",
    value: str = "",
    hint_text: str = "",
    prefix_icon: object = None,
    password: bool = False,
    can_reveal_password: bool = False,
    multiline: bool = False,
    min_lines: int | None = None,
    max_lines: int | None = None,
    width: int | float | None = None,
    height: int | None = None,
    expand: bool | int = False,
    on_change=None,
    on_submit=None,
    page: ft.Page | None = None,
) -> ft.TextField:
    """Standardized Tailwind/Shadcn TextField with dynamic Light/Dark colors and larger typography."""
    pal = get_theme_palette(page)
    kw = {
        "value": value,
        "hint_text": hint_text,
        "filled": True,
        "fill_color": pal["BG_SUB"],
        "border_radius": 10,
        "border_color": pal["BORDER_LIGHT"],
        "focused_border_color": PRIMARY,
        "focused_border_width": 2,
        "text_size": 14.5,
        "color": pal["TEXT_PRIMARY"],
        "label_style": ft.TextStyle(color=pal["TEXT_SECONDARY"], size=13.5),
        "hint_style": ft.TextStyle(color=pal["TEXT_MUTED"], size=13.5),
        "content_padding": ft.padding.symmetric(horizontal=16, vertical=14),
    }
    if label:
        kw["label"] = label
    if prefix_icon is not None:
        kw["prefix_icon"] = prefix_icon
    if password:
        kw["password"] = True
    if can_reveal_password:
        kw["can_reveal_password"] = True
    if multiline:
        kw["multiline"] = True
    if min_lines is not None:
        kw["min_lines"] = min_lines
    if max_lines is not None:
        kw["max_lines"] = max_lines
    if width is not None:
        kw["width"] = width
    if height is not None:
        kw["height"] = height
    if expand:
        kw["expand"] = expand
    if on_change is not None:
        kw["on_change"] = on_change
    if on_submit is not None:
        kw["on_submit"] = on_submit
    return ft.TextField(**kw)


def css_dropdown(
    label: str,
    value: str,
    options: list[tuple[str, str]],
    on_change=None,
    width: int | None = None,
    expand: bool = False,
    content_padding=None,
    page: ft.Page | None = None,
) -> ft.Dropdown:
    """Standardized Tailwind/Shadcn Dropdown with dynamic Light/Dark colors and larger typography."""
    pal = get_theme_palette(page)
    opts = [ft.dropdown.Option(key=k, text=t) for k, t in options]
    params = inspect.signature(ft.Dropdown.__init__).parameters
    pad = content_padding if content_padding is not None else ft.padding.symmetric(horizontal=16, vertical=14)
    kw = {
        "value": value,
        "options": opts,
        "dense": True,
    }
    if label:
        kw["label"] = label
    if width:
        kw["width"] = width
    if expand:
        kw["expand"] = True
    for k, v in (
        ("filled", True),
        ("fill_color", pal["BG_SUB"]),
        ("border_radius", 10),
        ("border_color", pal["BORDER_LIGHT"]),
        ("focused_border_color", PRIMARY),
        ("focused_border_width", 2),
        ("text_size", 14.5),
        ("color", pal["TEXT_PRIMARY"]),
        ("label_style", ft.TextStyle(color=pal["TEXT_SECONDARY"], size=13.5)),
        ("content_padding", pad),
    ):
        if k in params:
            kw[k] = v
    if on_change:
        if "on_select" in params:
            kw["on_select"] = on_change
        else:
            kw["on_change"] = on_change
    return ft.Dropdown(**kw)


def css_button_primary(
    text: str,
    icon: object = None,
    on_click=None,
    bgcolor: str = PRIMARY_DARK,
    hover_bgcolor: str | None = None,
    height: int = 52,
    radius: int = 12,
    width: int | float | None = float("inf"),
    padding: ft.Padding | int | None = None,
) -> ft.Container:
    """Standardized Tailwind/Shadcn Primary Action Button with smooth on_hover color & shadow elevation."""
    target_hover_bg = hover_bgcolor or (PRIMARY if bgcolor == PRIMARY_DARK else "#0369A1")

    def _on_hover(e):
        hovered = str(getattr(e, "data", "")).lower() == "true"
        e.control.bgcolor = target_hover_bg if hovered else bgcolor
        e.control.shadow = ft.BoxShadow(
            blur_radius=24 if hovered else 16,
            color=ft.Colors.with_opacity(0.34 if hovered else 0.22, target_hover_bg if hovered else bgcolor),
            offset=ft.Offset(0, 6 if hovered else 4),
        )
        e.control.update()

    row_children: list[ft.Control] = []
    if icon is not None:
        row_children.append(ft.Icon(icon, size=20, color="#FFFFFF"))
    row_children.append(
        ft.Text(
            text,
            size=16 if height >= 50 else 14,
            weight=ft.FontWeight.BOLD,
            color="#FFFFFF",
        )
    )

    return ft.Container(
        width=width,
        height=height,
        padding=padding or ft.padding.symmetric(horizontal=20, vertical=0),
        border_radius=radius,
        bgcolor=bgcolor,
        alignment=ft.alignment.center,
        animate=make_smooth_animation(180),
        ink=True,
        on_click=on_click,
        on_hover=_on_hover,
        shadow=ft.BoxShadow(
            blur_radius=16,
            color=ft.Colors.with_opacity(0.22, bgcolor),
            offset=ft.Offset(0, 4),
        ),
        content=ft.Row(
            row_children,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            tight=True,
        ),
    )


# 5. Làm mới KPI Stat Cards (Thẻ thống kê đầu trang)
def css_kpi_card(
    title: str,
    value: str,
    badge_text: str,
    icon: object,
    accent: str = PRIMARY_DARK,
    pastel_bg: str = "#ECFDF5",
    page: ft.Page | None = None,
) -> ft.Container:
    """
    Modern SaaS KPI Stat Card:
    - 48x48 rounded-12 pastel icon box
    - Value in size=26, weight=W_800
    - Top-right status badge (size=12.5)
    """
    pal = get_theme_palette(page)
    box_bg = ft.Colors.with_opacity(0.22, accent) if pal["IS_DARK"] else pastel_bg
    return css_card(
        padding=20,
        expand=1,
        border_radius=16,
        page=page,
        content=ft.Row(
            [
                ft.Container(
                    width=48,
                    height=48,
                    border_radius=12,
                    bgcolor=box_bg,
                    alignment=ft.alignment.center,
                    content=ft.Icon(icon, color=accent, size=24),
                ),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    title,
                                    size=13.5,
                                    weight=ft.FontWeight.W_600,
                                    color=pal["TEXT_SECONDARY"],
                                    expand=True,
                                ),
                                ft.Container(
                                    bgcolor=box_bg,
                                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                                    border_radius=20,
                                    content=ft.Text(
                                        badge_text,
                                        size=12.5,
                                        weight=ft.FontWeight.W_600,
                                        color=accent,
                                    ),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Text(
                            value,
                            size=26,
                            weight=ft.FontWeight.W_800,
                            color=pal["TEXT_PRIMARY"],
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
