"""
main.py — PigSkinResearchStudio Desktop
Chạy:  python main.py      (yêu cầu flet==0.28.3, xem requirements.txt)
"""
from __future__ import annotations

import flet as ft

import config
from components import safe_update, toast
from database.db_manager import DBManager
from views.dataset_version_view import DatasetVersionView
from views.image_explorer_view import ImageExplorerView
from views.inference_view import InferenceView
from views.overview_view import OverviewView
from views.training_runs_view import TrainingRunsView

NAV_ITEMS = [  # (key, nhãn, icon, icon khi chọn)
    ("overview", "Tổng quan", ft.Icons.DASHBOARD_OUTLINED, ft.Icons.DASHBOARD),
    ("images", "Kho ảnh", ft.Icons.PHOTO_LIBRARY_OUTLINED, ft.Icons.PHOTO_LIBRARY),
    ("datasets", "Dataset", ft.Icons.DATASET_OUTLINED, ft.Icons.DATASET),
    ("runs", "Huấn luyện", ft.Icons.MODEL_TRAINING_OUTLINED, ft.Icons.MODEL_TRAINING),
    ("inference", "Dự đoán", ft.Icons.BIOTECH_OUTLINED, ft.Icons.BIOTECH),
]


def build_theme(p: dict) -> ft.Theme:
    return ft.Theme(
        color_scheme_seed=config.THEME_SEED,
        color_scheme=ft.ColorScheme(
            primary=p["primary"], on_primary=p["on_primary"],
            primary_container=p["primary_container"], on_primary_container=p["on_primary_container"],
            secondary=p["secondary"], surface=p["surface"], on_surface=p["on_surface"],
            on_surface_variant=p["on_surface_variant"],
            surface_variant=p["surface_container_highest"],
            surface_container_high=p["surface_container_highest"],
            outline=p["outline"], outline_variant=p["outline_variant"], error=p["error"],
        ),
        visual_density=ft.VisualDensity.COMPACT,
        use_material3=True,
    )


def main(page: ft.Page) -> None:
    settings = config.load_settings()
    page.title = "PigSkin Research Studio"
    page.window.width = 1480
    page.window.height = 920
    page.window.min_width = 1100
    page.window.min_height = 700
    page.padding = 0
    page.theme = build_theme(config.LIGHT_PALETTE)
    page.dark_theme = build_theme(config.DARK_PALETTE)
    page.theme_mode = ft.ThemeMode.DARK if settings.get("theme_mode") == "dark" else ft.ThemeMode.LIGHT

    db = DBManager(config.DB_PATH)
    views: dict[str, ft.Control] = {}
    current = {"key": "overview"}

    content = ft.Container(expand=True, padding=ft.padding.only(left=24, right=24, top=20, bottom=16))

    def on_data_changed() -> None:
        # Importer vừa ghi dữ liệu → các view khác sẽ tự nạp lại khi được mở (load() mỗi lần điều hướng).
        pass

    def get_view(key: str) -> ft.Control:
        if key not in views:
            views[key] = {
                "overview": lambda: OverviewView(page, db),
                "images": lambda: ImageExplorerView(page, db),
                "datasets": lambda: DatasetVersionView(page, db, on_data_changed),
                "runs": lambda: TrainingRunsView(page, db),
                "inference": lambda: InferenceView(page, db),
            }[key]()
        return views[key]

    def navigate(key: str) -> None:
        current["key"] = key
        view = get_view(key)
        content.content = view
        page.update()
        view.load()

    def on_nav_change(e) -> None:
        navigate(NAV_ITEMS[e.control.selected_index][0])

    def toggle_theme(e) -> None:
        dark = page.theme_mode != ft.ThemeMode.DARK
        page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
        theme_btn.icon = ft.Icons.LIGHT_MODE if dark else ft.Icons.DARK_MODE
        config.save_settings(theme_mode="dark" if dark else "light")
        page.update()

    theme_btn = ft.IconButton(
        ft.Icons.LIGHT_MODE if page.theme_mode == ft.ThemeMode.DARK else ft.Icons.DARK_MODE,
        tooltip="Đổi giao diện sáng/tối", on_click=toggle_theme,
    )

    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=88,
        group_alignment=-0.85,
        leading=ft.Container(
            padding=ft.padding.only(top=18, bottom=10),
            content=ft.Column([
                ft.Container(
                    width=44, height=44, border_radius=12, alignment=ft.alignment.center,
                    gradient=ft.LinearGradient(colors=["#1F8A8A", "#3B82C4"],
                                               begin=ft.alignment.top_left, end=ft.alignment.bottom_right),
                    content=ft.Icon(ft.Icons.PETS, color=ft.Colors.WHITE, size=24),
                ),
                ft.Text("PigSkin\nStudio", size=10, weight=ft.FontWeight.W_700, text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
        ),
        trailing=ft.Container(theme_btn, padding=ft.padding.only(top=24)),
        destinations=[
            ft.NavigationRailDestination(icon=icon, selected_icon=sel_icon, label=label)
            for _, label, icon, sel_icon in NAV_ITEMS
        ],
        on_change=on_nav_change,
    )

    splash_text = ft.Text("Đang khởi tạo cơ sở dữ liệu…", size=13)
    splash_bar = ft.ProgressBar(width=360, bar_height=6, border_radius=3)
    content.content = ft.Container(
        alignment=ft.alignment.center, expand=True,
        content=ft.Column([ft.Icon(ft.Icons.SCIENCE, size=48, color=ft.Colors.PRIMARY), splash_text, splash_bar],
                          horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER,
                          spacing=14),
    )

    page.add(ft.Row([rail, ft.VerticalDivider(width=1), content], expand=True, spacing=0))

    def bootstrap() -> None:
        try:
            missing = db.initialize()
            if missing:
                raise RuntimeError(f"Schema thiếu: {missing}")
            seeded = False
            if db.is_empty():
                def progress(frac: float, msg: str) -> None:
                    splash_bar.value = frac
                    splash_text.value = msg
                    safe_update(splash_bar, splash_text)
                db.seed_mock_data(progress)
                seeded = True
        except Exception as ex:  # noqa: BLE001
            splash_text.value = f"Không khởi tạo được CSDL tại {config.DB_PATH}: {ex}"
            splash_bar.visible = False
            safe_update(splash_text, splash_bar)
            return
        navigate("overview")
        if seeded:
            toast(page, "CSDL trống → đã tạo dữ liệu mẫu 2.017 ảnh để demo. Dùng Importer để nạp dữ liệu thật.", "info")

    page.run_thread(bootstrap)


if __name__ == "__main__":
    ft.app(target=main)
