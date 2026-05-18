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
) -> dict:
    parsed = parse_complaint(raw_text)
    with get_conn() as conn:
        ticket = _next_ticket(conn)
        ack = f"{ACK_TICK} Ticket {ticket}. {parsed.acknowledgement}"
        cur = conn.execute(
            "INSERT INTO complaints (ticket_number, unit_number, category, "
            "priority, status, channel, raw_text, acknowledgement, "
            "reporter_phone, reporter_email, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
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
        row = conn.execute(
            "SELECT * FROM complaints WHERE id = ?", (cid,)
        ).fetchone()
        return _row_to_dict(row)


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
