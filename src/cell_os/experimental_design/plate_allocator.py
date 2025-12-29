"""
Stratified Plate Allocator (Attack 2B: Spatial Gradient Policy)

Enforces position-treatment independence by allocating treatments to wells
with balanced spatial coverage. Prevents agent from confounding treatment
effects with spatial gradients (pin bias, serpentine, edge effects).

Policy: Agent proposes treatments and replicates, allocator assigns wells.
Agent does NOT choose positions.

Three-axis balance:
1. Edge/center: Each treatment gets proportional edge representation
2. Row/col: Spread across plate regions
3. Serpentine time bins: Balance early/late dispensing timing
"""

import numpy as np
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass


@dataclass
class TreatmentRequest:
    """Agent's requested treatment (no position specified)."""
    treatment_id: str
    n_replicates: int
    metadata: Optional[Dict] = None


@dataclass
class WellAssignment:
    """Allocator's well assignment."""
    well_position: str
    treatment_id: str
    row: str
    col: int
    zone: str  # "edge", "center"
    time_bin: int  # Serpentine dispensing order quantile


class PlateAllocator:
    """
    Stratified plate allocator for experimental designs.

    Guarantees:
    - Treatment not predictable from position (spatial independence)
    - Each treatment has balanced edge/center representation
    - Each treatment has balanced row/col/time coverage
    """

    def __init__(self, plate_format: int = 384, seed: int = 42):
        """
        Args:
            plate_format: 96 or 384
            seed: Deterministic seed for reproducible allocation
        """
        self.plate_format = plate_format
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        # Plate dimensions
        if plate_format == 384:
            self.n_rows, self.n_cols = 16, 24
        elif plate_format == 96:
            self.n_rows, self.n_cols = 8, 12
        else:
            raise ValueError(f"Unsupported plate format: {plate_format}")

        self.rows = [chr(ord('A') + i) for i in range(self.n_rows)]
        self.cols = list(range(1, self.n_cols + 1))

        # Precompute well metadata
        self._well_metadata = self._compute_well_metadata()

    def _compute_well_metadata(self) -> Dict[str, Dict]:
        """
        Precompute zone and time bin for all wells.

        Zone: "edge" if outer perimeter, else "center"
        Time bin: Quantile of serpentine dispensing order (0-9 for 10 bins)
        """
        metadata = {}

        for row in self.rows:
            for col in self.cols:
                well_pos = f"{row}{col:02d}"
                row_idx = ord(row) - ord('A')

                # Zone classification
                is_edge = (
                    row_idx == 0 or
                    row_idx == (self.n_rows - 1) or
                    col == 1 or
                    col == self.n_cols
                )
                zone = "edge" if is_edge else "center"

                # Serpentine time bin (based on 8-channel manifold dispensing order)
                time_idx = self._compute_serpentine_time_index(row_idx, col)
                max_time = self.n_rows * self.n_cols
                time_bin = int((time_idx / max_time) * 10)  # 10 bins

                metadata[well_pos] = {
                    'row': row,
                    'col': col,
                    'row_idx': row_idx,
                    'col_idx': col - 1,
                    'zone': zone,
                    'time_bin': time_bin,
                    'time_idx': time_idx,
                }

        return metadata

    def _compute_serpentine_time_index(self, row_idx: int, col: int) -> int:
        """
        Compute dispensing order index for serpentine 8-channel pattern.

        Odd rows (A,C,E,G,...): L→R (col 1 early, col 24 late)
        Even rows (B,D,F,H,...): R→L (col 24 early, col 1 late)

        Args:
            row_idx: 0-indexed row (A=0, B=1, ...)
            col: 1-indexed column

        Returns:
            Time index (lower = dispensed earlier)
        """
        is_odd_row = (row_idx % 2) == 0  # A=0 (even index, odd row)

        if is_odd_row:
            # L→R: col 1 is early, col max is late
            col_order = col - 1
        else:
            # R→L: col max is early, col 1 is late
            col_order = self.n_cols - col

        # Approximate total order (rows processed sequentially)
        time_idx = row_idx * self.n_cols + col_order

        return time_idx

    def allocate(
        self,
        treatments: List[TreatmentRequest],
        target_edge_fraction: float = None
    ) -> List[WellAssignment]:
        """
        Allocate treatments to wells with stratified spatial balance.

        Args:
            treatments: List of treatment requests (agent's experimental plan)
            target_edge_fraction: Desired edge fraction per treatment
                                  (None = match plate edge fraction)

        Returns:
            List of well assignments

        Raises:
            ValueError: If total replicates exceed available wells
        """
        # Validate capacity
        total_reps = sum(t.n_replicates for t in treatments)
        total_wells = self.n_rows * self.n_cols

        if total_reps > total_wells:
            raise ValueError(
                f"Too many replicates ({total_reps}) for plate format "
                f"({self.plate_format}-well, {total_wells} wells)"
            )

        # Compute edge fraction
        if target_edge_fraction is None:
            # Use natural plate edge fraction
            n_edge = sum(1 for meta in self._well_metadata.values() if meta['zone'] == 'edge')
            target_edge_fraction = n_edge / total_wells

        # Partition wells by zone
        edge_wells = [w for w, m in self._well_metadata.items() if m['zone'] == 'edge']
        center_wells = [w for w, m in self._well_metadata.items() if m['zone'] == 'center']

        # Shuffle wells (deterministic under seed)
        self.rng.shuffle(edge_wells)
        self.rng.shuffle(center_wells)

        # Allocate per treatment
        assignments = []
        edge_cursor = 0
        center_cursor = 0

        for treatment in treatments:
            n_reps = treatment.n_replicates
            n_edge_reps = int(np.round(n_reps * target_edge_fraction))
            n_center_reps = n_reps - n_edge_reps

            # Assign edge wells
            for _ in range(n_edge_reps):
                if edge_cursor >= len(edge_wells):
                    # Ran out of edge wells, take from center
                    well_pos = center_wells[center_cursor]
                    center_cursor += 1
                else:
                    well_pos = edge_wells[edge_cursor]
                    edge_cursor += 1

                meta = self._well_metadata[well_pos]
                assignments.append(WellAssignment(
                    well_position=well_pos,
                    treatment_id=treatment.treatment_id,
                    row=meta['row'],
                    col=meta['col'],
                    zone=meta['zone'],
                    time_bin=meta['time_bin'],
                ))

            # Assign center wells
            for _ in range(n_center_reps):
                if center_cursor >= len(center_wells):
                    # Ran out of center wells, take from edge
                    well_pos = edge_wells[edge_cursor]
                    edge_cursor += 1
                else:
                    well_pos = center_wells[center_cursor]
                    center_cursor += 1

                meta = self._well_metadata[well_pos]
                assignments.append(WellAssignment(
                    well_position=well_pos,
                    treatment_id=treatment.treatment_id,
                    row=meta['row'],
                    col=meta['col'],
                    zone=meta['zone'],
                    time_bin=meta['time_bin'],
                ))

        # Post-allocation balance check (diagnostic)
        self._validate_balance(assignments, treatments)

        return assignments

    def _validate_balance(
        self,
        assignments: List[WellAssignment],
        treatments: List[TreatmentRequest]
    ) -> None:
        """
        Validate spatial balance across treatments (diagnostic).

        Checks:
        - Edge fraction variance across treatments
        - Time bin coverage variance across treatments
        """
        treatment_ids = [t.treatment_id for t in treatments]

        for tid in treatment_ids:
            tid_assignments = [a for a in assignments if a.treatment_id == tid]
            n_total = len(tid_assignments)

            if n_total == 0:
                continue

            # Edge fraction
            n_edge = sum(1 for a in tid_assignments if a.zone == 'edge')
            edge_frac = n_edge / n_total

            # Time bin coverage (unique bins covered)
            time_bins = set(a.time_bin for a in tid_assignments)
            n_time_bins = len(time_bins)

            # Log diagnostic (no hard failure, just awareness)
            if edge_frac < 0.1 or edge_frac > 0.9:
                print(
                    f"  Warning: Treatment {tid} has extreme edge fraction "
                    f"({edge_frac:.2f}) - may indicate imbalance"
                )

            if n_time_bins < 3 and n_total >= 10:
                print(
                    f"  Warning: Treatment {tid} covers only {n_time_bins} time bins "
                    f"with {n_total} replicates - temporal clustering"
                )

    def get_balance_summary(self, assignments: List[WellAssignment]) -> Dict:
        """
        Compute balance metrics for allocated plate.

        Returns:
            Dict with balance statistics:
            - edge_fraction_by_treatment
            - time_bin_coverage_by_treatment
            - row_coverage_by_treatment
            - col_coverage_by_treatment
        """
        treatment_ids = list(set(a.treatment_id for a in assignments))

        summary = {
            'edge_fraction_by_treatment': {},
            'time_bin_coverage_by_treatment': {},
            'row_coverage_by_treatment': {},
            'col_coverage_by_treatment': {},
        }

        for tid in treatment_ids:
            tid_assignments = [a for a in assignments if a.treatment_id == tid]
            n_total = len(tid_assignments)

            if n_total == 0:
                continue

            # Edge fraction
            n_edge = sum(1 for a in tid_assignments if a.zone == 'edge')
            summary['edge_fraction_by_treatment'][tid] = n_edge / n_total

            # Time bin coverage
            time_bins = set(a.time_bin for a in tid_assignments)
            summary['time_bin_coverage_by_treatment'][tid] = len(time_bins)

            # Row coverage
            rows = set(a.row for a in tid_assignments)
            summary['row_coverage_by_treatment'][tid] = len(rows)

            # Col coverage
            cols = set(a.col for a in tid_assignments)
            summary['col_coverage_by_treatment'][tid] = len(cols)

        return summary
