#!/bin/bash

# Watch directory for file changes and notify API
WATCH_DIR=$1
API_URL=$2

echo "Watching $WATCH_DIR for changes, will notify $API_URL"

# Use inotifywait to monitor the directory
inotifywait -m -r -e create,modify,delete "$WATCH_DIR" --format '%w%f %e' |
while read file event; do
    echo "File $file was $event"
    # Notify the API about the file change
    curl -X POST "$API_URL/file-changed" \
         -H "Content-Type: application/json" \
         -d "{\"file\":\"$file\",\"event\":\"$event\"}" \
         || echo "Failed to notify API"
done