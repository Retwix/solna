import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Face, Photo
from schemas import IngestIn, PhotoOut
from security import require_ingest_key
from storage import public_url

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/ingest", response_model=PhotoOut, dependencies=[Depends(require_ingest_key)])
def ingest(payload: IngestIn, db: Session = Depends(get_db)):
    """Register a photo the watcher has uploaded, plus any faces it detected.

    V1: the watcher embeds faces via the face service before calling this, so a
    photo arrives with its faces ready to store. Matching happens later, at guest
    selfie time, against these stored embeddings.
    """
    photo = Photo(
        event_id=payload.event_id,
        s3_raw_key=payload.s3_raw_key,
        s3_thumb_key=payload.s3_thumb_key,
        shot_at=payload.shot_at,
        status="ready",
        face_count=len(payload.faces),
    )
    db.add(photo)
    db.flush()  # assign photo.id before inserting faces

    for f in payload.faces:
        db.add(Face(
            photo_id=photo.id,
            event_id=payload.event_id,
            embedding=json.dumps(f.embedding),
            bbox=json.dumps(f.bbox) if f.bbox is not None else None,
            det_score=f.det_score,
        ))

    db.commit()
    db.refresh(photo)
    return PhotoOut(
        id=photo.id,
        url=public_url(photo.s3_raw_key),
        thumb_url=public_url(photo.s3_thumb_key),
        created_at=photo.created_at,
    )
