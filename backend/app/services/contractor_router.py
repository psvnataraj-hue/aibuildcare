"""Smart contractor routing with optional load balancing.

Portable raw SQL (SQLite test DB + Supabase Postgres via the db shim):
`is_active = 1`, lowercased LIKE (no Postgres-only ILIKE), `?` params.
"""
from __future__ import annotations

import logging

from ..db import get_conn
from . import system_config

log = logging.getLogger("aibuildcare.router")

_OPEN = "('received','acknowledged','assigned','in_progress')"


def pending_count(contractor_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM complaints "
            f"WHERE contractor_id = ? AND status IN {_OPEN}",
            (contractor_id,),
        ).fetchone()
    return dict(row)["c"]


def _candidates(category: str | None) -> list[dict]:
    if not category:
        return []
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


def best_contractor(category: str | None) -> dict | None:
    """Highest-rated matching contractor. With load balancing enabled,
    skip contractors at/over the pending-jobs threshold; if every
    candidate is overloaded, fall back to the least-loaded one."""
    cands = _candidates(category)
    if not cands:
        return None

    if not system_config.get_bool("load_balancing_enabled", True):
        log.info("LB off -> top-rated %s", cands[0]["name"])
        return cands[0]

    cap = system_config.get_int("max_pending_jobs_per_contractor", 10)
    loads = {c["id"]: pending_count(c["id"]) for c in cands}
    available = [c for c in cands if loads[c["id"]] < cap]
    if available:
        chosen = available[0]  # already rating-sorted
        log.info(
            "LB pick %s (rating %s, %d/%d pending)",
            chosen["name"], chosen["average_rating"],
            loads[chosen["id"]], cap,
        )
        return chosen
    # all overloaded -> safety fallback to least-loaded
    chosen = min(cands, key=lambda c: loads[c["id"]])
    log.warning(
        "LB all overloaded; fallback least-loaded %s (%d pending)",
        chosen["name"], loads[chosen["id"]],
    )
    return chosen


def contractors_by_category(category: str | None) -> list[dict]:
    """All active contractors for a category, best-rated first
    (manual-override dropdown)."""
    if not category:
        with get_conn() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM contractors WHERE is_active = 1 "
                    "ORDER BY average_rating DESC, name ASC"
                ).fetchall()
            ]
    return _candidates(category)
