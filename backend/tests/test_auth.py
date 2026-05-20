def test_login_success(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@aibuildcare.app", "password": "Secret!123"},
    )
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_wrong_password(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@aibuildcare.app", "password": "nope"},
    )
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@x.com", "password": "x"},
    )
    assert r.status_code == 401


def test_login_bad_payload(client):
    r = client.post("/api/v1/auth/login", json={"email": "not-an-email"})
    assert r.status_code == 422


def test_protected_requires_token(client):
    assert client.get("/api/v1/complaints").status_code == 401


def test_protected_rejects_bad_token(client):
    r = client.get(
        "/api/v1/complaints",
        headers={"Authorization": "Bearer garbage"},
    )
    assert r.status_code == 401


def test_protected_accepts_valid_token(client, auth_header):
    r = client.get("/api/v1/complaints", headers=auth_header)
    assert r.status_code == 200


def test_token_works_across_requests(client, auth_header):
    assert client.get("/api/v1/analytics", headers=auth_header).status_code == 200
    assert client.get("/api/v1/contractors", headers=auth_header).status_code == 200


# ---- B2 (Gemini audit): real JWT revocation via auth_sessions ------
def _login(client, email="admin@aibuildcare.app", password="Secret!123"):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_logout_revokes_current_token(client):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    # token works
    assert client.get("/api/v1/complaints", headers=headers).status_code == 200
    # logout
    r = client.post("/api/v1/auth/logout", headers=headers)
    assert r.status_code == 204
    # same token now rejected
    assert client.get("/api/v1/complaints", headers=headers).status_code == 401


def test_logout_other_token_still_valid(client):
    """Two independent logins -> two independent auth_sessions rows.
    Revoking one must not invalidate the other."""
    t1 = _login(client)
    t2 = _login(client)
    h1 = {"Authorization": f"Bearer {t1}"}
    h2 = {"Authorization": f"Bearer {t2}"}
    assert client.post("/api/v1/auth/logout", headers=h1).status_code == 204
    assert client.get("/api/v1/complaints", headers=h1).status_code == 401
    assert client.get("/api/v1/complaints", headers=h2).status_code == 200


def test_expired_session_row_rejected(client):
    """A token whose auth_sessions row has expired is rejected even
    if the JWT itself is still within its claim window."""
    from app.db import get_conn

    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/complaints", headers=headers).status_code == 200
    with get_conn() as conn:
        conn.execute(
            "UPDATE auth_sessions SET expires_at = '2000-01-01T00:00:00+00:00'"
        )
    assert client.get("/api/v1/complaints", headers=headers).status_code == 401


def test_token_without_session_row_rejected(client):
    """Cryptographically valid JWT whose auth_sessions row was DELETEd
    (e.g. via /logout, or by admin housekeeping) must be rejected."""
    from app.db import get_conn

    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/complaints", headers=headers).status_code == 200
    with get_conn() as conn:
        conn.execute("DELETE FROM auth_sessions")
    assert client.get("/api/v1/complaints", headers=headers).status_code == 401
