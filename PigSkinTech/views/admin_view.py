"""Admin Role View (/admin - Quản trị hệ thống): System Dashboard, Full-Width User & RBAC DataTable, AI & Classes CRUD."""
import asyncio
import inspect
import json

import flet as ft

from services.auth_service import (
    build_role_shell,
    close_dialog,
    create_file_picker,
    ensure_flet_compat,
    export_inspections_csv,
    header_stat_pill,
    kpi_stat_card,
    make_image,
    make_dropdown,
    open_dialog,
    pick_image_files,
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
from services.inference import inspect_image, predict
from services.project_data import (
    active_run,
    display_class,
    list_model_runs,
    load_classes_config,
    read_checkpoint_details,
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

        admin_pills = [
            header_stat_pill("Người dùng", str(stats["total_users"]), ft.Icons.PEOPLE_ALT_ROUNDED, "#0284C7", t["CYAN_SOFT"], "", page=page),
            header_stat_pill("Lượt khám", f"{stats['total_inspections']} ca", ft.Icons.ANALYTICS_ROUNDED, "#059669", t["EMERALD_SOFT"], "", page=page),
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
        model_names = {
            "mobilenet_v2": "MobileNetV2",
            "mobilenet_v3_large": "MobileNetV3-Large",
            "efficientnet_b0": "EfficientNet-B0",
        }
        run_options = [
            (
                r["checkpoint"],
                f"{r['name']}  ·  {model_names.get(r['model'], r['model'])}  ·  "
                f"Val macro-F1 {r['val_f1']:.1%}  ·  {r['classes_count']} lớp"
                if isinstance(r.get("val_f1"), (int, float))
                else f"{r['name']}  ·  {model_names.get(r['model'], r['model'])}  ·  {r['classes_count']} lớp",
            )
            for r in runs
        ]
        if not run_options and cur_ckpt:
            run_options = [(cur_ckpt, f"{cur_run['name']}  ·  Model đang dùng")]

        custom_ckpt_field = css_input(
            label="Đường dẫn trọng số mô hình đang kích hoạt",
            value=cur_ckpt,
            prefix_icon=ft.Icons.FOLDER_SPECIAL_OUTLINED,
            expand=True,
            page=page,
        )
        checkpoint_picker = create_file_picker(page)
        checkpoint_info = ft.Text(
            "Chọn file checkpoint để đọc thông số model.",
            size=12.5,
            color=t["SECONDARY"],
            selectable=True,
        )

        def update_checkpoint_info(path):
            custom_ckpt_field.value = str(path or "")
            if not path:
                checkpoint_info.value = "Chọn file checkpoint để đọc thông số model."
                checkpoint_info.color = t["SECONDARY"]
                return
            try:
                details = read_checkpoint_details(path)
                model_label = model_names.get(details["model"], details["model"])
                config = details["config"]
                train_values = [
                    f"Epoch tối đa: {config.get('epochs')}" if config.get("epochs") else None,
                    f"Head-only: {config.get('head_epochs')} epoch" if config.get("head_epochs") else None,
                    f"Batch: {details['batch_size']}" if details.get("batch_size") else None,
                    f"Optimizer: {config.get('optimizer')}" if config.get("optimizer") else None,
                    f"LR head: {config.get('head_lr')}" if config.get("head_lr") else None,
                    f"LR fine-tune: {config.get('finetune_lr')}" if config.get("finetune_lr") else None,
                    f"Weight decay: {config.get('weight_decay')}" if config.get("weight_decay") else None,
                    f"Early-stop patience: {config.get('early_stopping_patience')}"
                    if config.get("early_stopping_patience") else None,
                    f"Seed: {config.get('seed')}" if config.get("seed") is not None else None,
                    f"Pretrained: {'có' if config.get('pretrained') else 'không'}"
                    if config.get("pretrained") is not None else None,
                    f"Augmentation: {'bật' if config.get('augmentation', {}).get('enabled') else 'tắt'}"
                    if isinstance(config.get("augmentation"), dict) else None,
                ]
                result_values = [
                    f"Best epoch: {details['best_epoch']}" if details.get("best_epoch") else None,
                    f"Val macro-F1: {details['val_macro_f1']:.1%}"
                    if isinstance(details.get("val_macro_f1"), (int, float)) else None,
                    f"Test accuracy: {details['test_accuracy']:.1%}"
                    if isinstance(details.get("test_accuracy"), (int, float)) else None,
                    f"Test macro-F1: {details['test_macro_f1']:.1%}"
                    if isinstance(details.get("test_macro_f1"), (int, float)) else None,
                ]
                checkpoint_info.value = "\n".join(
                    [
                        f"Model: {model_label} | {len(details['classes'])} lớp | "
                        f"Ảnh {details['image_size']}×{details['image_size']}" if details.get("image_size")
                        else f"Model: {model_label} | {len(details['classes'])} lớp",
                        "Huấn luyện: " + " | ".join(value for value in train_values if value),
                        "Kết quả: " + " | ".join(value for value in result_values if value),
                        "Thông số được đọc từ config.json và final_metrics.json cạnh checkpoint.",
                    ]
                )
                checkpoint_info.color = t["EMERALD"]
            except (OSError, ValueError, json.JSONDecodeError) as err:
                checkpoint_info.value = f"Không đọc được thông số: {err}"
                checkpoint_info.color = t["RED"]

        def on_select_run(e):
            update_checkpoint_info(run_dropdown.value)
            page.update()

        run_dropdown = make_dropdown(
            "Chọn phiên bản mô hình huấn luyện",
            cur_ckpt if any(k == cur_ckpt for k, _ in run_options) else (run_options[0][0] if run_options else ""),
            run_options,
            on_change=on_select_run,
            expand=True,
            page=page,
        )

        def on_checkpoint_picked(e):
            files = getattr(e, "files", None) or []
            if files and getattr(files[0], "path", None):
                update_checkpoint_info(files[0].path)
                page.update()

        async def choose_checkpoint(e):
            if inspect.iscoroutinefunction(checkpoint_picker.pick_files):
                files = await checkpoint_picker.pick_files(
                    allow_multiple=False,
                    file_type=ft.FilePickerFileType.CUSTOM,
                    allowed_extensions=["pt", "pth"],
                )
                if files and getattr(files[0], "path", None):
                    update_checkpoint_info(files[0].path)
                    page.update()
            else:
                checkpoint_picker.on_result = on_checkpoint_picked
                checkpoint_picker.pick_files(
                    allow_multiple=False,
                    file_type=ft.FilePickerFileType.CUSTOM,
                    allowed_extensions=["pt", "pth"],
                )

        update_checkpoint_info(custom_ckpt_field.value)

        def handle_activate_model(e):
            try:
                info = set_active_checkpoint(custom_ckpt_field.value)
                if not info:
                    raise RuntimeError("Không xác nhận được model sau khi lưu.")
                model_code = info.get("config", {}).get("model", "")
                model_label = model_names.get(model_code, model_code)
                active_model_status.content = ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=t["EMERALD"], size=20),
                        ft.Column(
                            [
                                ft.Text(
                                    f"Model dùng chung cho các role: {model_label} · {info['name']}",
                                    size=13.5,
                                    weight=ft.FontWeight.BOLD,
                                    color=t["TEXT"],
                                ),
                                ft.Text(
                                    str(info["checkpoint"]),
                                    size=11.5,
                                    color=t["SECONDARY"],
                                    selectable=True,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                            spacing=3,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                )
                active_model_status.bgcolor = t["EMERALD_SOFT"]
                active_model_status.border = ft.border.all(1, t["BORDER"])
                page.update()
                show_snack(page, f"Đã lưu và kích hoạt {model_label} cho toàn ứng dụng.", "#059669")
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

        active_model_status = ft.Container(
            padding=12,
            border_radius=10,
            bgcolor=t["SUB_SURFACE"],
            border=ft.border.all(1, t["BORDER"]),
            content=(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=t["EMERALD"], size=20),
                        ft.Column(
                            [
                                ft.Text(
                                    f"Model dùng chung cho các role: "
                                    f"{model_names.get(cur_run['config'].get('model', ''), cur_run['config'].get('model', ''))} · {cur_run['name']}",
                                    size=13.5,
                                    weight=ft.FontWeight.BOLD,
                                    color=t["TEXT"],
                                ),
                                ft.Text(
                                    str(cur_run["checkpoint"]),
                                    size=11.5,
                                    color=t["SECONDARY"],
                                    selectable=True,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                            spacing=3,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                )
                if cur_run
                else ft.Row(
                    [
                        ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=t["SECONDARY"], size=20),
                        ft.Text("Chưa có model được kích hoạt.", size=13.5, color=t["SECONDARY"]),
                    ],
                    spacing=10,
                )
            ),
        )

        model_card = tech_card(
            page=page,
            padding=24,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.MEMORY_ROUNDED, color=t["EMERALD"], size=22),
                            ft.Text("1. Model AI dùng chung cho hệ thống", size=18, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                        ],
                        spacing=8,
                    ),
                    ft.Text(
                        "Chọn một run đã huấn luyện. Sau khi lưu, role quản trị, chuyên gia và nông dân cùng dùng model này.",
                        size=13,
                        color=t["SECONDARY"],
                    ),
                    active_model_status,
                    ft.Row([run_dropdown]),
                    ft.Row(
                        [
                            custom_ckpt_field,
                            ft.OutlinedButton(
                                "Chọn file",
                                icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                                on_click=choose_checkpoint,
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=4, vertical=2),
                        content=checkpoint_info,
                    ),
                    ft.Row(
                        [
                            ft.FilledButton(
                                "Lưu & dùng model",
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

    # Tab 4: Test the currently active checkpoint without saving a case.
    def build_model_test_tab():
        t = theme_tokens(page)
        run = active_run()
        picker = create_file_picker(page)
        state = {"image_path": None}

        model_label = run.get("model_label", run.get("model", "Model")) if run else "Chưa kích hoạt"
        run_name = run.get("name", "") if run else ""
        run_metrics = run.get("metrics", {}) if run else {}
        val_f1 = run_metrics.get("best_val_macro_f1")
        model_summary = (
            f"Đang kiểm thử bằng {model_label} · {run_name}"
            + (f" · Validation macro-F1 {val_f1:.1%}" if isinstance(val_f1, (int, float)) else "")
            if run
            else "Chưa có model hoạt động. Hãy kích hoạt checkpoint trong tab Mô hình & Danh mục bệnh."
        )
        model_summary_text = ft.Text(
            model_summary,
            size=13,
            color=t["EMERALD"] if run else t["RED"],
            selectable=True,
        )
        image_preview = ft.Container(
            height=340,
            expand=True,
            alignment=ft.alignment.center,
            bgcolor=t["SUB_SURFACE"],
            border=ft.border.all(1, t["BORDER"]),
            border_radius=14,
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.IMAGE_SEARCH_OUTLINED, size=42, color=t["SECONDARY"]),
                    ft.Text("Chọn ảnh da heo để bắt đầu kiểm thử", size=14, color=t["SECONDARY"]),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
        )
        image_caption = ft.Text("Chưa chọn ảnh", size=12.5, color=t["SECONDARY"])
        result_host = ft.Container()
        progress = ft.ProgressRing(width=18, height=18, stroke_width=2.5, visible=False)
        status_text = ft.Text("", size=12.5, color=t["SECONDARY"])
        predict_button = ft.FilledButton(
            "Dự đoán ảnh",
            icon=ft.Icons.AUTO_AWESOME_ROUNDED,
            disabled=not bool(run),
        )

        def render_result(result):
            if not result:
                result_host.content = None
                return
            if result.get("mode") != "ai":
                result_host.content = ft.Text(
                    result.get("message", "Model không trả về dự đoán."),
                    color=t["RED"],
                    size=13,
                )
                return

            confidence = float(result.get("confidence") or 0)
            score_rows = []
            for index, score in enumerate(result.get("scores", [])[:5], start=1):
                value = float(score.get("confidence") or 0)
                score_rows.append(
                    ft.Row(
                        [
                            ft.Text(f"{index}.", width=22, size=12, color=t["SECONDARY"]),
                            ft.Text(score.get("display_label", score.get("label", "")), expand=True, size=12.5, color=t["TEXT"]),
                            ft.Container(width=130, content=ft.ProgressBar(value=value, color=t["EMERALD"], bgcolor=t["BORDER"], bar_height=7)),
                            ft.Text(f"{value:.1%}", width=54, text_align=ft.TextAlign.RIGHT, size=12.5, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )
            result_host.content = tech_card(
                page=page,
                padding=20,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=t["EMERALD"], size=22),
                                ft.Column(
                                    [
                                        ft.Text(result.get("display_label", "Kết quả"), size=19, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                                        ft.Text(f"Độ tin cậy dự đoán: {confidence:.1%} · {result.get('model_info', model_label)}", size=12.5, color=t["SECONDARY"]),
                                    ],
                                    spacing=4,
                                    expand=True,
                                ),
                            ],
                            spacing=10,
                        ),
                        ft.Divider(height=8, color=t["BORDER"]),
                        *score_rows,
                        ft.Text(
                            "Đây là kết quả thử trên một ảnh, không phải độ chính xác tổng thể. Cần chuyên gia thú y xác minh.",
                            size=12,
                            color=t["SECONDARY"],
                        ),
                    ],
                    spacing=10,
                ),
            )

        def on_image_selected(paths):
            if not paths:
                return
            try:
                info = inspect_image(paths[0])
                state["image_path"] = paths[0]
                image_preview.content = make_image(
                    paths[0], width=600, height=330, border_radius=12, fit=ft.ImageFit.CONTAIN
                )
                image_caption.value = f"{info['name']} · {info['width']} × {info['height']} px · {info['bytes'] / 1024:.0f} KB"
                status_text.value = ""
                render_result(None)
                predict_button.disabled = not bool(run)
                page.update()
            except Exception as err:
                show_snack(page, str(err), "#DC2626")

        async def choose_test_image(e):
            await pick_image_files(picker, allow_multiple=False, on_picked=on_image_selected)

        async def handle_test_prediction(e):
            if not run:
                show_snack(page, "Chưa có model hoạt động để kiểm thử.", "#DC2626")
                return
            if not state["image_path"]:
                show_snack(page, "Hãy chọn ảnh trước khi chạy dự đoán.", "#DC2626")
                return
            predict_button.disabled = True
            progress.visible = True
            status_text.value = "Đang chạy model trên ảnh đã chọn…"
            status_text.color = t["SECONDARY"]
            page.update()
            try:
                result = await asyncio.to_thread(predict, state["image_path"], run_name)
                render_result(result)
                status_text.value = "Hoàn tất kiểm thử. Ca này không được lưu vào hồ sơ/database."
                status_text.color = t["EMERALD"]
            except Exception as err:
                status_text.value = f"Không thể chạy dự đoán: {err}"
                status_text.color = t["RED"]
                render_result(None)
            finally:
                progress.visible = False
                predict_button.disabled = not bool(run)
                page.update()

        predict_button.on_click = handle_test_prediction

        return [
            tech_banner(
                "Kiểm thử model",
                "Chạy thử ảnh với checkpoint đang kích hoạt và xem các lớp dự đoán nổi bật.",
                icon=ft.Icons.SCIENCE_OUTLINED,
                badge_text=model_label if run else "Chưa có model",
                page=page,
            ),
            tech_card(
                page=page,
                padding=20,
                content=ft.Column(
                    [
                        model_summary_text,
                        ft.Row(
                            [
                                ft.OutlinedButton(
                                    "Chọn ảnh",
                                    icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                                    on_click=choose_test_image,
                                ),
                                predict_button,
                                progress,
                                status_text,
                            ],
                            spacing=12,
                            wrap=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Row(
                            [
                                ft.Container(content=image_preview, expand=1),
                                ft.Container(
                                    expand=1,
                                    content=ft.Column(
                                        [
                                            ft.Text("Ảnh kiểm thử", size=15, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                                            image_caption,
                                            ft.Text("Kết quả", size=15, weight=ft.FontWeight.BOLD, color=t["TEXT"]),
                                            result_host,
                                        ],
                                        spacing=12,
                                    ),
                                ),
                            ],
                            spacing=18,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                    ],
                    spacing=14,
                ),
            ),
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
            label="Tên máy chủ / SQL Server instance",
            value=cfg.get("DB_SERVER") or cfg.get("SQLSERVER_HOST", "localhost"),
            hint_text=r"VD: TEN-MAY\SQLEXPRESS hoặc 192.168.1.10",
            prefix_icon=ft.Icons.DNS_ROUNDED,
            expand=True,
            page=page,
        )
        db_port_field = css_input(
            label="Cổng SQL Server",
            value=cfg.get("SQLSERVER_PORT", "1433"),
            hint_text="1433 (bỏ qua nếu nhập dạng TEN-MAY\\INSTANCE)",
            prefix_icon=ft.Icons.CABLE_ROUNDED,
            width=220,
            page=page,
        )
        db_name_field = css_input(
            label="DB_NAME (Tên Database)",
            value=cfg.get("DB_NAME") or cfg.get("SQLSERVER_DATABASE", "PigSkinTechDB"),
            prefix_icon=ft.Icons.STORAGE_ROUNDED,
            expand=True,
            page=page,
        )
        auth_info = ft.Container(
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            border_radius=10,
            bgcolor=t["EMERALD_SOFT"],
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.SECURITY_ROUNDED, color=t["EMERALD"], size=19),
                    ft.Text(
                        "Windows Integrated Authentication — dùng tài khoản Windows hiện tại, không gửi user/password SQL.",
                        size=12.5,
                        color=t["TEXT"],
                    ),
                ],
                spacing=8,
            ),
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
                "SQLSERVER_PORT": db_port_field.value or "1433",
                "DB_USER": "",
                "DB_PASSWORD": "",
                "Trusted_Connection": "yes",
            })
            if res["ok"]:
                # The connection test also provisions the selected DB and saves
                # the endpoint so the app initializes its tables on this server.
                try:
                    save_settings({
                        "DATABASE_ENGINE": "sqlserver",
                        "DB_SERVER": db_server_field.value or "localhost",
                        "DB_NAME": db_name_field.value or "PigSkinTechDB",
                        "SQLSERVER_PORT": db_port_field.value or "1433",
                        "Trusted_Connection": "yes",
                        "SQLSERVER_TRUSTED_CONNECTION": "true",
                    })
                    app_db = get_db_status()
                    if "SQL Server" not in (app_db.get("engine") or ""):
                        res = {
                            "ok": False,
                            "message": (
                                "Máy chủ phản hồi nhưng ứng dụng chưa khởi tạo được database. "
                                f"Trạng thái: {app_db.get('status')}. "
                                f"Chi tiết: {app_db.get('last_error', 'không có thông tin lỗi')}"
                            ),
                        }
                    else:
                        res["message"] += " Các bảng ứng dụng đã được khởi tạo và cấu hình đã lưu."
                except Exception as exc:
                    res = {
                        "ok": False,
                        "message": f"Kết nối SQL Server thành công nhưng lưu cấu hình/khởi tạo database gặp lỗi: {exc}",
                    }
            status_text.value = res["message"]
            status_text.color = "#059669" if res["ok"] else "#DC2626"
            show_snack(page, res["message"], "#059669" if res["ok"] else "#DC2626")
            page.update()

        def handle_save_all_settings(e):
            save_settings({
                "DATABASE_ENGINE": db_engine_dd.value or "sqlserver",
                "DB_SERVER": db_server_field.value or "localhost",
                "DB_NAME": db_name_field.value or "PigSkinTechDB",
                "SQLSERVER_PORT": db_port_field.value or "1433",
                "DB_USER": "",
                "DB_PASSWORD": "",
                "SQLSERVER_USERNAME": "",
                "SQLSERVER_PASSWORD": "",
                "Trusted_Connection": "yes",
                "SQLSERVER_TRUSTED_CONNECTION": "true",
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
            status_text.value = f"Đã lưu cấu hình vào database.json và .env! {new_stat.get('engine')} — {new_stat.get('status')}"
            status_text.color = "#059669"
            show_snack(page, "Đã lưu cấu hình máy chủ vào database.json và các cấu hình khác vào .env!", "#059669")
            page.update()

        sql_card = tech_card(
            page=page,
            padding=24,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.STORAGE_ROUNDED, color=t["EMERALD"], size=22),
                            ft.Text("1. Kết nối Cơ sở dữ liệu SQL Server (database.json)", size=18, weight=ft.FontWeight.BOLD, color=t["TEXT"], expand=True),
                            ft.OutlinedButton("🔌 Kiểm tra & tạo database", icon=ft.Icons.CABLE_ROUNDED, on_click=handle_test_sql),
                        ],
                        spacing=8,
                    ),
                    status_text,
                    ft.Row([db_engine_dd, db_server_field, db_port_field], spacing=12),
                    ft.Row([db_name_field], spacing=12),
                    ft.Text(
                        r"Nhập đúng tên máy trong SQL Server Configuration Manager, ví dụ .\SQLEXPRESS hoặc TEN-MAY\INSTANCE. Nếu kết nối qua IP, nhập IP ở ô máy chủ và cổng TCP ở ô cổng. Máy SQL Server cần bật dịch vụ và cho phép TCP/IP; app dùng Windows Authentication.",
                        size=12.5,
                        color=t["MUTED"],
                    ),
                    ft.Text(
                        "Nút kiểm tra sẽ tự tạo database nếu chưa có, khởi tạo các bảng của ứng dụng và lưu cấu hình máy chủ.",
                        size=12.5,
                        color=t["MUTED"],
                    ),
                    auth_info,
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
        ("Kiểm thử model", ft.Icons.SCIENCE_OUTLINED, ft.Icons.SCIENCE_ROUNDED),
        ("Cấu hình hệ thống", ft.Icons.SETTINGS_APPLICATIONS_OUTLINED, ft.Icons.SETTINGS_APPLICATIONS_ROUNDED),
    ]

    return build_role_shell(
        page=page,
        user=user,
        title="Không gian Quản Trị Hệ Thống (Admin)",
        destinations=destinations,
        tab_builders=[build_dashboard_tab, build_users_tab, build_config_tab, build_model_test_tab, build_system_settings_tab],
    )
