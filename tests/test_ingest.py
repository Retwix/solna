"""Behaviour: the internal ingest endpoint (watcher -> API)."""


def _body(event_id):
    return {"event_id": event_id, "s3_raw_key": f"raw/{event_id}/x.jpg",
            "s3_thumb_key": f"thumbs/{event_id}/x.jpg"}


def test_ingest_requires_the_shared_secret(client, make_event):
    """Without the correct ingest key, photos cannot be registered."""
    event = make_event("Auth Event")

    assert client.post("/internal/ingest", json=_body(event["id"])).status_code == 401
    assert client.post("/internal/ingest", json=_body(event["id"]),
                       headers={"X-Ingest-Key": "wrong"}).status_code == 401


def test_ingest_with_valid_key_registers_a_ready_photo(client, make_event):
    """With the right key, the photo is stored and exposed with public URLs."""
    event = make_event("Good Auth Event")
    resp = client.post("/internal/ingest", json=_body(event["id"]),
                       headers={"X-Ingest-Key": "test-key"})
    assert resp.status_code == 200
    photo = resp.json()
    assert photo["url"].endswith(f"raw/{event['id']}/x.jpg")
    assert photo["id"]
