"""E1c: manual escalation + hierarchy CRUD.

Levels 1..4 map: manager / sr_manager / secretary / chairman.
Escalation is society-scoped (hierarchy + complaint must match).
Each level set timestamp field on complaints + notification to that
society's contact at that level.
"""
from unittest.mock import MagicMock

import pytest

from app.db import get_conn
from app.security import hash_password
from app.services import escalation_service, rbac, rbac_overrides

PW = "Secret!123"


def _login(client, email: str) -> dict:
    r = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PW}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed_user(role: str, society_id: int = 1):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, "
            "role, society_id, is_active) VALUES (?,?,?,?,?,1)",
            (f"{role}@s{society_id}.com", hash_password(PW),
             role.title(), role, society_id),
        )


def _seed_hierarchy(society_id: int, level: int, role_name: str,
                    person: str, phone: str = "+910000000000",
                    wa: int = 1):
    return escalation_service.add_hierarchy(
        society_id, role_name=role_name, person_name=person,
        phone=phone, whatsapp_enabled=bool(wa),
        escalation_level=level,
    )


def _create_complaint(client, tok, text="leak in 5B"):
    r = client.post(
        "/api/v1/complaints", json={"raw_text": text}, headers=tok
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def eclient(client):
    """Adds non-admin role users + a full 4-level hierarchy in
    society 1; yields (client, society_id, tokens)."""
    sid = 1
    _seed_user("manager")
    _seed_user("staff")
    _seed_hierarchy(sid, 1, "manager", "Mira Manager",
                    "+910000000001")
    _seed_hierarchy(sid, 2, "sr_manager", "Sam Sr",
                    "+910000000002")
    _seed_hierarchy(sid, 3, "secretary", "Sita Secretary",
                    "+910000000003")
    _seed_hierarchy(sid, 4, "chairman", "Chand Chair",
                    "+910000000004")
    return client, sid, {
        "admin": _login(client, "admin@aibuildcare.app"),
        "manager": _login(client, "manager@s1.com"),
        "staff": _login(client, "staff@s1.com"),
    }


# ---- escalate action ------------------------------------------------
def test_first_escalation_sets_level1_and_notifies_manager(
    eclient, monkeypatch,
):
    client, _, tok = eclient
    sent = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.notify.send_whatsapp", sent)
    c = _create_complaint(client, tok["admin"])
    r = client.post(
        f"/api/v1/complaints/{c['id']}/escalate", headers=tok["admin"]
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["escalated_level"] == 1
    assert body["escalated_role"] == "manager"
    assert body["escalated_to_manager_at"] is not None
    assert body["escalated_to_sr_manager_at"] is None
    # notification sent
    assert sent.called
    phone, msg = sent.call_args[0]
    assert phone == "+910000000001"
    assert "ESCALATION L1" in msg
    assert body["ticket_number"] in msg


def test_sequential_escalation_through_all_4_levels(eclient):
    client, _, tok = eclient
    c = _create_complaint(client, tok["admin"])
    cid = c["id"]
    levels = []
    for expected in (1, 2, 3, 4):
        r = client.post(
            f"/api/v1/complaints/{cid}/escalate",
            headers=tok["admin"],
        )
        assert r.status_code == 200
        levels.append(r.json()["escalated_level"])
    assert levels == [1, 2, 3, 4]
    # fifth attempt -> 400 already at max
    r = client.post(
        f"/api/v1/complaints/{cid}/escalate", headers=tok["admin"]
    )
    assert r.status_code == 400
    assert "max" in r.json()["detail"]


def test_escalate_without_hierarchy_400(client, monkeypatch):
    tok = _login(client, "admin@aibuildcare.app")
    r = client.post(
        "/api/v1/complaints", json={"raw_text": "x"},
        headers={"Authorization": tok["Authorization"]},
    )
    cid = r.json()["id"]
    # no hierarchy seeded for society 1
    r = client.post(
        f"/api/v1/complaints/{cid}/escalate", headers=tok
    )
    assert r.status_code == 400
    assert "no active escalation contact" in r.json()["detail"]


def test_escalate_cross_society_is_404(eclient):
    """Escalating someone else's complaint must be a 404."""
    client, sid, tok = eclient
    # add society 2 + admin user in it
    with get_conn() as conn:
        conn.execute("INSERT INTO societies (name) VALUES ('Soc2')")
        s2 = dict(conn.execute(
            "SELECT id FROM societies ORDER BY id DESC LIMIT 1"
        ).fetchone())["id"]
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, "
            "role, society_id, is_active) VALUES (?,?,?,?,?,1)",
            ("admin2@x.com", hash_password(PW), "A2", "admin", s2),
        )
    h2 = _login(client, "admin2@x.com")
    c1 = _create_complaint(client, tok["admin"])
    # admin2 (society 2) tries to escalate society 1's complaint
    r = client.post(
        f"/api/v1/complaints/{c1['id']}/escalate", headers=h2
    )
    assert r.status_code == 404


def test_staff_lacks_escalate_permission(eclient):
    client, _, tok = eclient
    c = _create_complaint(client, tok["admin"])
    r = client.post(
        f"/api/v1/complaints/{c['id']}/escalate", headers=tok["staff"]
    )
    assert r.status_code == 403


def test_manager_has_escalate_by_default(eclient):
    client, _, tok = eclient
    c = _create_complaint(client, tok["admin"])
    r = client.post(
        f"/api/v1/complaints/{c['id']}/escalate", headers=tok["manager"]
    )
    assert r.status_code == 200


def test_inactive_hierarchy_row_skipped(eclient):
    """Mark L1 inactive -> next escalation should be unable to find a
    contact at L1 (and should NOT silently skip to L2)."""
    client, sid, tok = eclient
    # find L1 row and deactivate
    rows = escalation_service.list_hierarchy(sid)
    l1 = next(r for r in rows if r["escalation_level"] == 1)
    escalation_service.update_hierarchy(l1["id"], sid, active=False)
    c = _create_complaint(client, tok["admin"])
    r = client.post(
        f"/api/v1/complaints/{c['id']}/escalate", headers=tok["admin"]
    )
    assert r.status_code == 400
    assert "level 1" in r.json()["detail"]


def test_whatsapp_disabled_contact_gets_no_message(eclient, monkeypatch):
    client, sid, tok = eclient
    rows = escalation_service.list_hierarchy(sid)
    l1 = next(r for r in rows if r["escalation_level"] == 1)
    escalation_service.update_hierarchy(
        l1["id"], sid, whatsapp_enabled=False,
    )
    sent = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.notify.send_whatsapp", sent)
    c = _create_complaint(client, tok["admin"])
    r = client.post(
        f"/api/v1/complaints/{c['id']}/escalate", headers=tok["admin"]
    )
    assert r.status_code == 200
    assert not sent.called


# ---- hierarchy CRUD endpoints ---------------------------------------
def test_hierarchy_list_endpoint_society_scoped(eclient):
    client, sid, tok = eclient
    r = client.get("/api/v1/escalation/hierarchy", headers=tok["admin"])
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 4
    assert {r["escalation_level"] for r in rows} == {1, 2, 3, 4}


def test_hierarchy_post_put_delete_flow(eclient):
    client, _, tok = eclient
    # POST (admin has MODIFY_CONFIG)
    r = client.post(
        "/api/v1/escalation/hierarchy",
        json={"role_name": "manager", "person_name": "New M",
              "phone": "+919999999999", "escalation_level": 1},
        headers=tok["admin"],
    )
    assert r.status_code == 201
    eid = r.json()["id"]
    # PUT
    r = client.put(
        f"/api/v1/escalation/hierarchy/{eid}",
        json={"person_name": "Renamed M"}, headers=tok["admin"],
    )
    assert r.status_code == 200
    assert r.json()["person_name"] == "Renamed M"
    # DELETE
    r = client.delete(
        f"/api/v1/escalation/hierarchy/{eid}", headers=tok["admin"]
    )
    assert r.status_code == 200
    assert r.json()["deleted"] == 1


def test_hierarchy_post_invalid_role_400(eclient):
    client, _, tok = eclient
    r = client.post(
        "/api/v1/escalation/hierarchy",
        json={"role_name": "intern", "person_name": "X",
              "escalation_level": 1},
        headers=tok["admin"],
    )
    assert r.status_code == 400


def test_hierarchy_post_requires_modify_config(eclient):
    client, _, tok = eclient
    # manager has MODIFY_STAFF but NOT MODIFY_CONFIG by default
    r = client.post(
        "/api/v1/escalation/hierarchy",
        json={"role_name": "manager", "person_name": "X",
              "escalation_level": 1},
        headers=tok["manager"],
    )
    assert r.status_code == 403


def test_hierarchy_delete_unknown_404(eclient):
    client, _, tok = eclient
    r = client.delete(
        "/api/v1/escalation/hierarchy/999999", headers=tok["admin"]
    )
    assert r.status_code == 404
