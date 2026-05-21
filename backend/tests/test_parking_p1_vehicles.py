"""Parking P1: vehicles registry — CRUD + society-scoping + RBAC +
plate normalisation + soft-delete semantics.

Backend-only PR. Frontend (P5) lands later; the parking complaint
auto-link path is P2.
"""
from unittest.mock import MagicMock

from app.db import get_conn
from app.security import hash_password


# ---------- shared fixtures (in-line, not via conftest) -------------

def _add_society(name: str) -> int:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO societies (name, address) VALUES (?,?)",
            (name, "test addr"),
        )
        return dict(conn.execute(
            "SELECT id FROM societies ORDER BY id DESC LIMIT 1"
        ).fetchone())["id"]


def _add_user(email: str, password: str, role: str,
              society_id: int = 1) -> int:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, role, "
            "society_id, is_active) VALUES (?,?,?,?,?,1)",
            (email, hash_password(password), email.split("@")[0],
             role, society_id),
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


# ---------- happy path: create + list + get + update + soft-delete --

def test_create_minimal(client, auth_header):
    r = client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH01AB1234"},
        headers=auth_header,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["plate_number"] == "MH01AB1234"
    assert body["society_id"] == 1
    assert body["active"] is True
    assert body["owner_name"] is None
    assert "id" in body


def test_create_full(client, auth_header):
    r = client.post(
        "/api/v1/vehicles",
        json={
            "plate_number": "MH-02-XY-9999",  # whitespace + dashes
            "owner_unit_number": "5B",
            "owner_name": "Mr Resident",
            "owner_phone": "+919833000111",
            "vehicle_type": "car",
            "make_model": "Maruti Swift",
            "color": "blue",
            "notes": "compound parking spot 12",
        },
        headers=auth_header,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # plate stored normalised: stripped + uppercased
    assert body["plate_number"] == "MH02XY9999"
    assert body["owner_unit_number"] == "5B"
    assert body["vehicle_type"] == "car"


def test_list_orders_by_plate(client, auth_header):
    for p in ["MH99ZZ0001", "MH01AA0001", "MH50KK0001"]:
        client.post(
            "/api/v1/vehicles",
            json={"plate_number": p},
            headers=auth_header,
        )
    r = client.get("/api/v1/vehicles", headers=auth_header)
    assert r.status_code == 200
    plates = [v["plate_number"] for v in r.json()]
    assert plates == sorted(plates)


def test_get_by_id(client, auth_header):
    c = client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH09EE1212"},
        headers=auth_header,
    ).json()
    r = client.get(
        f"/api/v1/vehicles/{c['id']}", headers=auth_header,
    )
    assert r.status_code == 200
    assert r.json()["plate_number"] == "MH09EE1212"


def test_get_by_id_404(client, auth_header):
    r = client.get("/api/v1/vehicles/9999", headers=auth_header)
    assert r.status_code == 404


def test_update_owner_name(client, auth_header):
    c = client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH10FG1111"},
        headers=auth_header,
    ).json()
    r = client.put(
        f"/api/v1/vehicles/{c['id']}",
        json={"owner_name": "Updated Owner"},
        headers=auth_header,
    )
    assert r.status_code == 200
    assert r.json()["owner_name"] == "Updated Owner"


def test_update_plate_normalises(client, auth_header):
    c = client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH11HH2222"},
        headers=auth_header,
    ).json()
    r = client.put(
        f"/api/v1/vehicles/{c['id']}",
        json={"plate_number": "mh 11-hh-3333"},
        headers=auth_header,
    )
    assert r.status_code == 200
    assert r.json()["plate_number"] == "MH11HH3333"


def test_deactivate_then_reactivate(client, auth_header):
    c = client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH12II4444"},
        headers=auth_header,
    ).json()
    r = client.delete(
        f"/api/v1/vehicles/{c['id']}", headers=auth_header,
    )
    assert r.status_code == 200
    assert r.json()["active"] is False

    # list defaults to active-only -> not shown
    plates = [
        v["plate_number"] for v in
        client.get("/api/v1/vehicles", headers=auth_header).json()
    ]
    assert "MH12II4444" not in plates

    # include_inactive=true -> shown
    r2 = client.get(
        "/api/v1/vehicles?include_inactive=true",
        headers=auth_header,
    )
    plates2 = [v["plate_number"] for v in r2.json()]
    assert "MH12II4444" in plates2

    # reactivate
    r3 = client.put(
        f"/api/v1/vehicles/{c['id']}",
        json={"active": True},
        headers=auth_header,
    )
    assert r3.status_code == 200
    assert r3.json()["active"] is True


# ---------- uniqueness ---------------------------------------------

def test_duplicate_plate_in_same_society_409(client, auth_header):
    client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH13JJ5555"},
        headers=auth_header,
    )
    r = client.post(
        "/api/v1/vehicles",
        json={"plate_number": "mh-13-jj-5555"},  # same after normalisation
        headers=auth_header,
    )
    assert r.status_code == 409
    assert "already registered" in r.json()["detail"]


def test_update_plate_to_existing_plate_409(client, auth_header):
    a = client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH14KK1111"},
        headers=auth_header,
    ).json()
    client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH14KK2222"},
        headers=auth_header,
    )
    r = client.put(
        f"/api/v1/vehicles/{a['id']}",
        json={"plate_number": "MH14KK2222"},
        headers=auth_header,
    )
    assert r.status_code == 409


def test_update_plate_to_same_value_ok(client, auth_header):
    """Editing other fields without changing the plate must not trip
    the uniqueness check against the row's own plate."""
    c = client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH15LL3333"},
        headers=auth_header,
    ).json()
    r = client.put(
        f"/api/v1/vehicles/{c['id']}",
        json={"plate_number": "MH15LL3333", "color": "red"},
        headers=auth_header,
    )
    assert r.status_code == 200
    assert r.json()["color"] == "red"


# ---------- society scoping ----------------------------------------

def test_society_scoping_list(client, auth_header):
    """A vehicle in society 2 is invisible to a society 1 caller."""
    soc2 = _add_society("Other Society")
    # insert directly into society 2
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO vehicles (society_id, plate_number) VALUES (?,?)",
            (soc2, "MH99CROSS"),
        )
    r = client.get("/api/v1/vehicles", headers=auth_header)
    plates = [v["plate_number"] for v in r.json()]
    assert "MH99CROSS" not in plates


def test_society_scoping_get(client, auth_header):
    soc2 = _add_society("Society 2")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO vehicles (society_id, plate_number) VALUES (?,?)",
            (soc2, "MH88CROSS"),
        )
        row = dict(conn.execute(
            "SELECT id FROM vehicles WHERE plate_number = ?",
            ("MH88CROSS",),
        ).fetchone())
    # GET by id from society 1 caller -> 404
    r = client.get(
        f"/api/v1/vehicles/{row['id']}", headers=auth_header,
    )
    assert r.status_code == 404


# ---------- RBAC ----------------------------------------------------

def test_resident_cannot_create(client):
    _add_user("alice@p.example", "Pass!1", "resident")
    h = _login(client, "alice@p.example", "Pass!1")
    r = client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH77RES1111"},
        headers=h,
    )
    assert r.status_code == 403


def test_resident_cannot_read(client):
    """resident has neither VIEW_ALL nor MODIFY_STAFF."""
    _add_user("bob@p.example", "Pass!1", "resident")
    h = _login(client, "bob@p.example", "Pass!1")
    r = client.get("/api/v1/vehicles", headers=h)
    assert r.status_code == 403


def test_viewer_can_read_cannot_write(client, auth_header):
    """viewer has VIEW_ALL but not MODIFY_STAFF."""
    _add_user("v@p.example", "Pass!1", "viewer")
    # admin seeds a vehicle first
    client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH66VV1111"},
        headers=auth_header,
    )
    h = _login(client, "v@p.example", "Pass!1")
    # viewer can list
    assert client.get(
        "/api/v1/vehicles", headers=h,
    ).status_code == 200
    # viewer cannot create
    assert client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH66VV2222"},
        headers=h,
    ).status_code == 403


def test_manager_can_create_and_update(client):
    """manager has MODIFY_STAFF -> full vehicle CRUD."""
    _add_user("m@p.example", "Pass!1", "manager")
    h = _login(client, "m@p.example", "Pass!1")
    r = client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH55MM3333"},
        headers=h,
    )
    assert r.status_code == 201
    r2 = client.put(
        f"/api/v1/vehicles/{r.json()['id']}",
        json={"owner_name": "Manager Edit"},
        headers=h,
    )
    assert r2.status_code == 200
    assert r2.json()["owner_name"] == "Manager Edit"


# ---------- validation ---------------------------------------------

def test_create_empty_plate_400(client, auth_header):
    r = client.post(
        "/api/v1/vehicles",
        json={"plate_number": "   "},
        headers=auth_header,
    )
    assert r.status_code == 400


def test_create_unknown_vehicle_type_400(client, auth_header):
    r = client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH44NN1111", "vehicle_type": "submarine"},
        headers=auth_header,
    )
    assert r.status_code == 400
    assert "vehicle_type" in r.json()["detail"]


def test_create_vehicle_type_normalised_to_lower(client, auth_header):
    r = client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH33OO1111", "vehicle_type": "CAR"},
        headers=auth_header,
    )
    assert r.status_code == 201
    assert r.json()["vehicle_type"] == "car"


# ---------- /by-plate lookup helper ---------------------------------

def test_by_plate_lookup(client, auth_header):
    c = client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH22PP1111", "owner_name": "Found Owner"},
        headers=auth_header,
    ).json()
    r = client.get(
        "/api/v1/vehicles/by-plate?plate=mh-22-pp-1111",
        headers=auth_header,
    )
    assert r.status_code == 200
    assert r.json()["id"] == c["id"]
    assert r.json()["owner_name"] == "Found Owner"


def test_by_plate_404_when_missing(client, auth_header):
    r = client.get(
        "/api/v1/vehicles/by-plate?plate=XX99NOTHING",
        headers=auth_header,
    )
    assert r.status_code == 404


def test_by_plate_skips_inactive(client, auth_header):
    """find_by_plate is the future P2 auto-link entry point; we don't
    want it to surface deactivated owners."""
    c = client.post(
        "/api/v1/vehicles",
        json={"plate_number": "MH21QQ1111"},
        headers=auth_header,
    ).json()
    client.delete(
        f"/api/v1/vehicles/{c['id']}", headers=auth_header,
    )
    r = client.get(
        "/api/v1/vehicles/by-plate?plate=MH21QQ1111",
        headers=auth_header,
    )
    assert r.status_code == 404


# ---------- search filter -------------------------------------------

def test_list_plate_search_filters(client, auth_header):
    for p in ["MH01ABC123", "MH01XYZ999", "DL77ABC123"]:
        client.post(
            "/api/v1/vehicles",
            json={"plate_number": p},
            headers=auth_header,
        )
    r = client.get(
        "/api/v1/vehicles?plate_search=mh01",
        headers=auth_header,
    )
    plates = [v["plate_number"] for v in r.json()]
    assert set(plates) == {"MH01ABC123", "MH01XYZ999"}
