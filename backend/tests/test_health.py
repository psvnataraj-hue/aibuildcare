def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_openapi_available(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "AIBuildCare" in r.text
