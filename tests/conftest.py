"""Test setup for Solna V0.

Behaviour tests run the real FastAPI app against an isolated SQLite database and
a temp FTP root, with no S3/FTP network calls (storage URL building is pure
string work, and FTP provisioning only creates a directory).
"""
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "watcher"))

# Configure the environment BEFORE importing app modules (settings are cached).
_TMP = tempfile.mkdtemp(prefix="solna-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{_TMP}/test.db")
os.environ.setdefault("FTP_ROOT", f"{_TMP}/ftp")
os.environ.setdefault("S3_PUBLIC_ENDPOINT", "http://test-s3")
os.environ.setdefault("S3_BUCKET", "solna-media")
os.environ.setdefault("INGEST_API_KEY", "test-key")
os.environ.setdefault("PUBLIC_BASE_URL", "http://testserver")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

INGEST_KEY = os.environ["INGEST_API_KEY"]


@pytest.fixture()
def client():
    from database import Base, engine
    import models  # noqa: F401  (register tables on Base)
    from main import app

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def make_event(client):
    """Create an event and return its API payload."""
    def _make(name="Summer Wedding"):
        resp = client.post("/events", json={"name": name})
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _make


def ingest_photo(client, event_id, name="shot.jpg"):
    """Helper: register a photo the way the watcher would."""
    return client.post(
        "/internal/ingest",
        json={"event_id": event_id, "s3_raw_key": f"raw/{event_id}/{name}",
              "s3_thumb_key": f"thumbs/{event_id}/{name}"},
        headers={"X-Ingest-Key": INGEST_KEY},
    )


def disable_event(token):
    """Flip an event to 'disabled' directly (no admin endpoint in V0)."""
    from sqlalchemy import select
    from database import SessionLocal
    from models import Event

    db = SessionLocal()
    try:
        ev = db.scalar(select(Event).where(Event.gallery_token == token))
        ev.status = "disabled"
        db.commit()
    finally:
        db.close()


def token_from_gallery_url(url: str) -> str:
    return url.rsplit("/g/", 1)[1]
