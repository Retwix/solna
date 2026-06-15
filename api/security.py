from fastapi import Header, HTTPException, status

from config import get_settings

settings = get_settings()


def require_ingest_key(x_ingest_key: str = Header(default="")) -> None:
    """Shared-secret auth for the internal ingest endpoint (watcher -> API)."""
    if x_ingest_key != settings.ingest_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid ingest key")
