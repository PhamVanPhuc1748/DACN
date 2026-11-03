from datetime import datetime
import logging
import threading

from services.database import conn
from services.store import initialize as initialize_store

RESULT_CATEGORIES = {'healthy', 'condition', 'inconclusive'}
SUPPORT_STATUSES = {'open', 'answered', 'closed'}
_initialized = False
_initialize_lock = threading.Lock()
_audit_logger = logging.getLogger('pigskin.audit')


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _require_active_role(connection, user_id, roles, message):
    actor = connection.execute(
        'SELECT role,active FROM dbo.users WHERE id=?', (user_id,)
    ).fetchone()
    if actor is None or actor['role'] not in roles or not actor['active']:
        raise ValueError(message)
    return actor['role']


def _expire_support_threads(connection):
    """Close a thread 30 minutes after its latest staff response."""
    result = connection.execute('''UPDATE t
        SET status='closed',updated_at=?,user_unread=0,staff_unread=0
        FROM dbo.support_threads t
        WHERE t.status<>'closed'
          AND (SELECT MAX(m.created_at) FROM dbo.support_messages m
               WHERE m.thread_id=t.id AND m.sender_id<>t.user_id)
              <= CONVERT(NVARCHAR(19),DATEADD(minute,-30,GETDATE()),120)''', (_now(),))
    if result.rowcount > 0:
        _audit_logger.info('support_threads_auto_closed count=%s', result.rowcount)


def initialize():
    global _initialized
    if _initialized:
        return
    with _initialize_lock:
        if _initialized:
            return
        initialize_store()
        with conn() as connection:
            connection.execute('''IF OBJECT_ID('dbo.support_threads', 'U') IS NULL
            CREATE TABLE dbo.support_threads (
                id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                user_id INT NOT NULL,
                subject NVARCHAR(200) NOT NULL,
                status NVARCHAR(20) NOT NULL DEFAULT 'open',
                created_at NVARCHAR(19) NOT NULL,
                updated_at NVARCHAR(19) NOT NULL
            )''')
            connection.execute('''IF OBJECT_ID('dbo.support_messages', 'U') IS NULL
            CREATE TABLE dbo.support_messages (
                id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                thread_id INT NOT NULL,
                sender_id INT NOT NULL,
                body NVARCHAR(MAX) NOT NULL,
                created_at NVARCHAR(19) NOT NULL,
                CONSTRAINT FK_support_messages_threads
                    FOREIGN KEY (thread_id) REFERENCES dbo.support_threads(id)
            )''')
            connection.execute("""IF COL_LENGTH('dbo.support_threads', 'user_unread') IS NULL BEGIN
            ALTER TABLE dbo.support_threads
            ADD user_unread BIT NOT NULL
                CONSTRAINT DF_support_threads_user_unread DEFAULT 0;
            EXEC('UPDATE dbo.support_threads SET user_unread=1 WHERE status=''answered''');
        END""")
            connection.execute("""IF COL_LENGTH('dbo.support_threads', 'staff_unread') IS NULL BEGIN
            ALTER TABLE dbo.support_threads
            ADD staff_unread BIT NOT NULL
                CONSTRAINT DF_support_threads_staff_unread DEFAULT 0;
            EXEC('UPDATE dbo.support_threads SET staff_unread=1 WHERE status=''open''');
        END""")
        _initialized = True


def submit_expert_result(case_id, expert_id, category, result, notes=''):
    initialize()
    if not isinstance(category, str) or not isinstance(result, str) or not isinstance(notes, str):
        raise ValueError('Dữ liệu kết quả chuyên gia không hợp lệ.')
    result = result.strip()
    notes = notes.strip()
    if category not in RESULT_CATEGORIES:
        raise ValueError('Hãy chọn phân loại kết quả hợp lệ.')
    if not result or len(result) > 8000:
        raise ValueError('Kết quả cần có từ 1 đến 8000 ký tự.')
    if len(notes) > 8000:
        raise ValueError('Ghi chú chuyên môn tối đa 8000 ký tự.')
    with conn() as connection:
        actor = connection.execute(
            "SELECT role,active FROM dbo.users WHERE id=?", (expert_id,)
        ).fetchone()
        if actor is None or actor['role'] != 'expert' or not actor['active']:
            raise ValueError('Chỉ tài khoản chuyên gia đang hoạt động mới được soạn kết quả.')
        row = connection.execute('''UPDATE dbo.inspections
            SET result_status='pending_approval',result_category=?,expert_result=?,
                expert_notes=?,expert_id=?,result_submitted_at=?,approved_by=NULL,
                approved_at=NULL,result_seen=0,review_note=''
            WHERE id=? AND review_status<>'closed'
                AND result_status IN ('not_started','returned')
        ''', (category, result, notes, expert_id, _now(), case_id))
        if row.rowcount != 1:
            raise ValueError(
                'Không thể gửi kết quả: hồ sơ không tồn tại, đã đóng, hoặc đang được '
                'chuyên gia khác duyệt.'
            )
        _audit_logger.info('expert_result_submitted case_id=%s expert_id=%s',
            case_id, expert_id)


def review_expert_result(case_id, reviewer_id, approve, feedback=''):
    initialize()
    if not isinstance(approve, bool) or not isinstance(feedback, str):
        raise ValueError('Quyết định duyệt không hợp lệ.')
    feedback = feedback.strip()
    if len(feedback) > 4000:
        raise ValueError('Ghi chú duyệt tối đa 4000 ký tự.')
    with conn() as connection:
        actor = connection.execute(
            "SELECT role,active FROM dbo.users WHERE id=?", (reviewer_id,)
        ).fetchone()
        if actor is None or actor['role'] != 'expert' or not actor['active']:
            raise ValueError('Chỉ tài khoản chuyên gia đang hoạt động mới được duyệt kết quả.')
        case = connection.execute('''SELECT id, expert_id, result_status
            FROM dbo.inspections WITH (UPDLOCK, HOLDLOCK) WHERE id=?''',
            (case_id,)).fetchone()
        if case is None or case['result_status'] != 'pending_approval':
            raise ValueError('Kết quả này không còn chờ duyệt.')
        if case['expert_id'] == reviewer_id:
            raise ValueError('Chuyên gia soạn kết quả không thể tự duyệt kết quả đó.')
        if approve:
            connection.execute('''UPDATE dbo.inspections
                SET result_status='published',review_status='reviewed',
                    approved_by=?,approved_at=?,
                    result_seen=0,review_note=''
                WHERE id=? AND result_status='pending_approval' ''',
                (reviewer_id, _now(), case_id))
        else:
            if not feedback:
                raise ValueError('Hãy ghi lý do trả kết quả để chuyên gia chỉnh sửa.')
            connection.execute('''UPDATE dbo.inspections
                SET result_status='returned',review_status='needs_review',
                    approved_by=?,approved_at=NULL,
                    review_note=?,result_seen=0
                WHERE id=? AND result_status='pending_approval' ''',
                (reviewer_id, feedback, case_id))
        _audit_logger.info('expert_result_reviewed case_id=%s reviewer_id=%s approved=%s',
            case_id, reviewer_id, approve)


def unseen_result_count(user_id):
    initialize()
    with conn() as connection:
        _require_active_role(connection, user_id, {'user'}, 'Tài khoản không có quyền xem thông báo.')
        return connection.execute('''SELECT COUNT(*) AS count
            FROM dbo.inspections
            WHERE user_id=? AND result_status='published' AND result_seen=0''',
            (user_id,)).fetchone()[0]


def mark_results_seen(user_id):
    initialize()
    with conn() as connection:
        _require_active_role(connection, user_id, {'user'}, 'Tài khoản không có quyền xem kết quả.')
        connection.execute('''UPDATE dbo.inspections SET result_seen=1
            WHERE user_id=? AND result_status='published' AND result_seen=0''',
            (user_id,))


def mark_result_seen(user_id, case_id):
    initialize()
    with conn() as connection:
        _require_active_role(connection, user_id, {'user'}, 'Tài khoản không có quyền xem kết quả.')
        connection.execute('''UPDATE dbo.inspections SET result_seen=1
            WHERE id=? AND user_id=? AND result_status='published' AND result_seen=0''',
            (case_id, user_id))


def create_support_thread(user_id, subject, body):
    initialize()
    if not isinstance(subject, str) or not isinstance(body, str):
        raise ValueError('Nội dung yêu cầu hỗ trợ không hợp lệ.')
    subject = subject.strip()
    body = body.strip()
    if not subject or len(subject) > 200:
        raise ValueError('Tiêu đề cần có từ 1 đến 200 ký tự.')
    if not body or len(body) > 8000:
        raise ValueError('Nội dung cần có từ 1 đến 8000 ký tự.')
    with conn() as connection:
        actor = connection.execute(
            "SELECT role,active FROM dbo.users WHERE id=?", (user_id,)
        ).fetchone()
        if actor is None or actor['role'] != 'user' or not actor['active']:
            raise ValueError('Chỉ người dùng đang hoạt động mới được mở yêu cầu hỗ trợ.')
        thread = connection.execute('''INSERT INTO dbo.support_threads
            (user_id,subject,status,created_at,updated_at,user_unread,staff_unread)
            OUTPUT INSERTED.id
            VALUES (?,?,'open',?,?,0,1)''', (user_id, subject, _now(), _now())).fetchone()
        connection.execute('''INSERT INTO dbo.support_messages
            (thread_id,sender_id,body,created_at) VALUES (?,?,?,?)''',
            (thread['id'], user_id, body, _now()))
        return thread['id']


def support_threads(actor_id, actor_role):
    initialize()
    with conn() as connection:
        role = _require_active_role(connection, actor_id, {'user', 'expert', 'admin'},
            'Tài khoản không có quyền xem yêu cầu hỗ trợ.')
        if role != actor_role:
            raise ValueError('Vai trò tài khoản đã thay đổi; hãy đăng nhập lại.')
        _expire_support_threads(connection)
        if role in ('admin', 'expert'):
            rows = connection.execute('''SELECT t.*,u.display_name AS user_name,
                    (SELECT TOP (1) body FROM dbo.support_messages m
                     WHERE m.thread_id=t.id ORDER BY m.id DESC) AS last_message,
                    (SELECT COUNT(*) FROM dbo.support_messages m
                     WHERE m.thread_id=t.id AND m.sender_id=t.user_id) AS user_message_count,
                    (SELECT COUNT(*) FROM dbo.support_messages m
                     WHERE m.thread_id=t.id AND m.sender_id<>t.user_id) AS staff_message_count
                FROM dbo.support_threads t JOIN dbo.users u ON u.id=t.user_id
                ORDER BY CASE t.status WHEN 'open' THEN 0 WHEN 'answered' THEN 1 ELSE 2 END,
                    t.updated_at DESC''').fetchall()
        else:
            rows = connection.execute('''SELECT t.*,
                    (SELECT TOP (1) body FROM dbo.support_messages m
                     WHERE m.thread_id=t.id ORDER BY m.id DESC) AS last_message,
                    (SELECT COUNT(*) FROM dbo.support_messages m
                     WHERE m.thread_id=t.id AND m.sender_id=t.user_id) AS user_message_count,
                    (SELECT COUNT(*) FROM dbo.support_messages m
                     WHERE m.thread_id=t.id AND m.sender_id<>t.user_id) AS staff_message_count
                FROM dbo.support_threads t WHERE t.user_id=?
                ORDER BY t.updated_at DESC''', (actor_id,)).fetchall()
    return [dict(row) for row in rows]


def support_messages(thread_id, actor_id, actor_role):
    initialize()
    with conn() as connection:
        role = _require_active_role(connection, actor_id, {'user', 'expert', 'admin'},
            'Tài khoản không có quyền xem hội thoại hỗ trợ.')
        if role != actor_role:
            raise ValueError('Vai trò tài khoản đã thay đổi; hãy đăng nhập lại.')
        if role == 'user':
            thread = connection.execute(
                'SELECT id FROM dbo.support_threads WHERE id=? AND user_id=?',
                (thread_id, actor_id)
            ).fetchone()
            if thread is None:
                raise ValueError('Không tìm thấy hội thoại hỗ trợ.')
        rows = connection.execute('''SELECT m.*,u.display_name AS sender_name,u.role AS sender_role
            FROM dbo.support_messages m JOIN dbo.users u ON u.id=m.sender_id
            WHERE m.thread_id=? ORDER BY m.id''', (thread_id,)).fetchall()
    return [dict(row) for row in rows]


def support_unread_count(actor_id, actor_role):
    """Count support conversations awaiting this side's attention."""
    initialize()
    with conn() as connection:
        role = _require_active_role(connection, actor_id, {'user', 'expert', 'admin'},
            'Tài khoản không có quyền xem thông báo hỗ trợ.')
        if role != actor_role:
            raise ValueError('Vai trò tài khoản đã thay đổi; hãy đăng nhập lại.')
        _expire_support_threads(connection)
        if role == 'user':
            row = connection.execute('''SELECT COUNT(*) AS count
                FROM dbo.support_threads
                WHERE user_id=? AND user_unread=1 AND status<>'closed' ''',
                (actor_id,)).fetchone()
        else:
            row = connection.execute('''SELECT COUNT(*) AS count
                FROM dbo.support_threads
                WHERE status='open' ''').fetchone()
    return row['count'] or 0


def mark_support_thread_seen(thread_id, actor_id, actor_role):
    """Clear the unread flag only for the side currently viewing the thread."""
    initialize()
    with conn() as connection:
        role = _require_active_role(connection, actor_id, {'user', 'expert', 'admin'},
            'Tài khoản không có quyền xem hội thoại hỗ trợ.')
        if role != actor_role:
            raise ValueError('Vai trò tài khoản đã thay đổi; hãy đăng nhập lại.')
        if role == 'user':
            result = connection.execute('''UPDATE dbo.support_threads SET user_unread=0
                WHERE id=? AND user_id=?''', (thread_id, actor_id))
        else:
            result = connection.execute('''UPDATE dbo.support_threads SET staff_unread=0
                WHERE id=?''', (thread_id,))
        if result.rowcount != 1:
            raise ValueError('Không tìm thấy hội thoại hỗ trợ.')


def reply_support_thread(thread_id, sender_id, sender_role, body):
    initialize()
    if not isinstance(sender_role, str) or not isinstance(body, str):
        raise ValueError('Nội dung trả lời hỗ trợ không hợp lệ.')
    body = body.strip()
    if not body or len(body) > 8000:
        raise ValueError('Nội dung trả lời cần có từ 1 đến 8000 ký tự.')
    with conn() as connection:
        actor = connection.execute(
            "SELECT role,active FROM dbo.users WHERE id=?", (sender_id,)
        ).fetchone()
        if actor is None or actor['role'] != sender_role or not actor['active']:
            raise ValueError('Tài khoản không có quyền trả lời hỗ trợ.')
        if sender_role not in ('user', 'expert', 'admin'):
            raise ValueError('Vai trò không được hỗ trợ.')
        _expire_support_threads(connection)
        thread = connection.execute('''SELECT id,user_id,status
            FROM dbo.support_threads WITH (UPDLOCK,HOLDLOCK) WHERE id=?''', (thread_id,)).fetchone()
        if thread is None:
            raise ValueError('Không tìm thấy hội thoại hỗ trợ.')
        if sender_role == 'user' and thread['user_id'] != sender_id:
            raise ValueError('Bạn không có quyền trả lời hội thoại này.')
        if thread['status'] == 'closed':
            raise ValueError('Hội thoại đã đóng; hãy tạo yêu cầu hỗ trợ mới.')
        if sender_role == 'user':
            counts = connection.execute('''SELECT
                    SUM(CASE WHEN sender_id=? THEN 1 ELSE 0 END) AS user_messages,
                    SUM(CASE WHEN sender_id<>? THEN 1 ELSE 0 END) AS staff_messages
                FROM dbo.support_messages WHERE thread_id=?''',
                (thread['user_id'], thread['user_id'], thread_id)).fetchone()
            user_messages = counts['user_messages'] or 0
            staff_messages = counts['staff_messages'] or 0
            if staff_messages == 0 and user_messages >= 3:
                raise ValueError(
                    'Bạn đã gửi đủ 3 tin. Hãy chờ chuyên gia trả lời trước khi nhắn tiếp.'
                )
        connection.execute('''INSERT INTO dbo.support_messages
            (thread_id,sender_id,body,created_at) VALUES (?,?,?,?)''',
            (thread_id, sender_id, body, _now()))
        status = 'open' if sender_role == 'user' else 'answered'
        user_unread = 0 if sender_role == 'user' else 1
        staff_unread = 1 if sender_role == 'user' else 0
        connection.execute('''UPDATE dbo.support_threads
            SET status=?,updated_at=?,user_unread=?,staff_unread=? WHERE id=?''',
            (status, _now(), user_unread, staff_unread, thread_id))
        _audit_logger.info('support_reply thread_id=%s sender_id=%s sender_role=%s',
            thread_id, sender_id, sender_role)


def close_support_thread(thread_id, actor_id):
    initialize()
    with conn() as connection:
        actor = connection.execute(
            "SELECT role,active FROM dbo.users WHERE id=?", (actor_id,)
        ).fetchone()
        if actor is None or actor['role'] not in ('expert', 'admin') or not actor['active']:
            raise ValueError(
                'Chỉ chuyên gia hoặc quản trị viên đang hoạt động mới được đóng yêu cầu.'
            )
        result = connection.execute('''UPDATE dbo.support_threads
            SET status='closed',updated_at=?,user_unread=0,staff_unread=0
            WHERE id=?''', (_now(), thread_id))
        if result.rowcount != 1:
            raise ValueError('Không tìm thấy yêu cầu hỗ trợ.')
        _audit_logger.info('support_thread_closed thread_id=%s actor_id=%s role=%s',
            thread_id, actor_id, actor['role'])


def admin_metrics(admin_id):
    initialize()
    with conn() as connection:
        _require_active_role(connection, admin_id, {'admin'},
            'Chỉ quản trị viên đang hoạt động mới được xem số liệu quản trị.')
        accounts = connection.execute('''SELECT
            COUNT(*) AS total_accounts,
            SUM(CASE WHEN active=1 THEN 1 ELSE 0 END) AS active_accounts
            FROM dbo.users''').fetchone()
        cases = connection.execute('''SELECT
            COUNT(*) AS total_cases,
            SUM(CASE WHEN result_status IN ('not_started','returned') THEN 1 ELSE 0 END)
                AS awaiting_expert,
            SUM(CASE WHEN result_status='pending_approval' THEN 1 ELSE 0 END)
                AS awaiting_second_review,
            SUM(CASE WHEN result_status='published' THEN 1 ELSE 0 END) AS published,
            SUM(CASE WHEN result_status='published' AND result_category='condition'
                THEN 1 ELSE 0 END) AS disease_cases,
            SUM(CASE WHEN result_status='published' AND result_category IN ('condition','healthy')
                THEN 1 ELSE 0 END) AS classified
            FROM dbo.inspections''').fetchone()
        logins = connection.execute('''SELECT COUNT(*) AS count
            FROM dbo.login_events
            WHERE login_at >= CONVERT(NVARCHAR(10), DATEADD(day,-30,GETDATE()), 23)''').fetchone()
        months = connection.execute('''SELECT LEFT(created_at,7) AS month,
            COUNT(*) AS count FROM dbo.inspections
            WHERE created_at >= CONVERT(NVARCHAR(10), DATEADD(month,-5,GETDATE()), 23)
            GROUP BY LEFT(created_at,7) ORDER BY month''').fetchall()
        logins_by_month = connection.execute('''SELECT LEFT(login_at,7) AS month,
            COUNT(*) AS count FROM dbo.login_events
            WHERE login_at >= CONVERT(NVARCHAR(10), DATEADD(month,-5,GETDATE()), 23)
            GROUP BY LEFT(login_at,7) ORDER BY month''').fetchall()
    return {
        'total_accounts': accounts['total_accounts'] or 0,
        'active_accounts': accounts['active_accounts'] or 0,
        'total_cases': cases['total_cases'] or 0,
        'awaiting_expert': cases['awaiting_expert'] or 0,
        'awaiting_second_review': cases['awaiting_second_review'] or 0,
        'published': cases['published'] or 0,
        'disease_cases': cases['disease_cases'] or 0,
        'classified': cases['classified'] or 0,
        'disease_percent': (
            100 * cases['disease_cases'] / cases['classified']
            if cases['classified'] else 0
        ),
        'logins_30d': logins['count'] or 0,
        'cases_by_month': [dict(row) for row in months],
        'logins_by_month': [dict(row) for row in logins_by_month],
    }
