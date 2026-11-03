"""Read-only operational checks for the existing PigSkinAI LocalDB."""

from pathlib import Path

from services.database import DATABASE, _connect

ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / 'case_images'

REQUIRED_COLUMNS = {
    'users': {'id', 'email', 'display_name', 'password_salt', 'password_hash',
              'role', 'active', 'created_at'},
    'login_events': {'id', 'user_id', 'login_at'},
    'inspections': {'id', 'filename', 'width', 'height', 'size_bytes', 'mode',
                    'created_at', 'case_id', 'image_path', 'review_status',
                    'user_id', 'result_status', 'result_seen'},
    'support_threads': {'id', 'user_id', 'subject', 'status', 'created_at',
                        'updated_at', 'user_unread', 'staff_unread'},
    'support_messages': {'id', 'thread_id', 'sender_id', 'body', 'created_at'},
}


def _scalar(cursor, query, parameters=()):
    row = cursor.execute(query, tuple(parameters)).fetchone()
    return int(row[0] or 0)


def _archived_image_health(paths):
    archive_root = IMAGE_DIR.resolve()
    checked = missing = outside_archive = 0
    for raw_path in paths:
        if not raw_path:
            continue
        checked += 1
        try:
            path = Path(raw_path).resolve()
            if archive_root not in path.parents:
                outside_archive += 1
            elif not path.is_file():
                missing += 1
        except (OSError, RuntimeError):
            missing += 1
    return {
        'checked': checked,
        'missing': missing,
        'outside_archive': outside_archive,
    }


def run_readonly_audit():
    """Return aggregate health data without changing rows or schema."""
    connection = _connect(DATABASE)
    try:
        cursor = connection.cursor()
        cursor.execute('SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED')
        table_rows = cursor.execute('''SELECT TABLE_NAME,COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='dbo' ''').fetchall()
        actual_columns = {}
        for table_name, column_name in table_rows:
            actual_columns.setdefault(table_name, set()).add(column_name)
        missing_columns = {
            table: sorted(columns - actual_columns.get(table, set()))
            for table, columns in REQUIRED_COLUMNS.items()
            if columns - actual_columns.get(table, set())
        }

        counts = {
            table: _scalar(cursor, f'SELECT COUNT(*) FROM dbo.[{table}]')
            for table in REQUIRED_COLUMNS
            if table in actual_columns
        }
        issues = {}
        if {'role', 'active', 'email'} <= actual_columns.get('users', set()):
            issues['invalid_user_roles'] = _scalar(cursor,
                "SELECT COUNT(*) FROM dbo.users WHERE role NOT IN ('user','expert','admin')")
            issues['active_admins'] = _scalar(cursor,
                "SELECT COUNT(*) FROM dbo.users WHERE role='admin' AND active=1")
            issues['duplicate_emails'] = _scalar(cursor, '''SELECT COUNT(*) FROM (
                SELECT email FROM dbo.users GROUP BY email HAVING COUNT(*)>1
            ) duplicates''')
        if ({'user_id', 'result_status', 'expert_id', 'approved_by'}
                <= actual_columns.get('inspections', set())
                and {'id'} <= actual_columns.get('users', set())):
            issues['orphan_case_owners'] = _scalar(cursor, '''SELECT COUNT(*)
                FROM dbo.inspections i LEFT JOIN dbo.users u ON u.id=i.user_id
                WHERE i.user_id IS NOT NULL AND u.id IS NULL''')
            issues['invalid_case_states'] = _scalar(cursor, '''SELECT COUNT(*)
                FROM dbo.inspections
                WHERE result_status NOT IN
                    ('not_started','returned','pending_approval','published')''')
            issues['invalid_published_results'] = _scalar(cursor, '''SELECT COUNT(*)
                FROM dbo.inspections
                WHERE result_status='published'
                  AND (expert_id IS NULL OR approved_by IS NULL OR expert_id=approved_by)''')
        if ({'user_id', 'status'} <= actual_columns.get('support_threads', set())
                and {'id'} <= actual_columns.get('users', set())):
            issues['orphan_support_owners'] = _scalar(cursor, '''SELECT COUNT(*)
                FROM dbo.support_threads t LEFT JOIN dbo.users u ON u.id=t.user_id
                WHERE u.id IS NULL''')
            issues['invalid_support_states'] = _scalar(cursor, '''SELECT COUNT(*)
                FROM dbo.support_threads WHERE status NOT IN ('open','answered','closed')''')
        if ({'thread_id', 'sender_id'} <= actual_columns.get('support_messages', set())
                and {'id'} <= actual_columns.get('support_threads', set())
                and {'id'} <= actual_columns.get('users', set())):
            issues['orphan_support_messages'] = _scalar(cursor, '''SELECT COUNT(*)
                FROM dbo.support_messages m
                LEFT JOIN dbo.support_threads t ON t.id=m.thread_id
                LEFT JOIN dbo.users u ON u.id=m.sender_id
                WHERE t.id IS NULL OR u.id IS NULL''')

        image_paths = []
        if 'inspections' in actual_columns and 'image_path' in actual_columns['inspections']:
            image_paths = [row[0] for row in cursor.execute(
                "SELECT image_path FROM dbo.inspections WHERE image_path<>''"
            ).fetchall()]
        return {
            'database': DATABASE,
            'missing_columns': missing_columns,
            'row_counts': counts,
            'integrity': issues,
            'archived_images': _archived_image_health(image_paths),
        }
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
