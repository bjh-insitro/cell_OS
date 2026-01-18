"""
Menadione Phase 0 Simulation Runner

Executes the Menadione Phase 0 design through the biological simulation,
mimicking the real-world wet lab workflow:

Protocol Timeline:
    Day -1 (PM): Seed cells (EL406)
        - 24h plates: 2,000 cells/well (target 70-80% confluence at endpoint)
        - 48h plates: 1,000 cells/well (same target, extra doubling time)
        - 50 µL cell suspension per well

    Day 0 (AM): Feed + Dose
        - Feed: EL406 aspirates old medium (~15 µL residual), dispenses 50 µL fresh
        - Dose: Echo acoustic dispenser, immediately after feed
        - Compound in DMSO, final DMSO ~0.1-0.3%
        - Plates return to incubator (STX220)

    Day 1 (24h endpoint) / Day 2 (48h endpoint):
        - Pre-fixation brightfield QC (Spark Cyto)
        - Transfer supernatant to assay plate (CytoTox protease)
        - Fix cells (PFA)
        - Stain: Cell Painting (5-channel) + γ-H2AX antibody
        - Image (Nikon Ti2)

Assays:
    - Cell Painting: 5-channel morphology (Hoechst, Mito, ER, AGP, Phalloidin)
    - CytoTox-Glo: Dead-cell protease activity (AAF-Glo substrate, supernatant, pre-fixation)
    - γ-H2AX: Supplemental IF for DNA damage (fixed cells)

Usage:
    python menadione_phase0_runner.py --workers 8
    python menadione_phase0_runner.py --mode quick  # Single plate for testing
"""

import argparse
import logging
import time
from functools import partial
from multiprocessing import Pool, cpu_count
from typing import Any

from cell_os.cell_thalamus.menadione_phase0_design import (
    MenadionePhase0Design,
    MenadioneWellAssignment,
    create_menadione_design,
)
from cell_os.database.cell_thalamus_db import CellThalamusDB
from cell_os.hardware.assays.supplemental_if import SupplementalIFAssay
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Flag to control per-well logging (set by --quiet)
_QUIET_MODE = False

# Protocol constants
ATTACHMENT_PERIOD_H = 24.0  # 24h attachment (overnight, Day -1 to Day 0)
FEED_VOLUME_UL = 50.0  # Fresh medium volume during feed
SEED_VOLUME_UL = 50.0  # Cell suspension volume during seeding
RESIDUAL_VOLUME_UL = 15.0  # Residual after aspiration (~10-20 µL typical)

# Module-level variable for multiprocessing workers to access noise config
# Set by run_menadione_simulation before spawning workers
_WORKER_BIO_NOISE_CONFIG: dict | None = None

# Seeding densities (cells/well) - differential based on endpoint timepoint
# Target: ~70-80% confluence at endpoint for all timepoints
SEEDING_DENSITY = {
    24.0: 2000,  # 2 doublings to endpoint → ~8,000 cells
    48.0: 1000,  # 3 doublings to endpoint → ~8,000 cells
}


def init_worker(quiet: bool = False, bio_noise_config: dict | None = None):
    """Initialize worker process by pre-loading parameters.

    Args:
        quiet: Suppress verbose logging
        bio_noise_config: Noise configuration from design's variance_model
    """
    import os
    import random
    import time

    global _WORKER_BIO_NOISE_CONFIG
    _WORKER_BIO_NOISE_CONFIG = bio_noise_config

    # Suppress verbose logging from biological_virtual in quiet mode
    if quiet:
        logging.getLogger("cell_os.hardware.biological_virtual").setLevel(logging.ERROR)

    # Stagger worker startup to reduce database contention
    # Random delay 0-0.5s per worker
    time.sleep(random.random() * 0.5)

    # Pre-load parameters once per worker (populates the module-level cache)
    # Noise config comes from design's variance_model, NOT hard-coded here
    BiologicalVirtualMachine(simulation_speed=0, bio_noise_config=bio_noise_config)
    if not quiet:
        noise_status = (
            "enabled" if bio_noise_config and bio_noise_config.get("enabled") else "disabled"
        )
        logger.info(f"Worker {os.getpid()} ready (noise: {noise_status})")


def execute_well(args: tuple[MenadioneWellAssignment, str]) -> dict[str, Any] | None:
    """
    Execute a single well through the simulation, following real-world protocol.

    Protocol steps:
        1. Seed vessel with timepoint-appropriate density
        2. Incubate 24h for attachment (Day -1 → Day 0)
        3. Feed: aspirate old medium, add fresh (EL406)
        4. Dose: add compound (Echo, immediately after feed)
        5. Incubate to endpoint (24h or 48h post-dose)
        6. Pre-fixation brightfield QC (Spark Cyto)
        7. Transfer supernatant for CytoTox protease assay
        8. Fix and stain: Cell Painting + γ-H2AX
        9. Image

    Args:
        args: Tuple of (well_assignment, design_id)

    Returns:
        Result dict for database insertion, or None on error
    """
    import os
    import time

    well, design_id = args
    worker_id = os.getpid()
    start_time = time.time()

    try:
        # Create hardware instance for this worker
        # simulation_speed=0 disables artificial delays for faster batch execution
        # bio_noise_config comes from design's variance_model (set in init_worker)
        hardware = BiologicalVirtualMachine(
            simulation_speed=0, bio_noise_config=_WORKER_BIO_NOISE_CONFIG
        )
        vessel_id = f"{well.plate_id}_{well.well_id}"

        # === Step 1: Seed vessel (Day -1, PM) ===
        # Differential seeding density based on endpoint timepoint
        seeding_density = SEEDING_DENSITY.get(well.timepoint_h, 2000)

        hardware.seed_vessel(
            vessel_id,
            well.cell_line,
            initial_count=seeding_density,
            vessel_type="384-well",
            seeding_instrument="el406_8ch",
        )

        # === Step 2: Incubate for attachment (24h, Day -1 → Day 0) ===
        hardware.advance_time(ATTACHMENT_PERIOD_H)

        # === Step 3: Feed (Day 0, AM) ===
        # EL406 aspirates old medium, dispenses fresh
        # This resets cytotox_released_since_feed (clears accumulated death signal from attachment)
        # So CytoTox at endpoint only reflects death during treatment, not attachment period
        hardware.feed_vessel(vessel_id)

        # === Step 4: Dose (Day 0, immediately after feed) ===
        # Echo acoustic dispenser - contact-free, no artifacts to model
        if well.dose_uM > 0:
            hardware.treat_with_compound(vessel_id, well.compound, well.dose_uM)
        # Note: DMSO vehicle wells (dose_uM = 0) get DMSO from Echo but no compound

        # === Step 5: Incubate to endpoint ===
        # 24h plates: incubate 24h post-dose
        # 48h plates: incubate 48h post-dose (no mid-experiment feed)
        hardware.advance_time(well.timepoint_h)

        # === Step 6: Pre-fixation brightfield QC (Spark Cyto) ===
        # Captures confluence, gross morphology before fixation
        # In simulation, we can extract confluence from vessel state
        vessel = hardware.vessel_states[vessel_id]
        brightfield_confluence = getattr(vessel, "confluence", 0.0)

        # === Step 7: Transfer supernatant for CytoTox-Glo assay ===
        # Supernatant transferred to separate assay plate
        # CytoTox-Glo measures dead-cell protease activity (AAF-Glo substrate)
        # Signal proportional to accumulated dead cells since last media change
        cytotox_result = hardware.cytotox_assay(vessel_id)

        # === Step 8: Fix and stain ===
        # Cell Painting (5-channel morphology)
        painting_result = hardware.cell_painting_assay(vessel_id)

        # γ-H2AX Supplemental IF (if flagged for this well)
        gamma_h2ax_result = None
        if well.run_gamma_h2ax:
            gamma_h2ax_result = hardware.supplemental_if_assay(vessel_id, markers=["gamma_h2ax"])

        # Get ground-truth viability from vessel state
        ground_truth_viability = vessel.viability

        # === Step 9: Build result dict ===
        if painting_result["status"] == "success":
            result = {
                "design_id": design_id,
                "well_id": well.well_id,
                "cell_line": well.cell_line,
                "compound": well.compound,
                "dose_uM": well.dose_uM,
                "timepoint_h": well.timepoint_h,
                "plate_id": well.plate_id,
                "day": well.day,
                "operator": well.operator,
                "is_sentinel": well.is_sentinel,
                # Seeding info
                "seeding_density": seeding_density,
                # Pre-fixation QC
                "brightfield_confluence": brightfield_confluence,
                # CytoTox-Glo assay (supernatant - dead-cell protease release)
                "cytotox_signal": cytotox_result.get("cytotox_signal"),
                "atp_signal": cytotox_result.get("atp_signal"),  # ATP for metabolic state
                # Cell Painting morphology
                "morphology": painting_result["morphology"],
                # Ground truth
                "viability_fraction": ground_truth_viability,
            }

            # Add γ-H2AX if measured
            if gamma_h2ax_result and gamma_h2ax_result["status"] == "success":
                gamma_data = gamma_h2ax_result["markers"].get("gamma_h2ax", {})
                result["gamma_h2ax_intensity"] = gamma_data.get("mean_intensity")
                result["gamma_h2ax_fold_induction"] = gamma_data.get("fold_induction")
                result["gamma_h2ax_pct_positive"] = gamma_data.get("pct_above_vehicle_p95")

            return result

    except Exception as e:
        import traceback

        elapsed = time.time() - start_time
        logger.error(f"✗ Well {well.well_id} FAILED (worker {worker_id}, {elapsed:.1f}s): {e}")
        logger.error(traceback.format_exc())
        return None


def run_menadione_simulation(
    mode: str = "full",
    workers: int | None = None,
    db_path: str = "data/menadione_phase0.db",
    quiet: bool = False,
    variance_mode: str = "realistic",
) -> str:
    """
    Run Menadione Phase 0 simulation.

    Args:
        mode: "full" for complete design, "quick" for single plate test
        workers: Number of parallel workers (defaults to CPU count)
        db_path: Path to output database
        quiet: Suppress per-well logging, show only progress
        variance_mode: Variance model for simulation. One of:
            - "deterministic": No stochastic noise (for debugging/testing)
            - "conservative": Modest CVs with visible error bars
            - "realistic": Production-level variance (default)

    Returns:
        Design ID of the completed simulation
    """
    global _QUIET_MODE, _WORKER_BIO_NOISE_CONFIG
    _QUIET_MODE = quiet

    # Suppress verbose logging from biological_virtual in quiet mode
    if quiet:
        logging.getLogger("cell_os.hardware.biological_virtual").setLevel(logging.ERROR)

    start_time = time.time()

    # Create design - includes variance_model that defines noise behavior
    design = create_menadione_design(variance_mode=variance_mode)
    wells = design.generate_design()

    # Get noise config FROM THE DESIGN - this is the canonical source
    # The design owns the variance policy, the runner just executes it
    # Pass design_id so seed is derived from it (reproducible per-design)
    bio_noise_config = design.variance_model.to_bio_noise_config(design_id=design.design_id)
    _WORKER_BIO_NOISE_CONFIG = bio_noise_config  # For single-threaded mode

    # Filter for quick mode
    if mode == "quick":
        # Just run first plate from passage 1 at 24h
        first_plate = "MEN_Psg1_T24h_P1_Operator_A"
        wells = [w for w in wells if w.plate_id == first_plate]
        logger.info(f"Quick mode: running {len(wells)} wells from {first_plate}")

    logger.info(f"Running {len(wells)} wells with design {design.design_id}")
    summary = design.get_summary()
    logger.info(
        f"Design summary: {summary['experimental_wells']} experimental, {summary['sentinel_wells']} sentinels"
    )
    logger.info(f"γ-H2AX wells: {summary['gamma_h2ax_wells']}")

    # Log variance model from design - critical for understanding output variability
    vm = design.variance_model
    if vm.enabled:
        bio = vm.biology_noise
        logger.info(
            f"Variance model: ENABLED (growth_cv={bio.get('growth_cv', 0)}, "
            f"stress_cv={bio.get('stress_sensitivity_cv', 0)}, "
            f"plate_fraction={bio.get('plate_level_fraction', 0)})"
        )
    else:
        logger.info("Variance model: DISABLED (deterministic simulation)")

    # Log protocol info
    logger.info("Protocol: 24h attachment → Feed → Dose → Incubate to endpoint")
    logger.info(
        f"Seeding densities: 24h plates={SEEDING_DENSITY[24.0]}, 48h plates={SEEDING_DENSITY[48.0]} cells/well"
    )

    # Set up workers
    if workers is None:
        workers = min(cpu_count(), 16)

    # Prepare arguments
    args = [(well, design.design_id) for well in wells]

    # Run in parallel
    logger.info(f"Starting parallel execution with {workers} workers...")

    results = []
    if workers == 1:
        # Single-threaded for debugging
        for arg in args:
            result = execute_well(arg)
            if result:
                results.append(result)
            if len(results) % 10 == 0:
                logger.info(f"Completed {len(results)}/{len(wells)} wells")
    else:
        # Parallel execution with worker initialization
        # The initializer pre-loads parameters once per worker, avoiding
        # database contention when all workers start simultaneously
        # Pass bio_noise_config from design so workers use the same variance model
        if not quiet:
            logger.info("Initializing worker pool (this may take a few seconds)...")
        with Pool(workers, initializer=partial(init_worker, quiet, bio_noise_config)) as pool:
            if not quiet:
                logger.info("Worker pool ready, processing wells...")
            for i, result in enumerate(pool.imap_unordered(execute_well, args)):
                if result:
                    results.append(result)
                # Progress every 10% or every 50 wells, whichever is smaller
                progress_interval = max(1, min(50, len(wells) // 10))
                if (i + 1) % progress_interval == 0 or (i + 1) == len(wells):
                    pct = 100 * (i + 1) / len(wells)
                    logger.info(f"Progress: {i + 1}/{len(wells)} wells ({pct:.0f}%)")

    # Save to database
    logger.info(f"Saving {len(results)} results to {db_path}")
    db = CellThalamusDB(db_path=db_path)

    # Save design metadata - includes variance_model for traceability
    db.save_design(
        design_id=design.design_id,
        phase=0,  # Phase 0 = dose-response calibration
        cell_lines=[design.cell_line],
        compounds=[design.compound, "DMSO"],
        metadata={
            "type": "menadione_phase0",
            "plate_format": 384,
            "passages": design.passages,
            "plates_per_timepoint": design.plates_per_timepoint,
            "operators": design.operators,
            "total_plates": len(design.passages)
            * len(design.timepoints_h)
            * len(design.plates_per_timepoint),
            "well_count": len(wells),
            "template_mapping": design.template_mapping,
            "sentinel_count_per_plate": 64,
            "experimental_wells_per_plate": 318,
            "reps_per_dose_per_plate": 53,
            # Protocol details
            "protocol": {
                "attachment_h": ATTACHMENT_PERIOD_H,
                "seeding_density_24h": SEEDING_DENSITY[24.0],
                "seeding_density_48h": SEEDING_DENSITY[48.0],
                "seed_volume_ul": SEED_VOLUME_UL,
                "feed_volume_ul": FEED_VOLUME_UL,
                "residual_volume_ul": RESIDUAL_VOLUME_UL,
                "seeding_instrument": "EL406",
                "dosing_instrument": "Echo",
                "imaging_instrument": "Nikon Ti2",
                "brightfield_instrument": "Spark Cyto",
            },
            # Variance model - critical for understanding error bars
            # This answers "why do these error bars exist" with "because the design says so"
            "variance_model": design.variance_model.to_dict(),
        },
        doses=design.doses_uM,
        timepoints=design.timepoints_h,
    )

    # Save results using batch insert for efficiency
    db.insert_results_batch(results)

    db.close()

    elapsed = time.time() - start_time
    logger.info(f"Simulation complete in {elapsed:.1f}s")
    logger.info(f"Design ID: {design.design_id}")
    logger.info(f"Results saved to: {db_path}")

    return design.design_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Menadione Phase 0 simulation")
    parser.add_argument(
        "--mode", choices=["full", "quick"], default="quick", help="Simulation mode"
    )
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers")
    parser.add_argument(
        "--db", type=str, default="data/menadione_phase0.db", help="Output database path"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress per-well logging, show only progress"
    )
    parser.add_argument(
        "--variance-mode",
        choices=["deterministic", "conservative", "realistic"],
        default="realistic",
        help="Variance model: deterministic (no noise), conservative, or realistic (default)",
    )

    args = parser.parse_args()

    design_id = run_menadione_simulation(
        mode=args.mode,
        workers=args.workers,
        db_path=args.db,
        quiet=args.quiet,
        variance_mode=args.variance_mode,
    )

    print(f"\n✓ Simulation complete: {design_id}")
