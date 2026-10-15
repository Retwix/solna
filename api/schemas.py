from datetime import datetime

from pydantic import BaseModel


class FtpCredentials(BaseModel):
    host: str
    port: int
    username: str
    password: str
    directory: str


class PhotographerCreate(BaseModel):
    name: str
    email: str | None = None


class PhotographerCreated(BaseModel):
    id: str
    name: str
    # The stable credentials: shown once, entered into the camera once.
    ftp: FtpCredentials


class EventCreate(BaseModel):
    name: str
    photographer_id: str


class EventCreated(BaseModel):
    id: str
    photographer_id: str
    name: str
    slug: str
    gallery_url: str
    qr_png_base64: str


class LiveStatus(BaseModel):
    photographer_id: str
    active_event_id: str | None


class ClaimResult(BaseModel):
    claimed: int


class EventPublic(BaseModel):
    name: str
    photo_count: int
    poll_interval_ms: int


class PhotoOut(BaseModel):
    id: str
    url: str
    thumb_url: str | None
    created_at: datetime


class PhotoPage(BaseModel):
    photos: list[PhotoOut]
    cursor: str | None  # pass back as ?since= to fetch only newer photos


class FaceIn(BaseModel):
    embedding: list[float]
    bbox: list[float] | None = None
    det_score: float | None = None


class IngestIn(BaseModel):
    # The FTP ingest pipeline only knows who uploaded (from the path); the API resolves
    # which event is live for that account.
    photographer_id: str
    s3_raw_key: str
    s3_thumb_key: str | None = None
    shot_at: datetime | None = None
    faces: list[FaceIn] = []


class PhotoMove(BaseModel):
    event_id: str | None  # null moves the photo back to the unassigned tray


class MatchRequestMeta(BaseModel):
    email: str


class MatchResult(BaseModel):
    photos: list[PhotoOut]
    match_count: int
    faces_detected: int
    # Store this in the browser: GET /g/{token}/matches?guest= re-opens the
    # matched gallery (with any newer photos) without a new selfie.
    guest_token: str
