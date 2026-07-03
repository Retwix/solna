from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from database import get_db
from models import Event, Face, Photo
from schemas import PhotoMove, PhotoOut
from storage import public_url

router = APIRouter(prefix="/photos", tags=["photos"])


@router.patch("/{photo_id}", response_model=PhotoOut)
def move_photo(photo_id: str, payload: PhotoMove, db: Session = Depends(get_db)):
    """Manual fixup: move a single photo to a different event (or back to the
    tray with event_id=null). Event membership is only a column, so this never
    touches storage."""
    photo = db.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="photo not found")

    if payload.event_id is not None:
        event = db.get(Event, payload.event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="event not found")
        if event.photographer_id != photo.photographer_id:
            raise HTTPException(status_code=403, detail="photo belongs to another account")

    photo.event_id = payload.event_id
    photo.status = "ready" if payload.event_id else "unassigned"
    # Keep the denormalized face event_id consistent (used at match time).
    db.execute(
        update(Face).where(Face.photo_id == photo.id).values(event_id=payload.event_id)
    )
    db.commit()
    db.refresh(photo)

    return PhotoOut(
        id=photo.id,
        url=public_url(photo.s3_raw_key),
        thumb_url=public_url(photo.s3_thumb_key),
        created_at=photo.created_at,
    )
