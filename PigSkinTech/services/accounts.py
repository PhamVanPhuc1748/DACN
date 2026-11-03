import hashlib
import hmac
import logging
import secrets
import threading
from datetime import datetime
from services.database import conn
from services.otp import normalize_contact
PASSWORD_ITERATIONS = 310_000
ROLES = {'user', 'expert', 'admin'}
_initialized = False
_initialize_lock = threading.Lock()
_audit_logger = logging.getLogger('pigskin.audit')


def initialize():
    global _initialized
    if _initialized:
        return
    with _initialize_lock:
        if _initialized:
            return
        with conn() as connection:
            connection.execute('''IF OBJECT_ID('dbo.users', 'U') IS NULL
                EXEC sys.sp_executesql N'
                    CREATE TABLE dbo.users (
                        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                        email NVARCHAR(320) NULL,
                        phone NVARCHAR(20) NULL,
                        email_verified BIT NOT NULL DEFAULT 0,
                        phone_verified BIT NOT NULL DEFAULT 0,
                        display_name NVARCHAR(80) NOT NULL,
                        password_salt CHAR(32) NOT NULL,
                        password_hash CHAR(64) NOT NULL,
                        role NVARCHAR(20) NOT NULL
                            CHECK(role IN (''user'',''expert'',''admin'')),
                        active BIT NOT NULL DEFAULT 1,
                        created_at NVARCHAR(19) NOT NULL,
                        CHECK(email IS NOT NULL OR phone IS NOT NULL)
                    );
                    CREATE UNIQUE INDEX UX_users_email
                        ON dbo.users(email) WHERE email IS NOT NULL;
                    CREATE UNIQUE INDEX UX_users_phone
                        ON dbo.users(phone) WHERE phone IS NOT NULL;
                ' ''')
            connection.execute('''IF OBJECT_ID('dbo.login_events', 'U') IS NULL
                CREATE TABLE dbo.login_events (
                    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                    user_id INT NOT NULL,
                    login_at NVARCHAR(19) NOT NULL,
                    CONSTRAINT FK_login_events_users
                        FOREIGN KEY (user_id) REFERENCES dbo.users(id)
                )''')
        _initialized = True


def _password_hash(password, salt):
    return hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), bytes.fromhex(salt), PASSWORD_ITERATIONS
    ).hex()


def _public_user(row):
    return {
        'id': row['id'],
        'email': row['email'],
        'phone': row.get('phone'),
        'display_name': row['display_name'],
        'role': row['role'],
        'active': bool(row['active']),
        'created_at': row['created_at'],
    }


def account_count():
    initialize()
    with conn() as connection:
        return connection.execute('SELECT COUNT(*) AS count FROM dbo.users').fetchone()[0]


def otp_schema_ready():
    initialize()
    with conn() as connection:
        row = connection.execute('''SELECT CASE WHEN
            COL_LENGTH('dbo.users','phone') IS NOT NULL
            AND COL_LENGTH('dbo.users','email_verified') IS NOT NULL
            AND COL_LENGTH('dbo.users','phone_verified') IS NOT NULL
            AND OBJECT_ID('dbo.auth_otp_challenges','U') IS NOT NULL
            THEN 1 ELSE 0 END AS ready''').fetchone()
    return bool(row['ready'])


def current_account(user_id):
    """Read the current role and active state of a desktop session."""
    initialize()
    with conn() as connection:
        row = connection.execute(
            'SELECT id,email,display_name,role,active,created_at FROM dbo.users WHERE id=?',
            (user_id,)
        ).fetchone()
    return _public_user(row) if row is not None else None


def register(email, password, display_name, phone=None, verified_contact=None):
    initialize()
    if not isinstance(password, str) or not isinstance(display_name, str):
        raise ValueError('Thông tin đăng ký không hợp lệ.')
    if email is not None:
        email = normalize_contact(email, 'email')
    if phone is not None:
        phone = normalize_contact(phone, 'sms')
    if (email is None) == (phone is None):
        raise ValueError('Hãy đăng ký bằng email hoặc số điện thoại đã xác minh.')
    channel = 'email' if email is not None else 'sms'
    destination = email if email is not None else phone
    if (not isinstance(verified_contact, dict)
            or verified_contact.get('purpose') != 'registration'
            or verified_contact.get('channel') != channel
            or verified_contact.get('destination') != destination):
        raise ValueError('Hãy xác minh quyền sở hữu thông tin liên hệ trước khi đăng ký.')
    display_name = display_name.strip()
    if not 8 <= len(password) <= 128:
        raise ValueError('Mật khẩu cần dài từ 8 đến 128 ký tự.')
    if not display_name or len(display_name) > 80:
        raise ValueError('Tên hiển thị cần có từ 1 đến 80 ký tự.')

    salt = secrets.token_hex(16)
    password_hash = _password_hash(password, salt)
    with conn() as connection:
        role = 'user'
        try:
            row = connection.execute('''INSERT INTO dbo.users
                    (email, phone, email_verified, phone_verified, display_name,
                     password_salt, password_hash, role, created_at)
                    OUTPUT INSERTED.id, INSERTED.email, INSERTED.display_name,
                        INSERTED.phone, INSERTED.role, INSERTED.active,
                        INSERTED.created_at
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                    email, phone, int(channel == 'email'), int(channel == 'sms'),
                    display_name, salt, password_hash, role,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'))).fetchone()
        except Exception as exc:
            if '2601' in str(exc) or '2627' in str(exc):
                raise ValueError('Email này đã được đăng ký.') from exc
            raise
        connection.execute('''INSERT INTO dbo.login_events (user_id,login_at)
            VALUES (?,?)''', (
                row['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
        user = _public_user(row)
    _audit_logger.info('account_registered user_id=%s role=%s', row['id'], role)
    return user


def register_unverified_email(email, password, display_name):
    """Create a password-login account without claiming the email is verified."""
    initialize()
    if not isinstance(password, str) or not isinstance(display_name, str):
        raise ValueError('Thông tin đăng ký không hợp lệ.')
    email = normalize_contact(email, 'email')
    display_name = display_name.strip()
    if not 8 <= len(password) <= 128:
        raise ValueError('Mật khẩu cần dài từ 8 đến 128 ký tự.')
    if not display_name or len(display_name) > 80:
        raise ValueError('Tên hiển thị cần có từ 1 đến 80 ký tự.')

    salt = secrets.token_hex(16)
    password_hash = _password_hash(password, salt)
    with conn() as connection:
        role = 'user'
        try:
            row = connection.execute('''INSERT INTO dbo.users
                    (email, display_name, password_salt, password_hash,
                     role, created_at)
                    OUTPUT INSERTED.id, INSERTED.email, INSERTED.display_name,
                        INSERTED.role, INSERTED.active, INSERTED.created_at
                    VALUES (?, ?, ?, ?, ?, ?)''', (
                    email, display_name, salt, password_hash, role,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'))).fetchone()
        except Exception as exc:
            if '2601' in str(exc) or '2627' in str(exc):
                raise ValueError('Email này đã được đăng ký.') from exc
            raise
        connection.execute('''INSERT INTO dbo.login_events (user_id,login_at)
            VALUES (?,?)''', (
                row['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
        user = _public_user(row)
    _audit_logger.info('account_registered_unverified user_id=%s role=%s',
                       row['id'], role)
    return user


def contact_exists(contact, channel):
    initialize()
    destination = normalize_contact(contact, channel)
    column = 'email' if channel == 'email' else 'phone'
    with conn() as connection:
        row = connection.execute(
            f'SELECT TOP (1) id FROM dbo.users WHERE {column}=?',
            (destination,)
        ).fetchone()
    return row is not None


def find_verified_contact(contact, channel):
    initialize()
    destination = normalize_contact(contact, channel)
    column = 'email' if channel == 'email' else 'phone'
    verified_column = 'email_verified' if channel == 'email' else 'phone_verified'
    with conn() as connection:
        row = connection.execute(f'''SELECT id,email,phone,display_name,role,active,created_at
            FROM dbo.users WITH (UPDLOCK,HOLDLOCK)
            WHERE {column}=? AND {verified_column}=1 AND active=1''', (destination,)
        ).fetchone()
    return _public_user(row) if row is not None else None


def find_contact_for_password_reset(contact, channel):
    initialize()
    destination = normalize_contact(contact, channel)
    column = 'email' if channel == 'email' else 'phone'
    with conn() as connection:
        row = connection.execute(f'''SELECT id,email,phone,display_name,role,active,created_at
            FROM dbo.users WITH (UPDLOCK,HOLDLOCK)
            WHERE {column}=? AND active=1''', (destination,)
        ).fetchone()
    return _public_user(row) if row is not None else None


def authenticate(email, password):
    initialize()
    if not isinstance(email, str) or not isinstance(password, str) \
            or not password or len(password) > 128:
        return None
    with conn() as connection:
        row = connection.execute(
            'SELECT * FROM dbo.users WITH (UPDLOCK,HOLDLOCK) WHERE email=?',
            (email.strip().lower(),)
        ).fetchone()
        if row is None or not row['active']:
            return None
        candidate = _password_hash(password, row['password_salt'])
        if not hmac.compare_digest(candidate, row['password_hash']):
            return None
        connection.execute('''INSERT INTO dbo.login_events (user_id,login_at)
            VALUES (?,?)''', (
                row['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
        return _public_user(row)


def authenticate_otp(contact, channel):
    initialize()
    destination = normalize_contact(contact, channel)
    column = 'email' if channel == 'email' else 'phone'
    verified_column = 'email_verified' if channel == 'email' else 'phone_verified'
    with conn() as connection:
        row = connection.execute(f'''SELECT id,email,phone,display_name,role,active,created_at
            FROM dbo.users WITH (UPDLOCK,HOLDLOCK)
            WHERE {column}=? AND {verified_column}=1 AND active=1''', (destination,)
        ).fetchone()
        if row is None:
            return None
        connection.execute('''INSERT INTO dbo.login_events (user_id,login_at)
            VALUES (?,?)''', (
            row['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        return _public_user(row)


def reset_password(contact, channel, password, verified_contact):
    initialize()
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise ValueError('Mật khẩu cần dài từ 8 đến 128 ký tự.')
    destination = normalize_contact(contact, channel)
    if (not isinstance(verified_contact, dict)
            or verified_contact.get('purpose') != 'password_reset'
            or verified_contact.get('channel') != channel
            or verified_contact.get('destination') != destination):
        raise ValueError('Hãy xác minh quyền sở hữu thông tin liên hệ trước khi đặt lại mật khẩu.')
    column = 'email' if channel == 'email' else 'phone'
    verified_column = 'email_verified' if channel == 'email' else 'phone_verified'
    salt = secrets.token_hex(16)
    password_hash = _password_hash(password, salt)
    with conn() as connection:
        row = connection.execute(f'''SELECT id FROM dbo.users WITH (UPDLOCK,HOLDLOCK)
            WHERE {column}=? AND active=1''', (destination,)
        ).fetchone()
        if row is None:
            raise ValueError('Không thể đặt lại mật khẩu cho tài khoản này.')
        connection.execute(f'''UPDATE dbo.users
            SET password_salt=?, password_hash=?, {verified_column}=1 WHERE id=?''', (
            salt, password_hash, row['id']
        ))
    _audit_logger.info('account_password_reset user_id=%s', row['id'])


def _require_active_admin(connection, actor_id):
    actor = connection.execute(
        'SELECT role,active FROM dbo.users WITH (UPDLOCK,HOLDLOCK) WHERE id=?',
        (actor_id,)
    ).fetchone()
    if actor is None or actor['role'] != 'admin' or not actor['active']:
        raise ValueError('Chỉ quản trị viên đang hoạt động mới được quản lý tài khoản.')


def list_users(actor_id):
    initialize()
    with conn() as connection:
        _require_active_admin(connection, actor_id)
        rows = connection.execute(
            'SELECT * FROM dbo.users ORDER BY created_at, id'
        ).fetchall()
    return [_public_user(row) for row in rows]


def update_role(user_id, role, actor_id):
    initialize()
    if role not in ROLES:
        raise ValueError('Vai trò không hợp lệ.')
    with conn() as connection:
        _require_active_admin(connection, actor_id)
        target = connection.execute(
            'SELECT id, role FROM dbo.users WITH (UPDLOCK,HOLDLOCK) WHERE id=?',
            (user_id,)
        ).fetchone()
        if target is None:
            raise ValueError('Không tìm thấy tài khoản.')
        if user_id == actor_id and target['role'] != role:
            raise ValueError('Không thể tự thay đổi vai trò của tài khoản đang đăng nhập.')
        if target['role'] == 'admin' and role != 'admin':
            remaining = connection.execute(
                "SELECT COUNT(*) AS count FROM dbo.users WITH (TABLOCKX, HOLDLOCK) "
                "WHERE role='admin' AND active=1"
            ).fetchone()[0]
            if remaining <= 1:
                raise ValueError('Cần giữ lại ít nhất một quản trị viên đang hoạt động.')
        connection.execute('UPDATE dbo.users SET role=? WHERE id=?', (role, user_id))
        old_role = target['role']
    _audit_logger.info('account_role_changed actor_id=%s target_id=%s old=%s new=%s',
        actor_id, user_id, old_role, role)


def update_active(user_id, active, actor_id):
    initialize()
    if not isinstance(active, bool):
        raise ValueError('Trạng thái tài khoản không hợp lệ.')
    with conn() as connection:
        _require_active_admin(connection, actor_id)
        target = connection.execute(
            'SELECT id, role, active FROM dbo.users WITH (UPDLOCK,HOLDLOCK) WHERE id=?',
            (user_id,)
        ).fetchone()
        if target is None:
            raise ValueError('Không tìm thấy tài khoản.')
        if user_id == actor_id and not active:
            raise ValueError('Không thể khóa tài khoản đang đăng nhập.')
        if target['role'] == 'admin' and target['active'] and not active:
            remaining = connection.execute(
                "SELECT COUNT(*) AS count FROM dbo.users WITH (TABLOCKX, HOLDLOCK) "
                "WHERE role='admin' AND active=1"
            ).fetchone()[0]
            if remaining <= 1:
                raise ValueError('Cần giữ lại ít nhất một quản trị viên đang hoạt động.')
        connection.execute(
            'UPDATE dbo.users SET active=? WHERE id=?', (int(active), user_id)
        )
    _audit_logger.info('account_active_changed actor_id=%s target_id=%s active=%s',
        actor_id, user_id, active)
