import json
import shutil
import threading
from pathlib import Path
from datetime import datetime
from uuid import uuid4
from services.database import conn
from services.inference import inspect_image

IMAGE_DIR = Path(__file__).resolve().parents[1] / 'case_images'
_initialized = False
_initialize_lock = threading.Lock()


def _require_actor(connection, actor_id, roles):
    if actor_id is None:
        raise ValueError('Phiên đăng nhập không hợp lệ.')
    actor = connection.execute(
        'SELECT role,active FROM dbo.users WHERE id=?', (actor_id,)
    ).fetchone()
    if actor is None or not actor['active'] or actor['role'] not in roles:
        raise ValueError('Tài khoản đã bị khóa hoặc quyền truy cập đã thay đổi. Hãy đăng nhập lại.')
    return actor['role']


CASE_LIMITS = {'animal_id': 255, 'farm_name': 255, 'body_site': 255,
               'symptoms': 8000, 'onset_date': 40, 'entered_at': 40}


def _validate_case(case):
    values={}
    for key, limit in CASE_LIMITS.items():
        value=case.get(key, '')
        if not isinstance(value, str) or len(value.strip()) > limit:
            raise ValueError(f'Trường {key} không hợp lệ hoặc vượt quá {limit} ký tự.')
        values[key]=value.strip()
    if values['onset_date']:
        try:
            datetime.strptime(values['onset_date'], '%Y-%m-%d')
        except ValueError as exc:
            raise ValueError('Ngày khởi phát phải theo định dạng YYYY-MM-DD và là ngày hợp lệ.') from exc
    return values

CASE_COLUMNS = {
    'case_id': 'NVARCHAR(80)',
    'animal_id': 'NVARCHAR(255)',
    'farm_name': 'NVARCHAR(255)',
    'body_site': 'NVARCHAR(255)',
    'symptoms': 'NVARCHAR(MAX)',
    'onset_date': 'NVARCHAR(40)',
    'entered_at': 'NVARCHAR(40)',
    'image_path': 'NVARCHAR(2048)',
    'review_status': 'NVARCHAR(40)',
    'review_note': 'NVARCHAR(MAX)',
    'scores_json': 'NVARCHAR(MAX)',
    'model_info': 'NVARCHAR(MAX)',
    'user_id': 'INT',
    'result_status': "NVARCHAR(30) NOT NULL CONSTRAINT DF_inspections_result_status DEFAULT 'not_started'",
    'result_category': 'NVARCHAR(30)',
    'expert_result': 'NVARCHAR(MAX)',
    'expert_notes': 'NVARCHAR(MAX)',
    'expert_id': 'INT',
    'result_submitted_at': 'NVARCHAR(19)',
    'approved_by': 'INT',
    'approved_at': 'NVARCHAR(19)',
    'result_seen': 'BIT NOT NULL CONSTRAINT DF_inspections_result_seen DEFAULT 0',
}


def initialize():
    global _initialized
    if _initialized:
        return
    with _initialize_lock:
        if _initialized:
            return
        with conn() as c:
            c.execute('''IF OBJECT_ID('dbo.inspections', 'U') IS NULL
                CREATE TABLE dbo.inspections (
                id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                filename NVARCHAR(260) NOT NULL,
                width INT NOT NULL,
                height INT NOT NULL,
                size_bytes BIGINT NOT NULL,
                mode NVARCHAR(30) NOT NULL,
                predicted_class NVARCHAR(255) NULL,
                confidence FLOAT NULL,
                created_at NVARCHAR(19) NOT NULL,
                case_id NVARCHAR(80) NOT NULL DEFAULT '',
                animal_id NVARCHAR(255) NOT NULL DEFAULT '',
                farm_name NVARCHAR(255) NOT NULL DEFAULT '',
                body_site NVARCHAR(255) NOT NULL DEFAULT '',
                symptoms NVARCHAR(MAX) NOT NULL DEFAULT '',
                onset_date NVARCHAR(40) NOT NULL DEFAULT '',
                entered_at NVARCHAR(40) NOT NULL DEFAULT '',
                image_path NVARCHAR(2048) NOT NULL DEFAULT '',
                review_status NVARCHAR(40) NOT NULL DEFAULT 'needs_review',
                review_note NVARCHAR(MAX) NOT NULL DEFAULT '',
                scores_json NVARCHAR(MAX) NOT NULL DEFAULT '[]',
                model_info NVARCHAR(MAX) NOT NULL DEFAULT '',
                user_id INT NULL
                )''')
            for name, definition in CASE_COLUMNS.items():
                exists = c.execute(
                    'SELECT COL_LENGTH(?, ?) AS column_length',
                    ('dbo.inspections', name)
                ).fetchone()['column_length']
                if exists is None:
                    nullable = '' if 'NOT NULL' in definition else ' NULL'
                    c.execute(f'ALTER TABLE dbo.inspections ADD [{name}] {definition}{nullable}')
        _initialized = True

def save(info, result, case=None, source_image=None, owner_id=None):
    initialize()
    case = _validate_case(case or {})
    with conn() as c:
        _require_actor(c, owner_id, {'user', 'expert'})
    case_id = case.get('case_id','').strip()
    archived_path=''
    if source_image:
        source=Path(source_image)
        inspect_image(source)
        if not source.is_file() or source.suffix.lower() not in ('.jpg','.jpeg','.png','.webp'):
            raise ValueError('Không thể lưu ảnh hồ sơ không hợp lệ.')
        IMAGE_DIR.mkdir(parents=True,exist_ok=True)
        destination=IMAGE_DIR / f'{uuid4().hex}{source.suffix.lower()}'
        shutil.copy2(source,destination)
        archived_path=str(destination)
    try:
        with conn() as c:
            _require_actor(c, owner_id, {'user', 'expert'})
            cur = c.execute('''INSERT INTO dbo.inspections
        (filename,width,height,size_bytes,mode,predicted_class,confidence,created_at,image_path,
         case_id,animal_id,farm_name,body_site,symptoms,onset_date,entered_at,review_status,
         review_note,scores_json,model_info,user_id)
        OUTPUT INSERTED.id
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            info['name'],info['width'],info['height'],info['bytes'],result['mode'],
            result.get('label'),result.get('confidence'),datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            archived_path,
            case_id,case.get('animal_id','').strip(),case.get('farm_name','').strip(),
            case.get('body_site','').strip(),case.get('symptoms','').strip(),
            case.get('onset_date','').strip(),case.get('entered_at','').strip(),
            case.get('review_status','needs_review'),
            case.get('review_note','').strip(),
            json.dumps(result.get('scores',[]),ensure_ascii=False),
            result.get('model_info',''),owner_id))
            record_id = cur.fetchone()['id']
            if not case_id:
                case_id = f'PS-{record_id:06d}'
                c.execute('UPDATE dbo.inspections SET case_id=? WHERE id=?',(case_id,record_id))
            return record_id
    except Exception:
        if archived_path:
            Path(archived_path).unlink(missing_ok=True)
        raise

def recent(keyword='', owner_id=None, actor_id=None, limit=300, offset=0, status=None):
    initialize()
    if not isinstance(keyword, str):
        raise ValueError('Từ khóa tìm kiếm không hợp lệ.')
    if (isinstance(limit, bool) or not isinstance(limit, int)
            or isinstance(offset, bool) or not isinstance(offset, int)
            or not 1 <= limit <= 300 or offset < 0):
        raise ValueError('Tham số phân trang không hợp lệ.')
    if status is not None and status not in {'not_started','returned','pending_approval','published'}:
        raise ValueError('Trạng thái hồ sơ không hợp lệ.')
    with conn() as c:
        role = _require_actor(c, actor_id, {'user', 'expert', 'admin'})
        if role == 'user' and owner_id != actor_id:
            raise ValueError('Bạn chỉ có thể xem hồ sơ của mình.')
        if role != 'user' and owner_id is not None:
            raise ValueError('Bộ lọc chủ sở hữu không hợp lệ cho vai trò này.')
        pattern = '%'+keyword+'%'
        where = '(filename LIKE ? OR case_id LIKE ? OR animal_id LIKE ? OR farm_name LIKE ?)'
        parameters = [pattern] * 4
        if owner_id is not None:
            where = 'user_id=? AND ' + where
            parameters.insert(0, owner_id)
        if status is not None:
            where += ' AND result_status=?'
            parameters.append(status)
        rows = c.execute(f'''SELECT * FROM dbo.inspections WHERE {where}
            ORDER BY id DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY''',
            (*parameters, offset, limit)).fetchall()
        result = [dict(r) for r in rows]
        for item in result:
            item['result_status'] = item.get('result_status') or 'not_started'
            item['result_seen'] = bool(item.get('result_seen'))
            if role == 'user' and item['result_status'] != 'published':
                for key in ('result_category','expert_result','expert_notes',
                            'expert_id','result_submitted_at','approved_by','approved_at'):
                    item[key] = None
        return result


def count_cases(keyword='', owner_id=None, actor_id=None, status=None):
    initialize()
    if not isinstance(keyword, str):
        raise ValueError('Từ khóa tìm kiếm không hợp lệ.')
    if status is not None and status not in {'not_started','returned','pending_approval','published'}:
        raise ValueError('Trạng thái hồ sơ không hợp lệ.')
    with conn() as c:
        role = _require_actor(c, actor_id, {'user', 'expert', 'admin'})
        if role == 'user' and owner_id != actor_id:
            raise ValueError('Bạn chỉ có thể xem hồ sơ của mình.')
        if role != 'user' and owner_id is not None:
            raise ValueError('Bộ lọc chủ sở hữu không hợp lệ cho vai trò này.')
        pattern = '%'+keyword+'%'
        where = '(filename LIKE ? OR case_id LIKE ? OR animal_id LIKE ? OR farm_name LIKE ?)'
        parameters = [pattern] * 4
        if owner_id is not None:
            where = 'user_id=? AND ' + where
            parameters.insert(0, owner_id)
        if status is not None:
            where += ' AND result_status=?'
            parameters.append(status)
        return c.execute(f'SELECT COUNT(*) AS count FROM dbo.inspections WHERE {where}',
                         parameters).fetchone()[0]


def case_summary(actor_id):
    """Exact dashboard counts, independent of history pagination."""
    initialize()
    with conn() as c:
        role = _require_actor(c, actor_id, {'user', 'expert'})
        where = 'WHERE user_id=?' if role == 'user' else ''
        parameters = (actor_id, actor_id) if role == 'user' else (actor_id,)
        row = c.execute(f'''SELECT COUNT(*) AS total,
            SUM(CASE WHEN result_status IN ('not_started','returned') THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN result_status='pending_approval' THEN 1 ELSE 0 END) AS second_review,
            SUM(CASE WHEN result_status='published' THEN 1 ELSE 0 END) AS published,
            SUM(CASE WHEN mode='ai' AND predicted_class IS NOT NULL THEN 1 ELSE 0 END) AS inferred,
            SUM(CASE WHEN expert_id=? THEN 1 ELSE 0 END) AS authored
            FROM dbo.inspections {where}''', parameters).fetchone()
    return {key: row[key] or 0 for key in
        ('total','pending','second_review','published','inferred','authored')}


def authorized_image_path(record_id, actor_id):
    """Resolve an archived image only after checking the current account."""
    initialize()
    with conn() as c:
        role = _require_actor(c, actor_id, {'user', 'expert', 'admin'})
        if role == 'user':
            row = c.execute(
                'SELECT image_path FROM dbo.inspections WHERE id=? AND user_id=?',
                (record_id, actor_id)
            ).fetchone()
        else:
            row = c.execute(
                'SELECT image_path FROM dbo.inspections WHERE id=?', (record_id,)
            ).fetchone()
    if row is None or not row['image_path']:
        raise ValueError('Không tìm thấy ảnh hoặc bạn không có quyền xem hồ sơ.')
    path = Path(row['image_path']).resolve()
    if IMAGE_DIR.resolve() not in path.parents or not path.is_file():
        raise ValueError('Không tìm thấy ảnh đã lưu trong hồ sơ.')
    return path

def delete(record_id, owner_id):
    initialize()
    if owner_id is None:
        raise ValueError('Hãy đăng nhập bằng tài khoản người dùng để xóa hồ sơ.')
    with conn() as c:
        actor=c.execute('SELECT role,active FROM dbo.users WHERE id=?',(owner_id,)).fetchone()
        if actor is None or actor['role']!='user' or not actor['active']:
            raise ValueError('Chỉ người dùng đang hoạt động mới được xóa hồ sơ của mình.')
        row=c.execute('''SELECT image_path FROM dbo.inspections WITH (UPDLOCK,HOLDLOCK)
            WHERE id=? AND user_id=? AND result_status='not_started'
                AND expert_id IS NULL AND approved_by IS NULL
                AND review_status='needs_review' ''',(record_id,owner_id)).fetchone()
        if row is None:
            raise ValueError(
                'Chỉ có thể xóa hồ sơ của bạn chưa được chuyên gia tiếp nhận hoặc xử lý.'
            )
        result=c.execute('''DELETE FROM dbo.inspections
            WHERE id=? AND user_id=? AND result_status='not_started'
                AND expert_id IS NULL AND approved_by IS NULL
                AND review_status='needs_review' ''',(record_id,owner_id))
        if result.rowcount != 1:
            raise ValueError('Hồ sơ vừa thay đổi trạng thái; hãy tải lại lịch sử rồi thử lại.')
    if row and row['image_path']:
        image_file=Path(row['image_path']).resolve()
        archive_root=IMAGE_DIR.resolve()
        if archive_root in image_file.parents:
            image_file.unlink(missing_ok=True)

def update_review(record_id, status, note='', actor_id=None):
    initialize()
    allowed = {'needs_review','reviewed','lab_requested','closed'}
    if status not in allowed or not isinstance(note, str) or len(note.strip()) > 4000:
        raise ValueError('Trạng thái rà soát không hợp lệ.')
    with conn() as c:
        _require_actor(c, actor_id, {'expert'})
        result=c.execute('UPDATE dbo.inspections SET review_status=?,review_note=? WHERE id=?',
                         (status,note.strip(),record_id))
        if result.rowcount != 1:
            raise ValueError('Không tìm thấy hồ sơ cần cập nhật.')

def update_case(record_id, case, owner_id=None):
    initialize()
    if owner_id is None:
        raise ValueError('Cần tài khoản người dùng để sửa hồ sơ.')
    case = _validate_case(case)
    with conn() as c:
        _require_actor(c, owner_id, {'user'})
        ownership_clause = ' AND user_id=? AND result_status IN (\'not_started\',\'returned\')' \
            if owner_id is not None else ''
        review_reset = (
            ",review_status='needs_review',review_note='',result_status='not_started',"
            "result_category=NULL,expert_result=NULL,expert_notes=NULL,expert_id=NULL,"
            "result_submitted_at=NULL,approved_by=NULL,approved_at=NULL,result_seen=0"
        ) if owner_id is not None else ''
        parameters = [
            case.get('animal_id','').strip(),case.get('farm_name','').strip(),
            case.get('body_site','').strip(),case.get('symptoms','').strip(),
            case.get('onset_date','').strip(),case.get('entered_at','').strip(),record_id]
        if owner_id is not None:
            parameters.append(owner_id)
        cur = c.execute(f'''UPDATE dbo.inspections SET animal_id=?,farm_name=?,body_site=?,
            symptoms=?,onset_date=?,entered_at=?{review_reset} WHERE id=?{ownership_clause}''',
            parameters)
        return cur.rowcount > 0
