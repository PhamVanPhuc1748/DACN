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


# 1. Color Palette (Tailwind Slate & Emerald)
BG_MAIN = "#F8FAFC"         # Nền chính toàn trang - Slate 50
BG_CARD = "#FFFFFF"         # Nền các thẻ nội dung
BG_SIDEBAR = "#0F172A"      # Nền Sidebar trái - Slate 900
TEXT_PRIMARY = "#0F172A"    # Chữ tiêu đề đậm - Slate 900
TEXT_SECONDARY = "#475569"  # Chữ mô tả - Slate 600
TEXT_MUTED = "#94A3B8"      # Chữ phụ/ghi chú - Slate 400
BORDER_LIGHT = "#E2E8F0"    # Viền chuẩn 1px cho mọi Card và Input
PRIMARY = "#10B981"         # Emerald 500
PRIMARY_DARK = "#059669"    # Emerald 600


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
        color=ft.Colors.with_opacity(opacity, TEXT_PRIMARY),
        offset=ft.Offset(0, y_offset),
    )


# 2. Chuẩn hóa Card Style (css_card helper function)
def css_card(
    content: ft.Control,
    padding: int = 24,
    expand: int | bool | None = None,
    border_radius: int = 16,
    bgcolor: str = BG_CARD,
    border_color: str = BORDER_LIGHT,
    gradient: ft.LinearGradient | None = None,
    width: int | float | None = None,
    height: int | float | None = None,
) -> ft.Container:
    """Standardized Shadcn/Tailwind White Card."""
    return ft.Container(
        content=content,
        width=width,
        height=height,
        padding=padding,
        expand=expand,
        bgcolor=None if gradient else bgcolor,
        gradient=gradient,
        border_radius=border_radius,
        border=ft.border.all(1, border_color),
        shadow=css_shadow(0.04, 24, 6),
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
) -> ft.TextField:
    """Standardized Tailwind/Shadcn TextField with #F8FAFC fill and #10B981 focus border."""
    kw = {
        "value": value,
        "hint_text": hint_text,
        "filled": True,
        "fill_color": BG_MAIN,
        "border_radius": 10,
        "border_color": BORDER_LIGHT,
        "focused_border_color": PRIMARY,
        "focused_border_width": 2,
        "text_size": 14,
        "color": TEXT_PRIMARY,
        "label_style": ft.TextStyle(color=TEXT_SECONDARY, size=12),
        "hint_style": ft.TextStyle(color=TEXT_MUTED, size=13),
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
    return ft.TextField(**kw)


def css_dropdown(
    label: str,
    value: str,
    options: list[tuple[str, str]],
    on_change=None,
    width: int | None = None,
    expand: bool = False,
    content_padding=None,
) -> ft.Dropdown:
    """Standardized Tailwind/Shadcn Dropdown with #F8FAFC fill and #10B981 focus border."""
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
        ("fill_color", BG_MAIN),
        ("border_radius", 10),
        ("border_color", BORDER_LIGHT),
        ("focused_border_color", PRIMARY),
        ("focused_border_width", 2),
        ("text_size", 14),
        ("color", TEXT_PRIMARY),
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


# 5. Làm mới KPI Stat Cards (Thẻ thống kê đầu trang)
def css_kpi_card(
    title: str,
    value: str,
    badge_text: str,
    icon: object,
    accent: str = PRIMARY_DARK,
    pastel_bg: str = "#ECFDF5",
) -> ft.Container:
    """
    Modern SaaS KPI Stat Card:
    - 48x48 rounded-12 pastel icon box (#ECFDF5 emerald, #EFF6FF blue, #FFFBEB amber)
    - Value in size=26, weight=W_800, color=#0F172A
    - Top-right status badge (e.g. '+12% hôm nay' or 'Hoạt động tốt')
    """
    return css_card(
        padding=20,
        expand=1,
        border_radius=16,
        content=ft.Row(
            [
                ft.Container(
                    width=48,
                    height=48,
                    border_radius=12,
                    bgcolor=pastel_bg,
                    alignment=ft.alignment.center,
                    content=ft.Icon(icon, color=accent, size=24),
                ),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    title,
                                    size=12,
                                    weight=ft.FontWeight.W_600,
                                    color=TEXT_SECONDARY,
                                    expand=True,
                                ),
                                ft.Container(
                                    bgcolor=pastel_bg,
                                    padding=ft.padding.symmetric(horizontal=9, vertical=3),
                                    border_radius=20,
                                    content=ft.Text(
                                        badge_text,
                                        size=10,
                                        weight=ft.FontWeight.BOLD,
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
                            color=TEXT_PRIMARY,
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
