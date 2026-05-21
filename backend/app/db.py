"""Database access layer.

Two backends, one API:
  * SQLite  - local dev + the test suite (unchanged, native sqlite3).
  * Postgres - production (Supabase). A thin shim makes psycopg2 behave
    like sqlite3 for the raw-SQL the services already use, so no service
    code had to change.

Backend is chosen from settings.database_url: a postgres URL -> Postgres,
anything else -> SQLite file.
"""
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

from .config import get_settings

_MIG_DIR = Path(__file__).resolve().parents[2] / "migrations"
_MIGRATION_SQLITE = _MIG_DIR / "001_init.sql"
_MIGRATION_PG = _MIG_DIR / "001_init_pg.sql"


def _url() -> str:
    return get_settings().database_url


def _is_pg(url: str | None = None) -> bool:
    u = url or _url()
    return u.startswith("postgres://") or u.startswith("postgresql://")


# --------------------------------------------------------------------------
# Postgres shim - makes psycopg2 look enough like sqlite3 for our raw SQL
# --------------------------------------------------------------------------
class _PGCursor:
    def __init__(self, raw):
        self._cur = raw
        self.lastrowid = None

    def execute(self, sql: str, params=()):
        pg_sql = sql.replace("?", "%s")
        stripped = pg_sql.lstrip().lower()
        returns_id = False
        if stripped.startswith("insert") and "returning" not in stripped:
            pg_sql = pg_sql.rstrip().rstrip(";") + " RETURNING id"
            returns_id = True
        self._cur.execute(pg_sql, params)
        if returns_id:
            try:
                row = self._cur.fetchone()
                self.lastrowid = row["id"] if row else None
            except Exception:
                self.lastrowid = None
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def rowcount(self):
        return self._cur.rowcount


class _PGConn:
    """Wraps a psycopg2 connection so `.execute(sql, params)` returns a
    cursor-like object, mirroring sqlite3.Connection.execute."""

    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql: str, params=()):
        cur = _PGCursor(self._raw.cursor())
        return cur.execute(sql, params)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()


def _is_executable_sql(stmt: str) -> bool:
    """A migration fragment is executable only if at least one line
    isn't blank or a `-- comment`. A literal `;` inside an SQL comment
    (regression we hit on 2026-05-21) splits the comment in half;
    after `.strip()` the trailing half is a non-empty comment-only
    fragment that Postgres rejects with 'can't execute an empty
    query'. This guard skips those silently."""
    for line in stmt.splitlines():
        line = line.strip()
        if not line or line.startswith("--"):
            continue
        return True
    return False


def init_db(db_url: str | None = None) -> None:
    url = db_url or _url()
    if _is_pg(url):
        import psycopg2

        sql = _MIGRATION_PG.read_text(encoding="utf-8")
        conn = psycopg2.connect(url)
        try:
            with conn.cursor() as cur:
                # statements are ';'-terminated and (mostly) contain no
                # inner ';'. Guard against comments that happen to
                # contain a literal ';' by skipping comment-only
                # fragments — see _is_executable_sql.
                for raw in sql.split(";"):
                    stmt = raw.strip()
                    if stmt and _is_executable_sql(stmt):
                        cur.execute(stmt)
            conn.commit()
        finally:
            conn.close()
        return

    parent = os.path.dirname(url)
    if parent:
        os.makedirs(parent, exist_ok=True)
    sql = _MIGRATION_SQLITE.read_text(encoding="utf-8")
    conn = sqlite3.connect(url)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_conn(db_url: str | None = None):
    url = db_url or _url()
    if _is_pg(url):
        import psycopg2
        from psycopg2.extras import RealDictCursor

        raw = psycopg2.connect(url, cursor_factory=RealDictCursor)
        conn = _PGConn(raw)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(url)
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
