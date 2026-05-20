"""E1a: enterprise core schema (additive, behaviour-neutral).

Proves the 5 new tables exist, complaints has the new escalation
columns, and the SLA seed populated sensibly. No service code yet.
"""
import json

from app.db import get_conn


def test_new_tables_exist(client):
    with get_conn() as conn:
        # querying these tables must not error — they exist
        for tbl in (
            "staff_members", "staff_categories", "contractor_categories",
            "escalation_hierarchy", "category_sla_config",
        ):
            conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()


def test_complaints_has_new_escalation_columns(client):
    with get_conn() as conn:
        # SELECT must succeed — columns are present
        conn.execute(
            "SELECT assigned_staff_id, escalated_to_manager_at, "
            "escalated_to_sr_manager_at, escalated_to_secretary_at, "
            "escalated_to_chairman_at, last_complainant_update_at, "
            "last_assigned_staff_update_at, reminder_sent_count "
            "FROM complaints"
        ).fetchall()


def test_sla_seed_populated_for_default_society(client):
    with get_conn() as conn:
        sid = dict(
            conn.execute(
                "SELECT id FROM societies ORDER BY id LIMIT 1"
            ).fetchone()
        )["id"]
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT category, target_response_time_minutes, "
                "target_resolution_time_hours, escalation_levels "
                "FROM category_sla_config WHERE society_id = ?",
                (sid,),
            ).fetchall()
        ]
    cats = {r["category"] for r in rows}
    assert {"AC/Cooling", "Plumbing", "Electrical", "Elevator",
            "Housekeeping", "Security", "Other"} <= cats

    elev = next(r for r in rows if r["category"] == "Elevator")
    assert elev["target_response_time_minutes"] == 15  # safety SLA
    # escalation_levels is JSON
    parsed = json.loads(elev["escalation_levels"])
    assert parsed["1"]["notify"] == "manager"
    assert parsed["3"]["notify"] == "secretary"


def test_seed_is_idempotent(client):
    """Re-running seed must not duplicate SLA rows or error."""
    from app.seed import seed

    seed()
    with get_conn() as conn:
        sid = dict(
            conn.execute(
                "SELECT id FROM societies ORDER BY id LIMIT 1"
            ).fetchone()
        )["id"]
        n = dict(
            conn.execute(
                "SELECT COUNT(*) AS c FROM category_sla_config "
                "WHERE society_id = ?",
                (sid,),
            ).fetchone()
        )["c"]
    assert n == 24  # one row per category (E1 expanded set)
