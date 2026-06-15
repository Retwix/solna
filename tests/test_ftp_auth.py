"""Behaviour: FTP credentials issued at event creation can be authenticated.

These cover the contract the FTP server relies on (api/security.py hashing),
without needing the FTP server itself running.
"""
from sqlalchemy import select

from conftest import token_from_gallery_url  # noqa: F401  (kept for symmetry)
from security import hash_password, verify_password


def test_password_hash_round_trips_and_rejects_wrong():
    """A hashed password verifies; a wrong one does not."""
    stored = hash_password("super-secret")
    assert verify_password("super-secret", stored)
    assert not verify_password("not-it", stored)
    assert not verify_password("super-secret", "garbage")


def test_each_hash_is_salted_and_unique():
    """Hashing the same password twice yields different stored values (salt)."""
    assert hash_password("same") != hash_password("same")


def test_event_creation_stores_a_verifiable_ftp_password(client, make_event):
    """The plaintext FTP password returned to the photographer verifies against
    the hash stored on the event — the exact check the FTP server performs."""
    from database import SessionLocal
    from models import Event

    data = make_event("FTP Auth Event")
    plaintext = data["ftp"]["password"]

    db = SessionLocal()
    try:
        event = db.scalar(select(Event).where(Event.id == data["id"]))
        assert event.ftp_password_hash  # only the hash is persisted
        assert event.ftp_password_hash != plaintext
        assert verify_password(plaintext, event.ftp_password_hash)
        assert not verify_password("wrong-password", event.ftp_password_hash)
    finally:
        db.close()
