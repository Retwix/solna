"""Per-event FTP provisioning (one virtual user per event).

V0 keeps this deliberately simple and pluggable:
  * It creates the event's intake directory: {FTP_ROOT}/raw/{event_id}
  * It generates a password and registers a virtual user with the FTP server.

The directory creation is what the local watcher relies on. Wiring the virtual
user into the running FTP server is environment-specific; see ftp/README.md.
On AWS the equivalent is creating an AWS Transfer Family user scoped to the
raw/{event_id}/ prefix in S3.
"""
import os
import secrets
import subprocess
from pathlib import Path

from config import get_settings

settings = get_settings()

# Optional: path to a script that adds a virtual user to the FTP server.
# If unset, provisioning only creates the intake directory (still enough for
# the watcher + an FTP client that writes into the shared volume).
FTP_PROVISION_SCRIPT = os.getenv("FTP_PROVISION_SCRIPT", "")


def provision_event_ftp(event_id: str, username: str) -> str:
    password = secrets.token_urlsafe(12)

    intake_dir = Path(settings.ftp_root) / "raw" / event_id
    intake_dir.mkdir(parents=True, exist_ok=True)

    if FTP_PROVISION_SCRIPT and Path(FTP_PROVISION_SCRIPT).exists():
        # Script receives: username password absolute_home_dir
        subprocess.run(
            [FTP_PROVISION_SCRIPT, username, password, str(intake_dir)],
            check=True,
        )

    return password
