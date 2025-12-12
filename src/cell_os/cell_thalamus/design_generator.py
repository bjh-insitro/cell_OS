"""
Experimental Design Generator for Cell Thalamus Phase 0

Generates full factorial designs with sentinels for variance partitioning.
"""

import yaml
import itertools
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class WellAssignment:
    """Represents a single well assignment in a plate."""
    well_id: str
    cell_line: str
    compound: str
    dose_uM: float
    timepoint_h: float
    plate_id: str
    day: int
    operator: str
    is_sentinel: bool = False


class Phase0Design:
    """
    Generates Phase 0 experimental designs.

    Phase 0 Design:
    - 2 cell lines (A549, HepG2)
    - 10 compounds
    - 4 doses (vehicle, low, mid, high)
    - 2 timepoints (12h, 48h)
    - 3 plates × 2 days × 2 operators = 12 replicates per condition
    - Sentinels: DMSO, mild stress, strong stress (fixed positions)
    """

    def __init__(self, params_file: Optional[str] = None):
        if params_file is None:
            params_file = Path(__file__).parent.parent.parent.parent / "data" / "cell_thalamus_params.yaml"

        with open(params_file, 'r') as f:
            self.params = yaml.safe_load(f)

    def _calculate_dose(self, compound: str, level: str) -> float:
        """Calculate actual dose based on compound EC50 and dose level."""
        compound_params = self.params['compounds'][compound]
        ec50 = compound_params['ec50_uM']
        dose_grid = self.params['dose_grid']

        if level == 'vehicle':
            return 0.0
        elif level == 'low':
            return ec50 * dose_grid['low']
        elif level == 'mid':
            return ec50 * dose_grid['mid']
        elif level == 'high':
            return ec50 * dose_grid['high']
        else:
            raise ValueError(f"Unknown dose level: {level}")

    def generate_full_design(self, cell_lines: Optional[List[str]] = None,
                            compounds: Optional[List[str]] = None) -> List[WellAssignment]:
        """
        Generate the complete Phase 0 experimental design.

        Args:
            cell_lines: Optional list of cell lines (defaults to A549, HepG2)
            compounds: Optional list of compounds (defaults to all 10)

        Returns:
            List of WellAssignment objects
        """
        if cell_lines is None:
            cell_lines = ['A549', 'HepG2']

        if compounds is None:
            compounds = list(self.params['compounds'].keys())

        dose_levels = ['vehicle', 'low', 'mid', 'high']
        timepoints = [self.params['timepoints']['early'], self.params['timepoints']['late']]
        plates = [1, 2, 3]
        days = [1, 2]
        operators = ['Operator_A', 'Operator_B']

        assignments = []
        well_counter = 0

        # Generate full factorial
        for cell_line, compound, dose_level, timepoint, plate, day, operator in itertools.product(
            cell_lines, compounds, dose_levels, timepoints, plates, days, operators
        ):
            dose_uM = self._calculate_dose(compound, dose_level)

            # Generate well ID (384-well format: A01-P24)
            row = chr(65 + (well_counter % 16))  # A-P (16 rows)
            col = (well_counter // 16) % 24 + 1   # 1-24 (24 columns)
            well_id = f"{row}{col:02d}"

            plate_id = f"Plate_{plate}_Day{day}_{operator}_T{timepoint}h"

            assignment = WellAssignment(
                well_id=well_id,
                cell_line=cell_line,
                compound=compound,
                dose_uM=dose_uM,
                timepoint_h=timepoint,
                plate_id=plate_id,
                day=day,
                operator=operator,
                is_sentinel=False
            )

            assignments.append(assignment)
            well_counter += 1

        # Add sentinels
        sentinel_assignments = self._add_sentinels(cell_lines, timepoints, plates, days, operators)
        assignments.extend(sentinel_assignments)

        return assignments

    def _add_sentinels(self, cell_lines: List[str], timepoints: List[float],
                      plates: List[int], days: List[int], operators: List[str]) -> List[WellAssignment]:
        """Add sentinel wells to every plate."""
        sentinels = []
        sentinel_defs = self.params['sentinels']

        # For each plate/day/operator/timepoint/cell_line combination
        for cell_line, timepoint, plate, day, operator in itertools.product(
            cell_lines, timepoints, plates, days, operators
        ):
            plate_id = f"Plate_{plate}_Day{day}_{operator}_T{timepoint}h"

            # DMSO sentinels
            for well_pos in sentinel_defs['dmso']['well_positions']:
                sentinels.append(WellAssignment(
                    well_id=well_pos,
                    cell_line=cell_line,
                    compound='DMSO',
                    dose_uM=0.0,
                    timepoint_h=timepoint,
                    plate_id=plate_id,
                    day=day,
                    operator=operator,
                    is_sentinel=True
                ))

            # Mild stress sentinels
            for well_pos in sentinel_defs['mild_stress']['well_positions']:
                sentinels.append(WellAssignment(
                    well_id=well_pos,
                    cell_line=cell_line,
                    compound=sentinel_defs['mild_stress']['compound'],
                    dose_uM=sentinel_defs['mild_stress']['dose_uM'],
                    timepoint_h=timepoint,
                    plate_id=plate_id,
                    day=day,
                    operator=operator,
                    is_sentinel=True
                ))

            # Strong stress sentinels
            for well_pos in sentinel_defs['strong_stress']['well_positions']:
                sentinels.append(WellAssignment(
                    well_id=well_pos,
                    cell_line=cell_line,
                    compound=sentinel_defs['strong_stress']['compound'],
                    dose_uM=sentinel_defs['strong_stress']['dose_uM'],
                    timepoint_h=timepoint,
                    plate_id=plate_id,
                    day=day,
                    operator=operator,
                    is_sentinel=True
                ))

        return sentinels

    def generate_plate_layout(self, cell_line: str, timepoint: float,
                             plate: int, day: int, operator: str) -> List[WellAssignment]:
        """
        Generate layout for a single plate.

        Args:
            cell_line: Cell line name
            timepoint: Timepoint in hours
            plate: Plate number
            day: Day number
            operator: Operator name

        Returns:
            List of WellAssignment objects for this plate
        """
        full_design = self.generate_full_design(cell_lines=[cell_line])

        # Filter to this specific plate
        plate_id = f"Plate_{plate}_Day{day}_{operator}_T{timepoint}h"
        plate_wells = [
            w for w in full_design
            if w.plate_id == plate_id and w.cell_line == cell_line and w.timepoint_h == timepoint
        ]

        return plate_wells

    def get_design_summary(self) -> Dict:
        """Get summary statistics of the design."""
        full_design = self.generate_full_design()

        total_wells = len(full_design)
        sentinel_wells = sum(1 for w in full_design if w.is_sentinel)
        experimental_wells = total_wells - sentinel_wells

        unique_conditions = len(set(
            (w.cell_line, w.compound, w.dose_uM, w.timepoint_h)
            for w in full_design
            if not w.is_sentinel
        ))

        return {
            'total_wells': total_wells,
            'sentinel_wells': sentinel_wells,
            'experimental_wells': experimental_wells,
            'unique_conditions': unique_conditions,
            'cell_lines': 2,
            'compounds': 10,
            'doses_per_compound': 4,
            'timepoints': 2,
            'plates': 3,
            'days': 2,
            'operators': 2,
            'replicates_per_condition': experimental_wells // unique_conditions
        }
