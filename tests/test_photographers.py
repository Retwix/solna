"""Behaviour: photographer accounts and active-event routing.

The design (docs/design/photographer-accounts.md): a photographer enters FTP
credentials into their camera ONCE. Per event they press "go live"; incoming
photos are routed to whichever event is live, or held in an unassigned tray.
"""
from conftest import INGEST_KEY, ingest_photo, photo_name, token_from_gallery_url


# --- The account: stable FTP credentials --------------------------------------

def test_photographer_gets_stable_ftp_credentials(make_photographer):
    """Creating a photographer returns the once-only FTP credentials."""
    p = make_photographer("Ana Lens")

    assert p["id"]
    assert p["name"] == "Ana Lens"
    ftp = p["ftp"]
    assert ftp["username"].startswith("sol_")
    assert ftp["password"]
    assert ftp["host"] and ftp["port"]


def test_two_photographers_are_isolated(make_photographer):
    a = make_photographer("A")
    b = make_photographer("B")
    assert a["ftp"]["username"] != b["ftp"]["username"]


# --- Go live / stop ------------------------------------------------------------

def test_ingest_while_live_lands_ready_in_the_active_event(client, make_event):
    """Live event + incoming photo => photo is ready and visible in that gallery."""
    event = make_event("Live Event", full_album=True)
    pid = event["photographer"]["id"]

    assert ingest_photo(client, pid).status_code == 200

    token = token_from_gallery_url(event["gallery_url"])
    photos = client.get(f"/g/{token}/photos").json()["photos"]
    assert len(photos) == 1


def test_ingest_while_not_live_is_held_unassigned(client, make_event):
    """No live event => the photo is never lost, but shows in no gallery."""
    event = make_event("Quiet Event", live=False, full_album=True)
    pid = event["photographer"]["id"]

    assert ingest_photo(client, pid, "early.jpg").status_code == 200

    token = token_from_gallery_url(event["gallery_url"])
    assert client.get(f"/g/{token}/photos").json()["photos"] == []

    tray = client.get(f"/photographers/{pid}/unassigned").json()["photos"]
    assert len(tray) == 1


def test_go_live_switches_the_active_event(client, make_photographer, make_event):
    """One live event per account: going live on B stops routing to A."""
    p = make_photographer("Switcher")
    a = make_event("Event A", photographer=p, live=True, full_album=True)
    b = make_event("Event B", photographer=p, live=False, full_album=True)

    ingest_photo(client, p["id"], "for-a.jpg")
    assert client.post(f"/events/{b['id']}/go-live").status_code == 200
    ingest_photo(client, p["id"], "for-b.jpg")

    token_a = token_from_gallery_url(a["gallery_url"])
    token_b = token_from_gallery_url(b["gallery_url"])
    names_a = [photo_name(x["url"]) for x in client.get(f"/g/{token_a}/photos").json()["photos"]]
    names_b = [photo_name(x["url"]) for x in client.get(f"/g/{token_b}/photos").json()["photos"]]
    assert names_a == ["for-a.jpg"]
    assert names_b == ["for-b.jpg"]


def test_stop_clears_the_active_event(client, make_event):
    """After stop, incoming photos are unassigned again."""
    event = make_event("Stoppable", full_album=True)
    pid = event["photographer"]["id"]

    assert client.post(f"/events/{event['id']}/stop").status_code == 200
    ingest_photo(client, pid, "late.jpg")

    token = token_from_gallery_url(event["gallery_url"])
    assert client.get(f"/g/{token}/photos").json()["photos"] == []
    assert len(client.get(f"/photographers/{pid}/unassigned").json()["photos"]) == 1


# --- The unassigned tray --------------------------------------------------------

def test_claim_unassigned_moves_the_tray_into_an_event(client, make_event):
    """Forgot to go live: bulk-claim attaches the tray to the event."""
    event = make_event("Forgot Go Live", live=False, full_album=True)
    pid = event["photographer"]["id"]

    ingest_photo(client, pid, "one.jpg")
    ingest_photo(client, pid, "two.jpg")

    r = client.post(f"/events/{event['id']}/claim-unassigned")
    assert r.status_code == 200
    assert r.json()["claimed"] == 2

    token = token_from_gallery_url(event["gallery_url"])
    assert len(client.get(f"/g/{token}/photos").json()["photos"]) == 2
    assert client.get(f"/photographers/{pid}/unassigned").json()["photos"] == []


def test_a_single_photo_can_be_moved_between_events(client, make_photographer, make_event):
    """Manual fixup: PATCH a photo from one event to another."""
    p = make_photographer("Mover")
    a = make_event("Event A", photographer=p, live=True, full_album=True)
    b = make_event("Event B", photographer=p, live=False, full_album=True)

    photo_id = ingest_photo(client, p["id"], "misfiled.jpg").json()["id"]

    r = client.patch(f"/photos/{photo_id}", json={"event_id": b["id"]})
    assert r.status_code == 200

    token_a = token_from_gallery_url(a["gallery_url"])
    token_b = token_from_gallery_url(b["gallery_url"])
    assert client.get(f"/g/{token_a}/photos").json()["photos"] == []
    assert len(client.get(f"/g/{token_b}/photos").json()["photos"]) == 1


def test_claimed_photo_faces_become_matchable(client, make_event, monkeypatch):
    """Faces carry a denormalized event_id; claiming must fix it, or matching
    would silently skip claimed photos."""
    import face_client

    event = make_event("Claim Then Match", live=False)
    pid = event["photographer"]["id"]

    ingest_photo(client, pid, "me.jpg",
                 faces=[{"embedding": [1.0, 0.0, 0.0], "det_score": 1.0}])
    client.post(f"/events/{event['id']}/claim-unassigned")

    monkeypatch.setattr(
        face_client, "embed_image",
        lambda data, filename="selfie.jpg": [{"embedding": [1.0, 0.0, 0.0], "det_score": 0.99}],
    )
    token = token_from_gallery_url(event["gallery_url"])
    r = client.post(
        f"/g/{token}/match",
        data={"email": "guest@example.com"},
        files={"file": ("selfie.jpg", b"x", "image/jpeg")},
    )
    assert r.status_code == 200
    assert r.json()["match_count"] == 1


# --- Event creation no longer carries FTP credentials ----------------------------

def test_event_creation_requires_a_photographer(client):
    assert client.post("/events", json={"name": "Orphan Event"}).status_code == 422


def test_event_response_has_gallery_but_no_ftp_credentials(make_event):
    event = make_event("No Creds Event")
    assert "/g/" in event["gallery_url"]
    assert "ftp" not in event
