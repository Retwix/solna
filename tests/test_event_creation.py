"""Behaviour: creating an event."""
import base64
import os
from pathlib import Path

from conftest import token_from_gallery_url


def test_creating_an_event_returns_everything_to_start_shooting(make_event):
    """Given a name, when an event is created, then the photographer gets FTP
    credentials and the guest gets a QR/gallery URL."""
    data = make_event("Summer Wedding")

    assert data["name"] == "Summer Wedding"
    assert "/g/" in data["gallery_url"]

    ftp = data["ftp"]
    assert ftp["username"].startswith("sol_")
    assert ftp["password"]
    assert ftp["host"] and ftp["port"]

    # QR is a real PNG of the gallery URL.
    png = base64.b64decode(data["qr_png_base64"])
    assert png.startswith(b"\x89PNG\r\n")


def test_each_event_is_isolated_by_token_and_ftp_user(make_event):
    """When two events exist, then their gallery tokens, FTP users and slugs
    are all distinct (no cross-event access)."""
    a = make_event("Event A")
    b = make_event("Event B")

    assert token_from_gallery_url(a["gallery_url"]) != token_from_gallery_url(b["gallery_url"])
    assert a["ftp"]["username"] != b["ftp"]["username"]
    assert a["slug"] != b["slug"]


def test_creating_an_event_provisions_its_ftp_intake_directory(make_event):
    """When an event is created, then its raw/{event_id}/ intake directory
    exists so uploads land where the watcher looks."""
    data = make_event("With Intake Dir")
    intake = Path(os.environ["FTP_ROOT"]) / "raw" / data["id"]
    assert intake.is_dir()
