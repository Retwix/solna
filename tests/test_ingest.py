"""Behaviour: the internal ingest endpoint (watcher -> API).

The watcher posts the photographer it saw the file under; the API resolves
which event (if any) is live for that account.
"""
from conftest import ingest_photo


def test_ingest_requires_the_shared_secret(client, make_event):
    """Without the correct ingest key, photos cannot be registered."""
    event = make_event("Auth Event")
    pid = event["photographer"]["id"]
    body = {"photographer_id": pid, "s3_raw_key": f"raw/{pid}/x.jpg",
            "s3_thumb_key": f"thumbs/{pid}/x.jpg"}

    assert client.post("/internal/ingest", json=body).status_code == 401
    assert client.post("/internal/ingest", json=body,
                       headers={"X-Ingest-Key": "wrong"}).status_code == 401


def test_ingest_with_valid_key_registers_a_ready_photo(client, make_event):
    """With the right key, the photo is stored and exposed with public URLs."""
    event = make_event("Good Auth Event")
    pid = event["photographer"]["id"]

    resp = ingest_photo(client, pid, "x.jpg")
    assert resp.status_code == 200
    photo = resp.json()
    assert photo["url"].endswith(f"raw/{pid}/x.jpg")
    assert photo["id"]


def test_ingest_for_unknown_photographer_is_rejected(client):
    """A path that doesn't map to an account must not create orphan photos."""
    resp = ingest_photo(client, "not-a-real-photographer")
    assert resp.status_code == 404
