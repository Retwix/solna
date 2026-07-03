"""Behaviour: the matched gallery updates live — photos of the guest ingested
after the selfie are pushed over SSE, other people's photos are not."""
import asyncio
import json

import pytest

from conftest import disable_event, ingest_photo, token_from_gallery_url


def _ingest(client, event, name, embeddings):
    return ingest_photo(
        client, event["photographer"]["id"], name,
        faces=[{"embedding": e, "det_score": 1.0} for e in embeddings],
    )


def _take_selfie(client, monkeypatch, token, embedding):
    """Guest selfie via /match; returns the guest_token for the stream."""
    import face_client

    monkeypatch.setattr(
        face_client, "embed_image",
        lambda data, filename="selfie.jpg": [{"embedding": embedding, "det_score": 1.0}],
    )
    r = client.post(
        f"/g/{token}/match",
        data={"email": "guest@example.com"},
        files={"file": ("selfie.jpg", b"x", "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    return r.json()["guest_token"]


def _photo_name(sse_event: str) -> str:
    assert sse_event.startswith("data: ")
    return json.loads(sse_event[len("data: "):])["url"].rsplit("/", 1)[1]


def _fast_poll(monkeypatch):
    from routers import match as match_router

    monkeypatch.setattr(match_router.settings, "gallery_poll_interval_ms", 20)


def test_stream_emits_guest_photos_and_skips_other_peoples(client, make_event, monkeypatch):
    """A photo of the guest ingested after the selfie is pushed to their
    stream; a photo of someone else never appears on it."""
    from routers.match import matched_photo_events

    _fast_poll(monkeypatch)
    event = make_event("Live Match Event")
    token = token_from_gallery_url(event["gallery_url"])

    _ingest(client, event, "me-1.jpg", [[1.0, 0.0, 0.0]])
    guest_token = _take_selfie(client, monkeypatch, token, [1.0, 0.0, 0.0])
    _ingest(client, event, "other.jpg", [[0.0, 1.0, 0.0]])

    gen = matched_photo_events(token, guest_token)

    async def scenario():
        # First cycle resyncs from the start: the pre-selfie photo of me.
        first = await asyncio.wait_for(anext(gen), timeout=2)
        # A photo of me ingested while the stream is open arrives next…
        _ingest(client, event, "me-2.jpg", [[0.99, 0.1, 0.0]])
        second = await asyncio.wait_for(anext(gen), timeout=2)
        # …and the other person's photo never does.
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(anext(gen), timeout=0.2)
        return first, second

    first, second = asyncio.run(scenario())
    assert _photo_name(first) == "me-1.jpg"
    assert _photo_name(second) == "me-2.jpg"


def test_stream_closes_when_the_event_stops_being_active(client, make_event, monkeypatch):
    from routers.match import matched_photo_events

    _fast_poll(monkeypatch)
    event = make_event("Ends Event")
    token = token_from_gallery_url(event["gallery_url"])
    _ingest(client, event, "me.jpg", [[1.0, 0.0, 0.0]])
    guest_token = _take_selfie(client, monkeypatch, token, [1.0, 0.0, 0.0])

    disable_event(token)
    gen = matched_photo_events(token, guest_token)

    async def scenario():
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(anext(gen), timeout=2)

    asyncio.run(scenario())


def test_stream_endpoint_applies_the_same_404_semantics_as_matches(client, make_event, monkeypatch):
    """Unknown guest, guest from another event, and disabled event all 404
    before any streaming starts — exactly like GET /matches."""
    event_a = make_event("Stream Event A")
    event_b = make_event("Stream Event B")
    token_a = token_from_gallery_url(event_a["gallery_url"])
    token_b = token_from_gallery_url(event_b["gallery_url"])
    _ingest(client, event_a, "me.jpg", [[1.0, 0.0, 0.0]])
    guest_token = _take_selfie(client, monkeypatch, token_a, [1.0, 0.0, 0.0])

    r = client.get(f"/g/{token_a}/matches/stream", params={"guest": "nope"})
    assert (r.status_code, r.json()["detail"]) == (404, "guest not found")

    r = client.get(f"/g/{token_b}/matches/stream", params={"guest": guest_token})
    assert (r.status_code, r.json()["detail"]) == (404, "guest not found")

    disable_event(token_a)
    r = client.get(f"/g/{token_a}/matches/stream", params={"guest": guest_token})
    assert (r.status_code, r.json()["detail"]) == (404, "gallery not found")
