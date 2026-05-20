"""E3a: society-scoped staff_members CRUD + category subresource.

Permission gates:
  reads  -> VIEW_ALL    (admin, viewer, leaders, manager all OK)
  writes -> MODIFY_STAFF (admin, leaders, manager OK; staff/resident NO)
"""
import pytest

from app.db import get_conn
from app.security import hash_password

PW = "Secret!123"


def _login(client, email: str) -> dict:
    r = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PW}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def sclient(client):
    """Adds a low-priv 'staff' user + manager + viewer + a second
    society with its own admin (for cross-society isolation tests)."""
    with get_conn() as conn:
        # extra users in society 1
        for role in ("staff", "manager", "viewer"):
            conn.execute(
                "INSERT INTO users (email, password_hash, full_name, "
                "role, society_id, is_active) VALUES (?,?,?,?,?,1)",
                (f"{role}@s1.com", hash_password(PW),
                 role.title(), role, 1),
            )
        # society 2 + admin in it
        conn.execute("INSERT INTO societies (name) VALUES ('Soc2')")
        s2 = dict(conn.execute(
            "SELECT id FROM societies ORDER BY id DESC LIMIT 1"
        ).fetchone())["id"]
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, "
            "role, society_id, is_active) VALUES (?,?,?,?,?,1)",
            ("admin2@x.com", hash_password(PW), "A2", "admin", s2),
        )
    return client, s2, {
        "admin": _login(client, "admin@aibuildcare.app"),
        "manager": _login(client, "manager@s1.com"),
        "staff": _login(client, "staff@s1.com"),
        "viewer": _login(client, "viewer@s1.com"),
        "admin2": _login(client, "admin2@x.com"),
    }


# ---- CRUD basics ----------------------------------------------------
def test_create_list_get_staff(sclient):
    client, _, tok = sclient
    body = {
        "name": "Ramesh Plumber", "phone_primary": "+919000000001",
        "categories": [
            {"category": "Plumbing", "primary_category": True,
             "skill_level": "senior"},
            {"category": "Water Supply", "primary_category": False,
             "skill_level": "junior"},
        ],
    }
    r = client.post(
        "/api/v1/staff", json=body, headers=tok["admin"]
    )
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert r.json()["name"] == "Ramesh Plumber"
    assert len(r.json()["categories"]) == 2

    # LIST
    lst = client.get("/api/v1/staff", headers=tok["admin"]).json()
    assert any(s["id"] == sid for s in lst)

    # GET
    g = client.get(f"/api/v1/staff/{sid}", headers=tok["admin"])
    assert g.status_code == 200
    assert g.json()["whatsapp_enabled"] is True
    cats = {c["category"] for c in g.json()["categories"]}
    assert {"Plumbing", "Water Supply"} <= cats


def test_partial_update(sclient):
    client, _, tok = sclient
    r = client.post(
        "/api/v1/staff",
        json={"name": "X", "phone_primary": "+910"},
        headers=tok["admin"],
    )
    sid = r.json()["id"]
    r = client.put(
        f"/api/v1/staff/{sid}",
        json={"name": "X Updated", "whatsapp_enabled": False},
        headers=tok["admin"],
    )
    assert r.status_code == 200
    assert r.json()["name"] == "X Updated"
    assert r.json()["whatsapp_enabled"] is False
    # untouched field preserved
    assert r.json()["phone_primary"] == "+910"


def test_soft_delete_deactivates_not_destroys(sclient):
    client, _, tok = sclient
    r = client.post(
        "/api/v1/staff",
        json={"name": "Bye", "phone_primary": "+910"},
        headers=tok["admin"],
    )
    sid = r.json()["id"]
    r = client.delete(f"/api/v1/staff/{sid}", headers=tok["admin"])
    assert r.status_code == 200
    assert r.json()["active"] is False
    # default list (active only) excludes
    lst = client.get("/api/v1/staff", headers=tok["admin"]).json()
    assert not any(s["id"] == sid for s in lst)
    # include_inactive surfaces it
    lst = client.get(
        "/api/v1/staff?include_inactive=true", headers=tok["admin"]
    ).json()
    assert any(s["id"] == sid for s in lst)


# ---- category subresource ------------------------------------------
def test_add_and_remove_category(sclient):
    client, _, tok = sclient
    r = client.post(
        "/api/v1/staff",
        json={"name": "Y", "phone_primary": "+910"},
        headers=tok["admin"],
    )
    sid = r.json()["id"]
    r = client.post(
        f"/api/v1/staff/{sid}/categories",
        json={"category": "Carpentry", "primary_category": True,
              "skill_level": "expert"},
        headers=tok["admin"],
    )
    assert r.status_code == 200
    cats = {c["category"]: c for c in r.json()["categories"]}
    assert "Carpentry" in cats
    assert cats["Carpentry"]["skill_level"] == "expert"
    assert cats["Carpentry"]["primary_category"] is True

    r = client.delete(
        f"/api/v1/staff/{sid}/categories/Carpentry",
        headers=tok["admin"],
    )
    assert r.status_code == 200
    assert not any(
        c["category"] == "Carpentry" for c in r.json()["categories"]
    )


def test_invalid_category_400(sclient):
    client, _, tok = sclient
    r = client.post(
        "/api/v1/staff",
        json={"name": "Z", "phone_primary": "+910",
              "categories": [{"category": "Mind Reading"}]},
        headers=tok["admin"],
    )
    assert r.status_code == 400


def test_invalid_skill_400(sclient):
    client, _, tok = sclient
    r = client.post(
        "/api/v1/staff",
        json={"name": "Z", "phone_primary": "+910",
              "categories": [{"category": "Plumbing",
                              "skill_level": "wizard"}]},
        headers=tok["admin"],
    )
    assert r.status_code == 400


# ---- RBAC ----------------------------------------------------------
def test_staff_role_cannot_create(sclient):
    client, _, tok = sclient
    r = client.post(
        "/api/v1/staff",
        json={"name": "Q", "phone_primary": "+910"},
        headers=tok["staff"],
    )
    assert r.status_code == 403


def test_manager_can_create(sclient):
    """Manager has MODIFY_STAFF by default."""
    client, _, tok = sclient
    r = client.post(
        "/api/v1/staff",
        json={"name": "Q", "phone_primary": "+910"},
        headers=tok["manager"],
    )
    assert r.status_code == 201


def test_viewer_can_list_but_not_mutate(sclient):
    client, _, tok = sclient
    # viewer has VIEW_ALL
    assert client.get(
        "/api/v1/staff", headers=tok["viewer"]
    ).status_code == 200
    # but not MODIFY_STAFF
    assert client.post(
        "/api/v1/staff",
        json={"name": "X", "phone_primary": "+910"},
        headers=tok["viewer"],
    ).status_code == 403


# ---- society isolation ---------------------------------------------
def test_cross_society_get_is_404(sclient):
    """admin2 (society 2) cannot read or mutate society-1 staff."""
    client, s2, tok = sclient
    r = client.post(
        "/api/v1/staff",
        json={"name": "Society-1 person", "phone_primary": "+910"},
        headers=tok["admin"],
    )
    sid = r.json()["id"]
    # admin2 lists -> empty (their own society)
    other = client.get("/api/v1/staff", headers=tok["admin2"]).json()
    assert not any(s["id"] == sid for s in other)
    # admin2 GET by id -> 404
    assert client.get(
        f"/api/v1/staff/{sid}", headers=tok["admin2"]
    ).status_code == 404
    # PUT / DELETE / add-category -> 404
    assert client.put(
        f"/api/v1/staff/{sid}", json={"name": "x"},
        headers=tok["admin2"],
    ).status_code == 404
    assert client.delete(
        f"/api/v1/staff/{sid}", headers=tok["admin2"]
    ).status_code == 404


# ---- routing integration: new staff appears in routing -------------
def test_created_staff_picked_up_by_routing(sclient, monkeypatch):
    """Once a Plumbing-primary staff member exists in society 1, the
    next Plumbing complaint should auto-assign to them (routing test)."""
    client, _, tok = sclient
    # enable auto-assign for just this test
    monkeypatch.setenv("AIBUILDCARE_AUTO_ASSIGN_ENABLED", "true")
    from app.config import get_settings
    get_settings.cache_clear()

    r = client.post(
        "/api/v1/staff",
        json={"name": "Auto Plumber", "phone_primary": "+910",
              "categories": [{"category": "Plumbing",
                              "primary_category": True,
                              "skill_level": "senior"}]},
        headers=tok["admin"],
    )
    new_sid = r.json()["id"]
    c = client.post(
        "/api/v1/complaints", json={"raw_text": "5B nal leak"},
        headers=tok["admin"],
    ).json()
    get_settings.cache_clear()
    assert c["assigned_staff_id"] == new_sid
    assert c["contractor_id"] is None
