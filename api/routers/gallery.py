import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import get_settings
from database import SessionLocal, get_db
from models import Event, Photo
from schemas import EventPublic, PhotoOut, PhotoPage
from storage import public_url

router = APIRouter(prefix="/g", tags=["gallery"])
settings = get_settings()


def _get_active_event(db: Session, token: str) -> Event:
    event = db.scalar(select(Event).where(Event.gallery_token == token))
    if event is None or event.status != "active":
        raise HTTPException(status_code=404, detail="gallery not found")
    return event


def _photo_out(p: Photo) -> PhotoOut:
    return PhotoOut(
        id=p.id,
        url=public_url(p.s3_raw_key),
        thumb_url=public_url(p.s3_thumb_key),
        created_at=p.created_at,
    )


@router.get("/{token}", response_model=EventPublic)
def gallery_meta(token: str, db: Session = Depends(get_db)):
    event = _get_active_event(db, token)
    count = len(event.photos)
    return EventPublic(
        name=event.name,
        photo_count=count,
        poll_interval_ms=settings.gallery_poll_interval_ms,
    )


@router.get("/{token}/photos", response_model=PhotoPage)
def gallery_photos(
    token: str,
    since: str | None = Query(default=None, description="cursor: only return photos newer than this id"),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
):
    event = _get_active_event(db, token)

    stmt = select(Photo).where(Photo.event_id == event.id, Photo.status == "ready")
    if since:
        anchor = db.get(Photo, since)
        if anchor is not None:
            stmt = stmt.where(Photo.created_at > anchor.created_at)
    stmt = stmt.order_by(Photo.created_at.asc()).limit(limit)

    photos = list(db.scalars(stmt))
    cursor = photos[-1].id if photos else since
    return PhotoPage(photos=[_photo_out(p) for p in photos], cursor=cursor)


@router.get("/{token}/stream")
async def gallery_stream(token: str):
    """Server-Sent Events: push new photos as they arrive (live gallery).

    Simple poll-the-DB-and-emit loop. Fine for V0 volumes; V1 can swap in a
    queue/pubsub without changing the client contract.
    """

    async def event_generator():
        last_created = None
        while True:
            db = SessionLocal()
            try:
                event = db.scalar(select(Event).where(Event.gallery_token == token))
                if event is None or event.status != "active":
                    break
                stmt = select(Photo).where(Photo.event_id == event.id, Photo.status == "ready")
                if last_created is not None:
                    stmt = stmt.where(Photo.created_at > last_created)
                stmt = stmt.order_by(Photo.created_at.asc())
                for p in db.scalars(stmt):
                    last_created = p.created_at
                    yield f"data: {json.dumps(_photo_out(p).model_dump(mode='json'))}\n\n"
            finally:
                db.close()
            await asyncio.sleep(settings.gallery_poll_interval_ms / 1000)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
