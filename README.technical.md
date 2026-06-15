# Solna — Technical README (V1)

Technical reference for Solna's first production version. For the product overview, see [`README.md`](./README.md).

V1 goal: ingest photos from a photographer's camera over FTP, process each one automatically (face detection → embedding → pre-sort → styling), and let a guest find every photo they appear in by taking a selfie.

---

## 1. Stack at a glance

| Layer | Choice | Why |
|-------|--------|-----|
| **API / backend** | Python 3.12 + **FastAPI** | Best ecosystem for facial recognition and image processing; async-friendly for upload/match endpoints. |
| **Processing worker** | Python + Celery (or RQ) | Heavy per-photo work runs off the request path. |
| **Face engine** | **InsightFace** (`buffalo_l`) — self-hosted | Detection + 512-d embeddings, no per-image API cost. Better economics than a cloud API at event volumes (thousands of photos/event). |
| **Vector matching** | **PostgreSQL + pgvector** | Store face embeddings, do nearest-neighbour search for selfie matching. One DB for relational + vectors in V1. |
| **Image styling** | Pillow + LUT (`.cube`) / `rawpy` for RAW | Apply a Lightroom-style preset deterministically per photo. |
| **Object storage** | **AWS S3** | Originals, processed/styled renders, thumbnails. |
| **Relational DB** | **AWS RDS (PostgreSQL)** | Events, photos, faces, guests, matches. pgvector extension enabled. |
| **FTP intake** | AWS Transfer Family **or** vsftpd on EC2 → S3 | Camera pushes here; lands in per-event prefix. |
| **Queue** | AWS SQS (or S3 → Lambda trigger) | Decouples intake from processing. |
| **Frontend (guest)** | React (Vite) PWA | Mobile-first: QR landing, selfie capture, gallery. |
| **Deploy** | Docker; API + worker on ECS/Fargate (or EC2) | Reproducible, scales the worker independently. |

> **Face engine note:** InsightFace self-hosted is the V1 recommendation for cost control and data ownership. **AWS Rekognition** (`IndexFaces` / `SearchFacesByImage`) is a drop-in alternative if you want to skip ML ops at the cost of per-call pricing — the pipeline below is engine-agnostic behind the `FaceEngine` interface.

---

## 2. Architecture

```
                 Photographer's camera
                        │  FTP (auto-upload on capture)
                        ▼
        ┌──────────────────────────────┐
        │  FTP intake (Transfer Family) │ ──► writes to  S3: raw/{event_id}/...
        └──────────────────────────────┘
                        │  S3 event / SQS message
                        ▼
        ┌──────────────────────────────┐
        │     Processing worker         │
        │  1. detect faces (InsightFace)│
        │  2. embed each face (512-d)   │
        │  3. pre-sort / cluster        │
        │  4. apply LUT preset          │
        └──────────────────────────────┘
             │                     │
             ▼                     ▼
    S3: processed/, thumbs/   Postgres: photos, faces(+embedding), clusters
                        │
                        ▼
        ┌──────────────────────────────┐
        │        FastAPI API            │
        └──────────────────────────────┘
                        ▲
   QR scan → selfie + email            │  POST /match (selfie embedding → pgvector kNN)
        Guest (React PWA)  ────────────┘  ──► personal gallery
```

### Processing pipeline (per photo)

1. **Trigger** — new object in `raw/{event_id}/` emits an SQS message.
2. **Detect** — InsightFace finds face bounding boxes.
3. **Embed** — each face → 512-d L2-normalized vector.
4. **Pre-sort** — assign each face to a cluster (incremental cosine-similarity clustering per event) so photos are grouped by person before any guest shows up.
5. **Style** — apply the event's LUT/preset; write styled render + thumbnail to S3.
6. **Persist** — insert `photo`, `face` rows (with embedding + cluster id) into Postgres.

### Guest match flow

1. Scan QR → `/{event_id}` landing page.
2. Capture selfie in-browser, submit with email.
3. API embeds the selfie, runs pgvector kNN against `face.embedding` for that event, filters by a cosine-distance threshold.
4. Return distinct photos for the matched faces → guest gallery. Email stored for delivery/consent record.

---

## 3. Data model (V1)

```
events        (id, name, slug, created_at, lut_preset, status)
photos        (id, event_id, s3_raw_key, s3_processed_key, s3_thumb_key,
               shot_at, processed_at, status)
faces         (id, photo_id, event_id, bbox, embedding vector(512),
               cluster_id, quality_score)
clusters      (id, event_id, centroid vector(512), face_count)   -- pre-sort groups
guests        (id, event_id, email, selfie_embedding vector(512), created_at)
matches       (id, guest_id, photo_id, distance, created_at)
```

Index: `CREATE INDEX ON faces USING hnsw (embedding vector_cosine_ops);`

---

## 4. API surface (V1)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/events` | Create an event (returns slug + QR target). |
| `GET` | `/events/{slug}` | Public landing metadata for the guest page. |
| `POST` | `/events/{slug}/match` | Body: selfie image + email. Embeds, matches, returns gallery. |
| `GET` | `/events/{slug}/gallery?token=` | Paginated photos for a matched guest. |
| `POST` | `/internal/process` | Worker callback / manual reprocess (auth-protected). |
| `GET` | `/healthz` | Liveness. |

Auth: photographer/admin endpoints behind API keys or JWT; guest endpoints use a short-lived signed token issued after a successful match.

---

## 5. Repository layout (proposed)

```
solna/
├── api/                 # FastAPI app
│   ├── routers/
│   ├── models/          # SQLAlchemy + pydantic schemas
│   ├── services/        # match, gallery, events
│   └── main.py
├── worker/              # processing pipeline
│   ├── pipeline.py      # detect → embed → cluster → style → persist
│   ├── face_engine/     # InsightFace impl behind FaceEngine interface
│   └── styling/         # LUT / preset application
├── web/                 # React (Vite) guest PWA
├── infra/               # IaC (Terraform): S3, RDS, SQS, ECS, Transfer Family
├── migrations/          # Alembic
├── docker-compose.yml   # local dev: api, worker, postgres+pgvector, minio
└── README.technical.md
```

---

## 6. Local development

Prerequisites: Docker, Docker Compose, Python 3.12, Node 20.

```bash
# 1. Boot local infra (Postgres+pgvector, MinIO as S3 stand-in)
docker compose up -d postgres minio

# 2. API
cd api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload

# 3. Worker
cd ../worker
pip install -r requirements.txt   # pulls insightface, onnxruntime, pillow
python -m worker.consumer

# 4. Guest web app
cd ../web
npm install
npm run dev
```

`.env` (see `.env.example`):

```
DATABASE_URL=postgresql://solna:solna@localhost:5432/solna
S3_ENDPOINT=http://localhost:9000        # MinIO locally; empty in prod
S3_BUCKET=solna-media
SQS_QUEUE_URL=...                          # or LOCAL_QUEUE=1 for in-process
FACE_ENGINE=insightface                    # insightface | rekognition
MATCH_DISTANCE_THRESHOLD=0.35              # cosine distance; tune on real data
```

---

## 7. Key decisions & open questions for V1

- **Matching threshold** is the single biggest quality lever — must be tuned against real event photos (lighting, angles, motion blur) to balance false positives vs. missed photos.
- **GPU vs CPU** for InsightFace: CPU (`onnxruntime`) is fine to start; move the worker to GPU if per-event throughput lags behind shooting speed.
- **RAW handling**: cameras may FTP JPEG, RAW, or both. V1 should standardize on processing JPEG for speed; RAW styling via `rawpy` can follow.
- **Pre-sort vs. on-demand match**: V1 does both — cluster on ingest (organizes the gallery early) and kNN on selfie (per-guest result).

## 8. Privacy & consent (must-have for V1, not optional)

Solna processes **biometric data** (face embeddings) and personal data (email, selfie). Under GDPR this is a special category requiring a lawful basis (typically explicit consent).

- Capture **explicit consent** on the selfie/email screen before processing.
- Store selfie embeddings, not raw selfies, where possible; set retention/auto-deletion per event.
- Provide deletion on request; document data flow and processors (AWS).
- Display a clear privacy notice at the QR landing page.

A dedicated privacy/DPIA doc should accompany V1 — treat this section as the minimum bar.

---

*V1 scope. Subject to change as the matching engine and ingest path are validated on real events.*
