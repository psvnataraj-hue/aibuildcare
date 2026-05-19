from datetime import datetime, timezone

from ..db import get_conn
from .haiku_parser import parse_complaint

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


def _row_to_dict(row) -> dict | None:
    return dict(row) if row else None


def create_complaint(
    raw_text: str,
    channel: str = "dashboard",
    reporter_phone: str | None = None,
    reporter_email: str | None = None,
    image_urls: list[str] | None = None,
) -> dict:
    parsed = parse_complaint(raw_text, image_urls)
    media = ",".join(image_urls) if image_urls else None
    with get_conn() as conn:
        ticket = _next_ticket(conn)
        ack = f"{ACK_TICK} Ticket {ticket}. {parsed.acknowledgement}"
        cur = conn.execute(
            "INSERT INTO complaints (ticket_number, unit_number, category, "
            "priority, status, channel, raw_text, acknowledgement, "
            "reporter_phone, reporter_email, media_urls, detected_language, "
            "created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ticket,
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
            conn.execute(
                "UPDATE complaints SET contractor_id = ?, "
                "status = 'assigned', updated_at = ? WHERE id = ?",
                (con["id"], _now(), cid),
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
) -> list[dict]:
    sort_col = (
        sort if sort in {"created_at", "priority", "status"} else "created_at"
    )
    sql = "SELECT * FROM complaints"
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if q:
        clauses.append(
            "(raw_text LIKE ? OR ticket_number LIKE ? OR unit_number LIKE ?)"
        )
        params += [f"%{q}%"] * 3
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += f" ORDER BY {sort_col} DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_complaint(cid: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM complaints WHERE id = ?", (cid,)
        ).fetchone()
        if not row:
            raise ComplaintError("complaint not found")
        return dict(row)


def assign_contractor(cid: int, contractor_id: int) -> dict:
    with get_conn() as conn:
        c = conn.execute(
            "SELECT id FROM contractors WHERE id = ? AND is_active = 1",
            (contractor_id,),
        ).fetchone()
        if not c:
            raise ComplaintError("contractor not found")
        cur = conn.execute(
            "UPDATE complaints SET contractor_id = ?, status = 'assigned', "
            "updated_at = ? WHERE id = ?",
            (contractor_id, _now(), cid),
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
        return dict(row)


def update_status(cid: int, new_status: str) -> dict:
    if new_status not in STATUS_FLOW:
        raise ComplaintError(f"invalid status: {new_status}")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM complaints WHERE id = ?", (cid,)
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
        return dict(out)


def add_message(cid: int, sender: str, body: str) -> dict:
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM complaints WHERE id = ?", (cid,)
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


def list_messages(cid: int) -> list[dict]:
    with get_conn() as conn:
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


def rate_complaint(cid: int, rating: int, feedback: str | None) -> dict:
    if rating < 1 or rating > 5:
        raise ComplaintError("rating must be 1-5")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM complaints WHERE id = ?", (cid,)
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


def get_rating(cid: int) -> dict | None:
    with get_conn() as conn:
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
