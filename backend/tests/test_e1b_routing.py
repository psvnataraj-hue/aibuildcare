"""E1b: society-scoped, category-aware routing (staff -> contractor).

Tests the new routing_service ordering: staff (primary cat > secondary,
expert > senior > junior, then ascending workload) -> contractor
(primary cat > legacy specialty match, rating desc, workload asc)
-> unassigned. All scoped by society.
"""
import pytest
from fastapi.testclient import TestClient

from app.db import get_conn
from app.security import hash_password


@pytest.fixture()
def rclient(tmp_path, monkeypatch):
    """Self-contained client with AUTO_ASSIGN=true (the shared conftest
    client disables it). Yields TestClient with an admin bearer token."""
    monkeypatch.setenv("AIBUILDCARE_DATABASE_URL", str(tmp_path / "r.db"))
    monkeypatch.setenv("AIBUILDCARE_ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("AIBUILDCARE_TWILIO_ACCOUNT_SID", "")
    monkeypatch.setenv("AIBUILDCARE_TWILIO_AUTH_TOKEN", "")
    monkeypatch.setenv("AIBUILDCARE_SEED_ADMIN_EMAIL", "admin@aibuildcare.app")
    monkeypatch.setenv("AIBUILDCARE_SEED_ADMIN_PASSWORD", "Secret!123")
    monkeypatch.setenv("AIBUILDCARE_AUTO_ASSIGN_ENABLED", "true")

    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        tok = c.post(
            "/api/v1/auth/login",
            json={"email": "admin@aibuildcare.app",
                  "password": "Secret!123"},
        ).json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {tok}"})
        yield c
    get_settings.cache_clear()


def _add_staff(name, category, society_id=1, primary=1,
                skill="senior", phone="+919000111222",
                wa_enabled=1):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO staff_members (society_id, name, phone_primary, "
            "whatsapp_enabled, active) VALUES (?,?,?,?,1)",
            (society_id, name, phone, wa_enabled),
        )
        sid = dict(
            conn.execute(
                "SELECT id FROM staff_members ORDER BY id DESC LIMIT 1"
            ).fetchone()
        )["id"]
        conn.execute(
            "INSERT INTO staff_categories (staff_id, category, "
            "primary_category, skill_level) VALUES (?,?,?,?)",
            (sid, category, primary, skill),
        )
        return sid


def _create(rclient, raw_text):
    r = rclient.post("/api/v1/complaints", json={"raw_text": raw_text})
    assert r.status_code == 201, r.text
    return r.json()


# ---- core ordering --------------------------------------------------
def test_staff_with_primary_category_beats_contractor(rclient):
    """Staff for Plumbing exists -> staff picked, contractor_id stays NULL."""
    staff_id = _add_staff("Ramesh Plumber", "Plumbing")
    c = _create(rclient, "5B nal leak urgent")
    assert c["category"] == "Plumbing"
    assert c["status"] == "assigned"
    assert c["assigned_staff_id"] == staff_id
    assert c["contractor_id"] is None


def test_no_matching_staff_falls_back_to_contractor(rclient):
    """Staff exists but for a different category -> fall to contractor."""
    _add_staff("Ramesh Plumber", "Plumbing")
    c = _create(rclient, "fan not working in 7B")  # Electrical
    assert c["category"] == "Electrical"
    assert c["status"] == "assigned"
    assert c["assigned_staff_id"] is None
    assert c["contractor_id"] is not None  # Voltz Electricals seed


def test_no_staff_no_contractor_stays_unassigned(rclient):
    """Painting has no seed contractor (specialty doesn't include it)
    and no staff -> complaint stays 'received', no assignment."""
    c = _create(rclient, "whitewash needed in lobby")
    assert c["category"] == "Painting"
    assert c["status"] == "received"
    assert c["assigned_staff_id"] is None
    assert c["contractor_id"] is None


def test_staff_in_other_society_is_not_picked(rclient):
    """Society-2 staff is invisible to a society-1 complaint."""
    with get_conn() as conn:
        conn.execute("INSERT INTO societies (name) VALUES ('Soc2')")
        s2 = dict(
            conn.execute(
                "SELECT id FROM societies ORDER BY id DESC LIMIT 1"
            ).fetchone()
        )["id"]
    _add_staff("Society-2 Plumber", "Plumbing", society_id=s2)
    c = _create(rclient, "5B nal leak urgent")
    # falls through to society-1 contractor instead
    assert c["assigned_staff_id"] is None
    assert c["contractor_id"] is not None


def test_primary_category_beats_secondary(rclient):
    """Two staff for the same category -> primary_category=1 wins."""
    sec = _add_staff("Generalist", "Plumbing", primary=0, skill="senior")
    pri = _add_staff("Specialist", "Plumbing", primary=1, skill="senior")
    c = _create(rclient, "5B nal leak urgent")
    assert c["assigned_staff_id"] == pri
    assert c["assigned_staff_id"] != sec


def test_expert_skill_beats_senior_at_equal_workload(rclient):
    """Both primary, equal workload -> expert > senior > junior."""
    sen = _add_staff("S Senior", "Plumbing", primary=1, skill="senior")
    exp = _add_staff("X Expert", "Plumbing", primary=1, skill="expert")
    c = _create(rclient, "5B nal leak urgent")
    assert c["assigned_staff_id"] == exp
    assert c["assigned_staff_id"] != sen


def test_workload_tiebreak_picks_lighter(rclient):
    """Same primary+skill -> staff with fewer active complaints wins."""
    busy = _add_staff("Busy", "Plumbing", primary=1, skill="senior")
    free = _add_staff("Free", "Plumbing", primary=1, skill="senior")
    # pre-load 'busy' with 2 active complaints (direct DB so we don't
    # trigger the router for setup)
    with get_conn() as conn:
        for i in range(2):
            conn.execute(
                "INSERT INTO complaints "
                "(ticket_number, society_id, raw_text, status, "
                "assigned_staff_id) VALUES (?,?,?,?,?)",
                (f"SETUP-{i}", 1, "preload", "assigned", busy),
            )
    c = _create(rclient, "another leak in 3C")
    assert c["assigned_staff_id"] == free


def test_whatsapp_disabled_staff_gets_no_notification(rclient, monkeypatch):
    """whatsapp_enabled=0 -> we still assign, but skip the send_whatsapp."""
    from unittest.mock import MagicMock

    sent = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.notify.send_whatsapp", sent)
    sid = _add_staff(
        "Silent Sam", "Plumbing", primary=1, wa_enabled=0,
    )
    c = _create(rclient, "5B nal leak urgent")
    assert c["assigned_staff_id"] == sid
    assert not sent.called  # no WhatsApp despite assignment


def test_whatsapp_enabled_staff_gets_notification(rclient, monkeypatch):
    from unittest.mock import MagicMock

    sent = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.notify.send_whatsapp", sent)
    _add_staff("Loud Lakshmi", "Plumbing", primary=1, wa_enabled=1)
    c = _create(rclient, "5B nal leak urgent")
    assert sent.called
    _phone, body = sent.call_args[0]
    assert "ASSIGNED" in body and "Loud Lakshmi" in body
