"""
Standalone Cell Thalamus Parallel Runner for AWS/JupyterHub

This is a self-contained script with all compound parameters embedded.
Just upload this file and run it - no dependencies on external YAML files!

Full Mode Specifications:
- 2 cell lines (A549, HepG2)
- 10 compounds (oxidative, ER stress, mitochondrial, DNA damage, proteasome, microtubule)
- 4 doses per compound: vehicle (0×EC50), low (0.1×EC50), mid (1×EC50), high (10×EC50)
  * Each compound uses its own EC50 (e.g., tBHQ: 0, 3, 30, 300 µM; paclitaxel: 0, 0.001, 0.01, 0.1 µM)
- Sentinels per plate: 4 DMSO, 2 tBHQ (10µM), 2 tunicamycin (2µM) × 2 cell lines = 16 total
- 2 timepoints (12h, 48h)
- 2 days, 2 operators, 3 replicates
- Total: 2,304 wells (1,920 experimental + 384 sentinels)
- MATCHES the design_generator.py Full mode exactly!

Usage:
    # Full campaign with 64 workers (~5 minutes on c5.18xlarge)
    python standalone_cell_thalamus.py --mode full --workers 64

    # Quick demo test (4 wells)
    python standalone_cell_thalamus.py --mode demo --workers 4

Requirements (install on AWS/JupyterHub):
    pip install numpy tqdm

Output:
    - SQLite database: cell_thalamus_results.db
    - Compatible with Cell Thalamus React dashboard
"""

import argparse
import time
import logging
import uuid
import sqlite3
import os
from typing import List, Dict, Any, Optional, Tuple
from multiprocessing import Pool, cpu_count
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

import numpy as np
from tqdm import tqdm

logger = logging.getLogger(__name__)


# ============================================================================
# Database Module
# ============================================================================

class CellThalamusDB:
    """Lightweight database for Cell Thalamus results."""

    def __init__(self, db_path: str = "cell_thalamus.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._create_schema()

    def _create_schema(self):
        """Create database tables."""
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS thalamus_designs (
                design_id TEXT PRIMARY KEY,
                phase INTEGER,
                cell_lines TEXT,
                compounds TEXT,
                doses TEXT,
                timepoints TEXT,
                created_at TEXT,
                metadata TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS thalamus_results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                design_id TEXT,
                well_id TEXT,
                cell_line TEXT,
                compound TEXT,
                dose_uM REAL,
                timepoint_h REAL,
                plate_id TEXT,
                day INTEGER,
                operator TEXT,
                is_sentinel INTEGER,
                morph_er REAL,
                morph_mito REAL,
                morph_nucleus REAL,
                morph_actin REAL,
                morph_rna REAL,
                atp_signal REAL,
                timestamp TEXT
            )
        """)

        self.conn.commit()

    def save_design(self, design_id: str, phase: int, cell_lines: List[str],
                   compounds: List[str], metadata: Dict):
        """Save design metadata."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO thalamus_designs (design_id, phase, cell_lines, compounds, doses, timepoints, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (design_id, phase, str(cell_lines), str(compounds),
              str([0.1, 1.0, 10.0, 100.0]), str([12.0, 48.0]),
              datetime.now().isoformat(), str(metadata)))
        self.conn.commit()

    def insert_results_batch(self, results: List[Dict]):
        """Batch insert results."""
        if not results:
            return

        cursor = self.conn.cursor()
        timestamp = datetime.now().isoformat()

        data = []
        for r in results:
            m = r['morphology']
            data.append((
                r['design_id'], r['well_id'], r['cell_line'], r['compound'],
                r['dose_uM'], r['timepoint_h'], r['plate_id'], r['day'],
                r['operator'], r['is_sentinel'],
                m['er'], m['mito'], m['nucleus'], m['actin'], m['rna'],
                r['atp_signal'], timestamp
            ))

        cursor.executemany("""
            INSERT INTO thalamus_results
            (design_id, well_id, cell_line, compound, dose_uM, timepoint_h,
             plate_id, day, operator, is_sentinel,
             morph_er, morph_mito, morph_nucleus, morph_actin, morph_rna,
             atp_signal, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)

        self.conn.commit()
        logger.info(f"Batch inserted {len(results)} results")

    def close(self):
        self.conn.close()


# ============================================================================
# Experimental Design
# ============================================================================

@dataclass
class WellAssignment:
    """Single well assignment."""
    well_id: str
    cell_line: str
    compound: str
    dose_uM: float
    timepoint_h: float
    plate_id: str
    day: int
    operator: str
    is_sentinel: bool


def generate_design(cell_lines: List[str], compounds: List[str],
                   mode: str = "full") -> List[WellAssignment]:
    """Generate experimental design."""

    if mode == "demo":
        # Minimal 4 wells for testing
        design = []
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
        return design

    # Full design with EC50-relative dosing (matching main design_generator.py)
    design = []
    dose_levels = [0.0, 0.1, 1.0, 10.0]  # vehicle, low, mid, high (fractions of EC50)
    timepoints = [12.0, 48.0]  # 2 timepoints
    days = [1, 2]  # 2 days
    operators = ['Operator_A', 'Operator_B']  # 2 operators
    replicates = 3  # 3 biological replicates (plates)

    well_counter = 0

    for day in days:
        for operator in operators:
            for replicate in range(replicates):
                for timepoint in timepoints:
                    plate_id = f"Plate_{replicate+1}_Day{day}_{operator}_T{timepoint}h"

                    # Experimental wells (including vehicle = 0 µM for each compound)
                    for cell_line in cell_lines:
                        for compound in compounds:
                            # Get compound-specific EC50
                            ec50 = COMPOUND_PARAMS[compound]['ec50_uM']

                            for dose_level in dose_levels:
                                # Calculate actual dose: dose_level × EC50
                                dose_uM = dose_level * ec50

                                row = chr(65 + (well_counter % 8))
                                col = (well_counter // 8) % 12 + 1
                                well_id = f"{row}{col:02d}"

                                design.append(WellAssignment(
                                    well_id=well_id,
                                    cell_line=cell_line,
                                    compound=compound,
                                    dose_uM=dose_uM,
                                    timepoint_h=timepoint,
                                    plate_id=plate_id,
                                    day=day,
                                    operator=operator,
                                    is_sentinel=False
                                ))
                                well_counter += 1

                    # Sentinels (matching cell_thalamus_params.yaml sentinel definitions)
                    for cell_line in cell_lines:
                        # DMSO sentinels (4 corner positions)
                        for sentinel_well in ['A01', 'A12', 'H01', 'H12']:
                            design.append(WellAssignment(
                                well_id=sentinel_well,
                                cell_line=cell_line,
                                compound='DMSO',
                                dose_uM=0.0,
                                timepoint_h=timepoint,
                                plate_id=plate_id,
                                day=day,
                                operator=operator,
                                is_sentinel=True
                            ))

                        # Mild stress sentinels (tBHQ 10 µM, 2 positions)
                        for sentinel_well in ['A06', 'H06']:
                            design.append(WellAssignment(
                                well_id=sentinel_well,
                                cell_line=cell_line,
                                compound='tBHQ',
                                dose_uM=10.0,
                                timepoint_h=timepoint,
                                plate_id=plate_id,
                                day=day,
                                operator=operator,
                                is_sentinel=True
                            ))

                        # Strong stress sentinels (tunicamycin 2 µM, 2 positions)
                        for sentinel_well in ['D06', 'E06']:
                            design.append(WellAssignment(
                                well_id=sentinel_well,
                                cell_line=cell_line,
                                compound='tunicamycin',
                                dose_uM=2.0,
                                timepoint_h=timepoint,
                                plate_id=plate_id,
                                day=day,
                                operator=operator,
                                is_sentinel=True
                            ))

    return design


# ============================================================================
# Compound Parameters (embedded from cell_thalamus_params.yaml)
# ============================================================================

COMPOUND_PARAMS = {
    'tBHQ': {'ec50_uM': 30.0, 'hill_slope': 2.0, 'stress_axis': 'oxidative', 'intensity': 0.8},
    'H2O2': {'ec50_uM': 100.0, 'hill_slope': 2.0, 'stress_axis': 'oxidative', 'intensity': 1.2},
    'tbhp': {'ec50_uM': 80.0, 'hill_slope': 2.0, 'stress_axis': 'oxidative', 'intensity': 1.0},
    'tunicamycin': {'ec50_uM': 1.0, 'hill_slope': 2.0, 'stress_axis': 'er_stress', 'intensity': 1.2},
    'thapsigargin': {'ec50_uM': 0.5, 'hill_slope': 2.5, 'stress_axis': 'er_stress', 'intensity': 1.5},
    'CCCP': {'ec50_uM': 5.0, 'hill_slope': 2.0, 'stress_axis': 'mitochondrial', 'intensity': 1.3},
    'oligomycin': {'ec50_uM': 1.0, 'hill_slope': 2.0, 'stress_axis': 'mitochondrial', 'intensity': 1.0},
    'two_deoxy_d_glucose': {'ec50_uM': 1000.0, 'hill_slope': 1.5, 'stress_axis': 'mitochondrial', 'intensity': 0.6},
    'etoposide': {'ec50_uM': 10.0, 'hill_slope': 2.0, 'stress_axis': 'dna_damage', 'intensity': 1.0},
    'cisplatin': {'ec50_uM': 5.0, 'hill_slope': 2.0, 'stress_axis': 'dna_damage', 'intensity': 1.2},
    'doxorubicin': {'ec50_uM': 0.5, 'hill_slope': 2.5, 'stress_axis': 'dna_damage', 'intensity': 1.4},
    'staurosporine': {'ec50_uM': 0.1, 'hill_slope': 3.0, 'stress_axis': 'dna_damage', 'intensity': 1.8},
    'MG132': {'ec50_uM': 1.0, 'hill_slope': 2.0, 'stress_axis': 'proteasome', 'intensity': 1.1},
    'nocodazole': {'ec50_uM': 0.5, 'hill_slope': 2.0, 'stress_axis': 'microtubule', 'intensity': 1.3},
    'paclitaxel': {'ec50_uM': 0.01, 'hill_slope': 2.5, 'stress_axis': 'microtubule', 'intensity': 1.5},
}

STRESS_AXIS_EFFECTS = {
    'oxidative': {'er': 0.3, 'mito': 1.5, 'nucleus': 0.2, 'actin': -0.4, 'rna': 0.1},
    'er_stress': {'er': 2.0, 'mito': 0.5, 'nucleus': 0.3, 'actin': 0.0, 'rna': 0.8},
    'mitochondrial': {'er': 0.4, 'mito': 2.5, 'nucleus': 0.5, 'actin': -0.3, 'rna': 0.2},
    'dna_damage': {'er': 0.1, 'mito': 0.3, 'nucleus': 1.8, 'actin': -0.2, 'rna': 0.6},
    'proteasome': {'er': 1.2, 'mito': 0.4, 'nucleus': 0.7, 'actin': -0.5, 'rna': 1.0},
    'microtubule': {'er': 0.1, 'mito': 0.2, 'nucleus': 0.8, 'actin': -2.0, 'rna': 0.3},
}

# ============================================================================
# Simulation
# ============================================================================

def simulate_well(well: WellAssignment, design_id: str) -> Optional[Dict]:
    """Simulate a single well experiment with realistic compound effects."""

    try:
        # Baseline morphology
        baseline = {
            'A549': {'er': 1.0, 'mito': 1.0, 'nucleus': 1.0, 'actin': 1.0, 'rna': 1.0},
            'HepG2': {'er': 1.2, 'mito': 0.9, 'nucleus': 1.1, 'actin': 0.95, 'rna': 1.05}
        }

        morph = baseline.get(well.cell_line, baseline['A549']).copy()

        # Apply compound effects using proper parameters
        if well.compound in COMPOUND_PARAMS and well.dose_uM > 0:
            params = COMPOUND_PARAMS[well.compound]
            ec50 = params['ec50_uM']
            hill_slope = params['hill_slope']
            intensity = params['intensity']
            stress_axis = params['stress_axis']

            # Hill equation for dose-response
            dose_effect = intensity * (well.dose_uM ** hill_slope) / (ec50 ** hill_slope + well.dose_uM ** hill_slope)

            # Apply stress axis-specific morphology effects
            axis_effects = STRESS_AXIS_EFFECTS.get(stress_axis, {})
            for channel, effect in axis_effects.items():
                morph[channel] *= (1.0 + dose_effect * effect)

        # Add biological noise (15% CV per channel)
        for key in morph:
            morph[key] *= np.random.normal(1.0, 0.15)

        # Add technical noise (plate, day, operator, well effects)
        # These are multiplicative factors - matching biological_virtual.py lines 666-674
        plate_factor = np.random.normal(1.0, 0.08)    # 8% plate-to-plate variation
        day_factor = np.random.normal(1.0, 0.10)      # 10% day-to-day variation
        operator_factor = np.random.normal(1.0, 0.05) # 5% operator variation
        well_factor = np.random.normal(1.0, 0.12)     # 12% well-to-well noise

        total_tech_factor = plate_factor * day_factor * operator_factor * well_factor

        for key in morph:
            morph[key] *= total_tech_factor
            morph[key] = max(0.0, morph[key])  # No negative signals

        # ATP viability using 4-parameter logistic (4PL) curve
        # This matches biological_virtual.py lines 364 and 720-741
        atp_base = 1.0

        # DMSO vehicle control: high viability
        if well.compound == 'DMSO':
            atp_signal = atp_base
        elif well.compound in COMPOUND_PARAMS and well.dose_uM > 0:
            params = COMPOUND_PARAMS[well.compound]
            ic50 = params['ec50_uM']  # Using EC50 as IC50
            hill_slope = params['hill_slope']

            # 4PL dose-response curve (standard pharmacology model)
            # At IC50: viability = 50%, At 10×IC50: viability = ~1%
            viability_effect = 1.0 / (1.0 + (well.dose_uM / ic50) ** hill_slope)
            atp_signal = viability_effect
        else:
            atp_signal = atp_base

        # Add biological noise (15% CV) - matching biological_virtual.py line 725
        atp_signal *= np.random.normal(1.0, 0.15)

        # Add technical noise (same factors as morphology) - matching lines 734-740
        # Note: Using same technical factors to maintain correlation between ATP and morphology
        atp_signal *= total_tech_factor
        atp_signal = max(0.0, atp_signal)

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
            'morphology': morph,
            'atp_signal': atp_signal,
            'is_sentinel': well.is_sentinel
        }

    except Exception as e:
        logger.error(f"Error simulating well {well.well_id}: {e}")
        return None


def worker_function(args) -> Optional[Dict]:
    """Worker function for multiprocessing."""
    well, design_id = args
    return simulate_well(well, design_id)


# ============================================================================
# Main Runner
# ============================================================================

def run_parallel_simulation(
    cell_lines: Optional[List[str]] = None,
    compounds: Optional[List[str]] = None,
    mode: str = "full",
    workers: Optional[int] = None,
    db_path: str = "cell_thalamus_results.db"
) -> str:
    """Run parallel simulation."""

    if workers is None:
        workers = cpu_count()

    design_id = str(uuid.uuid4())

    # Default parameters
    if cell_lines is None:
        cell_lines = ['A549', 'HepG2']
    if compounds is None:
        # Original 10 compounds from Cell Thalamus Phase 0
        compounds = ['tBHQ', 'H2O2', 'tunicamycin', 'thapsigargin', 'CCCP',
                    'oligomycin', 'etoposide', 'MG132', 'nocodazole', 'paclitaxel']

    logger.info("=" * 70)
    logger.info("PARALLEL CELL THALAMUS SIMULATION")
    logger.info("=" * 70)
    logger.info(f"Mode: {mode}")
    logger.info(f"Workers: {workers} CPUs")
    logger.info(f"Design ID: {design_id}")

    # Generate design
    design = generate_design(cell_lines, compounds, mode)

    logger.info(f"Total wells: {len(design)}")
    logger.info(f"Estimated time: {len(design) * 2.9 / workers:.1f} seconds")

    # Save design
    db = CellThalamusDB(db_path=db_path)
    db.save_design(design_id, 0, cell_lines, compounds,
                   {'mode': mode, 'workers': workers})

    # Prepare worker args
    worker_args = [(well, design_id) for well in design]

    # Execute in parallel
    logger.info(f"\nStarting parallel execution with {workers} workers...")
    start_time = time.time()

    with Pool(processes=workers) as pool:
        results = []
        for i, result in enumerate(pool.imap_unordered(worker_function, worker_args), 1):
            if result:
                results.append(result)

            if i % 100 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed
                remaining = (len(design) - i) / rate
                logger.info(f"Progress: {i}/{len(design)} ({i/len(design)*100:.1f}%) - "
                          f"Rate: {rate:.1f} wells/sec - ETA: {remaining:.1f}s")

    elapsed = time.time() - start_time

    # Save results
    logger.info(f"\nSaving {len(results)} results...")
    db.insert_results_batch(results)
    db.close()

    # Statistics
    logger.info("=" * 70)
    logger.info("✓ SIMULATION COMPLETE!")
    logger.info("=" * 70)
    logger.info(f"Total wells: {len(design)}")
    logger.info(f"Successful: {len(results)}")
    logger.info(f"Total time: {elapsed:.2f}s ({elapsed/60:.2f} min)")
    logger.info(f"Per well: {elapsed/len(design):.3f}s")
    logger.info(f"Throughput: {len(design)/elapsed:.1f} wells/sec")
    logger.info(f"Speedup: {len(design) * 2.9 / elapsed:.1f}x")
    logger.info(f"Design ID: {design_id}")
    logger.info(f"Database: {db_path}")
    logger.info("=" * 70)

    return design_id


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Cell Thalamus Parallel Simulation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full campaign with all CPUs
  python standalone_cell_thalamus.py --mode full

  # Use 32 workers
  python standalone_cell_thalamus.py --mode full --workers 32

  # Quick test
  python standalone_cell_thalamus.py --mode demo --workers 4
        """
    )

    parser.add_argument('--mode', choices=['demo', 'full'], default='full')
    parser.add_argument('--workers', type=int, default=None)
    parser.add_argument('--db-path', default='cell_thalamus_results.db')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    design_id = run_parallel_simulation(
        mode=args.mode,
        workers=args.workers,
        db_path=args.db_path
    )

    print(f"\n✓ Complete! Design ID: {design_id}")
    print(f"Results saved to: {args.db_path}")
    print(f"\nNext steps:")
    print(f"1. Download {args.db_path} from your AWS instance")
    print(f"2. Place it in your local data/ directory")
    print(f"3. Open Cell Thalamus dashboard: http://localhost:5173/cell-thalamus")
    print(f"4. Select this run to visualize results across all tabs")


if __name__ == "__main__":
    main()
