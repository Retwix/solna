"""Behaviour: faces are stored on ingest, and the guest selfie match flow."""
import json

import pytest
from sqlalchemy import select

from conftest import ingest_photo, photo_name, token_from_gallery_url


def _ingest(client, event, name, embeddings):
    """Ingest a photo (via the live photographer) with one face per embedding."""
    return ingest_photo(
        client, event["photographer"]["id"], name,
        faces=[{"embedding": e, "det_score": 1.0} for e in embeddings],
    )


def test_ingest_stores_faces_and_face_count(client, make_event):
    """A photo ingested with faces persists Face rows and a face_count."""
    from database import SessionLocal
    from models import Face

    event = make_event("Faces Event")
    assert _ingest(client, event, "a.jpg", [[1, 0, 0], [0, 1, 0]]).status_code == 200

    db = SessionLocal()
    try:
        faces = db.scalars(select(Face).where(Face.event_id == event["id"])).all()
        assert len(faces) == 2
        assert json.loads(faces[0].embedding)  # stored as JSON
    finally:
        db.close()


def test_selfie_match_returns_photos_the_guest_appears_in(client, make_event, monkeypatch):
    """A selfie matches photos containing a similar face, and skips others."""
    import face_client

    event = make_event("Match Event")
    token = token_from_gallery_url(event["gallery_url"])

    # Two photos: one with "my" face, one with someone else.
    _ingest(client, event, "me.jpg", [[1.0, 0.0, 0.0]])
    _ingest(client, event, "other.jpg", [[0.0, 1.0, 0.0]])

    # The face service "detects" my face in the selfie.
    monkeypatch.setattr(
        face_client, "embed_image",
        lambda data, filename="selfie.jpg": [{"embedding": [1.0, 0.0, 0.0], "det_score": 0.99}],
    )

    r = client.post(
        f"/g/{token}/match",
        data={"email": "guest@example.com"},
        files={"file": ("selfie.jpg", b"fake-bytes", "image/jpeg")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["match_count"] == 1
    assert photo_name(body["photos"][0]["url"]) == "me.jpg"


def test_match_persists_the_guest(client, make_event, monkeypatch):
    """Submitting a selfie records the guest (email + embedding, not raw selfie)."""
    import face_client
    from database import SessionLocal
    from models import Guest

    event = make_event("Guest Event")
    token = token_from_gallery_url(event["gallery_url"])
    _ingest(client, event, "me.jpg", [[1.0, 0.0, 0.0]])

    monkeypatch.setattr(
        face_client, "embed_image",
        lambda data, filename="selfie.jpg": [{"embedding": [1.0, 0.0, 0.0], "det_score": 1.0}],
    )
    client.post(
        f"/g/{token}/match",
        data={"email": "alice@example.com"},
        files={"file": ("selfie.jpg", b"x", "image/jpeg")},
    )

    db = SessionLocal()
    try:
        guest = db.scalar(select(Guest).where(Guest.email == "alice@example.com"))
        assert guest is not None
        assert guest.event_id == event["id"]
        assert guest.match_count == 1
    finally:
        db.close()


def test_returning_guest_refetches_matches_without_a_new_selfie(client, make_event, monkeypatch):
    """The match response carries a guest token; GET /g/{token}/matches?guest=
    returns the CURRENT matches — including photos that arrived after the
    selfie — so a page refresh (or revisit) never forces a retake."""
    import face_client

    event = make_event("Returning Guest Event")
    token = token_from_gallery_url(event["gallery_url"])
    _ingest(client, event, "me-1.jpg", [[1.0, 0.0, 0.0]])

    monkeypatch.setattr(
        face_client, "embed_image",
        lambda data, filename="selfie.jpg": [{"embedding": [1.0, 0.0, 0.0], "det_score": 1.0}],
    )
    first = client.post(
        f"/g/{token}/match",
        data={"email": "guest@example.com"},
        files={"file": ("selfie.jpg", b"x", "image/jpeg")},
    ).json()
    guest_token = first["guest_token"]
    assert guest_token

    # More photos arrive after the selfie: one of me, one of someone else.
    _ingest(client, event, "me-2.jpg", [[0.99, 0.1, 0.0]])
    _ingest(client, event, "other.jpg", [[0.0, 1.0, 0.0]])

    r = client.get(f"/g/{token}/matches", params={"guest": guest_token})
    assert r.status_code == 200
    body = r.json()
    assert body["match_count"] == 2
    names = sorted(photo_name(p["url"]) for p in body["photos"])
    assert names == ["me-1.jpg", "me-2.jpg"]


def test_guest_token_is_scoped_and_unguessable(client, make_event, monkeypatch):
    """A wrong guest token 404s; a valid token from ANOTHER event 404s too."""
    import face_client

    event_a = make_event("Event A")
    event_b = make_event("Event B")
    token_a = token_from_gallery_url(event_a["gallery_url"])
    token_b = token_from_gallery_url(event_b["gallery_url"])
    _ingest(client, event_a, "me.jpg", [[1.0, 0.0, 0.0]])

    monkeypatch.setattr(
        face_client, "embed_image",
        lambda data, filename="selfie.jpg": [{"embedding": [1.0, 0.0, 0.0], "det_score": 1.0}],
    )
    guest_token = client.post(
        f"/g/{token_a}/match",
        data={"email": "guest@example.com"},
        files={"file": ("selfie.jpg", b"x", "image/jpeg")},
    ).json()["guest_token"]

    assert client.get(f"/g/{token_a}/matches", params={"guest": "nope"}).status_code == 404
    assert client.get(f"/g/{token_b}/matches", params={"guest": guest_token}).status_code == 404


def test_match_rejects_selfie_with_no_face(client, make_event, monkeypatch):
    """If no face is detected in the selfie, the guest gets a clear 422."""
    import face_client

    event = make_event("No Face Event")
    token = token_from_gallery_url(event["gallery_url"])

    monkeypatch.setattr(face_client, "embed_image", lambda data, filename="selfie.jpg": [])
    r = client.post(
        f"/g/{token}/match",
        data={"email": "guest@example.com"},
        files={"file": ("selfie.jpg", b"x", "image/jpeg")},
    )
    assert r.status_code == 422


def test_a_slow_face_service_does_not_stall_other_requests(client, make_event, monkeypatch):
    """While one guest's selfie waits on the face service, the API keeps
    answering everyone else (live galleries, other guests)."""
    import threading

    import face_client

    event = make_event("Busy Event")
    token = token_from_gallery_url(event["gallery_url"])
    selfie_in_flight = threading.Event()
    release_face_service = threading.Event()

    def slow_embed(data, filename="selfie.jpg"):
        selfie_in_flight.set()
        release_face_service.wait(timeout=5)
        return [{"embedding": [1.0, 0.0, 0.0], "det_score": 0.99}]

    monkeypatch.setattr(face_client, "embed_image", slow_embed)

    selfie = threading.Thread(target=lambda: client.post(
        f"/g/{token}/match",
        data={"email": "guest@example.com"},
        files={"file": ("selfie.jpg", b"fake-bytes", "image/jpeg")},
    ))
    selfie.start()
    assert selfie_in_flight.wait(timeout=5)

    other = {}
    meta = threading.Thread(target=lambda: other.update(r=client.get(f"/g/{token}")))
    meta.start()
    meta.join(timeout=2)
    answered_while_selfie_pending = not meta.is_alive()

    release_face_service.set()
    selfie.join(timeout=5)
    meta.join(timeout=5)
    assert answered_while_selfie_pending
    assert other["r"].status_code == 200
