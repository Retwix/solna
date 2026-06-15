# FTP intake (V0)

One **virtual FTP login per event**, authenticated against the `events` table.
The photographer enters these credentials in their camera's FTP settings;
uploads land in that event's intake directory, which the watcher observes.

The server lives in [`../ftpserver/`](../ftpserver/) (pyftpdlib). The legacy
`vsftpd.conf` in this folder is no longer used.

## How auth works

1. `POST /events` generates an FTP username + password, stores only a pbkdf2
   **hash** of the password (`events.ftp_password_hash`), and returns the
   plaintext password once in the response.
2. On FTP login, the server looks up the username, verifies the password
   against the stored hash, and (if the event is `active`) chroots the session
   into `{FTP_ROOT}/raw/{event_id}`.
3. The camera uploads JPEGs there → the watcher thumbnails + ingests them →
   they appear in the gallery.

Isolation: each login is chrooted to its own event directory, so one
photographer can only write to their own event.

## Connecting a camera

A camera is a separate device, so it cannot use `localhost`:

- **Host**: your computer's LAN IP (e.g. `192.168.1.42`)
- **Port**: `2121`
- **Username / password**: from the event-creation response
- **Mode**: passive (most cameras default to this)

Set these in `.env` before `docker compose up`:

```
FTP_HOST=192.168.1.42          # your LAN IP (cosmetic: shown in returned creds)
FTP_PASV_ADDRESS=192.168.1.42  # REQUIRED for cameras — advertised passive address
```

Without `FTP_PASV_ADDRESS` set to the LAN IP, the control connection succeeds
but data transfers hang — the classic "camera connects but won't upload" symptom.

## Same-machine testing (no camera)

Leave `FTP_PASV_ADDRESS` empty and use any FTP client on this machine:

```
lftp -u <username>,<password> -p 2121 localhost
# then: put some-photo.jpg
```

## Production (AWS)

The cloud equivalent is **AWS Transfer Family**: one Transfer user per event,
scoped (via IAM/home-directory mappings) to the `raw/{event_id}/` prefix in S3.
The watcher is then replaced by an S3 event → SQS → worker trigger; the rest of
the pipeline is unchanged.
