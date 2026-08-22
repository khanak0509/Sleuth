import time


def test_stream_status_fields(client):
    r = client.get("/stream/status")
    assert r.status_code == 200
    body = r.json()
    assert body["event_count"] >= 0
    assert "last_ingested_timestamp" in body
    assert body["running"] is True


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_stream_status_count_increases(client):
    a = client.get("/stream/status").json()["event_count"]
    grew = False
    # poll with wait — GitHub poll interval is ~5s
    for _ in range(8):
        time.sleep(3)
        b = client.get("/stream/status").json()["event_count"]
        if b > a:
            grew = True
            break
        a = max(a, b)
    assert grew, "event_count did not increase; ingest loop may be stalled"
