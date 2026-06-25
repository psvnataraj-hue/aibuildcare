"""Dump the live Supabase Postgres database to a portable .sql file.

Written 2026 for the "Supabase access may be cut off — back everything up"
emergency. Uses psycopg2 (already in backend/.venv), so no pg_dump install
needed.

Output: a single .sql file containing CREATE TABLE statements + INSERT
statements for every table in the `public` schema. Replayable against any
Postgres (Supabase, local, AWS RDS, anything) to recreate the DB
byte-equivalent.

Usage from repo root:

    # 1. Set the connection string in PowerShell (do NOT paste it elsewhere):
    $env:AIBUILDCARE_DATABASE_URL = '<your Supabase session-pooler URL>'

    # 2. Run the dump:
    .\backend\.venv\Scripts\python scripts\backup_supabase.py

    # 3. (Optional) Override the output path:
    .\backend\.venv\Scripts\python scripts\backup_supabase.py --out E:\CARIMO\aibuildcare_backup\dump.sql

By default writes to: E:\CARIMO\aibuildcare_backup\aibuildcare_supabase_<UTC-timestamp>.sql
(off OneDrive, off GitHub — the dump contains seeded user records + bcrypted
password hashes; treat the .sql file as sensitive.)

Read-only on the DB: only SELECTs run. Cannot corrupt the source DB.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 stdout so the progress lines render on Windows cp1252 consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _quote_value(v) -> str:
    """SQL-quote a value for an INSERT statement. Handles None, numbers,
    strings (with single-quote escape), bools, bytes, lists/dicts."""
    import json
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (bytes, memoryview)):
        b = bytes(v)
        return "'\\x" + b.hex() + "'"  # Postgres bytea hex literal
    if isinstance(v, (list, dict)):
        # JSON columns
        return "'" + json.dumps(v, ensure_ascii=False).replace("'", "''") + "'"
    # Strings (or anything stringifiable — datetime/Decimal/etc.)
    s = str(v)
    return "'" + s.replace("'", "''") + "'"


def _get_tables(cur) -> list[str]:
    cur.execute(
        """SELECT tablename FROM pg_catalog.pg_tables
           WHERE schemaname = 'public'
           ORDER BY tablename"""
    )
    return [r[0] for r in cur.fetchall()]


def _get_create_table(cur, table: str) -> str:
    """Reconstruct a CREATE TABLE statement from information_schema.
    pg_dump-perfect this isn't — but it captures column names + types +
    nullability + defaults, which is enough to replay the data."""
    cur.execute(
        """SELECT column_name, data_type, is_nullable, column_default,
                  character_maximum_length
           FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = %s
           ORDER BY ordinal_position""",
        (table,),
    )
    cols = cur.fetchall()
    if not cols:
        return f"-- (no columns found for {table})\n"
    lines: list[str] = []
    for name, dtype, nullable, default, maxlen in cols:
        type_str = dtype.upper()
        if maxlen and dtype in ("character varying", "character"):
            type_str = f"{dtype.upper()}({maxlen})"
        parts = [f'    "{name}"', type_str]
        if nullable == "NO":
            parts.append("NOT NULL")
        if default:
            parts.append(f"DEFAULT {default}")
        lines.append(" ".join(parts))

    # Primary keys
    cur.execute(
        """SELECT a.attname
           FROM pg_index i
           JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
           WHERE i.indrelid = %s::regclass AND i.indisprimary
           ORDER BY array_position(i.indkey, a.attnum)""",
        (table,),
    )
    pk_cols = [r[0] for r in cur.fetchall()]
    if pk_cols:
        lines.append(f'    PRIMARY KEY ({", ".join(chr(34)+c+chr(34) for c in pk_cols)})')

    body = ",\n".join(lines)
    return f'CREATE TABLE IF NOT EXISTS "{table}" (\n{body}\n);\n'


def _dump_table_rows(cur, out, table: str, batch: int = 1000) -> int:
    """SELECT * from a table and write INSERT statements, batched."""
    cur.execute(f'SELECT * FROM "{table}"')
    colnames = [d[0] for d in cur.description]
    if not colnames:
        return 0
    col_list = ", ".join(f'"{c}"' for c in colnames)
    total = 0
    while True:
        rows = cur.fetchmany(batch)
        if not rows:
            break
        for row in rows:
            values = ", ".join(_quote_value(v) for v in row)
            out.write(
                f'INSERT INTO "{table}" ({col_list}) VALUES ({values});\n'
            )
        total += len(rows)
    return total


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=None,
                   help="Output .sql path. Default: "
                        "E:/CARIMO/aibuildcare_backup/aibuildcare_supabase_<UTC>.sql")
    args = p.parse_args()

    url = os.getenv("AIBUILDCARE_DATABASE_URL")
    if not url:
        print("ERROR: AIBUILDCARE_DATABASE_URL not set.")
        print("Set it in your terminal first (do NOT paste it into chat):")
        print('  $env:AIBUILDCARE_DATABASE_URL = ' + "'<your supabase URL>'")
        return 2

    out_path = Path(args.out) if args.out else Path(
        f"E:/CARIMO/aibuildcare_backup/aibuildcare_supabase_{_utc_stamp()}.sql"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"connecting to Postgres...")
    try:
        import psycopg2
        conn = psycopg2.connect(url)
    except Exception as exc:
        print(f"ERROR connecting to DB: {type(exc).__name__}: {exc}")
        return 3

    print(f"writing to {out_path}")

    with conn.cursor() as cur, open(out_path, "w", encoding="utf-8") as out:
        # Header
        out.write(f"-- AIBuildCare Supabase backup\n")
        out.write(f"-- Generated: {datetime.now(timezone.utc).isoformat()}\n")
        out.write(f"-- Tool: scripts/backup_supabase.py (psycopg2 dump)\n")
        out.write(f"-- Replay: psql <target_db_url> < this_file.sql\n")
        out.write(f"-- WARNING: contains seeded user records + bcrypted password hashes;\n")
        out.write(f"-- treat as sensitive.\n\n")
        out.write("BEGIN;\n\n")

        tables = _get_tables(cur)
        print(f"  found {len(tables)} tables in public schema")

        # Schema first
        out.write("-- ============ SCHEMA ============\n\n")
        for t in tables:
            try:
                out.write(_get_create_table(cur, t))
                out.write("\n")
            except Exception as exc:
                print(f"    WARN schema for {t}: {exc}")
                out.write(f"-- WARN: could not introspect schema for {t}: {exc}\n\n")

        # Data
        out.write("-- ============ DATA ============\n\n")
        grand = 0
        for t in tables:
            try:
                n = _dump_table_rows(cur, out, t)
                grand += n
                print(f"    {t}: {n} rows")
                out.write("\n")
            except Exception as exc:
                print(f"    WARN data for {t}: {exc}")
                out.write(f"-- WARN: data dump for {t} failed: {exc}\n\n")

        out.write("COMMIT;\n")

    conn.close()
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"\nDONE: {grand} total rows across {len(tables)} tables -> {out_path}")
    print(f"file size: {size_mb:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
