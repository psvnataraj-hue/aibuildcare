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
