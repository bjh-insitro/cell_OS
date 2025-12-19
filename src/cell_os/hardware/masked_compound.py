"""
Phase 4 Option 2: Masked compounds and exploration pressure.

Forces agents to explore by hiding compound stress_axis.
Agent must infer axis from assay signatures (structural + scalars).

Reward includes information bonus for correct axis identification.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import numpy as np


@dataclass
class MaskedCompound:
    """
    Compound with hidden stress axis.

    Agent sees only:
    - compound_id: Anonymous identifier (e.g., "compound_A")
    - dose: Dose in µM

    Hidden from agent:
    - true_stress_axis: Ground truth ("er_stress", "mitochondrial", "microtubule")
    - compound_name: Real compound name (e.g., "tunicamycin")

    Agent must infer stress_axis from assay signatures.
    """
    compound_id: str
    true_stress_axis: str
    compound_name: str
    reference_dose_uM: float

    def __str__(self):
        return f"MaskedCompound(id={self.compound_id}, hidden_axis={self.true_stress_axis})"


# Standard masked compound library
MASKED_COMPOUND_LIBRARY: Dict[str, MaskedCompound] = {
    "compound_A": MaskedCompound(
        compound_id="compound_A",
        true_stress_axis="er_stress",
        compound_name="tunicamycin",
        reference_dose_uM=0.5
    ),
    "compound_B": MaskedCompound(
        compound_id="compound_B",
        true_stress_axis="mitochondrial",
        compound_name="cccp",
        reference_dose_uM=1.0
    ),
    "compound_C": MaskedCompound(
        compound_id="compound_C",
        true_stress_axis="microtubule",
        compound_name="paclitaxel",
        reference_dose_uM=0.005
    )
}


def infer_stress_axis_from_signatures(
    er_fold: float,
    mito_fold: float,
    actin_fold: float,
    upr_fold: float,
    atp_fold: float,
    trafficking_fold: float
) -> str:
    """
    Infer stress axis from assay signatures using rule-based classifier.

    Same classifier as identifiability tests (Phase 3).

    Args:
        *_fold: Fold-change from baseline (structural + scalars)

    Returns:
        Predicted stress axis: "er_stress", "mitochondrial", or "microtubule"

    Raises:
        ValueError: If signatures are ambiguous (control-like or multiple axes active)
    """
    # ER stress: UPR high (>30%) AND ER_struct up (>30%)
    er_signature = (upr_fold > 1.30 and er_fold > 1.30)

    # Mito dysfunction: ATP low (<85%) OR (ATP low (<90%) AND Mito_struct down (<95%))
    mito_signature = (atp_fold < 0.85 or (atp_fold < 0.90 and mito_fold < 0.95))

    # Transport dysfunction: Trafficking high (>30%) AND Actin_struct up (>30%)
    transport_signature = (trafficking_fold > 1.30 and actin_fold > 1.30)

    # Check for ambiguity
    active_count = sum([er_signature, mito_signature, transport_signature])

    if active_count == 0:
        raise ValueError("No clear signature detected (control-like)")
    elif active_count > 1:
        raise ValueError(f"Ambiguous signatures (multiple axes active: "
                         f"ER={er_signature}, Mito={mito_signature}, Transport={transport_signature})")

    # Return predicted axis
    if er_signature:
        return "er_stress"
    elif mito_signature:
        return "mitochondrial"
    elif transport_signature:
        return "microtubule"
    else:
        raise ValueError("Internal error: no signature matched despite active_count==1")


def compute_exploration_reward(
    mechanism_hit: bool,
    viability_48h: float,
    washout_count: int,
    feed_count: int,
    predicted_axis: Optional[str],
    true_axis: str,
    lambda_dead: float = 2.0,
    lambda_ops: float = 0.1,
    lambda_info: float = 0.5
) -> Tuple[float, Dict[str, float]]:
    """
    Multi-objective reward with information bonus for correct axis identification.

    Reward = mechanism_hit - death_penalty - ops_cost + info_bonus

    where:
    - mechanism_hit = 1.0 if actin target met (handled externally)
    - death_penalty = lambda_dead × (1 - viability_48h)²
    - ops_cost = lambda_ops × (washout_count + feed_count)
    - info_bonus = lambda_info if predicted_axis == true_axis else 0

    The info_bonus encourages exploration: agent must run assays to classify axis.

    Args:
        mechanism_hit: Whether mechanism target was hit (binary)
        viability_48h: Viability at 48h (0-1)
        washout_count: Number of washouts
        feed_count: Number of feeds
        predicted_axis: Agent's prediction (or None if no prediction)
        true_axis: Ground truth stress axis
        lambda_dead: Death penalty coefficient
        lambda_ops: Ops cost coefficient
        lambda_info: Information bonus coefficient

    Returns:
        (total_reward, components_dict) tuple
    """
    # Base reward components (same as Phase 3)
    reward_mechanism = 1.0 if mechanism_hit else 0.0
    total_dead_48h = 1.0 - viability_48h
    reward_death_penalty = -lambda_dead * (total_dead_48h ** 2)
    reward_ops_cost = -lambda_ops * (washout_count + feed_count)

    # Information bonus (new for exploration)
    if predicted_axis is None:
        reward_info_bonus = 0.0  # No prediction made
    elif predicted_axis == true_axis:
        reward_info_bonus = lambda_info  # Correct identification
    else:
        reward_info_bonus = -lambda_info  # Incorrect identification (penalty)

    # Total reward
    total_reward = reward_mechanism + reward_death_penalty + reward_ops_cost + reward_info_bonus

    # Components for diagnostic logging
    components = {
        'reward_mechanism': reward_mechanism,
        'reward_death_penalty': reward_death_penalty,
        'reward_ops_cost': reward_ops_cost,
        'reward_info_bonus': reward_info_bonus,
        'reward_total': total_reward,
        'mechanism_hit': mechanism_hit,
        'total_dead_48h': total_dead_48h,
        'ops_count': washout_count + feed_count,
        'axis_prediction_correct': (predicted_axis == true_axis) if predicted_axis is not None else None
    }

    return total_reward, components


def exploration_policy_template(
    vm,
    vessel_id: str,
    masked_compound: MaskedCompound,
    dose_fraction: float = 1.0
) -> Tuple[str, Dict]:
    """
    Template for exploration policy: dose early, assay at 12h, classify axis.

    This is a reference implementation showing how to use masked compounds.

    Args:
        vm: BiologicalVirtualMachine instance
        vessel_id: Vessel to treat
        masked_compound: Masked compound (axis hidden from agent)
        dose_fraction: Dose fraction (default: 1.0×)

    Returns:
        (predicted_axis, assay_data) tuple
    """
    # Get baseline
    baseline_result = vm.cell_painting_assay(vessel_id)
    baseline_struct = baseline_result['morphology_struct']
    baseline_scalars = vm.atp_viability_assay(vessel_id)

    baseline_er = baseline_struct['er']
    baseline_mito = baseline_struct['mito']
    baseline_actin = baseline_struct['actin']
    baseline_upr = baseline_scalars['upr_marker']
    baseline_atp = baseline_scalars['atp_signal']
    baseline_trafficking = baseline_scalars['trafficking_marker']

    # Apply masked compound (agent doesn't know axis)
    dose_uM = dose_fraction * masked_compound.reference_dose_uM
    vm.treat_with_compound(vessel_id, masked_compound.compound_name, dose_uM=dose_uM)

    # Advance to 12h (exploration window)
    vm.advance_time(12.0)

    # Run assays to classify axis
    result = vm.cell_painting_assay(vessel_id)
    morph_struct = result['morphology_struct']
    scalars = vm.atp_viability_assay(vessel_id)

    # Compute fold-changes
    er_fold = morph_struct['er'] / baseline_er
    mito_fold = morph_struct['mito'] / baseline_mito
    actin_fold = morph_struct['actin'] / baseline_actin
    upr_fold = scalars['upr_marker'] / baseline_upr
    atp_fold = scalars['atp_signal'] / baseline_atp
    trafficking_fold = scalars['trafficking_marker'] / baseline_trafficking

    # Infer axis
    try:
        predicted_axis = infer_stress_axis_from_signatures(
            er_fold=er_fold,
            mito_fold=mito_fold,
            actin_fold=actin_fold,
            upr_fold=upr_fold,
            atp_fold=atp_fold,
            trafficking_fold=trafficking_fold
        )
    except ValueError as e:
        # Classification failed (ambiguous or control-like)
        predicted_axis = None
        print(f"Warning: Axis classification failed: {e}")

    # Return prediction and assay data
    assay_data = {
        'er_fold': er_fold,
        'mito_fold': mito_fold,
        'actin_fold': actin_fold,
        'upr_fold': upr_fold,
        'atp_fold': atp_fold,
        'trafficking_fold': trafficking_fold,
        'predicted_axis': predicted_axis,
        'true_axis': masked_compound.true_stress_axis
    }

    return predicted_axis, assay_data
