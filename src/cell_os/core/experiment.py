"""
Canonical experiment types.

These types define the single source of truth for experimental semantics.
No ambiguity, no synonyms, no hidden assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional
import hashlib
import json

from .assay import AssayType


@dataclass(frozen=True)
class Treatment:
    """Canonical treatment specification.

    A treatment is a compound applied at a specific dose.
    """
    compound: str
    dose_uM: float


@dataclass(frozen=True)
class SpatialLocation:
    """Concrete physical location in a plate.

    This is where a well actually lives in the lab.

    Position abstractions (edge/center) are DERIVED from physical location,
    never stored independently. This prevents round-trip inference.
    """
    plate_id: str
    well_id: str

    @property
    def position_class(self) -> str:
        """Derive position classification from physical location.

        Returns 'edge' if well is on plate perimeter, 'center' otherwise.

        This is a DERIVED property, not stored data. The abstraction is
        computed FROM the concrete location, preventing position_tag round-trips.

        Standard 96-well plate:
        - Edge: rows A/H, columns 01/12
        - Center: all other positions
        """
        if not self.well_id or len(self.well_id) < 2:
            return "unknown"

        row = self.well_id[0].upper()
        try:
            col = int(self.well_id[1:])
        except ValueError:
            return "unknown"

        # Edge detection for 96-well plate
        is_edge_row = row in ['A', 'H']
        is_edge_col = col in [1, 12]

        if is_edge_row or is_edge_col:
            return "edge"
        else:
            return "center"

    def __str__(self) -> str:
        """String representation shows plate and well."""
        return f"{self.plate_id}:{self.well_id}"


@dataclass(frozen=True)
class Well:
    """Canonical well specification.

    A well represents a single experimental unit: cells + treatment + observation.

    Field semantics (CANONICAL - do not reinterpret):

    treatment_start_time_h:
        Hours since universal time origin (t=0) when treatment is applied.
        This is the causal anchor - observations cannot precede this time.
        Defaults to 0.0 (treatment at experiment start).

        Examples:
        - treatment_start_time_h=0.0 means "add compound at experiment start"
        - treatment_start_time_h=24.0 means "add compound 24h after experiment start"

        Invariant: treatment_start_time_h >= 0 (no time travel)

    observation_time_h:
        Hours since universal time origin (t=0) when the assay readout is taken.
        This is when the measurement happens, NOT duration.

        Examples:
        - observation_time_h=24.0 with treatment_start_time_h=0.0
          means "measure 24 hours after adding compound"
        - observation_time_h=48.0 with treatment_start_time_h=24.0
          means "measure 24 hours after adding compound (which was added at t=24h)"

        Invariant: observation_time_h >= treatment_start_time_h (causality)

        NOT:
        - "timepoint" (ambiguous reference point)
        - "time_h" (no semantic meaning)
        - "duration" (could mean treatment duration or observation time)

    assay:
        Canonical AssayType enum (not string).
        Use AssayType.from_string() to normalize legacy strings.

    location:
        Physical position in the lab. Can be None if not yet allocated.
    """
    cell_line: str
    treatment: Treatment
    observation_time_h: float
    assay: AssayType
    treatment_start_time_h: float = 0.0
    location: Optional[SpatialLocation] = None

    def __post_init__(self):
        """Validate temporal causality on Well construction."""
        from .temporal_causality import validate_well_temporal_causality
        validate_well_temporal_causality(self)


@dataclass(frozen=True)
class DesignSpec:
    """Design specification: template + parameters.

    This is what a Decision references - the intent to run a particular
    experiment design (e.g., "dose_response" with specific parameters).

    The compiler expands this into an Experiment by:
    1. Expanding template into Wells
    2. Allocating Well locations based on AllocationPolicy

    Fields:
        template: Template identifier (stable string, not prose)
        params: Template parameters (must be JSON-serializable primitives)
        intent: Optional human-readable intent (for provenance)
    """
    template: str
    params: Mapping[str, Any] = field(default_factory=dict)
    intent: str | None = None

    def __post_init__(self):
        """Validate params are JSON-serializable."""
        try:
            json.dumps(dict(self.params))
        except (TypeError, ValueError) as e:
            raise ValueError(f"DesignSpec.params must be JSON-serializable: {e}")


@dataclass(frozen=True)
class Experiment:
    """Canonical experiment: wells with allocated locations.

    An Experiment is the unit of execution. It contains:
    - Wells with concrete locations (allocated by compiler)
    - Design spec (what decision chose)
    - Capabilities and allocation policy fingerprints (for provenance)
    - Metadata (optional, not included in fingerprint)

    Key properties:
    - Immutable (frozen=True)
    - Fingerprintable (deterministic hash of canonical fields)
    - Wells are ordered (tuple) but fingerprint is order-independent

    The World executes Experiments. It doesn't interpret, allocate, or validate
    scientific quality. It just runs what it's given and measures what happens.
    """
    experiment_id: str | None
    wells: tuple[Well, ...]
    design_spec: DesignSpec
    capabilities_id: str
    allocation_policy_id: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def fingerprint_inputs(self) -> dict:
        """Return stable dict of canonical primitives for fingerprinting.

        The fingerprint includes:
        - Wells (sorted by location for order-independence)
        - Design spec (template + params)
        - Capabilities ID
        - Allocation policy ID

        NOT included:
        - experiment_id (assigned after fingerprinting)
        - metadata (not part of canonical identity)
        - timestamps, paths, run_id (not reproducible)
        """
        # Sort wells by (plate_id, well_id) for order-independence
        sorted_wells = sorted(
            self.wells,
            key=lambda w: (w.location.plate_id, w.location.well_id) if w.location else ("", "")
        )

        wells_data = [
            {
                "cell_line": w.cell_line,
                "compound": w.treatment.compound,
                "dose_uM": w.treatment.dose_uM,
                "observation_time_h": w.observation_time_h,
                "treatment_start_time_h": w.treatment_start_time_h,
                "assay": w.assay.value,  # Enum → string
                "plate_id": w.location.plate_id if w.location else None,
                "well_id": w.location.well_id if w.location else None,
            }
            for w in sorted_wells
        ]

        return {
            "wells": wells_data,
            "design_spec": {
                "template": self.design_spec.template,
                "params": dict(self.design_spec.params),
            },
            "capabilities_id": self.capabilities_id,
            "allocation_policy_id": self.allocation_policy_id,
        }

    def fingerprint(self) -> str:
        """Return SHA-256 fingerprint of experiment.

        Fingerprint is deterministic:
        - Same wells + design + capabilities → same fingerprint
        - Different well order → same fingerprint (sorted by location)
        - Different experiment_id → same fingerprint (ID not included)
        """
        inputs = self.fingerprint_inputs()
        canonical_json = json.dumps(inputs, sort_keys=True)
        return hashlib.sha256(canonical_json.encode()).hexdigest()

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "experiment_id": self.experiment_id,
            "wells": [
                {
                    "cell_line": w.cell_line,
                    "compound": w.treatment.compound,
                    "dose_uM": w.treatment.dose_uM,
                    "observation_time_h": w.observation_time_h,
                    "treatment_start_time_h": w.treatment_start_time_h,
                    "assay": w.assay.value,
                    "plate_id": w.location.plate_id if w.location else None,
                    "well_id": w.location.well_id if w.location else None,
                }
                for w in self.wells
            ],
            "design_spec": {
                "template": self.design_spec.template,
                "params": dict(self.design_spec.params),
                "intent": self.design_spec.intent,
            },
            "capabilities_id": self.capabilities_id,
            "allocation_policy_id": self.allocation_policy_id,
            "metadata": dict(self.metadata),
            "fingerprint": self.fingerprint(),
        }
