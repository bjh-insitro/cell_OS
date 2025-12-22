"""
Watcher Routes

Endpoints for controlling the S3 database watcher service.
"""

import logging
import subprocess
from pathlib import Path
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/thalamus/watcher/status")
async def get_watcher_status():
    """Check if S3 watcher is running"""
    try:
        script_path = str(Path(__file__).parent.parent.parent.parent.parent / "scripts" / "watch_s3_db.sh")
        result = subprocess.run(
            [script_path, "status"],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Parse output to determine status
        is_running = "Watcher running" in result.stdout

        # Extract PID if running
        pid = None
        if is_running:
            for line in result.stdout.split('\n'):
                if 'PID:' in line:
                    pid = line.split('PID:')[1].strip().rstrip(')')
                    break

        return {
            "running": is_running,
            "pid": pid,
            "message": result.stdout.strip()
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Watcher status check timed out")
    except Exception as e:
        logger.error(f"Error checking watcher status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/thalamus/watcher/start")
async def start_watcher():
    """Start the S3 watcher"""
    try:
        script_path = str(Path(__file__).parent.parent.parent.parent.parent / "scripts" / "watch_s3_db.sh")
        result = subprocess.run(
            [script_path, "start"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            # Check if already running
            if "already running" in result.stdout:
                return {
                    "success": False,
                    "message": "Watcher is already running",
                    "output": result.stdout
                }
            raise HTTPException(status_code=500, detail=result.stdout or result.stderr)

        return {
            "success": True,
            "message": "Watcher started successfully",
            "output": result.stdout
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Watcher start timed out")
    except Exception as e:
        logger.error(f"Error starting watcher: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/thalamus/watcher/stop")
async def stop_watcher():
    """Stop the S3 watcher"""
    try:
        script_path = str(Path(__file__).parent.parent.parent.parent.parent / "scripts" / "watch_s3_db.sh")
        result = subprocess.run(
            [script_path, "stop"],
            capture_output=True,
            text=True,
            timeout=5
        )

        return {
            "success": True,
            "message": "Watcher stopped successfully",
            "output": result.stdout
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Watcher stop timed out")
    except Exception as e:
        logger.error(f"Error stopping watcher: {e}")
        raise HTTPException(status_code=500, detail=str(e))
