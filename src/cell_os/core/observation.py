"""
Canonical observation types.

Observations are what the World returns after executing an Experiment.
They contain raw well results and link back to the Experiment via fingerprint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .experiment import SpatialLocation, Treatment
from .assay import AssayType


@dataclass(frozen=True)
class RawWellResult:
    """Raw result from a single well.

    This is the concrete, measured output from executing one well.
    No aggregation, no interpretation - just what was measured.

    Fields use canonical types:
    - location: SpatialLocation (concrete, not position_tag)
    - assay: AssayType enum (not string)
    - observation_time_h: explicit time semantics

    readouts can hold arbitrary nested structure (assay-specific).
    """
    location: SpatialLocation
    cell_line: str
    treatment: Treatment
    assay: AssayType
    observation_time_h: float
    readouts: Mapping[str, Any]
    qc: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConditionKey:
    """Canonical axes for aggregating wells into conditions.

    A condition is defined by the canonical observation tuple:
    (when, how, what, where) - but "where" is abstracted to position_class.

    This is used to group RawWellResults that should be aggregated together.
    """
    cell_line: str
    treatment: Treatment
    assay: AssayType
    observation_time_h: float
    position_class: str  # Derived from SpatialLocation, not stored separately


@dataclass(frozen=True)
class Observation:
    """Canonical observation: results from executing an Experiment.

    An Observation links back to the Experiment that produced it via
    experiment_fingerprint. This enables audit and replay.

    Fields:
    - experiment_fingerprint: Links to Experiment (provenance)
    - raw_wells: All measured results (tuple, ordered)
    - conditions: Aggregated summaries (optional, TBD)
    - metadata: Execution context (optional, not part of identity)

    Key properties:
    - Immutable (frozen=True)
    - Links to Experiment (fingerprint)
    - Raw wells preserved (no information loss)
    """
    experiment_fingerprint: str
    raw_wells: tuple[RawWellResult, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    # conditions: Future - aggregated summaries
    # For now, aggregation happens externally
