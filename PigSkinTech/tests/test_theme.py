"""Theme changes keep form state and readable text on both palettes."""

import sys
import unittest
from pathlib import Path

import flet as ft

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.auth_service import apply_theme_text_contrast, toggle_theme_mode


class FakePage:
    def __init__(self, control):
        self.session = {}
        self.theme_mode = ft.ThemeMode.LIGHT
        self.bgcolor = "#F8FAFC"
        self.controls = [control]
        self.overlay = []

    def update(self):
        pass

    def go(self, route):
        raise AssertionError("Theme toggle must not rebuild the route")


class ThemeTest(unittest.TestCase):
    def test_inputs_and_admin_table_follow_theme_without_losing_values(self):
        field = ft.TextField(value="Đang nhập", filled=True, fill_color="#F1F5F9",
                             color="#FFFFFF", hint_style=ft.TextStyle(color="#FFFFFF"))
        dropdown = ft.Dropdown(value="user", options=[ft.dropdown.Option("user", "User")],
                               filled=True, fill_color="#F1F5F9", color="#FFFFFF")
        header = ft.Text("Họ và tên", color="#FFFFFF")
        table = ft.DataTable(heading_row_color="#F1F5F9",
                             columns=[ft.DataColumn(header)],
                             rows=[ft.DataRow(cells=[ft.DataCell(ft.Text("A"))])])
        page = FakePage(ft.Container(bgcolor="#FFFFFF", content=ft.Column([field, dropdown, table])))
        apply_theme_text_contrast(page.controls[0], (248, 250, 252))
        self.assertEqual(field.color, "#0F172A")
        self.assertEqual(dropdown.color, "#0F172A")
        self.assertEqual(header.color, "#0F172A")

        toggle_theme_mode(page)
        self.assertEqual(field.value, "Đang nhập")
        self.assertEqual(field.fill_color, "#0F172A")
        self.assertEqual(dropdown.fill_color, "#0F172A")
        self.assertEqual(table.heading_row_color, "#0F172A")
        self.assertIn(field.color, ("#FFFFFF", "#F8FAFC"))
        self.assertIn(header.color, ("#FFFFFF", "#F8FAFC"))

        toggle_theme_mode(page)
        self.assertEqual(field.value, "Đang nhập")
        self.assertEqual(field.fill_color, "#F1F5F9")
        self.assertEqual(dropdown.color, "#0F172A")
        self.assertEqual(header.color, "#0F172A")

    def test_chat_and_sidebar_text_contrast(self):
        message = ft.Markdown("**Tư vấn**", md_style_sheet=ft.MarkdownStyleSheet(
            p_text_style=ft.TextStyle(color="#FFFFFF"),
            strong_text_style=ft.TextStyle(color="#FFFFFF")))
        chat = ft.Container(bgcolor="#FFFFFF", data="theme_chat_card", content=message)
        name = ft.Text("Tài khoản", color="#FFFFFF")
        sidebar = ft.Container(bgcolor="#1E293B", data="fixed_dark_sidebar_card", content=name)
        page = FakePage(ft.Column([chat, sidebar]))
        apply_theme_text_contrast(page.controls[0], (248, 250, 252))
        self.assertEqual(message.md_style_sheet.p_text_style.color, "#0F172A")
        toggle_theme_mode(page)
        self.assertEqual(chat.bgcolor, "#1E293B")
        self.assertEqual(sidebar.bgcolor, "#1E293B")
        self.assertEqual(name.color, "#FFFFFF")
        self.assertEqual(message.md_style_sheet.p_text_style.color, "#FFFFFF")


if __name__ == "__main__":
    unittest.main()
