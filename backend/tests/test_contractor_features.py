from unittest.mock import MagicMock

import app.routers.complaints as rc


def _new(client, h, text="5B mein AC kharab hai urgent"):
    return client.post(
        "/api/v1/complaints", json={"raw_text": text}, headers=h
    ).json()


# ---- #9 contractor WhatsApp notification on assign --------------------
def test_assign_contractor_notify(client, auth_header, monkeypatch):
    sent = MagicMock()
    monkeypatch.setattr(rc, "send_whatsapp", sent)
    cid = _new(client, auth_header)["id"]
    r = client.post(
        f"/api/v1/complaints/{cid}/assign",
        json={"contractor_id": 1},
        headers=auth_header,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "assigned"
    assert sent.called
    phone, body = sent.call_args[0]
    assert phone.startswith("+91")
    assert r.json()["ticket_number"] in body
    assert "assigned" in body.lower()


def test_assign_invalid_contractor_no_notify(client, auth_header, monkeypatch):
    sent = MagicMock()
    monkeypatch.setattr(rc, "send_whatsapp", sent)
    cid = _new(client, auth_header)["id"]
    r = client.post(
        f"/api/v1/complaints/{cid}/assign",
        json={"contractor_id": 9999},
        headers=auth_header,
    )
    assert r.status_code == 404
    assert not sent.called


# ---- #19 contractor performance --------------------------------------
def test_contractor_performance(client, auth_header):
    cid = _new(client, auth_header)["id"]
    client.post(
        f"/api/v1/complaints/{cid}/assign",
        json={"contractor_id": 1},
        headers=auth_header,
    )
    for s in ["in_progress", "resolved"]:
        client.post(
            f"/api/v1/complaints/{cid}/status",
            json={"status": s},
            headers=auth_header,
        )
    r = client.get(
        "/api/v1/contractors/1/performance", headers=auth_header
    )
    assert r.status_code == 200
    p = r.json()
    assert p["assigned_count"] == 1
    assert p["resolved_count"] == 1
    assert p["completion_rate"] == 100.0
    assert p["avg_response_time_hours"] is not None
    assert p["avg_resolution_time_hours"] is not None
    assert p["last_activity"]

    lst = client.get(
        "/api/v1/contractors/performance", headers=auth_header
    ).json()
    assert isinstance(lst, list) and len(lst) >= 1
    assert {"contractor_id", "completion_rate"} <= set(lst[0])


def test_performance_unknown_contractor(client, auth_header):
    assert (
        client.get(
            "/api/v1/contractors/9999/performance", headers=auth_header
        ).status_code
        == 404
    )


# ---- #20 post-resolution rating --------------------------------------
def test_rate_requires_resolved(client, auth_header):
    cid = _new(client, auth_header)["id"]
    r = client.post(
        f"/api/v1/complaints/{cid}/rate",
        json={"rating": 5, "feedback": "great"},
        headers=auth_header,
    )
    assert r.status_code == 400


def test_rate_complaint_flow(client, auth_header):
    cid = _new(client, auth_header)["id"]
    for s in ["acknowledged", "assigned", "in_progress", "resolved"]:
        client.post(
            f"/api/v1/complaints/{cid}/status",
            json={"status": s},
            headers=auth_header,
        )
    r = client.post(
        f"/api/v1/complaints/{cid}/rate",
        json={"rating": 4, "feedback": "Fast service, very helpful"},
        headers=auth_header,
    )
    assert r.status_code == 200
    assert r.json()["rating"] == 4

    # surfaced on the complaint detail
    detail = client.get(
        f"/api/v1/complaints/{cid}", headers=auth_header
    ).json()
    assert detail["rating"]["rating"] == 4
    assert detail["rating"]["feedback"] == "Fast service, very helpful"

    # cannot rate twice
    again = client.post(
        f"/api/v1/complaints/{cid}/rate",
        json={"rating": 1},
        headers=auth_header,
    )
    assert again.status_code == 400


def test_rate_validation_and_missing(client, auth_header):
    cid = _new(client, auth_header)["id"]
    client.post(
        f"/api/v1/complaints/{cid}/status",
        json={"status": "resolved"},
        headers=auth_header,
    )
    bad = client.post(
        f"/api/v1/complaints/{cid}/rate",
        json={"rating": 9},
        headers=auth_header,
    )
    assert bad.status_code == 422
    missing = client.post(
        "/api/v1/complaints/9999/rate",
        json={"rating": 5},
        headers=auth_header,
    )
    assert missing.status_code == 404
