"""E3h: GET /api/v1/auth/me returns identity + effective permissions
so the frontend can hide nav + action buttons by role.

Also covers the new rbac.permissions_for() helper directly, since the
endpoint is a thin wrapper around it and the helper has its own logic
(admin bypass, override application, DB resilience).
"""
import pytest

from app.db import get_conn
from app.security import hash_password
from app.services import rbac


# ---- rbac.permissions_for() helper -----------------------------------

def test_permissions_for_admin_returns_all(client):
    """Admin bypass: always all permissions, overrides ignored."""
    perms = rbac.permissions_for("admin", society_id=1)
    assert perms == rbac.ALL_PERMISSIONS


def test_permissions_for_unknown_role_empty(client):
    perms = rbac.permissions_for("ghost", society_id=1)
    assert perms == frozenset()


def test_permissions_for_resident_default(client):
    perms = rbac.permissions_for("resident", society_id=1)
    assert perms == frozenset({rbac.FILE_COMPLAINT, rbac.VIEW_OWN})


def test_permissions_for_manager_default(client):
    perms = rbac.permissions_for("manager", society_id=1)
    assert rbac.ASSIGN in perms
    assert rbac.MODIFY_STAFF in perms
    assert rbac.AUTHORIZE_ENFORCEMENT not in perms


def test_permissions_for_override_grants_new_permission(client):
    """Per-society override that GRANTS a permission not in defaults."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO role_permission_overrides "
            "(society_id, role, permission, granted) VALUES (?,?,?,?)",
            (1, "resident", rbac.VIEW_ALL, 1),
        )
    perms = rbac.permissions_for("resident", society_id=1)
    assert rbac.VIEW_ALL in perms


def test_permissions_for_override_revokes_default_permission(client):
    """Per-society override that REVOKES a permission residents
    normally have."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO role_permission_overrides "
            "(society_id, role, permission, granted) VALUES (?,?,?,?)",
            (1, "resident", rbac.FILE_COMPLAINT, 0),
        )
    perms = rbac.permissions_for("resident", society_id=1)
    assert rbac.FILE_COMPLAINT not in perms
    assert rbac.VIEW_OWN in perms  # other default still there


def test_permissions_for_admin_unaffected_by_overrides(client):
    """OEM safety: admin is hard-coded ALL, overrides cannot revoke."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO role_permission_overrides "
            "(society_id, role, permission, granted) VALUES (?,?,?,?)",
            (1, "admin", rbac.FILE_COMPLAINT, 0),
        )
    perms = rbac.permissions_for("admin", society_id=1)
    assert perms == rbac.ALL_PERMISSIONS


def test_permissions_for_no_society_id_skips_override_lookup(client):
    """When called without a society_id, only the default matrix is
    consulted. Used in tests / non-tenant code paths."""
    perms = rbac.permissions_for("resident", society_id=None)
    assert perms == frozenset({rbac.FILE_COMPLAINT, rbac.VIEW_OWN})


# ---- GET /api/v1/auth/me endpoint -------------------------------------

def _login(client, email, password):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed_user(email, password, role, full_name="User"):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, role, "
            "society_id, is_active) VALUES (?,?,?,?,?,1)",
            (email, hash_password(password), full_name, role, 1),
        )


def test_me_returns_admin_shape(client, auth_header):
    """Seed admin (role='admin') should report ALL permissions."""
    r = client.get("/api/v1/auth/me", headers=auth_header)
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "admin@aibuildcare.app"
    assert body["role"] == "admin"
    assert body["society_id"] == 1
    assert set(body["permissions"]) == rbac.ALL_PERMISSIONS


def test_me_returns_resident_shape(client):
    _seed_user("alice@palms.example", "Resident!1", "resident",
               "Alice Resident")
    h = _login(client, "alice@palms.example", "Resident!1")
    r = client.get("/api/v1/auth/me", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "resident"
    assert body["full_name"] == "Alice Resident"
    assert set(body["permissions"]) == {
        rbac.FILE_COMPLAINT, rbac.VIEW_OWN
    }


def test_me_returns_manager_shape(client):
    _seed_user("mira@palms.example", "Manager!1", "manager", "Mira Manager")
    h = _login(client, "mira@palms.example", "Manager!1")
    r = client.get("/api/v1/auth/me", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "manager"
    perms = set(body["permissions"])
    assert rbac.ASSIGN in perms
    assert rbac.MODIFY_STAFF in perms
    assert rbac.AUTHORIZE_ENFORCEMENT not in perms


def test_me_reflects_per_society_override(client):
    """If an override flips a permission for the calling user's role,
    /me reflects it (so the frontend hides matching UI)."""
    _seed_user("bob@palms.example", "Resident!2", "resident")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO role_permission_overrides "
            "(society_id, role, permission, granted) VALUES (?,?,?,?)",
            (1, "resident", rbac.VIEW_ALL, 1),
        )
    h = _login(client, "bob@palms.example", "Resident!2")
    r = client.get("/api/v1/auth/me", headers=h)
    assert r.status_code == 200
    assert rbac.VIEW_ALL in r.json()["permissions"]


def test_me_requires_auth(client):
    """No bearer token -> 401."""
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_permissions_are_sorted(client, auth_header):
    """Stable ordering simplifies frontend caching + diff checks."""
    r = client.get("/api/v1/auth/me", headers=auth_header)
    perms = r.json()["permissions"]
    assert perms == sorted(perms)
