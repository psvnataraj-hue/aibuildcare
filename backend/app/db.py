import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

from .config import get_settings

_MIGRATION = (
    Path(__file__).resolve().parents[2] / "migrations" / "001_init.sql"
)


def _db_path() -> str:
    return get_settings().database_url


def init_db(db_path: str | None = None) -> None:
    path = db_path or _db_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    sql = _MIGRATION.read_text(encoding="utf-8")
    conn = sqlite3.connect(path)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_conn(db_path: str | None = None):
    conn = sqlite3.connect(db_path or _db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
