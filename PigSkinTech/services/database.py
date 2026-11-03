import os
import re
import threading

SERVER = os.environ.get('PIGSKIN_SQLSERVER', r'(localdb)\MSSQLLocalDB')
DATABASE = os.environ.get('PIGSKIN_DATABASE', 'PigSkinAI')
_ready = False
_ready_lock = threading.Lock()


class Row(dict):
    def __init__(self, columns, values):
        super().__init__(zip(columns, values))
        self._values = values

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class Cursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, parameters=()):
        self._cursor.execute(query, tuple(parameters))
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        columns = [column[0] for column in self._cursor.description]
        return Row(columns, tuple(row))

    def fetchall(self):
        columns = [column[0] for column in self._cursor.description]
        return [Row(columns, tuple(row)) for row in self._cursor.fetchall()]

    @property
    def rowcount(self):
        return self._cursor.rowcount


class Connection:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, query, parameters=()):
        return Cursor(self._connection.cursor()).execute(query, parameters)


def _pyodbc():
    try:
        import pyodbc
    except ImportError as exc:
        raise RuntimeError(
            'Thiếu pyodbc. Hãy cài dependencies bằng: '
            'python -m pip install -r requirements.txt'
        ) from exc
    return pyodbc


def _driver(pyodbc):
    configured = os.environ.get('PIGSKIN_SQL_DRIVER')
    drivers = pyodbc.drivers()
    if configured:
        if configured not in drivers:
            raise RuntimeError(f'Không tìm thấy ODBC driver đã cấu hình: {configured}')
        return configured
    for candidate in ('ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server'):
        if candidate in drivers:
            return candidate
    raise RuntimeError(
        'Không tìm thấy ODBC Driver 17 hoặc 18 for SQL Server. '
        'Cài Microsoft ODBC Driver for SQL Server rồi thử lại.'
    )


def _connection_string(database):
    if not re.fullmatch(r'[A-Za-z0-9_]+', database):
        raise ValueError('Tên database chỉ được chứa chữ, số và dấu gạch dưới.')
    pyodbc = _pyodbc()
    driver = _driver(pyodbc)
    return (
        f'DRIVER={{{driver}}};SERVER={SERVER};DATABASE={database};'
        'Trusted_Connection=yes;Encrypt=no;'
    )


def _connect(database):
    return _pyodbc().connect(_connection_string(database), timeout=10)


def ensure_database():
    global _ready
    if _ready:
        return
    with _ready_lock:
        if _ready:
            return
        if not re.fullmatch(r'[A-Za-z0-9_]+', DATABASE):
            raise ValueError('Tên database chỉ được chứa chữ, số và dấu gạch dưới.')
        connection = _pyodbc().connect(
            _connection_string('master'), timeout=10, autocommit=True
        )
        try:
            cursor = connection.cursor()
            exists = cursor.execute(
                'SELECT database_id FROM sys.databases WHERE name=?', DATABASE
            ).fetchone()
            if exists is None:
                try:
                    cursor.execute(f'CREATE DATABASE [{DATABASE}]')
                except Exception:
                    exists = cursor.execute(
                        'SELECT database_id FROM sys.databases WHERE name=?', DATABASE
                    ).fetchone()
                    if exists is None:
                        raise
            _ready = True
        finally:
            connection.close()


class ConnectionContext:
    def __enter__(self):
        ensure_database()
        self._connection = _connect(DATABASE)
        return Connection(self._connection)

    def __exit__(self, *exception_info):
        try:
            if exception_info[0] is None:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            self._connection.close()
        return False


def conn():
    return ConnectionContext()
