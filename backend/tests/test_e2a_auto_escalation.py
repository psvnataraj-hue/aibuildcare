"""E2a: cron endpoint + auto-escalation job.

Endpoint auth: disabled until AIBUILDCARE_INTERNAL_JOBS_SECRET is set;
then gated by an X-Internal-Secret header (the secret a free external
cron caller is configured with).

Auto-escalation: every open complaint is evaluated against its
category's SLA escalation_levels JSON (seeded per society + category
in seed.py). Tests fast-forward `now` rather than backdating DB rows.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.db import get_conn
from app.services import escalation_service, jobs_service


def _create(client, headers, raw_text="leak in 5B"):
    r = client.post(
        "/api/v1/complaints", json={"raw_text": raw_text}, headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _seed_hierarchy_for_default_society():
    sid = 1
    escalation_service.add_hierarchy(
        sid, "manager", "Mira Manager",
        phone="+910000000001", escalation_level=1,
    )
    escalation_service.add_hierarchy(
        sid, "sr_manager", "Sam Sr",
        phone="+910000000002", escalation_level=2,
    )
    escalation_service.add_hierarchy(
        sid, "secretary", "Sita Secretary",
        phone="+910000000003", escalation_level=3,
    )
    escalation_service.add_hierarchy(
        sid, "chairman", "Chand Chair",
        phone="+910000000004", escalation_level=4,
    )


# ---- endpoint auth --------------------------------------------------
def test_tick_disabled_without_secret(client, auth_header):
    """No AIBUILDCARE_INTERNAL_JOBS_SECRET configured -> 503."""
    r = client.post("/internal/jobs/tick")
    assert r.status_code == 503


def test_tick_wrong_secret_403(client, monkeypatch):
    monkeypatch.setenv("AIBUILDCARE_INTERNAL_JOBS_SECRET", "tick-secret")
    from app.config import get_settings
    get_settings.cache_clear()
    r = client.post(
        "/internal/jobs/tick",
        headers={"X-Internal-Secret": "wrong"},
    )
    assert r.status_code == 403
    get_settings.cache_clear()


def test_tick_correct_secret_returns_summary(client, monkeypatch):
    monkeypatch.setenv("AIBUILDCARE_INTERNAL_JOBS_SECRET", "tick-secret")
    from app.config import get_settings
    get_settings.cache_clear()
    r = client.post(
        "/internal/jobs/tick",
        headers={"X-Internal-Secret": "tick-secret"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "auto_escalations" in body
    assert {"checked", "escalated", "errors"} <= set(
        body["auto_escalations"]
    )
    get_settings.cache_clear()


# ---- auto-escalation logic -----------------------------------------
def test_no_complaints_no_escalations(client):
    """Empty system tick should be a clean no-op."""
    out = jobs_service.run_due_escalations()
    assert out["checked"] == 0
    assert out["escalated"] == 0
    assert out["errors"] == []


def test_recent_complaint_not_escalated(client, auth_header):
    """A just-created complaint is well within SLA; tick is a no-op."""
    _seed_hierarchy_for_default_society()
    c = _create(client, auth_header)
    out = jobs_service.run_due_escalations()
    assert out["checked"] == 1
    assert out["escalated"] == 0


def test_old_complaint_escalates_to_level1(client, auth_header,
                                            monkeypatch):
    """Plumbing default SLA has L1 after_hours=2. Tick at +3h ->
    one escalation to manager."""
    _seed_hierarchy_for_default_society()
    sent = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.notify.send_whatsapp", sent)
    c = _create(client, auth_header, "5B nal leak")
    future = datetime.now(timezone.utc) + timedelta(hours=3)
    out = jobs_service.run_due_escalations(now=future)
    assert out["escalated"] == 1
    # complaint now has L1 timestamp set
    with get_conn() as conn:
        row = dict(conn.execute(
            "SELECT escalated_to_manager_at, escalated_to_sr_manager_at "
            "FROM complaints WHERE id = ?", (c["id"],)
        ).fetchone())
    assert row["escalated_to_manager_at"] is not None
    assert row["escalated_to_sr_manager_at"] is None
    # manager was notified
    assert any(
        "ESCALATION L1" in args[1] for args, _ in
        [(call.args, call.kwargs) for call in sent.call_args_list]
    )


def test_very_old_complaint_escalates_multiple_levels(
    client, auth_header,
):
    """At +10h, default SLA thresholds (2/4/8) are all exceeded ->
    a single tick walks through L1 -> L2 -> L3."""
    _seed_hierarchy_for_default_society()
    c = _create(client, auth_header, "5B nal leak")
    future = datetime.now(timezone.utc) + timedelta(hours=10)
    out = jobs_service.run_due_escalations(now=future)
    assert out["escalated"] == 3  # L1, L2, L3
    with get_conn() as conn:
        row = dict(conn.execute(
            "SELECT escalated_to_manager_at, escalated_to_sr_manager_at, "
            "escalated_to_secretary_at, escalated_to_chairman_at "
            "FROM complaints WHERE id = ?", (c["id"],)
        ).fetchone())
    assert row["escalated_to_manager_at"]
    assert row["escalated_to_sr_manager_at"]
    assert row["escalated_to_secretary_at"]
    assert row["escalated_to_chairman_at"] is None  # only 3 SLA levels


def test_already_max_complaint_is_a_noop(client, auth_header):
    """A complaint already at L4 (chairman) escalates 0 times, no error."""
    _seed_hierarchy_for_default_society()
    c = _create(client, auth_header)
    # ratchet to L4 via the service
    for _ in range(4):
        escalation_service.escalate(c["id"], 1)
    out = jobs_service.run_due_escalations(
        now=datetime.now(timezone.utc) + timedelta(hours=24)
    )
    assert out["escalated"] == 0
    assert out["errors"] == []


def test_missing_hierarchy_does_not_crash_tick(client, auth_header):
    """Old complaint + NO hierarchy seeded -> escalation is logged as
    skipped (not an error in the tick summary)."""
    c = _create(client, auth_header, "5B nal leak")
    out = jobs_service.run_due_escalations(
        now=datetime.now(timezone.utc) + timedelta(hours=24)
    )
    assert out["escalated"] == 0
    # Skip is logged inside _evaluate_complaint, NOT raised:
    assert out["errors"] == []


def test_urgent_priority_escalates_faster(client, auth_header,
                                           monkeypatch):
    """priority_high_multiplier=0.5 means urgent issues feel 2x older.
    L1 threshold = 2h; urgent issue at 1.5h -> NOT yet (1.5/0.5=3 > 2)."""
    _seed_hierarchy_for_default_society()
    # force urgent priority via the rule classifier ("urgent" keyword)
    c = _create(client, auth_header, "URGENT 5B nal leak")
    assert c["priority"] == "urgent"
    # +1.5h elapsed; without multiplier: 1.5 < 2 -> no escalation;
    # with multiplier 0.5: effective = 3 -> escalate L1.
    future = datetime.now(timezone.utc) + timedelta(hours=1, minutes=30)
    out = jobs_service.run_due_escalations(now=future)
    assert out["escalated"] >= 1


def test_resolved_complaint_not_evaluated(client, auth_header):
    _seed_hierarchy_for_default_society()
    c = _create(client, auth_header)
    # mark resolved
    client.post(
        f"/api/v1/complaints/{c['id']}/status",
        json={"status": "acknowledged"}, headers=auth_header,
    )
    client.post(
        f"/api/v1/complaints/{c['id']}/status",
        json={"status": "assigned"}, headers=auth_header,
    )
    client.post(
        f"/api/v1/complaints/{c['id']}/status",
        json={"status": "in_progress"}, headers=auth_header,
    )
    client.post(
        f"/api/v1/complaints/{c['id']}/status",
        json={"status": "resolved"}, headers=auth_header,
    )
    out = jobs_service.run_due_escalations(
        now=datetime.now(timezone.utc) + timedelta(hours=48)
    )
    assert out["checked"] == 0  # resolved complaints aren't open


def test_no_sla_config_no_escalation(client, auth_header):
    """Wipe the SLA row for a category; tick must not crash."""
    _seed_hierarchy_for_default_society()
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM category_sla_config WHERE category = ?",
            ("Plumbing",),
        )
    c = _create(client, auth_header, "5B nal leak")  # -> Plumbing
    out = jobs_service.run_due_escalations(
        now=datetime.now(timezone.utc) + timedelta(hours=24)
    )
    assert out["escalated"] == 0
    assert out["errors"] == []
