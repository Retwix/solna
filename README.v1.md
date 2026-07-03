# Solna — V1: Face recognition

Builds on V0. Now, instead of showing *every* photo, a guest takes a selfie and
sees only the photos they appear in.

See [`README.v0.md`](./README.v0.md) for the base pipeline and
[`README.technical.md`](./README.technical.md) for the longer-term target.

---

## What V1 adds

- **Face detection + embedding on ingest.** When a photo arrives, the watcher
  sends it to a **face service** which returns the faces and their 512-d
  embeddings. These are stored against the photo (`faces` table).
- **Guest selfie match.** `POST /g/{token}/match` (selfie + email) embeds the
  selfie, compares it to the event's stored face embeddings, and returns the
  matching photos. The guest is recorded (`guests` table — email + embedding,
  not the raw selfie).
- **Guest UI.** The gallery now opens on a selfie/email screen, then shows the
  personal gallery of matched photos.

## How matching works (and why this way)

V1 stores embeddings as JSON and matches **in Python** (cosine similarity, numpy)
at request time. At event scale (hundreds–thousands of faces) this is fast,
works on any database, and is easy to test. Moving to **pgvector** for
nearest-neighbour search is a later, isolated optimization — the matching logic
lives behind `api/matching.py`, so swapping the storage/search doesn't touch the
flow.

Similarity is cosine in `[-1, 1]`; a photo matches when its best face meets
`MATCH_SIMILARITY_THRESHOLD` (default `0.35`).

> **The threshold is the single most important knob.** It trades false positives
> (someone else's photos) against misses (your photos not found). It MUST be
> tuned on real event photos — lighting, angles, blur all matter. Start at 0.35
> and adjust while watching real results.

## Architecture (delta from V0)

```
photo arrives (FTP) → watcher → face service /embed → faces[]
                          └→ /internal/ingest { photo keys, faces[] } → photos + faces

guest → /g/{token} → selfie + email
        → POST /g/{token}/match → face service /embed (selfie)
        → cosine match vs event faces → matched photos  (+ store guest)
```

The face service is one small container so the heavy InsightFace dependency and
its model download live in exactly one place; both the watcher and the API call it.

## Running it

```bash
docker compose up --build      # adds the `faceservice` container
```

**First run with real recognition downloads the InsightFace model (~300 MB)** —
it's cached in the `facemodels` volume afterward. To run the whole pipeline
without that download (plumbing/dev only), set in `.env`:

```
FACE_ENGINE=fake               # deterministic stub embeddings — NOT real recognition
```

Because V1 adds tables/columns and we don't use migrations yet, reset the DB:

```bash
docker compose down -v && docker compose up --build
```

## Testing the flow

1. Create an event, upload a few photos (camera or `lftp`) that include a person.
2. Open the gallery QR/link, take a selfie of that person, enter an email.
3. You should get back only the photos that person appears in.

Behaviour tests cover the math and the endpoints with a stub engine
(`tests/test_matching.py`, `tests/test_faces.py`) — no model needed in CI.

## Known limits / next

- **Threshold not yet tuned** on real data — do this first.
- ~~Matched gallery is a point-in-time result~~ Done: `/match` returns a
  `guest_token`; `GET /g/{token}/matches?guest=` re-runs the stored embedding,
  so refresh/revisit keeps the gallery and picks up newer photos — and
  `GET /g/{token}/matches/stream` (SSE) pushes new photos of the guest live,
  so the open gallery updates seconds after the photographer shoots.
- No pre-sorting/clustering or styling/LUT yet (in the V1 target doc).
- Privacy: biometric data + email now in play — consent capture and retention
  belong in the "harden" pass before any real event.
