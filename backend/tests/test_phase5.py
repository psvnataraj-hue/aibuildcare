"""Phase 5 - load balancing, forecasts, analytics."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def p5(tmp_path, monkeypatch):
    monkeypatch.setenv("AIBUILDCARE_DATABASE_URL", str(tmp_path / "p5.db"))
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
        with db.get_conn() as cn:
            for n, r in [
                ("Top HVAC", 5.0),
                ("Mid HVAC", 4.5),
                ("Low HVAC", 4.0),
            ]:
                cn.execute(
                    "INSERT INTO contractors (name, phone, specialty, "
                    "average_rating) VALUES (?,?,?,?)",
                    (n, "+910000000000", "AC/Cooling,Heating", r),
                )
            cn.execute(
                "UPDATE contractors SET average_rating = 1.0 "
                "WHERE name = 'CoolAir Services'"
            )
        tok = c.post(
            "/api/v1/auth/login",
            json={"email": "admin@aibuildcare.app", "password": "Secret!123"},
        ).json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {tok}"})
        yield c
    get_settings.cache_clear()


def _cid(p5, name):
    from app import db

    with db.get_conn() as cn:
        return dict(
            cn.execute(
                "SELECT id FROM contractors WHERE name = ?", (name,)
            ).fetchone()
        )["id"]


def _load(p5, contractor_id, n):
    """Give a contractor n open complaints directly."""
    from app import db

    with db.get_conn() as cn:
        for i in range(n):
            cn.execute(
                "INSERT INTO complaints (ticket_number, raw_text, status, "
                "channel, contractor_id, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    f"LOAD-{contractor_id}-{i}",
                    "x",
                    "assigned",
                    "dashboard",
                    contractor_id,
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T00:00:00+00:00",
                ),
            )


def test_load_balancing_skips_overloaded(p5):
    from app.services import system_config
    from app.services.contractor_router import best_contractor

    system_config.set_config("max_pending_jobs_per_contractor", "2")
    _load(p5, _cid(p5, "Top HVAC"), 3)  # over threshold
    b = best_contractor("AC/Cooling")
    assert b["name"] == "Mid HVAC"  # skipped Top, next-rated under cap


def test_load_balancing_fallback(p5):
    from app.services import system_config
    from app.services.contractor_router import best_contractor

    system_config.set_config("max_pending_jobs_per_contractor", "1")
    # overload EVERY AC/Cooling candidate incl. the seed CoolAir
    for nm, ld in [
        ("Top HVAC", 5),
        ("Mid HVAC", 9),
        ("Low HVAC", 3),
        ("CoolAir Services", 8),
    ]:
        _load(p5, _cid(p5, nm), ld)
    b = best_contractor("AC/Cooling")
    assert b is not None  # all overloaded -> least-loaded fallback
    assert b["name"] == "Low HVAC"  # fewest pending (3)


def test_load_balancing_configurable_via_api(p5):
    r = p5.get("/api/v1/admin/config")
    assert r.status_code == 200
    assert r.json()["max_pending_jobs_per_contractor"] == "10"
    up = p5.post(
        "/api/v1/admin/config/max_pending_jobs_per_contractor",
        json={"value": "3"},
    )
    assert up.status_code == 200
    assert p5.get("/api/v1/admin/config").json()[
        "max_pending_jobs_per_contractor"
    ] == "3"


def test_forecast_from_category_avg(p5):
    from app.services.complaint_service import category_avg_resolution_hours

    assert category_avg_resolution_hours("Elevator") == 6.0  # default
    assert category_avg_resolution_hours(None) == 48.0


def test_forecast_set_on_assignment(p5):
    r = p5.post(
        "/api/v1/complaints", json={"raw_text": "AC broken in 5B urgent"}
    )
    body = r.json()
    assert body["status"] == "assigned"
    assert body["estimated_completion_date"] is not None
    from datetime import datetime

    assert datetime.fromisoformat(
        body["estimated_completion_date"]
    ) > datetime.fromisoformat(body["created_at"])


def test_admin_config_requires_auth(p5):
    bare = TestClient(p5.app)
    assert bare.get("/api/v1/admin/config").status_code == 401


def test_contractor_analytics_endpoints(p5):
    p5.post("/api/v1/complaints", json={"raw_text": "AC broken 5B urgent"})
    cid = _cid(p5, "Top HVAC")
    a = p5.get(f"/api/v1/contractors/{cid}/analytics")
    assert a.status_code == 200
    j = a.json()
    assert set(["workload", "response_time", "resolution_time",
                "rating_trend", "category_specialization",
                "availability"]) <= set(j)
    assert j["workload"]["total_assigned"] >= 1
    s = p5.get("/api/v1/contractors/analytics/summary")
    assert s.status_code == 200
    assert {"total_contractors", "top_performers",
            "workload_distribution"} <= set(s.json())
    assert p5.get("/api/v1/contractors/99999/analytics").status_code == 404
