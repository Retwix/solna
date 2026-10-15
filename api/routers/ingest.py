import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Face, Photo, Photographer
from schemas import IngestIn, PhotoOut
from security import require_ingest_key
from storage import public_url

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/ingest", response_model=PhotoOut, dependencies=[Depends(require_ingest_key)])
def ingest(payload: IngestIn, db: Session = Depends(get_db)):
    """Register a photo the FTP ingest pipeline has uploaded, plus any faces it detected.

    The pipeline only knows WHO uploaded (the photographer id from the path);
    this endpoint resolves WHERE it goes: the account's active event, or the
    unassigned tray if no event is live. The rule lives here, in one DB read.
    """
    photographer = db.get(Photographer, payload.photographer_id)
    if photographer is None:
        raise HTTPException(status_code=404, detail="photographer not found")

    event_id = photographer.active_event_id  # may be None = "not live"
    photo = Photo(
        photographer_id=photographer.id,
        event_id=event_id,
        s3_raw_key=payload.s3_raw_key,
        s3_thumb_key=payload.s3_thumb_key,
        shot_at=payload.shot_at,
        status="ready" if event_id else "unassigned",
        face_count=len(payload.faces),
    )
    db.add(photo)
    db.flush()  # assign photo.id before inserting faces

    for f in payload.faces:
        db.add(Face(
            photo_id=photo.id,
            event_id=event_id,
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
