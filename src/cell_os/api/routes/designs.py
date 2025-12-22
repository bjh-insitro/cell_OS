"""
Design Routes

Endpoints for managing experimental designs.
"""

import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException

from cell_os.database.cell_thalamus_db import CellThalamusDB
from ..models import DesignResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# These will be injected from main app
running_simulations: Dict[str, Dict[str, Any]] = {}
DB_PATH: str = ""


def init_globals(sims, db_path):
    """Initialize global state from main app"""
    global running_simulations, DB_PATH
    running_simulations = sims
    DB_PATH = db_path


@router.get("/api/thalamus/designs", response_model=List[DesignResponse])
async def list_designs():
    """List all designs (both running and completed)"""
    try:
        db = CellThalamusDB(db_path=DB_PATH)
        designs = db.get_designs()

        results = []
        for design in designs:
            # Check if it's currently running
            status = "completed"
            if design['design_id'] in running_simulations:
                status = running_simulations[design['design_id']]['status']

            # Get actual well count from results table
            well_count = db.get_well_count(design['design_id'])

            results.append(DesignResponse(
                design_id=design['design_id'],
                phase=design['phase'],
                cell_lines=eval(design['cell_lines']) if isinstance(design['cell_lines'], str) else design['cell_lines'],
                compounds=eval(design['compounds']) if isinstance(design['compounds'], str) else design['compounds'],
                status=status,
                created_at=design.get('created_at'),
                well_count=well_count
            ))

        db.close()
        return results

    except Exception as e:
        logger.error(f"Error listing designs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/thalamus/designs/{design_id}/status")
async def get_design_status(design_id: str):
    """Check simulation status"""
    if design_id in running_simulations:
        return running_simulations[design_id]

    # Check if completed in database
    try:
        db = CellThalamusDB(db_path=DB_PATH)
        results = db.get_results(design_id)
        db.close()

        if results:
            return {"status": "completed", "design_id": design_id}
        else:
            raise HTTPException(status_code=404, detail="Design not found")

    except Exception as e:
        logger.error(f"Error checking status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/thalamus/designs/{design_id}/cancel")
async def cancel_simulation(design_id: str):
    """Cancel a running simulation"""
    if design_id not in running_simulations:
        raise HTTPException(status_code=404, detail="Design not found or not running")

    if running_simulations[design_id]["status"] != "running":
        raise HTTPException(status_code=400, detail="Design is not running")

    # Mark as cancelled
    running_simulations[design_id]["status"] = "cancelled"
    logger.info(f"Cancelled simulation {design_id}")

    return {"status": "cancelled", "design_id": design_id, "message": "Simulation cancelled successfully"}
