"""E3c (first slice): /api/v1/complaints[/{id}] now exposes
`assigned_staff_name` (LEFT JOIN against staff_members) so the
frontend can render the staff name on the complaint card and the
detail view without an extra round-trip.

Field is NULL when no staff is assigned (which is the common case
for contractor-assigned or unassigned complaints).
"""
from unittest.mock import MagicMock

from app.db import get_conn


def _add_staff(name, society_id=1, phone="+919000000222"):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO staff_members (society_id, name, phone_primary, "
            "whatsapp_enabled, active) VALUES (?,?,?,1,1)",
            (society_id, name, phone),
        )
        return dict(conn.execute(
            "SELECT id FROM staff_members ORDER BY id DESC LIMIT 1"
        ).fetchone())["id"]


def _create(client, auth_header):
    r = client.post(
        "/api/v1/complaints", json={"raw_text": "5B nal leak"},
        headers=auth_header,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_unassigned_complaint_has_null_staff_name(client, auth_header):
    c = _create(client, auth_header)
    # The freshly-created complaint may have been auto-routed to a
    # contractor (no seeded staff for this society in tests), so
    # assigned_staff_id is None and assigned_staff_name is None.
    r = client.get(f"/api/v1/complaints/{c['id']}", headers=auth_header)
    assert r.status_code == 200
    body = r.json()
    assert body.get("assigned_staff_id") is None
    assert body.get("assigned_staff_name") is None


def test_staff_assigned_complaint_exposes_name(
    client, auth_header, monkeypatch
):
    monkeypatch.setattr(
        "app.routers.complaints.send_whatsapp",
        MagicMock(return_value=True),
    )
    c = _create(client, auth_header)
    staff_id = _add_staff("Ramesh Plumber", phone="+919833000001")
    assign = client.post(
        f"/api/v1/complaints/{c['id']}/assign",
        json={"staff_id": staff_id}, headers=auth_header,
    )
    assert assign.status_code == 200, assign.text

    # The assign response itself should already carry the name
    # (so the frontend's optimistic update has it).
    assert assign.json().get("assigned_staff_name") == "Ramesh Plumber"

    # And so should subsequent GET (single) and list endpoints.
    one = client.get(
        f"/api/v1/complaints/{c['id']}", headers=auth_header,
    )
    assert one.status_code == 200
    assert one.json().get("assigned_staff_name") == "Ramesh Plumber"

    listing = client.get("/api/v1/complaints", headers=auth_header)
    assert listing.status_code == 200
    match = next(
        x for x in listing.json() if x["id"] == c["id"]
    )
    assert match.get("assigned_staff_name") == "Ramesh Plumber"


def test_contractor_assigned_complaint_has_null_staff_name(
    client, auth_header, monkeypatch
):
    """Sanity: contractor-assigned complaints don't accidentally
    pick up a staff name via the JOIN."""
    monkeypatch.setattr(
        "app.routers.complaints.send_whatsapp",
        MagicMock(return_value=True),
    )
    c = _create(client, auth_header)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO contractors (society_id, name, specialty, "
            "phone, is_active) VALUES (1,?,?,?,1)",
            ("ABC Repairs", "Plumbing", "+919833000002"),
        )
        ctr = dict(conn.execute(
            "SELECT id FROM contractors ORDER BY id DESC LIMIT 1"
        ).fetchone())["id"]
    r = client.post(
        f"/api/v1/complaints/{c['id']}/assign",
        json={"contractor_id": ctr}, headers=auth_header,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("contractor_id") == ctr
    assert body.get("assigned_staff_id") is None
    assert body.get("assigned_staff_name") is None
