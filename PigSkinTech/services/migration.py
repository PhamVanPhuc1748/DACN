import os
import sqlite3
from pathlib import Path

from services.accounts import initialize as initialize_accounts
from services.database import conn
from services.store import initialize as initialize_store

ROOT = Path(__file__).resolve().parents[1]
SQLITE_DATABASE = Path(os.environ.get(
    'PIGSKIN_SQLITE_PATH', str(ROOT / 'pigskin_history.db')
))

USER_COLUMNS = (
    'id', 'email', 'display_name', 'password_salt', 'password_hash',
    'role', 'active', 'created_at'
)
INSPECTION_COLUMNS = (
    'id', 'filename', 'width', 'height', 'size_bytes', 'mode',
    'predicted_class', 'confidence', 'created_at', 'case_id', 'animal_id',
    'farm_name', 'body_site', 'symptoms', 'onset_date', 'entered_at',
    'image_path', 'review_status', 'review_note', 'scores_json', 'model_info',
    'user_id'
)
USER_DEFAULTS = {
    'role': 'user',
    'active': 1,
}
INSPECTION_DEFAULTS = {
    'filename': '',
    'width': 0,
    'height': 0,
    'size_bytes': 0,
    'mode': 'unavailable',
    'created_at': '',
    'case_id': '',
    'animal_id': '',
    'farm_name': '',
    'body_site': '',
    'symptoms': '',
    'onset_date': '',
    'entered_at': '',
    'image_path': '',
    'review_status': 'needs_review',
    'review_note': '',
    'scores_json': '[]',
    'model_info': '',
}


def migrate_sqlite_database(source_path=SQLITE_DATABASE):
    source_path = Path(source_path)
    if not source_path.is_file():
        raise FileNotFoundError(f'Không tìm thấy SQLite database: {source_path}')

    initialize_accounts()
    initialize_store()

    source = sqlite3.connect(source_path)
    source.row_factory = sqlite3.Row
    try:
        tables = {
            row['name'] for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        source_users = (
            [dict(row) for row in source.execute('SELECT * FROM users')]
            if 'users' in tables else []
        )
        source_inspections = (
            [dict(row) for row in source.execute('SELECT * FROM inspections')]
            if 'inspections' in tables else []
        )
    finally:
        source.close()

    with conn() as target:
        existing_users = target.execute(
            'SELECT COUNT(*) AS count FROM dbo.users'
        ).fetchone()[0]
        existing_inspections = target.execute(
            'SELECT COUNT(*) AS count FROM dbo.inspections'
        ).fetchone()[0]
        if existing_users or existing_inspections:
            raise RuntimeError(
                'Migration dừng để tránh ghi đè hoặc nhân đôi dữ liệu: '
                f'SQL Server hiện có {existing_users} tài khoản và '
                f'{existing_inspections} hồ sơ.'
            )

        user_ids = {row['id'] for row in source_users}
        for table, columns, rows, defaults in (
            ('users', USER_COLUMNS, source_users, USER_DEFAULTS),
            ('inspections', INSPECTION_COLUMNS, source_inspections, INSPECTION_DEFAULTS),
        ):
            if not rows:
                continue
            column_list = ', '.join(f'[{column}]' for column in columns)
            placeholders = ', '.join('?' for _ in columns)
            target.execute(f'SET IDENTITY_INSERT dbo.{table} ON')
            try:
                for source_row in rows:
                    values = [
                        source_row.get(column, defaults.get(column))
                        for column in columns
                    ]
                    if table == 'inspections':
                        values[-1] = values[-1] if values[-1] in user_ids else None
                        if not values[9]:
                            values[9] = f'PS-{values[0]:06d}'
                    target.execute(
                        f'INSERT INTO dbo.{table} ({column_list}) VALUES ({placeholders})',
                        values
                    )
            finally:
                target.execute(f'SET IDENTITY_INSERT dbo.{table} OFF')

    return {
        'users': len(source_users),
        'inspections': len(source_inspections),
        'source': str(source_path),
    }
