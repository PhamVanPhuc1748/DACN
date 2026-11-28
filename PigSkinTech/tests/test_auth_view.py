"""Run the Flet login handlers against temporary SQLite authentication."""
import asyncio
import secrets
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import flet as ft

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import store
from views import auth_view


class LoginPage:
    def __init__(self):
        self.session = {}
        self.route = "/login"

    def update(self):
        pass

    def go(self, route):
        self.route = route

    def run_task(self, handler):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(handler())
        else:
            loop.create_task(handler())


def flatten(control):
    yield control
    for child in control._get_children():
        yield from flatten(child)


class AuthViewTest(unittest.TestCase):
    def setUp(self):
        resources = ExitStack()
        self.addCleanup(resources.close)
        root = Path(resources.enter_context(tempfile.TemporaryDirectory()))
        self.password = secrets.token_urlsafe(24)
        self.settings = {"DATABASE_ENGINE": "sqlite", "PIGSKIN_DEMO_MODE": "true",
                         "PIGSKIN_DEMO_PASSWORD": self.password}
        resources.enter_context(patch.multiple(
            store, DB=root / "test.db", IMAGE_DIR=root / "images", pyodbc=None,
            read_settings=lambda: self.settings, _SHARED_RAW_CONN=None, _SHARED_ENGINE_TYPE=None,
            _SHARED_CONN_STR="", _SCHEMA_INITIALIZED_KEY=None, _ACTIVE_DB_INFO={},
        ))
        store.initialize()
        self.addCleanup(store._SHARED_RAW_CONN.close)
        self.assertEqual(store.get_db_status()["engine"], "SQLite")

    def view(self, **overrides):
        page = LoginPage()
        with patch.object(auth_view, "read_settings", return_value={**self.settings, **overrides}):
            controls = list(flatten(auth_view.build_auth_view(page)))
        return page, controls

    def button(self, controls, label):
        return next(c for c in controls if isinstance(c, ft.Container)
                    and isinstance(c.content, ft.Text) and label in (c.content.value or ""))

    def test_all_quick_buttons_use_sqlite_credentials_and_roles(self):
        for label, role in (("Nông dân", "user"), ("Chuyên gia", "expert"), ("Quản trị", "admin")):
            with self.subTest(role=role):
                page, controls = self.view()
                self.button(controls, label).on_click(None)
                self.assertEqual(page.route, f"/{role}")
                self.assertEqual(page.session["current_user"]["role"], role)
                password_field = next(c for c in controls if isinstance(c, ft.TextField) and c.password)
                self.assertEqual(password_field.value, self.password)

    def test_wrong_demo_password_and_locked_account_are_rejected(self):
        page, controls = self.view(PIGSKIN_DEMO_PASSWORD=secrets.token_urlsafe(24))
        self.button(controls, "Quản trị").on_click(None)
        self.assertEqual(page.session, {})
        with store.conn() as db:
            db.execute("UPDATE users SET is_active=0 WHERE role=?", ("admin",))
        page, controls = self.view()
        self.button(controls, "Quản trị").on_click(None)
        self.assertEqual(page.route, "/login")
        self.assertEqual(page.session, {})

    def test_demo_disabled_blocks_quick_click_but_manual_login_works(self):
        page, controls = self.view(PIGSKIN_DEMO_MODE="false")
        self.button(controls, "Nông dân").on_click(None)
        self.assertEqual(page.session, {})
        email, password = [c for c in controls if isinstance(c, ft.TextField)]
        email.value = next(a["email"] for a in store.DEFAULT_RBAC_USERS if a["role"] == "user")
        password.value = self.password
        self.button(controls, "Đăng nhập  ").on_click(None)
        self.assertEqual(page.route, "/user")
