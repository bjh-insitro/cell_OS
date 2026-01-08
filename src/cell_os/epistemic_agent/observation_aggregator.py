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

from typing import Sequence, Dict, List, Any, Literal, Tuple, Set, Optional
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
    Load cell line baseline morphology from database.

    Args:
        cell_line: Cell line identifier (A549, HepG2, U2OS, etc.)

    Returns:
        Dict with channel baselines: {er: float, mito: float, ...}

    Note:
        Baselines come from database (baseline_morphology table).
        If cell line not found, falls back to A549 baseline.
    """
    # Import here to avoid circular dependency
    from ..database.repositories.cell_thalamus_repository import CellThalamusRepository

    try:
        repo = CellThalamusRepository()
        baseline = repo.get_baseline_morphology(cell_line)

        if baseline is None:
            logger.warning(f"No baseline for cell line '{cell_line}', falling back to A549")
            baseline = repo.get_baseline_morphology('A549')

            if baseline is None:
                # Ultimate fallback if database query fails
                logger.warning("Database query failed, using hardcoded A549 baseline")
                return {'er': 100.0, 'mito': 150.0, 'nucleus': 200.0, 'actin': 120.0, 'rna': 180.0}

        return baseline

    except Exception as e:
        logger.error(f"Failed to load baseline from database: {e}, using default A549 baseline")
        return {'er': 100.0, 'mito': 150.0, 'nucleus': 200.0, 'actin': 120.0, 'rna': 180.0}


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
    normalization_mode: NormalizationMode = "none",
    snr_policy = None
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
        snr_policy: Optional SNRPolicy instance for filtering low-SNR conditions (Phase 4)

    Returns:
        Observation with aggregated summaries and QC flags

    Note:
        The aggregation strategy can be swapped without touching world.py.
        This enables testing different aggregation approaches (per-channel,
        scalar, different statistics) without changing execution logic.

        Agent 4 (Nuisance Control): normalization_mode removes cell line baseline
        confounding. Default is "none" so agent must discover the confound.

        Phase 4 (SNR Policy): snr_policy filters/flags conditions below minimum
        detectable signal to prevent agent from learning in sub-noise regimes.
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
        obs = _aggregate_per_channel(
            proposal, raw_results, budget_remaining, normalization_mode,
            integrity_state=integrity_state
        )
    elif strategy == "legacy_scalar_mean":
        obs = _aggregate_legacy_scalar(
            proposal, raw_results, budget_remaining, normalization_mode,
            integrity_state=integrity_state
        )
    else:
        raise ValueError(f"Unknown aggregation strategy: {strategy}")

    # Phase 4: Apply SNR policy if provided
    if snr_policy is not None:
        # Convert Observation to dict, apply policy, convert back
        obs_dict = _observation_to_dict(obs)
        filtered_dict = snr_policy.filter_observation(obs_dict, annotate=True)
        # Update observation with filtered conditions and SNR metadata
        obs = _update_observation_from_dict(obs, filtered_dict)

    return obs


# =============================================================================
# Phase 4: SNR Policy Enforcement Helpers
# =============================================================================

def _drop_none(xs):
    """Filter None values from a list (used to handle SNR-masked channels).

    Phase 4: SNR policy masks channels with insufficient signal to None.
    Aggregation must ignore these masked channels, not launder them to 0.0.
    """
    return [x for x in xs if x is not None]


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
        # Phase 4: Preserve None from SNR policy (do NOT launder to 0.0)
        morph = result.readouts.get('morphology', {})
        features = {
            'er': morph.get('er', None),
            'mito': morph.get('mito', None),
            'nucleus': morph.get('nucleus', None),
            'actin': morph.get('actin', None),
            'rna': morph.get('rna', None),
        }

        # Compute scalar response for backward compatibility
        # Phase 4: Exclude masked (None) channels from scalar computation
        usable_features = {k: v for k, v in features.items() if v is not None}
        if usable_features:
            response = float(np.mean(list(usable_features.values())))
        else:
            # All channels masked → cannot compute scalar
            response = None

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
    # Phase 5: Sort for deterministic iteration order (use tuple as sort key)
    for canonical_key, raw_params_set in sorted(raw_params_by_canonical.items(), key=lambda x: (x[0].cell_line, x[0].compound_id, x[0].dose_nM, x[0].time_min, x[0].assay, x[0].position_class or "")):
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
    # Phase 5: Sort for deterministic iteration order (use tuple as sort key)
    for canonical_key, values in sorted(conditions.items(), key=lambda x: (x[0].cell_line, x[0].compound_id, x[0].dose_nM, x[0].time_min, x[0].assay, x[0].position_class or "")):
        summary = _summarize_condition(canonical_key, values, normalization_mode)
        summaries.append(summary)

    # Generate QC flags (including spatial autocorrelation checks)
    qc_flags, qc_struct = _generate_qc_flags(summaries, raw_results=raw_results)

    # Agent 4: Build normalization metadata
    normalization_metadata = build_normalization_metadata(cell_lines_used, normalization_mode)

    # Agent 2: Track near-duplicate condition merges (empty for now - future diagnostic feature)
    near_duplicate_merges: list = []

    # Agent 3: Record aggregation strategy for transparency
    observation = Observation(
        design_id=proposal.design_id,
        conditions=summaries,
        wells_spent=len(raw_results),
        budget_remaining=budget_remaining,
        qc_flags=qc_flags,
        qc_struct=qc_struct,
        aggregation_strategy="default_per_channel",
        # Agent 4: Normalization transparency
        normalization_mode=normalization_mode,
        normalization_metadata=normalization_metadata,
        # Agent 2: Attach near-duplicate events for diagnostics
        near_duplicate_merges=near_duplicate_merges,
        # Execution integrity state from QC checks (plate map errors, etc.)
        execution_integrity=integrity_state,
    )

    # v0.6.1 Gap D: Runtime observation payload guard
    # Validates that no ground truth keys leaked into agent-facing observation
    _validate_observation_no_ground_truth(observation)

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

    # Phase 4: Filter None from responses (all channels masked case)
    responses = [r for r in all_responses if r is not None]
    n = len(responses)

    # Scalar statistics (handle case where all responses are None)
    if n == 0:
        # All channels masked → no scalar statistics possible
        mean_val = None
        std_val = None
        sem_val = None
        cv_val = None
        min_val = None
        max_val = None
    else:
        mean_val = float(np.mean(responses))
        std_val = float(np.std(responses, ddof=1)) if n > 1 else 0.0
        sem_val = std_val / np.sqrt(n) if n > 0 else 0.0
        cv_val = std_val / mean_val if mean_val > 0 else 0.0
        min_val = float(np.min(responses))
        max_val = float(np.max(responses))

    # Agent 3: Robust dispersion metrics (MAD, IQR)
    # Phase 4: Handle case where all responses are None
    if n > 0 and responses:
        mad_val = float(np.median(np.abs(np.array(responses) - np.median(responses))))
        iqr_val = float(np.percentile(responses, 75) - np.percentile(responses, 25)) if n > 1 else 0.0
    else:
        mad_val = None
        iqr_val = None

    # Per-channel statistics (Agent 4: Apply normalization before statistics)
    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']
    feature_means = {}
    feature_stds = {}

    for ch in channels:
        ch_values = [v['features'][ch] for v in used_values]

        # Phase 4: Filter out None (SNR-masked channels) BEFORE normalization
        ch_values = _drop_none(ch_values)

        # Agent 4: Apply cell line normalization BEFORE computing statistics
        if normalization_mode != "none":
            ch_values_normalized = [
                normalize_channel_value(val, key.cell_line, ch, normalization_mode)
                for val in ch_values
            ]
            ch_values = ch_values_normalized

        # Phase 4: If all replicates masked, propagate None
        if len(ch_values) == 0:
            feature_means[ch] = None
            feature_stds[ch] = None
        else:
            feature_means[ch] = float(np.mean(ch_values))
            feature_stds[ch] = float(np.std(ch_values, ddof=1)) if len(ch_values) > 1 else 0.0

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

    # Phase 4: Track which channels were usable vs masked by SNR policy
    usable_channels = [ch for ch, val in feature_means.items() if val is not None]
    masked_channels = [ch for ch, val in feature_means.items() if val is None]

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
        # Phase 4: SNR policy enforcement metadata
        usable_channels=usable_channels,
        masked_channels=masked_channels,
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

def _generate_qc_flags(
    summaries: List[ConditionSummary],
    raw_results: Optional[Sequence[RawWellResult]] = None
) -> Tuple[List[str], Dict[str, Any]]:
    """Generate QC flags from aggregated summaries and raw wells.

    QC flags are coarse indicators of potential issues. The agent
    must interpret these (world doesn't explain them).

    Args:
        summaries: Aggregated condition summaries
        raw_results: Optional raw well results for spatial QC checks

    Returns:
        Tuple of (qc_flags: list of human-readable strings, qc_struct: machine-readable dict)
    """
    flags = []
    qc_struct = {}

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
    # Phase 4: Handle None cv values (all channels masked case)
    high_cv_conditions = [s for s in summaries if s.cv is not None and s.cv > 0.15]
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

    # Spatial autocorrelation check (detect gradients, patterns)
    if raw_results and len(raw_results) > 10:  # Need sufficient wells
        from ..qc.spatial_diagnostics import check_spatial_autocorrelation

        try:
            flagged, diag = check_spatial_autocorrelation(
                list(raw_results),
                channel_key="morphology.nucleus",
                significance_threshold=1.96  # p < 0.05
            )

            # Populate structured QC data
            if "spatial_autocorrelation" not in qc_struct:
                qc_struct["spatial_autocorrelation"] = {}

            qc_struct["spatial_autocorrelation"]["morphology.nucleus"] = {
                "morans_i": float(diag['morans_i']),
                "z_score": float(diag['z_score']),
                "p_value": 0.05 if abs(diag['z_score']) > 1.96 else 1.0,  # Rough approximation
                "flagged": bool(flagged),
                "n_wells": int(diag['n_wells'])
            }

            # Human-readable flag (keep for backwards compat)
            if flagged:
                flags.append(
                    f"spatial_autocorrelation[morphology.nucleus]: "
                    f"I={diag['morans_i']:.3f} (Z={diag['z_score']:.2f}, p<0.05) FLAGGED"
                )
        except Exception as e:
            # Spatial QC is nice-to-have, don't crash if it fails
            logger.warning(f"Spatial autocorrelation check failed: {e}")

    return flags, qc_struct


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


# =============================================================================
# SNR Policy Integration Helpers (Phase 4)
# =============================================================================

def _observation_to_dict(obs: Observation) -> Dict[str, Any]:
    """Convert Observation to dict for SNR policy filtering."""
    from dataclasses import asdict
    return asdict(obs)


def _update_observation_from_dict(obs: Observation, filtered_dict: Dict[str, Any]) -> Observation:
    """Update Observation with SNR-filtered conditions and metadata."""
    # Update conditions with filtered list
    obs.conditions = [
        ConditionSummary(**cond) if isinstance(cond, dict) else cond
        for cond in filtered_dict.get("conditions", [])
    ]

    # Add SNR policy summary to QC struct (if not already there)
    if "snr_policy_summary" in filtered_dict:
        if obs.qc_struct is None:
            obs.qc_struct = {}
        obs.qc_struct["snr_policy"] = filtered_dict["snr_policy_summary"]

    return obs


# =============================================================================
# Runtime Observation Guard (v0.6.1 Gap D)
# =============================================================================

def _validate_observation_no_ground_truth(obs: Observation) -> None:
    """Validate that observation contains no ground truth keys.

    This is a runtime guard that prevents truth leakage into agent-facing
    observations. It complements the static import scanner by catching
    cases where ground truth could sneak into observation payloads.

    v0.6.1: Added as part of Gap D (ground-truth boundary hardening)

    The guard checks:
    - Condition summaries (feature_means, feature_stds, etc.)
    - QC struct and flags
    - Normalization metadata
    - Any nested dicts within the observation

    Raises:
        AssertionError: If any forbidden keys are detected

    Note:
        This is intentionally an assertion, not a warning. Ground truth
        leakage is a silent failure mode that can corrupt training and
        evaluation. Loud failures are preferred.
    """
    from cell_os.contracts.ground_truth_policy import (
        ALWAYS_FORBIDDEN_PATTERNS,
        validate_no_ground_truth,
        format_violations,
    )

    # Convert observation to dict for recursive validation
    obs_dict = {
        "design_id": obs.design_id,
        "wells_spent": obs.wells_spent,
        "budget_remaining": obs.budget_remaining,
        "qc_flags": obs.qc_flags,
        "qc_struct": obs.qc_struct,
        "normalization_mode": obs.normalization_mode,
        "normalization_metadata": obs.normalization_metadata,
    }

    # Add conditions (this is where truth would most likely leak)
    if obs.conditions:
        obs_dict["conditions"] = [
            {
                "compound": c.compound,
                "cell_line": c.cell_line,
                "dose_uM": c.dose_uM,
                "time_h": c.time_h,
                "assay": c.assay,
                "position_tag": c.position_tag,
                "n_wells": c.n_wells,
                "mean": c.mean,
                "std": c.std,
                "cv": c.cv,
                "feature_means": c.feature_means,
                "feature_stds": c.feature_stds,
            }
            for c in obs.conditions
        ]

    violations = validate_no_ground_truth(obs_dict, ALWAYS_FORBIDDEN_PATTERNS)

    if violations:
        error_msg = (
            "GROUND TRUTH LEAKED INTO OBSERVATION!\n"
            f"This is a critical integrity violation.\n"
            f"{format_violations(violations)}"
        )
        raise AssertionError(error_msg)
