"""Resident-facing vendor directory.

Returns society-vetted contractors who have opted in to personal job
referrals (contractors.available_for_personal_jobs = 1), for a given
category. Each result includes a `wa_link` — a click-to-chat WhatsApp
deep link the resident (or staff sharing on a resident's behalf) can
tap to open WhatsApp pre-populated with a polite opener.

Society-scoped: only vendors of the caller's society are returned.
"""
from __future__ import annotations

import urllib.parse

from ..db import get_conn


def _wa_link(phone: str | None, category: str) -> str | None:
    """Build a WhatsApp click-to-chat link, or None if no phone."""
    if not phone:
        return None
    digits = "".join(ch for ch in phone if ch.isdigit())
    if not digits:
        return None
    text = urllib.parse.quote_plus(
        f"Hi, I would like help with {category} at my flat."
    )
    return f"https://wa.me/{digits}?text={text}"


def list_vendors(society_id: int, category: str) -> list[dict]:
    """Vetted vendors for `category` in this society, opted-in to
    personal jobs, sorted by rating desc. Empty list if nothing
    matches (no error)."""
    if not category:
        return []
    spec_like = f"%{category.strip().lower()}%"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT c.id, c.name, c.phone, c.average_rating, "
            "c.specialty, cc.primary_category "
            "FROM contractors c "
            "LEFT JOIN contractor_categories cc "
            "  ON cc.contractor_id = c.id AND cc.category = ? "
            "WHERE c.society_id = ? AND c.is_active = 1 "
            "AND COALESCE(c.available_for_personal_jobs, 1) = 1 "
            "AND (cc.id IS NOT NULL OR lower(c.specialty) LIKE ?) "
            "ORDER BY c.average_rating DESC, c.name ASC",
            (category, society_id, spec_like),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["wa_link"] = _wa_link(d.get("phone"), category)
        # the SQL field is_for_filtering only; surface a clean shape
        out.append({
            "id": d["id"],
            "name": d["name"],
            "phone": d.get("phone"),
            "average_rating": float(d["average_rating"])
                if d.get("average_rating") is not None else None,
            "specialty": d.get("specialty"),
            "primary_category": bool(d.get("primary_category")),
            "wa_link": d["wa_link"],
        })
    return out
