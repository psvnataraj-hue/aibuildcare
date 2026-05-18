import pytest


def _create(client, h, text="5B mein AC kharab hai 3 din se urgent"):
    return client.post(
        "/api/v1/complaints", json={"raw_text": text}, headers=h
    )


def test_create_complaint(client, auth_header):
    r = _create(client, auth_header)
    assert r.status_code == 201
    body = r.json()
    assert body["ticket_number"].startswith("SER-")
    assert body["unit_number"] == "5B"
    assert body["category"] == "AC/Cooling"
    assert body["priority"] == "urgent"
    assert body["status"] == "received"
    assert "✅ Ticket" in body["acknowledgement"]


def test_create_validation(client, auth_header):
    r = client.post(
        "/api/v1/complaints", json={"raw_text": ""}, headers=auth_header
    )
    assert r.status_code == 422


def test_ticket_numbers_increment(client, auth_header):
    a = _create(client, auth_header).json()["ticket_number"]
    b = _create(client, auth_header).json()["ticket_number"]
    assert a != b


def test_list_and_filter(client, auth_header):
    _create(client, auth_header, "5B AC urgent")
    _create(client, auth_header, "12A water leak")
    r = client.get("/api/v1/complaints", headers=auth_header)
    assert len(r.json()) == 2
    r2 = client.get("/api/v1/complaints?q=water", headers=auth_header)
    assert len(r2.json()) == 1


def test_get_complaint_detail(client, auth_header):
    cid = _create(client, auth_header).json()["id"]
    r = client.get(f"/api/v1/complaints/{cid}", headers=auth_header)
    assert r.status_code == 200
    assert "messages" in r.json()
    assert len(r.json()["messages"]) >= 1


def test_get_missing_complaint(client, auth_header):
    r = client.get("/api/v1/complaints/9999", headers=auth_header)
    assert r.status_code == 404


def test_assign_contractor(client, auth_header):
    cid = _create(client, auth_header).json()["id"]
    r = client.post(
        f"/api/v1/complaints/{cid}/assign",
        json={"contractor_id": 1},
        headers=auth_header,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "assigned"
    assert r.json()["contractor_id"] == 1


def test_assign_invalid_contractor(client, auth_header):
    cid = _create(client, auth_header).json()["id"]
    r = client.post(
        f"/api/v1/complaints/{cid}/assign",
        json={"contractor_id": 999},
        headers=auth_header,
    )
    assert r.status_code == 404


@pytest.mark.parametrize(
    "seq", [["acknowledged", "assigned", "in_progress", "resolved", "closed"]]
)
def test_status_progression(client, auth_header, seq):
    cid = _create(client, auth_header).json()["id"]
    for st in seq:
        r = client.post(
            f"/api/v1/complaints/{cid}/status",
            json={"status": st},
            headers=auth_header,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == st


def test_status_cannot_go_backwards(client, auth_header):
    cid = _create(client, auth_header).json()["id"]
    client.post(
        f"/api/v1/complaints/{cid}/status",
        json={"status": "resolved"},
        headers=auth_header,
    )
    r = client.post(
        f"/api/v1/complaints/{cid}/status",
        json={"status": "received"},
        headers=auth_header,
    )
    assert r.status_code == 400


def test_status_invalid_value(client, auth_header):
    cid = _create(client, auth_header).json()["id"]
    r = client.post(
        f"/api/v1/complaints/{cid}/status",
        json={"status": "banana"},
        headers=auth_header,
    )
    assert r.status_code == 400


def test_message_thread(client, auth_header):
    cid = _create(client, auth_header).json()["id"]
    r = client.post(
        f"/api/v1/complaints/{cid}/messages",
        json={"sender": "staff", "body": "Technician dispatched"},
        headers=auth_header,
    )
    assert r.status_code == 201
    msgs = client.get(
        f"/api/v1/complaints/{cid}/messages", headers=auth_header
    ).json()
    assert any(m["body"] == "Technician dispatched" for m in msgs)


def test_message_on_missing_complaint(client, auth_header):
    r = client.post(
        "/api/v1/complaints/9999/messages",
        json={"body": "hi"},
        headers=auth_header,
    )
    assert r.status_code == 404


def test_analytics(client, auth_header):
    _create(client, auth_header, "5B AC urgent")
    _create(client, auth_header, "12A water leak")
    a = client.get("/api/v1/analytics", headers=auth_header).json()
    assert a["total"] == 2
    assert a["open"] == 2
    assert a["urgent_open"] >= 1


def test_contractors_list(client, auth_header):
    r = client.get("/api/v1/contractors", headers=auth_header)
    assert r.status_code == 200
    assert len(r.json()) >= 1
