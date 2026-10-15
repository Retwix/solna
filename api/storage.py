"""Object storage helpers (S3 / MinIO).

V0 keeps the exact key layout V1 expects:
    raw/{event_id}/<filename>      original upload
    thumbs/{event_id}/<filename>   generated thumbnail
"""
import boto3
from botocore.client import Config

from config import get_settings

settings = get_settings()

_s3 = boto3.client(
    "s3",
    endpoint_url=settings.s3_endpoint or None,
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
    region_name=settings.s3_region,
    config=Config(signature_version="s3v4"),
)


def raw_prefix(event_id: str) -> str:
    return f"raw/{event_id}/"


def thumb_prefix(event_id: str) -> str:
    return f"thumbs/{event_id}/"


def put_bytes(key: str, data: bytes, content_type: str = "image/jpeg") -> str:
    _s3.put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)
    return key


# Signs links for the browser: the signature covers the host, so this client
# targets the PUBLIC endpoint, not the compose-internal one. Signing is local
# computation — no network call.
_public_s3 = boto3.client(
    "s3",
    endpoint_url=settings.s3_public_endpoint or None,
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
    region_name=settings.s3_region,
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)
PHOTO_LINK_TTL_SECONDS = 7 * 24 * 3600  # SigV4 maximum; links are re-signed on every fetch


def public_url(key: str | None) -> str | None:
    if not key:
        return None
    return _public_s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=PHOTO_LINK_TTL_SECONDS,
    )
