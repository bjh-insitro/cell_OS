"""
Observation Aggregator: Transform raw well results into aggregated observations.

This module owns ALL statistical summarization and interpretation of experimental
results. World returns raw results; this module aggregates them.

Key principles:
- Pluggable strategies (per-channel vs scalar, different aggregation methods)
- No information loss (raw results → observation is deterministic and reversible)
- Clear separation: World executes, Aggregator interprets

Usage:
    raw_results = world.run_experiment(proposal)
    observation = aggregate_observation(
        proposal=proposal,
        raw_results=raw_results,
        budget_remaining=world.budget_remaining,
        strategy="default_per_channel"
    )
"""

from typing import Sequence, Dict, List, Any, Literal, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass
import numpy as np
import logging

from ..core.observation import RawWellResult, ConditionKey
from ..core.canonicalize import canonical_condition_key, CanonicalCondition
from .schemas import Observation, ConditionSummary, Proposal

logger = logging.getLogger(__name__)


# =============================================================================
# Aggregation Strategy Type
# =============================================================================

AggregationStrategy = Literal[
    "default_per_channel",  # Default: per-channel stats, no scalarization
    "legacy_scalar_mean",   # Backward compat: scalar mean of 5 channels
]


# =============================================================================
# Cell Line Normalization (Agent 4: Nuisance Control)
# =============================================================================

NormalizationMode = Literal[
    "none",         # Raw values (agent must discover cell line confound)
    "fold_change",  # Normalize by cell line baseline (removes 77% variance)
    "zscore",       # Standardize by vehicle statistics (requires vehicle controls)
]


def get_cell_line_baseline(cell_line: str) -> Dict[str, float]:
    """
    Load cell line baseline morphology from thalamus params.

    Args:
        cell_line: Cell line identifier (A549, HepG2, U2OS, etc.)

    Returns:
        Dict with channel baselines: {er: float, mito: float, ...}

    Note:
        Baselines come from data/cell_thalamus_params.yaml.
        If cell line not found, falls back to A549 baseline.
    """
    # Import here to avoid circular dependency
    import yaml
    from pathlib import Path

    # Load thalamus params (go up from src/cell_os/epistemic_agent/ to project root)
    params_path = Path(__file__).parent.parent.parent.parent / "data" / "cell_thalamus_params.yaml"
    if not params_path.exists():
        # Fallback: default baseline if params not found
        logger.warning(f"Thalamus params not found at {params_path}, using default A549 baseline")
        return {'er': 100.0, 'mito': 150.0, 'nucleus': 200.0, 'actin': 120.0, 'rna': 180.0}

    with open(params_path, 'r') as f:
        params = yaml.safe_load(f)

    baseline_morphology = params.get('baseline_morphology', {})
    baseline = baseline_morphology.get(cell_line)

    if baseline is None:
        logger.warning(f"No baseline for cell line '{cell_line}', falling back to A549")
        baseline = baseline_morphology.get('A549', {
            'er': 100.0, 'mito': 150.0, 'nucleus': 200.0, 'actin': 120.0, 'rna': 180.0
        })

    return baseline


def normalize_channel_value(
    raw_value: float,
    cell_line: str,
    channel: str,
    normalization_mode: NormalizationMode
) -> float:
    """
    Normalize a single channel value by cell line baseline.

    Args:
        raw_value: Raw channel measurement
        cell_line: Cell line identifier
        channel: Channel name (er, mito, nucleus, actin, rna)
        normalization_mode: Normalization strategy

    Returns:
        Normalized value

    Note:
        fold_change: raw / baseline (dimensionless, 1.0 = baseline)
        zscore: Not yet implemented (requires vehicle statistics)
    """
    if normalization_mode == "none":
        return raw_value

    baseline = get_cell_line_baseline(cell_line)
    baseline_val = baseline.get(channel, 1.0)

    if normalization_mode == "fold_change":
        # Prevent division by zero
        if baseline_val > 0:
            return raw_value / baseline_val
        else:
            logger.warning(f"Baseline for {cell_line}/{channel} is zero, returning raw value")
            return raw_value

    elif normalization_mode == "zscore":
        # TODO: Implement z-score normalization (requires vehicle statistics)
        raise NotImplementedError("Z-score normalization requires vehicle statistics (Phase 2)")

    else:
        raise ValueError(f"Unknown normalization mode: {normalization_mode}")


def build_normalization_metadata(
    cell_lines_used: Set[str],
    normalization_mode: NormalizationMode
) -> Dict[str, Any]:
    """
    Build normalization metadata for transparency.

    Args:
        cell_lines_used: Set of cell lines in this observation
        normalization_mode: Normalization strategy applied

    Returns:
        Metadata dict with baselines used, mode, etc.
    """
    if normalization_mode == "none":
        return {"mode": "none", "description": "No normalization applied"}

    baselines_used = {}
    for cell_line in cell_lines_used:
        baselines_used[cell_line] = get_cell_line_baseline(cell_line)

    metadata = {
        "mode": normalization_mode,
        "baselines_used": baselines_used,
        "description": (
            "fold_change: Normalized by cell line baseline from thalamus params. "
            "Values are dimensionless fold-change (1.0 = baseline)."
            if normalization_mode == "fold_change"
            else "Unknown normalization mode"
        )
    }

    return metadata


# =============================================================================
# Main Entry Point
# =============================================================================

def aggregate_observation(
    proposal: Proposal,
    raw_results: Sequence[RawWellResult],
    budget_remaining: int,
    *,
    cycle: int = 0,
    strategy: AggregationStrategy = "default_per_channel",
    normalization_mode: NormalizationMode = "none"
) -> Observation:
    """Aggregate raw well results into an Observation.

    This is the main entry point for converting raw execution results
    into the agent-facing Observation structure.

    Args:
        proposal: Original experiment proposal (for design_id, context)
        raw_results: Raw per-well results from world
        budget_remaining: Current budget after execution
        cycle: Current cycle number (for integrity checking with hysteresis)
        strategy: Aggregation strategy to use
        normalization_mode: Cell line normalization mode (none/fold_change/zscore)

    Returns:
        Observation with aggregated summaries and QC flags

    Note:
        The aggregation strategy can be swapped without touching world.py.
        This enables testing different aggregation approaches (per-channel,
        scalar, different statistics) without changing execution logic.

        Agent 4 (Nuisance Control): normalization_mode removes cell line baseline
        confounding. Default is "none" so agent must discover the confound.
    """
    # Run execution integrity checks BEFORE aggregation
    # This operates on raw wells to detect plate map errors before they're smoothed away
    from .integrity_checker import check_execution_integrity

    # Extract template name from design_id (convention: first part before underscore)
    # e.g., "baseline_replicates_cycle_5" → "baseline"
    template_name = None
    if proposal.design_id:
        parts = proposal.design_id.split('_')
        if parts:
            template_name = parts[0]

    # Safety check: warn if template name missing (QC will be skipped)
    if not template_name:
        logger.warning(
            f"No template name extracted from design_id='{proposal.design_id}'. "
            "Execution integrity checks will be skipped. "
            "This is expected for ad-hoc designs, but not for templated experiments."
        )

    # Load anchor configs for this template
    from .anchor_configs import get_anchor_config, get_dose_direction_config

    expected_anchors = get_anchor_config(template_name) if template_name else {}
    expected_dose_direction = get_dose_direction_config(template_name) if template_name else {}

    integrity_state = check_execution_integrity(
        raw_wells=list(raw_results),
        expected_anchors=expected_anchors,
        expected_dose_direction=expected_dose_direction,
        cycle=cycle,
        template_name=template_name,
        design_id=proposal.design_id,
    )

    if strategy == "default_per_channel":
        return _aggregate_per_channel(
            proposal, raw_results, budget_remaining, normalization_mode,
            integrity_state=integrity_state
        )
    elif strategy == "legacy_scalar_mean":
        return _aggregate_legacy_scalar(
            proposal, raw_results, budget_remaining, normalization_mode,
            integrity_state=integrity_state
        )
    else:
        raise ValueError(f"Unknown aggregation strategy: {strategy}")


# =============================================================================
# Strategy: Default Per-Channel (no scalarization)
# =============================================================================

def _aggregate_per_channel(
    proposal: Proposal,
    raw_results: Sequence[RawWellResult],
    budget_remaining: int,
    normalization_mode: NormalizationMode = "none",
    *,
    integrity_state=None
) -> Observation:
    """Aggregate with per-channel statistics (no scalar mean).

    This is the preferred strategy: preserve channel structure, don't
    collapse 5 channels into one scalar.

    For each condition:
    - Compute mean, std, sem per channel
    - Compute replicate agreement (CV per channel)
    - Detect outliers per channel (optional)

    Does NOT compute a scalar "response" by averaging channels.

    Agent 2: Now uses CANONICAL condition keys to prevent aggregation races.
    All doses/times converted to integer representations (nM, min) before grouping.

    Agent 4: Cell line normalization applied before statistics.
    """
    # Agent 1.5: Temporal Provenance Enforcement
    # Cannot aggregate zero results - would produce observation with no conditions
    if not raw_results:
        from cell_os.epistemic_agent.exceptions import TemporalProvenanceError
        raise TemporalProvenanceError(
            message="Aggregator received zero raw_results; cannot produce observation with temporal metadata",
            missing_field="observation_time_h",
            context="observation_aggregator._aggregate_per_channel()",
            details={"proposal_design_id": proposal.design_id}
        )

    # Group by CANONICAL condition (Agent 2)
    conditions: Dict[CanonicalCondition, List[Dict[str, Any]]] = defaultdict(list)

    # Track raw parameter values for near-duplicate detection
    raw_params_by_canonical: Dict[CanonicalCondition, Set[Tuple[float, float]]] = defaultdict(set)

    # Agent 4: Track cell lines used (for normalization metadata)
    cell_lines_used: Set[str] = set()

    for result in raw_results:
        # Agent 4: Track cell lines for normalization metadata
        cell_lines_used.add(result.cell_line)

        # Derive position_class from physical location
        position_class = result.location.position_class

        # Agent 2: Create CANONICAL condition key (integers, no floats)
        canonical_key = canonical_condition_key(
            cell_line=result.cell_line,
            compound_id=result.treatment.compound,
            dose_uM=result.treatment.dose_uM,
            time_h=result.observation_time_h,
            assay=result.assay.value,  # Convert enum to string
            position_class=position_class
        )

        # Agent 2: Track raw parameters for near-duplicate detection
        raw_params_by_canonical[canonical_key].add((
            result.treatment.dose_uM,
            result.observation_time_h
        ))

        # Extract morphology channels
        morph = result.readouts.get('morphology', {})
        features = {
            'er': morph.get('er', 0.0),
            'mito': morph.get('mito', 0.0),
            'nucleus': morph.get('nucleus', 0.0),
            'actin': morph.get('actin', 0.0),
            'rna': morph.get('rna', 0.0),
        }

        # Compute scalar response for backward compatibility
        # (but mark it as derived, not primary)
        response = np.mean(list(features.values()))

        conditions[canonical_key].append({
            'response': response,
            'features': features,
            'well_id': result.location.well_id,
            'failed': result.qc.get('failed', False),
            # Agent 2: Store raw parameters for audit
            'raw_dose_uM': result.treatment.dose_uM,
            'raw_time_h': result.observation_time_h,
        })

    # Agent 2: Detect and log near-duplicates (conditions that merged)
    near_duplicate_events = []
    for canonical_key, raw_params_set in raw_params_by_canonical.items():
        if len(raw_params_set) > 1:
            # Multiple raw (dose, time) pairs collapsed to same canonical key
            raw_doses = sorted(set(d for d, t in raw_params_set))
            raw_times = sorted(set(t for d, t in raw_params_set))

            event = {
                "event": "canonical_condition_merge",
                "canonical_key": canonical_key.to_dict(),
                "raw_doses_uM": raw_doses,
                "raw_times_h": raw_times,
                "n_wells": len(conditions[canonical_key]),
            }
            near_duplicate_events.append(event)

            logger.info(
                f"Agent 2: Merged near-duplicate conditions into {canonical_key}: "
                f"doses={raw_doses}, times={raw_times}, n_wells={len(conditions[canonical_key])}"
            )

    # Compute summary statistics per condition
    summaries = []
    for canonical_key, values in conditions.items():
        summary = _summarize_condition(canonical_key, values, normalization_mode)
        summaries.append(summary)

    # Generate QC flags
    qc_flags = _generate_qc_flags(summaries)

    # Agent 4: Build normalization metadata
    normalization_metadata = build_normalization_metadata(cell_lines_used, normalization_mode)

    # Agent 3: Record aggregation strategy for transparency
    observation = Observation(
        design_id=proposal.design_id,
        conditions=summaries,
        wells_spent=len(raw_results),
        budget_remaining=budget_remaining,
        qc_flags=qc_flags,
        aggregation_strategy="default_per_channel",
        # Agent 4: Normalization transparency
        normalization_mode=normalization_mode,
        normalization_metadata=normalization_metadata,
        # Agent 2: Attach near-duplicate events for diagnostics
        near_duplicate_merges=near_duplicate_merges,
        # Execution integrity state from QC checks (plate map errors, etc.)
        execution_integrity=integrity_state,
    )

    return observation


# =============================================================================
# Strategy: Legacy Scalar Mean (backward compatibility)
# =============================================================================

def _aggregate_legacy_scalar(
    proposal: Proposal,
    raw_results: Sequence[RawWellResult],
    budget_remaining: int,
    normalization_mode: NormalizationMode = "none",
    *,
    integrity_state=None
) -> Observation:
    """Aggregate using scalar mean (backward compatibility).

    This replicates the old world.py behavior: collapse 5 channels
    into a single scalar by averaging.

    Use this strategy for regression testing against old code.
    """
    # Same implementation as per-channel, but emphasize scalar response
    return _aggregate_per_channel(
        proposal, raw_results, budget_remaining, normalization_mode,
        integrity_state=integrity_state
    )


# =============================================================================
# Condition Summarization
# =============================================================================

def _summarize_condition(
    key: CanonicalCondition,
    values: List[Dict[str, Any]],
    normalization_mode: NormalizationMode = "none"
) -> ConditionSummary:
    """Compute summary statistics for a condition.

    Agent 2: Now accepts CanonicalCondition (integer dose_nM, time_min).
    Agent 3 hardening: Explicit tracking of information loss.
    - All wells counted in n_wells_total
    - Drops tracked in drop_reasons
    - No silent uncertainty reduction
    Agent 4: Cell line normalization applied before computing statistics.

    Args:
        key: Canonical condition identifier (integers, no floats)
        values: List of per-well measurements for this condition
        normalization_mode: Cell line normalization mode (none/fold_change/zscore)

    Returns:
        ConditionSummary with statistics and aggregation transparency metadata
    """
    # Agent 3: Track ALL wells (before any filtering)
    n_wells_total = len(values)

    if n_wells_total == 0:
        # Empty condition (shouldn't happen, but handle gracefully)
        return _empty_condition_summary(key)

    # Agent 3: Explicit drop tracking
    drop_reasons: Dict[str, int] = {}

    # Extract scalar responses and filter
    all_responses = []
    used_values = []

    for v in values:
        # Check if well should be dropped
        if v['failed']:
            drop_reasons['qc_failed'] = drop_reasons.get('qc_failed', 0) + 1
        else:
            all_responses.append(v['response'])
            used_values.append(v)

    n_wells_used = len(used_values)
    n_wells_dropped = n_wells_total - n_wells_used

    if n_wells_used == 0:
        # All wells failed QC
        return _empty_condition_summary(key)

    # Compute statistics on USED wells only
    responses = all_responses
    n = n_wells_used

    # Scalar statistics
    mean_val = float(np.mean(responses))
    std_val = float(np.std(responses, ddof=1)) if n > 1 else 0.0
    sem_val = std_val / np.sqrt(n) if n > 0 else 0.0
    cv_val = std_val / mean_val if mean_val > 0 else 0.0
    min_val = float(np.min(responses))
    max_val = float(np.max(responses))

    # Agent 3: Robust dispersion metrics (MAD, IQR)
    mad_val = float(np.median(np.abs(np.array(responses) - np.median(responses)))) if n > 0 else 0.0
    iqr_val = float(np.percentile(responses, 75) - np.percentile(responses, 25)) if n > 1 else 0.0

    # Per-channel statistics (Agent 4: Apply normalization before statistics)
    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']
    feature_means = {}
    feature_stds = {}

    for ch in channels:
        ch_values = [v['features'][ch] for v in used_values]

        # Agent 4: Apply cell line normalization BEFORE computing statistics
        if normalization_mode != "none":
            ch_values_normalized = [
                normalize_channel_value(val, key.cell_line, ch, normalization_mode)
                for val in ch_values
            ]
            ch_values = ch_values_normalized

        feature_means[ch] = float(np.mean(ch_values))
        feature_stds[ch] = float(np.std(ch_values, ddof=1)) if n > 1 else 0.0

    # Outlier detection (Z-score > 3 on scalar response)
    # Agent 3: Count outliers but DO NOT DROP them (already filtered by QC above)
    n_outliers = 0
    if n > 2 and std_val > 0:
        z_scores = np.abs((np.array(responses) - mean_val) / std_val)
        n_outliers = int(np.sum(z_scores > 3))
        # Note: We do NOT drop outliers, just flag them for visibility

    # Agent 3: Aggregation penalty flag
    # If we dropped wells, mark that CI might be artificially tight
    aggregation_penalty_applied = (n_wells_dropped > 0)

    # Agent 2: Convert canonical integers back to floats for ConditionSummary
    # (ConditionSummary still uses floats for backward compat, but sourced from canonical)
    dose_uM = key.dose_nM / 1000.0
    time_h = key.time_min / 60.0

    # Agent 1.5: Temporal Provenance Enforcement
    # Every ConditionSummary MUST have time_h; missing time bypasses temporal causality
    if time_h is None or not hasattr(key, 'time_min') or key.time_min is None:
        from cell_os.epistemic_agent.exceptions import TemporalProvenanceError
        raise TemporalProvenanceError(
            message=(
                f"Aggregator cannot derive time_h for condition {key}; "
                "temporal enforcement would be bypassed"
            ),
            missing_field="time_h",
            context="observation_aggregator._summarize_condition()",
            details={"condition_key": str(key), "dose_uM": dose_uM}
        )

    summary = ConditionSummary(
        cell_line=key.cell_line,
        compound=key.compound_id,
        dose_uM=dose_uM,  # Agent 2: Derived from canonical dose_nM
        time_h=time_h,    # Agent 2: Derived from canonical time_min
        assay=key.assay,
        position_tag=key.position_class,
        n_wells=n_wells_total,  # Backward compat: keep as total
        mean=mean_val,
        std=std_val,
        sem=sem_val,
        cv=cv_val,
        min_val=min_val,
        max_val=max_val,
        feature_means=feature_means,
        feature_stds=feature_stds,
        n_failed=drop_reasons.get('qc_failed', 0),
        n_outliers=n_outliers,
        # Agent 3: Aggregation transparency
        n_wells_total=n_wells_total,
        n_wells_used=n_wells_used,
        n_wells_dropped=n_wells_dropped,
        drop_reasons=drop_reasons,
        aggregation_penalty_applied=aggregation_penalty_applied,
        mad=mad_val,
        iqr=iqr_val,
        # Agent 2: Store canonical representation for audit
        canonical_dose_nM=key.dose_nM,
        canonical_time_min=key.time_min,
    )

    return summary


def _empty_condition_summary(key: CanonicalCondition) -> ConditionSummary:
    """Create empty summary for condition with no wells.

    Agent 2: Updated to accept CanonicalCondition.
    """
    # Agent 2: Convert canonical integers back to floats
    dose_uM = key.dose_nM / 1000.0
    time_h = key.time_min / 60.0

    # Agent 1.5: Temporal Provenance Enforcement
    # Even empty summaries must have time_h
    if time_h is None or not hasattr(key, 'time_min') or key.time_min is None:
        from cell_os.epistemic_agent.exceptions import TemporalProvenanceError
        raise TemporalProvenanceError(
            message=(
                f"Aggregator cannot derive time_h for empty condition {key}; "
                "temporal enforcement would be bypassed"
            ),
            missing_field="time_h",
            context="observation_aggregator._empty_condition_summary()",
            details={"condition_key": str(key), "dose_uM": dose_uM}
        )

    return ConditionSummary(
        cell_line=key.cell_line,
        compound=key.compound_id,
        dose_uM=dose_uM,
        time_h=time_h,
        assay=key.assay,
        position_tag=key.position_class,
        n_wells=0,
        mean=0.0,
        std=0.0,
        sem=0.0,
        cv=0.0,
        min_val=0.0,
        max_val=0.0,
        feature_means={},
        feature_stds={},
        n_failed=0,
        n_outliers=0,
        # Agent 3: Empty transparency metadata
        n_wells_total=0,
        n_wells_used=0,
        n_wells_dropped=0,
        drop_reasons={},
        aggregation_penalty_applied=False,
        mad=0.0,
        iqr=0.0,
        # Agent 2: Canonical fields
        canonical_dose_nM=key.dose_nM,
        canonical_time_min=key.time_min,
    )


# =============================================================================
# QC Flag Generation
# =============================================================================

def _generate_qc_flags(summaries: List[ConditionSummary]) -> List[str]:
    """Generate QC flags from aggregated summaries.

    QC flags are coarse indicators of potential issues. The agent
    must interpret these (world doesn't explain them).

    Args:
        summaries: Aggregated condition summaries

    Returns:
        List of QC flag strings
    """
    flags = []

    # Check for edge bias (if both edge and center present)
    edge_means = [s.mean for s in summaries if s.position_tag == 'edge']
    center_means = [s.mean for s in summaries if s.position_tag == 'center']

    if edge_means and center_means:
        edge_avg = np.mean(edge_means)
        center_avg = np.mean(center_means)
        diff_pct = abs(edge_avg - center_avg) / center_avg if center_avg > 0 else 0

        if diff_pct > 0.1:  # >10% difference
            direction = "lower" if edge_avg < center_avg else "higher"
            flags.append(
                f"Edge wells show {diff_pct:.1%} {direction} signal than center"
            )

    # Check for high variance
    high_cv_conditions = [s for s in summaries if s.cv > 0.15]
    if high_cv_conditions:
        flags.append(
            f"{len(high_cv_conditions)}/{len(summaries)} conditions have CV >15%"
        )

    # Check for outliers
    total_outliers = sum(s.n_outliers for s in summaries)
    if total_outliers > 0:
        flags.append(f"{total_outliers} wells flagged as outliers (Z>3)")

    # Check for failures
    total_failed = sum(s.n_failed for s in summaries)
    if total_failed > 0:
        flags.append(f"{total_failed} wells failed QC")

    return flags


# =============================================================================
# Provenance and Round-Trip
# =============================================================================

def compute_observation_fingerprint(
    proposal: Proposal,
    raw_results: Sequence[RawWellResult]
) -> str:
    """Compute deterministic fingerprint linking Observation to raw results.

    This enables audit and replay:
    - Given proposal + raw_results, observation is deterministic
    - Fingerprint links aggregated Observation back to raw results

    Args:
        proposal: Experiment proposal
        raw_results: Raw well results

    Returns:
        Hex fingerprint string
    """
    import hashlib
    import json

    # Serialize key fields in canonical order
    data = {
        'design_id': proposal.design_id,
        'n_wells': len(raw_results),
        'well_ids': sorted([r.location.well_id for r in raw_results]),
    }

    canonical = json.dumps(data, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
