"""
Canonical capabilities types.

Capabilities define what the experimental system can do.
They're used by the compiler to expand DesignSpec into Experiment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
import hashlib
import json

from .assay import AssayType


@dataclass(frozen=True)
class PlateGeometry:
    """Plate geometry: rows, columns, well identifiers.

    Provides edge detection for position classification.
    """
    rows: int
    cols: int
    well_ids: tuple[str, ...]  # All valid well IDs

    def is_edge(self, well_id: str) -> bool:
        """Check if well is on plate perimeter (edge).

        For standard 96-well plate:
        - Edge: rows A/H, columns 01/12
        - Center: all other positions
        """
        if not well_id or len(well_id) < 2:
            return False

        row = well_id[0].upper()
        try:
            col = int(well_id[1:])
        except ValueError:
            return False

        # Edge detection (assumes standard plate layout)
        is_edge_row = row in ['A', chr(ord('A') + self.rows - 1)]  # First/last row
        is_edge_col = col in [1, self.cols]  # First/last column

        return is_edge_row or is_edge_col

    @classmethod
    def standard_96_well(cls) -> PlateGeometry:
        """Create standard 96-well plate geometry."""
        rows = 8
        cols = 12
        well_ids = tuple(
            f"{chr(ord('A') + r)}{c:02d}"
            for r in range(rows)
            for c in range(1, cols + 1)
        )
        return cls(rows=rows, cols=cols, well_ids=well_ids)


@dataclass(frozen=True)
class Capabilities:
    """System capabilities: what experiments can be run.

    Defines:
    - Plate geometry (wells available)
    - Supported assays (what can be measured)
    - (Future) Cost models, timepoint constraints, etc.

    Used by compiler to validate and expand DesignSpec.
    """
    geometry: PlateGeometry
    supported_assays: frozenset[AssayType]
    # Future: max_wells_per_experiment, cost_model, etc.

    def fingerprint(self) -> str:
        """Return SHA-256 fingerprint of capabilities.

        Fingerprint includes geometry and supported assays.
        Used to track which capabilities were used to compile an Experiment.
        """
        inputs = {
            "geometry": {
                "rows": self.geometry.rows,
                "cols": self.geometry.cols,
            },
            "supported_assays": sorted([a.value for a in self.supported_assays]),
        }
        canonical_json = json.dumps(inputs, sort_keys=True)
        return hashlib.sha256(canonical_json.encode()).hexdigest()


@dataclass(frozen=True)
class AllocationPolicy:
    """Well allocation policy: how to map abstract positions to concrete wells.

    The compiler uses this to allocate well locations when expanding DesignSpec.

    Examples:
    - "sequential": Fill wells in order (A01, A02, ...)
    - "random": Random allocation with seed
    - "stratified": Balance edge/center across treatments
    """
    policy_id: str
    params: Mapping[str, Any] = field(default_factory=dict)

    def fingerprint(self) -> str:
        """Return SHA-256 fingerprint of allocation policy.

        Fingerprint includes policy_id and params.
        Used to track which allocation was used for an Experiment.
        """
        inputs = {
            "policy_id": self.policy_id,
            "params": dict(self.params),
        }
        canonical_json = json.dumps(inputs, sort_keys=True)
        return hashlib.sha256(canonical_json.encode()).hexdigest()
