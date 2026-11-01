import sqlite3
import json
import shutil
from pathlib import Path
from datetime import datetime
from uuid import uuid4
DB = Path(__file__).resolve().parents[1] / 'pigskin_history.db'
IMAGE_DIR = Path(__file__).resolve().parents[1] / 'case_images'

CASE_COLUMNS = {
    'case_id': "TEXT NOT NULL DEFAULT ''",
    'animal_id': "TEXT NOT NULL DEFAULT ''",
    'farm_name': "TEXT NOT NULL DEFAULT ''",
    'body_site': "TEXT NOT NULL DEFAULT ''",
    'symptoms': "TEXT NOT NULL DEFAULT ''",
    'onset_date': "TEXT NOT NULL DEFAULT ''",
    'entered_at': "TEXT NOT NULL DEFAULT ''",
    'image_path': "TEXT NOT NULL DEFAULT ''",
    'review_status': "TEXT NOT NULL DEFAULT 'needs_review'",
    'review_note': "TEXT NOT NULL DEFAULT ''",
    'scores_json': "TEXT NOT NULL DEFAULT '[]'",
    'model_info': "TEXT NOT NULL DEFAULT ''",
}

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def initialize():
    with conn() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT NOT NULL,
            width INTEGER NOT NULL, height INTEGER NOT NULL,
            size_bytes INTEGER NOT NULL, mode TEXT NOT NULL,
            predicted_class TEXT, confidence REAL, created_at TEXT NOT NULL)''')
        existing = {row['name'] for row in c.execute('PRAGMA table_info(inspections)')}
        for name, definition in CASE_COLUMNS.items():
            if name not in existing:
                c.execute(f'ALTER TABLE inspections ADD COLUMN {name} {definition}')

def save(info, result, case=None, source_image=None):
    initialize()
    case = case or {}
    case_id = case.get('case_id','').strip()
    archived_path=''
    if source_image:
        source=Path(source_image)
        if not source.is_file() or source.suffix.lower() not in ('.jpg','.jpeg','.png','.webp'):
            raise ValueError('Không thể lưu ảnh hồ sơ không hợp lệ.')
        IMAGE_DIR.mkdir(parents=True,exist_ok=True)
        destination=IMAGE_DIR / f'{uuid4().hex}{source.suffix.lower()}'
        shutil.copy2(source,destination)
        archived_path=str(destination)
    try:
        with conn() as c:
            cur = c.execute('''INSERT INTO inspections
        (filename,width,height,size_bytes,mode,predicted_class,confidence,created_at,image_path,
         case_id,animal_id,farm_name,body_site,symptoms,onset_date,entered_at,review_status,
         review_note,scores_json,model_info)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            info['name'],info['width'],info['height'],info['bytes'],result['mode'],
            result.get('label'),result.get('confidence'),datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            archived_path,
            case_id,case.get('animal_id','').strip(),case.get('farm_name','').strip(),
            case.get('body_site','').strip(),case.get('symptoms','').strip(),
            case.get('onset_date','').strip(),case.get('entered_at','').strip(),
            case.get('review_status','needs_review'),
            case.get('review_note','').strip(),
            json.dumps(result.get('scores',[]),ensure_ascii=False),
            result.get('model_info','')))
            if not case_id:
                case_id = f'PS-{cur.lastrowid:06d}'
                c.execute('UPDATE inspections SET case_id=? WHERE id=?',(case_id,cur.lastrowid))
            return cur.lastrowid
    except Exception:
        if archived_path:
            Path(archived_path).unlink(missing_ok=True)
        raise

def recent(keyword=''):
    initialize()
    with conn() as c:
        pattern = '%'+keyword+'%'
        rows = c.execute('''SELECT * FROM inspections
            WHERE filename LIKE ? OR case_id LIKE ? OR animal_id LIKE ? OR farm_name LIKE ?
            ORDER BY id DESC LIMIT 300''',(pattern,pattern,pattern,pattern)).fetchall()
        return [dict(r) for r in rows]

def delete(record_id):
    with conn() as c:
        row=c.execute('SELECT image_path FROM inspections WHERE id=?',(record_id,)).fetchone()
        c.execute('DELETE FROM inspections WHERE id=?',(record_id,))
    if row and row['image_path']:
        image_file=Path(row['image_path']).resolve()
        archive_root=IMAGE_DIR.resolve()
        if archive_root in image_file.parents:
            try:
                image_file.unlink(missing_ok=True)
            except OSError:
                pass

def update_review(record_id, status, note=''):
    allowed = {'needs_review','reviewed','lab_requested','closed'}
    if status not in allowed:
        raise ValueError('Trạng thái rà soát không hợp lệ.')
    with conn() as c:
        c.execute('UPDATE inspections SET review_status=?,review_note=? WHERE id=?',
                  (status,note.strip(),record_id))

def update_case(record_id, case):
    with conn() as c:
        cur = c.execute('''UPDATE inspections SET animal_id=?,farm_name=?,body_site=?,
            symptoms=?,onset_date=?,entered_at=? WHERE id=?''', (
            case.get('animal_id','').strip(),case.get('farm_name','').strip(),
            case.get('body_site','').strip(),case.get('symptoms','').strip(),
            case.get('onset_date','').strip(),case.get('entered_at','').strip(),record_id))
        return cur.rowcount > 0

initialize()
