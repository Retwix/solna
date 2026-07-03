import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    # Client-side, microsecond-precision timestamp. Keeps the gallery "since"
    # cursor reliable across Postgres and SQLite (SQLite NOW() is second-grained).
    return datetime.now(timezone.utc)


class Photographer(Base):
    """The stable FTP account: entered into the camera ONCE.

    Per event, the photographer just picks which event is "live"
    (active_event_id); incoming photos are routed to it. See
    docs/design/photographer-accounts.md.
    """
    __tablename__ = "photographers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)  # for later auth/login
    ftp_username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    # pbkdf2 hash of the stable FTP password; the FTP server verifies against this.
    ftp_password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    # Which event incoming photos are routed to right now. Null = "not live".
    # (use_alter: breaks the photographers<->events FK cycle at create time)
    active_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    photographer_id: Mapped[str] = mapped_column(
        ForeignKey("photographers.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    # High-entropy token that the QR encodes; the gallery is reached via this, never the slug.
    gallery_token: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    # status: active | disabled
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    photos: Mapped[list["Photo"]] = relationship(back_populates="event")


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    photographer_id: Mapped[str] = mapped_column(
        ForeignKey("photographers.id", ondelete="CASCADE"), index=True
    )
    # Nullable: null = the unassigned tray (uploaded while no event was live).
    event_id: Mapped[str | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), index=True, nullable=True
    )
    s3_raw_key: Mapped[str] = mapped_column(String, nullable=False)
    s3_thumb_key: Mapped[str | None] = mapped_column(String, nullable=True)
    # status: ready | unassigned | processing | failed
    status: Mapped[str] = mapped_column(String, default="ready", nullable=False)
    # number of faces detected in this photo (denormalized for quick display)
    face_count: Mapped[int] = mapped_column(default=0, nullable=False)
    shot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    event: Mapped["Event | None"] = relationship(back_populates="photos")
    faces: Mapped[list["Face"]] = relationship(back_populates="photo", cascade="all, delete-orphan")


class Face(Base):
    """One detected face in a photo, with its embedding.

    V1 stores the 512-d embedding as JSON text so matching works on any DB
    (SQLite in tests, Postgres in dev). Switching to pgvector for large-scale
    nearest-neighbour search is a later, isolated optimization.
    """
    __tablename__ = "faces"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id", ondelete="CASCADE"), index=True)
    # denormalized so we can load all faces for an event in one query at match time;
    # nullable while the photo sits in the unassigned tray (fixed up on claim/move)
    event_id: Mapped[str | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), index=True, nullable=True
    )
    embedding: Mapped[str] = mapped_column(Text, nullable=False)  # JSON list[float], L2-normalized
    bbox: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON [x1,y1,x2,y2]
    det_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    photo: Mapped["Photo"] = relationship(back_populates="faces")


class Guest(Base):
    """A guest who took a selfie to find their photos for an event."""
    __tablename__ = "guests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    # High-entropy token returned to the guest's browser so they can re-open
    # their matched gallery (refresh/revisit) without retaking the selfie.
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    selfie_embedding: Mapped[str] = mapped_column(Text, nullable=False)  # JSON list[float]
    match_count: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
