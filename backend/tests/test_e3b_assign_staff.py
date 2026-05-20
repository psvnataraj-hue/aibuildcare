"""E3b: POST /complaints/{cid}/assign now accepts staff_id OR
contractor_id (exactly one). Validates one-of, scopes by society,
and handles contractor->staff handover notification.
"""
from unittest.mock import MagicMock

from app.db import get_conn
from app.security import hash_password


def _add_staff(name, society_id=1, phone="+919000000111"):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO staff_members (society_id, name, phone_primary, "
            "whatsapp_enabled, active) VALUES (?,?,?,1,1)",
            (society_id, name, phone),
        )
        return dict(conn.execute(
            "SELECT id FROM staff_members ORDER BY id DESC LIMIT 1"
        ).fetchone())["id"]


def _create(client, auth_header):
    r = client.post(
        "/api/v1/complaints", json={"raw_text": "5B nal leak"},
        headers=auth_header,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_neither_id_provided_400(client, auth_header):
    c = _create(client, auth_header)
    r = client.post(
        f"/api/v1/complaints/{c['id']}/assign",
        json={}, headers=auth_header,
    )
    assert r.status_code == 400
    assert "exactly one" in r.json()["detail"]


def test_both_ids_provided_400(client, auth_header):
    c = _create(client, auth_header)
    sid = _add_staff("X")
    r = client.post(
        f"/api/v1/complaints/{c['id']}/assign",
        json={"contractor_id": 1, "staff_id": sid},
        headers=auth_header,
    )
    assert r.status_code == 400


def test_assign_to_staff_succeeds(client, auth_header, monkeypatch):
    sent = MagicMock(return_value=True)
    monkeypatch.setattr(
        "app.routers.complaints.send_whatsapp", sent,
    )
    c = _create(client, auth_header)
    staff_id = _add_staff("Ramesh Plumber", phone="+919833000000")
    r = client.post(
        f"/api/v1/complaints/{c['id']}/assign",
        json={"staff_id": staff_id}, headers=auth_header,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["assigned_staff_id"] == staff_id
    assert body["contractor_id"] is None
    assert body["status"] == "assigned"


def test_assign_to_contractor_still_works(client, auth_header,
                                           monkeypatch):
    """The original contractor-only path must remain unchanged."""
    sent = MagicMock(return_value=True)
    monkeypatch.setattr(
        "app.routers.complaints.send_whatsapp", sent,
    )
    c = _create(client, auth_header)
    # seed contractor for default society
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO contractors (name, specialty, society_id, "
            "is_active, phone) VALUES ('Aqua', 'Plumbing', 1, 1, "
            "'+919999999999')"
        )
        ctr = cur.lastrowid
    r = client.post(
        f"/api/v1/complaints/{c['id']}/assign",
        json={"contractor_id": ctr}, headers=auth_header,
    )
    assert r.status_code == 200, r.text
    assert r.json()["contractor_id"] == ctr
    assert r.json()["assigned_staff_id"] is None


def test_handover_from_contractor_to_staff_notifies_previous(
    client, auth_header, monkeypatch,
):
    sent = MagicMock(return_value=True)
    monkeypatch.setattr(
        "app.routers.complaints.send_whatsapp", sent,
    )
    c = _create(client, auth_header)
    # assign contractor first
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO contractors (name, specialty, society_id, "
            "is_active, phone) VALUES ('Aqua', 'Plumbing', 1, 1, "
            "'+919888888888')"
        )
        ctr = dict(conn.execute(
            "SELECT id FROM contractors ORDER BY id DESC LIMIT 1"
        ).fetchone())["id"]
    client.post(
        f"/api/v1/complaints/{c['id']}/assign",
        json={"contractor_id": ctr}, headers=auth_header,
    )
    sent.reset_mock()

    # now hand over to staff
    staff_id = _add_staff("In-House Plumber")
    r = client.post(
        f"/api/v1/complaints/{c['id']}/assign",
        json={"staff_id": staff_id}, headers=auth_header,
    )
    assert r.status_code == 200
    assert r.json()["assigned_staff_id"] == staff_id
    assert r.json()["contractor_id"] is None  # cleared on handover

    # previous contractor was WhatsApped a "handover" notice
    bodies = [call.args[1] for call in sent.call_args_list]
    assert any("handed over to in-house staff" in b for b in bodies)


def test_assign_unknown_staff_404(client, auth_header):
    c = _create(client, auth_header)
    r = client.post(
        f"/api/v1/complaints/{c['id']}/assign",
        json={"staff_id": 999999}, headers=auth_header,
    )
    assert r.status_code == 404


def test_cross_society_staff_assign_404(client, auth_header):
    """Staff in society 2 cannot be assigned to society 1's complaint."""
    with get_conn() as conn:
        conn.execute("INSERT INTO societies (name) VALUES ('Soc2')")
        s2 = dict(conn.execute(
            "SELECT id FROM societies ORDER BY id DESC LIMIT 1"
        ).fetchone())["id"]
    outsider = _add_staff("Outsider", society_id=s2)
    c = _create(client, auth_header)
    r = client.post(
        f"/api/v1/complaints/{c['id']}/assign",
        json={"staff_id": outsider}, headers=auth_header,
    )
    assert r.status_code == 404


def test_assign_to_inactive_staff_404(client, auth_header):
    sid = _add_staff("Retiree")
    with get_conn() as conn:
        conn.execute(
            "UPDATE staff_members SET active = 0 WHERE id = ?", (sid,)
        )
    c = _create(client, auth_header)
    r = client.post(
        f"/api/v1/complaints/{c['id']}/assign",
        json={"staff_id": sid}, headers=auth_header,
    )
    assert r.status_code == 404
