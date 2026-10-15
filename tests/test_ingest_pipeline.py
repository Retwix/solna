"""Behaviour: the FTP ingest pipeline (upload received -> processed)."""
import io

from PIL import Image


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


def _fake_backends(monkeypatch):
    """Stand-ins for the network boundaries: S3, the face service and the API.
    Returns (storage, ingested) so tests can read what reached them."""
    import ingest

    storage = _FakeStorage()
    ingested = []

    def post(url, json=None, files=None, headers=None, timeout=None):
        if url.endswith("/internal/ingest"):
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


def test_a_reused_camera_filename_never_overwrites_an_earlier_photo(monkeypatch):
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
