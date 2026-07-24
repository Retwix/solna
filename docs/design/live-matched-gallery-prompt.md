# Prompt: implement the live matched gallery

> Hand this file (or paste it) to a fresh agent working in the Solna repo.

---

You are working on **Solna**, a SaaS that delivers event photos to guests in
near real-time via facial recognition. Before writing anything, get oriented:

1. `git pull` and work from the latest `main` — earlier checkouts predate the
   features you'll build on.
2. Read `README.md`, `README.v1.md`, `docs/design/photographer-accounts.md`,
   and `TESTING.md`.
3. Run the test suite to confirm a green baseline (**42 passed** expected):
   `pip install -r api/requirements.txt -r watcher/requirements.txt pytest httpx && pytest -q`

## The feature

**Photos of a guest should appear in their matched gallery automatically,
seconds after the photographer shoots them — no button press.**

What exists today (don't rebuild it):
- Guest takes a selfie once → `POST /g/{token}/match` stores the guest (email +
  embedding, in `guests`) and returns matched photos + a `guest_token`.
- `GET /g/{token}/matches?guest=<guest_token>` re-runs the stored embedding
  against the event's faces (see `api/routers/match.py` — `_match_event_photos`,
  `matching.match_faces`).
- The web gallery (`web/src/Gallery.jsx`) persists `guest_token` in
  localStorage, restores on load, and has a manual **"Check for new photos"**
  button that calls `/matches`.
- A reference SSE implementation already exists for the (pre-face-recognition)
  all-photos stream: `gallery_stream` in `api/routers/gallery.py` — a simple
  poll-the-DB-and-emit loop using `gallery_poll_interval_ms`. Model yours on it.

## Suggested design (refine if you see better, say why)

**Backend** — `GET /g/{token}/matches/stream?guest=<guest_token>` (SSE, not
WebSocket — match the existing pattern):
- Validate event token + guest token up front with the same 404 semantics as
  `/matches` (unknown guest, guest from another event, disabled event).
- Loop: find photos for the event created after the last cursor, run the
  guest's stored embedding against **their** faces only, emit each matched
  photo as a `data:` event (same JSON shape as `PhotoOut`). Faces are inserted
  in the same transaction as their photo at ingest, so a photo-level
  `created_at` cursor is sound.
- Close the stream when the event stops being active.

**Frontend** — in `Gallery.jsx`, once a match result is shown (fresh match or
restored from localStorage), open an `EventSource` to the stream and append
arriving photos (dedupe by photo `id`, keep count in sync). On browser
auto-reconnect, re-fetch `/matches` once for a full resync, then resume the
stream. Clean up the EventSource on unmount and on "Search again". Keep the
manual button as a fallback.

## Working rules

- **TDD, strictly red → green.** Write failing behaviour tests first, show
  they fail, then implement. Follow the existing test style: real app against
  SQLite via `tests/conftest.py` fixtures (`make_event`, `ingest_photo`,
  monkeypatched `face_client`), behaviour-named tests. For the stream, testing
  the async generator/poll-cycle function directly is acceptable if SSE via
  TestClient is awkward — but the behaviour "photo ingested after the selfie
  is emitted to that guest, other people's photos are not" must be covered.
- Follow the repo's commit style: `feat(scope): imperative summary` + a body
  explaining the why, noting red-first testing.
- Update docs in the same commit: `TESTING.md` (test count) and `README.v1.md`
  ("live 'new photos of you'" is no longer a known limit).
- Finish with: full `pytest -q` green, `npx vite build` in `web/` clean.
- Manual verification recipe (document it if you change it): with
  `FACE_ENGINE=fake`, two identical copies of an image match each other —
  ingest one as an event photo, use the other as the selfie
  (see TESTING.md layers 3–4).

## Out of scope

Deployment, auth, email, consent, clustering, styling. Don't touch CORS or
docker-compose. Don't rework the all-photos SSE stream.
