"""
Simulation Service

Background tasks for running Cell Thalamus simulations.
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
import numpy as np

from cell_os.cell_thalamus import CellThalamusAgent
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.database.cell_thalamus_db import CellThalamusDB

logger = logging.getLogger(__name__)


def run_simulation_task(
    design_id: str,
    cell_lines: List[str],
    compounds: Optional[List[str]],
    mode: str,
    db_path: str,
    running_simulations: Dict[str, Dict[str, Any]]
):
    """Background task to run the simulation"""
    try:
        hardware = BiologicalVirtualMachine()
        db = CellThalamusDB(db_path=db_path)
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


def run_autonomous_loop_task(
    design_id: str,
    candidates: List,
    db_path: str,
    running_simulations: Dict[str, Dict[str, Any]],
    use_lambda: bool,
    lambda_client=None,
    lambda_function_name: str = None
):
    """Background task to run autonomous loop portfolio experiment"""
    try:
        # Check if Lambda should be used
        if _should_use_lambda(use_lambda, lambda_client, lambda_function_name, design_id, candidates, running_simulations):
            return

        # Run locally
        logger.info(f"💻 Running simulation locally")
        agent, db = _setup_local_simulation(design_id, db_path)

        # Save design to database
        _save_autonomous_loop_design(db, design_id, candidates)

        # Generate wells for all candidates
        wells = _generate_candidate_wells(candidates, _get_compound_params())

        # Execute wells with progress tracking
        _execute_simulation_wells(agent, db, wells, design_id, running_simulations)

        # Mark complete
        running_simulations[design_id]["status"] = "completed"
        running_simulations[design_id]["progress"]["percentage"] = 100
        logger.info(f"✓ Autonomous loop portfolio complete! Design ID: {design_id}, Wells: {len(wells)}")

    except Exception as e:
        logger.error(f"Autonomous loop failed: {e}")
        running_simulations[design_id]["status"] = "failed"
        running_simulations[design_id]["error"] = str(e)


def _should_use_lambda(
    use_lambda: bool,
    lambda_client,
    lambda_function_name: str,
    design_id: str,
    candidates: List,
    running_simulations: Dict
) -> bool:
    """Check if Lambda should be used and invoke if so."""
    if use_lambda and lambda_client:
        from .lambda_service import invoke_lambda_simulation
        logger.info(f"🚀 Invoking Lambda function: {lambda_function_name}")
        invoke_lambda_simulation(design_id, candidates, lambda_client, lambda_function_name, running_simulations)
        return True
    return False


def _setup_local_simulation(design_id: str, db_path: str):
    """Set up hardware, database, and agent for local simulation."""
    hardware = BiologicalVirtualMachine()
    db = CellThalamusDB(db_path=db_path)
    agent = CellThalamusAgent(phase=0, hardware=hardware, db=db)
    agent.design_id = design_id
    return agent, db


def _get_compound_params() -> Dict[str, Dict[str, float]]:
    """Get EC50 values for compounds used in dose spacing."""
    return {
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


def _save_autonomous_loop_design(db: CellThalamusDB, design_id: str, candidates: List):
    """Save autonomous loop design to database."""
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


def _generate_candidate_wells(candidates: List, compound_params: Dict) -> List:
    """Generate well assignments for all candidates."""
    from cell_os.cell_thalamus.design_generator import WellAssignment

    wells = []
    well_idx = 0
    plate_idx = 1

    # Calculate proportional control allocation
    controls_per_candidate = _calculate_control_allocation(candidates)

    for idx, candidate in enumerate(candidates):
        ec50 = compound_params.get(candidate.compound, {'ec50_uM': 10.0})['ec50_uM']
        num_controls = controls_per_candidate[idx]

        candidate_wells, well_idx, plate_idx = _generate_wells_for_candidate(
            candidate, ec50, num_controls, well_idx, plate_idx
        )
        wells.extend(candidate_wells)

    return wells


def _calculate_control_allocation(candidates: List) -> List[int]:
    """Calculate proportional control allocation to hit target."""
    total_experimental = sum(c.wells for c in candidates)
    TARGET_CONTROLS = 32  # 16 per plate × 2 plates

    controls_per_candidate = []
    for c in candidates:
        ctrl = max(4, round((c.wells / total_experimental) * TARGET_CONTROLS))
        controls_per_candidate.append(ctrl)

    # Adjust for rounding to hit exactly target
    total_controls = sum(controls_per_candidate)
    if total_controls != TARGET_CONTROLS:
        controls_per_candidate[0] += (TARGET_CONTROLS - total_controls)

    return controls_per_candidate


def _generate_wells_for_candidate(
    candidate,
    ec50: float,
    num_controls: int,
    well_idx: int,
    plate_idx: int
) -> Tuple[List, int, int]:
    """Generate wells for a single candidate."""
    from cell_os.cell_thalamus.design_generator import WellAssignment

    wells = []
    num_experimental = candidate.wells

    # Determine doses and replicates
    if num_experimental >= 80:
        num_doses = 8
    elif num_experimental >= 60:
        num_doses = 7
    else:
        num_doses = 6

    # Generate log-spaced doses around EC50
    log_doses = np.linspace(np.log10(ec50 * 0.1), np.log10(ec50 * 10), num_doses)
    doses = [10 ** ld for ld in log_doses]

    # Experimental wells
    base_reps = num_experimental // num_doses
    remainder = num_experimental % num_doses

    for dose_idx, dose in enumerate(doses):
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

    # Control wells
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

    return wells, well_idx, plate_idx


def _execute_simulation_wells(
    agent,
    db: CellThalamusDB,
    wells: List,
    design_id: str,
    running_simulations: Dict
):
    """Execute all wells with progress tracking."""
    total_wells = len(wells)

    def progress_callback(completed: int, total: int, well_id: str = None):
        if well_id and well_id not in running_simulations[design_id]["progress"]["completed_wells"]:
            running_simulations[design_id]["progress"]["completed_wells"].append(well_id)
        running_simulations[design_id]["progress"]["completed"] = completed
        running_simulations[design_id]["progress"]["total"] = total
        running_simulations[design_id]["progress"]["percentage"] = int((completed / total) * 100)
        running_simulations[design_id]["progress"]["last_well"] = well_id

    agent.progress_callback = progress_callback

    results = []
    for idx, well in enumerate(wells, 1):
        result = agent._execute_well(well)
        if result:
            results.append(result)
            db.insert_results_batch([result])
        progress_callback(idx, total_wells, well.well_id)
