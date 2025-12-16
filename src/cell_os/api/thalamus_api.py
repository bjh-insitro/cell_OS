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

# Database path - use absolute path to work from any directory
DB_PATH = str(Path(__file__).parent.parent.parent.parent / "data" / "cell_thalamus.db")


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


def _run_autonomous_loop_task(design_id: str, candidates: List):
    """Background task to run autonomous loop portfolio experiment"""
    try:
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

        # Calculate proportional control allocation to hit exactly 64 controls
        total_experimental = sum(c.wells for c in candidates)
        TARGET_CONTROLS = 64  # 16 per plate × 4 plates

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
