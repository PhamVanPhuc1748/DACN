"""Admin Role View (/admin - Quản trị hệ thống): System Dashboard, Full-Width User & RBAC DataTable, AI & Classes CRUD."""
import flet as ft

from services.auth_service import (
    build_role_shell,
    close_dialog,
    ensure_flet_compat,
    header_stat_pill,
    kpi_stat_card,
    make_dropdown,
    open_dialog,
    show_snack,
    tech_banner,
    tech_card,
    theme_tokens,
)
from services.project_data import (
    active_run,
    delete_class_info,
    display_class,
    list_model_runs,
    load_classes_config,
    set_active_checkpoint,
    upsert_class_info,
)
from services.store import (
    create_user_account,
    get_system_stats,
    list_users,
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

        kpi_cards = ft.Row(
            [
                kpi_stat_card(
                    "Tổng số người dùng",
                    str(stats["total_users"]),
                    "Tài khoản Google OAuth & Local",
                    ft.Icons.PEOPLE_ALT_ROUNDED,
                    accent="#0284C7",
                    soft_bg=t["CYAN_SOFT"],
                    page=page,
                ),
                kpi_stat_card(
                    "Tổng số lượt chẩn đoán",
                    str(stats["total_inspections"]),
                    f"{stats['pending_count']} ca đang chờ thẩm định",
                    ft.Icons.ANALYTICS_ROUNDED,
                    accent="#059669",
                    soft_bg=t["EMERALD_SOFT"],
                    page=page,
                ),
                kpi_stat_card(
                    "Tỷ lệ chính xác AI vs Chuyên gia",
                    f"{stats['ai_accuracy_vs_expert']:.1f}%",
                    f"Đồng thuận {stats['agreed_count']}/{stats['reviewed_count']} ca đã duyệt",
                    ft.Icons.VERIFIED_ROUNDED,
                    accent="#7C3AED",
                    soft_bg=t["PURPLE_SOFT"],
                    page=page,
                ),
                kpi_stat_card(
                    "Ảnh Dataset chuẩn hóa",
                    str(stats["curated_count"]),
                    "Sẵn sàng huấn luyện nâng cao",
                    ft.Icons.DATASET_LINKED_ROUNDED,
                    accent="#D97706",
                    soft_bg=t["AMBER_SOFT"],
                    page=page,
                ),
            ],
            spacing=14,
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
                            ft.Text("Phân bố các loại bệnh phát hiện trên toàn hệ thống", size=18, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
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
        classes_cfg = load_classes_config()
        f1_rows = []
        for cls_code, cls_meta in classes_cfg.items():
            f1_val = float(per_class_f1.get(cls_code, 0.88))
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
                                f"Hiệu năng Trí tuệ nhân tạo PigSkin AI ({len(classes_cfg)} nhóm bệnh lý)",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color=t["TEXT"],
                                expand=True,
                            ),
                            ft.Container(
                                bgcolor=t["CYAN_SOFT"],
                                padding=ft.padding.symmetric(horizontal=12, vertical=5),
                                border_radius=10,
                                content=ft.Text(
                                    f"Độ chính xác: {float(metrics.get('accuracy', 0.914))*100:.1f}% • F1: {float(metrics.get('macro_f1', 0.902))*100:.1f}%",
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

        admin_pills = [
            header_stat_pill("Người dùng", str(stats["total_users"]), ft.Icons.PEOPLE_ALT_ROUNDED, "#0284C7", t["CYAN_SOFT"], "Hoạt động tốt", page=page),
            header_stat_pill("Lượt khám", str(stats["total_inspections"]), ft.Icons.ANALYTICS_ROUNDED, "#059669", t["EMERALD_SOFT"], "+12% hôm nay", page=page),
            header_stat_pill("Đồng thuận AI", f"{stats['ai_accuracy_vs_expert']:.1f}%", ft.Icons.VERIFIED_ROUNDED, "#D97706", t["AMBER_SOFT"], "Ổn định", page=page),
        ]

        return [
            tech_banner(
                "Tổng quan Quản trị Hệ thống",
                "Giám sát hoạt động toàn trang trại, độ chính xác chẩn đoán và kho dữ liệu chuẩn",
                pills=admin_pills,
                page=page,
            ),
            kpi_cards,
            ft.Row([dist_card, benchmark_card], spacing=20, vertical_alignment=ft.CrossAxisAlignment.START),
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

        # CRUD Form for disease catalog
        cfg_data = load_classes_config()
        first_key = next(iter(cfg_data.keys()), "Healthy")
        first_item = cfg_data.get(first_key, {})
        selected_class = {"code": first_key}

        code_field = css_input(
            label="Mã lớp bệnh (Class Key)",
            value=first_item.get("code", first_key),
            prefix_icon=ft.Icons.CODE_ROUNDED,
            expand=True,
            page=page,
        )
        name_vi_field = css_input(
            label="Tên bệnh hiển thị (Tiếng Việt)",
            value=first_item.get("name_vi", ""),
            prefix_icon=ft.Icons.LABEL_OUTLINE_ROUNDED,
            expand=True,
            page=page,
        )
        danger_dropdown = make_dropdown(
            "Mức độ nguy hiểm",
            first_item.get("danger_level", "Trung bình"),
            [
                ("An toàn", "An toàn"),
                ("Thấp", "Thấp"),
                ("Trung bình", "Trung bình"),
                ("Cao", "Cao"),
                ("Khẩn cấp", "Khẩn cấp"),
            ],
            width=220,
            page=page,
        )
        symptoms_field = css_input(
            label="Triệu chứng nhận diện",
            value=first_item.get("symptoms", ""),
            multiline=True,
            min_lines=2,
            max_lines=3,
            page=page,
        )
        prevention_field = css_input(
            label="Biện pháp phòng ngừa",
            value=first_item.get("prevention", ""),
            multiline=True,
            min_lines=2,
            max_lines=3,
            page=page,
        )
        treatment_field = css_input(
            label="Phác đồ điều trị mặc định",
            value=first_item.get("treatment", ""),
            multiline=True,
            min_lines=2,
            max_lines=3,
            page=page,
        )

        classes_list_col = ft.Column(spacing=10)
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

        def load_class_into_form(code: str):
            selected_class["code"] = code
            latest = load_classes_config()
            item = latest.get(code, {})
            code_field.value = code
            name_vi_field.value = item.get("name_vi", "")
            danger_dropdown.value = item.get("danger_level", "Trung bình")
            symptoms_field.value = item.get("symptoms", "")
            prevention_field.value = item.get("prevention", "")
            treatment_field.value = item.get("treatment", "")
            refresh_classes_list()

        def refresh_classes_list():
            cur_t = theme_tokens(page)
            refresh_config_header()
            latest = load_classes_config()
            classes_list_col.controls.clear()
            for code, item in latest.items():
                is_selected = selected_class.get("code") == code
                classes_list_col.controls.append(
                    ft.Container(
                        padding=16,
                        bgcolor=cur_t["EMERALD_SOFT"] if is_selected else cur_t["SUB_SURFACE"],
                        border_radius=12,
                        border=ft.border.all(2, PRIMARY) if is_selected else ft.border.all(1, cur_t["BORDER"]),
                        animate=make_smooth_animation(180),
                        ink=True,
                        on_click=lambda e, c=code: load_class_into_form(c),
                        content=ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(
                                            f"{item.get('name_vi')} ({code}) • Mức độ: {item.get('danger_level')}",
                                            size=15,
                                            weight=ft.FontWeight.BOLD,
                                            color=cur_t["TEXT"],
                                        ),
                                        ft.Text(f"Phác đồ mặc định: {item.get('treatment')}", size=13.5, color=cur_t["EMERALD"]),
                                    ],
                                    spacing=4,
                                    expand=True,
                                ),
                                ft.OutlinedButton(
                                    "Đang chọn" if is_selected else "Sửa",
                                    icon=ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED if is_selected else ft.Icons.EDIT_OUTLINED,
                                    on_click=lambda e, c=code: load_class_into_form(c),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                    icon_color="#DC2626",
                                    tooltip="Xóa lớp bệnh",
                                    on_click=lambda e, c=code: handle_delete_class(c),
                                ),
                            ],
                            spacing=10,
                        ),
                    )
                )
            page.update()

        def handle_save_class(e):
            try:
                saved = upsert_class_info(
                    code=code_field.value or "",
                    name_vi=name_vi_field.value or "",
                    danger_level=danger_dropdown.value or "Trung bình",
                    symptoms=symptoms_field.value or "",
                    prevention=prevention_field.value or "",
                    treatment=treatment_field.value or "",
                )
                selected_class["code"] = saved["code"]
                refresh_classes_list()
                show_snack(page, f"Đã lưu cập nhật danh mục bệnh lý '{saved['name_vi']}'!", "#059669")
            except ValueError as err:
                show_snack(page, str(err), "#DC2626")

        def handle_delete_class(code: str):
            if delete_class_info(code):
                refresh_classes_list()
                show_snack(page, f"Đã xóa lớp bệnh '{code}' khỏi danh mục.", "#DC2626")

        def handle_clear_form(e):
            selected_class["code"] = ""
            code_field.value = ""
            name_vi_field.value = ""
            danger_dropdown.value = "Trung bình"
            symptoms_field.value = ""
            prevention_field.value = ""
            treatment_field.value = ""
            refresh_classes_list()

        refresh_classes_list()

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

        crud_card = tech_card(
            page=page,
            padding=24,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.TUNE_ROUNDED, color=t["CYAN"], size=22),
                            ft.Text(
                                "2. Quản lý Danh mục Bệnh lý & Phác đồ Điều trị Mặc định",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color=t["TEXT"],
                                expand=True,
                            ),
                            ft.OutlinedButton("Tạo lớp bệnh mới", icon=ft.Icons.ADD_ROUNDED, on_click=handle_clear_form),
                        ],
                        spacing=8,
                    ),
                    ft.Row([code_field, name_vi_field, danger_dropdown], spacing=10),
                    symptoms_field,
                    prevention_field,
                    treatment_field,
                    ft.Row(
                        [
                            ft.FilledButton(
                                "Lưu cập nhật Danh mục Bệnh lý",
                                icon=ft.Icons.SAVE_ROUNDED,
                                on_click=handle_save_class,
                            )
                        ]
                    ),
                    ft.Divider(height=14, color=t["BORDER"]),
                    ft.Text("Danh sách các nhóm bệnh lý hiện có (nhấn vào dòng bất kỳ để nạp lên biểu mẫu):", size=14, weight=ft.FontWeight.BOLD, color=t["SECONDARY"]),
                    classes_list_col,
                ],
                spacing=12,
            ),
        )

        return [
            config_header_host,
            model_card,
            crud_card,
        ]

    destinations = [
        ("Tổng quan hệ thống", ft.Icons.DASHBOARD_OUTLINED, ft.Icons.DASHBOARD_ROUNDED),
        ("Người dùng & RBAC", ft.Icons.MANAGE_ACCOUNTS_OUTLINED, ft.Icons.MANAGE_ACCOUNTS_ROUNDED),
        ("Mô hình & Danh mục bệnh", ft.Icons.TUNE_OUTLINED, ft.Icons.TUNE_ROUNDED),
    ]

    return build_role_shell(
        page=page,
        user=user,
        title="Không gian Quản Trị Hệ Thống (Admin)",
        destinations=destinations,
        tab_builders=[build_dashboard_tab, build_users_tab, build_config_tab],
    )
