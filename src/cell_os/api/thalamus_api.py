"""
Cell Thalamus FastAPI Backend

REST API for Cell Thalamus dashboard - provides endpoints for:
- Running simulations (Demo/Quick/Full modes)
- Retrieving experimental results
- Performing variance analysis
- Getting sentinel SPC data
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
from pathlib import Path
import uuid

from cell_os.cell_thalamus import CellThalamusAgent
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.database.cell_thalamus_db import CellThalamusDB
from cell_os.cell_thalamus.variance_analysis import VarianceAnalyzer

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Cell Thalamus API", version="1.0.0")

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for running simulations
running_simulations: Dict[str, Dict[str, Any]] = {}

# Database path
DB_PATH = "data/cell_thalamus.db"


# ============================================================================
# Pydantic Models (Request/Response)
# ============================================================================

class RunSimulationRequest(BaseModel):
    cell_lines: List[str]
    compounds: Optional[List[str]] = None
    mode: str = "demo"  # demo, quick, full


class DesignResponse(BaseModel):
    design_id: str
    phase: int
    cell_lines: List[str]
    compounds: List[str]
    status: str
    created_at: Optional[str] = None


class ResultResponse(BaseModel):
    result_id: int
    design_id: str
    well_id: str
    cell_line: str
    compound: str
    dose_uM: float
    timepoint_h: float
    plate_id: str
    day: int
    operator: str
    is_sentinel: bool
    morph_er: float
    morph_mito: float
    morph_nucleus: float
    morph_actin: float
    morph_rna: float
    atp_signal: float


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """API health check"""
    return {"status": "ok", "service": "Cell Thalamus API"}


@app.post("/api/thalamus/run", response_model=DesignResponse)
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
            _run_simulation_task,
            design_id=design_id,
            cell_lines=request.cell_lines,
            compounds=request.compounds,
            mode=request.mode
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


def _run_simulation_task(design_id: str, cell_lines: List[str], compounds: Optional[List[str]], mode: str):
    """Background task to run the simulation"""
    try:
        hardware = BiologicalVirtualMachine()
        db = CellThalamusDB(db_path=DB_PATH)
        agent = CellThalamusAgent(phase=0, hardware=hardware, db=db)

        # Override design_id to match our REST API ID
        agent.design_id = design_id

        # Set up progress tracking callback
        def progress_callback(completed_wells: int, total_wells: int, last_well_id: str = None):
            # Add to completed wells list
            if "completed_wells" not in running_simulations[design_id]["progress"]:
                running_simulations[design_id]["progress"]["completed_wells"] = []

            if last_well_id and last_well_id not in running_simulations[design_id]["progress"]["completed_wells"]:
                running_simulations[design_id]["progress"]["completed_wells"].append(last_well_id)

            running_simulations[design_id]["progress"]["completed"] = completed_wells
            running_simulations[design_id]["progress"]["total"] = total_wells
            running_simulations[design_id]["progress"]["percentage"] = int((completed_wells / total_wells) * 100) if total_wells > 0 else 0
            running_simulations[design_id]["progress"]["last_well"] = last_well_id

            logger.info(f"Progress: {completed_wells}/{total_wells} ({running_simulations[design_id]['progress']['percentage']}%) - Last well: {last_well_id}")

        # Store callback in agent
        agent.progress_callback = progress_callback

        # Run appropriate mode
        if mode == "demo":
            agent.run_demo_mode()
        elif mode == "benchmark":
            agent.run_benchmark_plate()
        elif mode == "quick":
            agent.run_quick_test()
        else:
            agent.run_phase_0(cell_lines=cell_lines, compounds=compounds)

        # Update status
        running_simulations[design_id]["status"] = "completed"
        running_simulations[design_id]["progress"]["percentage"] = 100

    except Exception as e:
        logger.error(f"Simulation failed: {e}")
        running_simulations[design_id]["status"] = "failed"
        running_simulations[design_id]["error"] = str(e)


@app.get("/api/thalamus/designs", response_model=List[DesignResponse])
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

            results.append(DesignResponse(
                design_id=design['design_id'],
                phase=design['phase'],
                cell_lines=eval(design['cell_lines']) if isinstance(design['cell_lines'], str) else design['cell_lines'],
                compounds=eval(design['compounds']) if isinstance(design['compounds'], str) else design['compounds'],
                status=status,
                created_at=design.get('created_at')
            ))

        db.close()
        return results

    except Exception as e:
        logger.error(f"Error listing designs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/thalamus/designs/{design_id}/status")
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


@app.post("/api/thalamus/designs/{design_id}/cancel")
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


@app.get("/api/thalamus/designs/{design_id}/results")
async def get_results(design_id: str):
    """Get all results for a design"""
    try:
        db = CellThalamusDB(db_path=DB_PATH)
        results = db.get_results(design_id)
        db.close()

        if not results:
            raise HTTPException(status_code=404, detail="No results found")

        return results

    except Exception as e:
        logger.error(f"Error getting results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/thalamus/designs/{design_id}/morphology")
async def get_morphology_matrix(design_id: str):
    """Get morphology matrix for PCA visualization"""
    try:
        db = CellThalamusDB(db_path=DB_PATH)
        matrix, well_ids = db.get_morphology_matrix(design_id)
        db.close()

        if not matrix:
            raise HTTPException(status_code=404, detail="No morphology data found")

        return {
            "matrix": matrix,
            "well_ids": well_ids,
            "channels": ["ER", "Mito", "Nucleus", "Actin", "RNA"]
        }

    except Exception as e:
        logger.error(f"Error getting morphology: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/thalamus/designs/{design_id}/dose-response")
async def get_dose_response(design_id: str, compound: str, cell_line: str, metric: str = "atp_signal"):
    """Get dose-response data for a specific compound/cell line"""
    try:
        db = CellThalamusDB(db_path=DB_PATH)
        data = db.get_dose_response_data(design_id, compound, cell_line, metric)
        db.close()

        if not data:
            raise HTTPException(status_code=404, detail="No dose-response data found")

        # Convert to dict format
        return {
            "doses": [d[0] for d in data],
            "values": [d[1] for d in data],
            "compound": compound,
            "cell_line": cell_line,
            "metric": metric
        }

    except Exception as e:
        logger.error(f"Error getting dose-response: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/thalamus/designs/{design_id}/variance")
async def get_variance_analysis(design_id: str):
    """Perform variance analysis"""
    try:
        db = CellThalamusDB(db_path=DB_PATH)
        analyzer = VarianceAnalyzer(db)
        raw_analysis = analyzer.analyze_design(design_id)
        db.close()

        if "error" in raw_analysis:
            raise HTTPException(status_code=404, detail=raw_analysis["error"])

        # Transform to match frontend structure and convert numpy types
        # Use ATP signal as the primary metric (could make this configurable)
        atp_components = raw_analysis['variance_components']['atp_signal']
        summary = raw_analysis['summary']
        spc = raw_analysis['spc_results']

        # Helper function to convert numpy types to Python native types
        def to_native(val):
            if hasattr(val, 'item'):
                return val.item()
            return float(val) if isinstance(val, (int, float)) else val

        # Build components array
        components = []
        for source, variance in atp_components['components'].items():
            total_var = atp_components['total_variance']
            fraction = variance / total_var if total_var > 0 else 0
            components.append({
                'source': source,
                'variance': to_native(variance),
                'fraction': to_native(fraction)
            })

        # Add residual variance as a component
        components.append({
            'source': 'residual',
            'variance': to_native(atp_components['residual_variance']),
            'fraction': to_native(atp_components['residual_fraction'])
        })

        # Calculate sentinel pass rate
        if 'error' not in spc:
            total_sentinels = sum(v['n_points'] for v in spc.values())
            in_control_sentinels = sum(
                v['n_points'] - v['n_out_of_control']
                for v in spc.values()
            )
            pass_rate = in_control_sentinels / total_sentinels if total_sentinels > 0 else 0
        else:
            pass_rate = 0

        # Transform to frontend format
        analysis = {
            'metric': 'atp_signal',
            'total_variance': to_native(atp_components['total_variance']),
            'biological_fraction': to_native(summary['biological_fraction_mean']),
            'technical_fraction': to_native(summary['technical_fraction_mean']),
            'pass_rate': to_native(pass_rate),
            'criteria': {
                'biological_dominance': bool(summary['criteria']['biological_dominance']['pass']),
                'technical_minimal': bool(summary['criteria']['technical_control']['pass']),
                'sentinel_stable': bool(summary['criteria']['sentinel_stability']['pass'])
            },
            'components': components
        }

        return analysis

    except Exception as e:
        logger.error(f"Error in variance analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/thalamus/designs/{design_id}/sentinels")
async def get_sentinel_data(design_id: str):
    """Get sentinel SPC data"""
    try:
        db = CellThalamusDB(db_path=DB_PATH)
        sentinel_data = db.get_sentinel_data(design_id)
        db.close()

        if not sentinel_data:
            raise HTTPException(status_code=404, detail="No sentinel data found")

        return sentinel_data

    except Exception as e:
        logger.error(f"Error getting sentinel data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/thalamus/designs/{design_id}/plates/{plate_id}")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
