"""
Simulation Routes

Endpoints for running simulations and autonomous loop experiments.
"""

import logging
import uuid
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks

from ..models import RunSimulationRequest, AutonomousLoopRequest, DesignResponse
from ..services import run_simulation_task, run_autonomous_loop_task

logger = logging.getLogger(__name__)

router = APIRouter()

# These will be injected from main app
running_simulations: Dict[str, Dict[str, Any]] = {}
DB_PATH: str = ""
USE_LAMBDA: bool = False
lambda_client = None
LAMBDA_FUNCTION_NAME: str = ""


def init_globals(sims, db_path, use_lambda, client, func_name):
    """Initialize global state from main app"""
    global running_simulations, DB_PATH, USE_LAMBDA, lambda_client, LAMBDA_FUNCTION_NAME
    running_simulations = sims
    DB_PATH = db_path
    USE_LAMBDA = use_lambda
    lambda_client = client
    LAMBDA_FUNCTION_NAME = func_name


@router.post("/api/thalamus/run", response_model=DesignResponse)
async def run_simulation(request: RunSimulationRequest, background_tasks: BackgroundTasks):
    """
    Start a Cell Thalamus simulation in the background.

    Modes:
    - demo: 7 wells, ~30 seconds
    - quick: 3 compounds, ~20 minutes
    - full: 10 compounds, full panel
    """
    try:
        design_id = str(uuid.uuid4())

        # Store initial status
        running_simulations[design_id] = {
            "status": "running",
            "design_id": design_id,
            "phase": 0,
            "cell_lines": request.cell_lines,
            "compounds": request.compounds or [],
            "mode": request.mode,
            "progress": {
                "completed": 0,
                "total": 8 if request.mode == "demo" else 96 if request.mode == "benchmark" else 576,
                "percentage": 0,
                "last_well": None,
                "completed_wells": []
            }
        }

        # Run simulation in background
        background_tasks.add_task(
            run_simulation_task,
            design_id=design_id,
            cell_lines=request.cell_lines,
            compounds=request.compounds,
            mode=request.mode,
            db_path=DB_PATH,
            running_simulations=running_simulations
        )

        return DesignResponse(
            design_id=design_id,
            phase=0,
            cell_lines=request.cell_lines,
            compounds=request.compounds or [],
            status="running"
        )

    except Exception as e:
        logger.error(f"Error starting simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/thalamus/autonomous-loop", response_model=DesignResponse)
async def run_autonomous_loop(request: AutonomousLoopRequest, background_tasks: BackgroundTasks):
    """
    Run an autonomous loop experiment - portfolio of high-uncertainty candidates.

    This generates a portfolio experiment design with:
    - Primary candidate: 60 wells (8 doses × 6 reps + 12 controls)
    - Scout candidates: 30 wells each (6 doses × 4 reps + 6 controls)
    - Probe candidates: 25 wells each (5 doses × 4 reps + 5 controls)
    Total: ~170 wells for 5 candidates
    """
    try:
        design_id = str(uuid.uuid4())

        total_wells = sum(c.wells for c in request.candidates)
        cell_lines = list(set(c.cell_line for c in request.candidates))
        compounds = list(set(c.compound for c in request.candidates))

        # Store initial status
        running_simulations[design_id] = {
            "status": "running",
            "design_id": design_id,
            "phase": 0,
            "cell_lines": cell_lines,
            "compounds": compounds,
            "mode": "autonomous_loop",
            "metadata": {
                "type": "autonomous_loop_portfolio",
                "candidates": [c.dict() for c in request.candidates],
                "total_wells": total_wells
            },
            "progress": {
                "completed": 0,
                "total": total_wells,
                "percentage": 0,
                "last_well": None,
                "completed_wells": []
            }
        }

        # Run autonomous loop experiment in background
        background_tasks.add_task(
            run_autonomous_loop_task,
            design_id=design_id,
            candidates=request.candidates,
            db_path=DB_PATH,
            running_simulations=running_simulations,
            use_lambda=USE_LAMBDA,
            lambda_client=lambda_client,
            lambda_function_name=LAMBDA_FUNCTION_NAME
        )

        return DesignResponse(
            design_id=design_id,
            phase=0,
            cell_lines=cell_lines,
            compounds=compounds,
            status="running"
        )

    except Exception as e:
        logger.error(f"Error starting autonomous loop: {e}")
        raise HTTPException(status_code=500, detail=str(e))
