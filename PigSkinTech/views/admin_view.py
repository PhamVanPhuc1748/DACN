"""Admin Role View (/admin - Quản trị hệ thống): System Dashboard, Full-Width User & RBAC DataTable, AI & Classes CRUD."""
import flet as ft

from services.auth_service import (
    build_role_shell,
    close_dialog,
    ensure_flet_compat,
    export_inspections_csv,
    header_stat_pill,
    kpi_stat_card,
    make_dropdown,
    open_dialog,
    show_snack,
    tech_banner,
    tech_card,
    theme_tokens,
)
from services.clinical_widgets import (
    build_clinical_charts_section,
    build_disease_catalog_crud_card,
    open_disease_editor_modal,
)
from services.config_store import read_settings, save_settings
from services.project_data import (
    active_run,
    display_class,
    list_model_runs,
    load_classes_config,
    set_active_checkpoint,
)
from services.store import (
    create_user_account,
    get_db_status,
    get_system_stats,
    list_users,
    recent,
    test_sqlserver_connection,
    toggle_user_lock,
    update_user_role,
)
from theme import PRIMARY, css_input, make_smooth_animation


def build_admin_view(page: ft.Page, user: dict) -> ft.Control:
    ensure_flet_compat(page)

    # Tab 1: System Dashboard
    def build_dashboard_tab():
        t = theme_tokens(page)
        stats = get_system_stats()
        total_ins = max(1, stats["total_inspections"])
        dist = stats["distribution"]

        kpi_cards = ft.ResponsiveRow(
            [
                kpi_stat_card(
                    "Tổng số người dùng",
                    str(stats["total_users"]),
                    "Google OAuth & Local",
                    ft.Icons.PEOPLE_ALT_ROUNDED,
                    accent="#0284C7",
                    soft_bg=t["CYAN_SOFT"],
                    page=page,
                    col={"xs": 12, "sm": 6, "lg": 3},
                ),
                kpi_stat_card(
                    "Tổng số lượt chẩn đoán",
                    str(stats["total_inspections"]),
                    f"{stats['pending_count']} ca chờ duyệt",
                    ft.Icons.ANALYTICS_ROUNDED,
                    accent="#059669",
                    soft_bg=t["EMERALD_SOFT"],
                    page=page,
                    col={"xs": 12, "sm": 6, "lg": 3},
                ),
                kpi_stat_card(
                    "Tỷ lệ chính xác AI vs Chuyên gia",
                    f"{stats['ai_accuracy_vs_expert']:.1f}%",
                    f"Đồng thuận {stats['agreed_count']}/{stats['reviewed_count']} ca",
                    ft.Icons.VERIFIED_ROUNDED,
                    accent="#7C3AED",
                    soft_bg=t["PURPLE_SOFT"],
                    page=page,
                    col={"xs": 12, "sm": 6, "lg": 3},
                ),
                kpi_stat_card(
                    "Ảnh Dataset chuẩn hóa",
                    str(stats["curated_count"]),
                    "Sẵn sàng huấn luyện",
                    ft.Icons.DATASET_LINKED_ROUNDED,
                    accent="#D97706",
                    soft_bg=t["AMBER_SOFT"],
                    page=page,
                    col={"xs": 12, "sm": 6, "lg": 3},
                ),
            ],
            run_spacing=16,
            spacing=16,
        )

        dist_rows = []
        for cls_code, count in sorted(dist.items(), key=lambda x: x[1], reverse=True):
            ratio = count / total_ins
            dist_rows.append(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(f"{display_class(cls_code)} ({cls_code})", size=14, weight=ft.FontWeight.W_600, color=t["TEXT"], expand=True),
                                ft.Text(f"{count} ca ({ratio*100:.1f}%)", size=13.5, weight=ft.FontWeight.BOLD, color=t["EMERALD"]),
                            ]
                        ),
                        ft.ProgressBar(value=ratio, bar_height=8, color=t["EMERALD"], bgcolor=t["BORDER"]),
                    ],
                    spacing=5,
                )
            )

        dist_card = tech_card(
            page=page,
            expand=1,
            padding=24,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.BAR_CHART_ROUNDED, color=t["EMERALD"], size=22),
                            ft.Text("Phân bố các loại bệnh phát hiện trên toàn hệ thống", size=18, weight=ft.FontWeight.BOLD, color=t["TEXT"], expand=True),
                            ft.OutlinedButton(
                                "📥 Xuất Báo cáo CSV",
                                icon=ft.Icons.DOWNLOAD_ROUNDED,
                                on_click=lambda e: export_inspections_csv(page, recent(""), "BaoCao_ChanDoan_Admin"),
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Divider(height=10, color=t["BORDER"]),
                    *(dist_rows or [ft.Text("Chưa có dữ liệu chẩn đoán.", size=14, color=t["MUTED"])]),
                ],
                spacing=12,
            ),
        )

        cur_run = active_run() or {}
        metrics = cur_run.get("metrics") or {}
        per_class_f1 = metrics.get("per_class_f1") or {}
        test_per_class = (metrics.get("test_metrics") or {}).get("per_class") or {}
        classes_cfg = load_classes_config()
        f1_rows = []
        for cls_code, cls_meta in classes_cfg.items():
            raw_cls_m = test_per_class.get(cls_code) or {}
            f1_val = float(
                per_class_f1.get(cls_code)
                if cls_code in per_class_f1
                else (raw_cls_m.get("f1", 0.0) if isinstance(raw_cls_m, dict) else 0.0)
            )
            f1_rows.append(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    f"{cls_meta.get('name_vi', cls_code)} ({cls_code})",
                                    size=14,
                                    weight=ft.FontWeight.W_600,
                                    color=t["TEXT"],
                                    expand=True,
                                ),
                                ft.Text(f"F1: {f1_val*100:.1f}%", size=13, weight=ft.FontWeight.BOLD, color=t["CYAN"]),
                            ]
                        ),
                        ft.ProgressBar(value=min(1.0, max(0.0, f1_val)), bar_height=8, color=t["CYAN"], bgcolor=t["BORDER"]),
                    ],
                    spacing=4,
                )
            )

        real_acc = float(metrics.get("accuracy") or (metrics.get("test_metrics") or {}).get("accuracy") or 0.0)
        real_f1 = float(metrics.get("best_val_macro_f1") or metrics.get("macro_f1") or 0.0)
        arch_title = f"{cur_run.get('model_label', 'MobileNetV2')} ({cur_run.get('name', '')})"

        benchmark_card = tech_card(
            page=page,
            expand=1,
            padding=24,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.MEMORY_ROUNDED, color=t["CYAN"], size=22),
                            ft.Text(
                                f"Hiệu năng Thực tế: {arch_title} ({len(classes_cfg)} lớp)",
                                size=17,
                                weight=ft.FontWeight.BOLD,
                                color=t["TEXT"],
                                expand=True,
                            ),
                            ft.Container(
                                bgcolor=t["CYAN_SOFT"],
                                padding=ft.padding.symmetric(horizontal=12, vertical=5),
                                border_radius=10,
                                content=ft.Text(
                                    f"Test Acc: {real_acc*100:.1f}% • Val F1: {real_f1*100:.1f}%",
                                    size=12.5,
                                    weight=ft.FontWeight.W_600,
                                    color=t["CYAN"],
                                ),
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Divider(height=10, color=t["BORDER"]),
                    *f1_rows,
                ],
                spacing=12,
            ),
        )

        db_info = stats.get("db_status", {})
        admin_pills = [
            header_stat_pill("Người dùng", str(stats["total_users"]), ft.Icons.PEOPLE_ALT_ROUNDED, "#0284C7", t["CYAN_SOFT"], db_info.get("engine", "SQL DB"), page=page),
            header_stat_pill("Lượt khám", f"{stats['total_inspections']} ca", ft.Icons.ANALYTICS_ROUNDED, "#059669", t["EMERALD_SOFT"], "Truy vấn SQL thật", page=page),
            header_stat_pill("Đồng thuận AI", f"{stats['ai_accuracy_vs_expert']:.1f}%", ft.Icons.VERIFIED_ROUNDED, "#D97706", t["AMBER_SOFT"], f"{stats['agreed_count']}/{stats['reviewed_count']} ca duyệt", page=page),
        ]

        return [
            tech_banner(
                "Tổng quan Quản trị Hệ thống",
                "Giám sát hoạt động toàn trang trại, độ chính xác chẩn đoán và kho dữ liệu chuẩn",
                pills=admin_pills,
                page=page,
            ),
            kpi_cards,
            build_clinical_charts_section(page, stats),
            ft.ResponsiveRow(
                [
                    ft.Container(col={"xs": 12, "lg": 6}, content=dist_card),
                    ft.Container(col={"xs": 12, "lg": 6}, content=benchmark_card),
                ],
                run_spacing=16,
                spacing=16,
            ),
        ]

    # Tab 2: User Management (Full-width DataTable + Search + Role Filter + Add User Modal)
    def build_users_tab():
        table_host = ft.Container(expand=True)
        search_field = css_input(
            label="Tìm kiếm theo họ tên, email hoặc username...",
            hint_text="Nhập từ khóa tìm kiếm...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            expand=True,
            page=page,
        )

        def handle_role_change(uid: int, new_role: str):
            update_user_role(uid, new_role)
            refresh_users()
            show_snack(page, f"Đã cập nhật phân quyền tài khoản ID #{uid} thành '{new_role.upper()}'!", "#0284C7")

        def handle_lock_toggle(uid: int):
            if uid == user.get("user_id"):
                show_snack(page, "Không thể tự khóa tài khoản Admin đang đăng nhập.", "#DC2626")
                return
            active = toggle_user_lock(uid)
            refresh_users()
            show_snack(
                page,
                f"Đã {'mở khóa' if active else 'khóa'} tài khoản ID #{uid}.",
                "#059669" if active else "#DC2626",
            )

        def open_add_user_dialog(e):
            new_name = css_input(label="Họ và tên người dùng", hint_text="VD: Nguyễn Văn B", prefix_icon=ft.Icons.BADGE_OUTLINED, page=page)
            new_email = css_input(label="Địa chỉ Email", hint_text="VD: b.nguyen@gmail.com", prefix_icon=ft.Icons.EMAIL_OUTLINED, page=page)
            new_pw = css_input(label="Mật khẩu khởi tạo", value="123456", prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED, page=page)
            new_role_dd = make_dropdown(
                "Phân quyền (RBAC)",
                "user",
                [
                    ("user", "User (Chăn nuôi)"),
                    ("expert", "Expert (Chuyên gia)"),
                    ("admin", "Admin (Quản trị)"),
                ],
                expand=True,
                page=page,
            )
            new_provider_dd = make_dropdown(
                "Phương thức xác thực",
                "google",
                [
                    ("google", "Google OAuth"),
                    ("local", "Local Account"),
                ],
                expand=True,
                page=page,
            )
            err_lbl = ft.Text("", size=13, color="#DC2626", visible=False)
            dlg = ft.AlertDialog(modal=True)

            def save_new_user(ev):
                try:
                    created = create_user_account(
                        email=new_email.value or "",
                        full_name=new_name.value or "",
                        role=new_role_dd.value or "user",
                        auth_provider=new_provider_dd.value or "google",
                        password=new_pw.value or "123456",
                    )
                    close_dialog(page, dlg)
                    refresh_users()
                    show_snack(page, f"Đã tạo tài khoản '{created['email']}' ({created['role'].upper()})!", "#059669")
                except ValueError as err:
                    err_lbl.value = str(err)
                    err_lbl.visible = True
                    page.update()

            dlg.title = ft.Row(
                [
                    ft.Icon(ft.Icons.PERSON_ADD_ALT_1_ROUNDED, color="#059669", size=22),
                    ft.Text("Thêm tài khoản mới vào hệ thống", size=18, weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            )
            dlg.content = ft.Container(
                width=460,
                content=ft.Column(
                    [
                        new_name,
                        new_email,
                        ft.Row([new_role_dd, new_provider_dd], spacing=10),
                        new_pw,
                        err_lbl,
                    ],
                    spacing=12,
                    tight=True,
                ),
            )
            dlg.actions = [
                ft.TextButton("Hủy", on_click=lambda ev: close_dialog(page, dlg)),
                ft.FilledButton("Tạo tài khoản", icon=ft.Icons.CHECK_ROUNDED, on_click=save_new_user),
            ]
            open_dialog(page, dlg)

        users_header_host = ft.Container()

        def refresh_users(e=None):
            t = theme_tokens(page)
            role_f = role_filter.value or "all"
            q_str = search_field.value or ""
            accounts = list_users(role_f, q_str)
            all_accounts = list_users("all", "")
            active_total = sum(1 for a in all_accounts if int(a.get("is_active") or 0) == 1)
            google_total = sum(1 for a in all_accounts if a.get("auth_provider") == "google")

            users_pills = [
                header_stat_pill("Tổng tài khoản", str(len(all_accounts)), ft.Icons.PEOPLE_ALT_ROUNDED, "#0284C7", t["CYAN_SOFT"], "Toàn hệ thống", page=page),
                header_stat_pill("Đang hoạt động", str(active_total), ft.Icons.VERIFIED_USER_ROUNDED, "#059669", t["EMERALD_SOFT"], "Cấp quyền RBAC", page=page),
                header_stat_pill("Google OAuth", str(google_total), ft.Icons.CLOUD_DONE_ROUNDED, "#D97706", t["AMBER_SOFT"], "Xác thực nhanh", page=page),
            ]
            users_header_host.content = tech_banner(
                "Quản lý Người dùng & Phân quyền",
                "Quản lý danh sách tài khoản Google OAuth và Local, tìm kiếm, khóa/mở khóa và cấp quyền truy cập",
                pills=users_pills,
                page=page,
            )
            rows = []
            for acc in accounts:
                uid = int(acc["id"])
                is_google = acc.get("auth_provider") == "google"
                is_active = int(acc.get("is_active") or 0) == 1
                r_code = acc.get("role", "user")

                provider_chip = ft.Container(
                    bgcolor=t["CYAN_SOFT"] if is_google else t["SUB_SURFACE"],
                    border=ft.border.all(1, "#38BDF8" if is_google else t["BORDER"]),
                    padding=ft.padding.symmetric(horizontal=10, vertical=5),
                    border_radius=12,
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.CLOUD_DONE_ROUNDED if is_google else ft.Icons.COMPUTER_ROUNDED,
                                size=15,
                                color=t["CYAN"] if is_google else t["MUTED"],
                            ),
                            ft.Text(
                                "Google OAuth" if is_google else "Local Account",
                                size=12.5,
                                color=t["CYAN"] if is_google else t["TEXT"],
                                weight=ft.FontWeight.W_600,
                            ),
                        ],
                        spacing=5,
                        tight=True,
                    ),
                )

                status_chip = ft.Container(
                    bgcolor=t["EMERALD_SOFT"] if is_active else t["RED_SOFT"],
                    border=ft.border.all(1, "#10B981" if is_active else "#F87171"),
                    padding=ft.padding.symmetric(horizontal=10, vertical=5),
                    border_radius=12,
                    content=ft.Text(
                        "Hoạt động" if is_active else "Đã khóa",
                        size=12.5,
                        color=t["EMERALD"] if is_active else t["RED"],
                        weight=ft.FontWeight.W_600,
                    ),
                )

                role_dd = make_dropdown(
                    label="",
                    value=r_code,
                    options=[
                        ("user", "User (Chăn nuôi)"),
                        ("expert", "Expert (Chuyên gia)"),
                        ("admin", "Admin (Quản trị)"),
                    ],
                    on_change=lambda ev, u_id=uid: handle_role_change(u_id, ev.control.value),
                    width=220,
                    content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    page=page,
                )

                lock_btn = ft.OutlinedButton(
                    "Khóa" if is_active else "Mở khóa",
                    icon=ft.Icons.LOCK_OUTLINE_ROUNDED if is_active else ft.Icons.LOCK_OPEN_ROUNDED,
                    on_click=lambda ev, u_id=uid: handle_lock_toggle(u_id),
                )

                rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(f"#{uid}", size=13.5, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
                            ft.DataCell(ft.Text(acc.get("full_name", ""), size=14, weight=ft.FontWeight.W_600, color=t["TEXT"])),
                            ft.DataCell(ft.Text(acc.get("email", ""), size=13.5, color=t["SECONDARY"])),
                            ft.DataCell(provider_chip),
                            ft.DataCell(ft.Container(width=220, padding=ft.padding.symmetric(vertical=4), content=role_dd)),
                            ft.DataCell(status_chip),
                            ft.DataCell(lock_btn),
                        ]
                    )
                )

            table = ft.DataTable(
                width=float("inf"),
                expand=True,
                column_spacing=26,
                horizontal_margin=16,
                data_row_min_height=58,
                data_row_max_height=66,
                heading_row_height=50,
                heading_row_color=t["SUB_SURFACE"],
                columns=[
                    ft.DataColumn(ft.Text("ID", size=13.5, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
                    ft.DataColumn(ft.Text("Họ và tên", size=13.5, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
                    ft.DataColumn(ft.Text("Email đăng nhập", size=13.5, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
                    ft.DataColumn(ft.Text("Phương thức", size=13.5, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
                    ft.DataColumn(ft.Text("Phân quyền (RBAC)", size=13.5, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
                    ft.DataColumn(ft.Text("Trạng thái", size=13.5, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
                    ft.DataColumn(ft.Text("Thao tác", size=13.5, weight=ft.FontWeight.BOLD, color=t["TEXT"])),
                ],
                rows=rows,
            )
            table_host.content = ft.Row([table], expand=True)
            page.update()

        role_filter = make_dropdown(
            "Lọc theo vai trò (Role)",
            "all",
            [
                ("all", "Tất cả vai trò"),
                ("user", "User (Chăn nuôi)"),
                ("expert", "Expert (Chuyên gia)"),
                ("admin", "Admin (Quản trị)"),
            ],
            on_change=refresh_users,
            width=240,
            page=page,
        )
        search_field.on_change = refresh_users
        refresh_users()

        toolbar_card = tech_card(
            page=page,
            padding=18,
            content=ft.Row(
                [
                    search_field,
                    role_filter,
                    ft.OutlinedButton(
                        "📥 Xuất Báo cáo CSV",
                        icon=ft.Icons.DOWNLOAD_ROUNDED,
                        on_click=lambda e: export_inspections_csv(page, recent(""), "BaoCao_HeThong_Admin"),
                    ),
                    ft.FilledButton(
                        "+ Thêm tài khoản mới",
                        icon=ft.Icons.PERSON_ADD_ALT_1_ROUNDED,
                        on_click=open_add_user_dialog,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        return [
            users_header_host,
            toolbar_card,
            tech_card(
                page=page,
                padding=18,
                content=ft.Row([table_host], expand=True),
            ),
        ]

    # Tab 3: AI & Classes Config
    def build_config_tab():
        t = theme_tokens(page)
        runs = list_model_runs()
        cur_run = active_run()
        cur_ckpt = str(cur_run["checkpoint"]) if cur_run else ""
        run_options = [(r["checkpoint"], f"{r['name']} • {r['model']} ({r['checkpoint']})") for r in runs]
        if not run_options and cur_ckpt:
            run_options = [(cur_ckpt, cur_ckpt)]

        custom_ckpt_field = css_input(
            label="Đường dẫn trọng số mô hình đang kích hoạt",
            value=cur_ckpt,
            prefix_icon=ft.Icons.FOLDER_SPECIAL_OUTLINED,
            expand=True,
            page=page,
        )

        def on_select_run(e):
            custom_ckpt_field.value = run_dropdown.value or ""
            page.update()

        run_dropdown = make_dropdown(
            "Chọn phiên bản mô hình huấn luyện",
            cur_ckpt if any(k == cur_ckpt for k, _ in run_options) else (run_options[0][0] if run_options else ""),
            run_options,
            on_change=on_select_run,
            expand=True,
            page=page,
        )

        def handle_activate_model(e):
            try:
                info = set_active_checkpoint(custom_ckpt_field.value)
                show_snack(page, f"Đã kích hoạt trọng số mô hình: {info.get('checkpoint')}", "#059669")
            except Exception as err:
                show_snack(page, str(err), "#DC2626")

        config_header_host = ft.Container()

        def refresh_config_header():
            cur_t = theme_tokens(page)
            latest = load_classes_config()
            urgent_cnt = sum(1 for v in latest.values() if v.get("danger_level") in ("Cao", "Khẩn cấp"))
            config_pills = [
                header_stat_pill("Phiên bản AI", str(len(runs) or 1), ft.Icons.MEMORY_ROUNDED, "#0284C7", cur_t["CYAN_SOFT"], "Đang kích hoạt", page=page),
                header_stat_pill("Nhóm bệnh lý", str(len(latest)), ft.Icons.MEDICAL_SERVICES_ROUNDED, "#059669", cur_t["EMERALD_SOFT"], "Danh mục chuẩn", page=page),
                header_stat_pill("Mức nguy hiểm cao", str(urgent_cnt), ft.Icons.WARNING_AMBER_ROUNDED, "#DC2626", cur_t["RED_SOFT"], "Cần giám sát", page=page),
            ]
            config_header_host.content = tech_banner(
                "Quản lý Mô hình AI & Danh mục Bệnh lý",
                "Chuyển đổi phiên bản trọng số Trí tuệ nhân tạo PigSkin AI và cập nhật trực tiếp phác đồ điều trị chuẩn",
                pills=config_pills,
                page=page,
            )

        refresh_config_header()

        model_card = tech_card(
            page=page,
            padding=24,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.MEMORY_ROUNDED, color=t["EMERALD"], size=22),
                            ft.Text("1. Quản lý Trọng số Mô hình AI Đang Kích hoạt", size=18, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                        ],
                        spacing=8,
                    ),
                    ft.Row([run_dropdown]),
                    ft.Row(
                        [
                            custom_ckpt_field,
                            ft.FilledButton(
                                "Kích hoạt Trọng số",
                                icon=ft.Icons.CHECK_CIRCLE_ROUNDED,
                                on_click=handle_activate_model,
                            ),
                        ],
                        spacing=10,
                    ),
                ],
                spacing=12,
            ),
        )

        crud_card = build_disease_catalog_crud_card(
            page=page,
            title_text="2. Quản lý Danh mục Bệnh lý & Phác đồ Điều trị Mặc định",
            on_changed=refresh_config_header,
        )

        return [
            config_header_host,
            model_card,
            crud_card,
        ]

    # Tab 4: System Settings (SQL Server, Google OAuth 2.0 & AI Chatbot)
    def build_system_settings_tab():
        t = theme_tokens(page)
        cfg = read_settings()
        db_stat = get_db_status()

        db_engine_dd = make_dropdown(
            "Database Engine",
            cfg.get("DATABASE_ENGINE", "sqlserver"),
            [
                ("sqlserver", "SQL Server (pyodbc / SQLAlchemy)"),
                ("sqlite", "Local SQL Engine (pigskin_history.db)"),
            ],
            expand=True,
            page=page,
        )
        db_server_field = css_input(
            label="DB_SERVER (Máy chủ SQL Server)",
            value=cfg.get("DB_SERVER") or cfg.get("SQLSERVER_HOST", "localhost"),
            prefix_icon=ft.Icons.DNS_ROUNDED,
            expand=True,
            page=page,
        )
        db_name_field = css_input(
            label="DB_NAME (Tên Database)",
            value=cfg.get("DB_NAME") or cfg.get("SQLSERVER_DATABASE", "PigSkinTechDB"),
            prefix_icon=ft.Icons.STORAGE_ROUNDED,
            expand=True,
            page=page,
        )
        db_user_field = css_input(
            label="DB_USER (Tài khoản SQL)",
            value=cfg.get("DB_USER") or cfg.get("SQLSERVER_USERNAME", ""),
            prefix_icon=ft.Icons.PERSON_OUTLINE_ROUNDED,
            expand=True,
            page=page,
        )
        db_pw_field = css_input(
            label="DB_PASSWORD (Mật khẩu SQL)",
            value=cfg.get("DB_PASSWORD") or cfg.get("SQLSERVER_PASSWORD", ""),
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
            expand=True,
            page=page,
        )
        trusted_chk = ft.Checkbox(
            label="Trusted_Connection=yes (Xác thực Windows Integrated)",
            value=str(cfg.get("Trusted_Connection", "yes")).lower() in ("yes", "true", "1"),
            active_color=PRIMARY,
        )

        google_cid_field = css_input(
            label="GOOGLE_CLIENT_ID",
            value=cfg.get("GOOGLE_CLIENT_ID", ""),
            hint_text="xxxx-yyyy.apps.googleusercontent.com",
            prefix_icon=ft.Icons.KEY_ROUNDED,
            expand=True,
            page=page,
        )
        google_csec_field = css_input(
            label="GOOGLE_CLIENT_SECRET",
            value=cfg.get("GOOGLE_CLIENT_SECRET", ""),
            hint_text="GOCSPX-...",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.LOCK_PERSON_ROUNDED,
            expand=True,
            page=page,
        )

        gemini_key_field = css_input(
            label="GEMINI_API_KEY (Google AI Studio — gemini-2.5-flash)",
            value=cfg.get("GEMINI_API_KEY", ""),
            hint_text="AIzaSy...",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.AUTO_AWESOME_ROUNDED,
            expand=True,
            page=page,
        )
        gemini_model_field = css_input(
            label="GEMINI_MODEL",
            value=cfg.get("GEMINI_MODEL", "gemini-2.5-flash"),
            prefix_icon=ft.Icons.PSYCHOLOGY_ROUNDED,
            expand=True,
            page=page,
        )
        ai_provider_dd = make_dropdown(
            "AI Provider (Chatbot)",
            cfg.get("AI_PROVIDER", "gemini"),
            [
                ("gemini", "Google Gemini API (gemini-2.5-flash)"),
                ("openai_compatible", "OpenAI / DeepSeek / Groq Compatible"),
                ("ollama", "Ollama Local (http://localhost:11434/v1)"),
            ],
            expand=True,
            page=page,
        )
        ai_base_field = css_input(
            label="AI_BASE_URL",
            value=cfg.get("AI_BASE_URL", "https://api.openai.com/v1"),
            prefix_icon=ft.Icons.LINK_ROUNDED,
            expand=True,
            page=page,
        )
        ai_key_field = css_input(
            label="AI_API_KEY",
            value=cfg.get("AI_API_KEY", ""),
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.VPN_KEY_ROUNDED,
            expand=True,
            page=page,
        )
        ai_model_field = css_input(
            label="AI_MODEL",
            value=cfg.get("AI_MODEL", "gpt-4o-mini"),
            prefix_icon=ft.Icons.SMART_TOY_ROUNDED,
            expand=True,
            page=page,
        )
        ai_prompt_field = css_input(
            label="AI_SYSTEM_PROMPT",
            value=cfg.get("AI_SYSTEM_PROMPT", ""),
            multiline=True,
            min_lines=2,
            max_lines=3,
            expand=True,
            page=page,
        )

        status_text = ft.Text(
            f"Trạng thái hiện tại: {db_stat.get('engine')} — {db_stat.get('status')}",
            size=13,
            weight=ft.FontWeight.W_600,
            color=t["EMERALD"],
        )

        def handle_test_sql(e):
            res = test_sqlserver_connection({
                "DB_SERVER": db_server_field.value or "localhost",
                "DB_NAME": db_name_field.value or "PigSkinTechDB",
                "DB_USER": db_user_field.value or "",
                "DB_PASSWORD": db_pw_field.value or "",
                "Trusted_Connection": "yes" if trusted_chk.value else "no",
            })
            status_text.value = res["message"]
            status_text.color = "#059669" if res["ok"] else "#DC2626"
            show_snack(page, res["message"], "#059669" if res["ok"] else "#DC2626")
            page.update()

        def handle_save_all_settings(e):
            save_settings({
                "DATABASE_ENGINE": db_engine_dd.value or "sqlserver",
                "DB_SERVER": db_server_field.value or "localhost",
                "DB_NAME": db_name_field.value or "PigSkinTechDB",
                "DB_USER": db_user_field.value or "",
                "DB_PASSWORD": db_pw_field.value or "",
                "Trusted_Connection": "yes" if trusted_chk.value else "no",
                "GOOGLE_CLIENT_ID": google_cid_field.value or "",
                "GOOGLE_CLIENT_SECRET": google_csec_field.value or "",
                "GEMINI_API_KEY": gemini_key_field.value or "",
                "GEMINI_MODEL": gemini_model_field.value or "gemini-2.5-flash",
                "AI_PROVIDER": ai_provider_dd.value or "gemini",
                "AI_BASE_URL": ai_base_field.value or "",
                "AI_API_KEY": ai_key_field.value or "",
                "AI_MODEL": ai_model_field.value or "gpt-4o-mini",
                "AI_SYSTEM_PROMPT": ai_prompt_field.value or "",
            })
            new_stat = get_db_status()
            status_text.value = f"Đã lưu cấu hình vào .env! {new_stat.get('engine')} — {new_stat.get('status')}"
            status_text.color = "#059669"
            show_snack(page, "Đã lưu cấu hình SQL Server, Google OAuth 2.0 và Gemini AI Chatbot vào file .env!", "#059669")
            page.update()

        sql_card = tech_card(
            page=page,
            padding=24,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.STORAGE_ROUNDED, color=t["EMERALD"], size=22),
                            ft.Text("1. Kết nối Cơ sở dữ liệu SQL Server (.env)", size=18, weight=ft.FontWeight.BOLD, color=t["TEXT"], expand=True),
                            ft.OutlinedButton("🔌 Kiểm tra kết nối SQL Server", icon=ft.Icons. CABLE_ROUNDED, on_click=handle_test_sql),
                        ],
                        spacing=8,
                    ),
                    status_text,
                    ft.Row([db_engine_dd, db_server_field, db_name_field], spacing=12),
                    ft.Row([db_user_field, db_pw_field], spacing=12),
                    trusted_chk,
                ],
                spacing=12,
            ),
        )

        oauth_ai_card = tech_card(
            page=page,
            padding=24,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.SECURITY_ROUNDED, color=t["CYAN"], size=22),
                            ft.Text("2. Google OAuth 2.0 (127.0.0.1:8765/callback) & Trợ lý AI Thú y (Gemini / LLM)", size=18, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                        ],
                        spacing=8,
                    ),
                    ft.Row([google_cid_field, google_csec_field], spacing=12),
                    ft.Divider(height=10, color=t["BORDER"]),
                    ft.Row([gemini_key_field, gemini_model_field], spacing=12),
                    ft.Row([ai_provider_dd, ai_base_field, ai_model_field], spacing=12),
                    ft.Row([ai_key_field]),
                    ft.Row([ai_prompt_field]),
                    ft.Row(
                        [
                            ft.FilledButton(
                                "💾 Lưu Toàn Bộ Cấu Hình Hệ Thống (.env)",
                                icon=ft.Icons.SAVE_ROUNDED,
                                on_click=handle_save_all_settings,
                            )
                        ]
                    ),
                ],
                spacing=12,
            ),
        )

        return [
            tech_banner(
                "Cấu hình Hệ thống & Kết nối Thực tế",
                "Quản lý kết nối SQL Server (PigSkinTechDB), Google OAuth 2.0 Authorization Code và Chatbot AI Thú y",
                badge_text="SQL Server • OAuth 2.0 • AI API",
                page=page,
            ),
            sql_card,
            oauth_ai_card,
        ]

    destinations = [
        ("Tổng quan hệ thống", ft.Icons.DASHBOARD_OUTLINED, ft.Icons.DASHBOARD_ROUNDED),
        ("Người dùng & RBAC", ft.Icons.MANAGE_ACCOUNTS_OUTLINED, ft.Icons.MANAGE_ACCOUNTS_ROUNDED),
        ("Mô hình & Danh mục bệnh", ft.Icons.TUNE_OUTLINED, ft.Icons.TUNE_ROUNDED),
        ("Cấu hình hệ thống", ft.Icons.SETTINGS_APPLICATIONS_OUTLINED, ft.Icons.SETTINGS_APPLICATIONS_ROUNDED),
    ]

    return build_role_shell(
        page=page,
        user=user,
        title="Không gian Quản Trị Hệ Thống (Admin)",
        destinations=destinations,
        tab_builders=[build_dashboard_tab, build_users_tab, build_config_tab, build_system_settings_tab],
    )
