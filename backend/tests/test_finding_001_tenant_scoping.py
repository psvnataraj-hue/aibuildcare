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


# --------------------------------------------------------------------
# shared multi-society fixture
# --------------------------------------------------------------------
@pytest.fixture()
def two_socs(client):
    """Society 1 (seed) + society 2, each with a tenant `admin` user
    and a contractor. Plus the seeded platform_operator. Returns a
    dict of (sid1, sid2, h_admin1, h_admin2, h_operator)."""
    with get_conn() as conn:
        sid1 = dict(
            conn.execute(
                "SELECT id FROM societies ORDER BY id LIMIT 1"
            ).fetchone()
        )["id"]
        conn.execute(
            "INSERT INTO societies (name, address) VALUES (?,?)",
            ("Society Two", "Elsewhere"),
        )
        sid2 = dict(
            conn.execute(
                "SELECT id FROM societies ORDER BY id DESC LIMIT 1"
            ).fetchone()
        )["id"]
        # a tenant-scoped admin in each society
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, role, "
            "society_id, is_active) VALUES (?,?,?,?,?,1)",
            ("admin1@s.com", hash_password(PW), "Admin One", "admin", sid1),
        )
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, role, "
            "society_id, is_active) VALUES (?,?,?,?,?,1)",
            ("admin2@s.com", hash_password(PW), "Admin Two", "admin", sid2),
        )
        # a contractor in each society
        conn.execute(
            "INSERT INTO contractors (name, specialty, society_id, "
            "is_active) VALUES (?,?,?,1)",
            ("Soc2 Plumber", "Plumbing", sid2),
        )
    return {
        "sid1": sid1,
        "sid2": sid2,
        "h_admin1": _login(client, "admin1@s.com"),
        "h_admin2": _login(client, "admin2@s.com"),
        "h_operator": _login(client, "admin@aibuildcare.app"),
    }


def _make(client, h, text):
    r = client.post(
        "/api/v1/complaints", json={"raw_text": text}, headers=h
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# --------------------------------------------------------------------
# leak #1 — GET /api/v1/analytics
# --------------------------------------------------------------------
def test_analytics_is_society_scoped(client, two_socs):
    """A tenant admin sees only their own society's complaint counts."""
    _make(client, two_socs["h_admin1"], "soc1 lift broken")
    _make(client, two_socs["h_admin1"], "soc1 water leak")
    _make(client, two_socs["h_admin2"], "soc2 power cut")

    a1 = client.get(
        "/api/v1/analytics", headers=two_socs["h_admin1"]
    ).json()
    a2 = client.get(
        "/api/v1/analytics", headers=two_socs["h_admin2"]
    ).json()
    assert a1["total"] == 2
    assert a2["total"] == 1


def test_analytics_operator_sees_global_and_can_target(client, two_socs):
    """platform_operator: no ?society_id= = global; ?society_id=N
    targets one tenant."""
    _make(client, two_socs["h_admin1"], "soc1 a")
    _make(client, two_socs["h_admin1"], "soc1 b")
    _make(client, two_socs["h_admin2"], "soc2 a")

    g = client.get(
        "/api/v1/analytics", headers=two_socs["h_operator"]
    ).json()
    assert g["total"] == 3  # global view across all tenants

    scoped = client.get(
        f"/api/v1/analytics?society_id={two_socs['sid2']}",
        headers=two_socs["h_operator"],
    ).json()
    assert scoped["total"] == 1


# --------------------------------------------------------------------
# leaks #2-7 — contractor endpoints
# --------------------------------------------------------------------
def _con_ids(rows):
    return {r["id"] for r in rows}


def test_contractors_list_is_society_scoped(client, two_socs):
    """leak #2: GET /contractors. The seed contractors (ids 1-4) are
    in society 1; the fixture adds 'Soc2 Plumber' in society 2."""
    list1 = client.get(
        "/api/v1/contractors", headers=two_socs["h_admin1"]
    ).json()
    list2 = client.get(
        "/api/v1/contractors", headers=two_socs["h_admin2"]
    ).json()
    names1 = {c["name"] for c in list1}
    names2 = {c["name"] for c in list2}
    assert "Soc2 Plumber" not in names1
    assert names2 == {"Soc2 Plumber"}
    # platform_operator sees all
    glob = client.get(
        "/api/v1/contractors", headers=two_socs["h_operator"]
    ).json()
    assert "Soc2 Plumber" in {c["name"] for c in glob}


def test_contractors_summary_is_society_scoped(client, two_socs):
    """leak #3: GET /contractors/analytics/summary."""
    s1 = client.get(
        "/api/v1/contractors/analytics/summary",
        headers=two_socs["h_admin1"],
    ).json()
    s2 = client.get(
        "/api/v1/contractors/analytics/summary",
        headers=two_socs["h_admin2"],
    ).json()
    # society 1 has the 4 seed contractors; society 2 has exactly 1
    assert s1["total_contractors"] == 4
    assert s2["total_contractors"] == 1


def test_contractor_analytics_cross_society_is_404(client, two_socs):
    """leak #4: GET /contractors/{cid}/analytics. Society 1's admin
    must not read society 2's contractor."""
    with get_conn() as conn:
        cid2 = dict(
            conn.execute(
                "SELECT id FROM contractors WHERE name = ?",
                ("Soc2 Plumber",),
            ).fetchone()
        )["id"]
    # admin1 cannot see society 2's contractor
    assert client.get(
        f"/api/v1/contractors/{cid2}/analytics",
        headers=two_socs["h_admin1"],
    ).status_code == 404
    # society 2's own admin can
    assert client.get(
        f"/api/v1/contractors/{cid2}/analytics",
        headers=two_socs["h_admin2"],
    ).status_code == 200
    # platform_operator can
    assert client.get(
        f"/api/v1/contractors/{cid2}/analytics",
        headers=two_socs["h_operator"],
    ).status_code == 200


def test_contractors_by_category_is_society_scoped(client, two_socs):
    """leak #5: GET /contractors/by-category."""
    r1 = client.get(
        "/api/v1/contractors/by-category?category=Plumbing",
        headers=two_socs["h_admin1"],
    ).json()
    r2 = client.get(
        "/api/v1/contractors/by-category?category=Plumbing",
        headers=two_socs["h_admin2"],
    ).json()
    assert "Soc2 Plumber" not in {c["name"] for c in r1}
    assert {c["name"] for c in r2} == {"Soc2 Plumber"}


def test_contractor_performance_is_society_scoped(client, two_socs):
    """leak #6/#7: GET /contractors/performance and
    /contractors/{cid}/performance."""
    perf1 = client.get(
        "/api/v1/contractors/performance", headers=two_socs["h_admin1"]
    ).json()
    perf2 = client.get(
        "/api/v1/contractors/performance", headers=two_socs["h_admin2"]
    ).json()
    assert "Soc2 Plumber" not in {p["name"] for p in perf1}
    assert {p["name"] for p in perf2} == {"Soc2 Plumber"}
    # cross-society single-contractor performance is 404
    with get_conn() as conn:
        cid2 = dict(
            conn.execute(
                "SELECT id FROM contractors WHERE name = ?",
                ("Soc2 Plumber",),
            ).fetchone()
        )["id"]
    assert client.get(
        f"/api/v1/contractors/{cid2}/performance",
        headers=two_socs["h_admin1"],
    ).status_code == 404
    assert client.get(
        f"/api/v1/contractors/{cid2}/performance",
        headers=two_socs["h_admin2"],
    ).status_code == 200


# --------------------------------------------------------------------
# leak #8 — GET/POST /api/v1/admin/config — global infra config,
# gated to platform_operator only
# --------------------------------------------------------------------
def test_admin_config_get_requires_platform_operator(client, two_socs):
    """system_config is GLOBAL infra config — a tenant admin must not
    read it. Only platform_operator may."""
    # tenant admin -> 403
    assert client.get(
        "/api/v1/admin/config", headers=two_socs["h_admin1"]
    ).status_code == 403
    # platform_operator -> 200
    assert client.get(
        "/api/v1/admin/config", headers=two_socs["h_operator"]
    ).status_code == 200


def test_admin_config_post_requires_platform_operator(client, two_socs):
    """Writing global infra config is platform_operator-only."""
    assert client.post(
        "/api/v1/admin/config/some_key", json={"value": "1"},
        headers=two_socs["h_admin1"],
    ).status_code == 403
    assert client.post(
        "/api/v1/admin/config/some_key", json={"value": "1"},
        headers=two_socs["h_operator"],
    ).status_code == 200
