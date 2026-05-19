def test_sendgrid_email_creates_ticket(client, auth_header):
    r = client.post(
        "/webhooks/sendgrid/email",
        data={
            "from": "Resident Name <resident@example.com>",
            "subject": "5B AC kharab hai",
            "text": "5B mein AC bilkul kaam nahi kar raha. Bahut garmi hai.",
        },
    )
    assert r.status_code == 200
    assert r.json()["ticket"].startswith("SER-")
    items = client.get("/api/v1/complaints?q=5B", headers=auth_header).json()
    em = [c for c in items if c["channel"] == "email"]
    assert em and em[0]["unit_number"] == "5B"
    assert em[0]["reporter_email"] == "resident@example.com"  # name stripped


def test_sendgrid_email_html_only(client):
    r = client.post(
        "/webhooks/sendgrid/email",
        data={
            "from": "x@y.com",
            "subject": "Plumbing",
            "html": "<div><p>12A water <b>leak</b> urgent</p></div>",
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_sendgrid_email_empty_body_still_logs(client):
    r = client.post(
        "/webhooks/sendgrid/email", data={"from": "a@b.com"}
    )
    assert r.status_code == 200
    assert r.json()["ticket"].startswith("SER-")


def test_sendgrid_email_no_sender_no_crash(client):
    r = client.post(
        "/webhooks/sendgrid/email",
        data={"subject": "9D lift band", "text": "9D lift band hai"},
    )
    assert r.status_code == 200


def test_sendgrid_inbound_alias_still_works(client):
    # backwards-compatible legacy path
    r = client.post(
        "/webhooks/sendgrid/inbound-email",
        data={"from": "old@example.com", "text": "7E electrical issue"},
    )
    assert r.status_code == 200
    assert r.json()["ticket"].startswith("SER-")
