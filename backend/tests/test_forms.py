def test_google_form_json_creates_ticket(client):
    r = client.post(
        "/webhooks/forms",
        json={"raw_text": "5B mein AC kharab hai urgent",
              "phone": "+919833129064"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["ticket"].startswith("SER-")


def test_google_form_no_auth_required(client):
    # Apps Script can't mint a JWT - endpoint must be open like webhooks
    r = client.post("/webhooks/forms", json={"raw_text": "12A water leak"})
    assert r.status_code == 200


def test_google_form_shows_in_list(client, auth_header):
    client.post("/webhooks/forms", json={"raw_text": "9D no power urgent"})
    items = client.get("/api/v1/complaints", headers=auth_header).json()
    assert any(c["channel"] == "form" for c in items)


def test_google_form_empty_still_logs(client):
    r = client.post("/webhooks/forms", json={})
    assert r.status_code == 200
    assert r.json()["ticket"].startswith("SER-")
