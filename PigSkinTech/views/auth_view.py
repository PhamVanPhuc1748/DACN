"""Authentication & Google OAuth Login View (/login) — Clean Pig Background & Minimalist SaaS Login Card."""
from pathlib import Path

import flet as ft

from services.auth_service import (
    ROLE_COLORS,
    ROLE_LABELS,
    authenticate_google,
    authenticate_local,
    build_google_oauth_provider,
    close_dialog,
    ensure_flet_compat,
    get_mock_google_accounts,
    is_real_oauth_configured,
    open_dialog,
    role_home_route,
    save_session_user,
    show_snack,
    theme_tokens,
)
from theme import make_smooth_animation


def _resolve_login_bg_image() -> Path:
    """Resolve case_images/login_bg_pig.png regardless of working directory."""
    direct_dir = Path(__file__).resolve().parent / "case_images"
    parent_dir = Path(__file__).resolve().parent.parent / "case_images"

    for folder in (direct_dir, parent_dir):
        candidate = folder / "login_bg_pig.png"
        if candidate.is_file():
            return candidate

    for folder in (direct_dir, parent_dir):
        if folder.is_dir():
            imgs = sorted(
                (p for p in folder.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if imgs:
                return imgs[0]

    return parent_dir / "login_bg_pig.png"


def _google_logo_badge() -> ft.Control:
    """Standard Google 'G' mark."""
    return ft.Container(
        width=22,
        height=22,
        bgcolor="#FFFFFF",
        border_radius=11,
        alignment=ft.alignment.center,
        content=ft.Text("G", size=15, weight=ft.FontWeight.W_900, color="#4285F4"),
    )


def build_auth_view(page: ft.Page) -> ft.Control:
    ensure_flet_compat(page)
    t = theme_tokens(page)
    page.appbar = None

    bg_img_path = _resolve_login_bg_image()

    error_text = ft.Text("", size=12, color="#DC2626", visible=False)

    def complete_login(user_record: dict):
        session_user = save_session_user(page, user_record)
        target_route = role_home_route(session_user["role"])
        page.go(target_route)

    def handle_local_login(e=None):
        try:
            error_text.visible = False
            user_record = authenticate_local(email_input.value, password_input.value)
            complete_login(user_record)
        except ValueError as err:
            error_text.value = str(err)
            error_text.visible = True
            page.update()

    # (3) Email Input (No floating label, no prefix_icon)
    email_input = ft.TextField(
        value="nongdan.pigskin@gmail.com",
        hint_text="you@pigskintech.com",
        height=48,
        text_size=14,
        border_radius=8,
        bgcolor="#FFFFFF",
        border_color="#E5E7EB",
        focused_border_color="#16A34A",
        color="#111827",
        hint_style=ft.TextStyle(color="#9CA3AF", size=14),
        content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
        on_submit=handle_local_login,
    )

    # (4) Password Input (No floating label, no prefix_icon)
    password_input = ft.TextField(
        value="123456",
        hint_text="••••••••",
        password=True,
        can_reveal_password=True,
        height=48,
        text_size=14,
        border_radius=8,
        bgcolor="#FFFFFF",
        border_color="#E5E7EB",
        focused_border_color="#16A34A",
        color="#111827",
        hint_style=ft.TextStyle(color="#9CA3AF", size=14),
        content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
        on_submit=handle_local_login,
    )

    # Real Google OAuth callback handler
    def on_oauth_login(e):
        if getattr(e, "error", None):
            error_text.value = f"Lỗi xác thực Google OAuth: {e.error}"
            error_text.visible = True
            page.update()
            return
        oauth_user = getattr(page.auth, "user", None)
        if oauth_user:
            email = oauth_user.get("email") or ""
            name = oauth_user.get("name") or ""
            picture = oauth_user.get("picture") or ""
            try:
                user_record = authenticate_google(email, full_name=name, avatar_url=picture)
                complete_login(user_record)
            except ValueError as err:
                error_text.value = str(err)
                error_text.visible = True
                page.update()

    page.on_login = on_oauth_login

    def open_mock_google_chooser():
        accounts = get_mock_google_accounts()
        custom_email_field = ft.TextField(
            label="Nhập email Google khác (Tự động tạo tài khoản Role: User)",
            hint_text="vidu.trangtrai@gmail.com",
            prefix_icon=ft.Icons.ALTERNATE_EMAIL_ROUNDED,
            dense=True,
        )
        dialog_error = ft.Text("", size=12, color="#DC2626", visible=False)
        chooser_dialog = ft.AlertDialog(modal=True)

        def pick_account(email: str, full_name: str = "", avatar_url: str = ""):
            try:
                user_record = authenticate_google(email, full_name=full_name, avatar_url=avatar_url)
                close_dialog(page, chooser_dialog)
                complete_login(user_record)
            except ValueError as err:
                dialog_error.value = str(err)
                dialog_error.visible = True
                page.update()

        account_tiles = []
        for acc in accounts:
            role_code = acc.get("role", "user")
            badge_color = ROLE_COLORS.get(role_code, "#059669")
            account_tiles.append(
                ft.Container(
                    padding=12,
                    border=ft.border.all(1, t["BORDER"]),
                    border_radius=12,
                    bgcolor=t["SUB_SURFACE"],
                    ink=True,
                    on_click=lambda e, em=acc["email"], fn=acc["full_name"], av=acc.get("avatar_url", ""): pick_account(em, fn, av),
                    content=ft.Row(
                        [
                            ft.CircleAvatar(
                                bgcolor=badge_color,
                                radius=18,
                                content=ft.Text(
                                    (acc["full_name"] or "G")[0].upper(),
                                    color="#FFFFFF",
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ),
                            ft.Column(
                                [
                                    ft.Text(acc["full_name"], size=13, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                                    ft.Text(acc["email"], size=12, color=t["MUTED"]),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Container(
                                bgcolor=badge_color,
                                padding=ft.padding.symmetric(horizontal=10, vertical=4),
                                border_radius=12,
                                content=ft.Text(
                                    ROLE_LABELS.get(role_code, role_code),
                                    size=10,
                                    color="#FFFFFF",
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ),
                        ],
                        spacing=10,
                    ),
                )
            )

        chooser_dialog.title = ft.Row(
            [
                _google_logo_badge(),
                ft.Column(
                    [
                        ft.Text("Chọn tài khoản để tiếp tục tới PigSkinTech", size=15, weight=ft.FontWeight.BOLD),
                        ft.Text("Google OAuth 2.0 (Chế độ Mock Fallback khi chưa đặt GOOGLE_CLIENT_ID)", size=11, color=t["MUTED"]),
                    ],
                    spacing=1,
                ),
            ],
            spacing=10,
        )
        chooser_dialog.content = ft.Container(
            width=490,
            content=ft.Column(
                [
                    ft.Text("Tài khoản Google mẫu theo 3 vai trò (RBAC):", size=12, weight=ft.FontWeight.W_600, color=t["TEXT"]),
                    *account_tiles,
                    ft.Divider(height=12, color=t["BORDER"]),
                    ft.Text("Hoặc đăng nhập bằng tài khoản Google tùy chỉnh:", size=12, weight=ft.FontWeight.W_600, color=t["TEXT"]),
                    custom_email_field,
                    dialog_error,
                ],
                spacing=10,
                tight=True,
            ),
        )
        chooser_dialog.actions = [
            ft.TextButton("Hủy", on_click=lambda e: close_dialog(page, chooser_dialog)),
            ft.FilledButton(
                "Tiếp tục với Email tùy chỉnh",
                icon=ft.Icons.LOGIN_ROUNDED,
                on_click=lambda e: pick_account(custom_email_field.value),
            ),
        ]
        open_dialog(page, chooser_dialog)

    def handle_google_button(e):
        provider = build_google_oauth_provider()
        if is_real_oauth_configured():
            try:
                page.login(provider)
                return
            except Exception:
                pass
        open_mock_google_chooser()

    instant_login_state = {"enabled": True}

    def fill_demo_account(email_val: str, role_label: str):
        email_input.value = email_val
        password_input.value = "123456"
        error_text.visible = False
        if instant_login_state["enabled"]:
            handle_local_login()
            return
        show_snack(page, f"Đã điền tài khoản {role_label}: {email_val} (Mật khẩu: 123456)", "#16A34A")
        page.update()

    def handle_forgot_password(e):
        password_input.value = "123456"
        error_text.visible = False
        show_snack(page, "Đã khôi phục mật khẩu mặc định của tài khoản demo: 123456", "#16A34A")
        page.update()

    def _underlined_role_link(label: str, email_val: str) -> ft.Control:
        return ft.Container(
            ink=True,
            on_click=lambda e: fill_demo_account(email_val, label),
            content=ft.Text(
                label,
                size=12,
                weight=ft.FontWeight.W_600,
                color="#16A34A",
                style=ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE),
            ),
        )

    instant_toggle_label = ft.Text(
        "⚡ 1-Click Đăng nhập thẳng: BẬT",
        size=11,
        weight=ft.FontWeight.BOLD,
        color="#15803D",
    )

    instant_toggle_btn = ft.Container(
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
        border_radius=14,
        bgcolor="#DCFCE7",
        border=ft.border.all(1, "#86EFAC"),
        animate=make_smooth_animation(180),
        ink=True,
        tooltip="Bật để nhấn vào vai trò mẫu là đăng nhập thẳng; tắt để chỉ điền sẵn Email/Mật khẩu",
        content=instant_toggle_label,
    )

    def toggle_instant_login(e):
        instant_login_state["enabled"] = not instant_login_state["enabled"]
        on = instant_login_state["enabled"]
        instant_toggle_label.value = "⚡ 1-Click Đăng nhập thẳng: BẬT" if on else "⚡ 1-Click Đăng nhập thẳng: TẮT"
        instant_toggle_label.color = "#15803D" if on else "#6B7280"
        instant_toggle_btn.bgcolor = "#DCFCE7" if on else "#F3F4F6"
        instant_toggle_btn.border = ft.border.all(1, "#86EFAC" if on else "#E5E7EB")
        page.update()

    instant_toggle_btn.on_click = toggle_instant_login

    # 100% Clean Full-Window Pig Background
    full_bg_image = (
        ft.Image(
            src=str(bg_img_path.resolve()),
            fit=ft.ImageFit.COVER,
            width=float("inf"),
            height=float("inf"),
        )
        if bg_img_path.is_file()
        else ft.Container(
            expand=True,
            width=float("inf"),
            height=float("inf"),
            bgcolor="#14532D",
        )
    )

    # (1) Eyebrow Text
    eyebrow_text = ft.Text(
        "+ CHÀO MỪNG TRỞ LẠI",
        size=11,
        weight=ft.FontWeight.W_600,
        color="#16A34A",
        style=ft.TextStyle(letter_spacing=1.2),
    )

    # (2) Two-tone Headline + Subtitle (4px below)
    headline_block = ft.Column(
        [
            ft.Text(
                spans=[
                    ft.TextSpan(
                        "Đăng nhập ",
                        ft.TextStyle(size=34, weight=ft.FontWeight.W_800, color="#111827"),
                    ),
                    ft.TextSpan(
                        "vào hệ thống.",
                        ft.TextStyle(size=34, weight=ft.FontWeight.W_800, color="#16A34A"),
                    ),
                ],
            ),
            ft.Text(
                "Tiếp tục công việc chẩn đoán và quản lý trang trại của bạn.",
                size=14,
                color="#4B5563",
            ),
        ],
        spacing=4,
        tight=True,
    )

    # (3) Email Field with Label on top
    email_block = ft.Column(
        [
            ft.Text("Email", size=13, weight=ft.FontWeight.W_600, color="#1F2937"),
            email_input,
        ],
        spacing=6,
        tight=True,
    )

    # (4) Password Field with Label on top
    password_block = ft.Column(
        [
            ft.Text("Mật khẩu", size=13, weight=ft.FontWeight.W_600, color="#1F2937"),
            password_input,
        ],
        spacing=6,
        tight=True,
    )

    def on_primary_login_hover(e):
        hovered = str(getattr(e, "data", "")).lower() == "true"
        e.control.bgcolor = "#15803D" if hovered else "#16A34A"
        e.control.shadow = ft.BoxShadow(
            blur_radius=20 if hovered else 14,
            color=ft.Colors.with_opacity(0.32 if hovered else 0.24, "#15803D" if hovered else "#16A34A"),
            offset=ft.Offset(0, 6 if hovered else 4),
        )
        e.control.update()

    # (5) Full Pill-Shaped Primary Login Button ("Đăng nhập  →") placed 20px below Password
    primary_login_btn = ft.Container(
        width=float("inf"),
        height=50,
        border_radius=30,
        bgcolor="#16A34A",
        alignment=ft.alignment.center,
        animate=make_smooth_animation(180),
        ink=True,
        on_click=handle_local_login,
        on_hover=on_primary_login_hover,
        shadow=ft.BoxShadow(
            blur_radius=14,
            color=ft.Colors.with_opacity(0.24, "#16A34A"),
            offset=ft.Offset(0, 4),
        ),
        content=ft.Text(
            "Đăng nhập  →",
            size=15,
            weight=ft.FontWeight.W_600,
            color="#FFFFFF",
        ),
    )

    # (6) Centered "Hoặc" divider with 14px top/bottom spacing
    or_divider = ft.Container(
        width=float("inf"),
        padding=ft.padding.symmetric(vertical=14),
        alignment=ft.alignment.center,
        content=ft.Text("Hoặc", size=13, color="#6B7280"),
    )

    def on_google_btn_hover(e):
        hovered = str(getattr(e, "data", "")).lower() == "true"
        e.control.bgcolor = "#F8FAFC" if hovered else "#FFFFFF"
        e.control.border = ft.border.all(1, "#CBD5E1" if hovered else "#E5E7EB")
        e.control.update()

    # (7) Outlined White Google Button below "Hoặc"
    google_outlined_btn = ft.Container(
        width=float("inf"),
        height=46,
        bgcolor="#FFFFFF",
        border=ft.border.all(1, "#E5E7EB"),
        border_radius=8,
        alignment=ft.alignment.center,
        animate=make_smooth_animation(180),
        ink=True,
        on_click=handle_google_button,
        on_hover=on_google_btn_hover,
        content=ft.Row(
            [
                _google_logo_badge(),
                ft.Text(
                    "Tiếp tục với Google",
                    size=14,
                    weight=ft.FontWeight.W_600,
                    color="#1F2937",
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
        ),
    )

    # (8) Compact Footer Links at bottom of Card
    footer_links = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("Quên mật khẩu? ", size=13, color="#4B5563"),
                    ft.Container(
                        ink=True,
                        on_click=handle_forgot_password,
                        content=ft.Text(
                            "Khôi phục tại đây",
                            size=13,
                            weight=ft.FontWeight.W_600,
                            color="#16A34A",
                            style=ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE),
                        ),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=0,
            ),
            ft.Row(
                [
                    ft.Text("Điền nhanh tài khoản mẫu: ", size=12, color="#6B7280"),
                    _underlined_role_link("Người chăn nuôi", "nongdan.pigskin@gmail.com"),
                    ft.Text("  •  ", size=12, color="#9CA3AF"),
                    _underlined_role_link("Chuyên gia", "bs.thuy.pigskin@gmail.com"),
                    ft.Text("  •  ", size=12, color="#9CA3AF"),
                    _underlined_role_link("Quản trị viên", "admin.pigskin@gmail.com"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=0,
                wrap=True,
            ),
            instant_toggle_btn,
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )

    # Minimalist SaaS Login Card (width=520, pure white #FFFFFF, border_radius=24)
    login_card = ft.Container(
        width=520,
        bgcolor="#FFFFFF",
        border_radius=24,
        padding=ft.padding.symmetric(horizontal=48, vertical=44),
        shadow=ft.BoxShadow(
            blur_radius=36,
            color=ft.Colors.with_opacity(0.22, ft.Colors.BLACK),
            offset=ft.Offset(0, 12),
        ),
        content=ft.Column(
            [
                eyebrow_text,
                ft.Container(height=6),
                headline_block,
                ft.Container(height=22),
                email_block,
                ft.Container(height=14),
                password_block,
                error_text,
                ft.Container(height=20),
                primary_login_btn,
                or_divider,
                google_outlined_btn,
                ft.Container(height=22),
                footer_links,
            ],
            spacing=0,
            tight=True,
        ),
    )

    right_aligned_wrapper = ft.Container(
        expand=True,
        width=float("inf"),
        height=float("inf"),
        padding=ft.padding.only(right=72, left=40, top=28, bottom=28),
        alignment=ft.alignment.center_right,
        content=login_card,
    )

    return ft.Stack(
        expand=True,
        controls=[
            full_bg_image,
            right_aligned_wrapper,
        ],
    )
