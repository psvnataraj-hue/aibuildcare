"""Phase 4.5 - smart auto-assignment + ratings.

Uses a self-contained client with AUTO_ASSIGN enabled (the shared
conftest client disables it so legacy status assertions stay valid).
"""
import os
import tempfile
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def aclient(tmp_path, monkeypatch):
    monkeypatch.setenv("AIBUILDCARE_DATABASE_URL", str(tmp_path / "aa.db"))
    monkeypatch.setenv("AIBUILDCARE_ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("AIBUILDCARE_TWILIO_ACCOUNT_SID", "")
    monkeypatch.setenv("AIBUILDCARE_TWILIO_AUTH_TOKEN", "")
    monkeypatch.setenv("AIBUILDCARE_SEED_ADMIN_EMAIL", "admin@aibuildcare.app")
    monkeypatch.setenv("AIBUILDCARE_SEED_ADMIN_PASSWORD", "Secret!123")
    monkeypatch.setenv("AIBUILDCARE_AUTO_ASSIGN_ENABLED", "true")

    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app
    from app import db

    app = create_app()
    with TestClient(app) as c:
        # extra rated HVAC + Plumbing contractors (seed already added 4
        # defaults at rating 5.0; raise CARIMO HVAC highest)
        with db.get_conn() as cn:
            rows = [
                ("CARIMO HVAC", "AC/Cooling,Heating", 5.0),
                ("Urban HVAC Solutions", "AC/Cooling,Heating", 4.8),
                ("Voltas Air Systems", "AC/Cooling,Heating", 3.9),
                ("CARIMO Plumbing", "Plumbing,Waterproofing", 5.0),
                ("Godrej Waterproofing", "Plumbing,Waterproofing", 4.1),
            ]
            for n, s, r in rows:
                cn.execute(
                    "INSERT INTO contractors (name, phone, specialty, "
                    "average_rating) VALUES (?,?,?,?)",
                    (n, "+919082397027", s, r),
                )
            # neutralise the 4 default seed contractors so the named
            # Phase-4.5 contractors win deterministically
            cn.execute(
                "UPDATE contractors SET average_rating = 1.0 WHERE name IN "
                "('CoolAir Services','AquaFix Plumbers',"
                "'Voltz Electricals','LiftCare')"
            )
        tok = c.post(
            "/api/v1/auth/login",
            json={"email": "admin@aibuildcare.app", "password": "Secret!123"},
        ).json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {tok}"})
        yield c
    get_settings.cache_clear()


# ---- unit: routing logic ---------------------------------------------
def test_auto_assign_highest_rated(aclient):
    from app.services.contractor_router import best_contractor

    b = best_contractor("AC/Cooling")
    assert b is not None
    assert b["name"] == "CARIMO HVAC"
    assert b["average_rating"] == 5.0


def test_auto_assign_by_category(aclient):
    from app.services.contractor_router import best_contractor

    assert "Plumb" in best_contractor("Plumbing")["specialty"]
    assert best_contractor("Plumbing")["name"] == "CARIMO Plumbing"


def test_auto_assign_missing_category(aclient):
    from app.services.contractor_router import best_contractor

    assert best_contractor("Quantum Teleportation") is None
    assert best_contractor(None) is None


def test_contractor_list_by_category(aclient):
    from app.services.contractor_router import contractors_by_category

    lst = contractors_by_category("AC/Cooling")
    ratings = [c["average_rating"] for c in lst]
    assert ratings == sorted(ratings, reverse=True)
    assert lst[0]["name"] == "CARIMO HVAC"


# ---- integration: create -> auto-assign ------------------------------
def test_complaint_auto_assigns_on_create(aclient):
    r = aclient.post(
        "/api/v1/complaints",
        json={"raw_text": "AC broken in 5B urgent"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["category"] == "AC/Cooling"
    assert body["status"] == "assigned"
    assert body["contractor_id"] is not None
    detail = aclient.get(
        f"/api/v1/complaints/{body['id']}"
    ).json()
    assert any(
        "Auto-assigned to CARIMO HVAC" in m["body"]
        for m in detail["messages"]
    )


def test_complaint_notifies_on_assign(aclient, monkeypatch):
    sent = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.notify.send_whatsapp", sent)
    r = aclient.post(
        "/api/v1/complaints", json={"raw_text": "AC not cooling 7B urgent"}
    )
    assert r.json()["status"] == "assigned"
    assert sent.called
    _phone, body = sent.call_args[0]
    assert "CARIMO HVAC" in body
    assert r.json()["ticket_number"] in body


def test_complaint_reassign_notifies_both(aclient, monkeypatch):
    import app.routers.complaints as rc

    sent = MagicMock(return_value=True)
    monkeypatch.setattr(rc, "send_whatsapp", sent)
    cid = aclient.post(
        "/api/v1/complaints", json={"raw_text": "AC broken 9C urgent"}
    ).json()["id"]
    # find a different HVAC contractor (lower rated) to reassign to
    lst = aclient.get(
        "/api/v1/contractors/by-category?category=AC/Cooling"
    ).json()
    target = next(c for c in lst if c["name"] == "Voltas Air Systems")
    r = aclient.post(
        f"/api/v1/complaints/{cid}/assign",
        json={"contractor_id": target["id"]},
    )
    assert r.status_code == 200
    bodies = " || ".join(call.args[1] for call in sent.call_args_list)
    assert "Voltas Air Systems" in bodies  # new contractor notified
    assert "reassigned away" in bodies  # old contractor notified
