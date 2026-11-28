"""PigSkinTech AI Studio — Material 3 RBAC Desktop Application (User / Expert / Admin)."""
import flet as ft

from services.auth_service import (
    ensure_flet_compat,
    get_session_user,
    role_home_route,
    show_snack,
)
from services.store import initialize
from theme import BG_MAIN, PRIMARY, PRIMARY_DARK, get_theme_palette
from views.admin_view import build_admin_view
from views.auth_view import build_auth_view
from views.expert_view import build_expert_view
from views.user_view import build_user_view


def main(page: ft.Page):
    initialize()
    ensure_flet_compat(page)

    page.title = "PigSkinTech AI — Hệ thống Chẩn đoán & Thẩm định Bệnh Da Heo"
    page.padding = 0
    page.spacing = 0
    page.bgcolor = BG_MAIN
    page.fonts = {
        "Plus Jakarta Sans": "https://fonts.gstatic.com/s/plusjakartasans/v8/L0xTDF4xlVMF-BfR8bXMIjhGq3-cXbKDO1w.ttf",
        "Inter": "https://fonts.gstatic.com/s/inter/v18/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuLyfAZ9hiA.ttf",
    }
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=PRIMARY_DARK, font_family="Plus Jakarta Sans")
    page.dark_theme = ft.Theme(color_scheme_seed=PRIMARY, font_family="Plus Jakarta Sans")

    if hasattr(page, "window"):
        page.window.width = 1440
        page.window.height = 900
        page.window.min_width = 1100
        page.window.min_height = 720

    ROUTE_BUILDERS = {
        "/user": ("user", build_user_view),
        "/expert": ("expert", build_expert_view),
        "/admin": ("admin", build_admin_view),
    }

    def render_route(route: str):
        target = (route or "/login").strip()
        if target not in ("/login", "/user", "/expert", "/admin"):
            target = "/login"

        user = get_session_user(page)
        if target == "/login":
            page.route = "/login"
            page.controls.clear()
            page.add(build_auth_view(page))
            page.update()
            return

        if not user:
            show_snack(page, "Vui lòng đăng nhập để truy cập hệ thống.", "#C62828")
            render_route("/login")
            return

        required_role, builder = ROUTE_BUILDERS[target]
        actual_role = user.get("role", "user")
        if actual_role != required_role and actual_role != "admin":
            show_snack(
                page,
                f"Tài khoản quyền '{actual_role}' không có quyền truy cập '{target}'. Đã điều hướng về trang chính.",
                "#EF6C00",
            )
            target = role_home_route(actual_role)
            _, builder = ROUTE_BUILDERS[target]

        page.route = target
        page.bgcolor = get_theme_palette(page)["BG_MAIN"]
        page.controls.clear()
        page.add(builder(page, user))
        page.update()

    def go_to(route: str):
        render_route(route)

    page.go = go_to
    page.on_route_change = lambda e: render_route(getattr(e, "route", None) or page.route)

    render_route("/login")


if __name__ == "__main__":
    ensure_flet_compat()
    ft.app(target=main)
