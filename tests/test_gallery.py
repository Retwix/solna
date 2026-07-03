"""Behaviour: the guest-facing live gallery and its privacy guarantees."""
from conftest import disable_event, ingest_photo, token_from_gallery_url


def test_guest_sees_photos_ingested_for_their_event(client, make_event):
    """Given an event with an ingested photo, when a guest opens the gallery,
    then they see that photo with viewable URLs."""
    event = make_event("Live Event")
    pid = event["photographer"]["id"]
    token = token_from_gallery_url(event["gallery_url"])

    assert ingest_photo(client, pid).status_code == 200

    resp = client.get(f"/g/{token}/photos")
    assert resp.status_code == 200
    photos = resp.json()["photos"]
    assert len(photos) == 1
    assert photos[0]["url"].endswith(f"raw/{pid}/shot.jpg")
    assert photos[0]["thumb_url"] is not None


def test_gallery_meta_reports_count_and_poll_interval(client, make_event):
    """The gallery page metadata drives the live PWA (count + poll cadence)."""
    event = make_event("Meta Event")
    token = token_from_gallery_url(event["gallery_url"])
    ingest_photo(client, event["photographer"]["id"], "a.jpg")

    meta = client.get(f"/g/{token}").json()
    assert meta["name"] == "Meta Event"
    assert meta["photo_count"] == 1
    assert meta["poll_interval_ms"] > 0


def test_gallery_is_not_reachable_via_the_slug(client, make_event):
    """The slug must NOT open the gallery — only the unguessable token does."""
    event = make_event("Private Event")
    resp = client.get(f"/g/{event['slug']}")
    assert resp.status_code == 404


def test_unknown_token_is_not_found(client, make_event):
    """An unknown/guessed token reveals nothing."""
    make_event("Some Event")
    assert client.get("/g/not-a-real-token/photos").status_code == 404


def test_disabled_event_gallery_is_closed(client, make_event):
    """When an event is disabled, then its gallery returns 404."""
    event = make_event("To Be Disabled")
    token = token_from_gallery_url(event["gallery_url"])
    assert client.get(f"/g/{token}").status_code == 200

    disable_event(token)
    assert client.get(f"/g/{token}").status_code == 404
    assert client.get(f"/g/{token}/photos").status_code == 404


def test_live_polling_returns_only_photos_newer_than_cursor(client, make_event):
    """Given a cursor from a first poll, when new photos arrive, then a poll
    with ?since= returns only the new ones (live update contract)."""
    event = make_event("Polling Event")
    pid = event["photographer"]["id"]
    token = token_from_gallery_url(event["gallery_url"])

    ingest_photo(client, pid, "first.jpg")
    first = client.get(f"/g/{token}/photos").json()
    assert len(first["photos"]) == 1
    cursor = first["cursor"]

    ingest_photo(client, pid, "second.jpg")
    page = client.get(f"/g/{token}/photos", params={"since": cursor}).json()
    names = [p["url"].rsplit("/", 1)[1] for p in page["photos"]]
    assert names == ["second.jpg"]
