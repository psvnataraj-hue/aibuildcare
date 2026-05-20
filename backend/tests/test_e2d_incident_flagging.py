"""E2d: major-incident auto-flagging.

Heuristics in priority order: rapid escalation -> safety-critical
urgent -> repeat unit (>=2 in 7d) -> category surge (>=3 in 24h).
Idempotent: once flagged, never re-evaluated.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.db import get_conn
from app.security import hash_password
from app.services import escalation_service, incident_flagging
from app.services.complaint_service import _now


def _create(client, auth_header, text="leak in 5B"):
    r = client.post(
        "/api/v1/complaints", json={"raw_text": text},
        headers=auth_header,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _seed_hierarchy(society_id: int = 1):
    return escalation_service.add_hierarchy(
        society_id, "manager", "M", phone="+910000000001",
        escalation_level=1,
    )


# ---- baseline -------------------------------------------------------
def test_empty_system_noop(client):
    out = incident_flagging.run_due_incident_flagging()
    assert out["checked"] == 0
    assert out["flagged"] == 0


def test_normal_complaint_not_flagged(client, auth_header):
    _create(client, auth_header, "5B fan not working")  # Electrical/normal
    out = incident_flagging.run_due_incident_flagging()
    assert out["checked"] == 1
    assert out["flagged"] == 0


# ---- safety-critical urgent ----------------------------------------
def test_safety_category_urgent_is_flagged(client, auth_header):
    c = _create(client, auth_header, "URGENT fire extinguisher missing 1A")
    # Verify parser classified as Fire Safety + urgent
    assert c["category"] == "Fire Safety"
    assert c["priority"] == "urgent"
    out = incident_flagging.run_due_incident_flagging()
    assert out["flagged"] == 1
    with get_conn() as conn:
        row = dict(conn.execute(
            "SELECT major_incident, major_incident_reason "
            "FROM complaints WHERE id = ?", (c["id"],)
        ).fetchone())
    assert row["major_incident"] == 1
    assert "safety-critical" in row["major_incident_reason"]


def test_safety_category_normal_priority_not_flagged(client, auth_header):
    # security gate complaint, no urgent keyword -> not safety-critical
    # at urgent. But Security might match other heuristics; verify the
    # safety-urgent path specifically does NOT fire on a non-urgent.
    c = _create(client, auth_header, "security guard absent at gate")
    assert c["category"] == "Security"
    assert c["priority"] == "normal"
    out = incident_flagging.run_due_incident_flagging()
    assert out["flagged"] == 0


# ---- repeat unit ----------------------------------------------------
def test_repeat_unit_within_7_days_is_flagged(client, auth_header):
    _create(client, auth_header, "5B nal leak first time")
    c2 = _create(client, auth_header, "5B nal leaking again")
    out = incident_flagging.run_due_incident_flagging()
    # Both should be flagged (each sees the other as a repeat)
    assert out["flagged"] >= 1
    with get_conn() as conn:
        n = dict(conn.execute(
            "SELECT COUNT(*) AS c FROM complaints "
            "WHERE unit_number = '5B' AND major_incident = 1"
        ).fetchone())["c"]
    assert n >= 1


# ---- category surge ------------------------------------------------
def test_category_surge_3_in_24h_is_flagged(client, auth_header):
    # 3 plumbing complaints, different units
    _create(client, auth_header, "5B nal leak")
    _create(client, auth_header, "7C tap dripping")
    c3 = _create(client, auth_header, "9D pipe broken")
    out = incident_flagging.run_due_incident_flagging()
    # at least the third one trips category surge
    assert out["flagged"] >= 1
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT major_incident_reason FROM complaints "
            "WHERE major_incident = 1"
        ).fetchall()
    reasons = [dict(r)["major_incident_reason"] for r in rows]
    assert any("surge" in (r or "") for r in reasons)


def test_two_complaints_not_a_surge(client, auth_header):
    _create(client, auth_header, "5B nal leak")
    _create(client, auth_header, "7C tap dripping")
    out = incident_flagging.run_due_incident_flagging()
    # 2 < 3 threshold; but repeat-unit could still flag if same unit;
    # different units -> neither fires
    assert out["flagged"] == 0


# ---- rapid escalation ----------------------------------------------
def test_rapid_escalation_to_chairman_is_flagged(client, auth_header):
    # set up the full escalation chain
    sid = 1
    escalation_service.add_hierarchy(
        sid, "manager", "M", phone="+910000000001",
        escalation_level=1,
    )
    escalation_service.add_hierarchy(
        sid, "sr_manager", "SM", phone="+910000000002",
        escalation_level=2,
    )
    escalation_service.add_hierarchy(
        sid, "secretary", "S", phone="+910000000003",
        escalation_level=3,
    )
    escalation_service.add_hierarchy(
        sid, "chairman", "C", phone="+910000000004",
        escalation_level=4,
    )
    c = _create(client, auth_header, "AC kharab")
    # ratchet through L1-L4 within seconds
    for _ in range(4):
        escalation_service.escalate(c["id"], sid)
    out = incident_flagging.run_due_incident_flagging()
    assert out["flagged"] == 1
    with get_conn() as conn:
        reason = dict(conn.execute(
            "SELECT major_incident_reason FROM complaints "
            "WHERE id = ?", (c["id"],)
        ).fetchone())["major_incident_reason"]
    assert "rapid escalation" in reason


# ---- idempotency ----------------------------------------------------
def test_idempotent_already_flagged_complaint_skipped(client, auth_header):
    _create(client, auth_header, "URGENT fire extinguisher missing")
    incident_flagging.run_due_incident_flagging()
    # second run finds 0 to check (the flagged row is excluded)
    out2 = incident_flagging.run_due_incident_flagging()
    assert out2["checked"] == 0
    assert out2["flagged"] == 0


# ---- notification ---------------------------------------------------
def test_notifies_committee_via_whatsapp_on_flag(
    client, auth_header, monkeypatch,
):
    _seed_hierarchy()  # adds a manager with phone
    sent = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.notify.send_whatsapp", sent)
    c = _create(client, auth_header, "URGENT fire alarm broken in lobby")
    incident_flagging.run_due_incident_flagging()
    assert sent.called
    phone, body = sent.call_args[0]
    assert "MAJOR INCIDENT" in body
    assert c["ticket_number"] in body


def test_no_hierarchy_still_flags_without_notify(
    client, auth_header, monkeypatch,
):
    sent = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.notify.send_whatsapp", sent)
    c = _create(client, auth_header, "URGENT fire extinguisher missing")
    out = incident_flagging.run_due_incident_flagging()
    assert out["flagged"] == 1
    # no hierarchy -> no WhatsApp recipients
    assert not sent.called
    # but the complaint IS flagged
    with get_conn() as conn:
        mi = dict(conn.execute(
            "SELECT major_incident FROM complaints WHERE id = ?",
            (c["id"],),
        ).fetchone())["major_incident"]
    assert mi == 1


# ---- tick integration -----------------------------------------------
def test_tick_includes_incident_flagging_key(client):
    from app.services import jobs_service

    summary = jobs_service.run_tick()
    assert "incident_flagging" in summary
    assert "checked" in summary["incident_flagging"]
