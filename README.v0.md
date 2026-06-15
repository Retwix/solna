# Solna — V0 Technical README (MVP)

The smallest version that proves the core promise: a photographer shoots, photos flow in over FTP, and guests see them almost instantly by scanning a QR code.

V0 has **no facial recognition**. The gallery shows *all* of an event's photos. The build is structured so V1 (faces, selfie matching, styling) drops in without rework — see [`README.technical.md`](./README.technical.md) for the V1 target.

---

## 1. V0 scope

**In:**

- Create an event (gets a per-event FTP user + storage repo + tokenized gallery URL + QR code).
- Photographer's camera auto-uploads photos over FTP into the event repo.
- Server receives each photo, generates a thumbnail, records it.
- Guests scan the QR → public **live** gallery PWA showing every photo from the event.

**Deferred to V1 (kept in mind, not built):** facial analysis, face embeddings, pre-sorting/clustering, selfie capture, guest email, per-guest filtering, custom LUT/filters.

---

## 2. Stack (V0)

| Layer | V0 choice | Notes / V1 path |
|-------|-----------|-----------------|
| **API** | Python 3.12 + FastAPI | Unchanged in V1. |
| **DB** | PostgreSQL | Same `events` / `photos` tables in V1; pgvector + `faces`/`guests`/`matches` added later. |
| **Storage** | S3 (MinIO locally) | Same `raw/{event_id}/` layout as V1. |
| **FTP intake** | vsftpd, one virtual user per event | Lands files in `raw/{event_id}/`; V1 keeps this path. |
| **Processing** | Background task: generate thumbnail + persist | This is the **hook** where V1 inserts detect → embed → style. No-op-ish in V0. |
| **Live updates** | Polling endpoint (V0) or SSE | Gallery refreshes as photos arrive. |
| **Guest web** | React (Vite) PWA, mobile-first | Becomes selfie + per-guest gallery in V1. |
| **Deploy** | Docker Compose (single host OK for V0) | Splits into ECS/queue in V1. |

V0 can run on a **single server** to stay simple; the storage layout and table schema are already the cloud/V1 shape, so migration is lift-not-rewrite.

---

## 3. Architecture (V0)

```
        Photographer's camera
               │  FTP (one user per event)
               ▼
   ┌────────────────────────┐
   │  FTP server (vsftpd)    │ ──► writes to  storage: raw/{event_id}/photo.jpg
   └────────────────────────┘
               │  filesystem/S3 event → watcher enqueues
               ▼
   ┌────────────────────────┐
   │  Processing (V0)        │
   │  • make thumbnail       │   ← V1 inserts detect→embed→cluster→style HERE
   │  • write thumb to store │
   │  • insert photo row     │
   └────────────────────────┘
               │
               ▼
        Postgres: photos(event_id, keys, status, shot_at)
               │
               ▼
   ┌────────────────────────┐
   │  FastAPI                │
   └────────────────────────┘
               ▲
   QR scan → /g/{gallery_token}      │  GET /events/{token}/photos?since=...
        Guest (React PWA) ───────────┘  live gallery of ALL event photos
```

### Photo intake flow

1. Camera pushes a JPEG over FTP into that event's home dir → stored at `raw/{event_id}/`.
2. A **watcher** (inotify on the FTP dir, or S3 event) detects the new file and enqueues a process job.
3. The processing step generates a thumbnail, writes it to `thumbs/{event_id}/`, and inserts a `photos` row with `status='ready'`.
4. The gallery's live endpoint surfaces the new photo on the next poll/SSE tick.

> The watcher + process step exists in V0 even though it only thumbnails. Keeping the queue/hook in place means V1 adds face work without changing intake or the API.

---

## 4. Data model (V0)

```
events   (id, name, slug, gallery_token, ftp_username, status, created_at)
photos   (id, event_id, s3_raw_key, s3_thumb_key, shot_at, status, created_at)
```

These two tables carry over to V1 unchanged. V1 adds `faces`, `guests`, `matches` and a pgvector column — nothing here is rewritten.

---

## 5. Privacy (V0)

Even with no faces, V0 hosts guests' photos behind a public link, so:

- **Gallery URL is tokenized and unguessable** — `/g/{gallery_token}` (random, high-entropy), never `/{slug}`. The token is what the QR encodes.
- The QR code points to the tokenized URL only.
- Per-event ability to **disable/expire** a gallery and delete its photos.
- A short privacy notice on the gallery page (whose event, who to contact, how to request removal).

Biometric/consent obligations arrive with V1's faces; V0 keeps the surface minimal but already private-by-URL.

---

## 6. API surface (V0)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/events` | Create event → returns `gallery_token`, QR image, FTP credentials. |
| `GET` | `/g/{gallery_token}` | Gallery page metadata (event name, photo count). |
| `GET` | `/g/{gallery_token}/photos?since={cursor}` | Photos for live gallery; `since` enables incremental polling. |
| `GET` | `/g/{gallery_token}/stream` | (Optional) SSE push of new photos. |
| `POST` | `/internal/ingest` | Watcher → API: register a newly arrived photo (auth-protected). |
| `GET` | `/healthz` | Liveness. |

QR code: generated at event creation, encodes the full `/g/{gallery_token}` URL.

---

## 7. FTP model (V0)

- **One virtual FTP user per event** (vsftpd virtual users, chrooted to that event's directory).
- Credentials generated and returned at event creation; the photographer enters them in the camera's FTP settings.
- The user's home maps to `raw/{event_id}/` so uploads land exactly where the watcher expects.
- Isolation: each photographer/event can only write to its own repo.

---

## 8. Repository layout (V0)

```
solna/
├── api/                 # FastAPI: events, gallery, ingest
│   ├── routers/
│   ├── models/
│   ├── services/        # event creation, qr, gallery
│   └── main.py
├── watcher/             # inotify/S3 watcher → enqueue → thumbnail + persist
│   └── process.py       # ← V1 face pipeline slots in here
├── web/                 # React (Vite) live gallery PWA
├── ftp/                 # vsftpd config + per-event user provisioning
├── migrations/          # Alembic
├── docker-compose.yml   # api, watcher, postgres, minio, vsftpd
└── README.v0.md
```

---

## 9. Local development

Prerequisites: Docker + Compose, Python 3.12, Node 20.

```bash
# Boot infra: Postgres, MinIO (S3), vsftpd
docker compose up -d postgres minio ftp

# API
cd api && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload

# Watcher (thumbnails + persistence)
cd ../watcher && pip install -r requirements.txt
python -m watcher.process

# Gallery PWA
cd ../web && npm install && npm run dev
```

`.env` (see `.env.example`):

```
DATABASE_URL=postgresql://solna:solna@localhost:5432/solna
S3_ENDPOINT=http://localhost:9000
S3_BUCKET=solna-media
FTP_HOST=localhost
GALLERY_TOKEN_BYTES=16
GALLERY_POLL_INTERVAL_MS=3000
```

---

## 10. Definition of done (V0)

1. Create an event via the API → receive FTP credentials, a QR code, and a gallery URL.
2. Point a camera (or FTP client) at those credentials and upload photos.
3. Photos appear in storage under `raw/{event_id}/`, with thumbnails generated.
4. Scanning the QR opens the PWA and shows all event photos, **updating live** as new ones arrive.
5. The gallery URL is tokenized; the event can be disabled and its photos deleted.

---

*V0 is intentionally minimal but built on V1's storage layout, data model, and processing hook, so V1 is additive rather than a rewrite.*
