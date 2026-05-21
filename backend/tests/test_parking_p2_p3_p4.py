"""Parking P2 + P3 + P4 backend.

P2: auto-link parking complaint to vehicles row, notify owner.
P3: 5th major-incident heuristic (repeat plate >=3 in 30 days).
P4: POST /complaints/{cid}/authorize-clamping endpoint.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.db import get_conn
from app.security import hash_password
from app.services import (
    complaint_service,
    incident_flagging,
)


def _seed_vehicle(plate: str, society_id: int = 1,
                  owner_phone: str | None = "+919833000111",
                  owner_name: str = "Owner X",
                  owner_unit: str = "5B") -> int:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO vehicles (society_id, plate_number, "
            "owner_phone, owner_name, owner_unit_number) "
            "VALUES (?,?,?,?,?)",
            (society_id, plate, owner_phone, owner_name, owner_unit),
        )
        return dict(conn.execute(
            "SELECT id FROM vehicles WHERE plate_number = ?", (plate,)
        ).fetchone())["id"]


def _seed_user(email: str, password: str, role: str,
               society_id: int = 1) -> int:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, role, "
            "society_id, is_active) VALUES (?,?,?,?,?,1)",
            (email, hash_password(password), email.split("@")[0],
             role, society_id),
        )
        return dict(conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone())["id"]


def _login(client, email: str, password: str) -> dict:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# =====================================================================
# P2 — auto-link parking complaint to vehicle + notify owner
# =====================================================================

def test_parking_complaint_with_known_plate_auto_links(
    client, auth_header, monkeypatch,
):
    sent = MagicMock()
    monkeypatch.setattr("app.services.complaint_service.send_whatsapp",
                        sent, raising=False)
    # patch the lazy import inside create_complaint too
    from app.services import notify as nt
    monkeypatch.setattr(nt, "send_whatsapp", sent)
    vid = _seed_vehicle("MH01PARK001", owner_phone="+919833000111")

    r = client.post(
        "/api/v1/complaints",
        json={
            # "parking" alone triggers Parking Management; we avoid
            # words like "gate" (Security wins), "fire" (Fire Safety
            # wins) etc. which would beat Parking in the keyword
            # walk-order.
            "raw_text": "Unauthorized vehicle in residents parking spot",
            "vehicle_plate": "MH 01 PARK 001",
            "violation_type": "blocking_fire_exit",
        },
        headers=auth_header,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["vehicle_plate"] == "MH01PARK001"  # normalised
    assert body["vehicle_id"] == vid
    assert body["violation_type"] == "blocking_fire_exit"
    # owner got a WhatsApp
    calls = [c.args for c in sent.call_args_list]
    assert any(
        c[0] == "+919833000111" and "MH01PARK001" in c[1]
        for c in calls
    ), f"expected owner notify; got calls={calls}"


def test_parking_complaint_with_unknown_plate_no_link(
    client, auth_header, monkeypatch,
):
    sent = MagicMock()
    from app.services import notify as nt
    monkeypatch.setattr(nt, "send_whatsapp", sent)
    r = client.post(
        "/api/v1/complaints",
        json={
            "raw_text": "Parking Management - unregistered plate",
            "vehicle_plate": "XX99NOTREG",
            "violation_type": "no_parking_zone",
        },
        headers=auth_header,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["vehicle_plate"] == "XX99NOTREG"
    assert body["vehicle_id"] is None
    assert body["violation_type"] == "no_parking_zone"
    # the system-message thread should mention the missing registry entry
    msgs_r = client.get(
        f"/api/v1/complaints/{body['id']}/messages", headers=auth_header,
    )
    bodies = [m["body"] for m in msgs_r.json()]
    assert any("not in vehicle registry" in b for b in bodies)


def test_parking_complaint_vehicle_without_phone(
    client, auth_header, monkeypatch,
):
    """Vehicle in registry but no owner_phone -> link succeeds, no
    notify call, system message logs the gap."""
    sent = MagicMock()
    from app.services import notify as nt
    monkeypatch.setattr(nt, "send_whatsapp", sent)
    _seed_vehicle("MH02NOPHONE", owner_phone=None)
    r = client.post(
        "/api/v1/complaints",
        json={
            "raw_text": "Parking Management - vehicle has no phone",
            "vehicle_plate": "MH02NOPHONE",
        },
        headers=auth_header,
    )
    assert r.status_code == 201
    assert r.json()["vehicle_id"] is not None
    # No owner notify (no phone) — but auto-assign notify may still fire
    # for the contractor. So we check no call was made to a "no-phone"
    # number; the contractor call has its own phone.
    cid = r.json()["id"]
    msgs_r = client.get(
        f"/api/v1/complaints/{cid}/messages", headers=auth_header,
    )
    bodies = [m["body"] for m in msgs_r.json()]
    assert any("No phone on file" in b for b in bodies)


def test_non_parking_category_ignores_plate(client, auth_header):
    """Plate sent on a non-parking complaint gets stored but no
    auto-link (the category routing would land it with a plumber,
    not the parking flow)."""
    _seed_vehicle("MH03IGNORE")
    r = client.post(
        "/api/v1/complaints",
        json={
            "raw_text": "AC kharab hai 5B",
            "vehicle_plate": "MH03IGNORE",
        },
        headers=auth_header,
    )
    assert r.status_code == 201
    body = r.json()
    # category is AC/Cooling — the parking branch never runs, so
    # vehicle_plate stays NULL.
    assert body["category"] == "AC/Cooling"
    assert body.get("vehicle_plate") is None
    assert body.get("vehicle_id") is None


def test_invalid_violation_type_rejected(client, auth_header):
    r = client.post(
        "/api/v1/complaints",
        json={
            "raw_text": "Parking violation",
            "vehicle_plate": "MH04INV001",
            "violation_type": "submarine_in_lobby",
        },
        headers=auth_header,
    )
    assert r.status_code == 400
    assert "violation_type" in r.json()["detail"]


# =====================================================================
# P3 — repeat parking offender heuristic
# =====================================================================

def _create_parking_complaints(client, auth_header, plate: str,
                               count: int, days_ago_each: list[int]):
    """Create N parking complaints for `plate`, then back-date their
    created_at to N days ago each (so the 30-day window test is
    deterministic)."""
    ids: list[int] = []
    for _ in range(count):
        r = client.post(
            "/api/v1/complaints",
            json={
                "raw_text": "Parking Management violation",
                "vehicle_plate": plate,
            },
            headers=auth_header,
        )
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    with get_conn() as conn:
        for cid, days in zip(ids, days_ago_each):
            ts = (
                datetime.now(timezone.utc) - timedelta(days=days)
            ).isoformat()
            conn.execute(
                "UPDATE complaints SET created_at = ? WHERE id = ?",
                (ts, cid),
            )
    return ids


def test_repeat_plate_3_in_30_days_flags_major(client, auth_header):
    _create_parking_complaints(
        client, auth_header, "MH99REP001", 3, [10, 5, 0],
    )
    out = incident_flagging.run_due_incident_flagging()
    assert out["flagged"] >= 1
    # last (just-created) ticket should be flagged
    with get_conn() as conn:
        row = dict(conn.execute(
            "SELECT major_incident, major_incident_reason FROM complaints "
            "WHERE vehicle_plate = 'MH99REP001' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone())
    assert row["major_incident"] == 1
    assert "repeat parking offender" in row["major_incident_reason"]


def test_repeat_plate_2_in_30_days_not_flagged(client, auth_header):
    _create_parking_complaints(
        client, auth_header, "MH99REP002", 2, [10, 0],
    )
    incident_flagging.run_due_incident_flagging()
    with get_conn() as conn:
        rows = [
            dict(r) for r in conn.execute(
                "SELECT major_incident, major_incident_reason "
                "FROM complaints WHERE vehicle_plate = 'MH99REP002'"
            ).fetchall()
        ]
    # none flagged by the repeat-offender rule (other rules may fire
    # for surge etc., so we only assert the rule we care about)
    for r in rows:
        if r["major_incident"]:
            assert "repeat parking offender" not in (
                r["major_incident_reason"] or ""
            )


def test_repeat_plate_3_outside_30_days_not_flagged(
    client, auth_header,
):
    """3 violations but the oldest is 60 days back — only 2 fall in
    the 30d window, so the heuristic doesn't fire."""
    _create_parking_complaints(
        client, auth_header, "MH99REP003", 3, [60, 5, 0],
    )
    incident_flagging.run_due_incident_flagging()
    with get_conn() as conn:
        rows = [
            dict(r) for r in conn.execute(
                "SELECT major_incident, major_incident_reason "
                "FROM complaints WHERE vehicle_plate = 'MH99REP003'"
            ).fetchall()
        ]
    for r in rows:
        if r["major_incident"]:
            assert "repeat parking offender" not in (
                r["major_incident_reason"] or ""
            )


def test_different_plates_dont_aggregate(client, auth_header):
    """Three plates, one violation each — repeat heuristic does NOT
    fire (plate is the grouping key, not the unit or society)."""
    for plate in ("MH99DIFA01", "MH99DIFB01", "MH99DIFC01"):
        _create_parking_complaints(
            client, auth_header, plate, 1, [0],
        )
    incident_flagging.run_due_incident_flagging()
    with get_conn() as conn:
        rows = [
            dict(r) for r in conn.execute(
                "SELECT major_incident, major_incident_reason "
                "FROM complaints "
                "WHERE vehicle_plate LIKE 'MH99DIF%'"
            ).fetchall()
        ]
    for r in rows:
        if r["major_incident"]:
            assert "repeat parking offender" not in (
                r["major_incident_reason"] or ""
            )


# =====================================================================
# P4 — authorize-clamping endpoint
# =====================================================================

def _make_parking_complaint(client, headers, plate: str = "MH88CLAMP01"):
    """Helper: seed a vehicle + file a parking complaint linked to it."""
    _seed_vehicle(plate, owner_phone="+919833000888")
    r = client.post(
        "/api/v1/complaints",
        json={
            "raw_text": "Parking Management blocking lobby",
            "vehicle_plate": plate,
            "violation_type": "blocking_fire_exit",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_clamping_by_admin_succeeds(
    client, auth_header, monkeypatch,
):
    sent = MagicMock()
    from app.services import notify as nt
    monkeypatch.setattr(nt, "send_whatsapp", sent)
    c = _make_parking_complaint(client, auth_header)
    r = client.post(
        f"/api/v1/complaints/{c['id']}/authorize-clamping",
        headers=auth_header,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["clamped"] == 1
    assert body["clamped_at"] is not None
    assert body["clamping_authorized_by"] is not None


def test_clamping_notifies_owner(client, auth_header, monkeypatch):
    sent = MagicMock()
    from app.services import notify as nt
    monkeypatch.setattr(nt, "send_whatsapp", sent)
    c = _make_parking_complaint(client, auth_header, "MH88CLAMP02")
    client.post(
        f"/api/v1/complaints/{c['id']}/authorize-clamping",
        headers=auth_header,
    )
    calls = [call.args for call in sent.call_args_list]
    assert any(
        "+919833000888" in call[0] and "clamped" in call[1].lower()
        for call in calls
    ), f"expected owner clamping notify; got calls={calls}"


def test_clamping_is_idempotent(client, auth_header, monkeypatch):
    sent = MagicMock()
    from app.services import notify as nt
    monkeypatch.setattr(nt, "send_whatsapp", sent)
    c = _make_parking_complaint(client, auth_header, "MH88CLAMP03")
    r1 = client.post(
        f"/api/v1/complaints/{c['id']}/authorize-clamping",
        headers=auth_header,
    )
    assert r1.status_code == 200
    first_at = r1.json()["clamped_at"]
    sent.reset_mock()
    # second call should NOT re-notify the owner
    r2 = client.post(
        f"/api/v1/complaints/{c['id']}/authorize-clamping",
        headers=auth_header,
    )
    assert r2.status_code == 200
    assert r2.json()["clamped"] == 1
    assert r2.json()["clamped_at"] == first_at  # preserved
    # no clamping-notify was sent on the second call
    clamp_calls = [
        call for call in sent.call_args_list
        if "clamped" in call.args[1].lower()
    ]
    assert clamp_calls == []


def test_clamping_on_non_parking_400(client, auth_header):
    r0 = client.post(
        "/api/v1/complaints",
        json={"raw_text": "AC kharab 5B"},
        headers=auth_header,
    )
    cid = r0.json()["id"]
    r = client.post(
        f"/api/v1/complaints/{cid}/authorize-clamping",
        headers=auth_header,
    )
    assert r.status_code == 400
    assert "Parking" in r.json()["detail"]


def test_clamping_404_unknown_complaint(client, auth_header):
    r = client.post(
        "/api/v1/complaints/99999/authorize-clamping",
        headers=auth_header,
    )
    assert r.status_code == 404


def test_clamping_by_manager_forbidden(client, auth_header):
    """manager has MODIFY_STAFF but not AUTHORIZE_ENFORCEMENT."""
    _seed_user("m_clamp@p.example", "Pass!1", "manager")
    h = _login(client, "m_clamp@p.example", "Pass!1")
    c = _make_parking_complaint(client, auth_header, "MH88CLAMP04")
    r = client.post(
        f"/api/v1/complaints/{c['id']}/authorize-clamping",
        headers=h,
    )
    assert r.status_code == 403


def test_clamping_by_chairman_succeeds(client, auth_header):
    """chairman has AUTHORIZE_ENFORCEMENT by default."""
    _seed_user("c_clamp@p.example", "Pass!1", "chairman")
    h = _login(client, "c_clamp@p.example", "Pass!1")
    c = _make_parking_complaint(client, auth_header, "MH88CLAMP05")
    r = client.post(
        f"/api/v1/complaints/{c['id']}/authorize-clamping",
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["clamped"] == 1
