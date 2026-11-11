"""Authentication & Google OAuth Login View (/login) — Clean Pig Background & Minimalist SaaS Login Card."""
import asyncio
from pathlib import Path

import flet as ft

from services.auth_service import (
    GOOGLE_REDIRECT_URI,
    ROLE_COLORS,
    ROLE_LABELS,
    authenticate_google,
    authenticate_local,
    close_dialog,
    ensure_flet_compat,
    get_google_oauth_config,
    open_dialog,
    role_home_route,
    run_google_oauth_desktop_flow,
    save_google_oauth_config,
    save_session_user,
    show_snack,
    theme_tokens,
)
from theme import make_smooth_animation


def _make_shake_animation(duration: int = 70):
    curve = getattr(ft.AnimationCurve, "EASE_IN_OUT", None)
    if hasattr(ft, "animation") and hasattr(ft.animation, "Animation"):
        return ft.animation.Animation(duration, curve)
    if hasattr(ft, "Animation"):
        return ft.Animation(duration, curve)
    return None


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

    error_text = ft.Text("", size=12.5, color="#DC2626", weight=ft.FontWeight.W_600, visible=False)
    shake_wrapper = ft.Container(
        offset=ft.Offset(0, 0),
        animate_offset=_make_shake_animation(70),
    )

    async def _run_error_shake():
        for dx in (-0.02, 0.02, -0.01, 0.0):
            shake_wrapper.offset = ft.Offset(dx, 0)
            page.update()
            await asyncio.sleep(0.07)

    def _trigger_shake():
        if hasattr(page, "run_task"):
            try:
                page.run_task(_run_error_shake)
                return
            except Exception:
                pass

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
            _trigger_shake()

    # (3) Email Input (filled, #F8FAFC, prefix_icon MAIL_OUTLINE_ROUNDED)
    email_input = ft.TextField(
        value="nongdan.pigskin@gmail.com",
        hint_text="you@pigskintech.com",
        prefix_icon=ft.Icons.MAIL_OUTLINE_ROUNDED,
        filled=True,
        bgcolor="#F8FAFC",
        fill_color="#F8FAFC",
        height=50,
        text_size=15,
        border_radius=12,
        border_color="#CBD5E1",
        focused_border_color="#16A34A",
        focused_border_width=2,
        color="#0F172A",
        hint_style=ft.TextStyle(color="#94A3B8", size=14),
        content_padding=ft.padding.symmetric(horizontal=16, vertical=14),
        on_submit=handle_local_login,
    )

    # (4) Password Input (filled, #F8FAFC, prefix_icon LOCK_OUTLINE_ROUNDED)
    password_input = ft.TextField(
        value="123456",
        hint_text="••••••••",
        prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
        password=True,
        can_reveal_password=True,
        filled=True,
        bgcolor="#F8FAFC",
        fill_color="#F8FAFC",
        height=50,
        text_size=15,
        border_radius=12,
        border_color="#CBD5E1",
        focused_border_color="#16A34A",
        focused_border_width=2,
        color="#0F172A",
        hint_style=ft.TextStyle(color="#94A3B8", size=14),
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

    google_btn_label = ft.Text(
        "Tiếp tục với Google",
        size=14.5,
        weight=ft.FontWeight.W_600,
        color="#1E293B",
    )

    def open_google_oauth_config_dialog():
        cfg = get_google_oauth_config()
        cid_input = ft.TextField(
            label="GOOGLE_CLIENT_ID",
            value=cfg.get("client_id", ""),
            hint_text="xxxx-yyyy.apps.googleusercontent.com",
            prefix_icon=ft.Icons.KEY_ROUNDED,
            dense=True,
        )
        csec_input = ft.TextField(
            label="GOOGLE_CLIENT_SECRET",
            value=cfg.get("client_secret", ""),
            hint_text="GOCSPX-...",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.LOCK_PERSON_ROUNDED,
            dense=True,
        )
        dlg_err = ft.Text("", size=12, color="#DC2626", visible=False)
        cfg_dialog = ft.AlertDialog(modal=True)

        def save_and_start_oauth(e=None):
            cid = (cid_input.value or "").strip()
            csec = (csec_input.value or "").strip()
            if not cid or not csec:
                dlg_err.value = "Vui lòng nhập đầy đủ GOOGLE_CLIENT_ID và GOOGLE_CLIENT_SECRET."
                dlg_err.visible = True
                page.update()
                return
            save_google_oauth_config(cid, csec)
            close_dialog(page, cfg_dialog)
            show_snack(page, "Đã lưu cấu hình Google OAuth 2.0 vào .env! Đang mở trình duyệt...", "#059669")
            handle_google_button(None)

        cfg_dialog.title = ft.Row(
            [
                _google_logo_badge(),
                ft.Column(
                    [
                        ft.Text("Cấu hình Google OAuth 2.0 Thật", size=15, weight=ft.FontWeight.BOLD),
                        ft.Text(f"Callback Server: {GOOGLE_REDIRECT_URI}", size=11, color=t["MUTED"]),
                    ],
                    spacing=1,
                ),
            ],
            spacing=10,
        )
        cfg_dialog.content = ft.Container(
            width=480,
            content=ft.Column(
                [
                    ft.Text(
                        f"Nhập Client ID & Client Secret từ Google Cloud Console (Authorized redirect URI: {GOOGLE_REDIRECT_URI}):",
                        size=12,
                        color=t["TEXT"],
                    ),
                    cid_input,
                    csec_input,
                    dlg_err,
                ],
                spacing=10,
                tight=True,
            ),
        )
        cfg_dialog.actions = [
            ft.TextButton("Hủy", on_click=lambda e: close_dialog(page, cfg_dialog)),
            ft.FilledButton(
                "Lưu .env & Xác thực Google",
                icon=ft.Icons.OPEN_IN_BROWSER_ROUNDED,
                on_click=save_and_start_oauth,
            ),
        ]
        open_dialog(page, cfg_dialog)

    oauth_busy = {"running": False}

    async def _run_google_oauth_task():
        if oauth_busy["running"]:
            return
        oauth_busy["running"] = True
        error_text.visible = False
        google_btn_label.value = "Đang chờ xác thực tại 127.0.0.1:8765/callback..."
        page.update()

        res = await asyncio.to_thread(run_google_oauth_desktop_flow, 120)

        oauth_busy["running"] = False
        google_btn_label.value = "Tiếp tục với Google"
        page.update()

        if res.get("needs_credentials"):
            open_google_oauth_config_dialog()
            return

        if not res.get("ok"):
            error_text.value = res.get("error") or "Đăng nhập Google OAuth 2.0 thất bại."
            error_text.visible = True
            page.update()
            _trigger_shake()
            return

        user_record = res["user"]
        show_snack(page, f"Đã xác thực Google OAuth 2.0: {user_record['full_name']} ({user_record['email']})", "#059669")
        complete_login(user_record)

    def handle_google_button(e):
        if hasattr(page, "run_task"):
            page.run_task(_run_google_oauth_task)

    def quick_login_role(email_val: str):
        email_input.value = email_val
        password_input.value = "123456"
        error_text.visible = False
        handle_local_login()

    def handle_forgot_password(e):
        password_input.value = "123456"
        error_text.visible = False
        show_snack(page, "Đã khôi phục mật khẩu mặc định của tài khoản demo: 123456", "#16A34A")
        page.update()

    def _quick_role_pill(label: str, email_val: str, accent_fg: str, soft_bg: str, border_col: str) -> ft.Control:
        def on_pill_hover(e):
            hovered = str(getattr(e, "data", "")).lower() == "true"
            e.control.bgcolor = accent_fg if hovered else soft_bg
            lbl_ctrl.color = "#FFFFFF" if hovered else accent_fg
            e.control.update()

        lbl_ctrl = ft.Text(
            label,
            size=12.5,
            weight=ft.FontWeight.W_700,
            color=accent_fg,
            text_align=ft.TextAlign.CENTER,
            no_wrap=True,
        )
        return ft.Container(
            expand=1,
            height=38,
            bgcolor=soft_bg,
            border=ft.border.all(1, border_col),
            border_radius=20,
            alignment=ft.alignment.center,
            animate=make_smooth_animation(160),
            ink=True,
            on_click=lambda e: quick_login_role(email_val),
            on_hover=on_pill_hover,
            content=lbl_ctrl,
        )

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

    # (0) Brand Header Pill above Eyebrow Text
    brand_header_pill = ft.Row(
        [
            ft.Container(
                width=36,
                height=36,
                border_radius=10,
                gradient=ft.LinearGradient(
                    colors=["#10B981", "#059669"],
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                ),
                alignment=ft.alignment.center,
                shadow=ft.BoxShadow(
                    blur_radius=10,
                    color=ft.Colors.with_opacity(0.25, "#10B981"),
                    offset=ft.Offset(0, 3),
                ),
                content=ft.Icon(ft.Icons.PETS_ROUNDED, size=20, color="#FFFFFF"),
            ),
            ft.Text(
                "PigSkinTech AI Studio",
                size=15,
                weight=ft.FontWeight.W_800,
                color="#0F172A",
            ),
        ],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # (1) Eyebrow Text
    eyebrow_text = ft.Text(
        "+ CHÀO MỪNG TRỞ LẠI",
        size=11,
        weight=ft.FontWeight.W_700,
        color="#16A34A",
        style=ft.TextStyle(letter_spacing=1.2),
    )

    # (2) Two-tone Headline on 1 single line ("Đăng nhập ngay.") + Subtitle
    headline_block = ft.Column(
        [
            ft.Text(
                no_wrap=True,
                spans=[
                    ft.TextSpan(
                        "Đăng nhập ",
                        ft.TextStyle(size=32, weight=ft.FontWeight.W_800, color="#0F172A"),
                    ),
                    ft.TextSpan(
                        "ngay.",
                        ft.TextStyle(size=32, weight=ft.FontWeight.W_800, color="#16A34A"),
                    ),
                ],
            ),
            ft.Text(
                "Tiếp tục công việc chẩn đoán và quản lý trang trại của bạn.",
                size=14,
                color="#475569",
            ),
        ],
        spacing=4,
        tight=True,
    )

    # (3) Email Field with Label on top
    email_block = ft.Column(
        [
            ft.Text("Email", size=13.5, weight=ft.FontWeight.W_600, color="#1E293B"),
            email_input,
        ],
        spacing=6,
        tight=True,
    )

    # (4) Password Field with Label + Forgot Password on top
    password_block = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("Mật khẩu", size=13.5, weight=ft.FontWeight.W_600, color="#1E293B", expand=True),
                    ft.Container(
                        ink=True,
                        on_click=handle_forgot_password,
                        content=ft.Text(
                            "Quên mật khẩu?",
                            size=12.5,
                            weight=ft.FontWeight.W_600,
                            color="#16A34A",
                        ),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            password_input,
        ],
        spacing=6,
        tight=True,
    )

    def on_primary_login_hover(e):
        hovered = str(getattr(e, "data", "")).lower() == "true"
        e.control.scale = 1.02 if hovered else 1.0
        e.control.shadow = ft.BoxShadow(
            blur_radius=22 if hovered else 14,
            color=ft.Colors.with_opacity(0.35 if hovered else 0.24, "#059669"),
            offset=ft.Offset(0, 6 if hovered else 4),
        )
        e.control.update()

    # (5) Full Pill-Shaped Primary Login Button ("Đăng nhập  →") with LinearGradient & scale hover
    primary_login_btn = ft.Container(
        width=float("inf"),
        height=52,
        border_radius=30,
        gradient=ft.LinearGradient(
            colors=["#16A34A", "#059669"],
            begin=ft.alignment.center_left,
            end=ft.alignment.center_right,
        ),
        scale=1.0,
        animate_scale=make_smooth_animation(160),
        animate=make_smooth_animation(180),
        alignment=ft.alignment.center,
        ink=True,
        on_click=handle_local_login,
        on_hover=on_primary_login_hover,
        shadow=ft.BoxShadow(
            blur_radius=14,
            color=ft.Colors.with_opacity(0.24, "#059669"),
            offset=ft.Offset(0, 4),
        ),
        content=ft.Text(
            "Đăng nhập  →",
            size=16,
            weight=ft.FontWeight.BOLD,
            color="#FFFFFF",
        ),
    )

    # (6) Centered "Hoặc" divider
    or_divider = ft.Container(
        width=float("inf"),
        padding=ft.padding.symmetric(vertical=12),
        alignment=ft.alignment.center,
        content=ft.Text("Hoặc", size=13, color="#64748B", weight=ft.FontWeight.W_500),
    )

    def on_google_btn_hover(e):
        hovered = str(getattr(e, "data", "")).lower() == "true"
        e.control.bgcolor = "#F8FAFC" if hovered else "#FFFFFF"
        e.control.border = ft.border.all(1.5 if hovered else 1, "#94A3B8" if hovered else "#CBD5E1")
        e.control.update()

    # (7) Outlined White Google Button (border_radius=30, height=48)
    google_outlined_btn = ft.Container(
        width=float("inf"),
        height=48,
        bgcolor="#FFFFFF",
        border=ft.border.all(1, "#CBD5E1"),
        border_radius=30,
        alignment=ft.alignment.center,
        animate=make_smooth_animation(180),
        ink=True,
        on_click=handle_google_button,
        on_hover=on_google_btn_hover,
        content=ft.Row(
            [
                _google_logo_badge(),
                google_btn_label,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
        ),
    )

    # (8) 1-Click Quick Role Selector Box at bottom of Card
    quick_roles_box = ft.Container(
        width=float("inf"),
        padding=ft.padding.symmetric(horizontal=14, vertical=12),
        bgcolor="#F8FAFC",
        border_radius=16,
        border=ft.border.all(1, "#E2E8F0"),
        content=ft.Column(
            [
                ft.Text(
                    "⚡ Đăng nhập nhanh 1-Click theo vai trò:",
                    size=12.5,
                    weight=ft.FontWeight.W_700,
                    color="#475569",
                ),
                ft.Row(
                    [
                        _quick_role_pill("🌾 Nông dân", "nongdan.pigskin@gmail.com", "#059669", "#ECFDF5", "#A7F3D0"),
                        _quick_role_pill("🩺 Chuyên gia", "bs.thuy.pigskin@gmail.com", "#0284C7", "#EFF6FF", "#BAE6FD"),
                        _quick_role_pill("🛡️ Quản trị", "admin.pigskin@gmail.com", "#7C3AED", "#F3E8FF", "#DDD6FE"),
                    ],
                    spacing=8,
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        ),
    )

    # Minimalist SaaS Login Card (width=520, pure white #FFFFFF, border_radius=24)
    login_card = ft.Container(
        width=520,
        bgcolor="#FFFFFF",
        border_radius=24,
        padding=ft.padding.symmetric(horizontal=46, vertical=38),
        shadow=ft.BoxShadow(
            blur_radius=36,
            color=ft.Colors.with_opacity(0.22, ft.Colors.BLACK),
            offset=ft.Offset(0, 12),
        ),
        content=ft.Column(
            [
                brand_header_pill,
                ft.Container(height=12),
                eyebrow_text,
                ft.Container(height=4),
                headline_block,
                ft.Container(height=18),
                email_block,
                ft.Container(height=12),
                password_block,
                error_text,
                ft.Container(height=18),
                primary_login_btn,
                or_divider,
                google_outlined_btn,
                ft.Container(height=18),
                quick_roles_box,
            ],
            spacing=0,
            tight=True,
        ),
    )
    shake_wrapper.content = login_card

    right_aligned_wrapper = ft.Container(
        expand=True,
        width=float("inf"),
        height=float("inf"),
        padding=ft.padding.only(right=72, left=40, top=24, bottom=24),
        alignment=ft.alignment.center_right,
        content=shake_wrapper,
    )

    return ft.Stack(
        expand=True,
        controls=[
            full_bg_image,
            right_aligned_wrapper,
        ],
    )
