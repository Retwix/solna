import asyncio
import json
import secrets

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

import face_client
from config import get_settings
from database import SessionLocal, get_db
from matching import FaceRecord, match_faces, to_vector
from models import Event, Face, Guest, Photo
from schemas import MatchResult
from storage import photo_out

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
            photo_out(p)
            for p in ordered
        ],
        match_count=len(ordered),
        faces_detected=faces_detected,
        guest_token=guest_token,
    )


@router.post("/{token}/match", response_model=MatchResult)
def match(
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

    selfie = file.file.read()
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


def _photo_event(p: Photo) -> str:
    out = photo_out(p)
    return f"data: {json.dumps(out.model_dump(mode='json'))}\n\n"


async def matched_photo_events(token: str, guest_token: str):
    """SSE generator for the live matched gallery: poll for photos newer than
    the cursor, match the guest's stored embedding against those photos' faces
    only, and emit each hit. Faces are inserted in the same transaction as
    their photo at ingest, so a photo-level created_at cursor is sound.
    Ends when the event stops being active (or the guest disappears)."""
    last_created = None
    while True:
        db = SessionLocal()
        try:
            event = db.scalar(select(Event).where(Event.gallery_token == token))
            if event is None or event.status != "active":
                break
            g = db.scalar(select(Guest).where(Guest.token == guest_token, Guest.event_id == event.id))
            if g is None:
                break
            query = to_vector(g.selfie_embedding)

            stmt = select(Photo).where(Photo.event_id == event.id, Photo.status == "ready")
            if last_created is not None:
                stmt = stmt.where(Photo.created_at > last_created)
            photos = list(db.scalars(stmt.order_by(Photo.created_at.asc())))
            if photos:
                last_created = photos[-1].created_at
                rows = db.scalars(select(Face).where(Face.photo_id.in_([p.id for p in photos]))).all()
                records = [FaceRecord(photo_id=f.photo_id, embedding=to_vector(f.embedding)) for f in rows]
                matched = {m.photo_id for m in match_faces(query, records, settings.match_similarity_threshold)}
                for p in photos:
                    if p.id in matched:
                        yield _photo_event(p)
        finally:
            db.close()
        await asyncio.sleep(settings.gallery_poll_interval_ms / 1000)


@router.get("/{token}/matches/stream")
def matches_stream(
    token: str,
    guest: str = Query(..., description="guest_token returned by /match"),
    db: Session = Depends(get_db),
):
    """Live matched gallery: validate up front with the same 404 semantics as
    /matches, then push each newly matched photo as an SSE event."""
    event = _get_active_event(db, token)
    g = db.scalar(select(Guest).where(Guest.token == guest, Guest.event_id == event.id))
    if g is None:
        raise HTTPException(status_code=404, detail="guest not found")

    return StreamingResponse(matched_photo_events(token, guest), media_type="text/event-stream")


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
