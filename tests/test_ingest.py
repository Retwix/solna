"""Behaviour: the internal ingest endpoint (FTP ingest -> API).

The FTP ingest pipeline posts the photographer it saw the file under; the API resolves
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


def test_ingest_for_unknown_photographer_is_rejected(client):
    """A path that doesn't map to an account must not create orphan photos."""
    resp = ingest_photo(client, "not-a-real-photographer")
    assert resp.status_code == 404


def test_photo_links_are_expiring_signed_urls_on_the_public_endpoint(client, make_event):
    """The bucket is private: a photo is only reachable through a signed,
    time-limited link that a guest's browser can open."""
    from urllib.parse import parse_qs, urlsplit

    event = make_event("Signed Links Event")
    pid = event["photographer"]["id"]

    photo = ingest_photo(client, pid, "x.jpg").json()

    for link in (photo["url"], photo["thumb_url"]):
        parts = urlsplit(link)
        query = parse_qs(parts.query)
        assert f"{parts.scheme}://{parts.netloc}" == "http://test-s3"
        assert parts.path.startswith(f"/solna-media/")
        assert "X-Amz-Signature" in query and "X-Amz-Expires" in query
    assert urlsplit(photo["url"]).path == f"/solna-media/raw/{pid}/x.jpg"
    assert urlsplit(photo["thumb_url"]).path == f"/solna-media/thumbs/{pid}/x.jpg"
