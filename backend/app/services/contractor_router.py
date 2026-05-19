"""Smart contractor routing.

Picks the highest-rated active contractor whose specialty matches a
complaint category. Portable raw SQL (works on both the SQLite test DB
and Supabase Postgres via the db shim): `is_active = 1`, lowercased
LIKE (no Postgres-only ILIKE), `?` placeholders.
"""
from __future__ import annotations

from ..db import get_conn


def best_contractor(category: str | None) -> dict | None:
    """Top-rated active contractor for the category, or None."""
    if not category:
        return None
    like = f"%{category.strip().lower()}%"
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM contractors "
            "WHERE is_active = 1 AND lower(specialty) LIKE ? "
            "ORDER BY average_rating DESC, name ASC LIMIT 1",
            (like,),
        ).fetchone()
        return dict(row) if row else None


def contractors_by_category(category: str | None) -> list[dict]:
    """All active contractors for a category, best-rated first
    (used by the manual-override dropdown)."""
    if not category:
        with get_conn() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM contractors WHERE is_active = 1 "
                    "ORDER BY average_rating DESC, name ASC"
                ).fetchall()
            ]
    like = f"%{category.strip().lower()}%"
    with get_conn() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM contractors "
                "WHERE is_active = 1 AND lower(specialty) LIKE ? "
                "ORDER BY average_rating DESC, name ASC",
                (like,),
            ).fetchall()
        ]
