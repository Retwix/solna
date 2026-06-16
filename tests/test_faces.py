"""Behaviour: faces are stored on ingest, and the guest selfie match flow."""
import json

import pytest
from sqlalchemy import select

from conftest import token_from_gallery_url

INGEST_KEY = "test-key"


def _ingest(client, event_id, name, embeddings):
    """Ingest a photo with one face per embedding."""
    return client.post(
        "/internal/ingest",
        json={
            "event_id": event_id,
            "s3_raw_key": f"raw/{event_id}/{name}",
            "s3_thumb_key": f"thumbs/{event_id}/{name}",
            "faces": [{"embedding": e, "det_score": 1.0} for e in embeddings],
        },
        headers={"X-Ingest-Key": INGEST_KEY},
    )


def test_ingest_stores_faces_and_face_count(client, make_event):
    """A photo ingested with faces persists Face rows and a face_count."""
    from database import SessionLocal
    from models import Face

    event = make_event("Faces Event")
    assert _ingest(client, event["id"], "a.jpg", [[1, 0, 0], [0, 1, 0]]).status_code == 200

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
    _ingest(client, event["id"], "me.jpg", [[1.0, 0.0, 0.0]])
    _ingest(client, event["id"], "other.jpg", [[0.0, 1.0, 0.0]])

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
    _ingest(client, event["id"], "me.jpg", [[1.0, 0.0, 0.0]])

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
