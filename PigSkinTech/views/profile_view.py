"""Shared account and security settings for every PigSkinTech role — Modern Medical Dashboard Layout."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import flet as ft
from PIL import Image, ImageOps

from services.auth_service import (
    ROLE_COLORS,
    ROLE_LABELS,
    create_file_picker,
    is_dark_mode,
    make_image,
    pick_image_files,
    role_home_route,
    save_session_user,
    show_snack,
    theme_tokens,
)
from services.store import change_user_password, update_user_profile
from theme import PRIMARY, PRIMARY_DARK, css_shadow, get_theme_palette


APP_DIR = Path(__file__).resolve().parents[1]
AVATAR_DIR = APP_DIR / "profile_avatars"
MAX_AVATAR_BYTES = 8 * 1024 * 1024


def _avatar_image(value: str | None, size: int, initials: str, bgcolor: str) -> ft.Control:
    raw = (value or "").strip()
    if raw.startswith(("https://", "http://")):
        return ft.Image(
            src=raw,
            fit=ft.ImageFit.COVER,
            width=size,
            height=size,
            border_radius=size // 2,
            error_content=ft.CircleAvatar(
                radius=size / 2,
                bgcolor=bgcolor,
                content=ft.Text(initials, size=size * 0.28, weight=ft.FontWeight.BOLD, color="#047857"),
            ),
        )
    if raw:
        path = Path(raw)
        if not path.is_absolute():
            path = APP_DIR / path
        if path.is_file():
            return make_image(path, width=size, height=size, border_radius=size // 2)
    return ft.CircleAvatar(
        radius=size / 2,
        bgcolor=bgcolor,
        content=ft.Text(initials, size=size * 0.28, weight=ft.FontWeight.BOLD, color="#047857"),
    )


def _store_avatar(source: Path, user_id: int) -> str:
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    destination = AVATAR_DIR / f"user_{user_id}_{uuid4().hex[:12]}.jpg"
    with Image.open(source) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGB")
        image.thumbnail((512, 512))
        image.save(destination, format="JPEG", quality=88, optimize=True)
    return destination.relative_to(APP_DIR).as_posix()


def _remove_managed_avatar(value: str | None) -> None:
    raw = (value or "").replace("\\", "/")
    if not raw.startswith("profile_avatars/"):
        return
    path = (APP_DIR / raw).resolve()
    if AVATAR_DIR.resolve() in path.parents:
        path.unlink(missing_ok=True)


def build_profile_view(page: ft.Page, user: dict) -> ft.Control:
    t = theme_tokens(page)
    pal = get_theme_palette(page)
    dark = is_dark_mode(page)

    user_id = int(user.get("user_id") or user.get("id"))
    role = str(user.get("role") or "user")
    role_label = ROLE_LABELS.get(role, role)
    role_color = ROLE_COLORS.get(role, PRIMARY_DARK)
    auth_provider = str(user.get("auth_provider") or "local")
    can_change_email = auth_provider != "google" or bool(user.get("google_sub"))
    initials = "".join(part[0].upper() for part in (user.get("full_name") or "U").split()[:2]) or "U"
    pending_avatar: dict[str, str | None] = {"path": None}
    picker = create_file_picker(page)

    card_shadow = css_shadow(0.22 if dark else 0.05, 22, 6)
    card_border = ft.border.all(1, "#334155" if dark else pal["BORDER_LIGHT"])
    input_bg = pal["BG_SUB"] if dark else "#F8FAFC"
    input_border = "#334155" if dark else "#CBD5E1"
    focus_teal = "#14B8A6" if dark else "#0F766E"

    def _profile_input(
        label: str,
        value: str = "",
        hint_text: str = "",
        prefix_icon: object = None,
        password: bool = False,
        can_reveal_password: bool = False,
        disabled: bool = False,
    ) -> ft.TextField:
        return ft.TextField(
            label=label,
            value=value,
            hint_text=hint_text,
            prefix_icon=prefix_icon,
            password=password,
            can_reveal_password=can_reveal_password,
            disabled=disabled,
            expand=True,
            filled=True,
            fill_color=input_bg,
            bgcolor=input_bg,
            border_radius=10,
            border_color=input_border,
            border_width=1,
            focused_border_color=focus_teal,
            focused_border_width=2,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=14),
            text_size=14,
            color=pal["TEXT_PRIMARY"],
            cursor_color=focus_teal,
            label_style=ft.TextStyle(size=13.5, weight=ft.FontWeight.W_500, color=pal["TEXT_SECONDARY"]),
            hint_style=ft.TextStyle(size=13.5, color=pal["TEXT_MUTED"]),
        )

    primary_btn_style = ft.ButtonStyle(
        bgcolor="#0F766E",
        color="#FFFFFF",
        icon_color="#FFFFFF",
        padding=ft.padding.symmetric(horizontal=20, vertical=12),
        shape=ft.RoundedRectangleBorder(radius=10),
        text_style=ft.TextStyle(size=14, weight=ft.FontWeight.W_600),
    )

    def _section_card(content: ft.Control, padding: int = 24) -> ft.Container:
        return ft.Container(
            padding=padding,
            border_radius=16,
            bgcolor=pal["BG_CARD"],
            border=card_border,
            shadow=card_shadow,
            content=content,
        )

    # --- Avatar & Live Preview Controls ---
    avatar_inner = ft.Container(
        width=96,
        height=96,
        border_radius=48,
        bgcolor="#D1FAE5",
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=_avatar_image(user.get("avatar_url"), 96, initials, "#D1FAE5"),
    )
    avatar_feedback = ft.Text(
        "PNG, JPG, WebP · Tối đa 8 MB",
        size=11.5,
        color=pal["TEXT_MUTED"],
        text_align=ft.TextAlign.CENTER,
    )
    display_name_preview = ft.Text(
        user.get("full_name") or "Người dùng PigSkinTech",
        size=18,
        weight=ft.FontWeight.BOLD,
        color=pal["TEXT_PRIMARY"],
        text_align=ft.TextAlign.CENTER,
    )
    email_preview = ft.Text(
        user.get("email") or "",
        size=13,
        color=pal["TEXT_SECONDARY"],
        text_align=ft.TextAlign.CENTER,
    )

    # --- Form Inputs ---
    full_name = _profile_input(
        label="Tên hiển thị",
        value=user.get("full_name") or "",
        hint_text="VD: Nguyễn Văn Nông",
        prefix_icon=ft.Icons.PERSON_OUTLINE_ROUNDED,
    )
    email_field = _profile_input(
        label="Email đăng nhập",
        value=user.get("email") or "",
        hint_text="tenban@example.com",
        prefix_icon=ft.Icons.MAIL_OUTLINE_ROUNDED,
        disabled=not can_change_email,
    )
    phone_field = _profile_input(
        label="Số điện thoại",
        value=user.get("phone") or "",
        hint_text="VD: 0912 345 678",
        prefix_icon=ft.Icons.PHONE_OUTLINED,
    )
    farm_field = _profile_input(
        label="Tên trang trại / Khu chuồng",
        value=user.get("farm_name") or "",
        hint_text="VD: Trại An Phú - Khu A",
        prefix_icon=ft.Icons.HOME_WORK_OUTLINED,
    )

    current_password = _profile_input(
        label="Mật khẩu hiện tại",
        hint_text="Nhập mật khẩu đang sử dụng",
        prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
        password=True,
        can_reveal_password=True,
    )
    new_password = _profile_input(
        label="Mật khẩu mới (ít nhất 8 ký tự)",
        hint_text="Tối thiểu 8 ký tự",
        prefix_icon=ft.Icons.LOCK_RESET_ROUNDED,
        password=True,
        can_reveal_password=True,
    )
    confirm_password = _profile_input(
        label="Nhập lại mật khẩu mới",
        hint_text="Xác nhận mật khẩu mới",
        prefix_icon=ft.Icons.LOCK_ROUNDED,
        password=True,
        can_reveal_password=True,
    )

    # --- Handlers (Preserve existing validated logic) ---
    def on_avatar_selected(paths: list[str]):
        source = Path(paths[0])
        try:
            if source.stat().st_size > MAX_AVATAR_BYTES:
                raise ValueError("Ảnh đại diện cần nhỏ hơn 8 MB.")
            with Image.open(source) as image:
                image.verify()
            previous_pending = pending_avatar["path"]
            stored_path = _store_avatar(source, user_id)
        except (OSError, ValueError) as exc:
            show_snack(page, str(exc) or "Không đọc được ảnh này.", "#DC2626")
            return
        pending_avatar["path"] = stored_path
        avatar_inner.content = _avatar_image(stored_path, 96, initials, "#D1FAE5")
        avatar_feedback.value = "Đã chọn ảnh mới · bấm 'Lưu thông tin cá nhân' để áp dụng."
        avatar_feedback.color = "#10B981" if dark else "#059669"
        if previous_pending:
            _remove_managed_avatar(previous_pending)
        page.update()

    async def open_avatar_picker():
        await pick_image_files(picker, allow_multiple=False, on_picked=on_avatar_selected)

    def choose_avatar(e):
        if hasattr(page, "run_task"):
            page.run_task(open_avatar_picker)
        else:
            show_snack(page, "Phiên bản Flet hiện tại không hỗ trợ chọn ảnh đại diện.", "#DC2626")

    def save_personal_info(e):
        saved_avatar: str | None = None
        try:
            saved_avatar = pending_avatar["path"]
            updated = update_user_profile(
                user_id,
                full_name.value or "",
                saved_avatar,
                email=email_field.value or "",
                phone=phone_field.value or "",
                farm_name=farm_field.value or "",
            )
            pending_avatar["path"] = None
            save_session_user(page, updated)
            display_name_preview.value = updated.get("full_name") or display_name_preview.value
            email_preview.value = updated.get("email") or email_preview.value
            if saved_avatar:
                _remove_managed_avatar(user.get("avatar_url"))
            show_snack(page, "Đã cập nhật hồ sơ cá nhân thành công.", "#059669")
            page.go(role_home_route(updated.get("role") or role))
        except (ValueError, OSError) as exc:
            show_snack(page, str(exc), "#DC2626")
        except Exception as exc:
            show_snack(page, f"Không thể lưu hồ sơ: {exc}", "#DC2626")

    def save_new_password(e):
        if new_password.value != confirm_password.value:
            show_snack(page, "Mật khẩu mới và phần xác nhận chưa khớp.", "#DC2626")
            return
        try:
            change_user_password(user_id, current_password.value or "", new_password.value or "")
            current_password.value = ""
            new_password.value = ""
            confirm_password.value = ""
            show_snack(page, "Đã đổi mật khẩu. Lần đăng nhập sau hãy dùng mật khẩu mới.", "#059669")
            page.update()
        except ValueError as exc:
            show_snack(page, str(exc), "#DC2626")
        except Exception as exc:
            show_snack(page, f"Không thể đổi mật khẩu: {exc}", "#DC2626")

    # --- LEFT COLUMN (width=330): Profile Identity Card ---
    avatar_ring_bg = pal["BG_CARD"] if dark else "#FFFFFF"
    avatar_stack = ft.Stack(
        width=104,
        height=104,
        controls=[
            ft.Container(
                width=104,
                height=104,
                border_radius=52,
                bgcolor=avatar_ring_bg,
                padding=4,
                shadow=css_shadow(0.24 if dark else 0.10, 14, 4),
                alignment=ft.alignment.center,
                content=avatar_inner,
            ),
            ft.Container(
                right=2,
                bottom=2,
                width=32,
                height=32,
                border_radius=16,
                bgcolor="#0F766E",
                border=ft.border.all(2.5, avatar_ring_bg),
                alignment=ft.alignment.center,
                ink=True,
                tooltip="Đổi ảnh đại diện",
                on_click=choose_avatar,
                content=ft.Icon(ft.Icons.CAMERA_ALT_ROUNDED, size=15, color="#FFFFFF"),
            ),
        ],
    )

    banner_and_avatar = ft.Stack(
        height=146,
        controls=[
            ft.Container(
                height=92,
                border_radius=ft.border_radius.only(top_left=15, top_right=15),
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                    colors=["#065F46", "#0D9488"] if dark else ["#0F766E", "#10B981"],
                ),
            ),
            ft.Container(
                top=40,
                left=0,
                right=0,
                alignment=ft.alignment.top_center,
                content=avatar_stack,
            ),
        ],
    )

    role_badge_fg = "#34D399" if role == "user" else ("#38BDF8" if role == "expert" else "#C084FC")
    role_badge_fg_light = "#047857" if role == "user" else ("#0369A1" if role == "expert" else "#7E22CE")
    role_badge_pill = ft.Container(
        padding=ft.padding.symmetric(horizontal=14, vertical=5),
        border_radius=20,
        bgcolor=ft.Colors.with_opacity(0.16 if dark else 0.12, role_color),
        border=ft.border.all(1, ft.Colors.with_opacity(0.45, role_color)),
        content=ft.Row(
            [
                ft.Icon(
                    ft.Icons.VERIFIED_USER_ROUNDED if role == "admin" else (
                        ft.Icons.MEDICAL_SERVICES_ROUNDED if role == "expert" else ft.Icons.AGRICULTURE_ROUNDED
                    ),
                    size=14,
                    color=role_badge_fg if dark else role_badge_fg_light,
                ),
                ft.Text(
                    role_label,
                    size=12.5,
                    weight=ft.FontWeight.BOLD,
                    color=role_badge_fg if dark else role_badge_fg_light,
                ),
            ],
            spacing=6,
            tight=True,
        ),
    )

    def _info_item(leading: ft.Control, title: str, value: str, value_color: str | None = None) -> ft.Control:
        return ft.Row(
            [
                ft.Container(
                    width=32,
                    height=32,
                    border_radius=8,
                    bgcolor=pal["BG_SUB"],
                    alignment=ft.alignment.center,
                    content=leading,
                ),
                ft.Column(
                    [
                        ft.Text(title, size=11.5, color=pal["TEXT_MUTED"]),
                        ft.Text(
                            value,
                            size=13,
                            weight=ft.FontWeight.W_600,
                            color=value_color or pal["TEXT_PRIMARY"],
                        ),
                    ],
                    spacing=1,
                    tight=True,
                    expand=True,
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    left_identity_card = ft.Container(
        width=330,
        border_radius=16,
        bgcolor=pal["BG_CARD"],
        border=card_border,
        shadow=card_shadow,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Column(
            [
                banner_and_avatar,
                ft.Container(
                    padding=ft.padding.only(left=20, right=20, top=6, bottom=22),
                    content=ft.Column(
                        [
                            display_name_preview,
                            email_preview,
                            ft.Container(padding=ft.padding.only(top=4, bottom=6), content=role_badge_pill),
                            ft.OutlinedButton(
                                "Chọn ảnh đại diện",
                                icon=ft.Icons.ADD_A_PHOTO_OUTLINED,
                                style=ft.ButtonStyle(
                                    padding=ft.padding.symmetric(horizontal=14, vertical=8),
                                    shape=ft.RoundedRectangleBorder(radius=10),
                                    text_style=ft.TextStyle(size=12.5, weight=ft.FontWeight.W_600),
                                ),
                                on_click=choose_avatar,
                            ),
                            avatar_feedback,
                            ft.Divider(height=20, color=pal["BORDER_LIGHT"]),
                            ft.Column(
                                [
                                    ft.Text(
                                        "THÔNG TIN TÀI KHOẢN",
                                        size=11,
                                        weight=ft.FontWeight.BOLD,
                                        color=pal["TEXT_MUTED"],
                                    ),
                                    _info_item(
                                        ft.Icon(
                                            ft.Icons.CLOUD_DONE_OUTLINED if auth_provider == "google" else ft.Icons.BADGE_OUTLINED,
                                            size=17,
                                            color="#0284C7" if not dark else "#38BDF8",
                                        ),
                                        "Phương thức đăng nhập",
                                        "Google OAuth 2.0" if auth_provider == "google" else "Tài khoản PigSkinTech",
                                    ),
                                    _info_item(
                                        ft.Icon(ft.Icons.SHIELD_ROUNDED, size=17, color="#10B981"),
                                        "Trạng thái bảo mật",
                                        "Mật khẩu mã hóa PBKDF2-SHA256",
                                        value_color="#34D399" if dark else "#059669",
                                    ),
                                    _info_item(
                                        ft.Container(width=10, height=10, border_radius=5, bgcolor="#10B981"),
                                        "Trạng thái hoạt động",
                                        "Đang hoạt động",
                                        value_color="#34D399" if dark else "#059669",
                                    ),
                                ],
                                spacing=12,
                                tight=True,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        tight=True,
                    ),
                ),
            ],
            spacing=0,
            tight=True,
        ),
    )

    # --- RIGHT COLUMN (expand=True): Card 1 (Personal Info) + Card 2 (Security & Password) ---
    def _card_header(icon_name: object, title: str, subtitle: str, icon_color: str, soft_bg: str) -> ft.Control:
        return ft.Row(
            [
                ft.Container(
                    width=40,
                    height=40,
                    border_radius=10,
                    bgcolor=soft_bg,
                    alignment=ft.alignment.center,
                    content=ft.Icon(icon_name, color=icon_color, size=21),
                ),
                ft.Column(
                    [
                        ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=pal["TEXT_PRIMARY"]),
                        ft.Text(subtitle, size=13, color=pal["TEXT_SECONDARY"]),
                    ],
                    spacing=2,
                    tight=True,
                    expand=True,
                ),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    personal_info_card = _section_card(
        content=ft.Column(
            [
                _card_header(
                    ft.Icons.PERSON_OUTLINE_ROUNDED,
                    "Thông tin hiển thị & Liên hệ",
                    "Cập nhật họ tên, email đăng nhập và thông tin trang trại để đồng bộ vào hồ sơ bệnh án.",
                    "#14B8A6" if dark else "#0F766E",
                    pal["SOFT_EMERALD"],
                ),
                ft.Divider(height=6, color=pal["BORDER_LIGHT"]),
                ft.Row([full_name, email_field], spacing=16),
                ft.Row([phone_field, farm_field], spacing=16),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=16, color=pal["TEXT_MUTED"]),
                        ft.Text(
                            (
                                "Email Google đang liên kết không thể đổi tại đây; hãy đổi email trong tài khoản Google."
                                if not can_change_email
                                else "Email mới sẽ dùng cho lần đăng nhập tiếp theo; lịch sử khám và chat vẫn được giữ nguyên."
                            ),
                            size=12.5,
                            color=pal["TEXT_MUTED"],
                            expand=True,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        ft.FilledButton(
                            "Lưu thông tin cá nhân",
                            icon=ft.Icons.SAVE_OUTLINED,
                            style=primary_btn_style,
                            on_click=save_personal_info,
                        )
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=16,
            tight=True,
        ),
    )

    password_security_card = _section_card(
        content=ft.Column(
            [
                _card_header(
                    ft.Icons.SHIELD_OUTLINED,
                    "Bảo mật & Đổi mật khẩu",
                    "Xác nhận mật khẩu hiện tại trước khi thiết lập mật khẩu mới cho tài khoản.",
                    "#34D399" if dark else "#059669",
                    pal["SOFT_EMERALD"],
                ),
                ft.Divider(height=6, color=pal["BORDER_LIGHT"]),
                ft.Row([current_password], spacing=16),
                ft.Row([new_password, confirm_password], spacing=16),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.TIPS_AND_UPDATES_OUTLINED, size=16, color=pal["TEXT_MUTED"]),
                        ft.Text(
                            "Nên kết hợp chữ hoa, chữ thường, chữ số và ký tự đặc biệt để tăng độ an toàn tài khoản.",
                            size=12.5,
                            color=pal["TEXT_MUTED"],
                            expand=True,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        ft.FilledButton(
                            "Cập nhật mật khẩu",
                            icon=ft.Icons.LOCK_RESET_ROUNDED,
                            style=primary_btn_style,
                            on_click=save_new_password,
                        )
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=16,
            tight=True,
        ),
    )

    right_forms_col = ft.Column(
        [
            personal_info_card,
            password_security_card,
        ],
        spacing=20,
        expand=True,
        tight=True,
    )

    # --- Page Header (size=24 BOLD) ---
    page_header = ft.Row(
        [
            ft.Column(
                [
                    ft.Text("Hồ sơ cá nhân", size=24, weight=ft.FontWeight.BOLD, color=pal["TEXT_PRIMARY"]),
                    ft.Text(
                        "Quản lý thông tin hiển thị, ảnh đại diện, liên hệ trang trại và bảo mật tài khoản của bạn.",
                        size=13.5,
                        color=pal["TEXT_SECONDARY"],
                    ),
                ],
                spacing=4,
                tight=True,
                expand=True,
            ),
            ft.Container(
                bgcolor=pal["BG_CARD"],
                border=card_border,
                padding=ft.padding.symmetric(horizontal=14, vertical=7),
                border_radius=20,
                content=ft.Row(
                    [
                        ft.Container(width=8, height=8, bgcolor=PRIMARY, border_radius=4),
                        ft.Text(role_label, size=13, color=pal["TEXT_PRIMARY"], weight=ft.FontWeight.W_600),
                    ],
                    spacing=7,
                    tight=True,
                ),
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    page_w = getattr(page, "width", None) or 1440
    max_frame_w = 1160 if (int(page_w) - 318) > 1160 else None

    inner_dashboard = ft.Container(
        width=max_frame_w,
        content=ft.Column(
            [
                page_header,
                ft.Row(
                    [
                        left_identity_card,
                        right_forms_col,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    spacing=24,
                ),
            ],
            spacing=20,
            tight=True,
        ),
    )

    return ft.Container(
        alignment=ft.alignment.top_center,
        content=inner_dashboard,
    )
