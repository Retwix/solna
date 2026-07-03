import re
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from models import Event, Face, Photo, Photographer
from qr import qr_png_base64
from schemas import ClaimResult, EventCreate, EventCreated, LiveStatus

router = APIRouter(prefix="/events", tags=["events"])
settings = get_settings()


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "event"
    return f"{base}-{secrets.token_hex(3)}"


def _get_event(db: Session, event_id: str) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    return event


@router.post("", response_model=EventCreated, status_code=201)
def create_event(payload: EventCreate, db: Session = Depends(get_db)):
    """Create an event for a photographer. FTP credentials are NOT issued here
    anymore — they live on the photographer account (entered into the camera
    once); routing to this event happens via go-live."""
    if db.get(Photographer, payload.photographer_id) is None:
        raise HTTPException(status_code=404, detail="photographer not found")

    slug = _slugify(payload.name)
    gallery_token = secrets.token_urlsafe(settings.gallery_token_bytes)

    event = Event(
        photographer_id=payload.photographer_id,
        name=payload.name,
        slug=slug,
        gallery_token=gallery_token,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    gallery_url = f"{settings.public_base_url.rstrip('/')}/g/{gallery_token}"

    return EventCreated(
        id=event.id,
        photographer_id=event.photographer_id,
        name=event.name,
        slug=event.slug,
        gallery_url=gallery_url,
        qr_png_base64=qr_png_base64(gallery_url),
    )


@router.post("/{event_id}/go-live", response_model=LiveStatus)
def go_live(event_id: str, db: Session = Depends(get_db)):
    """The one button: route this account's incoming photos to this event.
    Setting active_event_id implicitly un-lives any other event (one live
    event per account, by construction)."""
    event = _get_event(db, event_id)
    photographer = db.get(Photographer, event.photographer_id)
    photographer.active_event_id = event.id
    db.commit()
    return LiveStatus(photographer_id=photographer.id, active_event_id=event.id)


@router.post("/{event_id}/stop", response_model=LiveStatus)
def stop(event_id: str, db: Session = Depends(get_db)):
    """Stop routing to this event (only if it is the one currently live)."""
    event = _get_event(db, event_id)
    photographer = db.get(Photographer, event.photographer_id)
    if photographer.active_event_id == event.id:
        photographer.active_event_id = None
        db.commit()
    return LiveStatus(photographer_id=photographer.id,
                      active_event_id=photographer.active_event_id)


@router.post("/{event_id}/claim-unassigned", response_model=ClaimResult)
def claim_unassigned(event_id: str, db: Session = Depends(get_db)):
    """Bulk-assign the owning photographer's unassigned photos to this event
    (the 'forgot to press go-live' fixup)."""
    event = _get_event(db, event_id)

    tray_ids = list(db.scalars(
        select(Photo.id).where(
            Photo.photographer_id == event.photographer_id,
            Photo.event_id.is_(None),
        )
    ))
    if tray_ids:
        db.execute(
            update(Photo)
            .where(Photo.id.in_(tray_ids))
            .values(event_id=event.id, status="ready")
        )
        # Faces carry a denormalized event_id used at match time — fix it up
        # so claimed photos are matchable.
        db.execute(
            update(Face)
            .where(Face.photo_id.in_(tray_ids))
            .values(event_id=event.id)
        )
        db.commit()
    return ClaimResult(claimed=len(tray_ids))
