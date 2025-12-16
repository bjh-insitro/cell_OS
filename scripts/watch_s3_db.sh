#!/bin/bash
# Background S3 DB Watcher for Cell Thalamus
# Auto-downloads database from S3 when it changes
#
# Usage:
#   ./scripts/watch_s3_db.sh start   # Start watching in background
#   ./scripts/watch_s3_db.sh stop    # Stop watching
#   ./scripts/watch_s3_db.sh status  # Check if running

set -e

S3_BUCKET="insitro-user"
S3_KEY="brig/cell_thalamus_results.db"
LOCAL_DB_PATH="/Users/bjh/cell_OS/data/cell_thalamus.db"
CHECK_INTERVAL=30  # seconds between checks
PID_FILE="/tmp/cell_os_s3_watcher.pid"
LOG_FILE="/tmp/cell_os_s3_watcher.log"

function watch_loop() {
    echo "🔍 Starting S3 watcher..."
    echo "   Checking s3://$S3_BUCKET/$S3_KEY every ${CHECK_INTERVAL}s"
    echo "   Local DB: $LOCAL_DB_PATH"
    echo "   Log: $LOG_FILE"
    echo ""

    last_etag=""

    while true; do
        # Get S3 file ETag (unique identifier for file version)
        current_etag=$(aws s3api head-object \
            --bucket "$S3_BUCKET" \
            --key "$S3_KEY" \
            --profile bedrock \
            --query 'ETag' \
            --output text 2>/dev/null || echo "")

        if [ -z "$current_etag" ]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  Could not reach S3 (check connection)"
            /bin/sleep $CHECK_INTERVAL
            continue
        fi

        # Check if file changed
        if [ "$current_etag" != "$last_etag" ]; then
            if [ -n "$last_etag" ]; then
                echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🔄 Change detected! Downloading..."

                # Download updated DB
                aws s3 cp "s3://$S3_BUCKET/$S3_KEY" "$LOCAL_DB_PATH" --profile bedrock

                size=$(ls -lh "$LOCAL_DB_PATH" | awk '{print $5}')
                echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Downloaded! Size: $size"
                echo ""
            else
                echo "[$(date '+%Y-%m-%d %H:%M:%S')] 📡 Initial sync - tracking ETag: ${current_etag:0:12}..."
            fi

            last_etag="$current_etag"
        fi

        /bin/sleep $CHECK_INTERVAL
    done
}

function start_watcher() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "❌ Watcher already running (PID: $pid)"
            echo "   Use './scripts/watch_s3_db.sh stop' to stop it first"
            exit 1
        else
            # Stale PID file
            rm "$PID_FILE"
        fi
    fi

    # Start watcher in background - call this script recursively with _watch_loop
    nohup "$0" _watch_loop > "$LOG_FILE" 2>&1 &
    pid=$!
    echo $pid > "$PID_FILE"

    echo "✅ S3 watcher started (PID: $pid)"
    echo "   Checking s3://$S3_BUCKET/$S3_KEY every ${CHECK_INTERVAL}s"
    echo ""
    echo "Commands:"
    echo "   tail -f $LOG_FILE        # View live log"
    echo "   ./scripts/watch_s3_db.sh stop   # Stop watcher"
}

function stop_watcher() {
    if [ ! -f "$PID_FILE" ]; then
        echo "⚠️  Watcher not running (no PID file found)"
        exit 0
    fi

    pid=$(cat "$PID_FILE")

    if ps -p "$pid" > /dev/null 2>&1; then
        kill "$pid"
        rm "$PID_FILE"
        echo "✅ Watcher stopped (PID: $pid)"
    else
        echo "⚠️  Watcher not running (stale PID)"
        rm "$PID_FILE"
    fi
}

function status_watcher() {
    if [ ! -f "$PID_FILE" ]; then
        echo "❌ Watcher not running"
        exit 0
    fi

    pid=$(cat "$PID_FILE")

    if ps -p "$pid" > /dev/null 2>&1; then
        echo "✅ Watcher running (PID: $pid)"
        echo "   Log: $LOG_FILE"
        echo ""
        echo "Recent activity:"
        tail -5 "$LOG_FILE" 2>/dev/null || echo "   (no logs yet)"
    else
        echo "❌ Watcher not running (stale PID file)"
        rm "$PID_FILE"
    fi
}

# Main
case "${1:-}" in
    _watch_loop)
        # Internal: called by nohup for background process
        watch_loop
        ;;
    start)
        start_watcher
        ;;
    stop)
        stop_watcher
        ;;
    status)
        status_watcher
        ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        echo ""
        echo "Commands:"
        echo "  start   - Start watching S3 for changes (runs in background)"
        echo "  stop    - Stop the watcher"
        echo "  status  - Check if watcher is running"
        echo ""
        echo "Example workflow:"
        echo "  1. Start watcher:  ./scripts/watch_s3_db.sh start"
        echo "  2. Run simulation on JupyterHub (auto-uploads to S3)"
        echo "  3. Watch auto-downloads to your Mac"
        echo "  4. Stop watcher:   ./scripts/watch_s3_db.sh stop"
        exit 1
        ;;
esac
