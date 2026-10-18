"""Solna FTP server.

A small pyftpdlib server that authenticates each login against the Solna
`photographers` table: the STABLE FTP username/password returned once at
account creation (entered into the camera once, never changed per event). On a
successful login the user is chrooted into their account's intake directory
(raw/{photographer_id}), so uploads land in the photographer's own intake directory
and one photographer can only ever write to their own space. Which event a
photo belongs to is resolved later by the API (the account's active event).

Cameras connect with: host = your machine's LAN IP, port 2121, and the
credentials from the photographer-creation response. FTP_PASV_ADDRESS must be
that same LAN IP so passive-mode data transfers work from a separate device.
"""
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
import requests
from pyftpdlib.authorizers import AuthenticationFailed
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

import ingest
from passwords import verify_password

log = logging.getLogger("ftpserver")

# psycopg wants a plain libpq URL (strip the SQLAlchemy +psycopg dialect tag).
DATABASE_URL = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
FTP_ROOT = os.getenv("FTP_ROOT", "/data/ftp")
PASV_ADDRESS = os.getenv("FTP_PASV_ADDRESS", "")
PASV_MIN = int(os.getenv("FTP_PASV_MIN_PORT", "21100"))
PASV_MAX = int(os.getenv("FTP_PASV_MAX_PORT", "21110"))
FULL_PERMS = "elradfmwMT"


class PhotographerAuthorizer:
    """pyftpdlib authorizer backed by the photographers table."""

    def __init__(self):
        self._homes: dict[str, str] = {}

    def _lookup(self, username: str):
        with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, ftp_password_hash FROM photographers WHERE ftp_username = %s",
                (username,),
            )
            return cur.fetchone()

    def validate_authentication(self, username, password, handler):
        row = self._lookup(username)
        if not row:
            raise AuthenticationFailed("authentication failed")
        photographer_id, pw_hash = row
        if not pw_hash or not verify_password(password, pw_hash):
            raise AuthenticationFailed("authentication failed")

        home = Path(FTP_ROOT) / "raw" / photographer_id
        home.mkdir(parents=True, exist_ok=True)
        self._homes[username] = str(home)

    def get_home_dir(self, username):
        return self._homes[username]

    # The remaining methods complete pyftpdlib's authorizer contract.
    def has_user(self, username):
        return True

    def has_perm(self, username, perm, path=None):
        return perm in FULL_PERMS

    def get_perms(self, username):
        return FULL_PERMS

    def get_msg_login(self, username):
        return "Solna FTP ready — upload your photos."

    def get_msg_quit(self, username):
        return "Goodbye."

    def impersonate_user(self, username, password):
        pass

    def terminate_impersonation(self, username):
        pass


def _retry_can_succeed(error):
    if isinstance(error, FileNotFoundError):
        return False
    if isinstance(error, requests.HTTPError):
        return error.response.status_code >= 500
    return True


def make_handler(authorizer, on_photo, retry_after=60):
    """FTP handler that hands each completely received file to `on_photo`.

    pyftpdlib fires on_file_received only once the transfer has finished, so
    a camera pausing mid-upload never yields a half-written photo. Processing
    runs on one background worker so slow ingestion never blocks FTP clients.
    A photo whose processing raises is queued again after `retry_after` seconds,
    unless its file is gone or the API rejected it.
    """
    worker = ThreadPoolExecutor(max_workers=1)

    def ingest_photo(path):
        try:
            on_photo(path)
        except Exception as error:  # noqa: BLE001
            if not _retry_can_succeed(error):
                log.exception("could not ingest %s; giving up", path)
                return
            log.exception("could not ingest %s; retrying in %s s", path, retry_after)
            threading.Timer(retry_after, submit_photo, (path,)).start()

    def submit_photo(path):
        worker.submit(ingest_photo, path)

    class IngestingHandler(FTPHandler):
        def on_file_received(self, file):
            submit_photo(Path(file))

    IngestingHandler.authorizer = authorizer
    IngestingHandler.submit_photo = staticmethod(submit_photo)
    return IngestingHandler


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler = make_handler(PhotographerAuthorizer(), ingest.handle_upload)
    for path in ingest.pending_photos():
        handler.submit_photo(path)  # queued: FTP accepts uploads meanwhile
    handler.passive_ports = range(PASV_MIN, PASV_MAX + 1)
    if PASV_ADDRESS:
        # Address advertised to clients for passive connections (your LAN IP).
        handler.masquerade_address = PASV_ADDRESS

    server = FTPServer(("0.0.0.0", 21), handler)
    log.info(
        "listening on :21  passive=%s-%s  masquerade=%s", PASV_MIN, PASV_MAX, PASV_ADDRESS or "(none)"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
