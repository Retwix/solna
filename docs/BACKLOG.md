# Solna — Backlog to a workable app

**Updated:** 2026-07-24 · **Definition of "workable":** a photographer can run a real
event with real guests, legally and reliably, without the dev team standing next to the box.

## Where we are

Shipped and behaviour-tested (V0 + V1):

- FTP intake → watcher → thumbnail pipeline → live QR gallery
- Stable photographer accounts, go-live event routing, unassigned-photo tray
- Face detection + embedding on ingest (InsightFace service, fake engine for dev/CI)
- Guest selfie match, returning guests, matched gallery that updates live over SSE

Everything runs on localhost via docker-compose. There is **no deployment, no auth on
the admin surface, no email sending, no DB migrations, and no consent capture**. Those
are the gaps between "demo" and "workable".

Milestones are ordered: each one is releasable and makes the next one testable.
Stories inside a milestone are vertical slices — each names an actor, delivers
observable value, and can ship alone.

---

## Milestone 1 — One real event (the deploy pass)

> Design already drafted in [`docs/design/deploy-pass.md`](./design/deploy-pass.md).
> These three come together because each forces the next: public URL → HTTPS →
> admin auth → email.

### 1.1 Guests reach the app over public HTTPS
**Actor:** guest · **Value:** the QR code works on a phone in the field (mobile
browsers block the selfie camera on plain HTTP).
- Single VPS, Caddy in front, one origin (`/`, `/api`, `/media`) — CORS wildcard removed
- `docker-compose.prod.yml` overlay; only 443 + FTP ports exposed
- **Accept:** scan QR on a phone over 4G → selfie camera opens → match returns photos.

### 1.2 Schema survives deploys (Alembic)
**Actor:** photographer (their data) · **Value:** first real event's photos and guests
are never wiped by `down -v`.
- Initial migration from current models; API startup runs `upgrade head`
- **Accept:** deploy a schema change to a DB with data; nothing lost.
- *Blocker for everything after: 1.3's schema changes should be migration #2.*

### 1.3 Photographer signs in with a magic link
**Actor:** photographer · **Value:** a public URL where only they can manage their
events (today anyone can create events and go live).
- `Photographer.email` required + unique; `login_tokens` table (hashed, 15-min expiry)
- Signed session cookie; signup = name + email → first magic link; FTP creds move
  behind login ("camera setup" page)
- Console mail backend for dev/CI, SMTP (e.g. Brevo) in prod
- **Accept:** anonymous request to events CRUD → 401; cross-account access → 403;
  expired/used token rejected; magic link in captured mail logs you in.

### 1.4 Guest receives their gallery link by email
**Actor:** guest · **Value:** the email field finally does something — guests can
reopen their gallery from any device.
- After a match, send `https://<domain>/g/<token>?guest=<guest_token>`; gallery page
  reads `?guest=` as well as localStorage
- Rate limits: 3 magic links / email / hour; 1 guest mail per match
- **Accept:** match on phone A → open emailed link on phone B → same personal gallery.

### 1.5 Ops floor: backups + deploy script + hardening checklist
**Actor:** operator (us) · **Value:** a crashed box or bad deploy doesn't end the pilot.
- Nightly `pg_dump` + weekly MinIO snapshot off-box; `scripts/deploy.sh`
- Checklist from deploy-pass §5: no public DB/MinIO/faceservice ports, secure
  cookies, strong secrets in `.env.prod`
- **Accept:** restore drill on a fresh VM reproduces a working app with data.

---

## Milestone 2 — Legal & trustworthy (before any non-friendly guest)

### 2.1 Guest consents before biometric processing
**Actor:** guest · **Value:** GDPR lawful basis — embeddings are special-category data.
- Consent checkbox + privacy notice at the selfie screen; consent recorded with the guest
- **Accept:** no `/match` call possible without consent; consent timestamp stored.

### 2.2 Data retention & deletion
**Actor:** guest + photographer · **Value:** "your face isn't kept forever" is true.
- Per-event retention window; auto-delete guests/faces/photos after it
- Guest deletion on request (link in the gallery email is the cheap version)
- **Accept:** expired event has no embeddings left; deletion request removes the guest.

### 2.3 Match threshold tuned on real photos
**Actor:** guest · **Value:** the product's core promise — right photos, not someone
else's. Flagged in README.v1 as the single most important knob.
- Use the existing threshold-tuning harness on a real shoot (dry-run event counts)
- Document the chosen value + false-positive/miss trade-off observed
- **Accept:** written tuning report; threshold set from data, not the 0.35 default.

---

## Milestone 3 — Feels like a product

### 3.1 UI design pass
**Actor:** both users · **Value:** first impression at a real event; today it's one
hand-rolled dark CSS file. Brief already written in
[`docs/design/ui-design-prompt.md`](./design/ui-design-prompt.md).
- Priority order: guest selfie/gallery flow (used once, must work in 30 s) →
  camera-FTP-settings page (high stakes, transcribed into a camera menu) → dashboard
- Includes the new screens M1 created: login, "check your inbox", consent moment

### 3.2 Photographer sees what's happening mid-event
**Actor:** photographer · **Value:** confidence between shots — "are photos landing?"
- Dashboard shows per-event: photos ingested (live count), last-photo-at, guest count
- **Accept:** shoot a photo → dashboard count ticks up within seconds.

### 3.3 Guest downloads / shares their photos
**Actor:** guest · **Value:** the gallery is only worth something if they can keep it.
- Full-res download per photo; "download all" can wait
- **Accept:** downloaded file is the processed original, not the thumbnail.

---

## Milestone 4 — The rest of the V1 vision

- **4.1 Pre-sorting / clustering on ingest** — photos grouped by person before any
  guest arrives; feeds a future "browse by person" and speeds matching.
- **4.2 Styling / LUT presets** — photographer picks a look per event; delivered
  photos are styled automatically (JPEG first, RAW via `rawpy` later).
- **4.3 pgvector nearest-neighbour search** — isolated optimization behind
  `api/matching.py`; only when in-Python cosine at event scale actually hurts.
- **4.4 FTPS where cameras support it** — plain-FTP credentials/photos cross the
  network unencrypted; acceptable for the pilot, not for paying customers.

---

## Milestone 5 — SaaS (only after a successful paid-ish pilot)

- Pricing + payments (per event? subscription?) — *needs a product decision first*
- Multi-photographer orgs / second shooters on one event
- Managed infra path (S3/RDS/queue per README.technical) if single-VPS stops scaling
- Monitoring/alerting beyond logs (uptime, ingest-lag alarm)

---

## Parking lot — open decisions (from deploy-pass §8)

1. **Signup policy for the pilot:** open, or invite-only allowlist? (Open signup +
   open FTP provisioning on a public box invites abuse — recommend invite-only.)
2. Guest gallery email: send immediately on match, or only when photos > 0?
3. Session length: 30 days vs shorter?
4. VPS provider/region and who owns billing?
5. Pilot event: which real event, and who's the guinea-pig photographer?

## Warnings

- **Do not run a real event before 2.1 (consent)** — biometrics without a lawful
  basis is the one item that can't be patched retroactively.
- 1.2 (Alembic) must land **before** 1.3's schema changes, or the first production
  DB starts life hand-edited.
- Milestone 4 items are tempting but none of them block a workable app — resist
  starting 4.x before M1–M2 are done.

## Next step

Pick story **1.1 + 1.2** as the first slice (public HTTPS with a migration-managed
DB is the walking skeleton of production). Then load `planning` to turn it into
PR-sized slices; each slice runs the full TDD cycle (`tdd`, `testing`,
`mutation-testing`, `refactoring`) before code changes.
