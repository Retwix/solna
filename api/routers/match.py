import json
import secrets

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

import face_client
from config import get_settings
from database import get_db
from matching import FaceRecord, match_faces, to_vector
from models import Event, Face, Guest, Photo
from schemas import MatchResult, PhotoOut
from storage import public_url

router = APIRouter(prefix="/g", tags=["match"])
settings = get_settings()


def _get_active_event(db: Session, token: str) -> Event:
    event = db.scalar(select(Event).where(Event.gallery_token == token))
    if event is None or event.status != "active":
        raise HTTPException(status_code=404, detail="gallery not found")
    return event


def _match_event_photos(db: Session, event: Event, query) -> list[str]:
    """Run the guest's embedding against the event's stored faces; return the
    matched photo ids (best-first, as match_faces orders them)."""
    rows = db.scalars(select(Face).where(Face.event_id == event.id)).all()
    records = [FaceRecord(photo_id=f.photo_id, embedding=to_vector(f.embedding)) for f in rows]
    matches = match_faces(query, records, settings.match_similarity_threshold)
    return [m.photo_id for m in matches]


def _result(db: Session, matched_ids: list[str], faces_detected: int, guest_token: str) -> MatchResult:
    photos = (
        {p.id: p for p in db.scalars(select(Photo).where(Photo.id.in_(matched_ids)))}
        if matched_ids else {}
    )
    ordered = [photos[pid] for pid in matched_ids if pid in photos]
    return MatchResult(
        photos=[
            PhotoOut(
                id=p.id,
                url=public_url(p.s3_raw_key),
                thumb_url=public_url(p.s3_thumb_key),
                created_at=p.created_at,
            )
            for p in ordered
        ],
        match_count=len(ordered),
        faces_detected=faces_detected,
        guest_token=guest_token,
    )


@router.post("/{token}/match", response_model=MatchResult)
async def match(
    token: str,
    file: UploadFile,
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    """Guest selfie flow: embed the selfie, match it against the event's stored
    face embeddings, persist the guest, and return the photos they appear in.
    The returned guest_token lets the browser re-open this gallery later.
    """
    event = _get_active_event(db, token)

    selfie = await file.read()
    if not selfie:
        raise HTTPException(status_code=400, detail="empty selfie")

    detected = face_client.embed_image(selfie, file.filename or "selfie.jpg")
    if not detected:
        raise HTTPException(status_code=422, detail="no face detected in selfie")

    # Use the most confident / largest detected face as the query.
    query = max(detected, key=lambda f: f.get("det_score", 0.0))["embedding"]
    matched_ids = _match_event_photos(db, event, query)

    # Persist the guest (store the embedding, not the raw selfie).
    guest_token = secrets.token_urlsafe(16)
    db.add(Guest(
        token=guest_token,
        event_id=event.id,
        email=email,
        selfie_embedding=json.dumps(list(map(float, to_vector(query)))),
        match_count=len(matched_ids),
    ))
    db.commit()

    return _result(db, matched_ids, faces_detected=len(detected), guest_token=guest_token)


@router.get("/{token}/matches", response_model=MatchResult)
def matches(
    token: str,
    guest: str = Query(..., description="guest_token returned by /match"),
    db: Session = Depends(get_db),
):
    """Returning guest: re-run the stored selfie embedding against the event's
    faces. Refresh/revisit never forces a retake, and photos ingested since the
    selfie show up too."""
    event = _get_active_event(db, token)
    g = db.scalar(select(Guest).where(Guest.token == guest, Guest.event_id == event.id))
    if g is None:
        raise HTTPException(status_code=404, detail="guest not found")

    query = to_vector(g.selfie_embedding)
    matched_ids = _match_event_photos(db, event, query)

    g.match_count = len(matched_ids)
    db.commit()

    return _result(db, matched_ids, faces_detected=1, guest_token=g.token)
