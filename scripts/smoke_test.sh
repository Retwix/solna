#!/usr/bin/env bash
#
# End-to-end smoke test for Solna.
#
# Exercises the full pipe WITHOUT a camera:
#   create photographer -> create event -> go live
#   -> upload a photo over FTP with the account's credentials
#   -> FTP server thumbnails + ingests -> photo shows up in the gallery API.
#
# Prereqs: `docker compose up --build` is running.
# Usage:   ./scripts/smoke_test.sh
#
set -euo pipefail

API="${API:-http://localhost:8080}"
FTP="${FTP:-localhost:2121}"
FACE="${FACE:-http://localhost:9200}"

echo "1) Creating a photographer account..."
PHOTOGRAPHER_JSON="$(curl -fsS -X POST "$API/photographers" \
  -H 'content-type: application/json' \
  -d '{"name":"Smoke Test Photographer"}')"
read -r PHOTOGRAPHER_ID FTP_USER FTP_PASS <<EOF
$(python3 -c 'import json,sys;d=json.loads(sys.argv[1]);print(d["id"],d["ftp"]["username"],d["ftp"]["password"])' "$PHOTOGRAPHER_JSON")
EOF
echo "   photographer_id = $PHOTOGRAPHER_ID"

echo "2) Creating an event and going live..."
EVENT_JSON="$(curl -fsS -X POST "$API/events" \
  -H 'content-type: application/json' \
  -d "{\"name\":\"Smoke Test Event\",\"photographer_id\":\"$PHOTOGRAPHER_ID\"}")"

read -r EVENT_ID TOKEN GALLERY_URL <<EOF
$(python3 - "$EVENT_JSON" <<'PY'
import json, sys
d = json.loads(sys.argv[1])
print(d["id"], d["gallery_url"].rsplit("/g/", 1)[1], d["gallery_url"])
PY
)
EOF

curl -fsS -X POST "$API/events/$EVENT_ID/go-live" > /dev/null
echo "   event_id   = $EVENT_ID (live)"
echo "   gallery    = $GALLERY_URL"

echo "3) Uploading a test photo over FTP (as the camera would)..."
PHOTO="$(mktemp -t solna-smoke.XXXXXX).jpg"
docker compose exec -T api python -c '
import io, sys
from PIL import Image
buf = io.BytesIO()
Image.new("RGB", (1600, 1200), (90, 140, 200)).save(buf, "JPEG")
sys.stdout.buffer.write(buf.getvalue())' > "$PHOTO"
# The first /embed loads (and after `down -v` downloads) the face model.
curl -fsS --max-time 300 -F "file=@$PHOTO" "$FACE/embed" > /dev/null
curl -fsS -T "$PHOTO" "ftp://$FTP_USER:$FTP_PASS@$FTP/smoke-1.jpg"
rm -f "$PHOTO"
echo "   uploaded smoke-1.jpg"

echo "4) Waiting for the photo to appear in the gallery..."
for i in $(seq 1 20); do
  COUNT="$(curl -fsS "$API/g/$TOKEN" \
    | python3 -c 'import json,sys;print(json.load(sys.stdin)["photo_count"])')"
  if [ "$COUNT" -ge 1 ]; then
    echo "   ✅ gallery now shows $COUNT photo(s) after ~$((i))s"
    echo
    echo "Open the live gallery in a browser:  $GALLERY_URL"
    echo "(make sure the web app is running:   cd web && npm install && npm run dev)"
    exit 0
  fi
  sleep 1
done

echo "   ❌ photo did not appear within 20s — check: docker compose logs ftp api"
exit 1
