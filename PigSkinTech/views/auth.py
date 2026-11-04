"""Responsive login, registration, recovery, and OTP Flet screens."""

import base64
from pathlib import Path

import flet as ft

_HERO_IMAGE = base64.b64encode(
    (Path(__file__).resolve().parents[1] / 'assets' / 'login_pig.png').read_bytes()
).decode('ascii')

GREEN = '#087F8C'
GREEN_DARK = '#075A63'
NAVY = '#142B3A'
MUTED = '#526575'
LINE = '#C9D8D0'
RED = '#B4233C'


def build_auth_view(state, actions):
    """Build the full-screen split auth layout from mutable flow state."""

    def refresh():
        actions['render']()

    def switch_mode(mode):
        state.update(
            mode=mode, step='form', challenge_id=None, message='',
            password='', confirm_password='', new_password='', code='',
            show_password=False,
        )
        if mode == 'login':
            state.update(channel='email', method='password')
        refresh()

    def switch_method(method):
        if method == 'password' and state['channel'] != 'email':
            return
        state.update(method=method, message='')
        refresh()

    def switch_contact(channel):
        state.update(
            channel=channel, contact='', step='form', challenge_id=None,
            code='', message='',
        )
        if channel == 'sms' and state['mode'] == 'login':
            state['method'] = 'otp'
        refresh()

    def return_to_contact_form():
        state.update(step='form', challenge_id=None, code='', message='')
        refresh()

    def masked_contact():
        value = str(state.get('contact', '')).strip()
        if state.get('channel') == 'email' and '@' in value:
            local, domain = value.rsplit('@', 1)
            visible = local[:2] if len(local) > 1 else local[:1]
            return f"{visible}{'*' * max(3, len(local) - len(visible))}@{domain}"
        digits = ''.join(character for character in value if character.isdigit())
        return f"***{digits[-3:]}" if len(digits) >= 3 else 'thông tin liên hệ đã nhập'

    is_verify = state['step'] == 'verify'
    mode = state['mode']
    channel = state['channel']
    is_email = channel == 'email'
    otp_enabled = bool(state.get('otp_enabled', False))
    mode_titles = {
        'login': 'Đăng nhập vào hệ thống',
        'register': 'Tạo tài khoản mới',
        'forgot': 'Khôi phục mật khẩu',
    }
    mode_subtitles = {
        'login': 'Hệ thống hỗ trợ nhận diện và thẩm định bệnh da trên heo.',
        'register': ('Xác minh email hoặc số điện thoại để bảo vệ tài khoản.'
                     if otp_enabled else
                     'Tạo tài khoản người dùng bằng email và mật khẩu.'),
        'forgot': 'Nếu thông tin thuộc tài khoản, hướng dẫn xác minh sẽ được gửi.',
    }
    field_style = {
        'color': NAVY,
        'text_style': ft.TextStyle(color=NAVY),
        'label_style': ft.TextStyle(color=MUTED),
        'hint_style': ft.TextStyle(color='#718292'),
        'filled': True,
        'fill_color': '#F7FAF8',
        'focused_bgcolor': '#FFFFFF',
        'focused_border_width': 2,
        'hover_color': '#EEF5F0',
    }
    contact = ft.TextField(
        label='Email' if is_email else 'Số điện thoại Việt Nam',
        hint_text='ten@email.com' if is_email else '+84 9xx xxx xxx',
        value=state.get('contact', ''),
        prefix_icon=ft.Icons.EMAIL_OUTLINED if is_email else ft.Icons.PHONE_ANDROID,
        keyboard_type=ft.KeyboardType.EMAIL if is_email else ft.KeyboardType.PHONE,
        **field_style,
        text_size=14,
        border_radius=12,
        border_color=LINE,
        focused_border_color=GREEN,
        disabled=state.get('loading', False),
        on_change=lambda e: state.__setitem__('contact', e.control.value or ''),
    )

    def password_field(key, label, icon=ft.Icons.LOCK_OUTLINE):
        return ft.TextField(
            label=label,
            value=state.get(key, ''),
            password=not state.get('show_password', False),
            can_reveal_password=False,
            disabled=state.get('loading', False),
            prefix_icon=icon,
            **field_style,
            suffix=ft.IconButton(
                icon=ft.Icons.VISIBILITY_OFF if state.get('show_password') else ft.Icons.VISIBILITY,
                tooltip='Ẩn mật khẩu' if state.get('show_password') else 'Hiện mật khẩu',
                disabled=state.get('loading', False),
                on_click=lambda _: (
                    state.__setitem__('show_password', not state.get('show_password', False)),
                    refresh(),
                ),
            ),
            text_size=14,
            border_radius=12,
            border_color=LINE,
            focused_border_color=GREEN,
            on_change=lambda e: state.__setitem__(key, e.control.value or ''),
        )

    fields = []
    if not is_verify:
        if mode == 'login' and otp_enabled:
            fields.append(ft.Row([
                ft.TextButton(
                    'Mật khẩu',
                    disabled=state.get('loading', False)
                    or state['method'] == 'password' or not is_email,
                    on_click=lambda _: switch_method('password'),
                    style=ft.ButtonStyle(color=GREEN, overlay_color='#EAF4ED'),
                ),
                ft.TextButton(
                    'Mã OTP', disabled=state.get('loading', False)
                    or state['method'] == 'otp',
                    on_click=lambda _: switch_method('otp'),
                    style=ft.ButtonStyle(color=GREEN, overlay_color='#EAF4ED'),
                ),
            ], spacing=4))
        if otp_enabled and (mode in {'register', 'forgot'} or (
            mode == 'login' and state['method'] == 'otp'
        )):
            fields.append(ft.Row([
                ft.TextButton(
                    'Email', disabled=state.get('loading', False) or is_email,
                    on_click=lambda _: switch_contact('email'),
                    style=ft.ButtonStyle(color=GREEN, overlay_color='#EAF4ED'),
                ),
                ft.TextButton(
                    'Số điện thoại',
                    disabled=state.get('loading', False) or not is_email,
                    on_click=lambda _: switch_contact('sms'),
                    style=ft.ButtonStyle(color=GREEN, overlay_color='#EAF4ED'),
                ),
            ], spacing=4))
        fields.append(contact)
        if mode == 'register':
            fields.extend([
                ft.TextField(
                    label='Họ và tên', value=state.get('display_name', ''),
                    prefix_icon=ft.Icons.PERSON_OUTLINE, **field_style,
                    text_size=14,
                    border_radius=12, border_color=LINE,
                    focused_border_color=GREEN,
                    disabled=state.get('loading', False),
                    on_change=lambda e: state.__setitem__(
                        'display_name', e.control.value or ''
                    ),
                ),
                password_field('password', 'Mật khẩu (ít nhất 8 ký tự)'),
                ft.TextField(
                    label='Nhập lại mật khẩu',
                    value=state.get('confirm_password', ''),
                    **field_style,
                    password=True, prefix_icon=ft.Icons.LOCK_OUTLINE,
                    text_size=14, border_radius=12, border_color=LINE,
                    focused_border_color=GREEN,
                    disabled=state.get('loading', False),
                    on_change=lambda e: state.__setitem__(
                        'confirm_password', e.control.value or ''
                    ),
                ),
            ])
        elif mode == 'login' and state['method'] == 'password':
            fields.append(password_field('password', 'Mật khẩu'))
        if mode == 'login' and otp_enabled:
            fields.append(ft.Row([
                ft.Container(expand=True),
                ft.TextButton(
                    'Quên mật khẩu?', on_click=lambda _: switch_mode('forgot'),
                    disabled=state.get('loading', False),
                    style=ft.ButtonStyle(color=GREEN, overlay_color='#EAF4ED'),
                ),
            ]))
    else:
        fields.extend([
            ft.Container(
                bgcolor='#F2F7F3', border_radius=12, padding=14,
                content=ft.Row([
                    ft.Icon(ft.Icons.MARK_EMAIL_READ_OUTLINED, color=GREEN),
                    ft.Column([
                        ft.Text('Nhập mã xác minh 6 chữ số', size=13,
                                color=NAVY, weight=ft.FontWeight.BOLD),
                        ft.Text(
                            f"Đã yêu cầu gửi tới {masked_contact()}. Mã hết hạn sau 5 phút.",
                            size=11, color=MUTED,
                        ),
                    ], spacing=3, expand=True),
                ], spacing=10),
            ),
            ft.TextField(
                label='Mã OTP', hint_text='000000',
                value=state.get('code', ''), max_length=6,
                keyboard_type=ft.KeyboardType.NUMBER,
                prefix_icon=ft.Icons.PASSWORD, **field_style, text_size=16,
                border_radius=12, border_color=LINE,
                focused_border_color=GREEN,
                disabled=state.get('loading', False),
                on_change=lambda e: state.__setitem__('code', e.control.value or ''),
            ),
        ])
        if mode == 'forgot':
            fields.extend([
                password_field('new_password', 'Mật khẩu mới'),
                ft.TextField(
                    label='Nhập lại mật khẩu mới',
                    value=state.get('confirm_password', ''),
                    **field_style,
                    password=True, prefix_icon=ft.Icons.LOCK_OUTLINE,
                    text_size=14, border_radius=12, border_color=LINE,
                    focused_border_color=GREEN,
                    disabled=state.get('loading', False),
                    on_change=lambda e: state.__setitem__(
                        'confirm_password', e.control.value or ''
                    ),
                ),
            ])

    if state.get('message'):
        fields.append(ft.Container(
            bgcolor='#FDE8EA' if state.get('message_error', True) else '#E4F3E8',
            border_radius=10, padding=11,
            content=ft.Row([
                ft.Icon(
                    ft.Icons.ERROR_OUTLINE if state.get('message_error', True)
                    else ft.Icons.CHECK_CIRCLE_OUTLINE,
                    color=RED if state.get('message_error', True) else GREEN,
                    size=18,
                ),
                ft.Text(
                    state['message'], size=12,
                    color=RED if state.get('message_error', True) else GREEN_DARK,
                    expand=True,
                ),
            ], spacing=8),
        ))

    if mode == 'login' and state['method'] == 'password':
        button_text = 'Đang đăng nhập...' if state.get('loading') else 'Đăng nhập'
        callback = actions['submit']
    elif mode == 'register' and not otp_enabled and not is_verify:
        button_text = 'Đang tạo tài khoản...' if state.get('loading') else 'Tạo tài khoản'
        callback = actions['register_unverified']
    elif is_verify:
        button_text = 'Đang xác minh...' if state.get('loading') else {
            'login': 'Xác minh và đăng nhập',
            'register': 'Xác minh và tạo tài khoản',
            'forgot': 'Xác minh và đặt lại mật khẩu',
        }[mode]
        callback = actions['verify']
    else:
        button_text = 'Đang gửi mã...' if state.get('loading') else {
            'login': 'Gửi mã đăng nhập',
            'register': 'Gửi mã xác minh',
            'forgot': 'Gửi mã khôi phục',
        }[mode]
        callback = actions['request']

    button_icon = (
        ft.Icons.LOGIN if mode == 'login'
        else ft.Icons.PERSON_ADD_OUTLINED
        if mode == 'register' and not otp_enabled
        else ft.Icons.VERIFIED_USER_OUTLINED
    )
    button_label = ft.Row([
        ft.ProgressRing(width=17, height=17, stroke_width=2, color='#FFFFFF')
        if state.get('loading') else ft.Icon(
            button_icon,
            size=18, color='#FFFFFF',
        ),
        ft.Text(button_text, size=14, weight=ft.FontWeight.BOLD, color='#FFFFFF'),
    ], alignment=ft.MainAxisAlignment.CENTER, spacing=9)
    fields.append(ft.ElevatedButton(
        content=button_label,
        on_click=callback,
        disabled=state.get('loading', False),
        width=460, height=50, elevation=2,
        style=ft.ButtonStyle(
            bgcolor=GREEN, color='#FFFFFF',
            overlay_color=GREEN_DARK,
            shape=ft.RoundedRectangleBorder(radius=12),
        ),
    ))
    if mode == 'register' and not is_verify and is_email and otp_enabled:
        fields.extend([
            ft.Text(
                'Không xác minh email; khôi phục tài khoản sau này sẽ cần OTP.',
                size=11, color=MUTED, text_align=ft.TextAlign.CENTER,
            ),
            ft.TextButton(
                'Tạo tài khoản không cần gửi mã',
                on_click=actions['register_unverified'],
                disabled=state.get('loading', False),
                style=ft.ButtonStyle(
                    color=NAVY, overlay_color='#EEF5F0',
                ),
            ),
        ])
    if is_verify:
        fields.append(ft.Row([
            ft.TextButton(
                'Gửi lại mã', on_click=actions['resend'],
                disabled=state.get('loading', False),
                style=ft.ButtonStyle(color=GREEN, overlay_color='#EAF4ED'),
            ),
            ft.Container(expand=True),
            ft.TextButton(
                'Đổi email' if is_email else 'Đổi số điện thoại',
                on_click=lambda _: return_to_contact_form(),
                disabled=state.get('loading', False),
                style=ft.ButtonStyle(color=NAVY, overlay_color='#EEF5F0'),
            ),
        ]))
    elif mode == 'login':
        fields.append(ft.TextButton(
            'Tạo tài khoản mới', on_click=lambda _: switch_mode('register'),
            disabled=state.get('loading', False),
            style=ft.ButtonStyle(color=GREEN, overlay_color='#EAF4ED'),
        ))
    else:
        fields.append(ft.TextButton(
            'Quay lại đăng nhập', on_click=lambda _: switch_mode('login'),
            disabled=state.get('loading', False),
            style=ft.ButtonStyle(color=GREEN, overlay_color='#EAF4ED'),
        ))

    form = ft.Column([
        ft.Row([
            ft.Container(
                bgcolor='#EAF4ED', border_radius=12, padding=10,
                content=ft.Icon(ft.Icons.MONITOR_HEART, color=GREEN, size=24),
            ),
            ft.Column([
                ft.Text('PigSkin AI', size=18, color=NAVY,
                        weight=ft.FontWeight.BOLD),
                ft.Text('STUDIO', size=9, color=GREEN,
                        weight=ft.FontWeight.BOLD),
            ], spacing=0),
        ], spacing=10),
        ft.Container(height=14),
        ft.Text(mode_titles[mode], size=27, color=NAVY,
                weight=ft.FontWeight.BOLD),
        ft.Text(mode_subtitles[mode], size=14, color=MUTED),
        *([ft.Container(
            bgcolor='#E8F4F5', border_radius=10, padding=10,
            content=ft.Row([
                ft.Icon(ft.Icons.LOCK_OUTLINE, color=GREEN, size=17),
                ft.Text('Đăng nhập và tạo tài khoản hiện sử dụng email/mật khẩu.',
                        size=11, color=GREEN_DARK, expand=True),
            ], spacing=8),
        )] if not otp_enabled and not is_verify else []),
        ft.Container(height=6),
        *fields,
        ft.Text(
            'Hỗ trợ nhận diện và thẩm định bệnh da trên heo',
            size=11, color=MUTED, text_align=ft.TextAlign.CENTER,
        ),
    ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
       expand=True, scroll=ft.ScrollMode.AUTO)
    right_panel = ft.Container(
        expand=5, bgcolor='#FFFFFF', border_radius=24,
        padding=ft.padding.symmetric(horizontal=42, vertical=30),
        alignment=ft.alignment.center,
        shadow=ft.BoxShadow(
            blur_radius=28, spread_radius=1,
            color='#172B3B18', offset=ft.Offset(0, 8),
        ),
        content=ft.Container(
            width=520, expand=True, alignment=ft.alignment.center,
            content=form,
        ),
    )
    image_panel = ft.Container(
        expand=6, border_radius=24, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Stack(controls=[
            ft.Image(
                src_base64=_HERO_IMAGE, fit=ft.ImageFit.COVER,
                expand=True, semantics_label='Heo con khỏe mạnh trên đồng cỏ',
            ),
            ft.Container(expand=True, bgcolor='#092114', opacity=0.28),
            ft.Container(
                expand=True, alignment=ft.alignment.bottom_left, padding=38,
                content=ft.Column([
                    ft.Container(
                        bgcolor='#FFFFFF26', border_radius=20,
                        padding=ft.padding.symmetric(horizontal=12, vertical=7),
                        content=ft.Text(
                            'NÔNG NGHIỆP • AI • CHĂM SÓC SỨC KHỎE',
                            size=9, color='#FFFFFF', weight=ft.FontWeight.BOLD,
                        ),
                    ),
                    ft.Text(
                        'Chăm sóc đàn heo\nbắt đầu từ sự thấu hiểu.',
                        size=32, color='#FFFFFF', weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        'Công cụ hỗ trợ quan sát tổn thương da và kết nối '
                        'quy trình thẩm định chuyên môn.',
                        size=13, color='#F1F7F2',
                    ),
                ], spacing=11),
            ),
        ]),
    )
    return ft.Container(
        expand=True, bgcolor='#E6EFE9', padding=18,
        content=ft.Row([image_panel, right_panel], spacing=18, expand=True),
    )
