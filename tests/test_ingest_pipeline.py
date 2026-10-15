"""Behaviour: the FTP ingest pipeline (upload received -> processed)."""
import io

import pytest
from PIL import Image


@pytest.fixture()
def inbox(tmp_path, monkeypatch):
    """A fresh FTP intake root per test, so leftover photos never leak."""
    import ingest

    monkeypatch.setattr(ingest, "RAW_ROOT", tmp_path / "raw")


def _img_bytes(size, mode="RGB", fmt="JPEG"):
    img = Image.new(mode, size, color=(120, 90, 60) if mode == "RGB" else (120, 90, 60, 255))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_thumbnail_is_downscaled_and_jpeg():
    """A large photo is downscaled to the thumbnail bound and re-encoded JPEG."""
    import ingest

    out = ingest._make_thumbnail(_img_bytes((3000, 2000)))
    thumb = Image.open(io.BytesIO(out))
    assert thumb.format == "JPEG"
    assert max(thumb.size) <= ingest.THUMB_MAX


def test_thumbnail_flattens_transparency_to_rgb():
    """A PNG with alpha is converted to RGB so it can be saved as JPEG."""
    import ingest

    out = ingest._make_thumbnail(_img_bytes((1000, 1000), mode="RGBA", fmt="PNG"))
    assert Image.open(io.BytesIO(out)).mode == "RGB"


def test_photographer_id_is_parsed_from_intake_path():
    """raw/{photographer_id}/<file> resolves to the account; files outside don't."""
    import ingest

    inside = ingest.RAW_ROOT / "ph-123" / "photo.jpg"
    assert ingest._photographer_id_from_path(inside) == "ph-123"

    loose = ingest.RAW_ROOT / "stray.jpg"  # no account folder
    assert ingest._photographer_id_from_path(loose) is None


def test_only_image_files_are_processed():
    """Non-image files (e.g. a stray .txt) are ignored by the pipeline."""
    import ingest
    from pathlib import Path

    assert ingest._is_image(Path("a.JPG"))
    assert ingest._is_image(Path("a.png"))
    assert not ingest._is_image(Path("notes.txt"))


def test_a_photo_is_processed_once_its_upload_completes_not_while_it_stalls(tmp_path):
    """A camera on flaky Wi-Fi pauses mid-upload. The photo must reach the
    pipeline exactly once, whole, after the transfer ends — never half-written."""
    import ftplib
    import threading
    import time

    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.servers import FTPServer

    import server

    home = tmp_path / "raw" / "ph-1"
    home.mkdir(parents=True)
    authorizer = DummyAuthorizer()
    authorizer.add_user("cam", "pw", str(home), perm="elradfmwMT")

    received = []
    done = threading.Event()

    def on_photo(path):
        received.append((path.name, path.read_bytes()))
        done.set()

    ftpd = FTPServer(("127.0.0.1", 0), server.make_handler(authorizer, on_photo))
    stop = threading.Event()

    def serve():
        while not stop.is_set():
            ftpd.serve_forever(timeout=0.05, blocking=False)

    loop = threading.Thread(target=serve, daemon=True)
    loop.start()
    try:
        ftp = ftplib.FTP()
        ftp.connect("127.0.0.1", ftpd.address[1])
        ftp.login("cam", "pw")
        photo = b"\xff\xd8" + b"x" * 200_000
        data = ftp.transfercmd("STOR DSC00001.JPG")
        data.sendall(photo[:100_000])
        time.sleep(1.0)
        processed_during_stall = list(received)
        data.sendall(photo[100_000:])
        data.close()
        ftp.voidresp()
        ftp.quit()

        assert done.wait(timeout=5)
        assert processed_during_stall == []
        assert received == [("DSC00001.JPG", photo)]
    finally:
        stop.set()
        loop.join(timeout=5)
        ftpd.close_all()


class _FakeStorage:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body


class _FakeResponse:
    def __init__(self, payload=None):
        self._payload = payload or {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _fake_backends(monkeypatch, api_down_for=0):
    """Stand-ins for the network boundaries: S3, the face service and the API
    (unreachable for its first `api_down_for` calls). Returns (storage,
    ingested) so tests can read what reached them."""
    import ingest

    storage = _FakeStorage()
    ingested = []
    api_calls = []

    def post(url, json=None, files=None, headers=None, timeout=None):
        if url.endswith("/internal/ingest"):
            api_calls.append(json)
            if len(api_calls) <= api_down_for:
                raise ingest.requests.ConnectionError("api unreachable")
            ingested.append(json)
        return _FakeResponse({"faces": []})

    monkeypatch.setattr(ingest, "s3", storage)
    monkeypatch.setattr(ingest.requests, "post", post)
    return storage, ingested


def _drop(photographer_id, name, data):
    import ingest

    path = ingest.RAW_ROOT / photographer_id / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_a_reused_camera_filename_never_overwrites_an_earlier_photo(monkeypatch, inbox):
    """Cameras restart their numbering (new card, counter wrap, next event), so
    the same filename arrives twice. Both photos must survive in storage."""
    import ingest

    storage, ingested = _fake_backends(monkeypatch)
    first, second = _img_bytes((40, 30)), _img_bytes((30, 40))

    ingest.process_image(_drop("ph-1", "DSC00042.JPG", first))
    ingest.process_image(_drop("ph-1", "DSC00042.JPG", second))

    raw_keys = [p["s3_raw_key"] for p in ingested]
    thumb_keys = [p["s3_thumb_key"] for p in ingested]
    assert [storage.objects[k] for k in raw_keys] == [first, second]
    assert [Image.open(io.BytesIO(storage.objects[k])).size for k in thumb_keys] == [(40, 30), (30, 40)]


def test_a_photo_survives_a_brief_api_outage(monkeypatch, inbox):
    """The API restarting (deploy, crash) while a photo arrives must not lose it."""
    import ingest

    _, ingested = _fake_backends(monkeypatch, api_down_for=2)
    waits = []
    monkeypatch.setattr("time.sleep", waits.append)

    ingest.process_image(_drop("ph-1", "DSC00100.JPG", _img_bytes((40, 30))))

    assert len(ingested) == 1
    assert len(waits) == 2 and all(w > 0 for w in waits)  # backs off, doesn't hammer


def test_the_inbox_keeps_only_photos_not_yet_ingested(monkeypatch, inbox):
    """A registered photo leaves the FTP inbox (storage has it); one the API
    never accepted stays there to be retried on the next start."""
    import ingest

    monkeypatch.setattr("time.sleep", lambda seconds: None)
    _fake_backends(monkeypatch)
    done = _drop("ph-1", "DSC00200.JPG", _img_bytes((40, 30)))
    ingest.handle_upload(done)

    _fake_backends(monkeypatch, api_down_for=ingest.INGEST_ATTEMPTS)
    stuck = _drop("ph-1", "DSC00201.JPG", _img_bytes((40, 30)))
    ingest.handle_upload(stuck)

    assert not done.exists()
    assert stuck.exists()


def test_photos_left_in_the_inbox_are_ingested_when_the_server_starts(monkeypatch, inbox):
    """Photos the API never accepted (or that arrived while the server was
    down mid-processing) are picked up on the next start, images only."""
    import ingest

    _, ingested = _fake_backends(monkeypatch)
    _drop("ph-1", "DSC00300.JPG", _img_bytes((40, 30)))
    _drop("ph-2", "IMG_0001.png", _img_bytes((40, 30), fmt="PNG"))
    notes = _drop("ph-2", "notes.txt", b"not a photo")

    ingest.recover_inbox()

    assert sorted(p["photographer_id"] for p in ingested) == ["ph-1", "ph-2"]
    assert notes.exists()
