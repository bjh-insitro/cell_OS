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

        # Execute all wells
        logger.info("\nExecuting experiments...")
        for well in tqdm(design, desc="Running wells"):
            self._execute_well(well)

        logger.info(f"\n✓ Phase 0 complete! Design ID: {self.design_id}")
        logger.info(f"  Results stored in database: {self.db.db_path}")

        return self.design_id

    def _execute_well(self, well: WellAssignment):
        """Execute a single well: seed, treat, incubate, measure."""
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
        # Cell Painting (morphology)
        painting_result = self.hardware.cell_painting_assay(vessel_id)

        # ATP viability (scalar)
        atp_result = self.hardware.atp_viability_assay(vessel_id)

        # 6. Store results
        if painting_result['status'] == 'success' and atp_result['status'] == 'success':
            self.db.insert_result(
                design_id=self.design_id,
                well_id=well.well_id,
                cell_line=well.cell_line,
                compound=well.compound,
                dose_uM=well.dose_uM,
                timepoint_h=well.timepoint_h,
                plate_id=well.plate_id,
                day=well.day,
                operator=well.operator,
                morphology=painting_result['morphology'],
                atp_signal=atp_result['atp_signal'],
                is_sentinel=well.is_sentinel
            )

        # Clean up vessel to save memory
        if vessel_id in self.hardware.vessel_states:
            del self.hardware.vessel_states[vessel_id]

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

    def run_demo_mode(self) -> str:
        """
        Run ultra-quick demo (1 cell line, 2 compounds, minimal replication).

        Ultra-fast mode for dashboard testing:
        - 1 cell line (A549)
        - 2 compounds
        - 2 doses (vehicle + high)
        - 1 timepoint
        - 1 plate, 1 day, 1 operator
        - Total: ~10 wells (experimental + sentinels)
        - Runtime: ~30 seconds
        """
        logger.info("Running DEMO MODE (ultra-fast)...")

        # Generate minimal design
        from cell_os.cell_thalamus.design_generator import WellAssignment

        cell_line = 'A549'
        compounds = ['tBHQ', 'tunicamycin']
        doses = [0.0, 10.0]  # vehicle and high dose
        timepoint = 12.0
        plate = 1
        day = 1
        operator = 'Demo_Operator'

        # Save minimal design
        self.db.save_design(
            design_id=self.design_id,
            phase=self.phase,
            cell_lines=[cell_line],
            compounds=compounds,
            doses=doses,
            timepoints=[timepoint],
            metadata={'mode': 'demo', 'wells': 'minimal'}
        )

        # Generate wells manually
        wells = []
        well_counter = 0

        for compound in compounds:
            for dose in doses:
                row = chr(65 + (well_counter % 8))
                col = (well_counter // 8) % 12 + 1
                well_id = f"{row}{col:02d}"

                wells.append(WellAssignment(
                    well_id=well_id,
                    cell_line=cell_line,
                    compound=compound,
                    dose_uM=dose,
                    timepoint_h=timepoint,
                    plate_id=f"Demo_Plate_{plate}",
                    day=day,
                    operator=operator,
                    is_sentinel=False
                ))
                well_counter += 1

        # Add 3 sentinels
        wells.append(WellAssignment(
            well_id="A5",
            cell_line=cell_line,
            compound='DMSO',
            dose_uM=0.0,
            timepoint_h=timepoint,
            plate_id=f"Demo_Plate_{plate}",
            day=day,
            operator=operator,
            is_sentinel=True
        ))

        wells.append(WellAssignment(
            well_id="A6",
            cell_line=cell_line,
            compound='tBHQ',
            dose_uM=10.0,
            timepoint_h=timepoint,
            plate_id=f"Demo_Plate_{plate}",
            day=day,
            operator=operator,
            is_sentinel=True
        ))

        wells.append(WellAssignment(
            well_id="A7",
            cell_line=cell_line,
            compound='tunicamycin',
            dose_uM=2.0,
            timepoint_h=timepoint,
            plate_id=f"Demo_Plate_{plate}",
            day=day,
            operator=operator,
            is_sentinel=True
        ))

        logger.info(f"Demo mode: {len(wells)} wells total")

        # Execute wells
        for well in tqdm(wells, desc="Demo wells"):
            self._execute_well(well)

        logger.info(f"\n✓ Demo complete! Design ID: {self.design_id}")

        return self.design_id
