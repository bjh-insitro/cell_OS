"""
Anchor Budgeter - Sentinel Well Allocation

Allocates sentinel wells per batch with spatial distribution
to sample position effects.
"""

from typing import List, Dict
import logging

from .types import SentinelSpec

logger = logging.getLogger(__name__)


class AnchorBudgeter:
    """
    Allocate sentinel wells per batch and place them to sample position effects.

    Layout principle: Spread sentinels across edge/middle/center zones.
    Vehicle gets extra reps (8) as the primary anchor.
    """

    def __init__(
        self,
        sentinel_specs: List[SentinelSpec],
        reps_per_sentinel: int = 5,
        vehicle_reps: int = 8
    ):
        self.sentinel_specs = sentinel_specs
        self.reps_per_sentinel = reps_per_sentinel
        self.vehicle_reps = vehicle_reps

    def allocate(
        self,
        plate_format: int,
        reserved_frac: float,
        batch_id: str
    ) -> Dict:
        """
        Allocate sentinel wells with spatial distribution.

        Args:
            plate_format: Number of wells (96, 384)
            reserved_frac: Fraction of plate reserved for sentinels (e.g., 0.31 for 30%)
            batch_id: Identifier for this batch

        Returns:
            {
                "n_sentinel_wells": int,
                "n_experimental_wells": int,
                "sentinel_wells": list[dict],
                "layout_constraints": dict
            }
        """
        n_sentinel_wells = int(plate_format * reserved_frac)
        n_experimental_wells = plate_format - n_sentinel_wells

        # Each sentinel gets reps_per_sentinel wells
        wells_per_sentinel = self.reps_per_sentinel

        # Adjust if total exceeds budget
        total_sentinel_wells_needed = len(self.sentinel_specs) * wells_per_sentinel
        if total_sentinel_wells_needed > n_sentinel_wells:
            logger.warning(
                f"Sentinel budget ({n_sentinel_wells}) insufficient for "
                f"{len(self.sentinel_specs)} sentinels × {wells_per_sentinel} reps. "
                f"Reducing reps per sentinel."
            )
            wells_per_sentinel = n_sentinel_wells // len(self.sentinel_specs)

        # Allocate sentinel wells with spatial distribution
        # Vehicle gets extra reps (8) as primary anchor
        sentinel_wells = []

        for i, spec in enumerate(self.sentinel_specs):
            # Vehicle gets more reps
            if spec.name == "vehicle":
                n_reps = self.vehicle_reps
            else:
                n_reps = wells_per_sentinel

            # Distribute reps across zones: edge, mid-ring, center
            # For 8 vehicle reps: 2 edge, 2 mid, 4 center
            # For 5 other reps: 1 edge, 2 mid, 2 center
            if n_reps >= 8:
                n_edge = 2
                n_mid = 2
                n_center = n_reps - n_edge - n_mid
            elif n_reps >= 5:
                n_edge = 1
                n_mid = 2
                n_center = n_reps - n_edge - n_mid
            else:
                n_edge = 1
                n_mid = 1
                n_center = n_reps - n_edge - n_mid

            for zone_idx, (zone, zone_count) in enumerate([
                ("edge", n_edge),
                ("mid", n_mid),
                ("center", n_center)
            ]):
                for rep in range(zone_count):
                    sentinel_wells.append({
                        "sentinel_name": spec.name,
                        "cell_line": spec.cell_line,
                        "compound": spec.compound,
                        "dose_uM": spec.dose_uM,
                        "timepoint": spec.timepoint,
                        "zone": zone,
                        "rep": zone_idx * (n_reps // 3) + rep,  # Global rep index
                    })

        # Use any remaining budget for extra vehicle wells (buffer = extra anchor)
        buffer_wells = n_sentinel_wells - len(sentinel_wells)
        if buffer_wells > 0:
            vehicle_spec = next((s for s in self.sentinel_specs if s.name == "vehicle"), None)
            if vehicle_spec:
                for i in range(buffer_wells):
                    sentinel_wells.append({
                        "sentinel_name": "vehicle",
                        "cell_line": vehicle_spec.cell_line,
                        "compound": vehicle_spec.compound,
                        "dose_uM": vehicle_spec.dose_uM,
                        "timepoint": vehicle_spec.timepoint,
                        "zone": "center",  # Extra buffer wells go to center
                        "rep": self.vehicle_reps + i,
                    })

        return {
            "batch_id": batch_id,
            "n_sentinel_wells": len(sentinel_wells),
            "n_experimental_wells": n_experimental_wells,
            "sentinel_wells": sentinel_wells,
            "layout_constraints": {
                "spatial_distribution": "edge_mid_center",
                "reps_per_zone": [n_edge, n_mid, n_center]
            }
        }
