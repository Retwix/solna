from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Photo
from schemas import IngestIn, PhotoOut
from security import require_ingest_key
from storage import public_url

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/ingest", response_model=PhotoOut, dependencies=[Depends(require_ingest_key)])
def ingest(payload: IngestIn, db: Session = Depends(get_db)):
    """Register a photo that the watcher has uploaded to storage.

    V0: photo is immediately 'ready'. V1: the watcher (or this endpoint) would
    enqueue face detection/embedding/styling and the photo would start as
    'processing' until that completes.
    """
    photo = Photo(
        event_id=payload.event_id,
        s3_raw_key=payload.s3_raw_key,
        s3_thumb_key=payload.s3_thumb_key,
        shot_at=payload.shot_at,
        status="ready",
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return PhotoOut(
        id=photo.id,
        url=public_url(photo.s3_raw_key),
        thumb_url=public_url(photo.s3_thumb_key),
        created_at=photo.created_at,
    )
