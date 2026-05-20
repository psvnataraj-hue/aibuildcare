"""Categories expanded 7 -> 24 (E1 scope-up).

Existing test_haiku_parser regression already proves the original 7
categories still classify correctly. This file proves a sampling of
the new categories also work in the rule fallback (LLM handles the
ambiguous cases at runtime).
"""
import pytest

from app.services import haiku_parser as hp


def test_categories_has_24_distinct_entries():
    assert len(hp.CATEGORIES) == len(set(hp.CATEGORIES)) == 24
    must_contain = {
        "Carpentry", "Gardening", "Pest Control", "Garbage/Waste",
        "Water Supply", "Sewage/Drainage", "Lighting", "Painting",
        "CCTV/Intercom", "Generator/Power Backup", "Fire Safety",
        "Civil/Structural", "Swimming Pool", "Sports/Gym/Clubhouse",
        "Children's Play Area", "Parking Management", "Noise/Visitor",
    }
    assert must_contain <= set(hp.CATEGORIES)


@pytest.mark.parametrize(
    "text,cat",
    [
        ("carpenter needed for cupboard repair", "Carpentry"),
        ("cockroach infestation in kitchen", "Pest Control"),
        ("wall whitewash needed urgently", "Painting"),
        ("parking slot blocked since morning", "Parking Management"),
        ("loud noise from above flat", "Noise/Visitor"),
        ("fire extinguisher missing in lobby", "Fire Safety"),
        ("bulb fused in our wing", "Lighting"),
        ("tanker has not come today", "Water Supply"),
        ("manhole open on terrace", "Sewage/Drainage"),
        ("inverter battery died last night", "Generator/Power Backup"),
        ("gardener absent for two days", "Gardening"),
        ("ceiling crack visible", "Civil/Structural"),
        ("intercom not ringing", "CCTV/Intercom"),
        ("pool chlorine smell too strong", "Swimming Pool"),
        ("gym treadmill broken", "Sports/Gym/Clubhouse"),
        ("playground swing broken", "Children's Play Area"),
        ("waste collection delayed", "Garbage/Waste"),
    ],
)
def test_new_categories_rule_classifier(text, cat):
    assert hp.rule_based_parse(text).category == cat


def test_default_forecast_hours_covers_all_categories():
    from app.services.complaint_service import DEFAULT_FORECAST_HOURS

    for cat in hp.CATEGORIES:
        assert cat in DEFAULT_FORECAST_HOURS, (
            f"missing forecast for {cat!r}"
        )


def test_sla_seed_covers_all_24_categories(client):
    from app.db import get_conn

    with get_conn() as conn:
        sid = dict(
            conn.execute(
                "SELECT id FROM societies ORDER BY id LIMIT 1"
            ).fetchone()
        )["id"]
        rows = conn.execute(
            "SELECT category FROM category_sla_config WHERE society_id = ?",
            (sid,),
        ).fetchall()
    seeded = {dict(r)["category"] for r in rows}
    assert set(hp.CATEGORIES) <= seeded
