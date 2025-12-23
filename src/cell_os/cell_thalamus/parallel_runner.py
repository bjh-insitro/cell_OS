"""
Parallel Cell Thalamus Runner

Runs Cell Thalamus simulations using multiprocessing for massive speedup.
Designed for JupyterHub with 16-64 vCPUs.

Example usage on JupyterHub:
    python parallel_runner.py --mode full --workers 64
"""

import argparse
import time
import logging
from typing import List, Dict, Any, Optional
from multiprocessing import Pool, cpu_count
import uuid

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.database.cell_thalamus_db import CellThalamusDB
from cell_os.cell_thalamus.design_generator import Phase0Design, WellAssignment

logger = logging.getLogger(__name__)


def execute_well_worker(args) -> Optional[Dict[str, Any]]:
    """
    Worker function to execute a single well.

    Args:
        args: Tuple of (well, design_id)

    Returns:
        Result dict for database insertion
    """
    well, design_id = args

    # Create hardware instance for this worker
    hardware = BiologicalVirtualMachine()
    vessel_id = f"{well.plate_id}_{well.well_id}"

    try:
        # 1. Seed vessel using database-backed density lookup
        # Cell Thalamus uses 96-well plates (see design_generator.py)
        hardware.seed_vessel(
            vessel_id,
            well.cell_line,
            vessel_type="96-well",
            density_level="NOMINAL"
        )

        # 2. Incubate for attachment
        hardware.advance_time(4.0)

        # 3. Apply compound
        if well.compound != 'DMSO' and well.dose_uM > 0:
            hardware.treat_with_compound(vessel_id, well.compound, well.dose_uM)

        # 4. Incubate to timepoint
        remaining_time = well.timepoint_h - 4.0
        if remaining_time > 0:
            hardware.advance_time(remaining_time)

        # 5. Run assays
        painting_result = hardware.cell_painting_assay(vessel_id)
        atp_result = hardware.atp_viability_assay(vessel_id)

        # 6. Return result dict
        if painting_result['status'] == 'success' and atp_result['status'] == 'success':
            return {
                'design_id': design_id,
                'well_id': well.well_id,
                'cell_line': well.cell_line,
                'compound': well.compound,
                'dose_uM': well.dose_uM,
                'timepoint_h': well.timepoint_h,
                'plate_id': well.plate_id,
                'day': well.day,
                'operator': well.operator,
                'morphology': painting_result['morphology'],
                'atp_signal': atp_result['atp_signal'],
                'is_sentinel': well.is_sentinel
            }
    except Exception as e:
        logger.error(f"Error executing well {well.well_id}: {e}")
        return None


def run_parallel_simulation(
    cell_lines: Optional[List[str]] = None,
    compounds: Optional[List[str]] = None,
    mode: str = "full",
    workers: Optional[int] = None,
    db_path: str = "data/cell_thalamus_parallel.db"
) -> str:
    """
    Run Cell Thalamus simulation in parallel.

    Args:
        cell_lines: List of cell lines (defaults to A549, HepG2)
        compounds: List of compounds (defaults to all 10)
        mode: 'demo', 'quick', or 'full'
        workers: Number of parallel workers (defaults to cpu_count)
        db_path: Database path for results

    Returns:
        design_id
    """
    if workers is None:
        workers = cpu_count()

    design_id = str(uuid.uuid4())

    logger.info("=" * 70)
    logger.info("PARALLEL CELL THALAMUS SIMULATION")
    logger.info("=" * 70)
    logger.info(f"Mode: {mode}")
    logger.info(f"Workers: {workers} CPUs")
    logger.info(f"Design ID: {design_id}")

    # Generate design
    design_generator = Phase0Design()

    if mode == "demo":
        # Minimal design for testing
        design = []
        # Create just a few wells for demo
        for i, compound in enumerate(['tBHQ', 'tunicamycin']):
            for dose in [0.0, 10.0]:
                design.append(WellAssignment(
                    well_id=f"A{i*2+1:02d}",
                    cell_line='A549',
                    compound=compound,
                    dose_uM=dose,
                    timepoint_h=12.0,
                    plate_id="Demo_Plate_1",
                    day=1,
                    operator="Demo",
                    is_sentinel=False
                ))
    elif mode == "quick":
        # Quick test with 3 compounds
        cell_lines = cell_lines or ['A549']
        compounds = ['tBHQ', 'tunicamycin', 'etoposide']
        design = design_generator.generate_full_design(cell_lines, compounds)
    else:
        # Full Phase 0 design
        cell_lines = cell_lines or ['A549', 'HepG2']
        compounds = compounds or list(design_generator.params['compounds'].keys())
        design = design_generator.generate_full_design(cell_lines, compounds)

    logger.info(f"Total wells to execute: {len(design)}")
    logger.info(f"Estimated time: {len(design) * 2.9 / workers:.1f} seconds (~{len(design) * 2.9 / workers / 60:.1f} minutes)")

    # Save design to database
    db = CellThalamusDB(db_path=db_path)
    used_cell_lines = cell_lines or ['A549', 'HepG2']
    used_compounds = compounds or list(design_generator.params['compounds'].keys())

    db.save_design(
        design_id=design_id,
        phase=0,
        cell_lines=used_cell_lines,
        compounds=used_compounds,
        doses=[0.0, 0.1, 1.0, 10.0],
        timepoints=[12.0, 48.0],
        metadata={'mode': mode, 'workers': workers}
    )

    # Prepare worker arguments
    worker_args = [(well, design_id) for well in design]

    # Execute in parallel
    logger.info(f"\nStarting parallel execution with {workers} workers...")
    start_time = time.time()

    with Pool(processes=workers) as pool:
        # Use imap_unordered for better performance (doesn't maintain order)
        results = []
        for i, result in enumerate(pool.imap_unordered(execute_well_worker, worker_args), 1):
            if result:
                results.append(result)

            # Progress update every 100 wells
            if i % 100 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed
                remaining = (len(design) - i) / rate
                logger.info(f"Progress: {i}/{len(design)} wells ({i/len(design)*100:.1f}%) - "
                          f"Rate: {rate:.1f} wells/sec - ETA: {remaining:.1f}s")

    elapsed = time.time() - start_time

    # Batch insert all results
    logger.info(f"\nSaving {len(results)} results to database...")
    db.insert_results_batch(results)
    db.close()

    # Final statistics
    logger.info("=" * 70)
    logger.info("✓ PARALLEL SIMULATION COMPLETE!")
    logger.info("=" * 70)
    logger.info(f"Total wells: {len(design)}")
    logger.info(f"Successful results: {len(results)}")
    logger.info(f"Total time: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
    logger.info(f"Time per well: {elapsed/len(design):.3f} seconds")
    logger.info(f"Throughput: {len(design)/elapsed:.1f} wells/second")
    logger.info(f"Speedup: {len(design) * 2.9 / elapsed:.1f}x vs serial")
    logger.info(f"Design ID: {design_id}")
    logger.info(f"Database: {db_path}")
    logger.info("=" * 70)

    return design_id


def main():
    """CLI entry point for parallel runner."""
    parser = argparse.ArgumentParser(description='Run Cell Thalamus simulation in parallel')
    parser.add_argument('--mode', choices=['demo', 'quick', 'full'], default='full',
                       help='Simulation mode (default: full)')
    parser.add_argument('--workers', type=int, default=None,
                       help='Number of parallel workers (default: auto-detect CPUs)')
    parser.add_argument('--cell-lines', nargs='+', default=None,
                       help='Cell lines to test (default: A549 HepG2)')
    parser.add_argument('--compounds', nargs='+', default=None,
                       help='Compounds to test (default: all 10)')
    parser.add_argument('--db-path', default='data/cell_thalamus_parallel.db',
                       help='Database path (default: data/cell_thalamus_parallel.db)')

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Run simulation
    design_id = run_parallel_simulation(
        cell_lines=args.cell_lines,
        compounds=args.compounds,
        mode=args.mode,
        workers=args.workers,
        db_path=args.db_path
    )

    print(f"\n✓ Simulation complete! Design ID: {design_id}")


if __name__ == "__main__":
    main()
