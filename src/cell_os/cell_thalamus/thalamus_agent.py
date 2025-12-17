"""
Cell Thalamus Agent - Orchestrates Phase 0-3 campaigns

The agent generates experimental designs, executes them via the hardware layer,
collects morphology and ATP data, and stores results for variance analysis.
"""

import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from tqdm import tqdm

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.database.cell_thalamus_db import CellThalamusDB
from cell_os.cell_thalamus.design_generator import Phase0Design, WellAssignment

logger = logging.getLogger(__name__)


class CellThalamusAgent:
    """
    Autonomous agent for Cell Thalamus campaigns.

    Phase 0: Chemistry only (validation of rails)
    Phase 1: Chemistry + small KO panel (causal annotation)
    Phase 2: Autonomous loop (active learning sandbox)
    Phase 3: Scale test (more lines, perturbations, modalities)
    """

    def __init__(
        self,
        phase: int = 0,
        hardware: Optional[BiologicalVirtualMachine] = None,
        db: Optional[CellThalamusDB] = None,
        config: Optional[Dict] = None
    ):
        self.phase = phase
        self.hardware = hardware or BiologicalVirtualMachine()
        self.db = db or CellThalamusDB()
        self.config = config or {}

        self.design_generator = Phase0Design()
        self.design_id = str(uuid.uuid4())

        logger.info(f"Cell Thalamus Agent initialized (Phase {phase}, Design {self.design_id})")

    def run_phase_0(self, cell_lines: Optional[List[str]] = None,
                   compounds: Optional[List[str]] = None) -> str:
        """
        Execute Phase 0 campaign: chemistry-only variance validation.

        Args:
            cell_lines: Optional list of cell lines (defaults to A549, HepG2)
            compounds: Optional list of compounds (defaults to all 10)

        Returns:
            design_id for querying results
        """
        logger.info("=" * 60)
        logger.info("CELL THALAMUS PHASE 0 - MEASUREMENT VALIDATION")
        logger.info("=" * 60)

        # Generate experimental design
        design = self.design_generator.generate_full_design(cell_lines, compounds)

        # Get summary
        summary = self.design_generator.get_design_summary()
        logger.info(f"Design Summary:")
        logger.info(f"  Total wells: {summary['total_wells']}")
        logger.info(f"  Experimental wells: {summary['experimental_wells']}")
        logger.info(f"  Sentinel wells: {summary['sentinel_wells']}")
        logger.info(f"  Unique conditions: {summary['unique_conditions']}")
        logger.info(f"  Replicates per condition: {summary['replicates_per_condition']}")

        # Save design to database
        used_cell_lines = cell_lines or ['A549', 'HepG2']
        used_compounds = compounds or list(self.design_generator.params['compounds'].keys())

        self.db.save_design(
            design_id=self.design_id,
            phase=self.phase,
            cell_lines=used_cell_lines,
            compounds=used_compounds,
            doses=[0.0, 0.1, 1.0, 10.0],  # Relative to EC50
            timepoints=[12.0, 48.0],
            metadata={'summary': summary}
        )

        # Execute all wells and save results incrementally for live updates
        logger.info("\nExecuting experiments...")
        results = []
        total_wells = len(design)
        for idx, well in enumerate(tqdm(design, desc="Running wells"), 1):
            result = self._execute_well(well)
            if result:
                results.append(result)
                # Insert result immediately for live updates
                self.db.insert_results_batch([result])

            # Report progress if callback is available
            if hasattr(self, 'progress_callback') and self.progress_callback:
                self.progress_callback(idx, total_wells, well.well_id)

        logger.info(f"Completed {len(results)} wells")

        logger.info(f"\n✓ Phase 0 complete! Design ID: {self.design_id}")
        logger.info(f"  Results stored in database: {self.db.db_path}")

        return self.design_id

    def _execute_well(self, well: WellAssignment) -> Optional[Dict]:
        """Execute a single well: seed, treat, incubate, measure. Returns result dict."""
        vessel_id = f"{well.plate_id}_{well.well_id}"

        # 1. Seed vessel
        initial_count = 5e5  # 500K cells per well
        capacity = 2e6       # 2M max capacity
        self.hardware.seed_vessel(vessel_id, well.cell_line, initial_count, capacity)

        # 2. Incubate for attachment (4 hours)
        self.hardware.advance_time(4.0)

        # 3. Apply compound
        if well.compound != 'DMSO' and well.dose_uM > 0:
            self.hardware.treat_with_compound(vessel_id, well.compound, well.dose_uM)

        # 4. Incubate to timepoint
        remaining_time = well.timepoint_h - 4.0
        if remaining_time > 0:
            self.hardware.advance_time(remaining_time)

        # 5. Run assays
        # Cell Painting (morphology) - pass batch metadata for noise model
        painting_result = self.hardware.cell_painting_assay(
            vessel_id,
            plate_id=well.plate_id,
            day=well.day,
            operator=well.operator,
            well_position=well.well_id
        )

        # ATP viability (scalar) - pass batch metadata for noise model
        atp_result = self.hardware.atp_viability_assay(
            vessel_id,
            plate_id=well.plate_id,
            day=well.day,
            operator=well.operator,
            well_position=well.well_id
        )

        # 6. Clean up vessel to save memory
        if vessel_id in self.hardware.vessel_states:
            del self.hardware.vessel_states[vessel_id]

        # 7. Return result dict for batch insert
        if painting_result['status'] == 'success' and atp_result['status'] == 'success':
            return {
                'design_id': self.design_id,
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
        return None

    def get_results_summary(self, design_id: Optional[str] = None) -> Dict[str, Any]:
        """Get summary of campaign results."""
        design_id = design_id or self.design_id

        results = self.db.get_results(design_id)

        if not results:
            return {"error": "No results found"}

        # Count by type
        total_results = len(results)
        sentinel_results = sum(1 for r in results if r['is_sentinel'])
        experimental_results = total_results - sentinel_results

        # Unique values
        unique_compounds = len(set(r['compound'] for r in results))
        unique_cell_lines = len(set(r['cell_line'] for r in results))

        return {
            'design_id': design_id,
            'total_wells': total_results,
            'experimental_wells': experimental_results,
            'sentinel_wells': sentinel_results,
            'unique_compounds': unique_compounds,
            'unique_cell_lines': unique_cell_lines,
            'database_path': self.db.db_path
        }

    def run_quick_test(self) -> str:
        """
        Run a minimal Phase 0 test (1 cell line, 3 compounds, 1 day).

        Useful for testing the pipeline without running the full design.
        """
        logger.info("Running quick test (minimal Phase 0)...")

        test_cell_lines = ['A549']
        test_compounds = ['tBHQ', 'tunicamycin', 'etoposide']

        return self.run_phase_0(cell_lines=test_cell_lines, compounds=test_compounds)

    def run_benchmark_plate(self) -> str:
        """
        Run exactly 1 full plate (96 wells) for benchmarking.

        Benchmark mode creates a proper 96-well plate:
        - 2 cell lines (A549, HepG2) - 48 wells each
        - 10 compounds (all Phase 0 compounds)
        - 4 doses per compound (vehicle, 0.1x, 1x, 10x EC50)
        - 16 DMSO sentinel wells (8 per cell line)
        - 1 timepoint (12h)
        - Sequential well IDs (A01-H12)
        - Total: 96 wells (80 experimental + 16 sentinels)
        """
        logger.info("Running BENCHMARK MODE (1 full plate)...")
        import time
        from cell_os.cell_thalamus.design_generator import WellAssignment

        start_time = time.time()

        # Get all 10 compounds
        all_compounds = list(self.design_generator.params['compounds'].keys())

        # Create proper 96-well plate layout with ALL 10 compounds
        plate_wells = []
        well_idx = 0
        rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

        # Layout: 2 cell lines × 10 compounds × 4 doses = 80 experimental wells
        # Plus 16 DMSO sentinels (8 per cell line) = 96 total

        for cell_line in ['A549', 'HepG2']:
            # Add experimental wells for all 10 compounds (40 wells per cell line)
            for compound in all_compounds:
                # Get dose parameters for this compound
                compound_params = self.design_generator.params['compounds'][compound]
                ec50 = compound_params['ec50_uM']

                # 4 doses: vehicle, low (0.1x), mid (1x), high (10x EC50)
                doses = [0.0, ec50 * 0.1, ec50 * 1.0, ec50 * 10.0]

                for dose_uM in doses:
                    row = rows[well_idx // 12]
                    col = (well_idx % 12) + 1
                    well_id = f"{row}{col:02d}"

                    plate_wells.append(WellAssignment(
                        well_id=well_id,
                        cell_line=cell_line,
                        compound=compound,
                        dose_uM=dose_uM,
                        timepoint_h=12.0,
                        plate_id='Benchmark_Plate_1',
                        day=1,
                        operator='Benchmark_Op',
                        is_sentinel=False
                    ))
                    well_idx += 1

            # Add 8 DMSO sentinels for this cell line
            for _ in range(8):
                row = rows[well_idx // 12]
                col = (well_idx % 12) + 1
                well_id = f"{row}{col:02d}"

                plate_wells.append(WellAssignment(
                    well_id=well_id,
                    cell_line=cell_line,
                    compound='DMSO',
                    dose_uM=0.0,
                    timepoint_h=12.0,
                    plate_id='Benchmark_Plate_1',
                    day=1,
                    operator='Benchmark_Op',
                    is_sentinel=True
                ))
                well_idx += 1

        # Save design to database
        self.db.save_design(
            design_id=self.design_id,
            phase=self.phase,
            cell_lines=['A549', 'HepG2'],
            compounds=all_compounds + ['DMSO'],
            doses=[0.0, 0.1, 1.0, 10.0],
            timepoints=[12.0],
            metadata={'mode': 'benchmark', 'plate_count': 1}
        )

        logger.info(f"Executing {len(plate_wells)} wells...")

        results = []
        total_wells = len(plate_wells)
        for idx, well in enumerate(plate_wells, 1):
            result = self._execute_well(well)
            if result:
                results.append(result)
                # Insert result immediately for live updates
                self.db.insert_results_batch([result])

            # Report progress if callback is available
            if hasattr(self, 'progress_callback') and self.progress_callback:
                self.progress_callback(idx, total_wells, well.well_id)
                # Add small delay for visualization (100ms per well for larger runs)
                import time
                time.sleep(0.1)

        logger.info(f"Completed {len(results)} wells")

        elapsed = time.time() - start_time
        ms_per_well = (elapsed / len(plate_wells) * 1000) if len(plate_wells) > 0 else 0
        logger.info(f"✓ Benchmark complete! {len(plate_wells)} wells in {elapsed:.2f} seconds ({ms_per_well:.1f} ms/well)")

        return self.design_id

    def run_demo_mode(self) -> str:
        """
        Run realistic demo with tBHQ dose-response.

        Demo mode shows realistic dose-response curve:
        - 1 cell line (A549)
        - 1 compound (tBHQ) + DMSO control
        - 4 doses showing full response curve:
          * 0.1 µM: No effect (~100% viability, no morphology change)
          * 1.0 µM: Mild effect (~90% viability, visible ER stress)
          * 10 µM: Strong effect (~70% viability, strong morphology changes)
          * 100 µM: Toxic (~20% viability, degraded signal)
        - DMSO vehicle control
        - 3 sentinels (DMSO, mild, strong)
        - Total: 8 wells
        - Runtime: ~20 seconds
        """
        logger.info("Running DEMO MODE - tBHQ dose-response...")

        # Generate minimal design
        from cell_os.cell_thalamus.design_generator import WellAssignment

        cell_line = 'A549'
        timepoint = 12.0
        plate = 1
        day = 1
        operator = 'Demo_Operator'

        # Save minimal design
        self.db.save_design(
            design_id=self.design_id,
            phase=self.phase,
            cell_lines=[cell_line],
            compounds=['tBHQ', 'DMSO'],
            doses=[0.0, 0.1, 1.0, 10.0, 100.0],
            timepoints=[timepoint],
            metadata={'mode': 'demo', 'description': 'tBHQ dose-response with sentinels'}
        )

        # Generate wells manually
        wells = []

        # DMSO vehicle control (well A01)
        wells.append(WellAssignment(
            well_id="A01",
            cell_line=cell_line,
            compound='DMSO',
            dose_uM=0.0,
            timepoint_h=timepoint,
            plate_id=f"Demo_Plate_{plate}",
            day=day,
            operator=operator,
            is_sentinel=False
        ))

        # tBHQ dose series (wells A02-A05)
        doses = [0.1, 1.0, 10.0, 100.0]
        for i, dose in enumerate(doses):
            wells.append(WellAssignment(
                well_id=f"A{i+2:02d}",
                cell_line=cell_line,
                compound='tBHQ',
                dose_uM=dose,
                timepoint_h=timepoint,
                plate_id=f"Demo_Plate_{plate}",
                day=day,
                operator=operator,
                is_sentinel=False
            ))

        # Sentinels (wells A06-A08)
        # Sentinel 1: DMSO reference control
        wells.append(WellAssignment(
            well_id="A06",
            cell_line=cell_line,
            compound='DMSO',
            dose_uM=0.0,
            timepoint_h=timepoint,
            plate_id=f"Demo_Plate_{plate}",
            day=day,
            operator=operator,
            is_sentinel=True
        ))

        # Sentinel 2: Mild stress (tBHQ 1 µM)
        wells.append(WellAssignment(
            well_id="A07",
            cell_line=cell_line,
            compound='tBHQ',
            dose_uM=1.0,
            timepoint_h=timepoint,
            plate_id=f"Demo_Plate_{plate}",
            day=day,
            operator=operator,
            is_sentinel=True
        ))

        # Sentinel 3: Strong stress (tBHQ 10 µM)
        wells.append(WellAssignment(
            well_id="A08",
            cell_line=cell_line,
            compound='tBHQ',
            dose_uM=10.0,
            timepoint_h=timepoint,
            plate_id=f"Demo_Plate_{plate}",
            day=day,
            operator=operator,
            is_sentinel=True
        ))

        logger.info(f"Demo mode: {len(wells)} wells total")

        # Execute wells and collect results
        results = []
        total_wells = len(wells)
        for idx, well in enumerate(tqdm(wells, desc="Demo wells"), 1):
            result = self._execute_well(well)
            if result:
                results.append(result)

            # Report progress if callback is available
            if hasattr(self, 'progress_callback') and self.progress_callback:
                self.progress_callback(idx, total_wells, well.well_id)
                # Add small delay for visualization (200ms per well)
                import time
                time.sleep(0.2)

        # Batch insert results
        logger.info(f"Saving {len(results)} results to database...")
        self.db.insert_results_batch(results)

        logger.info(f"\n✓ Demo complete! Design ID: {self.design_id}")

        return self.design_id
