"""Per-event FTP intake directory.

Each event's uploads land in {FTP_ROOT}/raw/{event_id}. The FTP server
authenticates against the events table (see ftpserver/) and chroots each login
into this directory, so a photographer can only write to their own event.

On AWS the equivalent is an AWS Transfer Family user scoped (via IAM/home
mappings) to the raw/{event_id}/ prefix in S3.
"""
from pathlib import Path

from config import get_settings

settings = get_settings()


def ensure_event_intake_dir(event_id: str) -> Path:
    intake_dir = Path(settings.ftp_root) / "raw" / event_id
    intake_dir.mkdir(parents=True, exist_ok=True)
    return intake_dir
