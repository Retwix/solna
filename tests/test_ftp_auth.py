"""Behaviour: FTP credentials issued at photographer creation can be authenticated.

These cover the contract the FTP server relies on (api/security.py hashing),
without needing the FTP server itself running.
"""
from sqlalchemy import select

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


def test_photographer_creation_stores_a_verifiable_ftp_password(client, make_photographer):
    """The plaintext FTP password returned once at account creation verifies
    against the stored hash — the exact check the FTP server performs."""
    from database import SessionLocal
    from models import Photographer

    data = make_photographer("FTP Auth Account")
    plaintext = data["ftp"]["password"]

    db = SessionLocal()
    try:
        p = db.scalar(select(Photographer).where(Photographer.id == data["id"]))
        assert p.ftp_password_hash  # only the hash is persisted
        assert p.ftp_password_hash != plaintext
        assert verify_password(plaintext, p.ftp_password_hash)
        assert not verify_password("wrong-password", p.ftp_password_hash)
    finally:
        db.close()
