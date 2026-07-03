"""Thin client for the face service (used by the API at selfie-match time).

Kept as a single function so it is trivial to monkeypatch in tests.
"""
import requests

from config import get_settings

settings = get_settings()


def embed_image(data: bytes, filename: str = "selfie.jpg") -> list[dict]:
    """POST an image to the face service; return its detected faces.

    Each face: {"bbox": [...], "det_score": float, "embedding": [float x512]}.
    """
    resp = requests.post(
        f"{settings.face_service_url.rstrip('/')}/embed",
        files={"file": (filename, data, "application/octet-stream")},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("faces", [])
