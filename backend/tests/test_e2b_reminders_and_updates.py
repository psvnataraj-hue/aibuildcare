"""E2b: staff reminders + complainant-update jobs.

Same cron tick (POST /internal/jobs/tick) drives both. Throttled per
complaint via DB timestamps (last_reminder_sent_at,
last_complainant_update_at) so cron frequency doesn't equal user
notification frequency.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.db import get_conn
from app.security import hash_password
from app.services import jobs_service

PW = "Secret!123"


def _seed_staff(name, category="Plumbing", phone="+919000000111",
                wa=1, society_id=1):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO staff_members (society_id, name, phone_primary, "
            "whatsapp_enabled, active) VALUES (?,?,?,?,1)",
            (society_id, name, phone, wa),
        )
        sid = dict(conn.execute(
            "SELECT id FROM staff_members ORDER BY id DESC LIMIT 1"
        ).fetchone())["id"]
        conn.execute(
            "INSERT INTO staff_categories (staff_id, category, "
            "primary_category, skill_level) VALUES (?,?,1,'senior')",
            (sid, category),
        )
    return sid


def _create(client, auth_header, text="leak in 5B",
            reporter_phone="+910000000099"):
    r = client.post(
        "/api/v1/complaints",
        json={"raw_text": text, "reporter_phone": reporter_phone},
        headers=auth_header,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _assign_to_staff(cid: int, staff_id: int, status: str = "assigned"):
    """Direct DB write so we don't depend on a manual-assign-staff
    endpoint (which doesn't exist yet in E1)."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE complaints SET assigned_staff_id = ?, status = ? "
            "WHERE id = ?",
            (staff_id, status, cid),
        )


# ---- staff reminders ------------------------------------------------
def test_no_assignments_no_reminders(client):
    out = jobs_service.run_due_staff_reminders()
    assert out == {"checked": 0, "reminded": 0, "errors": []}


def test_recent_assignment_not_reminded(client, auth_header):
    staff = _seed_staff("Ravi")
    c = _create(client, auth_header)
    _assign_to_staff(c["id"], staff)
    out = jobs_service.run_due_staff_reminders()
    assert out["checked"] == 1
    assert out["reminded"] == 0


def test_old_assigned_complaint_reminds_staff(client, auth_header,
                                               monkeypatch):
    sent = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.notify.send_whatsapp", sent)
    staff = _seed_staff("Ravi", phone="+919000000111")
    c = _create(client, auth_header)
    _assign_to_staff(c["id"], staff)
    future = datetime.now(timezone.utc) + timedelta(hours=3)
    out = jobs_service.run_due_staff_reminders(now=future)
    assert out["reminded"] == 1
    # WhatsApp sent to staff
    phone, msg = sent.call_args[0]
    assert phone == "+919000000111"
    assert "REMINDER" in msg
    assert c["ticket_number"] in msg
    # counter incremented + throttle stamp set
    with get_conn() as conn:
        row = dict(conn.execute(
            "SELECT reminder_sent_count, last_reminder_sent_at "
            "FROM complaints WHERE id = ?", (c["id"],)
        ).fetchone())
    assert row["reminder_sent_count"] == 1
    assert row["last_reminder_sent_at"] is not None


def test_in_progress_complaint_not_reminded(client, auth_header):
    """Spec: staff already working on it shouldn't get a 'pending' nag."""
    staff = _seed_staff("Ravi")
    c = _create(client, auth_header)
    _assign_to_staff(c["id"], staff, status="in_progress")
    out = jobs_service.run_due_staff_reminders(
        now=datetime.now(timezone.utc) + timedelta(hours=10)
    )
    assert out["checked"] == 0


def test_resolved_complaint_not_reminded(client, auth_header):
    staff = _seed_staff("Ravi")
    c = _create(client, auth_header)
    _assign_to_staff(c["id"], staff, status="resolved")
    out = jobs_service.run_due_staff_reminders(
        now=datetime.now(timezone.utc) + timedelta(hours=10)
    )
    assert out["checked"] == 0


def test_wa_disabled_staff_gets_no_notify_but_counter_still_ticks(
    client, auth_header, monkeypatch,
):
    sent = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.notify.send_whatsapp", sent)
    staff = _seed_staff("Silent", wa=0)
    c = _create(client, auth_header)
    _assign_to_staff(c["id"], staff)
    out = jobs_service.run_due_staff_reminders(
        now=datetime.now(timezone.utc) + timedelta(hours=3)
    )
    # The job still 'reminded' (state update happened), but no msg
    assert out["reminded"] == 1
    assert not sent.called


def test_reminder_throttle_within_2h(client, auth_header):
    """After one reminder lands, the next eval within 2h is a no-op."""
    staff = _seed_staff("Ravi")
    c = _create(client, auth_header)
    _assign_to_staff(c["id"], staff)
    # first tick: +3h -> reminded
    jobs_service.run_due_staff_reminders(
        now=datetime.now(timezone.utc) + timedelta(hours=3),
    )
    # second tick: +30 min later (last_reminder_sent_at just set)
    out = jobs_service.run_due_staff_reminders(
        now=datetime.now(timezone.utc) + timedelta(hours=3, minutes=30)
    )
    assert out["reminded"] == 0


# ---- complainant updates --------------------------------------------
def test_recent_complaint_no_complainant_update(client, auth_header):
    _create(client, auth_header)
    out = jobs_service.run_due_complainant_updates()
    assert out["checked"] == 1
    assert out["updated"] == 0


def test_old_complaint_sends_complainant_update(client, auth_header,
                                                 monkeypatch):
    sent = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.notify.send_whatsapp", sent)
    c = _create(
        client, auth_header, reporter_phone="+919833129064"
    )
    future = datetime.now(timezone.utc) + timedelta(hours=5)
    out = jobs_service.run_due_complainant_updates(now=future)
    assert out["updated"] == 1
    phone, msg = sent.call_args[0]
    assert phone == "+919833129064"
    assert c["ticket_number"] in msg
    with get_conn() as conn:
        ts = dict(conn.execute(
            "SELECT last_complainant_update_at FROM complaints "
            "WHERE id = ?", (c["id"],)
        ).fetchone())["last_complainant_update_at"]
    assert ts is not None


def test_complaint_without_phone_skipped(client, auth_header):
    # create via API; we'll null the phone via DB
    c = _create(client, auth_header)
    with get_conn() as conn:
        conn.execute(
            "UPDATE complaints SET reporter_phone = NULL WHERE id = ?",
            (c["id"],),
        )
    out = jobs_service.run_due_complainant_updates(
        now=datetime.now(timezone.utc) + timedelta(hours=10)
    )
    assert out["checked"] == 0  # excluded by the SQL WHERE


def test_complainant_update_throttled_within_4h(client, auth_header):
    c = _create(client, auth_header)
    jobs_service.run_due_complainant_updates(
        now=datetime.now(timezone.utc) + timedelta(hours=5)
    )
    # second tick 1h later -> throttled
    out = jobs_service.run_due_complainant_updates(
        now=datetime.now(timezone.utc) + timedelta(hours=6)
    )
    assert out["updated"] == 0


def test_resolved_complaint_no_complainant_update(client, auth_header):
    c = _create(client, auth_header)
    with get_conn() as conn:
        conn.execute(
            "UPDATE complaints SET status = 'resolved' WHERE id = ?",
            (c["id"],),
        )
    out = jobs_service.run_due_complainant_updates(
        now=datetime.now(timezone.utc) + timedelta(hours=10)
    )
    assert out["checked"] == 0


# ---- tick combines all three ----------------------------------------
def test_tick_returns_all_three_job_summaries(client):
    summary = jobs_service.run_tick()
    assert {"auto_escalations", "staff_reminders",
            "complainant_updates"} == set(summary)
    for k in summary:
        assert "checked" in summary[k]
