import re
import secrets

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from ftp_provision import ensure_event_intake_dir
from models import Event
from qr import qr_png_base64
from schemas import EventCreate, EventCreated, FtpCredentials
from security import hash_password

router = APIRouter(prefix="/events", tags=["events"])
settings = get_settings()


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "event"
    return f"{base}-{secrets.token_hex(3)}"


@router.post("", response_model=EventCreated, status_code=201)
def create_event(payload: EventCreate, db: Session = Depends(get_db)):
    slug = _slugify(payload.name)
    gallery_token = secrets.token_urlsafe(settings.gallery_token_bytes)
    ftp_username = f"sol_{secrets.token_hex(4)}"
    # Generated once and returned in plaintext here; only the hash is stored.
    ftp_password = secrets.token_urlsafe(12)

    event = Event(
        name=payload.name,
        slug=slug,
        gallery_token=gallery_token,
        ftp_username=ftp_username,
        ftp_password_hash=hash_password(ftp_password),
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # Its intake dir maps to raw/{event_id}/ so uploads land where the watcher looks.
    ensure_event_intake_dir(event.id)

    gallery_url = f"{settings.public_base_url.rstrip('/')}/g/{gallery_token}"

    return EventCreated(
        id=event.id,
        name=event.name,
        slug=event.slug,
        gallery_url=gallery_url,
        qr_png_base64=qr_png_base64(gallery_url),
        ftp=FtpCredentials(
            host=settings.ftp_host,
            port=settings.ftp_port,
            username=ftp_username,
            password=ftp_password,
            directory="/",
        ),
    )
