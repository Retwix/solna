"""Per-photographer FTP intake directory.

Uploads land in {FTP_ROOT}/raw/{photographer_id} — stable per account, so the
camera's FTP config never changes. The FTP server authenticates against the
photographers table (see ftpserver/) and chroots each login into this
directory. Event membership is decided in the DB at ingest time (the account's
active event), never by the storage path.

On AWS the equivalent is an AWS Transfer Family user scoped (via IAM/home
mappings) to the raw/{photographer_id}/ prefix in S3.
"""
from pathlib import Path

from config import get_settings

settings = get_settings()


def ensure_photographer_intake_dir(photographer_id: str) -> Path:
    intake_dir = Path(settings.ftp_root) / "raw" / photographer_id
    intake_dir.mkdir(parents=True, exist_ok=True)
    return intake_dir
