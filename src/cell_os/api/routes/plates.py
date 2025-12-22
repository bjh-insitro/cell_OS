"""
Plates Routes

Endpoints for retrieving plate-specific data.
"""

import logging
from fastapi import APIRouter, HTTPException

from cell_os.database.cell_thalamus_db import CellThalamusDB

logger = logging.getLogger(__name__)

router = APIRouter()

# These will be injected from main app
DB_PATH: str = ""


def init_globals(db_path):
    """Initialize global state from main app"""
    global DB_PATH
    DB_PATH = db_path


@router.get("/api/thalamus/designs/{design_id}/plates/{plate_id}")
async def get_plate_data(design_id: str, plate_id: str):
    """Get data for a specific plate (for heatmap)"""
    try:
        db = CellThalamusDB(db_path=DB_PATH)
        results = db.get_results(design_id, filters={'plate_id': plate_id})
        db.close()

        if not results:
            raise HTTPException(status_code=404, detail="No plate data found")

        return results

    except Exception as e:
        logger.error(f"Error getting plate data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
