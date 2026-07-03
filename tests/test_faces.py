"""Behaviour: faces are stored on ingest, and the guest selfie match flow."""
import json

import pytest
from sqlalchemy import select

from conftest import ingest_photo, token_from_gallery_url


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
    assert body["photos"][0]["url"].endswith("me.jpg")


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
    names = sorted(p["url"].rsplit("/", 1)[1] for p in body["photos"])
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
