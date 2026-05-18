def test_twilio_whatsapp_intake(client):
    r = client.post(
        "/webhooks/twilio/whatsapp",
        data={"From": "whatsapp:+919812345678",
              "Body": "5B mein AC kharab hai urgent"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["ticket"].startswith("SER-")


def test_twilio_sms_intake(client):
    r = client.post(
        "/webhooks/twilio/sms",
        data={"From": "+919812345678", "Body": "12A water leak"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_sendgrid_inbound_email(client):
    r = client.post(
        "/webhooks/sendgrid/inbound-email",
        data={"from": "resident@example.com",
              "subject": "Lift broken",
              "text": "3C lift not working since 2 days"},
    )
    assert r.status_code == 200
    assert r.json()["ticket"].startswith("SER-")


def test_webhook_creates_complaint_visible_in_list(client, auth_header):
    client.post(
        "/webhooks/twilio/whatsapp",
        data={"From": "whatsapp:+910000000000", "Body": "9D no power urgent"},
    )
    items = client.get("/api/v1/complaints", headers=auth_header).json()
    assert any(c["channel"] == "whatsapp" for c in items)


def test_webhook_empty_body_still_logs(client):
    r = client.post(
        "/webhooks/twilio/sms",
        data={"From": "+910000000000", "Body": "."},
    )
    assert r.status_code == 200


def test_webhook_no_auth_required(client):
    # webhooks are provider-authenticated upstream, not JWT
    r = client.post(
        "/webhooks/twilio/whatsapp",
        data={"From": "whatsapp:+911111111111", "Body": "test"},
    )
    assert r.status_code == 200
