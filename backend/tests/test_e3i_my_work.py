"""E3i: GET /api/v1/complaints/mine — staff mobile work-list.

Links calling user's email to a staff_members row (case-insensitive)
and returns the complaints currently assigned to that staff_member.
Used by the /my-work mobile-first page so a 'staff' RBAC role (which
lacks VIEW_ALL) can still see what they need to act on.
"""
from unittest.mock import MagicMock

from app.db import get_conn
from app.security import hash_password


def _seed_user(email, password, role, society_id=1):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, role, "
            "society_id, is_active) VALUES (?,?,?,?,?,1)",
            (email, hash_password(password), email.split("@")[0],
             role, society_id),
        )


def _seed_staff(name, email, society_id=1, phone="+919000000111"):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO staff_members (society_id, name, "
            "phone_primary, whatsapp_enabled, active, email) "
            "VALUES (?,?,?,1,1,?)",
            (society_id, name, phone, email),
        )
        return dict(conn.execute(
            "SELECT id FROM staff_members ORDER BY id DESC LIMIT 1"
        ).fetchone())["id"]


def _login(client, email, password):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_and_assign(client, auth_header, staff_id,
                       raw_text="5B nal leak"):
    """Admin creates a complaint and assigns it to a staff member."""
    r = client.post(
        "/api/v1/complaints", json={"raw_text": raw_text},
        headers=auth_header,
    )
    assert r.status_code == 201
    cid = r.json()["id"]
    r2 = client.post(
        f"/api/v1/complaints/{cid}/assign",
        json={"staff_id": staff_id}, headers=auth_header,
    )
    assert r2.status_code == 200, r2.text
    return cid


def test_mine_empty_when_no_staff_record(client):
    """A user with role='staff' but no matching staff_members row
    sees an empty list + null staff (the UI should explain)."""
    _seed_user("orphan@p.example", "Pass!1", "staff")
    h = _login(client, "orphan@p.example", "Pass!1")
    r = client.get("/api/v1/complaints/mine", headers=h)
    assert r.status_code == 200
    assert r.json() == {"staff": None, "complaints": []}


def test_mine_returns_assigned_complaints(client, auth_header,
                                          monkeypatch):
    """When the staff_members row exists and has assignments, they're
    returned."""
    monkeypatch.setattr(
        "app.routers.complaints.send_whatsapp",
        MagicMock(return_value=True),
    )
    sid = _seed_staff("Ramesh", "ramesh@p.example")
    _seed_user("ramesh@p.example", "Pass!1", "staff")
    # admin assigns two complaints to Ramesh
    cid1 = _create_and_assign(client, auth_header, sid, "5B nal leak")
    cid2 = _create_and_assign(client, auth_header, sid, "12A nal toot")

    h = _login(client, "ramesh@p.example", "Pass!1")
    r = client.get("/api/v1/complaints/mine", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["staff"]["name"] == "Ramesh"
    ids = [c["id"] for c in body["complaints"]]
    assert set(ids) == {cid1, cid2}


def test_mine_email_match_case_insensitive(client, auth_header,
                                            monkeypatch):
    """User email matches staff_members email case-insensitively.
    The user is seeded lowercase (Pydantic EmailStr normalises the
    login payload). The staff_members row stores mixed-case email,
    proving the LOOKUP normalises both sides."""
    monkeypatch.setattr(
        "app.routers.complaints.send_whatsapp",
        MagicMock(return_value=True),
    )
    sid = _seed_staff("Alice", "Alice@P.Example")  # mixed-case in DB
    _seed_user("alice@p.example", "Pass!1", "staff")  # lowercase user
    _create_and_assign(client, auth_header, sid)

    h = _login(client, "alice@p.example", "Pass!1")
    r = client.get("/api/v1/complaints/mine", headers=h)
    assert r.status_code == 200
    assert r.json()["staff"]["name"] == "Alice"
    assert len(r.json()["complaints"]) == 1


def test_mine_excludes_resolved_by_default(client, auth_header,
                                            monkeypatch):
    monkeypatch.setattr(
        "app.routers.complaints.send_whatsapp",
        MagicMock(return_value=True),
    )
    sid = _seed_staff("Bob", "bob@p.example")
    _seed_user("bob@p.example", "Pass!1", "staff")
    cid_open = _create_and_assign(client, auth_header, sid)
    cid_done = _create_and_assign(client, auth_header, sid)
    for s in ("in_progress", "resolved"):
        client.post(
            f"/api/v1/complaints/{cid_done}/status",
            json={"status": s}, headers=auth_header,
        )

    h = _login(client, "bob@p.example", "Pass!1")
    r = client.get("/api/v1/complaints/mine", headers=h)
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()["complaints"]]
    assert cid_open in ids
    assert cid_done not in ids  # default excludes resolved

    # but include_resolved=true brings it back
    r2 = client.get(
        "/api/v1/complaints/mine?include_resolved=true", headers=h,
    )
    ids2 = [c["id"] for c in r2.json()["complaints"]]
    assert cid_done in ids2


def test_mine_sorted_urgent_first(client, auth_header, monkeypatch):
    monkeypatch.setattr(
        "app.routers.complaints.send_whatsapp",
        MagicMock(return_value=True),
    )
    sid = _seed_staff("Carol", "carol@p.example")
    _seed_user("carol@p.example", "Pass!1", "staff")
    # urgent first via the keyword in raw_text; then high; then normal
    cid_urgent = _create_and_assign(
        client, auth_header, sid, "5B urgent water leak",
    )
    cid_normal = _create_and_assign(
        client, auth_header, sid, "5B nal leak slow",
    )

    h = _login(client, "carol@p.example", "Pass!1")
    r = client.get("/api/v1/complaints/mine", headers=h)
    rows = r.json()["complaints"]
    assert rows[0]["id"] == cid_urgent
    # the normal one is later in the list (or absent if assignment failed)
    assert any(x["id"] == cid_normal for x in rows)


def test_mine_society_scoped(client, auth_header, monkeypatch):
    """A staff member in society 2 cannot see society 1's assignments
    even if their staff_members row also exists in society 1."""
    monkeypatch.setattr(
        "app.routers.complaints.send_whatsapp",
        MagicMock(return_value=True),
    )
    sid1 = _seed_staff("Dee", "dee@p.example", society_id=1)
    _seed_user("dee@p.example", "Pass!1", "staff", society_id=1)
    # assign a complaint in society 1
    _create_and_assign(client, auth_header, sid1)

    # second society + matching user there
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO societies (name, address) VALUES (?,?)",
            ("Society 2", "addr"),
        )
        soc2 = dict(conn.execute(
            "SELECT id FROM societies ORDER BY id DESC LIMIT 1"
        ).fetchone())["id"]
    _seed_staff("Dee", "dee2@p.example", society_id=soc2)
    _seed_user("dee2@p.example", "Pass!1", "staff", society_id=soc2)

    h2 = _login(client, "dee2@p.example", "Pass!1")
    r = client.get("/api/v1/complaints/mine", headers=h2)
    # society 2's Dee has no assignments
    assert r.status_code == 200
    assert r.json()["complaints"] == []


def test_mine_requires_resolve_permission(client):
    """A 'viewer' role (VIEW_ALL but no RESOLVE) is rejected.
    Read-only roles aren't the audience for this work-list."""
    _seed_user("viewer@p.example", "Pass!1", "viewer")
    h = _login(client, "viewer@p.example", "Pass!1")
    r = client.get("/api/v1/complaints/mine", headers=h)
    assert r.status_code == 403


def test_mine_unauth_401(client):
    r = client.get("/api/v1/complaints/mine")
    assert r.status_code == 401
