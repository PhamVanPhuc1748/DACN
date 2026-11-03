"""Baseline service tests that never connect to the real PigSkinAI database."""

import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from services import accounts, store, workflow

# Unit tests exercise business SQL against scripted connections, never schema
# initialization. Production still performs its guarded one-time initialization.
accounts._initialized = True
store._initialized = True
workflow._initialized = True


class Result:
    def __init__(self, rows=None, rowcount=1):
        self.rows = list(rows or [])
        self.rowcount = rowcount

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class ScriptedConnection:
    """Return predetermined results and retain every SQL call for assertions."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def execute(self, query, parameters=()):
        self.calls.append((" ".join(query.split()), tuple(parameters)))
        if not self.results:
            raise AssertionError(f"Unexpected SQL call: {query}")
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class ConnectionFactory:
    def __init__(self, connections):
        self.connections = list(connections)

    def __call__(self):
        if not self.connections:
            raise AssertionError("Unexpected database connection")
        return self.connections.pop(0)


def public_user(**overrides):
    data = {
        "id": 7,
        "email": "user@example.test",
        "display_name": "Test User",
        "password_salt": "00" * 16,
        "password_hash": "",
        "role": "user",
        "active": 1,
        "created_at": "2026-11-03 10:00:00",
    }
    data.update(overrides)
    return data


class AccountTests(unittest.TestCase):
    def test_initialize_defers_new_account_schema_for_existing_legacy_tables(self):
        connection = ScriptedConnection([Result(), Result()])
        with patch.object(accounts, "_initialized", False), patch.object(
            accounts, "conn", ConnectionFactory([connection])
        ):
            accounts.initialize()

        create_users = connection.calls[0][0]
        self.assertIn("IF OBJECT_ID('dbo.users', 'U') IS NULL", create_users)
        self.assertIn("EXEC sys.sp_executesql N'", create_users)
        self.assertIn("CREATE TABLE dbo.users", create_users)
        self.assertIn("CREATE UNIQUE INDEX UX_users_phone", create_users)
        self.assertNotIn("ALTER TABLE dbo.users", create_users)

    def test_authenticate_accepts_valid_active_account_and_logs_event(self):
        row = public_user()
        row["password_hash"] = accounts._password_hash("correct-pass", row["password_salt"])
        connection = ScriptedConnection([Result([row]), Result()])

        with patch.object(accounts, "initialize"), patch.object(
            accounts, "conn", ConnectionFactory([connection])
        ):
            authenticated = accounts.authenticate("USER@example.test", "correct-pass")

        self.assertEqual(authenticated["id"], 7)
        self.assertNotIn("password_hash", authenticated)
        self.assertEqual(connection.calls[0][1], ("user@example.test",))
        self.assertIn("INSERT INTO dbo.login_events", connection.calls[1][0])

    def test_authenticate_rejects_locked_account_without_logging_event(self):
        row = public_user(active=0)
        lookup = ScriptedConnection([Result([row])])

        with patch.object(accounts, "initialize"), patch.object(
            accounts, "conn", ConnectionFactory([lookup])
        ):
            authenticated = accounts.authenticate("user@example.test", "correct-pass")

        self.assertIsNone(authenticated)

    def test_last_active_admin_cannot_be_demoted(self):
        connection = ScriptedConnection([
            Result([{"role": "admin", "active": 1}]),
            Result([{"id": 1, "role": "admin"}]),
            Result([{0: 1, "count": 1}]),
        ])

        with patch.object(accounts, "conn", ConnectionFactory([connection])):
            with self.assertRaises(ValueError):
                accounts.update_role(1, "user", 2)

    def test_authenticate_rejects_non_string_input(self):
        with patch.object(accounts, "initialize"):
            self.assertIsNone(accounts.authenticate(None, "password"))
            self.assertIsNone(accounts.authenticate("user@example.test", None))

    def test_update_active_requires_boolean(self):
        with self.assertRaises(ValueError):
            accounts.update_active(7, 1, 2)

    def test_verified_registration_always_creates_a_user_role(self):
        created = public_user(email='verified@example.test', role='user')
        connection = ScriptedConnection([Result([created]), Result()])
        verification = {
            'destination': 'verified@example.test',
            'channel': 'email',
            'purpose': 'registration',
        }
        with patch.object(accounts, 'initialize'), patch.object(
            accounts, 'conn', ConnectionFactory([connection])
        ):
            result = accounts.register(
                'VERIFIED@example.test', 'correct-pass', 'Verified User',
                verified_contact=verification,
            )
        self.assertEqual(result['role'], 'user')
        insert = connection.calls[0]
        self.assertIn('email_verified, phone_verified', insert[0])
        self.assertEqual(insert[1][0:4], ('verified@example.test', None, 1, 0))
        self.assertEqual(insert[1][7], 'user')
        self.assertNotIn('password_hash', result)

    def test_unverified_email_registration_skips_otp_but_stays_user_role(self):
        created = public_user(email='unverified@example.test', role='user')
        connection = ScriptedConnection([Result([created]), Result()])
        with patch.object(accounts, 'initialize'), patch.object(
            accounts, 'conn', ConnectionFactory([connection])
        ):
            result = accounts.register_unverified_email(
                'UNVERIFIED@example.test', 'correct-pass', 'Unverified User'
            )

        self.assertEqual(result['email'], 'unverified@example.test')
        self.assertEqual(result['role'], 'user')
        insert = connection.calls[0]
        self.assertIn('INSERT INTO dbo.users', insert[0])
        self.assertNotIn('phone', insert[0])
        self.assertNotIn('email_verified', insert[0])
        self.assertEqual(insert[1][0], 'unverified@example.test')
        self.assertEqual(insert[1][4], 'user')
        self.assertIn('INSERT INTO dbo.login_events', connection.calls[1][0])
        self.assertNotIn('password_hash', result)

    def test_registration_requires_matching_verification_and_has_no_role_argument(self):
        with patch.object(accounts, 'initialize'):
            with self.assertRaisesRegex(ValueError, 'xác minh'):
                accounts.register(
                    'user@example.test', 'correct-pass', 'User',
                    verified_contact={
                        'destination': 'other@example.test',
                        'channel': 'email',
                        'purpose': 'registration',
                    },
                )
        self.assertNotIn('role', inspect.signature(accounts.register).parameters)

    def test_verified_phone_registration_is_supported_without_an_email(self):
        created = public_user(email=None, phone='+84901234567', role='user')
        connection = ScriptedConnection([Result([created]), Result()])
        verification = {
            'destination': '+84901234567',
            'channel': 'sms',
            'purpose': 'registration',
        }
        with patch.object(accounts, 'initialize'), patch.object(
            accounts, 'conn', ConnectionFactory([connection])
        ):
            result = accounts.register(
                None, 'correct-pass', 'Phone User', '0901 234 567', verification
            )
        self.assertIsNone(result['email'])
        self.assertEqual(result['phone'], '+84901234567')
        self.assertEqual(connection.calls[0][1][0:4],
                         (None, '+84901234567', 0, 1))
        self.assertEqual(connection.calls[0][1][7], 'user')

    def test_otp_login_requires_a_verified_contact_and_logs_success(self):
        row = public_user()
        connection = ScriptedConnection([Result([row]), Result()])
        with patch.object(accounts, 'initialize'), patch.object(
            accounts, 'conn', ConnectionFactory([connection])
        ):
            result = accounts.authenticate_otp('USER@example.test', 'email')
        self.assertEqual(result['id'], 7)
        self.assertIn('email_verified=1', connection.calls[0][0])
        self.assertIn('INSERT INTO dbo.login_events', connection.calls[1][0])

    def test_password_recovery_replaces_the_password_hash(self):
        connection = ScriptedConnection([Result([{'id': 7}]), Result()])
        verification = {
            'destination': 'user@example.test',
            'channel': 'email',
            'purpose': 'password_reset',
        }
        with patch.object(accounts, 'initialize'), patch.object(
            accounts, 'conn', ConnectionFactory([connection])
        ):
            accounts.reset_password(
                'USER@example.test', 'email', 'new-pass-123', verification
            )
        self.assertNotIn('email_verified=1', connection.calls[0][0])
        self.assertIn('UPDATE dbo.users', connection.calls[1][0])
        self.assertIn('email_verified=1', connection.calls[1][0])
        salt, password_hash, user_id = connection.calls[1][1]
        self.assertEqual(user_id, 7)
        self.assertNotEqual(password_hash, 'new-pass-123')
        self.assertEqual(
            password_hash,
            accounts._password_hash('new-pass-123', salt),
        )

    def test_password_reset_requires_a_matching_consumed_otp_result(self):
        with patch.object(accounts, 'initialize'):
            with self.assertRaisesRegex(ValueError, 'xác minh'):
                accounts.reset_password(
                    'user@example.test', 'email', 'new-pass-123', None
                )

    def test_recovery_can_find_a_legacy_unverified_email_for_otp(self):
        connection = ScriptedConnection([Result([public_user()])])
        with patch.object(accounts, 'initialize'), patch.object(
            accounts, 'conn', ConnectionFactory([connection])
        ):
            account=accounts.find_contact_for_password_reset(
                'USER@example.test','email'
            )
        self.assertEqual(account['email'],'user@example.test')
        self.assertNotIn('email_verified=1',connection.calls[0][0])


class CaseStoreTests(unittest.TestCase):
    def test_summary_scopes_user_and_uses_full_table(self):
        totals={key: 0 for key in ('total','pending','second_review',
                                   'published','inferred','authored')}
        totals['total']=12
        connection=ScriptedConnection([
            Result([{'role':'user','active':1}]), Result([totals])
        ])
        with patch.object(store,'conn',ConnectionFactory([connection])):
            summary=store.case_summary(7)
        self.assertEqual(summary['total'],12)
        self.assertIn('WHERE user_id=?',connection.calls[1][0])
        self.assertEqual(connection.calls[1][1],(7,7))

    def test_user_history_hides_unpublished_expert_result(self):
        row={'id': 9, 'result_status': 'pending_approval',
             'expert_result': 'Draft diagnosis', 'expert_notes': 'Draft note'}
        connection = ScriptedConnection([
            Result([{"role": "user", "active": 1}]), Result([row])
        ])
        with patch.object(store, "initialize"), patch.object(
            store, "conn", ConnectionFactory([connection])
        ):
            items = store.recent(owner_id=7, actor_id=7)
        self.assertIsNone(items[0]['expert_result'])
        self.assertIsNone(items[0]['expert_notes'])

    def test_history_pagination_is_scoped_and_parameterized(self):
        connection = ScriptedConnection([
            Result([{"role": "user", "active": 1}]), Result([])
        ])
        with patch.object(store, "initialize"), patch.object(
            store, "conn", ConnectionFactory([connection])
        ):
            rows = store.recent('PIG', owner_id=7, actor_id=7,
                                limit=25, offset=25, status='published')
        self.assertEqual(rows, [])
        self.assertIn('OFFSET ? ROWS FETCH NEXT ? ROWS ONLY', connection.calls[1][0])
        self.assertEqual(connection.calls[1][1][-3:], ('published', 25, 25))

    def test_history_rejects_other_users_cases(self):
        connection = ScriptedConnection([Result([{"role": "user", "active": 1}])])
        with patch.object(store, "initialize"), patch.object(
            store, "conn", ConnectionFactory([connection])
        ):
            with self.assertRaises(ValueError):
                store.recent(owner_id=8, actor_id=7)

    def test_save_archives_source_and_generates_case_id(self):
        insert = Result([{"id": 42}])
        authorization = ScriptedConnection([Result([{"role": "user", "active": 1}])])
        connection = ScriptedConnection([Result([{"role": "user", "active": 1}]), insert, Result()])
        result = {"mode": "unavailable", "label": None, "confidence": None, "scores": []}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sample.jpg"
            Image.new("RGB", (20, 10)).save(source)
            info = store.inspect_image(source)
            archive = root / "archive"
            with patch.object(store, "initialize"), patch.object(
                store, "IMAGE_DIR", archive
            ), patch.object(
                store, "conn", ConnectionFactory([authorization, connection])
            ):
                record_id = store.save(info, result, source_image=source, owner_id=7)

            self.assertEqual(record_id, 42)
            self.assertEqual(len(list(archive.glob("*.jpg"))), 1)
            self.assertEqual(connection.calls[2][1], ("PS-000042", 42))

    def test_delete_removes_only_owned_unclaimed_case_and_archived_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary)
            image = archive / "case.jpg"
            image.write_bytes(b"test")
            connection = ScriptedConnection([
                Result([{"role": "user", "active": 1}]),
                Result([{"image_path": str(image)}]),
                Result(rowcount=1),
            ])
            with patch.object(store, "IMAGE_DIR", archive), patch.object(
                store, "conn", ConnectionFactory([connection])
            ):
                store.delete(9, 7)

            self.assertFalse(image.exists())
            self.assertIn("user_id=?", connection.calls[1][0])
            self.assertIn("expert_id IS NULL", connection.calls[1][0])

    def test_update_case_is_scoped_to_owner_and_editable_statuses(self):
        connection = ScriptedConnection([Result([{"role": "user", "active": 1}]), Result(rowcount=1)])
        with patch.object(store, "conn", ConnectionFactory([connection])):
            changed = store.update_case(9, {"animal_id": "PIG-9"}, owner_id=7)

        self.assertTrue(changed)
        self.assertIn("user_id=?", connection.calls[1][0])
        self.assertIn("result_status IN ('not_started','returned')", connection.calls[1][0])

    def test_locked_user_session_must_not_be_able_to_update_case(self):
        connection = ScriptedConnection([Result([{"role": "user", "active": 0}])])
        with patch.object(store, "conn", ConnectionFactory([connection])):
            with self.assertRaises(ValueError):
                store.update_case(9, {"animal_id": "PIG-9"}, owner_id=7)

    def test_stale_role_session_must_not_be_able_to_read_user_history(self):
        connection = ScriptedConnection([Result([{"role": "expert", "active": 1}])])
        with patch.object(store, "initialize"), patch.object(
            store, "conn", ConnectionFactory([connection])
        ):
            with self.assertRaises(ValueError):
                store.recent(owner_id=7, actor_id=7)

    def test_history_rejects_invalid_search_and_boolean_page_size(self):
        with patch.object(store, "initialize"):
            with self.assertRaises(ValueError):
                store.recent(None, owner_id=7, actor_id=7)
            with self.assertRaises(ValueError):
                store.recent('', owner_id=7, actor_id=7, limit=True)


class ExpertWorkflowTests(unittest.TestCase):
    def test_changed_role_invalidates_expert_submit_permission(self):
        connection = ScriptedConnection([
            Result([{"role": "user", "active": 1}]),
        ])
        with patch.object(workflow, "initialize"), patch.object(
            workflow, "conn", ConnectionFactory([connection])
        ):
            with self.assertRaises(ValueError):
                workflow.submit_expert_result(12, 3, "condition", "Cần theo dõi")

    def test_locked_expert_session_cannot_submit_result(self):
        connection = ScriptedConnection([
            Result([{"role": "expert", "active": 0}]),
        ])
        with patch.object(workflow, "initialize"), patch.object(
            workflow, "conn", ConnectionFactory([connection])
        ):
            with self.assertRaises(ValueError):
                workflow.submit_expert_result(12, 3, "condition", "Cần theo dõi")

    def test_active_expert_can_submit_result_for_second_review(self):
        connection = ScriptedConnection([
            Result([{"role": "expert", "active": 1}]),
            Result(rowcount=1),
        ])
        with patch.object(workflow, "initialize"), patch.object(
            workflow, "conn", ConnectionFactory([connection])
        ):
            workflow.submit_expert_result(12, 3, "condition", "Cần theo dõi", "Ghi chú")

        self.assertIn("result_status='pending_approval'", connection.calls[1][0])
        self.assertEqual(connection.calls[1][1][0], "condition")

    def test_author_cannot_approve_own_result(self):
        connection = ScriptedConnection([
            Result([{"role": "expert", "active": 1}]),
            Result([{"id": 12, "expert_id": 3, "result_status": "pending_approval"}]),
        ])
        with patch.object(workflow, "initialize"), patch.object(
            workflow, "conn", ConnectionFactory([connection])
        ):
            with self.assertRaises(ValueError):
                workflow.review_expert_result(12, 3, True)

    def test_second_expert_can_publish_result(self):
        connection = ScriptedConnection([
            Result([{"role": "expert", "active": 1}]),
            Result([{"id": 12, "expert_id": 3, "result_status": "pending_approval"}]),
            Result(rowcount=1),
        ])
        with patch.object(workflow, "initialize"), patch.object(
            workflow, "conn", ConnectionFactory([connection])
        ):
            workflow.review_expert_result(12, 4, True)

        self.assertIn("result_status='published'", connection.calls[2][0])
        self.assertEqual(connection.calls[2][1][0], 4)

    def test_pending_result_cannot_be_resubmitted_by_author(self):
        connection = ScriptedConnection([
            Result([{"role": "expert", "active": 1}]),
            Result(rowcount=0),
        ])
        with patch.object(workflow, "initialize"), patch.object(
            workflow, "conn", ConnectionFactory([connection])
        ):
            with self.assertRaises(ValueError):
                workflow.submit_expert_result(12, 3, "condition", "Thay đổi")
        self.assertNotIn("pending_approval' AND expert_id", connection.calls[1][0])

    def test_review_decision_must_be_boolean(self):
        with patch.object(workflow, "initialize"):
            with self.assertRaises(ValueError):
                workflow.review_expert_result(12, 4, 'yes')


class SupportTests(unittest.TestCase):
    def test_closed_thread_rejects_expert_reply(self):
        connection = ScriptedConnection([
            Result([{"role": "expert", "active": 1}]),
            Result(rowcount=0),
            Result([{"id": 5, "user_id": 7, "status": "closed"}]),
        ])
        with patch.object(workflow, "initialize"), patch.object(
            workflow, "conn", ConnectionFactory([connection])
        ):
            with self.assertRaises(ValueError):
                workflow.reply_support_thread(5, 3, 'expert', 'Trả lời')
        self.assertEqual(len(connection.calls), 3)

    def test_expert_reply_clears_staff_badge_and_notifies_user(self):
        connection = ScriptedConnection([
            Result([{"role": "expert", "active": 1}]),
            Result(rowcount=0),
            Result([{"id": 5, "user_id": 7, "status": "open"}]),
            Result(rowcount=1),
            Result(rowcount=1),
        ])
        with patch.object(workflow, "initialize"), patch.object(
            workflow, "conn", ConnectionFactory([connection])
        ):
            workflow.reply_support_thread(5, 3, 'expert', 'Trả lời')

        update_sql, update_params = connection.calls[4]
        self.assertIn('user_unread=?', update_sql)
        self.assertIn('staff_unread=?', update_sql)
        self.assertEqual(update_params[0], 'answered')
        self.assertEqual(update_params[2:4], (1, 0))

    def test_expert_badge_counts_unread_support_threads(self):
        connection = ScriptedConnection([
            Result([{"role": "expert", "active": 1}]),
            Result(rowcount=0),
            Result([{"count": 2}]),
        ])
        with patch.object(workflow, "initialize"), patch.object(
            workflow, "conn", ConnectionFactory([connection])
        ):
            count = workflow.support_unread_count(3, 'expert')

        self.assertEqual(count, 2)
        self.assertIn("status='open'", connection.calls[2][0])

    def test_user_opening_thread_clears_only_user_badge(self):
        connection = ScriptedConnection([
            Result([{"role": "user", "active": 1}]),
            Result(rowcount=1),
        ])
        with patch.object(workflow, "initialize"), patch.object(
            workflow, "conn", ConnectionFactory([connection])
        ):
            workflow.mark_support_thread_seen(5, 7, 'user')

        self.assertIn('user_unread=0', connection.calls[1][0])
        self.assertEqual(connection.calls[1][1], (5, 7))

    def test_user_cannot_send_fourth_message_before_staff_reply(self):
        connection = ScriptedConnection([
            Result([{"role": "user", "active": 1}]),
            Result(rowcount=0),
            Result([{"id": 5, "user_id": 7, "status": "open"}]),
            Result([{"user_messages": 3, "staff_messages": 0}]),
        ])
        with patch.object(workflow, "initialize"), patch.object(
            workflow, "conn", ConnectionFactory([connection])
        ):
            with self.assertRaises(ValueError):
                workflow.reply_support_thread(5, 7, 'user', 'Tin thứ tư')
        self.assertEqual(len(connection.calls), 4)

    def test_user_can_continue_after_staff_has_replied(self):
        connection = ScriptedConnection([
            Result([{"role": "user", "active": 1}]),
            Result(rowcount=0),
            Result([{"id": 5, "user_id": 7, "status": "answered"}]),
            Result([{"user_messages": 9, "staff_messages": 1}]),
            Result(rowcount=1),
            Result(rowcount=1),
        ])
        with patch.object(workflow, "initialize"), patch.object(
            workflow, "conn", ConnectionFactory([connection])
        ):
            workflow.reply_support_thread(5, 7, 'user', 'Tiếp tục trao đổi')
        self.assertIn('INSERT INTO dbo.support_messages', connection.calls[4][0])

    def test_expert_can_close_support_thread(self):
        connection = ScriptedConnection([
            Result([{"role": "expert", "active": 1}]),
            Result(rowcount=1),
        ])
        with patch.object(workflow, "initialize"), patch.object(
            workflow, "conn", ConnectionFactory([connection])
        ):
            workflow.close_support_thread(5, 3)
        self.assertIn("status='closed'", connection.calls[1][0])

    def test_expiry_uses_latest_staff_message_and_thirty_minutes(self):
        connection = ScriptedConnection([Result(rowcount=2)])
        workflow._expire_support_threads(connection)
        self.assertIn('DATEADD(minute,-30,GETDATE())', connection.calls[0][0])
        self.assertIn('m.sender_id<>t.user_id', connection.calls[0][0])

    def test_unauthorized_reply_does_not_run_expiry_update(self):
        connection = ScriptedConnection([Result([{"role": "user", "active": 1}])])
        with patch.object(workflow, "initialize"), patch.object(
            workflow, "conn", ConnectionFactory([connection])
        ):
            with self.assertRaises(ValueError):
                workflow.reply_support_thread(5, 7, 'expert', 'Không hợp lệ')
        self.assertEqual(len(connection.calls), 1)


class NotificationTests(unittest.TestCase):
    def test_seen_update_targets_one_published_case_of_owner(self):
        connection = ScriptedConnection([
            Result([{'role': 'user', 'active': 1}]), Result(rowcount=1)
        ])
        with patch.object(workflow, 'initialize'), patch.object(
            workflow, 'conn', ConnectionFactory([connection])
        ):
            workflow.mark_result_seen(7, 12)
        self.assertIn("result_status='published'", connection.calls[1][0])
        self.assertEqual(connection.calls[1][1], (12, 7))


if __name__ == "__main__":
    unittest.main()
