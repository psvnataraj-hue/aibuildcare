"""Finding 001 — cross-tenant data leak remediation.

`admin` is now tenant-scoped; `platform_operator` is the cross-tenant
role. Every formerly-global endpoint is society-scoped at the
query/router layer. A `platform_operator` may target any tenant via
`?society_id=`; omitting it = global view. Every other role is pinned
to its own society.
"""
import pytest

from app.db import get_conn
from app.security import hash_password

PW = "Secret!123"


def _login(client, email: str, password: str = PW) -> dict:
    r = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --------------------------------------------------------------------
# seed.py — the seeded operator is platform_operator, bound to society 1
# --------------------------------------------------------------------
def test_seeded_admin_is_platform_operator(client):
    """The seeded admin@aibuildcare.app is the cross-tenant operator."""
    with get_conn() as conn:
        row = dict(
            conn.execute(
                "SELECT role, society_id FROM users WHERE email = ?",
                ("admin@aibuildcare.app",),
            ).fetchone()
        )
    assert row["role"] == "platform_operator"
    # critical: it stays BOUND to society 1 (non-NULL) so the test
    # suite's current_society endpoints keep working.
    assert row["society_id"] == 1


# --------------------------------------------------------------------
# deps.target_society — cross-tenant targeting dependency
# --------------------------------------------------------------------
def test_target_society_normal_role_returns_own_ignores_query():
    """A non-operator role gets its own society_id; any ?society_id=
    query param is ignored."""
    from app.deps import target_society

    user = {"role": "manager", "society_id": 7}
    assert target_society(society_id=None, user=user) == 7
    # query param ignored — cannot escape its own tenant
    assert target_society(society_id=999, user=user) == 7


def test_target_society_normal_role_no_society_403():
    """A non-operator role with no society_id is rejected (403)."""
    from fastapi import HTTPException

    from app.deps import target_society

    user = {"role": "manager", "society_id": None}
    with pytest.raises(HTTPException) as ei:
        target_society(society_id=None, user=user)
    assert ei.value.status_code == 403


def test_target_society_operator_targets_any_or_global():
    """platform_operator: ?society_id=N targets tenant N; omitting it
    returns None = 'all societies' global view."""
    from app.deps import target_society

    operator = {"role": "platform_operator", "society_id": 1}
    assert target_society(society_id=42, user=operator) == 42
    assert target_society(society_id=None, user=operator) is None
