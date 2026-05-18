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
