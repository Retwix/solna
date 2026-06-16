# Design: photographer accounts + active-event routing

**Status:** draft for review · **Supersedes:** per-event FTP credentials (current V0)

## Goal

Stop forcing photographers to re-enter FTP credentials per event. A photographer
enters FTP settings into their camera **once**. Per event, they just pick which
event is "live" in the app; the server routes incoming photos to that event.

---

## 1. Schema changes

### New table: `photographers` (the stable FTP account)

```python
class Photographer(Base):
    __tablename__ = "photographers"

    id: Mapped[str]                 # uuid
    name: Mapped[str]
    email: Mapped[str | None]       # optional, for later auth/login
    ftp_username: Mapped[str]       # unique, STABLE — entered into the camera once
    ftp_password_hash: Mapped[str]
    # Which event incoming photos are routed to right now. Null = "not live".
    active_event_id: Mapped[str | None]  # FK -> events.id, nullable
    created_at: Mapped[datetime]
```

### `events` — credentials move OUT, ownership moves IN

```python
class Event(Base):
    __tablename__ = "events"

    id: Mapped[str]
    photographer_id: Mapped[str]    # FK -> photographers.id  (NEW: owner)
    name: Mapped[str]
    slug: Mapped[str]
    gallery_token: Mapped[str]      # unchanged
    status: Mapped[str]             # active | disabled (unchanged)
    created_at: Mapped[datetime]
    # REMOVED: ftp_username, ftp_password_hash  (now on Photographer)
```

### `photos` — can now be "unassigned"

```python
class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[str]
    photographer_id: Mapped[str]    # FK -> photographers.id  (NEW: who uploaded)
    event_id: Mapped[str | None]    # NOW NULLABLE: null = unassigned tray
    s3_raw_key: Mapped[str]
    s3_thumb_key: Mapped[str | None]
    # ready | unassigned   (V1 adds: processing | failed)
    status: Mapped[str]
    shot_at: Mapped[datetime | None]
    created_at: Mapped[datetime]
```

Key idea: **the event association lives only in the DB**, not in the storage path
or FTP folder. That makes "assign" and "reassign" a single column update — no
moving of files.

---

## 2. FTP auth change

- The FTP server authenticates against **`photographers`** (not `events`).
- Each login is chrooted to `raw/{photographer_id}/` (was `raw/{event_id}/`).
- Credentials are stable, so the camera config never changes.

The only change in `ftpserver/server.py` is the lookup query and the home path:

```sql
SELECT id, ftp_password_hash FROM photographers WHERE ftp_username = %s
```
home = `raw/{photographer_id}/`

---

## 3. Ingest resolution (the heart of option 1)

The watcher no longer knows the event. It parses the **photographer id** from the
path and posts that; the **API resolves the active event** (keeps the rule in one
place, in a single DB read):

```
watcher: file at raw/{photographer_id}/<name>
   -> upload original + thumbnail to storage
   -> POST /internal/ingest { photographer_id, s3_raw_key, s3_thumb_key }

API /internal/ingest:
   photographer = get(photographer_id)
   event_id = photographer.active_event_id          # may be None
   status   = "ready" if event_id else "unassigned"
   insert Photo(photographer_id, event_id, keys, status)
```

- **Live:** `active_event_id` set → photo is `ready` and shows in that gallery.
- **Not live:** `active_event_id` is null → photo is `unassigned`, held in a tray,
  never lost, never shown in any gallery.

Gallery query is unchanged in spirit: `photos WHERE event_id = :event AND status = 'ready'`.

---

## 4. Storage key layout

```
raw/{photographer_id}/<name>      # where FTP lands (stable per account)
thumbs/{photographer_id}/<name>   # generated thumbnail
```

Event membership is the `event_id` column, so reassigning a photo to another event
is just `UPDATE photos SET event_id = ...` — no object copy/move.

---

## 5. API changes

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/photographers` | Create an account → returns **stable FTP credentials** (the once-only setup). |
| `POST` | `/events` | Now requires/*infers* `photographer_id`; returns QR + gallery URL (no FTP creds). |
| `POST` | `/events/{id}/go-live` | Sets `photographer.active_event_id = {id}`. The "one button". |
| `POST` | `/events/{id}/stop` | Clears `active_event_id` if it points here. |
| `GET`  | `/photographers/{id}/unassigned` | List photos with no event (the tray). |
| `POST` | `/events/{id}/claim-unassigned` | Bulk-assign that photographer's unassigned photos to this event. |
| `PATCH`| `/photos/{id}` | Move a single photo to a different event (manual fixup). |

(`/internal/ingest` body changes from `event_id` to `photographer_id`.)

---

## 6. Admin UI changes

- New first-run step: "Create photographer account" → shows the stable FTP creds
  (the screen that currently appears per event).
- Event page gains a **Go live / Stop** toggle, and a badge showing which event is
  currently live for the account.
- An **Unassigned** tray view with a "move to event" action.

---

## 7. Rules & edge cases

- **Forgot to go live:** photos land as `unassigned`; bulk-claim them afterward.
- **One account = one live event at a time.** Truly simultaneous shooting from one
  camera needs a second photographer account (or fall back to per-event folders).
- **Switch mid-shoot:** instantaneous, but in-flight queued photos from the camera
  may land a few seconds late and attach to the new event → fix via the tray.
- **Only one event live per account:** `go-live` first clears any other event this
  account had live (enforced in the same transaction).

---

## 8. Migration plan

This is a breaking schema change.

- **Dev (now):** `docker compose down -v && up --build` to recreate. Acceptable —
  no real data yet.
- **If we had real data:** create one `photographer` per distinct existing
  `events.ftp_username`, backfill `events.photographer_id` and
  `photos.photographer_id`, then drop the FTP columns from `events`. This is the
  point where we should adopt **Alembic** (currently using create-on-startup),
  because we now have a non-trivial migration.

---

## 9. Test impact

- `test_event_creation` / `test_ftp_auth`: FTP credentials assertions move from the
  event-creation response to a new **photographer-creation** test.
- New behaviour tests:
  - ingest while live → photo lands `ready` in the active event;
  - ingest while not live → photo lands `unassigned`, not in any gallery;
  - `go-live` switches the active event (and unsets the previous one);
  - `claim-unassigned` moves tray photos into an event.

---

## 10. Open questions

1. Do we want **auth on the admin** (who can create events / go live) now, or keep
   it open for V0 and add it in the "harden" pass?
2. Should `go-live` auto-claim any recent unassigned photos (e.g. last 5 min) to
   smooth the "forgot to press go-live" case?
3. Adopt **Alembic** as part of this change, given the migration above?
4. Sequencing: do this **before** or **after** the V1 face spike? Both touch the
   ingest path, so doing them back-to-back avoids reworking ingest twice.
