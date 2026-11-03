"""Build Flet controls without starting a desktop window or opening LocalDB."""

import types
import inspect
import asyncio
import unittest
from unittest.mock import patch

import main as app
from views.model_operations import build_model_view


class FakePage:
    def __init__(self):
        self.window = types.SimpleNamespace(width=1510, height=920)
        self.overlay = []
        self.controls = []

    def add(self, control):
        self.controls.append(control)

    def update(self):
        pass


class UISmokeTests(unittest.TestCase):
    def test_inference_runs_off_the_flet_event_loop(self):
        source = inspect.getsource(app.main)
        self.assertIn('await asyncio.to_thread(predict,path)', source)
        self.assertIn('await asyncio.to_thread(prewarm_ai_worker)', source)

    def text_values(self, control):
        values=[]
        pending=[control]
        seen=set()
        while pending:
            item=pending.pop()
            if item is None or id(item) in seen:
                continue
            seen.add(id(item))
            if isinstance(item, app.ft.Text):
                values.append(item.value)
            content=getattr(item,'content',None)
            if content is not None:
                pending.append(content)
            pending.extend(getattr(item,'controls',[]) or [])
            pending.extend(getattr(item,'actions',[]) or [])
        return values

    def controls_of_type(self, root, control_type):
        found=[]
        pending=[root]
        seen=set()
        while pending:
            item=pending.pop()
            if item is None or id(item) in seen:
                continue
            seen.add(id(item))
            if isinstance(item,control_type):
                found.append(item)
            content=getattr(item,'content',None)
            if content is not None:
                pending.append(content)
            pending.extend(getattr(item,'controls',[]) or [])
            pending.extend(getattr(item,'actions',[]) or [])
            suffix=getattr(item,'suffix',None)
            if suffix is not None:
                pending.append(suffix)
        return found

    def click(self, control):
        result=control.on_click(types.SimpleNamespace(control=control))
        if inspect.isawaitable(result):
            asyncio.run(result)

    def build_role(self, role):
        page = FakePage()
        user = {'id': 7, 'email': 'user@example.test', 'display_name': 'User',
                'role': role, 'active': True, 'created_at': '2026-11-03 10:00:00'}
        metrics={'disease_percent':0,'classified':0,'disease_cases':0,
                 'active_accounts':2,'total_accounts':2,'logins_30d':0,
                 'total_cases':12,'awaiting_second_review':0,'published':0,
                 'cases_by_month':[],'logins_by_month':[]}
        case_totals={'total':12,'pending':12,'second_review':0,
                     'published':0,'inferred':0,'authored':0}
        with patch.object(app, 'account_count', return_value=2), patch.object(
            app, 'authenticate', return_value=user
        ), patch.object(app, 'current_account', return_value=user), patch.object(
            app, 'recent', return_value=[]
        ), patch.object(app, 'unseen_result_count', return_value=0), patch.object(
            app, 'admin_metrics', return_value=metrics
        ), patch.object(app, 'case_summary', return_value=case_totals
        ), patch.object(app, 'list_users', return_value=[]
        ), patch.object(app, 'support_threads', return_value=[]
        ), patch.object(app, 'support_unread_count', return_value=0
        ):
            app.main(page)
            login_button=self.controls_of_type(
                page.controls[0],app.ft.ElevatedButton
            )[0]
            self.click(login_button)
            self.assertEqual(len(page.controls), 1)
            self.assertIsInstance(page.controls[0], app.ft.Row)
            return page

    def test_auth_and_user_dashboard_build(self):
        page=self.build_role('user')
        self.assertEqual((page.window.width,page.window.height),(1366,768))

    def test_expert_dashboard_build(self):
        self.build_role('expert')

    def test_admin_dashboard_build(self):
        self.build_role('admin')

    def test_admin_navigation_highlight_and_content_are_synchronized(self):
        page=self.build_role('admin')
        shell=page.controls[0]
        sidebar=shell.controls[0].content
        nav=next(control for control in sidebar.controls
                 if isinstance(control,app.ft.Column) and
                 any(getattr(item,'tooltip',None)=='Dataset' for item in control.controls))
        workspace_body=shell.controls[1].content.controls[1]
        previous_content=workspace_body.content
        account={'id':7,'email':'admin@example.test','display_name':'Admin',
                 'role':'admin','active':True}
        with patch.object(app,'current_account',return_value=account), patch.object(
            app,'list_users',return_value=[]
        ), patch.object(app,'support_threads',return_value=[]), patch.object(
            app,'support_unread_count',return_value=0):
            for name,expected_sections in [('Dataset',3),('Huấn luyện',5),
                                           ('Mô hình AI',3),('Quản lý tài khoản',2),
                                           ('Hỗ trợ',2)]:
                item=next(control for control in nav.controls if control.tooltip==name)
                item.on_click(types.SimpleNamespace(control=item))
                self.assertEqual(item.bgcolor,app.NAV_SELECTED)
                self.assertTrue(all(other.bgcolor==app.SIDEBAR for other in nav.controls
                                    if other is not item))
                self.assertIsNot(workspace_body.content,previous_content)
                self.assertEqual(len(workspace_body.content.controls),expected_sections)
                previous_content=workspace_body.content

    def test_model_operations_build_with_verified_checkpoint(self):
        controls = build_model_view(app.PALETTES['dark'], app.label,
                                    app.block, app.caption_head)
        self.assertEqual(len(controls), 3)

    def test_database_startup_error_renders_recoverable_auth_screen(self):
        page=FakePage()
        with self.assertLogs('pigskin',level='ERROR'), patch.object(
            app,'account_count',side_effect=RuntimeError('offline')):
                app.main(page)
        values=self.text_values(page.controls[0])
        self.assertTrue(any('Không thể kết nối SQL Server LocalDB' in value for value in values))

    def test_auth_layout_is_split_and_credentials_start_empty(self):
        page=FakePage()
        with patch.object(app,'account_count',return_value=1):
            app.main(page)
        root=page.controls[0]
        self.assertIsInstance(root,app.ft.Container)
        self.assertIsInstance(root.content,app.ft.Row)
        left,right=root.content.controls
        self.assertEqual((left.expand,right.expand),(6,5))
        self.assertEqual(left.content.controls[0].fit,app.ft.ImageFit.COVER)
        password_fields=[
            field for field in self.controls_of_type(root,app.ft.TextField)
            if field.password
        ]
        self.assertTrue(password_fields)
        self.assertTrue(all(not field.value for field in password_fields))
        self.assertIn('Đăng nhập vào hệ thống',self.text_values(root))
        self.assertIn(
            'Hệ thống hỗ trợ nhận diện và thẩm định bệnh da trên heo.',
            self.text_values(root),
        )
        hero_text=next(
            value for value in self.text_values(root)
            if value.startswith('Chăm sóc đàn heo')
        )
        self.assertIn('\n',hero_text)
        self.assertNotIn('\\n',hero_text)

    def test_login_otp_without_provider_reports_unconfigured_service(self):
        page=FakePage()
        user={'id':7,'email':'user@example.test','display_name':'User',
              'role':'user','active':True,'created_at':'2026-11-03 10:00:00'}
        with patch.object(app,'account_count',return_value=2), patch.object(
            app,'find_verified_contact',return_value=user), patch.object(
            app,'OTPService',
            side_effect=app.OTPNotConfiguredError(
                'Chưa cấu hình dịch vụ gửi mã.'
            )):
            app.main(page)
            root=page.controls[0]
            contact=next(
                field for field in self.controls_of_type(root,app.ft.TextField)
                if field.label=='Email'
            )
            contact.value='user@example.test'
            contact.on_change(types.SimpleNamespace(control=contact))
            otp_toggle=next(
                button for button in self.controls_of_type(root,app.ft.TextButton)
                if button.text=='Mã OTP'
            )
            self.click(otp_toggle)
            request=self.controls_of_type(page.controls[0],app.ft.ElevatedButton)[0]
            self.click(request)
        self.assertTrue(any(
            'Chưa cấu hình dịch vụ gửi mã' in value
            for value in self.text_values(page.controls[0])
        ))

    def test_registration_and_recovery_views_build_for_email_and_phone(self):
        state={
            'mode':'register','method':'otp','channel':'email','step':'form',
            'contact':'','display_name':'','password':'','confirm_password':'',
            'new_password':'','code':'','show_password':False,'loading':False,
            'message':'',
        }
        actions={name:(lambda *_:None) for name in (
            'render','submit','request','verify','resend','register_unverified'
        )}
        register_view=app.build_auth_view(state,actions)
        register_text=self.text_values(register_view)
        self.assertIn('Tạo tài khoản mới',register_text)
        register_button_labels=[
            button.text for button in self.controls_of_type(
                register_view,app.ft.TextButton
            )
        ]
        self.assertIn('Tạo tài khoản không cần gửi mã',register_button_labels)
        self.assertTrue(any(
            'khôi phục tài khoản sau này sẽ cần OTP' in value
            for value in register_text
        ))
        register_fields=self.controls_of_type(register_view,app.ft.TextField)
        self.assertIn('Email',[field.label for field in register_fields])
        state['channel']='sms'
        phone_register_view=app.build_auth_view(state,actions)
        self.assertIn(
            'Số điện thoại Việt Nam',
            [field.label for field in self.controls_of_type(
                phone_register_view,app.ft.TextField
            )],
        )
        self.assertNotIn(
            'Tạo tài khoản không cần gửi mã',
            [button.text for button in self.controls_of_type(
                phone_register_view,app.ft.TextButton
            )],
        )

        state.update(mode='forgot',channel='email',step='verify')
        recovery_view=app.build_auth_view(state,actions)
        recovery_text=self.text_values(recovery_view)
        self.assertIn('Khôi phục mật khẩu',recovery_text)
        recovery_fields=self.controls_of_type(recovery_view,app.ft.TextField)
        self.assertIn('Mã OTP',[field.label for field in recovery_fields])
        self.assertIn('Mật khẩu mới',[field.label for field in recovery_fields])

    def test_password_recovery_does_not_disclose_account_existence(self):
        user={'id':7,'email':'user@example.test','display_name':'User',
              'role':'user','active':True,'created_at':'2026-11-03 10:00:00'}

        class ReadyOTP:
            def __init__(self,*_):
                pass

            def request_code(self,*_):
                return 'a' * 64

        def reset_screen(found_account):
            page=FakePage()
            with patch.object(app,'account_count',return_value=2), patch.object(
                app,'find_contact_for_password_reset',
                return_value=user if found_account else None
            ), patch.object(app,'OTPService',ReadyOTP), patch.object(
                app,'configured_provider',return_value=object()
            ), patch.object(app,'otp_schema_ready',return_value=True):
                app.main(page)
                forgot=next(
                    button for button in self.controls_of_type(
                        page.controls[0],app.ft.TextButton
                    ) if button.text=='Quên mật khẩu?'
                )
                self.click(forgot)
                contact=next(
                    field for field in self.controls_of_type(
                        page.controls[0],app.ft.TextField
                    ) if field.label=='Email'
                )
                contact.value='user@example.test'
                contact.on_change(types.SimpleNamespace(control=contact))
                request=self.controls_of_type(
                    page.controls[0],app.ft.ElevatedButton
                )[0]
                self.click(request)
            return self.text_values(page.controls[0]), [
                field.label for field in self.controls_of_type(
                    page.controls[0],app.ft.TextField
                )
            ]

        unknown_screen=reset_screen(False)
        known_screen=reset_screen(True)
        self.assertEqual(unknown_screen,known_screen)
        self.assertIn('Mã OTP',known_screen[1])

    def test_closed_support_thread_has_no_reply_field(self):
        page=FakePage()
        user={'id':7,'email':'user@example.test','display_name':'User',
              'role':'user','active':True,'created_at':'2026-11-03 10:00:00'}
        totals={'total':0,'pending':0,'second_review':0,'published':0,
                'inferred':0,'authored':0}
        thread={'id':5,'user_id':7,'subject':'Đã xử lý','status':'closed',
                'created_at':'2026-11-03 10:00:00','updated_at':'2026-11-03 10:30:00',
                'last_message':'Hoàn tất','user_message_count':1,'staff_message_count':1}
        messages=[{'id':1,'thread_id':5,'sender_id':7,'sender_name':'User',
                   'sender_role':'user','body':'Cần hỗ trợ','created_at':'2026-11-03 10:00:00'}]
        with patch.object(app,'account_count',return_value=2), patch.object(
            app,'authenticate',return_value=user), patch.object(
            app,'current_account',return_value=user), patch.object(
            app,'recent',return_value=[]), patch.object(
            app,'case_summary',return_value=totals), patch.object(
            app,'unseen_result_count',return_value=0), patch.object(
            app,'support_unread_count',return_value=0), patch.object(
            app,'support_threads',return_value=[thread]), patch.object(
            app,'support_messages',return_value=messages), patch.object(
            app,'mark_support_thread_seen'):
            app.main(page)
            login=self.controls_of_type(
                page.controls[0],app.ft.ElevatedButton
            )[0]
            self.click(login)
            shell=page.controls[0]
            sidebar=shell.controls[0].content
            nav=next(control for control in sidebar.controls
                     if isinstance(control,app.ft.Column) and
                     any(getattr(item,'tooltip',None)=='Hỗ trợ' for item in control.controls))
            support=next(item for item in nav.controls if item.tooltip=='Hỗ trợ')
            support.on_click(types.SimpleNamespace(control=support))
            thread_item=(shell.controls[1].content.controls[1].content.controls[1]
                .controls[0].content.controls[1].controls[0])
            thread_item.on_click(types.SimpleNamespace(control=thread_item))
            workspace=shell.controls[1].content.controls[1].content
            values=self.text_values(workspace)
            self.assertIn('CUỘC TRÒ CHUYỆN ĐÃ ĐÓNG',values)
            fields=[]
            pending=[workspace]
            while pending:
                item=pending.pop()
                if isinstance(item,app.ft.TextField):
                    fields.append(item)
                content=getattr(item,'content',None)
                if content is not None:
                    pending.append(content)
                pending.extend(getattr(item,'controls',[]) or [])
            self.assertFalse(any(field.label=='Nhập câu trả lời' for field in fields))


if __name__ == '__main__':
    unittest.main()
