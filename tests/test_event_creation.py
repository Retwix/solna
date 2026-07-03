"""Behaviour: creating an event (now owned by a photographer)."""
import base64

from conftest import token_from_gallery_url


def test_creating_an_event_returns_the_guest_side_essentials(make_event):
    """Given a name, when an event is created, then the guest gets a QR and a
    gallery URL. (FTP credentials now come from photographer creation.)"""
    data = make_event("Summer Wedding")

    assert data["name"] == "Summer Wedding"
    assert "/g/" in data["gallery_url"]

    # QR is a real PNG of the gallery URL.
    png = base64.b64decode(data["qr_png_base64"])
    assert png.startswith(b"\x89PNG\r\n")


def test_each_event_is_isolated_by_token_and_slug(make_event):
    """When two events exist, then their gallery tokens and slugs are distinct
    (no cross-event access)."""
    a = make_event("Event A")
    b = make_event("Event B")

    assert token_from_gallery_url(a["gallery_url"]) != token_from_gallery_url(b["gallery_url"])
    assert a["slug"] != b["slug"]


def test_event_belongs_to_its_photographer(make_photographer, make_event):
    p = make_photographer("Owner")
    event = make_event("Owned Event", photographer=p)
    assert event["photographer_id"] == p["id"]
