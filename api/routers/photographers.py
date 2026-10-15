import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from models import Photo, Photographer
from schemas import FtpCredentials, PhotographerCreate, PhotographerCreated, PhotoPage
from security import hash_password
from storage import photo_out

router = APIRouter(prefix="/photographers", tags=["photographers"])
settings = get_settings()


@router.post("", response_model=PhotographerCreated, status_code=201)
def create_photographer(payload: PhotographerCreate, db: Session = Depends(get_db)):
    """The once-only setup: create the account and hand back the stable FTP
    credentials the photographer enters into their camera."""
    ftp_username = f"sol_{secrets.token_hex(4)}"
    # Generated once and returned in plaintext here; only the hash is stored.
    ftp_password = secrets.token_urlsafe(12)

    photographer = Photographer(
        name=payload.name,
        email=payload.email,
        ftp_username=ftp_username,
        ftp_password_hash=hash_password(ftp_password),
    )
    db.add(photographer)
    db.commit()
    db.refresh(photographer)

    return PhotographerCreated(
        id=photographer.id,
        name=photographer.name,
        ftp=FtpCredentials(
            host=settings.ftp_host,
            port=settings.ftp_port,
            username=ftp_username,
            password=ftp_password,
            directory="/",
        ),
    )


@router.get("/{photographer_id}/unassigned", response_model=PhotoPage)
def unassigned_photos(photographer_id: str, db: Session = Depends(get_db)):
    """The tray: photos uploaded while no event was live. Never lost, never
    shown in any gallery — waiting to be claimed into an event."""
    if db.get(Photographer, photographer_id) is None:
        raise HTTPException(status_code=404, detail="photographer not found")

    photos = list(db.scalars(
        select(Photo)
        .where(Photo.photographer_id == photographer_id, Photo.event_id.is_(None))
        .order_by(Photo.created_at.asc())
    ))
    return PhotoPage(
        photos=[
            photo_out(p)
            for p in photos
        ],
        cursor=photos[-1].id if photos else None,
    )
