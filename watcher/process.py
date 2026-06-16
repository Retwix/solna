"""Solna watcher.

Observes the FTP intake directory ({FTP_ROOT}/raw/{event_id}/...). For each new
image it:
  1. uploads the original to storage at raw/{event_id}/<name>
  2. generates a thumbnail and uploads it to thumbs/{event_id}/<name>
  3. (V1) calls the face service to detect + embed faces
  4. notifies the API (/internal/ingest) with the photo keys and any faces

Faces are embedded here, on ingest, and stored against the photo. Matching a
specific guest happens later (at selfie time) against these stored embeddings.
"""
import io
import os
import time
from pathlib import Path

import boto3
import requests
from botocore.client import Config as BotoConfig
from PIL import Image, ImageOps
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

FTP_ROOT = os.getenv("FTP_ROOT", "/data/ftp")
RAW_ROOT = Path(FTP_ROOT) / "raw"
# Internal API address the watcher posts ingests to (NOT the public gallery URL).
API_BASE = os.getenv("API_INTERNAL_URL", "http://api:8000")
INGEST_URL = f"{API_BASE.rstrip('/')}/internal/ingest"
INGEST_KEY = os.getenv("INGEST_API_KEY", "dev-ingest-key")
FACE_SERVICE_URL = os.getenv("FACE_SERVICE_URL", "http://faceservice:9000")

S3_BUCKET = os.getenv("S3_BUCKET", "solna-media")
THUMB_MAX = 800  # longest edge, px
VALID_EXT = {".jpg", ".jpeg", ".png"}

s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_ENDPOINT") or None,
    aws_access_key_id=os.getenv("S3_ACCESS_KEY", "minioadmin"),
    aws_secret_access_key=os.getenv("S3_SECRET_KEY", "minioadmin"),
    region_name=os.getenv("S3_REGION", "us-east-1"),
    config=BotoConfig(signature_version="s3v4"),
)


def _event_id_from_path(path: Path) -> str | None:
    """raw/{event_id}/<file> -> event_id"""
    try:
        rel = path.relative_to(RAW_ROOT)
    except ValueError:
        return None
    parts = rel.parts
    return parts[0] if len(parts) >= 2 else None


def _make_thumbnail(data: bytes) -> bytes:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)  # respect camera orientation
    img.thumbnail((THUMB_MAX, THUMB_MAX))
    if img.mode != "RGB":
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


def process_image(path: Path) -> None:
    event_id = _event_id_from_path(path)
    if not event_id:
        return

    data = path.read_bytes()
    name = path.name

    raw_key = f"raw/{event_id}/{name}"
    thumb_key = f"thumbs/{event_id}/{name}"

    s3.put_object(Bucket=S3_BUCKET, Key=raw_key, Body=data, ContentType="image/jpeg")

    try:
        thumb = _make_thumbnail(data)
        s3.put_object(Bucket=S3_BUCKET, Key=thumb_key, Body=thumb, ContentType="image/jpeg")
    except Exception as e:  # noqa: BLE001 - a bad thumbnail shouldn't drop the photo
        print(f"[watcher] thumbnail failed for {name}: {e}")
        thumb_key = None

    # V1: detect + embed faces via the face service. A failure here must not
    # drop the photo — it still belongs in the gallery, just without matches.
    faces = _embed_faces(data, name)

    resp = requests.post(
        INGEST_URL,
        json={
            "event_id": event_id,
            "s3_raw_key": raw_key,
            "s3_thumb_key": thumb_key,
            "faces": faces,
        },
        headers={"X-Ingest-Key": INGEST_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    print(f"[watcher] ingested {raw_key} ({len(faces)} face(s))")


def _embed_faces(data: bytes, name: str) -> list:
    try:
        resp = requests.post(
            f"{FACE_SERVICE_URL.rstrip('/')}/embed",
            files={"file": (name, data, "application/octet-stream")},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json().get("faces", [])
    except Exception as e:  # noqa: BLE001
        print(f"[watcher] face embedding failed for {name}: {e}")
        return []


def _is_image(path: Path) -> bool:
    return path.suffix.lower() in VALID_EXT


def _wait_until_stable(path: Path, tries: int = 10, interval: float = 0.5) -> bool:
    """Wait for the FTP upload to finish (size stops changing)."""
    last = -1
    for _ in range(tries):
        if not path.exists():
            return False
        size = path.stat().st_size
        if size == last and size > 0:
            return True
        last = size
        time.sleep(interval)
    return path.exists()


class Handler(FileSystemEventHandler):
    def _handle(self, src_path: str) -> None:
        path = Path(src_path)
        if not _is_image(path):
            return
        if not _wait_until_stable(path):
            return
        try:
            process_image(path)
        except Exception as e:  # noqa: BLE001
            print(f"[watcher] error processing {path}: {e}")

    def on_created(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def on_moved(self, event):  # some FTP servers upload to a temp name then rename
        if not event.is_directory:
            self._handle(event.dest_path)


def main() -> None:
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"[watcher] watching {RAW_ROOT}")
    observer = Observer()
    observer.schedule(Handler(), str(RAW_ROOT), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
