"""
QC Gate - Clean separation between QC metadata and agent-visible observations.

Option B: QC is gate-only, not optimization surface.

The agent sees:
- Morphology values (with masked channels removed)
- Binary accept/reject decision
- NO continuous QC metrics (quality_score, margins, counts)

QC metadata is kept in audit stream for humans/debugging only.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Any, Optional
from copy import deepcopy

logger = logging.getLogger(__name__)


def strip_qc_metadata(observation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strip QC metadata from observation, leaving only agent-visible information.

    Agent sees:
    - Morphology values (feature_means, feature_stds) with masked channels removed
    - Binary accept/reject per condition (via presence in conditions list)
    - NO quality_score, min_margin, usable_channels, n_usable, etc.

    QC metadata is moved to audit_qc (human/debug only).

    Args:
        observation: Observation dict with SNR policy applied

    Returns:
        Agent-visible observation (QC metadata stripped)
    """
    agent_obs = deepcopy(observation)

    # Move QC summary to audit stream
    if "snr_policy_summary" in agent_obs:
        if "audit_qc" not in agent_obs:
            agent_obs["audit_qc"] = {}
        agent_obs["audit_qc"]["snr_policy_summary"] = agent_obs.pop("snr_policy_summary")

    # Strip per-condition QC metadata
    for cond in agent_obs.get("conditions", []):
        if "snr_policy" in cond:
            # Move to audit stream
            if "audit_qc" not in cond:
                cond["audit_qc"] = {}
            cond["audit_qc"]["snr_policy"] = cond.pop("snr_policy")

        # Remove masked channels entirely (not just set to None)
        # Agent should not see the *existence* of masked channels
        if "feature_means" in cond:
            feature_means = cond["feature_means"]
            # Remove None values (masked channels)
            cond["feature_means"] = {ch: val for ch, val in feature_means.items() if val is not None}

        if "feature_stds" in cond:
            feature_stds = cond["feature_stds"]
            # Remove stds for masked channels
            cond["feature_stds"] = {ch: val for ch, val in feature_stds.items() if ch in cond["feature_means"]}

    return agent_obs


def apply_qc_gate(
    observation: Dict[str, Any],
    min_usable_channels: int = 3,
    min_quality_score: float = 0.6
) -> Dict[str, Any]:
    """
    Apply QC gate: reject conditions that don't meet minimum criteria.

    This is the ONLY place where QC metrics affect the agent's view.
    Conditions are either accepted (present) or rejected (absent).

    Args:
        observation: Observation dict with SNR policy applied
        min_usable_channels: Minimum number of usable channels to accept
        min_quality_score: Minimum quality score to accept

    Returns:
        Observation with rejected conditions removed
    """
    conditions = observation.get("conditions", [])
    accepted = []
    rejected = []

    for cond in conditions:
        snr = cond.get("snr_policy", {})

        # Gate criteria
        n_usable = len(snr.get("usable_channels", []))
        quality_score = snr.get("quality_score", 1.0)

        if n_usable >= min_usable_channels and quality_score >= min_quality_score:
            accepted.append(cond)
        else:
            # Keep rejected for audit, but mark as rejected
            cond["qc_rejected"] = True
            cond["qc_rejection_reason"] = f"n_usable={n_usable} < {min_usable_channels} or quality={quality_score:.2f} < {min_quality_score:.2f}"
            rejected.append(cond)

    # Update observation
    gated_obs = observation.copy()
    gated_obs["conditions"] = accepted

    # Store rejected in audit stream
    if rejected:
        if "audit_qc" not in gated_obs:
            gated_obs["audit_qc"] = {}
        gated_obs["audit_qc"]["rejected_conditions"] = rejected

    logger.info(f"QC gate: {len(accepted)} accepted, {len(rejected)} rejected")

    return gated_obs


def prepare_agent_observation(
    observation: Dict[str, Any],
    apply_gate: bool = True,
    min_usable_channels: int = 3,
    min_quality_score: float = 0.6
) -> Dict[str, Any]:
    """
    Prepare observation for agent consumption.

    Pipeline:
    1. Apply QC gate (optional, reject low-quality conditions)
    2. Strip QC metadata (quality_score, margins, usable_channels, etc.)
    3. Remove masked channels from morphology

    Result:
    - Agent sees only accepted conditions
    - Agent sees only usable morphology channels
    - Agent does NOT see quality_score, margins, or any continuous QC metric

    Args:
        observation: Observation dict with SNR policy applied
        apply_gate: If True, reject conditions below threshold
        min_usable_channels: Minimum usable channels (if gating)
        min_quality_score: Minimum quality score (if gating)

    Returns:
        Agent-visible observation (clean, no QC leakage)
    """
    # Step 1: Apply gate (reject low-quality conditions)
    if apply_gate:
        gated_obs = apply_qc_gate(observation, min_usable_channels, min_quality_score)
    else:
        gated_obs = observation

    # Step 2: Strip QC metadata
    agent_obs = strip_qc_metadata(gated_obs)

    return agent_obs


def extract_audit_qc(observation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract QC metadata from observation for audit/debugging.

    This is for humans, not the agent.

    Args:
        observation: Agent-visible observation (QC metadata stripped)

    Returns:
        QC audit data (quality_score, margins, etc.)
    """
    audit = observation.get("audit_qc", {})

    # Extract per-condition QC
    conditions_qc = []
    for cond in observation.get("conditions", []):
        cond_qc = cond.get("audit_qc", {})
        if cond_qc:
            conditions_qc.append({
                "compound": cond.get("compound"),
                "dose_uM": cond.get("dose_uM"),
                "time_h": cond.get("time_h"),
                "qc": cond_qc
            })

    if conditions_qc:
        audit["conditions"] = conditions_qc

    return audit
