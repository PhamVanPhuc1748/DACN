import unittest

from controllers.session import refresh_session


class SessionTests(unittest.TestCase):
    def test_locked_account_invalidates_session(self):
        self.assertIsNone(refresh_session({'id': 2, 'role': 'user'},
            lambda _: {'id': 2, 'role': 'user', 'active': False}))

    def test_changed_role_invalidates_session(self):
        self.assertIsNone(refresh_session({'id': 2, 'role': 'expert'},
            lambda _: {'id': 2, 'role': 'user', 'active': True}))

    def test_unchanged_session_refreshes_profile(self):
        fresh={'id': 2, 'role': 'user', 'active': True, 'display_name': 'New name'}
        self.assertIs(refresh_session({'id': 2, 'role': 'user'},lambda _: fresh),fresh)
