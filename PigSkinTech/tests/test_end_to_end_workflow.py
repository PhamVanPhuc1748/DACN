"""Isolated user-to-expert workflow smoke test; never opens LocalDB."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from tests import test_services as helpers


class EndToEndWorkflowTests(unittest.TestCase):
    def test_login_ai_case_review_publish_and_user_view(self):
        accounts = helpers.accounts
        store = helpers.store
        workflow = helpers.workflow
        user = helpers.public_user()
        user['password_hash'] = accounts._password_hash(
            'correct-pass', user['password_salt'])
        login_connection = helpers.ScriptedConnection([
            helpers.Result([user]), helpers.Result(),
        ])
        with patch.object(accounts, 'initialize'), patch.object(
                accounts, 'conn', helpers.ConnectionFactory([login_connection])):
            authenticated = accounts.authenticate('user@example.test', 'correct-pass')
        self.assertEqual(authenticated['id'], 7)

        ai_result = {
            'mode': 'ai', 'label': 'Healthy', 'confidence': 0.9,
            'scores': [{'label': 'Healthy', 'confidence': 0.9}],
            'model_info': 'mobilenet_v2 • run 20261103_125653',
        }
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            source = root_path / 'case.jpg'
            Image.new('RGB', (40, 30), (120, 90, 70)).save(source)
            info = store.inspect_image(source)
            authorization = helpers.ScriptedConnection([
                helpers.Result([{'role': 'user', 'active': 1}]),
            ])
            save_connection = helpers.ScriptedConnection([
                helpers.Result([{'role': 'user', 'active': 1}]),
                helpers.Result([{'id': 42}]), helpers.Result(),
            ])
            with patch.object(store, 'initialize'), patch.object(
                    store, 'IMAGE_DIR', root_path / 'archive'), patch.object(
                    store, 'conn', helpers.ConnectionFactory(
                        [authorization, save_connection])):
                case_id = store.save(info, ai_result, source_image=source, owner_id=7)
        self.assertEqual(case_id, 42)

        submit_connection = helpers.ScriptedConnection([
            helpers.Result([{'role': 'expert', 'active': 1}]),
            helpers.Result(rowcount=1),
        ])
        with patch.object(workflow, 'initialize'), patch.object(
                workflow, 'conn', helpers.ConnectionFactory([submit_connection])):
            workflow.submit_expert_result(
                case_id, 3, 'healthy', 'Không thấy dấu hiệu bệnh', 'Tiếp tục theo dõi')

        approval_connection = helpers.ScriptedConnection([
            helpers.Result([{'role': 'expert', 'active': 1}]),
            helpers.Result([{'id': case_id, 'expert_id': 3,
                             'result_status': 'pending_approval'}]),
            helpers.Result(rowcount=1),
        ])
        with patch.object(workflow, 'initialize'), patch.object(
                workflow, 'conn', helpers.ConnectionFactory([approval_connection])):
            workflow.review_expert_result(case_id, 4, True)

        published = {
            'id': case_id, 'result_status': 'published',
            'expert_result': 'Không thấy dấu hiệu bệnh',
            'expert_notes': 'Tiếp tục theo dõi',
        }
        history_connection = helpers.ScriptedConnection([
            helpers.Result([{'role': 'user', 'active': 1}]),
            helpers.Result([published]),
        ])
        with patch.object(store, 'initialize'), patch.object(
                store, 'conn', helpers.ConnectionFactory([history_connection])):
            rows = store.recent(owner_id=7, actor_id=7)
        self.assertEqual(rows[0]['expert_result'], 'Không thấy dấu hiệu bệnh')

        seen_connection = helpers.ScriptedConnection([
            helpers.Result([{'role': 'user', 'active': 1}]),
            helpers.Result(rowcount=1),
        ])
        with patch.object(workflow, 'initialize'), patch.object(
                workflow, 'conn', helpers.ConnectionFactory([seen_connection])):
            workflow.mark_result_seen(7, case_id)
        self.assertIn("result_status='published'", seen_connection.calls[1][0])


if __name__ == '__main__':
    unittest.main()
