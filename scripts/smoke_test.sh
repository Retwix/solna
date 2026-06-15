#!/usr/bin/env bash
#
# End-to-end smoke test for Solna V0.
#
# Exercises the full pipe WITHOUT a camera:
#   create event -> drop a photo into the event's FTP intake dir
#   -> watcher thumbnails + ingests -> photo shows up in the gallery API.
#
# Prereqs: `docker compose up --build` is running.
# Usage:   ./scripts/smoke_test.sh
#
set -euo pipefail

API="${API:-http://localhost:8080}"
INGEST_KEY="${INGEST_API_KEY:-dev-ingest-key}"

echo "1) Creating an event..."
EVENT_JSON="$(curl -fsS -X POST "$API/events" \
  -H 'content-type: application/json' \
  -d '{"name":"Smoke Test Event"}')"

read -r EVENT_ID TOKEN GALLERY_URL <<EOF
$(python3 - "$EVENT_JSON" <<'PY'
import json, sys
d = json.loads(sys.argv[1])
print(d["id"], d["gallery_url"].rsplit("/g/", 1)[1], d["gallery_url"])
PY
)
EOF

echo "   event_id   = $EVENT_ID"
echo "   gallery    = $GALLERY_URL"

echo "2) Dropping a test photo into the event's FTP intake dir..."
# Generate a JPEG straight into the shared volume the watcher observes.
docker compose exec -T watcher python - "$EVENT_ID" <<'PY'
import os, sys
from PIL import Image
event_id = sys.argv[1]
d = f"/data/ftp/raw/{event_id}"
os.makedirs(d, exist_ok=True)
Image.new("RGB", (1600, 1200), (90, 140, 200)).save(f"{d}/smoke-1.jpg", "JPEG")
print("dropped", f"{d}/smoke-1.jpg")
PY

echo "3) Waiting for the photo to appear in the gallery..."
for i in $(seq 1 20); do
  COUNT="$(curl -fsS "$API/g/$TOKEN/photos" \
    | python3 -c 'import json,sys;print(len(json.load(sys.stdin)["photos"]))')"
  if [ "$COUNT" -ge 1 ]; then
    echo "   ✅ gallery now shows $COUNT photo(s) after ~$((i))s"
    echo
    echo "Open the live gallery in a browser:  $GALLERY_URL"
    echo "(make sure the web app is running:   cd web && npm install && npm run dev)"
    exit 0
  fi
  sleep 1
done

echo "   ❌ photo did not appear within 20s — check: docker compose logs watcher api"
exit 1
