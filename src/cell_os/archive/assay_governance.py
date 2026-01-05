"""
Assay governance: principled gating for expensive assays.

PHILOSOPHY: Expensive assays (scRNA-seq, mass spec, etc.) should require
justification, not just be available on demand. This module enforces:

1. No expensive assays without demonstrating cheaper alternatives failed
2. Underpowered requests are flagged or refused
3. High-drift scenarios require replicate plans, not just "sequence more"
4. Expected information gain must justify cost

This prevents agents from using scRNA-seq as an "emotional support assay"
that they default to whenever uncertain.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssayJustification:
    """
    Justification required for expensive assays.

    Fields:
        ambiguity: What specific ambiguity does this assay resolve?
                   e.g. "ER vs oxidative crosstalk"
        failed_modalities: Which cheaper modalities were attempted first?
                          e.g. ("cell_painting", "atp_assay")
        expected_information_gain: Predicted information gain (bits or scalar)
        min_cells: Minimum cells requested (for scRNA-seq)
        replicate_strategy: Optional description of replicate plan if drift is high
    """

    ambiguity: str
    failed_modalities: Tuple[str, ...]
    expected_information_gain: float
    min_cells: int
    replicate_strategy: Optional[str] = None


def allow_scrna_seq(
    justification: AssayJustification,
    params: Dict[str, Any],
    drift_score: float = 0.0,
) -> Tuple[bool, str]:
    """
    Gate scRNA-seq requests based on principled criteria.

    Args:
        justification: Assay justification object
        params: scRNA-seq params dict (loaded from YAML)
        drift_score: Current drift score (0-1), higher = more batch risk

    Returns:
        (allowed: bool, reason: str)

    Refusal criteria:
        1. Underpowered: min_cells < params["costs"]["min_cells"]
        2. No cheaper alternatives attempted
        3. Poor information gain per dollar
        4. High drift without replicate strategy
    """
    costs = params.get("costs", {})
    min_cells_required = int(costs.get("min_cells", 500))
    reagent_cost = float(costs.get("reagent_cost_usd", 200.0))

    # 1. Check power
    if justification.min_cells < min_cells_required:
        return False, f"REFUSE: underpowered scRNA request ({justification.min_cells} < {min_cells_required} cells)"

    # 2. Check that cheaper modalities were tried first
    if len(justification.failed_modalities) < 1:
        return False, "REFUSE: no cheaper modality attempted before scRNA-seq"

    # 3. Check information gain per dollar
    # Info gain should be at least 0.2 bits per dollar to justify cost
    # (This is a placeholder heuristic; calibrate to your reward scale)
    info_per_dollar = justification.expected_information_gain / max(reagent_cost, 1e-6)
    if info_per_dollar < 2e-3:  # 0.002 bits/$
        return (
            False,
            f"REFUSE: poor expected info gain per cost ({info_per_dollar:.4f} < 0.002 bits/$)",
        )

    # 4. High drift requires replicate strategy
    if drift_score > 0.7:
        if justification.replicate_strategy is None or "replicate" not in justification.replicate_strategy.lower():
            return (
                False,
                f"REFUSE: high drift risk (score={drift_score:.2f}), scRNA without replicate plan is self-harm",
            )

    return True, "ALLOW"


def estimate_scRNA_info_gain(
    current_uncertainty: float,
    mechanism_ambiguity: float,
    viability: float,
) -> float:
    """
    Estimate expected information gain from scRNA-seq (bits).

    This is a placeholder heuristic. In a real system, this would:
    - Query your belief state posterior entropy
    - Estimate mutual information I(mechanisms; scRNA data | current belief)
    - Account for technical noise and batch effects

    Args:
        current_uncertainty: Entropy of current belief (bits)
        mechanism_ambiguity: How many plausible mechanisms remain
        viability: Cell viability (low viability = low scRNA quality)

    Returns:
        Estimated information gain (bits)
    """
    # Base gain: resolve mechanism ambiguity
    base_gain = mechanism_ambiguity * 1.5  # bits per mechanism

    # Scale by current uncertainty (more uncertain = more to gain)
    gain = base_gain * (current_uncertainty / 3.0)  # normalize to ~3 bits max

    # Penalize low viability (dead cells = noisy scRNA)
    if viability < 0.5:
        gain *= (viability / 0.5) ** 2

    return max(0.0, gain)
