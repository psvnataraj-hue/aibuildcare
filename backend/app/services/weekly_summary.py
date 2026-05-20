"""E2c: weekly HTML committee summary.

Runs on every cron tick; sends only when:
  (a) today is Sunday (UTC), and
  (b) no row exists in `weekly_summaries_sent` for
      (society_id, this_week_start) — i.e., we haven't sent yet.

The PRIMARY KEY (society_id, week_start_date) makes it impossible
to send twice for the same week even under cron races / retries.

Recipients = active users in the society whose role is one of
chairman / committee_member / secretary / sr_manager / manager
AND has an email; falls back to escalation_hierarchy.email.

Content is plain HTML (no PDF / Chart.js per the locked design;
SendGrid HTML body); cheap to render server-side on the free tier.
"""
from __future__ import annotations

import html
import logging
from datetime import date, datetime, timedelta, timezone

from ..db import get_conn
from .complaint_service import _now

log = logging.getLogger("aibuildcare.weekly")


def _week_window(now: datetime) -> tuple[date, date]:
    """Return (monday, sunday) of `now`'s ISO week (UTC)."""
    today = now.date()
    monday = today - timedelta(days=today.weekday())  # weekday 0=Mon
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _is_sunday(now: datetime) -> bool:
    return now.weekday() == 6


def _has_been_sent(conn, society_id: int, week_start: date) -> bool:
    r = conn.execute(
        "SELECT 1 FROM weekly_summaries_sent "
        "WHERE society_id = ? AND week_start_date = ?",
        (society_id, week_start.isoformat()),
    ).fetchone()
    return r is not None


def _mark_sent(
    conn, society_id: int, week_start: date, recipient_count: int
) -> None:
    conn.execute(
        "INSERT INTO weekly_summaries_sent "
        "(society_id, week_start_date, sent_at, recipient_count) "
        "VALUES (?,?,?,?)",
        (society_id, week_start.isoformat(), _now(), recipient_count),
    )


def _recipients(conn, society_id: int) -> list[str]:
    """Active users in this society with leader/committee roles + an
    email. Falls back to escalation_hierarchy emails if no users."""
    roles = ("chairman", "committee_member", "secretary",
             "sr_manager", "manager")
    ph = ",".join("?" * len(roles))
    rows = conn.execute(
        f"SELECT email FROM users WHERE society_id = ? "
        f"AND is_active = 1 AND role IN ({ph}) "
        f"AND email IS NOT NULL AND email != ''",
        (society_id, *roles),
    ).fetchall()
    emails = [dict(r)["email"] for r in rows]
    if emails:
        return emails
    rows = conn.execute(
        "SELECT email FROM escalation_hierarchy "
        "WHERE society_id = ? AND active = 1 "
        "AND email IS NOT NULL AND email != ''",
        (society_id,),
    ).fetchall()
    return [dict(r)["email"] for r in rows]


def _compute_stats(
    conn, society_id: int, start: date, end: date
) -> dict:
    """Compact statistics dict for the (start..end) window inclusive."""
    s = f"{start.isoformat()}T00:00:00+00:00"
    e = f"{end.isoformat()}T23:59:59+00:00"

    total = dict(conn.execute(
        "SELECT COUNT(*) AS c FROM complaints "
        "WHERE society_id = ? AND created_at BETWEEN ? AND ?",
        (society_id, s, e),
    ).fetchone())["c"]

    resolved = dict(conn.execute(
        "SELECT COUNT(*) AS c FROM complaints "
        "WHERE society_id = ? AND status IN ('resolved','closed') "
        "AND COALESCE(resolved_at, updated_at) BETWEEN ? AND ?",
        (society_id, s, e),
    ).fetchone())["c"]

    open_now = dict(conn.execute(
        "SELECT COUNT(*) AS c FROM complaints "
        "WHERE society_id = ? AND status IN "
        "('received','acknowledged','assigned','in_progress')",
        (society_id,),
    ).fetchone())["c"]

    overdue = dict(conn.execute(
        "SELECT COUNT(*) AS c FROM complaints "
        "WHERE society_id = ? "
        "AND status NOT IN ('resolved','closed') "
        "AND estimated_completion_date IS NOT NULL "
        "AND estimated_completion_date < ?",
        (society_id, _now()),
    ).fetchone())["c"]

    by_cat = [
        dict(r) for r in conn.execute(
            "SELECT category, COUNT(*) AS n FROM complaints "
            "WHERE society_id = ? AND created_at BETWEEN ? AND ? "
            "GROUP BY category ORDER BY n DESC",
            (society_id, s, e),
        ).fetchall()
    ]

    avg_rating_row = conn.execute(
        "SELECT AVG(r.rating) AS avg_r, COUNT(*) AS n "
        "FROM complaint_ratings r "
        "JOIN complaints c ON c.id = r.complaint_id "
        "WHERE c.society_id = ? AND r.created_at BETWEEN ? AND ?",
        (society_id, s, e),
    ).fetchone()
    avg_rating = dict(avg_rating_row)["avg_r"] if avg_rating_row else None
    rating_n = dict(avg_rating_row)["n"] if avg_rating_row else 0

    escalations = dict(conn.execute(
        "SELECT "
        " SUM(CASE WHEN escalated_to_manager_at IS NOT NULL "
        "          THEN 1 ELSE 0 END) AS l1, "
        " SUM(CASE WHEN escalated_to_sr_manager_at IS NOT NULL "
        "          THEN 1 ELSE 0 END) AS l2, "
        " SUM(CASE WHEN escalated_to_secretary_at IS NOT NULL "
        "          THEN 1 ELSE 0 END) AS l3, "
        " SUM(CASE WHEN escalated_to_chairman_at IS NOT NULL "
        "          THEN 1 ELSE 0 END) AS l4 "
        "FROM complaints WHERE society_id = ? "
        "AND created_at BETWEEN ? AND ?",
        (society_id, s, e),
    ).fetchone() or {})
    escalations = {k: int(v or 0) for k, v in escalations.items()}

    return {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "total_complaints": total,
        "resolved_this_week": resolved,
        "open_now": open_now,
        "overdue": overdue,
        "by_category": by_cat,
        "avg_rating": (
            round(float(avg_rating), 2) if avg_rating is not None else None
        ),
        "rating_count": rating_n,
        "escalations": escalations,
    }


def _h(s: object) -> str:
    return html.escape(str(s if s is not None else ""))


def _render_html(society_name: str, stats: dict) -> str:
    cat_rows = "".join(
        f"<tr><td>{_h(r['category'] or 'Uncategorized')}</td>"
        f"<td style='text-align:right'>{_h(r['n'])}</td></tr>"
        for r in stats["by_category"]
    ) or (
        "<tr><td colspan='2' style='color:#888'>"
        "No complaints this week.</td></tr>"
    )
    rating = (
        f"{stats['avg_rating']} / 5 ({stats['rating_count']} reviews)"
        if stats["avg_rating"] is not None else "—"
    )
    esc = stats["escalations"]
    return f"""\
<!doctype html><html><body style="font-family:Arial,sans-serif;
color:#222;max-width:640px;margin:auto">
<h2 style="color:#1a73e8">Weekly summary — {_h(society_name)}</h2>
<p style="color:#555">Week of {_h(stats['week_start'])} — \
{_h(stats['week_end'])} (UTC)</p>

<table cellpadding="8" style="border-collapse:collapse;width:100%;
background:#f7f8fa;border-radius:8px">
<tr><td><b>New complaints</b></td><td style='text-align:right'>\
{_h(stats['total_complaints'])}</td></tr>
<tr><td><b>Resolved this week</b></td><td style='text-align:right'>\
{_h(stats['resolved_this_week'])}</td></tr>
<tr><td><b>Currently open</b></td><td style='text-align:right'>\
{_h(stats['open_now'])}</td></tr>
<tr><td><b>Overdue</b></td><td style='text-align:right;color:#c00'>\
{_h(stats['overdue'])}</td></tr>
<tr><td><b>Avg resident rating</b></td><td style='text-align:right'>\
{_h(rating)}</td></tr>
<tr><td><b>Escalations this week</b></td><td style='text-align:right'>\
L1: {_h(esc.get('l1', 0))} · L2: {_h(esc.get('l2', 0))} · \
L3: {_h(esc.get('l3', 0))} · L4: {_h(esc.get('l4', 0))}</td></tr>
</table>

<h3 style="margin-top:24px">Complaints by category</h3>
<table cellpadding="6" style="border-collapse:collapse;width:100%;
border:1px solid #eee">
<thead><tr style="background:#eef"><th style='text-align:left'>Category\
</th><th>Count</th></tr></thead><tbody>{cat_rows}</tbody></table>

<p style="color:#888;font-size:12px;margin-top:24px">
This summary was generated automatically. Reply to your society admin
for follow-up.</p>
</body></html>"""


# ---- job entry point -------------------------------------------------
def run_due_weekly_summaries(now: datetime | None = None) -> dict:
    """Once per Sunday (UTC) per society, email the committee an
    HTML summary of the current ISO week."""
    now = now or datetime.now(timezone.utc)
    out: dict = {"checked": 0, "sent": 0, "skipped": 0, "errors": []}
    if not _is_sunday(now):
        out["skipped"] = -1  # not a sending day
        return out
    week_start, week_end = _week_window(now)
    with get_conn() as conn:
        societies = [dict(r) for r in conn.execute(
            "SELECT id, name FROM societies"
        ).fetchall()]
    for soc in societies:
        sid, sname = soc["id"], soc["name"]
        out["checked"] += 1
        try:
            with get_conn() as conn:
                if _has_been_sent(conn, sid, week_start):
                    out["skipped"] += 1
                    continue
                emails = _recipients(conn, sid)
            if not emails:
                # nothing to send -- still mark as sent so we don't
                # re-check every tick this week
                with get_conn() as conn:
                    _mark_sent(conn, sid, week_start, 0)
                out["skipped"] += 1
                continue
            with get_conn() as conn:
                stats = _compute_stats(conn, sid, week_start, week_end)
            html_body = _render_html(sname, stats)
            from .notify import send_email

            subject = (
                f"AIBuildCare weekly summary — {sname} "
                f"({stats['week_start']} → {stats['week_end']})"
            )
            sent_count = 0
            for em in emails:
                if send_email(em, subject, html_body):
                    sent_count += 1
            with get_conn() as conn:
                _mark_sent(conn, sid, week_start, sent_count)
            out["sent"] += sent_count
        except Exception as exc:
            log.warning(
                "weekly summary error sid=%s: %s", sid, exc
            )
            out["errors"].append(
                {"society_id": sid, "error": str(exc)}
            )
    return out
