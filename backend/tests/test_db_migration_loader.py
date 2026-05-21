"""Regression for the 2026-05-21 prod startup crash:
psycopg2.ProgrammingError: can't execute an empty query.

Cause: a literal `;` inside an SQL comment was split as a statement
boundary by `sql.split(';')`, leaving a comment-only fragment that
Postgres rejects. The loader now skips comment-only fragments via
`_is_executable_sql`.
"""
from app.db import _is_executable_sql


def test_empty_string_is_not_executable():
    assert _is_executable_sql("") is False
    assert _is_executable_sql("   ") is False
    assert _is_executable_sql("\n\n\n") is False


def test_single_line_comment_is_not_executable():
    assert _is_executable_sql("-- a comment") is False


def test_multiline_comment_is_not_executable():
    """The actual prod regression: a comment that contains a literal
    `;` gets cleaved in half by sql.split(';'). The first half ends
    with no semicolon. After stripping, it's just comment lines."""
    fragment = (
        "-- P1 (parking vertical): per-society vehicle registry.\n"
        "-- Plate is unique WITHIN a society (different societies\n"
        "-- may register the same plate"
    )
    assert _is_executable_sql(fragment) is False


def test_blank_lines_in_comment_block_still_not_executable():
    fragment = "-- comment line 1\n\n-- comment line 2\n   \n"
    assert _is_executable_sql(fragment) is False


def test_real_sql_with_leading_comments_is_executable():
    """The other half of the cleaved fragment — has actual SQL after
    one or more comment lines — IS executable."""
    fragment = (
        "-- P1: parking\n"
        "CREATE TABLE IF NOT EXISTS vehicles (\n"
        "    id INTEGER PRIMARY KEY\n"
        ")"
    )
    assert _is_executable_sql(fragment) is True


def test_inline_sql_no_comments_is_executable():
    assert _is_executable_sql(
        "ALTER TABLE complaints ADD COLUMN foo TEXT"
    ) is True


def test_init_db_tolerates_semicolon_in_comment(tmp_path, monkeypatch):
    """End-to-end: a migration script that has a `;` inside a comment
    must NOT crash init_db. Verifies the loader correctly skips the
    cleaved comment-only fragment."""
    # Patch the sqlite migration to a temp file that contains a
    # semicolon inside a comment, then a valid CREATE TABLE.
    bad_migration = (
        "-- a comment with a stray ; inside it\n"
        "CREATE TABLE IF NOT EXISTS test_init_db_table (\n"
        "    id INTEGER PRIMARY KEY,\n"
        "    name TEXT\n"
        ");\n"
    )
    mig_file = tmp_path / "bad_migration.sql"
    mig_file.write_text(bad_migration, encoding="utf-8")

    db_file = tmp_path / "test.db"
    monkeypatch.setattr(
        "app.db._MIGRATION_SQLITE", mig_file,
    )

    from app.db import init_db
    # Should not raise
    init_db(str(db_file))
    # And the table must exist
    import sqlite3
    conn = sqlite3.connect(str(db_file))
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='test_init_db_table'"
        ).fetchone()
        assert row is not None
    finally:
        conn.close()
