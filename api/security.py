import hashlib
import hmac
import os

from fastapi import Header, HTTPException, status

from config import get_settings

settings = get_settings()


def require_ingest_key(x_ingest_key: str = Header(default="")) -> None:
    """Shared-secret auth for the internal ingest endpoint (FTP ingest -> API)."""
    if x_ingest_key != settings.ingest_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid ingest key")


# --- FTP password hashing (pbkdf2, stdlib only) -----------------------------
# Format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
# Kept dependency-free and self-describing so the FTP server can verify it too.
_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False
