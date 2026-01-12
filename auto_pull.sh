#!/bin/bash
# Auto-pull script - polls for changes and pulls automatically

REPO_DIR="/Users/aarontopol/Desktop/cell_OS"
INTERVAL=30  # seconds between checks

cd "$REPO_DIR"

echo "🔄 Auto-pull started (checking every ${INTERVAL}s)"
echo "Press Ctrl+C to stop"

while true; do
  # Fetch to see if there are changes
  git fetch origin main --quiet 2>/dev/null

  # Check if local is behind remote
  LOCAL=$(git rev-parse HEAD)
  REMOTE=$(git rev-parse origin/main)

  if [ "$LOCAL" != "$REMOTE" ]; then
    echo "[$(date '+%H:%M:%S')] 📥 New changes detected, pulling..."
    git pull --quiet
    echo "[$(date '+%H:%M:%S')] ✓ Pull complete"
  fi

  sleep $INTERVAL
done
