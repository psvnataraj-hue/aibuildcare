"""B4 (Gemini audit): residents can no longer rate complaints they
did NOT file.

The /rate endpoint is gated only by FILE_COMPLAINT in the RBAC matrix,
which residents have — so before this patch a resident could rate any
complaint whose id they could guess, poisoning analytics. The fix
checks reporter_email against the calling user's email when role is
'resident'; staff/admin/managers stay unaffected (they're moderating,
not creating fake ratings).
"""
from app.db import get_conn
from app.security import hash_password


RESIDENT_EMAIL = "alice.resident@palms.example"
RESIDENT_PWD = "Resident!123"


def _seed_resident(
    email: str = RESIDENT_EMAIL, password: str = RESIDENT_PWD,
) -> int:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, role, "
            "society_id, is_active) VALUES (?,?,?,?,?,1)",
            (email, hash_password(password), "Alice Resident",
             "resident", 1),
        )
        return dict(conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone())["id"]


def _login(client, email: str, password: str) -> dict:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_complaint_with_reporter(
    client, admin_headers, reporter_email: str | None,
) -> int:
    """Use admin to create + resolve a complaint, then patch the
    reporter_email directly (the dashboard /complaints POST schema
    doesn't take reporter_email as a body field for residents)."""
    r = client.post(
        "/api/v1/complaints",
        json={"raw_text": "5B nal leak"},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    # mark resolved so rate is allowed by the existing service-layer
    # status guard
    for s in ("acknowledged", "assigned", "in_progress", "resolved"):
        sr = client.post(
            f"/api/v1/complaints/{cid}/status",
            json={"status": s}, headers=admin_headers,
        )
        assert sr.status_code == 200, sr.text
    with get_conn() as conn:
        conn.execute(
            "UPDATE complaints SET reporter_email = ? WHERE id = ?",
            (reporter_email, cid),
        )
    return cid


def test_resident_can_rate_own_complaint(client, auth_header):
    _seed_resident()
    cid = _create_complaint_with_reporter(client, auth_header, RESIDENT_EMAIL)
    rh = _login(client, RESIDENT_EMAIL, RESIDENT_PWD)
    r = client.post(
        f"/api/v1/complaints/{cid}/rate",
        json={"rating": 5, "feedback": "great"},
        headers=rh,
    )
    assert r.status_code == 200, r.text
    assert r.json()["rating"] == 5


def test_resident_cannot_rate_others_complaint(client, auth_header):
    _seed_resident()
    cid = _create_complaint_with_reporter(
        client, auth_header, "someone.else@palms.example",
    )
    rh = _login(client, RESIDENT_EMAIL, RESIDENT_PWD)
    r = client.post(
        f"/api/v1/complaints/{cid}/rate",
        json={"rating": 1, "feedback": "trolling"},
        headers=rh,
    )
    assert r.status_code == 403
    assert "own" in r.json()["detail"].lower()


def test_resident_cannot_rate_null_reporter_email(client, auth_header):
    """A complaint with reporter_email=NULL (e.g. WhatsApp-only intake
    where no email was extractable) is not ownable by any resident."""
    _seed_resident()
    cid = _create_complaint_with_reporter(client, auth_header, None)
    rh = _login(client, RESIDENT_EMAIL, RESIDENT_PWD)
    r = client.post(
        f"/api/v1/complaints/{cid}/rate",
        json={"rating": 5, "feedback": "x"}, headers=rh,
    )
    assert r.status_code == 403


def test_admin_can_still_rate_any(client, auth_header):
    """Regression: the seed admin user (role='admin') was always
    allowed to rate; that path must keep working untouched."""
    cid = _create_complaint_with_reporter(
        client, auth_header, "someone.else@palms.example",
    )
    r = client.post(
        f"/api/v1/complaints/{cid}/rate",
        json={"rating": 4, "feedback": "ok"},
        headers=auth_header,
    )
    assert r.status_code == 200, r.text
    assert r.json()["rating"] == 4
