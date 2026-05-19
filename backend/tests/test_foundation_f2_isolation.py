"""Foundation F2 — cross-society isolation (the merge gate).

Two societies, two admins. Each token must see/act on ONLY its own
society's complaints. Any cross-society read or mutation must behave
as 'not found' (no data, no leak, no info via error shape).
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


@pytest.fixture()
def two_societies(client):
    """Seed admin is society 1 (Phase-1 backfill). Add society 2 + its
    admin. Returns (h1, h2) auth headers."""
    with get_conn() as conn:
        s1 = dict(
            conn.execute(
                "SELECT id FROM societies ORDER BY id LIMIT 1"
            ).fetchone()
        )["id"]
        conn.execute(
            "INSERT INTO societies (name, address) VALUES (?,?)",
            ("Society Two", "Elsewhere"),
        )
        s2 = dict(
            conn.execute(
                "SELECT id FROM societies ORDER BY id DESC LIMIT 1"
            ).fetchone()
        )["id"]
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, role, "
            "society_id, is_active) VALUES (?,?,?,?,?,1)",
            ("boss2@x.com", hash_password(PW), "Boss Two", "admin", s2),
        )
    assert s1 != s2
    h1 = _login(client, "admin@aibuildcare.app")
    h2 = _login(client, "boss2@x.com")
    return h1, h2


def _make(client, h, text):
    r = client.post(
        "/api/v1/complaints", json={"raw_text": text}, headers=h
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_list_is_scoped_to_own_society(client, two_societies):
    h1, h2 = two_societies
    c1 = _make(client, h1, "society one lift broken 1A")
    c2 = _make(client, h2, "society two water leak 2B")

    ids1 = {c["id"] for c in client.get(
        "/api/v1/complaints", headers=h1).json()}
    ids2 = {c["id"] for c in client.get(
        "/api/v1/complaints", headers=h2).json()}

    assert c1 in ids1 and c2 not in ids1
    assert c2 in ids2 and c1 not in ids2


def test_cross_society_get_is_404(client, two_societies):
    h1, h2 = two_societies
    c1 = _make(client, h1, "soc1 only")
    assert client.get(f"/api/v1/complaints/{c1}", headers=h2
                       ).status_code == 404
    assert client.get(f"/api/v1/complaints/{c1}", headers=h1
                       ).status_code == 200


def test_cross_society_mutations_blocked(client, two_societies):
    h1, h2 = two_societies
    c1 = _make(client, h1, "soc1 status test")

    # status / message / rate from the WRONG society must not work
    assert client.post(
        f"/api/v1/complaints/{c1}/status",
        json={"status": "acknowledged"}, headers=h2,
    ).status_code in (400, 404)
    assert client.post(
        f"/api/v1/complaints/{c1}/messages",
        json={"sender": "staff", "body": "intruder note"}, headers=h2,
    ).status_code == 404
    assert client.get(
        f"/api/v1/complaints/{c1}/messages", headers=h2
    ).json() == []

    # owner can still operate normally
    assert client.post(
        f"/api/v1/complaints/{c1}/status",
        json={"status": "acknowledged"}, headers=h1,
    ).status_code == 200


def test_cross_society_assign_blocked(client, two_societies):
    h1, h2 = two_societies
    c1 = _make(client, h1, "soc1 assign test")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO contractors (name, specialty, is_active) "
            "VALUES (?,?,1)",
            ("X", "Plumbing"),
        )
        ctr = dict(
            conn.execute(
                "SELECT id FROM contractors ORDER BY id DESC LIMIT 1"
            ).fetchone()
        )["id"]
    assert client.post(
        f"/api/v1/complaints/{c1}/assign",
        json={"contractor_id": ctr}, headers=h2,
    ).status_code == 404
