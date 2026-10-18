"""Solna ingest pipeline.

Runs inside the FTP server: for each image fully received into the intake
directory ({FTP_ROOT}/raw/{photographer_id}/...) it:
  1. uploads the original to storage at raw/{photographer_id}/<hash>-<name>
  2. generates a thumbnail and uploads it to thumbs/{photographer_id}/<hash>-<name>
  3. calls the face service to detect + embed faces
  4. notifies the API (/internal/ingest) with the photographer, keys and faces
  5. removes the file from the inbox (anything left there is still pending)

The pipeline does NOT know the event: it reports who uploaded, and the API
resolves the account's active event (or holds the photo unassigned). Faces are
embedded here, on ingest; matching a specific guest happens later (at selfie
time) against these stored embeddings.
"""
import hashlib
import io
import logging
import os
import time
from pathlib import Path

import boto3
import requests
from botocore.client import Config as BotoConfig
from PIL import Image, ImageOps

log = logging.getLogger("ingest")

FTP_ROOT = os.getenv("FTP_ROOT", "/data/ftp")
RAW_ROOT = Path(FTP_ROOT) / "raw"
# Internal API address the pipeline posts ingests to (NOT the public gallery URL).
API_BASE = os.getenv("API_INTERNAL_URL", "http://api:8000")
INGEST_URL = f"{API_BASE.rstrip('/')}/internal/ingest"
INGEST_KEY = os.getenv("INGEST_API_KEY", "dev-ingest-key")
FACE_SERVICE_URL = os.getenv("FACE_SERVICE_URL", "http://faceservice:9000")

S3_BUCKET = os.getenv("S3_BUCKET", "solna-media")
THUMB_MAX = 800  # longest edge, px
VALID_EXT = {".jpg", ".jpeg", ".png"}
INGEST_ATTEMPTS = 5  # backoff 1+2+4+8 s rides out an API restart

s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_ENDPOINT") or None,
    aws_access_key_id=os.getenv("S3_ACCESS_KEY", "minioadmin"),
    aws_secret_access_key=os.getenv("S3_SECRET_KEY", "minioadmin"),
    region_name=os.getenv("S3_REGION", "us-east-1"),
    config=BotoConfig(signature_version="s3v4"),
)


def _photographer_id_from_path(path: Path) -> str | None:
    """raw/{photographer_id}/<file> -> photographer_id"""
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
    photographer_id = _photographer_id_from_path(path)
    if not photographer_id:
        return

    data = path.read_bytes()
    name = path.name

    stored_name = f"{hashlib.sha256(data).hexdigest()[:32]}-{name}"
    raw_key = f"raw/{photographer_id}/{stored_name}"
    thumb_key = f"thumbs/{photographer_id}/{stored_name}"

    s3.put_object(Bucket=S3_BUCKET, Key=raw_key, Body=data, ContentType="image/jpeg")

    try:
        thumb = _make_thumbnail(data)
        s3.put_object(Bucket=S3_BUCKET, Key=thumb_key, Body=thumb, ContentType="image/jpeg")
    except Exception as e:  # noqa: BLE001 - a bad thumbnail shouldn't drop the photo
        log.warning("thumbnail failed for %s: %s", name, e)
        thumb_key = None

    # V1: detect + embed faces via the face service. A failure here must not
    # drop the photo — it still belongs in the gallery, just without matches.
    faces = _embed_faces(data, name)

    _notify_api({
        "photographer_id": photographer_id,
        "s3_raw_key": raw_key,
        "s3_thumb_key": thumb_key,
        "faces": faces,
    })
    path.unlink()
    log.info("ingested %s (%d face(s))", raw_key, len(faces))


def _notify_api(payload: dict) -> None:
    for attempt in range(INGEST_ATTEMPTS):
        try:
            resp = requests.post(
                INGEST_URL, json=payload, headers={"X-Ingest-Key": INGEST_KEY}, timeout=30
            )
            resp.raise_for_status()
            return
        except requests.RequestException:
            if attempt == INGEST_ATTEMPTS - 1:
                raise
            time.sleep(2 ** attempt)


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
        log.warning("face embedding failed for %s, stored without faces: %s", name, e)
        return []


def _is_image(path: Path) -> bool:
    return path.suffix.lower() in VALID_EXT


def handle_upload(path: Path) -> None:
    """Entry point for each file the FTP server has fully received."""
    if not _is_image(path):
        return
    process_image(path)


def pending_photos() -> list[Path]:
    """Files left in the inbox by a crash or a long API outage."""
    return sorted(RAW_ROOT.glob("*/*"))
