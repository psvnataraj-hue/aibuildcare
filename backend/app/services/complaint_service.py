import json
from datetime import datetime, timedelta, timezone

from ..db import get_conn
from .haiku_parser import parse_complaint

# fallback completion estimate (hours) when there is no history yet
DEFAULT_FORECAST_HOURS = {
    # safety-critical
    "Fire Safety": 4,
    "Security": 6,
    "Elevator": 6,
    "Generator/Power Backup": 8,
    # building / common-area services
    "Electrical": 12,
    "Plumbing": 24,
    "AC/Cooling": 24,
    "Water Supply": 12,
    "Sewage/Drainage": 12,
    "Lighting": 24,
    "Housekeeping": 24,
    "Garbage/Waste": 24,
    "Pest Control": 48,
    "Gardening": 72,
    "Carpentry": 48,
    "Painting": 72,
    "Civil/Structural": 96,
    "CCTV/Intercom": 24,
    # amenities
    "Swimming Pool": 48,
    "Sports/Gym/Clubhouse": 72,
    "Children's Play Area": 48,
    # community / non-physical
    "Parking Management": 24,
    "Noise/Visitor": 6,
    "Other": 48,
}


def category_avg_resolution_hours(category: str | None) -> float:
    """Avg assigned->resolved hours for the category from history,
    else a sensible per-category default."""
    default = DEFAULT_FORECAST_HOURS.get(category or "", 48)
    if not category:
        return float(default)
    with get_conn() as conn:
        ids = [
            dict(r)["id"]
            for r in conn.execute(
                "SELECT id FROM complaints WHERE category = ? "
                "AND status IN ('resolved','closed')",
                (category,),
            ).fetchall()
        ]
        pairs = []
        for cid in ids:
            hist = [
                dict(h)
                for h in conn.execute(
                    "SELECT to_status, created_at FROM "
                    "complaint_status_history WHERE complaint_id = ? "
                    "ORDER BY created_at",
                    (cid,),
                ).fetchall()
            ]
            first: dict = {}
            for h in hist:
                first.setdefault(h["to_status"], h["created_at"])
            if "assigned" in first and "resolved" in first:
                pairs.append((first["assigned"], first["resolved"]))
    hrs = _avg_hours(pairs)
    return float(hrs) if hrs else float(default)

STATUS_FLOW = [
    "received",
    "acknowledged",
    "assigned",
    "in_progress",
    "resolved",
    "closed",
]

ACK_TICK = "\u2705"


class ComplaintError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_ticket(conn) -> str:
    year = datetime.now(timezone.utc).year
    row = conn.execute("SELECT COUNT(*) AS c FROM complaints").fetchone()
    return f"SER-{year}-{row['c'] + 1:05d}"


def _default_society_id(conn) -> int:
    """Fallback tenant for back-compat callers (webhooks, legacy)
    until per-society inbound routing (Enterprise R1) lands."""
    r = conn.execute(
        "SELECT id FROM societies ORDER BY id LIMIT 1"
    ).fetchone()
    return dict(r)["id"] if r else 1


def _sid(conn, society_id: int | None) -> int:
    return society_id if society_id is not None else _default_society_id(conn)


def _row_to_dict(row) -> dict | None:
    if not row:
        return None
    d = dict(row)
    if "official_summaries" in d:
        raw = d["official_summaries"]
        try:
            d["official_summaries"] = json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            d["official_summaries"] = {}
    return d


def create_complaint(
    raw_text: str,
    channel: str = "dashboard",
    reporter_phone: str | None = None,
    reporter_email: str | None = None,
    image_urls: list[str] | None = None,
    society_id: int | None = None,
) -> dict:
    parsed = parse_complaint(raw_text, image_urls)
    media = ",".join(image_urls) if image_urls else None
    with get_conn() as conn:
        sid = _sid(conn, society_id)
        ticket = _next_ticket(conn)
        ack = f"{ACK_TICK} Ticket {ticket}. {parsed.acknowledgement}"
        cur = conn.execute(
            "INSERT INTO complaints (ticket_number, society_id, "
            "unit_number, category, "
            "priority, status, channel, raw_text, acknowledgement, "
            "reporter_phone, reporter_email, media_urls, detected_language, "
            "official_summaries, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ticket,
                sid,
                parsed.unit_number,
                parsed.category,
                parsed.priority,
                "received",
                channel,
                raw_text,
                ack,
                reporter_phone,
                reporter_email,
                media,
                parsed.detected_language,
                json.dumps(parsed.official_summaries or {}),
                _now(),
                _now(),
            ),
        )
        cid = cur.lastrowid
        conn.execute(
            "INSERT INTO complaint_status_history (complaint_id, "
            "from_status, to_status, changed_by) VALUES (?,?,?,?)",
            (cid, None, "received", channel),
        )
        conn.execute(
            "INSERT INTO complaint_messages (complaint_id, sender, body) "
            "VALUES (?,?,?)",
            (cid, "system", ack),
        )
        # --- smart auto-assignment (Phase 4.5) ---------------------------
        from ..config import get_settings
        from .contractor_router import best_contractor

        con = (
            best_contractor(parsed.category)
            if get_settings().auto_assign_enabled
            else None
        )
        if con:
            eta = (
                datetime.now(timezone.utc)
                + timedelta(
                    hours=category_avg_resolution_hours(parsed.category)
                )
            ).isoformat()
            conn.execute(
                "UPDATE complaints SET contractor_id = ?, "
                "status = 'assigned', updated_at = ?, "
                "estimated_completion_date = ? WHERE id = ?",
                (con["id"], _now(), eta, cid),
            )
            conn.execute(
                "INSERT INTO complaint_status_history (complaint_id, "
                "from_status, to_status, changed_by) VALUES (?,?,?,?)",
                (cid, "received", "assigned", "auto-router"),
            )
            conn.execute(
                "INSERT INTO complaint_messages (complaint_id, sender, "
                "body) VALUES (?,?,?)",
                (
                    cid,
                    "system",
                    f"Auto-assigned to {con['name']} "
                    f"(rating {con['average_rating']}).",
                ),
            )
        row = conn.execute(
            "SELECT * FROM complaints WHERE id = ?", (cid,)
        ).fetchone()
        result = _row_to_dict(row)

    # notify the auto-assigned contractor (graceful no-op w/o Twilio)
    if con and con.get("phone"):
        from .notify import send_whatsapp

        send_whatsapp(
            con["phone"],
            f"{ACK_TICK} ASSIGNED: {con['name']}. Unit "
            f"{result.get('unit_number') or '?'}, "
            f"{result.get('category')} ({result['ticket_number']}). "
            f"Status: Assigned.",
        )
    return result


def list_complaints(
    status: str | None = None,
    q: str | None = None,
    sort: str = "created_at",
    society_id: int | None = None,
) -> list[dict]:
    sort_col = (
        sort if sort in {"created_at", "priority", "status"} else "created_at"
    )
    with get_conn() as conn:
        sid = _sid(conn, society_id)
        clauses = ["society_id = ?"]  # tenant boundary, always applied
        params: list = [sid]
        if status:
            clauses.append("status = ?")
            params.append(status)
        if q:
            clauses.append(
                "(raw_text LIKE ? OR ticket_number LIKE ? "
                "OR unit_number LIKE ?)"
            )
            params += [f"%{q}%"] * 3
        sql = (
            "SELECT * FROM complaints WHERE "
            + " AND ".join(clauses)
            + f" ORDER BY {sort_col} DESC"
        )
        return [_row_to_dict(r) for r in conn.execute(sql, params).fetchall()]


def get_complaint(cid: int, society_id: int | None = None) -> dict:
    with get_conn() as conn:
        sid = _sid(conn, society_id)
        row = conn.execute(
            "SELECT * FROM complaints WHERE id = ? AND society_id = ?",
            (cid, sid),
        ).fetchone()
        if not row:
            raise ComplaintError("complaint not found")
        return _row_to_dict(row)


def assign_contractor(
    cid: int, contractor_id: int, society_id: int | None = None
) -> dict:
    with get_conn() as conn:
        sid = _sid(conn, society_id)
        c = conn.execute(
            "SELECT id FROM contractors WHERE id = ? AND is_active = 1",
            (contractor_id,),
        ).fetchone()
        if not c:
            raise ComplaintError("contractor not found")
        cur = conn.execute(
            "UPDATE complaints SET contractor_id = ?, status = 'assigned', "
            "updated_at = ? WHERE id = ? AND society_id = ?",
            (contractor_id, _now(), cid, sid),
        )
        if cur.rowcount == 0:
            raise ComplaintError("complaint not found")
        conn.execute(
            "INSERT INTO complaint_status_history (complaint_id, "
            "to_status, changed_by) VALUES (?,?,?)",
            (cid, "assigned", "staff"),
        )
        row = conn.execute(
            "SELECT * FROM complaints WHERE id = ?", (cid,)
        ).fetchone()
        return _row_to_dict(row)


def update_status(
    cid: int, new_status: str, society_id: int | None = None
) -> dict:
    if new_status not in STATUS_FLOW:
        raise ComplaintError(f"invalid status: {new_status}")
    with get_conn() as conn:
        sid = _sid(conn, society_id)
        row = conn.execute(
            "SELECT status FROM complaints WHERE id = ? AND society_id = ?",
            (cid, sid),
        ).fetchone()
        if not row:
            raise ComplaintError("complaint not found")
        old = row["status"]
        if STATUS_FLOW.index(new_status) < STATUS_FLOW.index(old):
            raise ComplaintError(
                f"cannot move from {old} back to {new_status}"
            )
        resolved = _now() if new_status == "resolved" else None
        conn.execute(
            "UPDATE complaints SET status = ?, updated_at = ?, "
            "resolved_at = COALESCE(?, resolved_at) WHERE id = ?",
            (new_status, _now(), resolved, cid),
        )
        conn.execute(
            "INSERT INTO complaint_status_history (complaint_id, "
            "from_status, to_status, changed_by) VALUES (?,?,?,?)",
            (cid, old, new_status, "staff"),
        )
        out = conn.execute(
            "SELECT * FROM complaints WHERE id = ?", (cid,)
        ).fetchone()
        return _row_to_dict(out)


def add_message(
    cid: int, sender: str, body: str, society_id: int | None = None
) -> dict:
    with get_conn() as conn:
        sid = _sid(conn, society_id)
        exists = conn.execute(
            "SELECT 1 FROM complaints WHERE id = ? AND society_id = ?",
            (cid, sid),
        ).fetchone()
        if not exists:
            raise ComplaintError("complaint not found")
        cur = conn.execute(
            "INSERT INTO complaint_messages (complaint_id, sender, body) "
            "VALUES (?,?,?)",
            (cid, sender, body),
        )
        row = conn.execute(
            "SELECT * FROM complaint_messages WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
        return dict(row)


def list_messages(cid: int, society_id: int | None = None) -> list[dict]:
    with get_conn() as conn:
        sid = _sid(conn, society_id)
        owns = conn.execute(
            "SELECT 1 FROM complaints WHERE id = ? AND society_id = ?",
            (cid, sid),
        ).fetchone()
        if not owns:
            return []  # cross-society: reveal nothing
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM complaint_messages WHERE complaint_id = ? "
                "ORDER BY created_at",
                (cid,),
            ).fetchall()
        ]


def get_contractor(contractor_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM contractors WHERE id = ?", (contractor_id,)
        ).fetchone()
        return dict(row) if row else None


def rate_complaint(
    cid: int, rating: int, feedback: str | None,
    society_id: int | None = None,
) -> dict:
    if rating < 1 or rating > 5:
        raise ComplaintError("rating must be 1-5")
    with get_conn() as conn:
        sid = _sid(conn, society_id)
        row = conn.execute(
            "SELECT status FROM complaints WHERE id = ? AND society_id = ?",
            (cid, sid),
        ).fetchone()
        if not row:
            raise ComplaintError("complaint not found")
        if row["status"] not in ("resolved", "closed"):
            raise ComplaintError("can only rate a resolved complaint")
        dup = conn.execute(
            "SELECT 1 FROM complaint_ratings WHERE complaint_id = ?", (cid,)
        ).fetchone()
        if dup:
            raise ComplaintError("complaint already rated")
        conn.execute(
            "INSERT INTO complaint_ratings (complaint_id, rating, feedback, "
            "created_at) VALUES (?,?,?,?)",
            (cid, rating, feedback, _now()),
        )
        out = conn.execute(
            "SELECT rating, feedback, created_at AS rated_at "
            "FROM complaint_ratings WHERE complaint_id = ?",
            (cid,),
        ).fetchone()
        return dict(out)


def get_rating(cid: int, society_id: int | None = None) -> dict | None:
    with get_conn() as conn:
        sid = _sid(conn, society_id)
        owns = conn.execute(
            "SELECT 1 FROM complaints WHERE id = ? AND society_id = ?",
            (cid, sid),
        ).fetchone()
        if not owns:
            return None
        row = conn.execute(
            "SELECT rating, feedback, created_at AS rated_at "
            "FROM complaint_ratings WHERE complaint_id = ?",
            (cid,),
        ).fetchone()
        return dict(row) if row else None


def _avg_hours(pairs: list[tuple[str, str]]) -> float | None:
    spans = []
    for a, b in pairs:
        try:
            ta = datetime.fromisoformat(a)
            tb = datetime.fromisoformat(b)
            spans.append((tb - ta).total_seconds())
        except Exception:
            continue
    if not spans:
        return None
    return round(sum(spans) / len(spans) / 3600, 2)


def contractor_performance(contractor_id: int | None = None) -> list[dict]:
    with get_conn() as conn:
        if contractor_id is not None:
            cons = conn.execute(
                "SELECT * FROM contractors WHERE id = ?", (contractor_id,)
            ).fetchall()
        else:
            cons = conn.execute(
                "SELECT * FROM contractors WHERE is_active = 1 ORDER BY name"
            ).fetchall()
        out = []
        for con in cons:
            con = dict(con)
            comps = [
                dict(r)
                for r in conn.execute(
                    "SELECT id, status, updated_at FROM complaints "
                    "WHERE contractor_id = ?",
                    (con["id"],),
                ).fetchall()
            ]
            assigned = len(comps)
            resolved = sum(
                1 for c in comps if c["status"] in ("resolved", "closed")
            )
            resp_pairs, reso_pairs = [], []
            for c in comps:
                hist = [
                    dict(h)
                    for h in conn.execute(
                        "SELECT to_status, created_at FROM "
                        "complaint_status_history WHERE complaint_id = ? "
                        "ORDER BY created_at",
                        (c["id"],),
                    ).fetchall()
                ]
                first = {}
                for h in hist:
                    first.setdefault(h["to_status"], h["created_at"])
                if "assigned" in first and "in_progress" in first:
                    resp_pairs.append(
                        (first["assigned"], first["in_progress"])
                    )
                if "assigned" in first and "resolved" in first:
                    reso_pairs.append((first["assigned"], first["resolved"]))
            last = max((c["updated_at"] for c in comps), default=None)
            out.append(
                {
                    "contractor_id": con["id"],
                    "name": con["name"],
                    "phone": con["phone"],
                    "specialty": con["specialty"],
                    "average_rating": con.get("average_rating"),
                    "assigned_count": assigned,
                    "resolved_count": resolved,
                    "avg_response_time_hours": _avg_hours(resp_pairs),
                    "avg_resolution_time_hours": _avg_hours(reso_pairs),
                    "completion_rate": (
                        round(resolved / assigned * 100, 1)
                        if assigned
                        else 0.0
                    ),
                    "last_activity": last,
                }
            )
        return out


def _spans_hours(pairs):
    out = []
    for a, b in pairs:
        try:
            out.append(
                (datetime.fromisoformat(b) - datetime.fromisoformat(a))
                .total_seconds()
                / 3600
            )
        except Exception:
            continue
    return out


def _hist_first(conn, cid):
    first = {}
    for h in conn.execute(
        "SELECT to_status, created_at FROM complaint_status_history "
        "WHERE complaint_id = ? ORDER BY created_at",
        (cid,),
    ).fetchall():
        d = dict(h)
        first.setdefault(d["to_status"], d["created_at"])
    return first


def contractor_analytics(contractor_id: int) -> dict | None:
    with get_conn() as conn:
        crow = conn.execute(
            "SELECT * FROM contractors WHERE id = ?", (contractor_id,)
        ).fetchone()
        if not crow:
            return None
        con = dict(crow)
        comps = [
            dict(r)
            for r in conn.execute(
                "SELECT id, status, category, updated_at FROM complaints "
                "WHERE contractor_id = ?",
                (contractor_id,),
            ).fetchall()
        ]
        open_set = {"received", "acknowledged", "assigned"}
        pending = sum(1 for c in comps if c["status"] in open_set)
        in_prog = sum(1 for c in comps if c["status"] == "in_progress")
        completed = sum(
            1 for c in comps if c["status"] in ("resolved", "closed")
        )
        resp, reso = [], []
        for c in comps:
            f = _hist_first(conn, c["id"])
            if "assigned" in f and "in_progress" in f:
                resp.append((f["assigned"], f["in_progress"]))
            if "assigned" in f and "resolved" in f:
                reso.append((f["assigned"], f["resolved"]))
        rs, rz = _spans_hours(resp), _spans_hours(reso)
        ratings = [
            dict(r)["rating"]
            for r in conn.execute(
                "SELECT cr.rating FROM complaint_ratings cr "
                "JOIN complaints c ON c.id = cr.complaint_id "
                "WHERE c.contractor_id = ? ORDER BY cr.created_at",
                (contractor_id,),
            ).fetchall()
        ]
        spec: dict = {}
        for c in comps:
            cat = c["category"] or "Other"
            spec.setdefault(cat, 0)
            if c["status"] in ("resolved", "closed"):
                spec[cat] += 1
        total = len(comps) or 1

        def stat(xs):
            return {
                "avg_hours": round(sum(xs) / len(xs), 2) if xs else None,
                "min_hours": round(min(xs), 2) if xs else None,
                "max_hours": round(max(xs), 2) if xs else None,
                "trend": [round(x, 2) for x in xs[-5:]],
            }

        return {
            "contractor_id": con["id"],
            "name": con["name"],
            "rating": con.get("average_rating"),
            "workload": {
                "pending_count": pending,
                "in_progress_count": in_prog,
                "completed_count": completed,
                "total_assigned": len(comps),
            },
            "response_time": stat(rs),
            "resolution_time": stat(rz),
            "rating_trend": {
                "current": con.get("average_rating"),
                "data_points": ratings[-5:],
                "samples": len(ratings),
            },
            "category_specialization": {
                k: {
                    "completed": v,
                    "pct_of_total": round(v / total * 100, 1),
                }
                for k, v in spec.items()
            },
            "availability": {
                "status": "online" if con.get("is_active") else "inactive",
                "last_activity": max(
                    (c["updated_at"] for c in comps), default=None
                ),
            },
        }


def analytics_summary() -> dict:
    from . import system_config

    cap = system_config.get_int("max_pending_jobs_per_contractor", 10)
    with get_conn() as conn:
        cons = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM contractors WHERE is_active = 1"
            ).fetchall()
        ]
        total_all = dict(
            conn.execute(
                "SELECT COUNT(*) AS c FROM contractors"
            ).fetchone()
        )["c"]
        perf = contractor_performance()
    ratings = [
        c["average_rating"] for c in cons if c.get("average_rating")
    ]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
    by_id = {p["contractor_id"]: p for p in perf}
    top = sorted(
        perf, key=lambda p: (p["resolved_count"], p.get("average_rating") or 0),
        reverse=True,
    )[:5]
    available = at_cap = 0
    for c in cons:
        from .contractor_router import pending_count

        if pending_count(c["id"]) >= cap:
            at_cap += 1
        else:
            available += 1
    cat_perf: dict = {}
    for p in perf:
        cat = (p.get("specialty") or "Other").split(",")[0]
        cat_perf.setdefault(cat, {"resp": [], "reso": []})
        if p["avg_response_time_hours"] is not None:
            cat_perf[cat]["resp"].append(p["avg_response_time_hours"])
        if p["avg_resolution_time_hours"] is not None:
            cat_perf[cat]["reso"].append(p["avg_resolution_time_hours"])
    return {
        "total_contractors": total_all,
        "active_contractors": len(cons),
        "avg_rating_across_all": avg_rating,
        "top_performers": [
            {
                "name": t["name"],
                "rating": by_id[t["contractor_id"]].get("average_rating"),
                "completed": t["resolved_count"],
            }
            for t in top
        ],
        "workload_distribution": {
            "available": available,
            "at_capacity": at_cap,
            "overloaded": 0,
        },
        "category_performance": {
            k: {
                "avg_response_time": (
                    round(sum(v["resp"]) / len(v["resp"]), 2)
                    if v["resp"]
                    else None
                ),
                "avg_resolution_time": (
                    round(sum(v["reso"]) / len(v["reso"]), 2)
                    if v["reso"]
                    else None
                ),
            }
            for k, v in cat_perf.items()
        },
    }


def analytics() -> dict:
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) c FROM complaints"
        ).fetchone()["c"]
        open_ = conn.execute(
            "SELECT COUNT(*) c FROM complaints WHERE status NOT IN "
            "('resolved','closed')"
        ).fetchone()["c"]
        urgent = conn.execute(
            "SELECT COUNT(*) c FROM complaints WHERE priority = 'urgent' "
            "AND status NOT IN ('resolved','closed')"
        ).fetchone()["c"]
        by_status = {
            r["status"]: r["c"]
            for r in conn.execute(
                "SELECT status, COUNT(*) c FROM complaints GROUP BY status"
            ).fetchall()
        }
        return {
            "total": total,
            "open": open_,
            "urgent_open": urgent,
            "by_status": by_status,
        }
