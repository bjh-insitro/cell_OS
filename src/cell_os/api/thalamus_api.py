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
import os
import json
from datetime import datetime

from cell_os.cell_thalamus import CellThalamusAgent
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.database.cell_thalamus_db import CellThalamusDB
from cell_os.cell_thalamus.variance_analysis import VarianceAnalyzer
from cell_os.cell_thalamus.boundary_detection import (
    analyze_boundaries,
    SentinelSpec,
    AnchorBudgeter,
    BoundaryBandSelector,
    AcquisitionPlanner
)
from cell_os.cell_thalamus.manifold_charts import (
    BoundaryType,
    ChartStatus,
    ManifoldChart,
    create_chart_from_integration_test,
    compute_dose_pair_separation,
    compute_archetype_fanout
)

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

# Database path - use absolute path to work from any directory
DB_PATH = str(Path(__file__).parent.parent.parent.parent / "data" / "cell_thalamus.db")

# Lambda configuration
USE_LAMBDA = os.getenv('USE_LAMBDA', 'false').lower() == 'true'
LAMBDA_FUNCTION_NAME = os.getenv('LAMBDA_FUNCTION_NAME', 'cell-thalamus-simulator')
AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')
AWS_PROFILE = os.getenv('AWS_PROFILE', 'bedrock')

# Initialize Lambda client if using Lambda
lambda_client = None
if USE_LAMBDA:
    try:
        import boto3  # Only import if using Lambda
        session = boto3.Session(profile_name=AWS_PROFILE)
        lambda_client = session.client('lambda', region_name=AWS_REGION)
        logger.info(f"✓ Lambda client initialized (function: {LAMBDA_FUNCTION_NAME}, region: {AWS_REGION})")
    except ImportError:
        logger.warning("boto3 not installed. Install with: pip install boto3. Falling back to local execution.")
        USE_LAMBDA = False
    except Exception as e:
        logger.warning(f"Failed to initialize Lambda client: {e}. Falling back to local execution.")
        USE_LAMBDA = False


# ============================================================================
# Pydantic Models (Request/Response)
# ============================================================================

class RunSimulationRequest(BaseModel):
    cell_lines: List[str]
    compounds: Optional[List[str]] = None
    mode: str = "demo"  # demo, quick, full


class AutonomousLoopCandidate(BaseModel):
    """Individual candidate in autonomous loop portfolio"""
    compound: str
    cell_line: str
    timepoint_h: float
    wells: int  # Allocated well count
    priority: str  # "Primary", "Scout", "Probe"


class AutonomousLoopRequest(BaseModel):
    """Request for autonomous loop experiment - portfolio of top candidates"""
    candidates: List[AutonomousLoopCandidate]


class DesignResponse(BaseModel):
    design_id: str
    phase: int
    cell_lines: List[str]
    compounds: List[str]
    status: str
    created_at: Optional[str] = None
    well_count: Optional[int] = None


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
    atp_signal: float  # NOTE: Actually LDH cytotoxicity (kept name for backward compat). High = cell death, Low = viable


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """API health check"""
    return {"status": "ok", "service": "Cell Thalamus API"}


@app.post("/api/thalamus/autonomous-loop", response_model=DesignResponse)
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
            _run_autonomous_loop_task,
            design_id=design_id,
            candidates=request.candidates
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


def _invoke_lambda_simulation(design_id: str, candidates: List):
    """Invoke AWS Lambda to run simulation"""
    try:
        # Prepare payload
        payload = {
            'design_id': design_id,
            'candidates': [c.dict() if hasattr(c, 'dict') else c for c in candidates]
        }

        logger.info(f"Invoking Lambda with {len(candidates)} candidates...")

        # Invoke Lambda asynchronously
        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )

        status_code = response['StatusCode']
        if status_code == 202:
            running_simulations[design_id]["status"] = "running_lambda"
            running_simulations[design_id]["lambda_invoked"] = True
            logger.info(f"✓ Lambda invoked successfully (status: {status_code})")
            logger.info(f"⏳ Simulation running on Lambda. Results will appear in S3 and auto-sync to local.")
        else:
            raise Exception(f"Lambda invocation failed with status: {status_code}")

    except Exception as e:
        logger.error(f"Lambda invocation failed: {e}")
        running_simulations[design_id]["status"] = "failed"
        running_simulations[design_id]["error"] = f"Lambda invocation failed: {str(e)}"
        raise


def _run_autonomous_loop_task(design_id: str, candidates: List):
    """Background task to run autonomous loop portfolio experiment"""
    try:
        # Check if we should use Lambda
        if USE_LAMBDA and lambda_client:
            logger.info(f"🚀 Invoking Lambda function: {LAMBDA_FUNCTION_NAME}")
            _invoke_lambda_simulation(design_id, candidates)
            return

        # Otherwise run locally
        logger.info(f"💻 Running simulation locally")
        from cell_os.cell_thalamus.design_generator import WellAssignment
        import numpy as np

        hardware = BiologicalVirtualMachine()
        db = CellThalamusDB(db_path=DB_PATH)
        agent = CellThalamusAgent(phase=0, hardware=hardware, db=db)
        agent.design_id = design_id

        # Compound EC50 values for dose spacing
        compound_params = {
            'tBHQ': {'ec50_uM': 30.0},
            'H2O2': {'ec50_uM': 100.0},
            'tunicamycin': {'ec50_uM': 1.0},
            'thapsigargin': {'ec50_uM': 0.5},
            'CCCP': {'ec50_uM': 5.0},
            'oligomycin': {'ec50_uM': 1.0},
            'etoposide': {'ec50_uM': 10.0},
            'MG132': {'ec50_uM': 1.0},
            'nocodazole': {'ec50_uM': 0.5},
            'paclitaxel': {'ec50_uM': 0.01}
        }

        # Save design
        all_cell_lines = list(set(c.cell_line for c in candidates))
        all_compounds = list(set(c.compound for c in candidates))
        all_timepoints = list(set(c.timepoint_h for c in candidates))

        db.save_design(
            design_id=design_id,
            phase=0,
            cell_lines=all_cell_lines,
            compounds=all_compounds,
            metadata={
                'type': 'autonomous_loop_portfolio',
                'mode': 'autonomous_loop',
                'timepoints': all_timepoints,
                'candidates': [c.dict() for c in candidates]
            }
        )

        # Generate wells for each candidate
        wells = []
        well_idx = 0
        plate_idx = 1

        # Calculate proportional control allocation to hit exactly 32 controls
        total_experimental = sum(c.wells for c in candidates)
        TARGET_CONTROLS = 32  # 16 per plate × 2 plates

        controls_per_candidate = []
        for c in candidates:
            ctrl = max(4, round((c.wells / total_experimental) * TARGET_CONTROLS))
            controls_per_candidate.append(ctrl)

        # Adjust for rounding to hit exactly 64
        total_controls = sum(controls_per_candidate)
        if total_controls != TARGET_CONTROLS:
            controls_per_candidate[0] += (TARGET_CONTROLS - total_controls)

        for idx, candidate in enumerate(candidates):
            ec50 = compound_params.get(candidate.compound, {'ec50_uM': 10.0})['ec50_uM']

            # Use allocated experimental wells and proportional controls
            num_experimental = candidate.wells
            num_controls = controls_per_candidate[idx]

            # Determine doses and replicates to fill experimental wells
            # Try to get 6-8 dose points with good replication
            if num_experimental >= 80:  # Primary allocation (~94 wells)
                num_doses = 8
                num_reps = num_experimental // num_doses
            elif num_experimental >= 60:  # Scout allocation (~69 wells)
                num_doses = 7
                num_reps = num_experimental // num_doses
            else:  # Probe allocation (~44 wells)
                num_doses = 6
                num_reps = num_experimental // num_doses

            # Generate log-spaced doses around EC50
            log_doses = np.linspace(np.log10(ec50 * 0.1), np.log10(ec50 * 10), num_doses)
            doses = [10 ** ld for ld in log_doses]

            # Experimental wells - distribute all allocated wells
            # Use floor division for base replicates, then add remainder wells
            base_reps = num_experimental // num_doses
            remainder = num_experimental % num_doses

            for dose_idx, dose in enumerate(doses):
                # Add 1 extra replicate to first 'remainder' doses to use all wells
                reps_for_this_dose = base_reps + (1 if dose_idx < remainder else 0)

                for rep in range(reps_for_this_dose):
                    wells.append(WellAssignment(
                        well_id=f"W{well_idx+1:03d}",
                        cell_line=candidate.cell_line,
                        compound=candidate.compound,
                        dose_uM=dose,
                        timepoint_h=candidate.timepoint_h,
                        plate_id=f"AutonomousLoop_Plate_{plate_idx}",
                        day=1,
                        operator="Autonomous_Agent",
                        is_sentinel=False
                    ))
                    well_idx += 1

            # Control wells (split between DMSO and sentinels)
            dmso_controls = num_controls // 2
            sentinel_controls = num_controls - dmso_controls

            for i in range(dmso_controls):
                wells.append(WellAssignment(
                    well_id=f"W{well_idx+1:03d}",
                    cell_line=candidate.cell_line,
                    compound='DMSO',
                    dose_uM=0.0,
                    timepoint_h=candidate.timepoint_h,
                    plate_id=f"AutonomousLoop_Plate_{plate_idx}",
                    day=1,
                    operator="Autonomous_Agent",
                    is_sentinel=True
                ))
                well_idx += 1

            for i in range(sentinel_controls):
                wells.append(WellAssignment(
                    well_id=f"W{well_idx+1:03d}",
                    cell_line=candidate.cell_line,
                    compound=candidate.compound,
                    dose_uM=ec50,
                    timepoint_h=candidate.timepoint_h,
                    plate_id=f"AutonomousLoop_Plate_{plate_idx}",
                    day=1,
                    operator="Autonomous_Agent",
                    is_sentinel=True
                ))
                well_idx += 1

            # Move to next plate every 96 wells
            if well_idx >= plate_idx * 96:
                plate_idx += 1

        # Progress callback
        total_wells = len(wells)
        def progress_callback(completed: int, total: int, well_id: str = None):
            if well_id and well_id not in running_simulations[design_id]["progress"]["completed_wells"]:
                running_simulations[design_id]["progress"]["completed_wells"].append(well_id)
            running_simulations[design_id]["progress"]["completed"] = completed
            running_simulations[design_id]["progress"]["total"] = total
            running_simulations[design_id]["progress"]["percentage"] = int((completed / total) * 100)
            running_simulations[design_id]["progress"]["last_well"] = well_id

        agent.progress_callback = progress_callback

        # Execute wells
        results = []
        for idx, well in enumerate(wells, 1):
            result = agent._execute_well(well)
            if result:
                results.append(result)
                db.insert_results_batch([result])
            progress_callback(idx, total_wells, well.well_id)

        # Mark complete
        running_simulations[design_id]["status"] = "completed"
        running_simulations[design_id]["progress"]["percentage"] = 100

        logger.info(f"✓ Autonomous loop portfolio complete! Design ID: {design_id}, Wells: {total_wells}")

    except Exception as e:
        logger.error(f"Autonomous loop failed: {e}")
        running_simulations[design_id]["status"] = "failed"
        running_simulations[design_id]["error"] = str(e)


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


@app.get("/api/thalamus/designs/{design_id}/pca")
async def get_pca_data(design_id: str, channels: Optional[str] = None):
    """
    Compute real PCA on morphology data with optional channel selection.

    Args:
        design_id: Design ID
        channels: Comma-separated channel names (e.g., "er,mito,rna"). Defaults to all 5.

    Returns:
        PC scores, loadings, variance explained, and well metadata
    """
    try:
        from sklearn.decomposition import PCA
        import numpy as np

        db = CellThalamusDB(db_path=DB_PATH)
        results = db.get_results(design_id)

        if not results:
            db.close()
            raise HTTPException(status_code=404, detail="No results found")

        # All available channels in order
        all_channels = ['er', 'mito', 'nucleus', 'actin', 'rna']
        channel_map = {
            'er': 'morph_er',
            'mito': 'morph_mito',
            'nucleus': 'morph_nucleus',
            'actin': 'morph_actin',
            'rna': 'morph_rna'
        }

        # Parse selected channels
        if channels:
            selected_channels = [c.strip().lower() for c in channels.split(',')]
            # Validate channels
            selected_channels = [c for c in selected_channels if c in all_channels]
            if not selected_channels:
                selected_channels = all_channels
        else:
            selected_channels = all_channels

        # Extract morphology matrix for selected channels
        matrix = []
        well_metadata = []

        for result in results:
            # Get values for selected channels
            values = [result[channel_map[ch]] for ch in selected_channels]

            # Skip if any values are None
            if None in values:
                continue

            matrix.append(values)
            well_metadata.append({
                'well_id': result['well_id'],
                'cell_line': result['cell_line'],
                'compound': result['compound'],
                'dose_uM': result['dose_uM'],
                'timepoint_h': result['timepoint_h'],
                'is_sentinel': result['is_sentinel']
            })

        db.close()

        if len(matrix) < 2:
            raise HTTPException(status_code=400, detail="Not enough data points for PCA")

        # Convert to numpy array
        X = np.array(matrix, dtype=float)

        # Compute PCA (2 components)
        pca = PCA(n_components=2)
        pc_scores = pca.fit_transform(X)

        # Get loadings (eigenvectors)
        loadings = pca.components_.T  # Shape: (n_channels, 2)

        # Variance explained
        variance_explained = pca.explained_variance_ratio_

        return {
            'pc_scores': pc_scores.tolist(),  # List of [PC1, PC2] for each well
            'loadings': loadings.tolist(),    # List of [PC1_loading, PC2_loading] for each channel
            'variance_explained': {
                'pc1': float(variance_explained[0]),
                'pc2': float(variance_explained[1]),
                'total': float(variance_explained[0] + variance_explained[1])
            },
            'channels': selected_channels,
            'well_metadata': well_metadata,
            'n_wells': len(well_metadata)
        }

    except Exception as e:
        logger.error(f"Error computing PCA: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/thalamus/designs/{design_id}/dose-response")
async def get_dose_response(design_id: str, compound: str, cell_line: str, metric: str = "atp_signal", timepoint: Optional[float] = None):
    """Get dose-response data for a specific compound/cell line with error bars"""
    try:
        db = CellThalamusDB(db_path=DB_PATH)
        data = db.get_dose_response_data(design_id, compound, cell_line, metric, timepoint)
        db.close()

        if not data:
            raise HTTPException(status_code=404, detail="No dose-response data found")

        # Convert to dict format with mean, std, n
        return {
            "doses": [d[0] for d in data],
            "values": [d[1] for d in data],  # mean
            "std": [d[2] for d in data],     # standard deviation
            "n": [d[3] for d in data],       # sample size
            "compound": compound,
            "cell_line": cell_line,
            "metric": metric
        }

    except Exception as e:
        logger.error(f"Error getting dose-response: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/thalamus/designs/{design_id}/variance")
async def get_variance_analysis(design_id: str, metric: str = None):
    """Perform variance analysis"""
    try:
        db = CellThalamusDB(db_path=DB_PATH)
        analyzer = VarianceAnalyzer(db)
        raw_analysis = analyzer.analyze_design(design_id)
        db.close()

        if "error" in raw_analysis:
            raise HTTPException(status_code=404, detail=raw_analysis["error"])

        # Helper function to convert numpy types to Python native types
        def to_native(val):
            if hasattr(val, 'item'):
                return val.item()
            return float(val) if isinstance(val, (int, float)) else val

        # If no metric specified, return all metrics for heatmap
        if metric is None:
            all_metrics = {}
            for metric_name, components_data in raw_analysis['variance_components'].items():
                metric_components = []
                for source, variance in components_data['components'].items():
                    total_var = components_data['total_variance']
                    fraction = variance / total_var if total_var > 0 else 0
                    metric_components.append({
                        'source': source,
                        'variance': to_native(variance),
                        'fraction': to_native(fraction)
                    })

                # Add residual
                metric_components.append({
                    'source': 'residual',
                    'variance': to_native(components_data['residual_variance']),
                    'fraction': to_native(components_data['residual_fraction'])
                })

                all_metrics[metric_name] = {
                    'components': metric_components,
                    'total_variance': to_native(components_data['total_variance'])
                }

            # Convert summary to native types
            summary = raw_analysis['summary']
            safe_summary = {
                'biological_fraction_mean': to_native(summary['biological_fraction_mean']),
                'technical_fraction_mean': to_native(summary['technical_fraction_mean']),
                'criteria': {
                    'biological_dominance': {
                        'pass': bool(summary['criteria']['biological_dominance']['pass'])
                    },
                    'technical_control': {
                        'pass': bool(summary['criteria']['technical_control']['pass'])
                    },
                    'sentinel_stability': {
                        'pass': bool(summary['criteria']['sentinel_stability']['pass'])
                    }
                }
            }

            return {
                'all_metrics': all_metrics,
                'summary': safe_summary
            }

        # Single metric request - existing logic
        atp_components = raw_analysis['variance_components'][metric]
        summary = raw_analysis['summary']
        spc = raw_analysis['spc_results']

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
            'metric': metric,
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


@app.get("/api/thalamus/designs/{design_id}/morphology-variance")
async def get_morphology_variance_analysis(design_id: str):
    """
    Analyze morphology variance for autonomous loop candidate ranking (Phase 1).

    This replaces entropy/CV-based ranking with morphology covariance analysis:
    - Per-condition scatter in PC space (tr(Σ_c))
    - Nuisance variance decomposition (plate/day/operator effects)
    - Priority scoring: high variance, non-death, low nuisance

    Returns ranked conditions and global diagnostics.
    """
    try:
        from cell_os.cell_thalamus.morphology_variance_analysis import rank_conditions_for_autonomous_loop

        # Get results for this design
        db = CellThalamusDB(db_path=DB_PATH)
        results = db.get_results(design_id)
        db.close()

        if not results:
            raise HTTPException(status_code=404, detail="No results found")

        # Run morphology variance analysis
        candidates, diagnostics = rank_conditions_for_autonomous_loop(
            results=results,
            design_id=design_id,
            top_k=15
        )

        return {
            'candidates': candidates,
            'diagnostics': diagnostics,
            'design_id': design_id,
            'analysis_type': 'morphology_covariance',
        }

    except Exception as e:
        logger.error(f"Error in morphology variance analysis: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/thalamus/designs/{design_id}/boundaries")
async def get_boundary_analysis(
    design_id: str,
    boundary_type: str = "death",
    timepoint_h: Optional[float] = None,
    chart_id: Optional[str] = None
):
    """
    Phase 2: Boundary detection with manifold chart capability gating.

    This endpoint now enforces architectural constraints:
    - Mechanism-axis boundaries require geometry_preservation >= 0.90
    - Charts are first-class coordinate systems with explicit capabilities
    - Requests for disallowed boundary types return hard errors (not warnings)

    Args:
        design_id: Design to analyze
        boundary_type: "death" or "mechanism_axis"
        timepoint_h: Optional timepoint filter (creates chart per timepoint)
        chart_id: Optional chart ID (overrides timepoint_h if provided)

    Returns:
        {
            "charts": List of available charts with health + capabilities,
            "selected_chart": Chart used for this analysis (if boundary succeeded),
            "boundary_conditions": Conditions near decision boundary (if allowed),
            "error": Structured error if boundary type not allowed on chart
        }
    """
    try:
        # Get results
        db = CellThalamusDB(db_path=DB_PATH)
        results = db.get_results(design_id)
        db.close()

        if not results:
            raise HTTPException(status_code=404, detail="No results found")

        # Parse boundary type
        try:
            requested_boundary = BoundaryType(boundary_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid boundary_type: {boundary_type}. Must be one of: {[bt.value for bt in BoundaryType]}"
            )

        # Group results by timepoint
        timepoint_results = {}
        for r in results:
            tp = r.get('timepoint_h', 0.0)
            if tp not in timepoint_results:
                timepoint_results[tp] = []
            timepoint_results[tp].append(r)

        logger.info(f"Found {len(timepoint_results)} unique timepoints: {sorted(timepoint_results.keys())}")

        # Define standard sentinel specs
        sentinel_specs = [
            SentinelSpec(name="vehicle", cell_line="A549", compound="DMSO", dose_uM=0.0),
            SentinelSpec(name="ER", cell_line="A549", compound="thapsigargin", dose_uM=0.5),
            SentinelSpec(name="mito", cell_line="A549", compound="oligomycin", dose_uM=1.0),
            SentinelSpec(name="proteostasis", cell_line="A549", compound="MG132", dose_uM=1.0),
            SentinelSpec(name="oxidative", cell_line="A549", compound="tBHQ", dose_uM=30.0),
        ]

        # Analyze each timepoint separately and create charts
        charts = []
        for tp, tp_results in sorted(timepoint_results.items()):
            logger.info(f"Analyzing timepoint {tp}h ({len(tp_results)} wells)")

            # Run boundary analysis for this timepoint only
            analysis = analyze_boundaries(
                results=tp_results,
                design_id=f"{design_id}_T{int(tp):02d}h",
                phase1_metrics={"trajectory_snr": {}, "global_nuisance_fraction": 0.5},
                sentinel_specs=sentinel_specs,
                boundary_type=boundary_type
            )

            # Create chart from integration test
            chart = create_chart_from_integration_test(
                timepoint_h=tp,
                batch_diagnostics=analysis["batch_diagnostics"],
                integration_test=analysis["integration_test"],
                within_scatter=analysis["integration_test"]["within_scatter"]
            )

            charts.append({
                "chart": chart,
                "analysis": analysis
            })

        # Select chart based on user request
        selected_chart = None
        selected_analysis = None

        if chart_id:
            # Find by chart_id
            for c in charts:
                if c["chart"].chart_id == chart_id:
                    selected_chart = c["chart"]
                    selected_analysis = c["analysis"]
                    break
            if not selected_chart:
                raise HTTPException(
                    status_code=404,
                    detail=f"Chart {chart_id} not found. Available charts: {[c['chart'].chart_id for c in charts]}"
                )
        elif timepoint_h is not None:
            # Find by timepoint
            for c in charts:
                if c["chart"].timepoint_h == timepoint_h:
                    selected_chart = c["chart"]
                    selected_analysis = c["analysis"]
                    break
            if not selected_chart:
                raise HTTPException(
                    status_code=404,
                    detail=f"No chart found for timepoint {timepoint_h}h"
                )
        else:
            # Auto-select: prefer PASS charts, then earliest CONDITIONAL
            pass_charts = [c for c in charts if c["chart"].status == ChartStatus.PASS]
            if pass_charts:
                selected_chart = pass_charts[0]["chart"]
                selected_analysis = pass_charts[0]["analysis"]
            else:
                conditional_charts = [c for c in charts if c["chart"].status == ChartStatus.CONDITIONAL]
                if conditional_charts:
                    selected_chart = conditional_charts[0]["chart"]
                    selected_analysis = conditional_charts[0]["analysis"]
                else:
                    # All failed - return error with chart health
                    return {
                        "error": {
                            "code": "ALL_CHARTS_FAILED",
                            "message": "All timepoint charts failed integration tests",
                            "details": {
                                "charts": [{
                                    "chart_id": c["chart"].chart_id,
                                    "timepoint_h": c["chart"].timepoint_h,
                                    "status": c["chart"].status.value,
                                    "health": {
                                        "geometry_preservation": c["chart"].health.geometry_preservation_median,
                                        "vehicle_drift": c["chart"].health.vehicle_drift_median_normalized
                                    }
                                } for c in charts]
                            },
                            "recommendation": "Run anchor tightening cycle with increased sentinel replicates (8 vehicle + 5 per archetype)"
                        }
                    }

        # Check if requested boundary type is allowed on selected chart
        if not selected_chart.allows_boundary_type(requested_boundary):
            # HARD ERROR - capability violation
            refuse_response = selected_chart.refuse_message(requested_boundary)
            refuse_response["available_charts"] = [{
                "chart_id": c["chart"].chart_id,
                "timepoint_h": c["chart"].timepoint_h,
                "status": c["chart"].status.value,
                "allowed_boundaries": [bt.value for bt in c["chart"].allowed_boundary_types],
                "health": {
                    "geometry_preservation": c["chart"].health.geometry_preservation_median,
                    "sentinel_max_drift": c["chart"].health.sentinel_max_drift_normalized
                }
            } for c in charts]
            return refuse_response

        # Boundary type is allowed - return analysis
        # Get Phase 1 metrics for acquisition planning
        from cell_os.cell_thalamus.morphology_variance_analysis import rank_conditions_for_autonomous_loop
        try:
            _, phase1_diagnostics = rank_conditions_for_autonomous_loop(
                results=timepoint_results[selected_chart.timepoint_h],
                design_id=design_id,
                top_k=15
            )
        except Exception as e:
            logger.warning(f"Could not get Phase 1 metrics: {e}")
            phase1_diagnostics = {
                "trajectory_snr": {},
                "global_nuisance_fraction": 0.5
            }

        # Generate acquisition plan
        anchor_budgeter = AnchorBudgeter(sentinel_specs, reps_per_sentinel=5, vehicle_reps=8)
        boundary_selector = BoundaryBandSelector(mode="entropy")
        planner = AcquisitionPlanner(anchor_budgeter, boundary_selector)

        boundary_scores = {
            (cond["cell_line"], cond["compound"], cond["dose_uM"], cond["timepoint"]): 1.0
            for cond in selected_analysis["boundary_conditions"]
        }

        acquisition_plan = planner.plan(
            candidate_conditions=list(boundary_scores.keys()),
            phase1_metrics=phase1_diagnostics,
            boundary_scores=boundary_scores,
            plate_format=96,
            batch_id=f"anchor_tightening_{design_id[:8]}_T{int(selected_chart.timepoint_h):02d}h",
            policy={"boundary_frac": 0.6, "trajectory_frac": 0.4, "sentinel_frac": 0.31}
        )

        return {
            "design_id": design_id,
            "charts": [{
                "chart_id": c["chart"].chart_id,
                "timepoint_h": c["chart"].timepoint_h,
                "status": c["chart"].status.value,
                "chart_type": c["chart"].chart_type,
                "allowed_boundaries": [bt.value for bt in c["chart"].allowed_boundary_types],
                "health": {
                    "geometry_preservation_median": c["chart"].health.geometry_preservation_median,
                    "geometry_preservation_min": c["chart"].health.geometry_preservation_min,
                    "sentinel_max_drift": c["chart"].health.sentinel_max_drift_normalized,
                    "vehicle_drift_median": c["chart"].health.vehicle_drift_median_normalized,
                    "n_batches": c["chart"].health.n_batches
                },
                "notes": c["chart"].notes
            } for c in charts],
            "selected_chart": {
                "chart_id": selected_chart.chart_id,
                "timepoint_h": selected_chart.timepoint_h,
                "status": selected_chart.status.value,
                "chart_type": selected_chart.chart_type
            },
            "boundary_type": boundary_type,
            "boundary_conditions": selected_analysis["boundary_conditions"],
            "batch_diagnostics": selected_analysis["batch_diagnostics"],
            "integration_test": selected_analysis["integration_test"],
            "acquisition_plan": acquisition_plan,
            "model_fitted": selected_analysis["model_fitted"],
            "phase": "Phase2_BoundaryDetection",
            "model_version": "phase2_v2.0_chart_gating",
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in boundary analysis: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/thalamus/designs/{design_id}/sentinels")
async def get_sentinel_data(design_id: str):
    """Get sentinel SPC data"""
    try:
        import numpy as np
        from collections import defaultdict

        db = CellThalamusDB(db_path=DB_PATH)
        sentinel_wells = db.get_sentinel_data(design_id)
        db.close()

        if not sentinel_wells:
            raise HTTPException(status_code=404, detail="No sentinel data found")

        # Group sentinels by compound and cell line
        grouped = defaultdict(list)
        for well in sentinel_wells:
            key = f"{well['compound']} ({well['cell_line']})"
            grouped[key].append(well)

        # Calculate SPC statistics for each sentinel type and metric
        spc_data = []
        metrics = ['atp_signal', 'morph_er', 'morph_mito', 'morph_nucleus', 'morph_actin', 'morph_rna']

        for sentinel_type, wells in grouped.items():
            for metric in metrics:
                # Extract values for this metric
                values = [w[metric] for w in wells if w[metric] is not None]

                if len(values) < 2:
                    continue

                # Calculate statistics
                mean = float(np.mean(values))
                std = float(np.std(values, ddof=1))
                ucl = mean + 3 * std
                lcl = mean - 3 * std

                # Create points with outlier detection
                points = []
                for well in wells:
                    value = well[metric]
                    if value is not None:
                        is_outlier = value > ucl or value < lcl
                        points.append({
                            'plate_id': well['plate_id'],
                            'day': well['day'],
                            'operator': well['operator'],
                            'value': float(value),
                            'is_outlier': bool(is_outlier)
                        })

                spc_data.append({
                    'sentinel_type': sentinel_type,
                    'metric': metric,
                    'mean': mean,
                    'std': std,
                    'ucl': ucl,
                    'lcl': lcl,
                    'points': points
                })

        return spc_data

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


@app.get("/api/thalamus/catalog")
async def get_design_catalog():
    """Get the design catalog with all versions and evolution history"""
    try:
        catalog_path = Path(__file__).parent.parent.parent.parent / "data" / "designs" / "catalog.json"

        if not catalog_path.exists():
            raise HTTPException(status_code=404, detail="Catalog not found")

        with open(catalog_path, 'r') as f:
            catalog = json.load(f)

        return catalog

    except Exception as e:
        logger.error(f"Error getting design catalog: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/thalamus/catalog/designs/{design_id}")
async def get_catalog_design(design_id: str):
    """Get full design file from catalog"""
    try:
        designs_dir = Path(__file__).parent.parent.parent.parent / "data" / "designs"
        catalog_path = designs_dir / "catalog.json"

        if not catalog_path.exists():
            raise HTTPException(status_code=404, detail="Catalog not found")

        # Load catalog to get filename
        with open(catalog_path, 'r') as f:
            catalog = json.load(f)

        # Find design in catalog
        design_entry = None
        for design in catalog['designs']:
            if design['design_id'] == design_id:
                design_entry = design
                break

        if not design_entry:
            raise HTTPException(status_code=404, detail=f"Design {design_id} not found in catalog")

        # Load full design file
        design_file = designs_dir / design_entry['filename']
        if not design_file.exists():
            raise HTTPException(status_code=404, detail=f"Design file {design_entry['filename']} not found")

        with open(design_file, 'r') as f:
            design_data = json.load(f)

        return {
            "catalog_entry": design_entry,
            "design_data": design_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting catalog design: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# S3 Watcher Control Endpoints
# ============================================================================

@app.get("/api/thalamus/watcher/status")
async def get_watcher_status():
    """Check if S3 watcher is running"""
    import subprocess
    try:
        script_path = str(Path(__file__).parent.parent.parent.parent / "scripts" / "watch_s3_db.sh")
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


@app.get("/api/thalamus/designs/{design_id}/mechanism-recovery")
async def get_mechanism_recovery_stats(design_id: str):
    """
    Compute mechanism recovery statistics for a design.

    Returns separation ratios and centroid distances for:
    - All doses mixed (baseline collapse)
    - Mid-dose 12h only (optimal separation)
    - High-dose 48h only (death signature)
    """
    try:
        import numpy as np
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler
        from collections import defaultdict

        db = CellThalamusDB(DB_PATH)

        # EC50 map for dose stratification
        EC50_MAP = {
            'tBHQ': 30.0, 'H2O2': 100.0, 'tunicamycin': 1.0, 'thapsigargin': 0.5,
            'CCCP': 5.0, 'oligomycin': 1.0, 'etoposide': 10.0, 'MG132': 1.0,
            'nocodazole': 0.5, 'paclitaxel': 0.01,
        }

        STRESS_AXES = {
            'tBHQ': 'oxidative', 'H2O2': 'oxidative',
            'tunicamycin': 'er_stress', 'thapsigargin': 'er_stress',
            'CCCP': 'mitochondrial', 'oligomycin': 'mitochondrial',
            'etoposide': 'dna_damage', 'MG132': 'proteasome',
            'nocodazole': 'microtubule', 'paclitaxel': 'microtubule',
        }

        def load_and_filter(dose_filter='all', timepoint_filter=None):
            """Load morphology data with optional dose/timepoint filtering."""
            cursor = db.conn.cursor()
            cursor.execute("""
                SELECT compound, cell_line, timepoint_h, dose_uM,
                       morph_er, morph_mito, morph_nucleus, morph_actin, morph_rna
                FROM thalamus_results
                WHERE design_id = ? AND is_sentinel = 0 AND compound != 'DMSO' AND dose_uM > 0
            """, (design_id,))

            rows = cursor.fetchall()
            data = []
            metadata = []

            for row in rows:
                compound, cell_line, timepoint, dose, er, mito, nucleus, actin, rna = row

                # Timepoint filter
                if timepoint_filter is not None and timepoint != timepoint_filter:
                    continue

                # Dose filter
                ec50 = EC50_MAP.get(compound)
                if ec50 is None:
                    continue

                dose_ratio = dose / ec50

                if dose_filter == 'mid' and not (0.5 <= dose_ratio <= 2.0):
                    continue
                elif dose_filter == 'high' and dose_ratio < 5.0:
                    continue

                stress_axis = STRESS_AXES.get(compound, 'unknown')
                morph_vector = np.array([er, mito, nucleus, actin, rna])

                data.append(morph_vector)
                metadata.append({'stress_axis': stress_axis})

            return np.array(data), metadata

        def compute_separation(X, metadata):
            """Compute PCA and separation ratio."""
            if len(X) < 10:
                return 0.0, 0.0, [], []

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            pca = PCA(n_components=2)
            X_pca = pca.fit_transform(X_scaled)

            # Compute separation ratio
            centroids = defaultdict(lambda: {'pc1': [], 'pc2': []})
            for i, meta in enumerate(metadata):
                stress_axis = meta['stress_axis']
                centroids[stress_axis]['pc1'].append(X_pca[i, 0])
                centroids[stress_axis]['pc2'].append(X_pca[i, 1])

            within_var = 0
            between_var = 0
            global_centroid = X_pca.mean(axis=0)

            for stress_axis, data in centroids.items():
                class_centroid = np.array([np.mean(data['pc1']), np.mean(data['pc2'])])
                between_var += len(data['pc1']) * np.sum((class_centroid - global_centroid)**2)

                for i, meta in enumerate(metadata):
                    if meta['stress_axis'] == stress_axis:
                        point = X_pca[i]
                        within_var += np.sum((point - class_centroid)**2)

            separation_ratio = between_var / (within_var + 1e-9)

            # Compute average pairwise centroid distance
            axes = list(centroids.keys())
            distances = []
            for i, ax1 in enumerate(axes):
                for ax2 in axes[i+1:]:
                    c1 = np.array([np.mean(centroids[ax1]['pc1']), np.mean(centroids[ax1]['pc2'])])
                    c2 = np.array([np.mean(centroids[ax2]['pc1']), np.mean(centroids[ax2]['pc2'])])
                    dist = np.linalg.norm(c1 - c2)
                    distances.append(dist)

            centroid_distance = np.mean(distances) if distances else 0.0

            # Return PCA coordinates for plotting
            pc_scores = X_pca.tolist()

            return separation_ratio, centroid_distance, pc_scores, metadata

        # Compute stats for each condition
        X_all, meta_all = load_and_filter(dose_filter='all')
        sep_all, dist_all, pc_all, pc_meta_all = compute_separation(X_all, meta_all)

        X_mid, meta_mid = load_and_filter(dose_filter='mid', timepoint_filter=12.0)
        sep_mid, dist_mid, pc_mid, pc_meta_mid = compute_separation(X_mid, meta_mid)

        X_high, meta_high = load_and_filter(dose_filter='high', timepoint_filter=48.0)
        sep_high, dist_high, pc_high, pc_meta_high = compute_separation(X_high, meta_high)

        improvement_factor = sep_mid / sep_all if sep_all > 0 else 0.0

        return {
            "all_doses": {
                "separation_ratio": float(sep_all),
                "centroid_distance": float(dist_all),
                "n_wells": len(X_all),
                "pc_scores": pc_all,
                "metadata": [{"stress_axis": m["stress_axis"]} for m in pc_meta_all]
            },
            "mid_dose": {
                "separation_ratio": float(sep_mid),
                "centroid_distance": float(dist_mid),
                "n_wells": len(X_mid),
                "pc_scores": pc_mid,
                "metadata": [{"stress_axis": m["stress_axis"]} for m in pc_meta_mid]
            },
            "high_dose": {
                "separation_ratio": float(sep_high),
                "centroid_distance": float(dist_high),
                "n_wells": len(X_high),
                "pc_scores": pc_high,
                "metadata": [{"stress_axis": m["stress_axis"]} for m in pc_meta_high]
            },
            "improvement_factor": float(improvement_factor)
        }

    except Exception as e:
        logger.error(f"Error computing mechanism recovery stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/thalamus/watcher/start")
async def start_watcher():
    """Start the S3 watcher"""
    import subprocess
    try:
        script_path = str(Path(__file__).parent.parent.parent.parent / "scripts" / "watch_s3_db.sh")
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


@app.post("/api/thalamus/watcher/stop")
async def stop_watcher():
    """Stop the S3 watcher"""
    import subprocess
    try:
        script_path = str(Path(__file__).parent.parent.parent.parent / "scripts" / "watch_s3_db.sh")
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


# ============================================================================
# PHASE 1: EPISTEMIC AGENT ENDPOINTS
# ============================================================================

# Store running epistemic campaigns
running_epistemic_campaigns: Dict[str, Dict[str, Any]] = {}


class EpistemicCampaignRequest(BaseModel):
    """Request to start an epistemic agent campaign."""
    budget: int = 200
    n_iterations: int = 20
    cell_lines: Optional[List[str]] = None
    compounds: Optional[List[str]] = None


@app.post("/api/thalamus/epistemic/start")
async def start_epistemic_campaign(request: EpistemicCampaignRequest, background_tasks: BackgroundTasks):
    """
    Start a Phase 1 epistemic agent campaign.

    The agent will autonomously explore dose/timepoint space to discover
    which conditions maximize mechanistic information content.
    """
    try:
        from cell_os.cell_thalamus.epistemic_agent import EpistemicAgent

        campaign_id = str(uuid.uuid4())

        logger.info(f"Starting epistemic campaign {campaign_id}")
        logger.info(f"  Budget: {request.budget} wells")
        logger.info(f"  Iterations: {request.n_iterations}")

        # Initialize campaign tracking
        running_epistemic_campaigns[campaign_id] = {
            "status": "initializing",
            "budget": request.budget,
            "n_iterations": request.n_iterations,
            "started_at": datetime.now().isoformat(),
            "progress": 0,
            "current_iteration": 0
        }

        # Start campaign in background
        background_tasks.add_task(
            _run_epistemic_campaign_task,
            campaign_id,
            request.budget,
            request.n_iterations
        )

        return {
            "campaign_id": campaign_id,
            "status": "started",
            "budget": request.budget,
            "n_iterations": request.n_iterations
        }

    except Exception as e:
        logger.error(f"Error starting epistemic campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _run_epistemic_campaign_task(campaign_id: str, budget: int, n_iterations: int):
    """Background task to run epistemic agent campaign."""
    try:
        from cell_os.cell_thalamus.epistemic_agent import EpistemicAgent

        # Update status
        running_epistemic_campaigns[campaign_id]["status"] = "running"

        # Initialize agent
        agent = EpistemicAgent(budget=budget)

        # Run campaign with progress updates
        iteration_stats = []

        for iteration in range(n_iterations):
            logger.info(f"Campaign {campaign_id}: Iteration {iteration + 1}/{n_iterations}")

            # Update progress
            running_epistemic_campaigns[campaign_id]["current_iteration"] = iteration + 1
            running_epistemic_campaigns[campaign_id]["progress"] = (iteration + 1) / n_iterations

            # Execute one iteration
            query = agent.acquisition_function()
            result = agent.execute_query(query)

            # Compute current metrics
            if len(agent.results) >= 4:
                from cell_os.cell_thalamus.epistemic_agent import InformationMetrics
                sep_ratio = InformationMetrics.compute_separation_ratio(
                    agent.results, agent.stress_class_map
                )
            else:
                sep_ratio = 0.0

            iteration_stats.append({
                'iteration': iteration + 1,
                'query': str(query),
                'separation_ratio': sep_ratio,
                'budget_remaining': agent.budget_remaining
            })

            # Update campaign status
            running_epistemic_campaigns[campaign_id]["latest_separation_ratio"] = sep_ratio
            running_epistemic_campaigns[campaign_id]["budget_remaining"] = agent.budget_remaining

        # Generate final summary
        summary = agent._generate_summary(iteration_stats)

        # Mark as completed
        running_epistemic_campaigns[campaign_id]["status"] = "completed"
        running_epistemic_campaigns[campaign_id]["summary"] = summary
        running_epistemic_campaigns[campaign_id]["completed_at"] = datetime.now().isoformat()

        logger.info(f"Campaign {campaign_id} completed")
        logger.info(f"  Final separation ratio: {summary['final_separation_ratio']:.3f}")

    except Exception as e:
        logger.error(f"Error in epistemic campaign {campaign_id}: {e}")
        running_epistemic_campaigns[campaign_id]["status"] = "failed"
        running_epistemic_campaigns[campaign_id]["error"] = str(e)


@app.get("/api/thalamus/epistemic/status/{campaign_id}")
async def get_epistemic_campaign_status(campaign_id: str):
    """Get status of a running epistemic campaign."""
    if campaign_id not in running_epistemic_campaigns:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return running_epistemic_campaigns[campaign_id]


@app.get("/api/thalamus/epistemic/campaigns")
async def list_epistemic_campaigns():
    """List all epistemic campaigns (running and completed)."""
    return {
        "campaigns": [
            {
                "campaign_id": cid,
                "status": data["status"],
                "started_at": data.get("started_at"),
                "progress": data.get("progress", 0),
                "current_iteration": data.get("current_iteration", 0),
                "n_iterations": data.get("n_iterations", 0)
            }
            for cid, data in running_epistemic_campaigns.items()
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
