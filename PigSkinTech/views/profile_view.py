"""Shared account and security settings for every PigSkinTech role."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import flet as ft
from PIL import Image, ImageOps

from services.auth_service import (
    ROLE_LABELS,
    create_file_picker,
    make_image,
    pick_image_files,
    role_home_route,
    save_session_user,
    show_snack,
    tech_banner,
    tech_card,
    theme_tokens,
)
from services.store import change_user_password, update_user_profile
from theme import css_input


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
                content=ft.Text(initials, size=size * 0.27, weight=ft.FontWeight.BOLD, color="#047857"),
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
        content=ft.Text(initials, size=size * 0.27, weight=ft.FontWeight.BOLD, color="#047857"),
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
    user_id = int(user.get("user_id") or user.get("id"))
    role = str(user.get("role") or "user")
    auth_provider = str(user.get("auth_provider") or "local")
    can_change_email = auth_provider != "google" or bool(user.get("google_sub"))
    initials = "".join(part[0].upper() for part in (user.get("full_name") or "U").split()[:2]) or "U"
    pending_avatar: dict[str, str | None] = {"path": None}
    picker = create_file_picker(page)

    avatar = ft.Container(
        width=96,
        height=96,
        border_radius=48,
        bgcolor="#D1FAE5",
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=_avatar_image(user.get("avatar_url"), 96, initials, "#D1FAE5"),
    )
    avatar_feedback = ft.Text(
        "Chọn ảnh rồi bấm Lưu thông tin cá nhân để áp dụng.",
        size=11.5,
        color=t["MUTED"],
        text_align=ft.TextAlign.CENTER,
    )
    full_name = css_input(
        label="Tên hiển thị",
        value=user.get("full_name") or "",
        prefix_icon=ft.Icons.PERSON_OUTLINE_ROUNDED,
        expand=True,
        page=page,
    )
    email_field = css_input(
        label="Email đăng nhập",
        value=user.get("email") or "",
        hint_text="tenban@example.com",
        prefix_icon=ft.Icons.MAIL_OUTLINE_ROUNDED,
        expand=True,
        page=page,
    )
    email_field.disabled = not can_change_email

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
        avatar.content = _avatar_image(stored_path, 96, initials, "#D1FAE5")
        avatar_feedback.value = "Đã chọn ảnh mới · bấm Lưu thông tin cá nhân để lưu vào tài khoản."
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
            )
            pending_avatar["path"] = None
            save_session_user(page, updated)
            if saved_avatar:
                _remove_managed_avatar(user.get("avatar_url"))
            show_snack(page, "Đã cập nhật hồ sơ cá nhân.", "#059669")
            page.go(role_home_route(updated.get("role") or role))
        except (ValueError, OSError) as exc:
            show_snack(page, str(exc), "#DC2626")
        except Exception as exc:
            show_snack(page, f"Không thể lưu hồ sơ: {exc}", "#DC2626")

    current_password = css_input(
        label="Mật khẩu hiện tại",
        password=True,
        can_reveal_password=True,
        prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
        expand=True,
        page=page,
    )
    new_password = css_input(
        label="Mật khẩu mới (ít nhất 8 ký tự)",
        password=True,
        can_reveal_password=True,
        prefix_icon=ft.Icons.LOCK_RESET_ROUNDED,
        expand=True,
        page=page,
    )
    confirm_password = css_input(
        label="Nhập lại mật khẩu mới",
        password=True,
        can_reveal_password=True,
        prefix_icon=ft.Icons.LOCK_ROUNDED,
        expand=True,
        page=page,
    )

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

    profile_card = tech_card(
        page=page,
        padding=22,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                avatar,
                                ft.OutlinedButton(
                                    "Chọn ảnh",
                                    icon=ft.Icons.ADD_A_PHOTO_OUTLINED,
                                    on_click=choose_avatar,
                                ),
                                ft.Text("PNG, JPG hoặc WebP · tối đa 8 MB", size=11.5, color=t["MUTED"]),
                                avatar_feedback,
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                        ),
                        ft.Column(
                            [
                                full_name,
                                email_field,
                                ft.Text(
                                    "Email Google đang liên kết không thể đổi tại đây; hãy đổi email trong tài khoản Google."
                                    if not can_change_email
                                    else "Email mới sẽ được dùng cho lần đăng nhập tiếp theo; lịch sử khám và chat vẫn được giữ.",
                                    size=11.5,
                                    color=t["MUTED"],
                                ),
                                ft.Row(
                                    [
                                        ft.Text("Vai trò", size=12, color=t["MUTED"]),
                                        ft.Text(ROLE_LABELS.get(role, role), size=13, weight=ft.FontWeight.W_600, color=t["TEXT"]),
                                        ft.Text("·", color=t["MUTED"]),
                                        ft.Text(
                                            "Đăng nhập Google" if user.get("auth_provider") == "google" else "Tài khoản PigSkinTech",
                                            size=12,
                                            color=t["MUTED"],
                                        ),
                                    ],
                                    spacing=8,
                                    wrap=True,
                                ),
                            ],
                            spacing=14,
                            expand=True,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=24,
                ),
                ft.Row(
                    [
                        ft.FilledButton(
                            "Lưu thông tin cá nhân",
                            icon=ft.Icons.SAVE_OUTLINED,
                            on_click=save_personal_info,
                        )
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=18,
        ),
    )

    password_card = tech_card(
        page=page,
        padding=22,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.SHIELD_OUTLINED, color=t["EMERALD"], size=22),
                        ft.Column(
                            [
                                ft.Text("Đổi mật khẩu", size=17, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                                ft.Text("Xác nhận mật khẩu hiện tại trước khi thay đổi.", size=12.5, color=t["MUTED"]),
                            ],
                            spacing=3,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                ),
                ft.Row([current_password, new_password], spacing=12),
                ft.Row([confirm_password], spacing=12),
                ft.Row(
                    [
                        ft.FilledButton(
                            "Cập nhật mật khẩu",
                            icon=ft.Icons.LOCK_RESET_ROUNDED,
                            on_click=save_new_password,
                        )
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=14,
        ),
    )

    return ft.Column(
        [
            tech_banner(
                "Hồ sơ cá nhân",
                "Quản lý thông tin hiển thị, ảnh đại diện và bảo mật tài khoản của bạn.",
                badge_text=ROLE_LABELS.get(role, role),
                page=page,
            ),
            profile_card,
            password_card,
        ],
        spacing=18,
        expand=True,
    )
