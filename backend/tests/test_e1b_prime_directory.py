"""E1b': resident-facing vendor directory.

Society-scoped, opted-in vendors with click-to-chat WhatsApp links,
gated by FILE_COMPLAINT (so future residents/staff can call it).
"""
import urllib.parse

import pytest

from app.db import get_conn
from app.security import hash_password
from app.services import vendor_directory

PW = "Secret!123"


def _login(client, email: str) -> dict:
    r = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PW}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def vclient(client):
    """Adds a low-priv 'staff' user for permission tests."""
    with get_conn() as conn:
        sid = dict(
            conn.execute(
                "SELECT id FROM societies ORDER BY id LIMIT 1"
            ).fetchone()
        )["id"]
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, "
            "role, society_id, is_active) VALUES (?,?,?,?,?,1)",
            ("staff@s1.com", hash_password(PW), "Staff", "staff", sid),
        )
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, "
            "role, society_id, is_active) VALUES (?,?,?,?,?,1)",
            ("viewer@s1.com", hash_password(PW), "Viewer", "viewer", sid),
        )
    return client, sid, {
        "admin": _login(client, "admin@aibuildcare.app"),
        "staff": _login(client, "staff@s1.com"),
        "viewer": _login(client, "viewer@s1.com"),
    }


# ---- service ---------------------------------------------------------
def test_directory_returns_vetted_vendors_with_walinks(client):
    sid = 1  # default society from seed
    result = vendor_directory.list_vendors(sid, "Plumbing")
    # AquaFix Plumbers is the seeded Plumbing contractor (society 1)
    assert any(v["name"] == "AquaFix Plumbers" for v in result)
    aqua = next(v for v in result if v["name"] == "AquaFix Plumbers")
    assert aqua["wa_link"].startswith("https://wa.me/")
    assert "Plumbing" in urllib.parse.unquote_plus(aqua["wa_link"])


def test_opted_out_vendor_excluded(client):
    with get_conn() as conn:
        # opt the seeded AquaFix out
        conn.execute(
            "UPDATE contractors SET available_for_personal_jobs = 0 "
            "WHERE name = 'AquaFix Plumbers'"
        )
    result = vendor_directory.list_vendors(1, "Plumbing")
    assert not any(v["name"] == "AquaFix Plumbers" for v in result)


def test_society_isolation(client):
    """Vendor in society 2 must not appear in society 1's directory."""
    with get_conn() as conn:
        conn.execute("INSERT INTO societies (name) VALUES ('Soc2')")
        s2 = dict(
            conn.execute(
                "SELECT id FROM societies ORDER BY id DESC LIMIT 1"
            ).fetchone()
        )["id"]
        conn.execute(
            "INSERT INTO contractors (name, phone, specialty, "
            "average_rating, society_id, is_active, "
            "available_for_personal_jobs) "
            "VALUES (?,?,?,?,?,1,1)",
            ("Outsider Plumber", "+919999999999", "Plumbing", 5.0, s2),
        )
    in_s1 = vendor_directory.list_vendors(1, "Plumbing")
    in_s2 = vendor_directory.list_vendors(s2, "Plumbing")
    assert not any(v["name"] == "Outsider Plumber" for v in in_s1)
    assert any(v["name"] == "Outsider Plumber" for v in in_s2)


def test_unknown_category_returns_empty(client):
    assert vendor_directory.list_vendors(1, "Quantum Sword Polishing") == []
    assert vendor_directory.list_vendors(1, "") == []


def test_sorted_by_rating_desc(client):
    with get_conn() as conn:
        # add two Carpentry contractors with different ratings
        conn.execute(
            "INSERT INTO contractors (name, phone, specialty, "
            "average_rating, society_id, is_active, "
            "available_for_personal_jobs) "
            "VALUES (?,?,?,?,1,1,1)",
            ("MediumWood", "+910000000000", "Carpentry", 4.0),
        )
        conn.execute(
            "INSERT INTO contractors (name, phone, specialty, "
            "average_rating, society_id, is_active, "
            "available_for_personal_jobs) "
            "VALUES (?,?,?,?,1,1,1)",
            ("TopWood", "+911111111111", "Carpentry", 5.0),
        )
    rows = vendor_directory.list_vendors(1, "Carpentry")
    names = [r["name"] for r in rows]
    assert names.index("TopWood") < names.index("MediumWood")


def test_wa_link_strips_non_digits():
    link = vendor_directory._wa_link("+91 (982) 123-4567", "Plumbing")
    assert link.startswith("https://wa.me/919821234567?text=")


def test_wa_link_returns_none_for_missing_phone():
    assert vendor_directory._wa_link(None, "Plumbing") is None
    assert vendor_directory._wa_link("", "Plumbing") is None


# ---- endpoint + RBAC ------------------------------------------------
def test_endpoint_returns_directory_with_walinks(vclient):
    client, sid, tok = vclient
    r = client.get(
        "/api/v1/vendors/by-category?category=Plumbing",
        headers=tok["admin"],
    )
    assert r.status_code == 200
    rows = r.json()
    assert any(v["name"] == "AquaFix Plumbers" for v in rows)
    for v in rows:
        assert v["wa_link"] is None or v["wa_link"].startswith(
            "https://wa.me/"
        )


def test_endpoint_residents_and_staff_allowed(vclient):
    """staff has FILE_COMPLAINT by default -> 200."""
    client, _, tok = vclient
    r = client.get(
        "/api/v1/vendors/by-category?category=Plumbing",
        headers=tok["staff"],
    )
    assert r.status_code == 200


def test_endpoint_viewer_role_forbidden(vclient):
    """viewer has VIEW_ALL but NOT FILE_COMPLAINT -> 403."""
    client, _, tok = vclient
    r = client.get(
        "/api/v1/vendors/by-category?category=Plumbing",
        headers=tok["viewer"],
    )
    assert r.status_code == 403


def test_endpoint_unauthenticated_rejected(vclient):
    client, _, _ = vclient
    r = client.get("/api/v1/vendors/by-category?category=Plumbing")
    assert r.status_code == 401


def test_endpoint_category_required(vclient):
    """Missing query param -> 422 (FastAPI validation)."""
    client, _, tok = vclient
    r = client.get(
        "/api/v1/vendors/by-category", headers=tok["admin"]
    )
    assert r.status_code == 422
