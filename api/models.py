import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    # Client-side, microsecond-precision timestamp. Keeps the gallery "since"
    # cursor reliable across Postgres and SQLite (SQLite NOW() is second-grained).
    return datetime.now(timezone.utc)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    # High-entropy token that the QR encodes; the gallery is reached via this, never the slug.
    gallery_token: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    ftp_username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    # pbkdf2 hash of the per-event FTP password; the FTP server verifies against this.
    ftp_password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    # status: active | disabled
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    photos: Mapped[list["Photo"]] = relationship(back_populates="event", cascade="all, delete-orphan")


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    s3_raw_key: Mapped[str] = mapped_column(String, nullable=False)
    s3_thumb_key: Mapped[str | None] = mapped_column(String, nullable=True)
    # status: ready (V0). V1 will add: processing | failed while faces are computed.
    status: Mapped[str] = mapped_column(String, default="ready", nullable=False)
    shot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    event: Mapped["Event"] = relationship(back_populates="photos")
