"""
Legacy adapters: Convert old types to canonical Well.

These adapters exist in exactly ONE place to prevent translation proliferation.
Each adapter documents exactly what it maps and what it assumes.

When adding a new adapter:
1. Document what fields you expect on the input type
2. Document what you're assuming (and make caller provide if possible)
3. Map semantics explicitly (time_h -> observation_time_h means X)
"""

from __future__ import annotations

from .experiment import Well, Treatment, SpatialLocation
from .assay import AssayType


def well_spec_to_well(spec) -> Well:
    """Convert legacy WellSpec -> canonical Well.

    Expects spec to have:
    - cell_line: str
    - compound: str
    - dose_uM: float
    - time_h: float (maps to observation_time_h)
    - assay: str (normalized to AssayType via from_string)
    - position_tag: str (ignored - location allocated separately)

    Maps:
    - spec.time_h -> Well.observation_time_h
    - spec.compound + spec.dose_uM -> Well.treatment
    - spec.assay (string) -> Well.assay (AssayType enum)

    Does NOT map:
    - position_tag (location allocation is separate concern)
    """
    return Well(
        cell_line=spec.cell_line,
        treatment=Treatment(compound=spec.compound, dose_uM=spec.dose_uM),
        observation_time_h=float(spec.time_h),
        assay=AssayType.from_string(spec.assay),  # Normalize string -> enum
        location=None,  # Location allocated separately by world
    )


def well_assignment_to_well(assignment, *, assay: AssayType) -> Well:
    """Convert simulator WellAssignment -> canonical Well.

    Expects assignment to have:
    - cell_line: str
    - compound: str
    - dose_uM: float
    - timepoint_h: float (maps to observation_time_h)
    - plate_id: str
    - well_id: str

    Maps:
    - assignment.timepoint_h -> Well.observation_time_h
    - assignment.compound + assignment.dose_uM -> Well.treatment
    - assignment.plate_id + assignment.well_id -> Well.location

    Requires:
    - assay: AssayType (must be provided by caller, not string)

    Why assay is required:
    WellAssignment doesn't contain assay information. Rather than inventing
    a default, we force the caller to be explicit about what assay they're
    running. This prevents hidden assumptions.

    NOTE: assay parameter is now AssayType, not string. Caller must normalize.
    """
    return Well(
        cell_line=assignment.cell_line,
        treatment=Treatment(compound=assignment.compound, dose_uM=assignment.dose_uM),
        observation_time_h=float(assignment.timepoint_h),
        assay=assay,
        location=SpatialLocation(plate_id=assignment.plate_id, well_id=assignment.well_id),
    )


def well_to_well_spec(well, *, position_tag: str):
    """Convert canonical Well -> legacy WellSpec.

    Requires:
    - position_tag: Must be provided by caller (Well doesn't have position_tag)

    Maps:
    - Well.assay (AssayType enum) -> WellSpec.assay (string via .value)

    This is a reverse adapter for cases where legacy code still needs WellSpec.
    Use sparingly - prefer updating code to use canonical Well.
    """
    # Avoid circular import
    from cell_os.epistemic_agent.schemas import WellSpec

    return WellSpec(
        cell_line=well.cell_line,
        compound=well.treatment.compound,
        dose_uM=well.treatment.dose_uM,
        time_h=well.observation_time_h,  # Map back to legacy name
        assay=well.assay.value,  # Convert enum -> string
        position_tag=position_tag,
    )


def decision_event_to_decision(event, *, decision_id: str = None) -> "Decision":
    """Convert legacy DecisionEvent to canonical Decision.

    Args:
        event: Legacy DecisionEvent from beliefs/ledger.py
        decision_id: Optional decision ID (generated if not provided)

    Returns:
        Canonical Decision with full provenance

    Note:
        Legacy DecisionEvent has:
        - cycle, selected, selected_score, selected_candidate, reason, candidates

        Canonical Decision requires:
        - decision_id, cycle, timestamp_utc, kind, chosen_template, chosen_kwargs,
          rationale (with rules_fired, thresholds, metrics), inputs_fingerprint
    """
    from .decision import Decision, DecisionRationale
    import hashlib

    # Generate decision_id if not provided
    if decision_id is None:
        # Use cycle + selected template + hash of candidates
        cand_str = str(event.selected_candidate)
        cand_hash = hashlib.md5(cand_str.encode()).hexdigest()[:8]
        decision_id = f"cycle-{event.cycle}-{cand_hash}"

    # Determine kind from selected template
    selected = event.selected
    if selected.startswith("abort"):
        kind = "abort"
    elif selected in ["ldh_baseline", "scrna_baseline", "baseline_replicates"]:
        kind = "calibration"
    elif event.selected_candidate.get("forced") and event.selected_candidate.get("trigger") == "must_calibrate":
        kind = "calibration"
    elif event.selected_candidate.get("trigger") == "abort":
        kind = "refusal"
    else:
        kind = "proposal"

    # Extract metrics from selected_candidate
    cand = event.selected_candidate
    metrics = {}
    if "rel_width" in cand:
        metrics["rel_width"] = float(cand["rel_width"])
    if "top_prob" in cand:
        metrics["top_prob"] = float(cand["top_prob"])
    if "ece" in cand:
        metrics["ece"] = float(cand["ece"])
    if "score" in cand:
        metrics["score"] = float(cand["score"])

    # Extract thresholds (may not be in legacy event)
    thresholds = {}
    if "gate_enter" in cand:
        thresholds["gate_enter"] = float(cand["gate_enter"])
    if "commit" in cand:
        thresholds["commit"] = float(cand["commit"])

    # Extract rules fired
    rules_fired = []
    if "regime" in cand:
        rules_fired.append(f"regime_{cand['regime']}")
    if "enforcement_layer" in cand:
        rules_fired.append(f"enforcement_{cand['enforcement_layer']}")
    if cand.get("forced"):
        rules_fired.append("forced_by_policy")

    # Create rationale
    rationale = DecisionRationale(
        summary=event.reason,
        rules_fired=tuple(rules_fired),
        warnings=tuple(),  # Legacy event doesn't have warnings
        metrics=metrics,
        thresholds=thresholds,
        counterfactuals={},  # Legacy event doesn't have counterfactuals
    )

    # Generate inputs fingerprint (legacy event doesn't have this)
    # Use cycle + candidates hash as proxy
    candidates_str = str(event.candidates)
    fingerprint = hashlib.md5(f"{event.cycle}_{candidates_str}".encode()).hexdigest()[:16]

    # Extract chosen_kwargs from selected_candidate
    # Filter out meta fields (regime, forced, trigger, enforcement_layer, etc.)
    meta_fields = {"regime", "forced", "trigger", "enforcement_layer", "base_ev",
                   "cost", "score", "multiplier", "rel_width", "top_prob", "ece",
                   "gate_enter", "commit"}
    chosen_kwargs = {k: v for k, v in cand.items() if k not in meta_fields}

    return Decision(
        decision_id=decision_id,
        cycle=event.cycle,
        timestamp_utc=Decision.now_utc(),  # Legacy event doesn't have timestamp
        kind=kind,
        chosen_template=event.selected if kind != "refusal" else None,
        chosen_kwargs=chosen_kwargs,
        rationale=rationale,
        inputs_fingerprint=fingerprint,
    )
