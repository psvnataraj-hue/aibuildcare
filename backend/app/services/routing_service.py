"""Society-scoped, category-aware auto-assignment.

Order (spec Part 3.1):
  1. In-house staff with this category as PRIMARY (sorted:
     skill_level expert > senior > junior, then ascending workload).
  2. In-house staff with this category as secondary.
  3. External contractors with this category as PRIMARY (via the new
     contractor_categories M:N) — sorted by rating desc, workload asc.
  4. External contractors via legacy `contractors.specialty` match.
  5. None -> complaint stays in 'received' (manager must assign).

All queries are scoped by society_id (tenant boundary).
Auto-assignment itself is gated upstream by settings.auto_assign_enabled.
"""
from ..db import get_conn
from .contractor_router import pending_count


_SKILL_RANK = {"expert": 0, "senior": 1, "junior": 2}


def _staff_workload(conn, staff_id: int) -> int:
    r = conn.execute(
        "SELECT COUNT(*) AS c FROM complaints "
        "WHERE assigned_staff_id = ? "
        "AND status NOT IN ('resolved','closed')",
        (staff_id,),
    ).fetchone()
    return dict(r)["c"]


def _staff_candidates(
    conn, category: str, society_id: int
) -> list[dict]:
    rows = conn.execute(
        "SELECT sm.id, sm.name, sm.phone_primary AS phone, "
        "sm.whatsapp_enabled, sc.primary_category, sc.skill_level "
        "FROM staff_members sm "
        "JOIN staff_categories sc ON sc.staff_id = sm.id "
        "WHERE sm.society_id = ? AND sm.active = 1 "
        "AND sc.category = ?",
        (society_id, category),
    ).fetchall()
    cands = [dict(r) for r in rows]
    for c in cands:
        c["workload"] = _staff_workload(conn, c["id"])
    cands.sort(key=lambda c: (
        0 if c["primary_category"] else 1,
        _SKILL_RANK.get(c.get("skill_level"), 9),
        c["workload"],
    ))
    return cands


def _contractor_candidates(
    conn, category: str, society_id: int
) -> list[dict]:
    # Legacy `contractors.specialty` is a comma-separated string
    # (e.g. "AC/Cooling,Heating") so match it case-insensitively via
    # LIKE; the new contractor_categories M:N uses exact-category rows.
    spec_like = f"%{category.strip().lower()}%"
    rows = conn.execute(
        "SELECT c.id, c.name, c.phone, c.average_rating, "
        "cc.primary_category "
        "FROM contractors c "
        "LEFT JOIN contractor_categories cc "
        "  ON cc.contractor_id = c.id AND cc.category = ? "
        "WHERE c.society_id = ? AND c.is_active = 1 "
        "AND (cc.id IS NOT NULL OR lower(c.specialty) LIKE ?)",
        (category, society_id, spec_like),
    ).fetchall()
    cands = [dict(r) for r in rows]
    for c in cands:
        c["workload"] = pending_count(c["id"])
    cands.sort(key=lambda c: (
        0 if c.get("primary_category") else 1,
        -float(c.get("average_rating") or 0),
        c["workload"],
    ))
    return cands


def find_assignee(
    category: str | None, society_id: int
) -> dict | None:
    """Pick the best assignee for this complaint or None.

    Returns: {"type": "staff"|"contractor", "id", "name", "phone",
              "whatsapp_enabled"} or None.
    """
    if not category:
        return None
    with get_conn() as conn:
        staff = _staff_candidates(conn, category, society_id)
        if staff:
            s = staff[0]
            return {
                "type": "staff",
                "id": s["id"],
                "name": s["name"],
                "phone": s.get("phone"),
                "whatsapp_enabled": bool(s.get("whatsapp_enabled")),
            }
        contractors = _contractor_candidates(conn, category, society_id)
        if contractors:
            c = contractors[0]
            return {
                "type": "contractor",
                "id": c["id"],
                "name": c["name"],
                "phone": c.get("phone"),
                "whatsapp_enabled": True,  # contractors default on
            }
    return None
