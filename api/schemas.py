from datetime import datetime

from pydantic import BaseModel


class EventCreate(BaseModel):
    name: str


class FtpCredentials(BaseModel):
    host: str
    port: int
    username: str
    password: str
    directory: str


class EventCreated(BaseModel):
    id: str
    name: str
    slug: str
    gallery_url: str
    qr_png_base64: str
    ftp: FtpCredentials


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
    event_id: str
    s3_raw_key: str
    s3_thumb_key: str | None = None
    shot_at: datetime | None = None
    faces: list[FaceIn] = []


class MatchRequestMeta(BaseModel):
    email: str


class MatchResult(BaseModel):
    photos: list[PhotoOut]
    match_count: int
    faces_detected: int
