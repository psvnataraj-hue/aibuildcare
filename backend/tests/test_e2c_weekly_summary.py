"""E2c: weekly HTML committee summary.

Gated by (a) today == Sunday (UTC), (b) no prior row in
weekly_summaries_sent for (society_id, this_week_start).
"""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.db import get_conn
from app.services import weekly_summary
from app.services.complaint_service import _now


# Known reference points (today is 2026-05-20, a Wednesday).
SUNDAY = datetime(2026, 5, 24, 21, 0, tzinfo=timezone.utc)
NOT_SUNDAY = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)


# ---- helpers --------------------------------------------------------
def test_week_window_for_sunday():
    mon, sun = weekly_summary._week_window(SUNDAY)
    assert mon == date(2026, 5, 18)
    assert sun == date(2026, 5, 24)


def test_week_window_for_midweek():
    mon, sun = weekly_summary._week_window(NOT_SUNDAY)
    assert mon == date(2026, 5, 18)
    assert sun == date(2026, 5, 24)


def test_is_sunday():
    assert weekly_summary._is_sunday(SUNDAY)
    assert not weekly_summary._is_sunday(NOT_SUNDAY)


# ---- render ---------------------------------------------------------
def test_render_html_handles_empty_stats():
    stats = {
        "week_start": "2026-05-18", "week_end": "2026-05-24",
        "total_complaints": 0, "resolved_this_week": 0,
        "open_now": 0, "overdue": 0, "by_category": [],
        "avg_rating": None, "rating_count": 0,
        "escalations": {"l1": 0, "l2": 0, "l3": 0, "l4": 0},
    }
    h = weekly_summary._render_html("Palms Residency", stats)
    assert "Weekly summary" in h
    assert "Palms Residency" in h
    assert "No complaints this week" in h


def test_render_html_escapes_user_supplied_society_name():
    stats = {
        "week_start": "x", "week_end": "y",
        "total_complaints": 0, "resolved_this_week": 0,
        "open_now": 0, "overdue": 0, "by_category": [],
        "avg_rating": None, "rating_count": 0,
        "escalations": {"l1": 0, "l2": 0, "l3": 0, "l4": 0},
    }
    h = weekly_summary._render_html("<script>x</script>", stats)
    assert "<script>x</script>" not in h
    assert "&lt;script&gt;" in h


# ---- compute_stats --------------------------------------------------
def test_compute_stats_counts_this_weeks_complaints(client, auth_header):
    # create + resolve one complaint
    r = client.post(
        "/api/v1/complaints", json={"raw_text": "5B nal leak"},
        headers=auth_header,
    )
    cid = r.json()["id"]
    with get_conn() as conn:
        conn.execute(
            "UPDATE complaints SET status = 'resolved', "
            "resolved_at = ? WHERE id = ?",
            (_now(), cid),
        )
    today = date.today()
    mon = today - timedelta(days=today.weekday())
    sun = mon + timedelta(days=6)
    with get_conn() as conn:
        stats = weekly_summary._compute_stats(conn, 1, mon, sun)
    assert stats["total_complaints"] >= 1
    assert stats["resolved_this_week"] >= 1
    assert isinstance(stats["by_category"], list)


# ---- job behaviour --------------------------------------------------
def test_skipped_on_non_sunday(client):
    out = weekly_summary.run_due_weekly_summaries(now=NOT_SUNDAY)
    assert out["sent"] == 0
    assert out["checked"] == 0


def test_no_recipients_marks_sent_to_avoid_retick(client, monkeypatch):
    """The default seed admin's role='admin' is NOT in the recipient
    list -> 0 emails sent. But we still record the row so the next
    tick this week is a no-op."""
    sends = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.notify.send_email", sends)

    out = weekly_summary.run_due_weekly_summaries(now=SUNDAY)
    assert out["sent"] == 0
    assert out["skipped"] >= 1
    assert not sends.called
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM weekly_summaries_sent"
        ).fetchall()
    assert len(rows) >= 1


def test_sends_to_committee_users(client, monkeypatch):
    """Promote the seed admin to chairman with an email."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET role = 'chairman', "
            "email = 'chair@example.com' WHERE society_id = 1"
        )
    sends = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.notify.send_email", sends)

    out = weekly_summary.run_due_weekly_summaries(now=SUNDAY)
    assert out["sent"] == 1
    to, subject, body = sends.call_args[0]
    assert to == "chair@example.com"
    assert "Weekly summary" in body
    assert "Palms Residency" in body
    assert "weekly summary" in subject.lower()


def test_idempotent_within_the_same_week(client, monkeypatch):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET role = 'chairman', "
            "email = 'c@x.com' WHERE society_id = 1"
        )
    sends = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.notify.send_email", sends)

    weekly_summary.run_due_weekly_summaries(now=SUNDAY)
    # second tick later the same Sunday -> already sent, no-op
    weekly_summary.run_due_weekly_summaries(
        now=SUNDAY + timedelta(minutes=30)
    )
    assert sends.call_count == 1


def test_falls_back_to_hierarchy_emails(client, monkeypatch):
    """No leader-role users; but escalation_hierarchy has emails."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO escalation_hierarchy "
            "(society_id, role_name, person_name, phone, "
            "whatsapp_enabled, email, escalation_level, active) "
            "VALUES (1,'chairman','Chair Chair','+910',1,"
            "'fallback@x.com',4,1)"
        )
    sends = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.notify.send_email", sends)

    out = weekly_summary.run_due_weekly_summaries(now=SUNDAY)
    assert out["sent"] == 1
    assert sends.call_args[0][0] == "fallback@x.com"


# ---- tick integration -----------------------------------------------
def test_tick_includes_weekly_summary_key():
    from app.services import jobs_service

    summary = jobs_service.run_tick()
    assert "weekly_summaries" in summary
