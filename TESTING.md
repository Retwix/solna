# Testing Solna

Test in layers — each one builds on the last. If something breaks, you'll know
exactly which layer, instead of debugging the whole system at once.

| Layer | What it proves | Needs |
|-------|----------------|-------|
| 1. Automated tests | The core logic is correct | Python only |
| 2. Stack health | All services start | Docker |
| 3. Plumbing smoke test | Event → photo → gallery works | Docker (fake faces) |
| 4. Real faces (no camera) | Recognition + selfie match works | Docker (InsightFace) |
| 5. Camera end-to-end | A real camera uploads and sorts | Docker + camera + WiFi |
| 6. Threshold tuning | Match accuracy is good | A few labelled photos |

---

## Layer 1 — Automated tests (start here, ~3s)

Fastest confidence, no Docker. From the repo root:

```bash
pip install -r api/requirements.txt -r ftpserver/requirements.txt pytest httpx
pytest -q
```

**Success:** `45 passed`. These cover photographer accounts, event creation,
go-live routing and the unassigned tray, the gallery, privacy, FTP password
hashing, the face-matching math, the selfie-match flow (with a stub face
engine), and the live matched-photo stream. This is also what runs in CI on every push.

---

## Layer 2 — Bring up the stack and check health

```bash
cp .env.example .env          # first time only
docker compose up --build
```

Give it a minute. In another terminal, check each service answers:

```bash
curl localhost:8080/healthz       # API     -> {"status":"ok"}
curl localhost:9200/healthz       # faces   -> {"status":"ok","engine":"..."}
# MinIO console (browser): http://localhost:9101   (login minioadmin / minioadmin)
```

Start the web app too (separate terminal):

```bash
cd web && npm install && npm run dev
# -> http://localhost:5173
```

**Success:** both `/healthz` calls return ok, and `localhost:5173` shows the
"create photographer account" step (then the events dashboard).

---

## Layer 3 — Plumbing smoke test (no camera, no real faces)

Confirms the whole pipe moves a photo from intake to gallery. Set `FACE_ENGINE=fake`
in `.env` first (so no model download), then `docker compose up -d --force-recreate faceservice`.

```bash
./scripts/smoke_test.sh
```

**Success:** it prints `gallery now shows 1 photo(s)` and a gallery URL. This
means: event created → photo dropped into the intake dir → watcher thumbnailed
and ingested it → it appears via the API. If this passes, the plumbing is sound.

---

## Layer 4 — Real face recognition (still no camera)

Now test actual recognition without involving a camera yet.

1. In `.env` set `FACE_ENGINE=insightface`, then reset and restart
   (new model; first photo is slow while it downloads ~300MB):
   ```bash
   docker compose down -v && docker compose up --build
   ```
2. At `http://localhost:5173/`: create your photographer account (note the
   one-time FTP credentials), create an event, and press **Go live**.
3. Upload a few photos **of two different people** with a desktop FTP client,
   so there's something to sort:
   ```bash
   lftp -u <username>,<password> -p 2121 localhost \
     -e "set ftp:passive-mode true; mput ~/photos/*.jpg; bye"
   ```
4. Watch them get processed:
   ```bash
   docker compose logs -f watcher faceservice
   # -> [watcher] ingested raw/<photographer>/IMG_001.jpg (2 face(s))
   ```
5. Test the sorting on the **Mac** (localhost allows live camera): open the
   event's gallery link, click "Take selfie" as one of the people, enter an email.

**Success:** you get back only that person's photos, not the other's. Run it as
the second person → a different set. That's recognition working.

---

## Layer 5 — Camera, end-to-end on your WiFi

Now the real thing. Find your Mac's LAN IP: `ipconfig getifaddr en0` (e.g. `192.168.1.42`).

1. In `.env` (keep `FACE_ENGINE=insightface`):
   ```
   FTP_HOST=192.168.1.42
   FTP_PASV_ADDRESS=192.168.1.42        # critical — uploads hang without it
   PUBLIC_BASE_URL=http://192.168.1.42:5173
   S3_PUBLIC_ENDPOINT=http://192.168.1.42:9100
   ```
   Recreate the affected services: `docker compose up -d --force-recreate api ftp`,
   and run the web app with `npm run dev -- --host`.
2. Create a fresh photographer account + event (so the QR/links use the LAN
   IP), and press **Go live** on the event.
3. In the camera's FTP settings: host = your LAN IP, port **2121**,
   **plain FTP, passive mode, secure OFF**, the account's stable username/password
   (entered once — future events reuse it).
   Camera and Mac on the **same WiFi**.
4. Shoot photos of two different people. Watch `docker compose logs -f watcher`.
5. On a **phone**, open the gallery QR. Use the **"Upload a photo"** option (the
   live selfie button needs HTTPS, which we don't have locally) — it opens the
   phone camera. Enter an email.

**Success:** the photo uploads from the camera within seconds, appears in the
logs with a face count, and the guest selfie returns only that person's photos.

---

## Layer 6 — Tune match accuracy (optional but important)

The match threshold (`MATCH_SIMILARITY_THRESHOLD`, default 0.35) decides
false positives vs misses. To set it from data, assemble a labelled folder:

```
tuning/
  alice/{selfie.jpg, matches/*.jpg}     # photos alice is really in
  bob/{selfie.jpg, matches/*.jpg}
```

With the stack up on `insightface`:

```bash
pip install numpy requests
python3 scripts/tune_threshold.py ./tuning
```

It prints precision/recall/F1 at each threshold and recommends one. Set it in
`.env`, then `docker compose up -d --force-recreate api`.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| Camera connects but upload hangs | `FTP_PASV_ADDRESS` not set to your LAN IP. |
| Camera login refused | Wrong creds, or secure/SFTP on — use plain FTP, or the account was reset (`down -v` wipes photographers). |
| Photos broken in gallery | `S3_PUBLIC_ENDPOINT` wrong; must be reachable host/LAN IP:9100. Recreate `api` after `.env` changes. |
| Gallery 404 | Using the slug instead of the token, or DB was reset after the event was made. |
| Photos uploaded but not in the gallery | No event was live — check the unassigned tray on the admin page and claim them. |
| Selfie button does nothing on phone | Expected over HTTP — use "Upload a photo". |
| Selfie says "no face detected" | Clearer/closer selfie; check face service is on `insightface`, not `fake`. |
| Matches look wrong | Threshold not tuned — run Layer 6. |
| Changed `.env`, no effect | Env is read at container start: `docker compose up -d --force-recreate <service>`. |

**Reset everything (wipes all data):** `docker compose down -v && docker compose up --build`.
