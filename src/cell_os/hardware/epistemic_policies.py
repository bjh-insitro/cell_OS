"""
Phase 5: Epistemic Control - Baseline policies.

Three policies that demonstrate epistemic control tradeoffs:
1. Naive: dose high, wait long, classify late (violates death budget or gets noisy signatures)
2. Greedy: dose low, classify early (fails on weak signatures - forced guess under ambiguity)
3. Smart: probe at moderate dose, classify, commit based on axis (succeeds on all)
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from .biological_virtual import BiologicalVirtualMachine
from .masked_compound_phase5 import (
    Phase5Compound,
    infer_stress_axis_with_confidence,
    check_valid_attempt
)


@dataclass
class EpistemicReceipt:
    """
    Outcome of an epistemic control episode.

    Fields match Phase 5 reward structure.
    """
    predicted_axis: Optional[str]
    true_axis: str
    correct_axis: bool
    confidence: float

    # Mechanism engagement (for microtubule axis)
    mechanism_engaged: bool
    actin_fold_12h: float

    # Budget compliance
    death_48h: float
    viability_48h: float
    interventions_used: int
    valid_attempt: bool

    # Reward components
    reward_axis: float
    reward_mechanism: float
    reward_survival: float
    reward_parsimony: float
    reward_total: float

    # Diagnostic
    dose_schedule: List[float]
    assay_times: List[float]
    trajectory: List[Dict[str, Any]]


def compute_epistemic_reward(
    predicted_axis: Optional[str],
    true_axis: str,
    mechanism_engaged: bool,
    viability_48h: float,
    interventions_used: int,
    valid_attempt: bool,
    max_interventions: int = 2,
    death_tolerance: float = 0.20
) -> Tuple[float, Dict[str, float]]:
    """
    Compute Phase 5 epistemic control reward.

    Reward structure:
        +1.0 for correct axis identification
        +0.5 for mechanism engagement if microtubule axis
        +0.5 survival bonus (linear from 80% to 100% viability)
        +0.2 × unused_interventions (parsimony bonus)

    Survival and parsimony bonuses gated behind valid_attempt.

    Hard constraints (failure modes):
        - interventions > max_interventions: hard fail
        - viability < (1 - death_tolerance): hard fail

    Args:
        predicted_axis: Agent's prediction (or None if uncertain)
        true_axis: Ground truth axis
        mechanism_engaged: Whether mechanism target met (actin >1.4× at 12h for microtubule)
        viability_48h: Final viability (0-1)
        interventions_used: Number of interventions consumed
        valid_attempt: Whether agent made valid probe attempt
        max_interventions: Budget limit (default: 2)
        death_tolerance: Death budget (default: 0.20 = 80% viability minimum)

    Returns:
        (total_reward, components_dict)
    """
    # Hard constraint checks
    if interventions_used > max_interventions:
        # Budget violation: hard fail
        return -10.0, {
            'reward_axis': 0.0,
            'reward_mechanism': 0.0,
            'reward_survival': 0.0,
            'reward_parsimony': 0.0,
            'reward_total': -10.0,
            'failure_mode': 'budget_violation'
        }

    if viability_48h < (1.0 - death_tolerance):
        # Death tolerance violated: hard fail
        return -10.0, {
            'reward_axis': 0.0,
            'reward_mechanism': 0.0,
            'reward_survival': 0.0,
            'reward_parsimony': 0.0,
            'reward_total': -10.0,
            'failure_mode': 'death_violation'
        }

    # Reward components
    reward_axis = 1.0 if (predicted_axis == true_axis) else 0.0

    # Mechanism engagement bonus (only for microtubule axis)
    reward_mechanism = 0.0
    if true_axis == "microtubule" and mechanism_engaged:
        reward_mechanism = 0.5

    # Survival bonus: linear from 80% to 100%
    # Only awarded if valid_attempt is true (prevents "do nothing" attractor)
    if valid_attempt:
        # Map viability [0.8, 1.0] to reward [0.0, 0.5]
        survival_fraction = (viability_48h - 0.8) / 0.2
        reward_survival = 0.5 * np.clip(survival_fraction, 0.0, 1.0)
    else:
        reward_survival = 0.0

    # Parsimony bonus: 0.2 per unused intervention
    # Only awarded if valid_attempt is true
    if valid_attempt:
        unused = max_interventions - interventions_used
        reward_parsimony = 0.2 * unused
    else:
        reward_parsimony = 0.0

    reward_total = reward_axis + reward_mechanism + reward_survival + reward_parsimony

    components = {
        'reward_axis': reward_axis,
        'reward_mechanism': reward_mechanism,
        'reward_survival': reward_survival,
        'reward_parsimony': reward_parsimony,
        'reward_total': reward_total,
        'failure_mode': None
    }

    return reward_total, components


def run_naive_policy(
    phase5_compound: Phase5Compound,
    cell_line: str = "A549",
    seed: int = 42
) -> EpistemicReceipt:
    """
    Naive policy: Dose high (1.0×), wait 48h, classify from late readout.

    Expected failure mode:
        - High dose over 48h violates death budget (>20% death)
        - OR late signatures are noisy/confounded (misclassification)

    Strategy:
        - Dose 1.0× at t=0
        - No interventions (no washout, no feed)
        - Assay at t=48h
        - Classify from final signatures

    This is the "brute force" approach that ignores temporal structure.
    """
    vm = BiologicalVirtualMachine(seed=seed)
    vm.seed_vessel("test", cell_line, 1e6, capacity=1e7, initial_viability=0.98)

    # Measure baseline
    baseline_result = vm.cell_painting_assay("test")
    baseline_struct = baseline_result['morphology_struct']
    baseline_scalars = vm.atp_viability_assay("test")

    baseline_er = baseline_struct['er']
    baseline_mito = baseline_struct['mito']
    baseline_actin = baseline_struct['actin']
    baseline_upr = baseline_scalars['upr_marker']
    baseline_atp = baseline_scalars['atp_signal']
    baseline_trafficking = baseline_scalars['trafficking_marker']

    # Dose high (1.0×) at t=0
    dose_uM = 1.0 * phase5_compound.reference_dose_uM
    vm.treat_with_compound(
        "test",
        phase5_compound.compound_name,
        dose_uM=dose_uM,
        potency_scalar=phase5_compound.potency_scalar,
        toxicity_scalar=phase5_compound.toxicity_scalar
    )

    # Advance to 48h in 6h steps for numerical accuracy
    trajectory = []
    for step in range(8):  # 8 × 6h = 48h
        vm.advance_time(6.0)
        vessel = vm.vessel_states["test"]
        trajectory.append({
            'time_h': vm.simulated_time,
            'viability': vessel.viability,
            'transport_dysfunction': vessel.transport_dysfunction,
            'er_stress': vessel.er_stress,
            'mito_dysfunction': vessel.mito_dysfunction
        })

    # Assay at 48h
    result = vm.cell_painting_assay("test")
    morph_struct = result['morphology_struct']
    scalars = vm.atp_viability_assay("test")

    # Compute fold-changes
    er_fold = morph_struct['er'] / baseline_er
    mito_fold = morph_struct['mito'] / baseline_mito
    actin_fold = morph_struct['actin'] / baseline_actin
    upr_fold = scalars['upr_marker'] / baseline_upr
    atp_fold = scalars['atp_signal'] / baseline_atp
    trafficking_fold = scalars['trafficking_marker'] / baseline_trafficking

    # Classify axis
    predicted_axis, confidence = infer_stress_axis_with_confidence(
        er_fold=er_fold,
        mito_fold=mito_fold,
        actin_fold=actin_fold,
        upr_fold=upr_fold,
        atp_fold=atp_fold,
        trafficking_fold=trafficking_fold
    )

    # Check mechanism engagement (actin at 12h)
    # Naive didn't measure at 12h, so use placeholder
    actin_fold_12h = 0.0  # Not measured
    mechanism_engaged = False

    # Final state
    vessel = vm.vessel_states["test"]
    viability_48h = vessel.viability
    death_48h = 1.0 - viability_48h

    # No interventions used (no washout, no feed)
    interventions_used = 0

    # Check valid attempt
    dose_schedule = [1.0] + [0.0] * 7  # Dosed at step 0, maintained
    assay_times = [48.0]
    valid_attempt = check_valid_attempt(dose_schedule, assay_times)

    # Compute reward
    reward_total, components = compute_epistemic_reward(
        predicted_axis=predicted_axis,
        true_axis=phase5_compound.true_stress_axis,
        mechanism_engaged=mechanism_engaged,
        viability_48h=viability_48h,
        interventions_used=interventions_used,
        valid_attempt=valid_attempt
    )

    return EpistemicReceipt(
        predicted_axis=predicted_axis,
        true_axis=phase5_compound.true_stress_axis,
        correct_axis=(predicted_axis == phase5_compound.true_stress_axis),
        confidence=confidence,
        mechanism_engaged=mechanism_engaged,
        actin_fold_12h=actin_fold_12h,
        death_48h=death_48h,
        viability_48h=viability_48h,
        interventions_used=interventions_used,
        valid_attempt=valid_attempt,
        reward_axis=components['reward_axis'],
        reward_mechanism=components['reward_mechanism'],
        reward_survival=components['reward_survival'],
        reward_parsimony=components['reward_parsimony'],
        reward_total=reward_total,
        dose_schedule=dose_schedule,
        assay_times=assay_times,
        trajectory=trajectory
    )


def run_greedy_policy(
    phase5_compound: Phase5Compound,
    cell_line: str = "A549",
    seed: int = 42
) -> EpistemicReceipt:
    """
    Greedy policy: Dose low (0.25×), classify at 12h from weak signatures.

    Expected failure mode:
        - Weak compounds have ambiguous signatures at 12h
        - Forced to guess under low confidence
        - Misclassification

    Strategy:
        - Dose 0.25× at t=0
        - Assay at t=12h
        - Classify from early signatures (likely ambiguous for weak compounds)
        - No further interventions

    This is the "impatient" approach that ignores temporal dynamics.
    """
    vm = BiologicalVirtualMachine(seed=seed)
    vm.seed_vessel("test", cell_line, 1e6, capacity=1e7, initial_viability=0.98)

    # Measure baseline
    baseline_result = vm.cell_painting_assay("test")
    baseline_struct = baseline_result['morphology_struct']
    baseline_scalars = vm.atp_viability_assay("test")

    baseline_er = baseline_struct['er']
    baseline_mito = baseline_struct['mito']
    baseline_actin = baseline_struct['actin']
    baseline_upr = baseline_scalars['upr_marker']
    baseline_atp = baseline_scalars['atp_signal']
    baseline_trafficking = baseline_scalars['trafficking_marker']

    # Dose low (0.25×) at t=0
    dose_uM = 0.25 * phase5_compound.reference_dose_uM
    vm.treat_with_compound(
        "test",
        phase5_compound.compound_name,
        dose_uM=dose_uM,
        potency_scalar=phase5_compound.potency_scalar,
        toxicity_scalar=phase5_compound.toxicity_scalar
    )

    # Advance to 12h in 6h steps
    trajectory = []
    for step in range(2):  # 2 × 6h = 12h
        vm.advance_time(6.0)
        vessel = vm.vessel_states["test"]
        trajectory.append({
            'time_h': vm.simulated_time,
            'viability': vessel.viability,
            'transport_dysfunction': vessel.transport_dysfunction,
            'er_stress': vessel.er_stress,
            'mito_dysfunction': vessel.mito_dysfunction
        })

    # Assay at 12h
    result = vm.cell_painting_assay("test")
    morph_struct = result['morphology_struct']
    scalars = vm.atp_viability_assay("test")

    # Compute fold-changes
    er_fold = morph_struct['er'] / baseline_er
    mito_fold = morph_struct['mito'] / baseline_mito
    actin_fold = morph_struct['actin'] / baseline_actin
    upr_fold = scalars['upr_marker'] / baseline_upr
    atp_fold = scalars['atp_signal'] / baseline_atp
    trafficking_fold = scalars['trafficking_marker'] / baseline_trafficking

    # Classify axis
    predicted_axis, confidence = infer_stress_axis_with_confidence(
        er_fold=er_fold,
        mito_fold=mito_fold,
        actin_fold=actin_fold,
        upr_fold=upr_fold,
        atp_fold=atp_fold,
        trafficking_fold=trafficking_fold
    )

    # Check mechanism engagement (actin at 12h)
    actin_fold_12h = actin_fold
    mechanism_engaged = (actin_fold_12h >= 1.35 and phase5_compound.true_stress_axis == "microtubule")

    # Continue to 48h (no further intervention)
    for step in range(6):  # 6 × 6h = 36h more, total 48h
        vm.advance_time(6.0)
        vessel = vm.vessel_states["test"]
        trajectory.append({
            'time_h': vm.simulated_time,
            'viability': vessel.viability,
            'transport_dysfunction': vessel.transport_dysfunction,
            'er_stress': vessel.er_stress,
            'mito_dysfunction': vessel.mito_dysfunction
        })

    # Final state
    vessel = vm.vessel_states["test"]
    viability_48h = vessel.viability
    death_48h = 1.0 - viability_48h

    # No interventions used
    interventions_used = 0

    # Check valid attempt
    dose_schedule = [0.25] + [0.0] * 7
    assay_times = [12.0]
    valid_attempt = check_valid_attempt(dose_schedule, assay_times)

    # Compute reward
    reward_total, components = compute_epistemic_reward(
        predicted_axis=predicted_axis,
        true_axis=phase5_compound.true_stress_axis,
        mechanism_engaged=mechanism_engaged,
        viability_48h=viability_48h,
        interventions_used=interventions_used,
        valid_attempt=valid_attempt
    )

    return EpistemicReceipt(
        predicted_axis=predicted_axis,
        true_axis=phase5_compound.true_stress_axis,
        correct_axis=(predicted_axis == phase5_compound.true_stress_axis),
        confidence=confidence,
        mechanism_engaged=mechanism_engaged,
        actin_fold_12h=actin_fold_12h,
        death_48h=death_48h,
        viability_48h=viability_48h,
        interventions_used=interventions_used,
        valid_attempt=valid_attempt,
        reward_axis=components['reward_axis'],
        reward_mechanism=components['reward_mechanism'],
        reward_survival=components['reward_survival'],
        reward_parsimony=components['reward_parsimony'],
        reward_total=reward_total,
        dose_schedule=dose_schedule,
        assay_times=assay_times,
        trajectory=trajectory
    )


def run_smart_policy(
    phase5_compound: Phase5Compound,
    cell_line: str = "A549",
    seed: int = 42
) -> EpistemicReceipt:
    """
    Smart policy: Probe at moderate dose (0.5×) to 12h, classify, commit based on axis.

    Strategy:
        1. Probe phase: dose 0.5× to 12h, assay, classify
        2. Commit phase:
           - If microtubule: continue to 24h for mechanism engagement, then washout
           - If ER or mito: washout immediately at 12h (no mechanism target)

    This uses 1 intervention (washout) and succeeds on all compounds:
        - Moderate dose disambiguates weak signatures by 12h
        - Targeted washout prevents death budget violation
        - Stays within 2-intervention budget

    Expected outcome:
        - Correct axis identification
        - Mechanism engaged if microtubule
        - Death < 20%
        - 1-2 interventions used
        - High reward
    """
    vm = BiologicalVirtualMachine(seed=seed)
    vm.seed_vessel("test", cell_line, 1e6, capacity=1e7, initial_viability=0.98)

    # Measure baseline
    baseline_result = vm.cell_painting_assay("test")
    baseline_struct = baseline_result['morphology_struct']
    baseline_scalars = vm.atp_viability_assay("test")

    baseline_er = baseline_struct['er']
    baseline_mito = baseline_struct['mito']
    baseline_actin = baseline_struct['actin']
    baseline_upr = baseline_scalars['upr_marker']
    baseline_atp = baseline_scalars['atp_signal']
    baseline_trafficking = baseline_scalars['trafficking_marker']

    # PROBE PHASE: Dose moderate (0.5×) at t=0
    dose_uM = 0.5 * phase5_compound.reference_dose_uM
    vm.treat_with_compound(
        "test",
        phase5_compound.compound_name,
        dose_uM=dose_uM,
        potency_scalar=phase5_compound.potency_scalar,
        toxicity_scalar=phase5_compound.toxicity_scalar
    )

    # Advance to 12h
    trajectory = []
    for step in range(2):  # 2 × 6h = 12h
        vm.advance_time(6.0)
        vessel = vm.vessel_states["test"]
        trajectory.append({
            'time_h': vm.simulated_time,
            'viability': vessel.viability,
            'transport_dysfunction': vessel.transport_dysfunction,
            'er_stress': vessel.er_stress,
            'mito_dysfunction': vessel.mito_dysfunction
        })

    # Assay at 12h
    result = vm.cell_painting_assay("test")
    morph_struct = result['morphology_struct']
    scalars = vm.atp_viability_assay("test")

    # Compute fold-changes
    er_fold = morph_struct['er'] / baseline_er
    mito_fold = morph_struct['mito'] / baseline_mito
    actin_fold = morph_struct['actin'] / baseline_actin
    upr_fold = scalars['upr_marker'] / baseline_upr
    atp_fold = scalars['atp_signal'] / baseline_atp
    trafficking_fold = scalars['trafficking_marker'] / baseline_trafficking

    # Classify axis
    predicted_axis, confidence = infer_stress_axis_with_confidence(
        er_fold=er_fold,
        mito_fold=mito_fold,
        actin_fold=actin_fold,
        upr_fold=upr_fold,
        atp_fold=atp_fold,
        trafficking_fold=trafficking_fold
    )

    # Check mechanism engagement at 12h
    actin_fold_12h = actin_fold
    mechanism_engaged = (actin_fold_12h >= 1.35 and predicted_axis == "microtubule")

    # COMMIT PHASE: Decision based on predicted axis
    interventions_used = 0

    if predicted_axis == "microtubule":
        # Continue dosing to 24h for mechanism engagement, then washout
        for step in range(2):  # 2 × 6h = 12h more, total 24h
            vm.advance_time(6.0)
            vessel = vm.vessel_states["test"]
            trajectory.append({
                'time_h': vm.simulated_time,
                'viability': vessel.viability,
                'transport_dysfunction': vessel.transport_dysfunction,
                'er_stress': vessel.er_stress,
                'mito_dysfunction': vessel.mito_dysfunction
            })

        # Washout at 24h
        vm.washout_compound("test", phase5_compound.compound_name)
        interventions_used += 1

        # Continue to 48h
        for step in range(4):  # 4 × 6h = 24h more, total 48h
            vm.advance_time(6.0)
            vessel = vm.vessel_states["test"]
            trajectory.append({
                'time_h': vm.simulated_time,
                'viability': vessel.viability,
                'transport_dysfunction': vessel.transport_dysfunction,
                'er_stress': vessel.er_stress,
                'mito_dysfunction': vessel.mito_dysfunction
            })

    else:
        # ER or mito: washout immediately at 12h
        vm.washout_compound("test", phase5_compound.compound_name)
        interventions_used += 1

        # Continue to 48h (recovery)
        for step in range(6):  # 6 × 6h = 36h more, total 48h
            vm.advance_time(6.0)
            vessel = vm.vessel_states["test"]
            trajectory.append({
                'time_h': vm.simulated_time,
                'viability': vessel.viability,
                'transport_dysfunction': vessel.transport_dysfunction,
                'er_stress': vessel.er_stress,
                'mito_dysfunction': vessel.mito_dysfunction
            })

    # Final state
    vessel = vm.vessel_states["test"]
    viability_48h = vessel.viability
    death_48h = 1.0 - viability_48h

    # Check valid attempt
    if predicted_axis == "microtubule":
        dose_schedule = [0.5, 0.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0]  # Dosed at 0h, maintained to 12h, dosed again to 24h
    else:
        dose_schedule = [0.5, 0.0] + [0.0] * 6  # Dosed at 0h, maintained to 12h, then washed out
    assay_times = [12.0]
    valid_attempt = check_valid_attempt(dose_schedule, assay_times)

    # Compute reward
    reward_total, components = compute_epistemic_reward(
        predicted_axis=predicted_axis,
        true_axis=phase5_compound.true_stress_axis,
        mechanism_engaged=mechanism_engaged,
        viability_48h=viability_48h,
        interventions_used=interventions_used,
        valid_attempt=valid_attempt
    )

    return EpistemicReceipt(
        predicted_axis=predicted_axis,
        true_axis=phase5_compound.true_stress_axis,
        correct_axis=(predicted_axis == phase5_compound.true_stress_axis),
        confidence=confidence,
        mechanism_engaged=mechanism_engaged,
        actin_fold_12h=actin_fold_12h,
        death_48h=death_48h,
        viability_48h=viability_48h,
        interventions_used=interventions_used,
        valid_attempt=valid_attempt,
        reward_axis=components['reward_axis'],
        reward_mechanism=components['reward_mechanism'],
        reward_survival=components['reward_survival'],
        reward_parsimony=components['reward_parsimony'],
        reward_total=reward_total,
        dose_schedule=dose_schedule,
        assay_times=assay_times,
        trajectory=trajectory
    )
