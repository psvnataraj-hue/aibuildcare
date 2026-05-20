"""Foundation F3: endpoint RBAC enforcement + per-society overrides.

Defaults come from rbac.ROLE_PERMISSIONS. A society can grant or revoke
any permission for any non-admin role; the OEM superuser (admin) is
never overridable.
"""
import pytest

from app.db import get_conn
from app.security import hash_password
from app.services import rbac, rbac_overrides

PW = "Secret!123"


def _login(client, email: str) -> dict:
    r = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PW}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def roles_in_soc1(client):
    """Create a user per role-of-interest in the default (seed)
    society, all with the same password."""
    with get_conn() as conn:
        sid = dict(
            conn.execute(
                "SELECT id FROM societies ORDER BY id LIMIT 1"
            ).fetchone()
        )["id"]
        for role in ("staff", "manager", "viewer", "resident"):
            conn.execute(
                "INSERT INTO users (email, password_hash, full_name, "
                "role, society_id, is_active) VALUES (?,?,?,?,?,1)",
                (f"{role}@s1.com", hash_password(PW), role.title(),
                 role, sid),
            )
    return sid, {
        "staff": _login(client, "staff@s1.com"),
        "manager": _login(client, "manager@s1.com"),
        "viewer": _login(client, "viewer@s1.com"),
        "resident": _login(client, "resident@s1.com"),
        "admin": _login(client, "admin@aibuildcare.app"),
    }


# ---- default matrix enforcement -------------------------------------
def test_staff_cannot_assign_by_default(client, roles_in_soc1):
    sid, tok = roles_in_soc1
    # admin makes a complaint to target
    rc = client.post(
        "/api/v1/complaints", json={"raw_text": "test"}, headers=tok["admin"]
    )
    cid = rc.json()["id"]

    # staff (no ASSIGN by default) -> 403
    r = client.post(
        f"/api/v1/complaints/{cid}/assign",
        json={"contractor_id": 1}, headers=tok["staff"],
    )
    assert r.status_code == 403
    assert "lacks 'assign'" in r.json()["detail"]


def test_manager_can_assign_by_default(client, roles_in_soc1):
    sid, tok = roles_in_soc1
    rc = client.post(
        "/api/v1/complaints", json={"raw_text": "test"}, headers=tok["admin"]
    )
    cid = rc.json()["id"]
    r = client.post(
        f"/api/v1/complaints/{cid}/assign",
        json={"contractor_id": 1}, headers=tok["manager"],
    )
    # manager has ASSIGN -> reaches the service (200 or 404 if contractor
    # missing); the key assertion is NOT 403
    assert r.status_code != 403


def test_resident_cannot_view_all(client, roles_in_soc1):
    _, tok = roles_in_soc1
    r = client.get("/api/v1/complaints", headers=tok["resident"])
    assert r.status_code == 403


def test_viewer_can_view_all(client, roles_in_soc1):
    _, tok = roles_in_soc1
    r = client.get("/api/v1/complaints", headers=tok["viewer"])
    assert r.status_code == 200


def test_modify_config_gated(client, roles_in_soc1):
    _, tok = roles_in_soc1
    # manager lacks MODIFY_CONFIG by default
    r = client.post(
        "/api/v1/admin/config/x", json={"value": "1"}, headers=tok["manager"]
    )
    assert r.status_code == 403
    # admin OK
    r = client.post(
        "/api/v1/admin/config/x", json={"value": "1"}, headers=tok["admin"]
    )
    assert r.status_code == 200


# ---- per-society overrides ------------------------------------------
def test_grant_override_unlocks_endpoint(client, roles_in_soc1):
    sid, tok = roles_in_soc1
    rc = client.post(
        "/api/v1/complaints", json={"raw_text": "x"}, headers=tok["admin"]
    )
    cid = rc.json()["id"]

    # initially staff blocked
    assert client.post(
        f"/api/v1/complaints/{cid}/assign",
        json={"contractor_id": 1}, headers=tok["staff"],
    ).status_code == 403

    rbac_overrides.set_override(sid, "staff", rbac.ASSIGN, True)

    assert client.post(
        f"/api/v1/complaints/{cid}/assign",
        json={"contractor_id": 1}, headers=tok["staff"],
    ).status_code != 403


def test_revoke_override_blocks_endpoint(client, roles_in_soc1):
    sid, tok = roles_in_soc1
    # manager normally allowed
    assert client.get(
        "/api/v1/complaints", headers=tok["manager"]
    ).status_code == 200
    rbac_overrides.set_override(sid, "manager", rbac.VIEW_ALL, False)
    assert client.get(
        "/api/v1/complaints", headers=tok["manager"]
    ).status_code == 403


def test_clear_override_restores_default(client, roles_in_soc1):
    sid, tok = roles_in_soc1
    rbac_overrides.set_override(sid, "staff", rbac.ASSIGN, True)
    rbac_overrides.clear_override(sid, "staff", rbac.ASSIGN)
    # back to default -> blocked
    assert rbac.has_permission("staff", rbac.ASSIGN, sid) is False


def test_admin_is_never_overridable(client, roles_in_soc1):
    sid, _ = roles_in_soc1
    # cannot revoke admin permissions
    with pytest.raises(rbac_overrides.OverrideError):
        rbac_overrides.set_override(sid, "admin", rbac.ASSIGN, False)
    # admin still has all perms in this society
    for p in rbac.ALL_PERMISSIONS:
        assert rbac.has_permission("admin", p, sid) is True


def test_override_validation_rejects_unknowns(client, roles_in_soc1):
    sid, _ = roles_in_soc1
    with pytest.raises(rbac_overrides.OverrideError):
        rbac_overrides.set_override(sid, "ghost_role", rbac.ASSIGN, True)
    with pytest.raises(rbac_overrides.OverrideError):
        rbac_overrides.set_override(sid, "staff", "ghost_perm", True)


def test_overrides_are_isolated_per_society(client, roles_in_soc1):
    sid1, _ = roles_in_soc1
    # add a second society
    with get_conn() as conn:
        conn.execute("INSERT INTO societies (name) VALUES ('Soc2')")
        sid2 = dict(
            conn.execute(
                "SELECT id FROM societies ORDER BY id DESC LIMIT 1"
            ).fetchone()
        )["id"]
    rbac_overrides.set_override(sid2, "staff", rbac.ASSIGN, True)
    # society 2 staff got ASSIGN; society 1 staff did NOT
    assert rbac.has_permission("staff", rbac.ASSIGN, sid2) is True
    assert rbac.has_permission("staff", rbac.ASSIGN, sid1) is False


# ---- OEM permission admin endpoints ---------------------------------
def test_effective_matrix_endpoint(client, roles_in_soc1):
    sid, tok = roles_in_soc1
    rbac_overrides.set_override(sid, "staff", rbac.ASSIGN, True)
    r = client.get("/api/v1/admin/permissions", headers=tok["admin"])
    assert r.status_code == 200
    roles = r.json()["roles"]
    assert rbac.ASSIGN in roles["staff"]            # override applied
    assert rbac.ASSIGN not in roles["resident"]     # untouched default


def test_oem_upsert_and_delete_override_via_api(client, roles_in_soc1):
    _, tok = roles_in_soc1
    # PUT (admin has MODIFY_CONFIG)
    r = client.put(
        "/api/v1/admin/permissions/overrides",
        json={"role": "staff", "permission": rbac.ASSIGN, "granted": True},
        headers=tok["admin"],
    )
    assert r.status_code == 200
    # show in list
    rows = client.get(
        "/api/v1/admin/permissions/overrides", headers=tok["admin"]
    ).json()
    assert any(r["role"] == "staff" and r["permission"] == rbac.ASSIGN
               for r in rows)
    # DELETE
    r = client.delete(
        f"/api/v1/admin/permissions/overrides"
        f"?role=staff&permission={rbac.ASSIGN}",
        headers=tok["admin"],
    )
    assert r.status_code == 200 and r.json()["cleared"] == 1


def test_oem_cross_society_requires_admin(client, roles_in_soc1):
    _, tok = roles_in_soc1
    # create society 2
    with get_conn() as conn:
        conn.execute("INSERT INTO societies (name) VALUES ('Soc2')")
        sid2 = dict(
            conn.execute(
                "SELECT id FROM societies ORDER BY id DESC LIMIT 1"
            ).fetchone()
        )["id"]

    # manager in soc1 has MODIFY_CONFIG by default, but cannot manage soc2
    r = client.put(
        f"/api/v1/admin/permissions/overrides?society_id={sid2}",
        json={"role": "staff", "permission": rbac.ASSIGN, "granted": True},
        headers=tok["manager"],
    )
    # manager doesn't have modify_config by default either -> 403
    # (either way, must NOT succeed)
    assert r.status_code == 403

    # admin can target any society
    r = client.put(
        f"/api/v1/admin/permissions/overrides?society_id={sid2}",
        json={"role": "staff", "permission": rbac.ASSIGN, "granted": True},
        headers=tok["admin"],
    )
    assert r.status_code == 200


def test_override_db_failure_falls_back_to_default(client, roles_in_soc1,
                                                    monkeypatch):
    """If the overrides table query throws, has_permission must not
    crash the request — it falls back to the default matrix."""
    sid, _ = roles_in_soc1

    def boom(*a, **k):
        raise RuntimeError("simulated DB outage")

    # Patch get_conn at the rbac call site
    monkeypatch.setattr("app.services.rbac.get_conn", boom, raising=False)
    # default: staff lacks ASSIGN -> still False (no crash)
    assert rbac.has_permission("staff", rbac.ASSIGN, sid) is False
    # default: manager has ASSIGN -> still True
    assert rbac.has_permission("manager", rbac.ASSIGN, sid) is True
