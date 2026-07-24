# Design: the deploy pass — public HTTPS, magic-link auth, email

**Status:** draft for review · **Goal:** a photographer can run ONE real event with real guests.

## Why these three together

Deployment forces HTTPS (mobile browsers block the selfie camera on plain
HTTP). A public URL forces admin auth (today anyone can create events and go
live). Magic-link auth forces email sending — which the product needs anyway
(guests type an email that currently goes nowhere). One pass, three
dependencies resolved in the right order.

---

## 1. Topology (single cheap VPS)

Hetzner CX32 / OVH / Scaleway equivalent — 4 vCPU, 8 GB RAM (InsightFace wants
~2 GB; 4 GB total is workable but tight next to Postgres + MinIO). Ubuntu LTS,
Docker + compose. Free subdomain for the pilot (e.g. DuckDNS) — swap for a
real domain later; nothing below depends on the name.

```
                    Internet
                       │
       ┌───────────────┼──────────────────┐
       │ :80 + :443    │ :2121 + passive  │
       ▼               ▼                  │
  ┌─────────┐     ┌─────────┐             │
  │  Caddy  │     │   ftp   │             │
  └────┬────┘     └─────────┘             │
       │ serves/                     VPS firewall:
       │ proxies                     80, 443, 2121, 21100-21110 only
       ├── /            → web/dist (static build)
       ├── /api/*       → api:8000
       └── /media/*     → minio:9000/solna-media
```

**Key decision: one origin.** The web app, API and photo URLs all live under
the same domain (`/`, `/api`, `/media`). This kills CORS entirely (the
dev-only `allow_origins=["*"]` goes away), makes cookies trivially safe, and
means the QR/gallery links are just `https://<domain>/g/<token>`.

Changes this implies:
- Port 80 stays open: Caddy needs it for the ACME HTTP-01 challenge and for
  redirecting `http://` hits (typed URLs, old links) to HTTPS.
- `web`: `VITE_API_BASE=/api` at build time; Caddy serves `dist/` (no Node in prod).
- `api`: Caddy strips the `/api` prefix (`handle_path`); uvicorn additionally
  gets `--root-path /api` so generated docs/URLs are correct. (`--root-path`
  alone does NOT strip the prefix — the strip must happen in Caddy.)
- `PUBLIC_BASE_URL=https://<domain>` — QR/gallery links are built server-side
  from it (`api/routers/events.py`); left at the default they point at
  `localhost:8000` even with everything else deployed.
- `S3_PUBLIC_ENDPOINT=https://<domain>/media`; Caddy proxies to MinIO. Public
  object URLs are `<endpoint>/solna-media/<key>` (`api/storage.py`), so the
  `/media/*` route strips `/media` and forwards the rest (bucket included) to
  `minio:9000`.
- `ftp`: config-only change — `FTP_PASV_ADDRESS` must be set to the VPS public
  IP, otherwise passive mode advertises an unreachable address to cameras.
- SSE endpoints (`/g/*/stream`, `/g/*/matches/stream`) work through Caddy's
  `reverse_proxy` unmodified — it auto-detects `text/event-stream` and flushes.
- New `docker-compose.prod.yml` overlay: adds caddy, removes host-port
  mappings except ftp, sets restart policies.

**FTP reality check.** Cameras speak plain FTP: credentials and photos cross
the network unencrypted. Acceptable for the pilot (short-lived per-account
creds, chrooted, nothing else on the box), but document it and revisit
(FTPS where cameras support it) before charging customers.

---

## 2. Magic-link auth (photographer/admin)

### Schema

```python
class Photographer(Base):
    email: Mapped[str]              # becomes REQUIRED and unique (was optional)
    ...

class LoginToken(Base):
    id: Mapped[str]                 # uuid
    photographer_id: Mapped[str]    # FK
    token_hash: Mapped[str]         # sha256 of the token — never store plaintext
    expires_at: Mapped[datetime]    # now + 15 min
    used_at: Mapped[datetime | None]
```

Sessions: signed cookie (`itsdangerous`), httpOnly + Secure + SameSite=Lax,
30-day expiry. No session table needed for V1 (nothing to revoke yet).

### Flow

```
POST /api/auth/request-link {email}
  → always 200 (no account enumeration)
  → if email known: create LoginToken, send email with
    https://<domain>/auth/verify?token=...
GET /api/auth/verify?token=
  → valid + unused + unexpired: set session cookie, redirect to /
  → else: redirect to /login?error=expired
POST /api/auth/logout → clear cookie
GET  /api/me          → current photographer (id, name, email)
GET  /api/me/events   → their events (the list endpoint the UI finally needs)
```

### What gets protected

| Surface | Auth |
|---|---|
| `POST /photographers` | becomes **signup**: name + email → sends first magic link (no creds shown until logged in; FTP creds move to a "camera setup" page shown after login) |
| events CRUD, go-live/stop, claim, tray, PATCH photo | session cookie, and the resource must belong to the logged-in photographer |
| `/g/*` guest endpoints | unchanged — the unguessable token IS the auth |
| `/internal/ingest` | unchanged — `X-Ingest-Key` |

### Admin UI changes

localStorage stops being the source of truth for identity (it burned us once
already). Login screen (enter email → "check your inbox") → dashboard loads
from `/api/me` + `/api/me/events`. The stale-account detection becomes
"401 → redirect to login".

---

## 3. Email

One tiny abstraction, two backends:

```python
# api/mailer.py
def send(to: str, subject: str, html: str) -> None: ...
```

- **`MAIL_BACKEND=console`** (dev/CI default): print the message — magic links
  land in `docker compose logs api`, tests assert on a captured message,
  nothing external needed.
- **`MAIL_BACKEND=smtp`**: any provider. Suggest **Brevo** (French, GDPR-easy,
  300 mails/day free) — but it's just SMTP env vars, swappable.

Also used (same pass, cheap): after a guest match, email them their personal
gallery link `https://<domain>/g/<token>?guest=<guest_token>` — makes the
email field finally deliver value, and solves "guest switches device".
(The gallery page learns to read `?guest=` in addition to localStorage.)

Rate limits: 3 link requests / email / hour; 1 guest email per match.

---

## 4. Alembic (now mandatory)

First deploy = first data that survives. `down -v` stops being an option.
- Add alembic, generate the initial migration from current models.
- API startup: run `alembic upgrade head` instead of `create_all`.
- This pass's own schema changes (email required, login_tokens) become the
  second migration — a real test of the workflow.

---

## 5. Hardening checklist (same pass, small items)

- [ ] CORS middleware removed (single origin) — or locked to the domain
- [ ] Cookies: httpOnly, Secure, SameSite=Lax
- [ ] MinIO console not exposed; bucket read via Caddy path only
- [ ] Postgres/MinIO/faceservice: no public ports (compose-internal only)
- [ ] `INGEST_API_KEY`, session secret, SMTP creds: strong values in `.env.prod` (never committed)
- [ ] Nightly `pg_dump` + weekly MinIO volume snapshot to off-box storage
- [ ] Watchtower or manual `git pull && compose up -d --build` deploy script (`scripts/deploy.sh`)

## 6. Test impact

- Auth behaviour tests: request-link creates a hashed token + "sends" mail
  (console backend captured); verify sets a session; expired/used tokens
  rejected; protected endpoints 401 anonymous, 403 cross-account.
- Guest email test: match → mail captured with the right link.
- Existing tests: `make_photographer` gains an email; fixtures log in via a
  test helper that mints a session cookie directly.

## 7. Non-goals of this pass

Payments, multi-photographer orgs, FTPS, S3/RDS migration, consent capture
(next pass — but the deploy makes it urgent), styling/clustering.

## 8. Open questions

1. Signup: open to anyone, or invite-only (env-var allowlist of emails) for
   the pilot? Open signup + open FTP provisioning on a public box invites abuse.
2. Guest gallery links: send immediately on match, or only if photos > 0?
3. Session length: 30 days OK, or shorter for a shared-computer scenario?
4. Which VPS provider/region — and who owns the account/billing?
