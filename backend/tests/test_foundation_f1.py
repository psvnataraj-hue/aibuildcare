"""Foundation F1: RBAC matrix + current_society()/require() deps.

Behaviour-neutral scaffolding (not yet wired into product endpoints).
"""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.deps import current_society, current_user, require
from app.services import rbac


# ---- permission matrix ----------------------------------------------
def test_matrix_resident_minimal():
    assert rbac.has_permission("resident", rbac.FILE_COMPLAINT)
    assert rbac.has_permission("resident", rbac.VIEW_OWN)
    assert not rbac.has_permission("resident", rbac.VIEW_ALL)
    assert not rbac.has_permission("resident", rbac.ASSIGN)


def test_matrix_staff_can_resolve_not_assign():
    assert rbac.has_permission("staff", rbac.RESOLVE)
    assert not rbac.has_permission("staff", rbac.ASSIGN)
    assert not rbac.has_permission("staff", rbac.ESCALATE)


def test_matrix_manager_assigns_but_no_enforcement():
    assert rbac.has_permission("manager", rbac.ASSIGN)
    assert rbac.has_permission("manager", rbac.MODIFY_STAFF)
    assert not rbac.has_permission("manager", rbac.AUTHORIZE_ENFORCEMENT)
    assert not rbac.has_permission("manager", rbac.MODIFY_CONFIG)


@pytest.mark.parametrize("role", ["sr_manager", "secretary", "chairman"])
def test_matrix_leaders_full_authority(role):
    for p in (rbac.AUTHORIZE_ENFORCEMENT, rbac.MODIFY_CONFIG,
              rbac.APPROVE_REPORTS, rbac.VIEW_FINANCIAL, rbac.ASSIGN):
        assert rbac.has_permission(role, p)


def test_matrix_committee_decides_not_modifies():
    assert rbac.has_permission("committee_member", rbac.AUTHORIZE_ENFORCEMENT)
    assert rbac.has_permission("committee_member", rbac.APPROVE_REPORTS)
    assert not rbac.has_permission("committee_member", rbac.MODIFY_STAFF)
    assert not rbac.has_permission("committee_member", rbac.MODIFY_CONFIG)


def test_matrix_viewer_readonly_admin_all_unknown_none():
    assert rbac.has_permission("viewer", rbac.VIEW_ALL)
    assert not rbac.has_permission("viewer", rbac.RESOLVE)
    assert all(rbac.has_permission("admin", p) for p in rbac.ALL_PERMISSIONS)
    assert not rbac.has_permission("nonsense", rbac.VIEW_OWN)
    assert not rbac.has_permission(None, rbac.VIEW_OWN)


# ---- deps: current_society + require ---------------------------------
def _client(user: dict) -> TestClient:
    app = FastAPI()

    @app.get("/soc")
    def soc(sid: int = Depends(current_society)):
        return {"sid": sid}

    @app.get("/assign-only")
    def assign_only(u: dict = Depends(require(rbac.ASSIGN))):
        return {"ok": True}

    app.dependency_overrides[current_user] = lambda: user
    return TestClient(app)


def test_current_society_returns_bound_id():
    c = _client({"role": "manager", "society_id": 7})
    assert c.get("/soc").json() == {"sid": 7}


def test_current_society_403_when_unbound():
    c = _client({"role": "manager", "society_id": None})
    assert c.get("/soc").status_code == 403


def test_require_allows_authorized_role():
    c = _client({"role": "manager", "society_id": 1})
    assert c.get("/assign-only").status_code == 200


def test_require_blocks_unauthorized_role():
    c = _client({"role": "staff", "society_id": 1})
    r = c.get("/assign-only")
    assert r.status_code == 403
    assert "lacks 'assign'" in r.json()["detail"]
