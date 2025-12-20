"""
Diagnostic: Is 12h refusal genuine or planner blindness?

Test:
1. Treat with nocodazole (microtubule) at mid-dose
2. Measure actin at 6h, 12h, 18h, 24h
3. Decompose uncertainty budget at each timepoint
4. Show if waiting actually buys information
"""

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext
import numpy as np


def decompose_uncertainty_budget(vessel, simulated_time, baseline_actin):
    """
    Decompose confidence collapse into components.

    Returns dict with:
    - artifact_inflation: How much plating artifacts inflate mixture width
    - heterogeneity_width: Biological variance across subpopulations
    - total_width: Combined uncertainty
    - confidence: Resulting confidence (0-1)
    """
    # Get base mixture width (heterogeneity only)
    base_width = vessel.get_mixture_width('transport_dysfunction')

    # Get artifact-inflated width (heterogeneity + plating artifacts)
    inflated_width = vessel.get_artifact_inflated_mixture_width('transport_dysfunction', simulated_time)

    # Artifact contribution
    artifact_inflation = inflated_width - base_width

    # Confidence accounting (simplified)
    # Base confidence from axis separation (assume 0.80)
    base_confidence = 0.80

    # Penalty from mixture width
    width_penalty = min(1.0, inflated_width / 0.3)
    confidence = base_confidence * (1.0 - width_penalty)

    # Fraction explained by each source
    if inflated_width > 0:
        artifact_fraction = artifact_inflation / inflated_width
        bio_fraction = base_width / inflated_width
    else:
        artifact_fraction = 0.0
        bio_fraction = 1.0

    return {
        'base_width': base_width,
        'artifact_inflation': artifact_inflation,
        'total_width': inflated_width,
        'confidence': confidence,
        'artifact_fraction': artifact_fraction,
        'bio_fraction': bio_fraction
    }


def test_temporal_rescue():
    """Test if waiting from 12h to 24h actually rescues mechanism classification."""

    print("=== Temporal Rescue Test: 12h vs 24h ===\n")

    # Setup with Phase 5B realism
    ctx = RunContext.sample(seed=42)
    vm = BiologicalVirtualMachine(seed=42, run_context=ctx)
    vm.seed_vessel("test", "A549", 1e6)

    # Measure baseline
    baseline = vm.cell_painting_assay("test")
    baseline_actin_struct = baseline['morphology_struct']['actin']

    print(f"Baseline actin (structural): {baseline_actin_struct:.1f}\n")

    # Treat with nocodazole at mid-dose with reduced toxicity (keep cells alive)
    vm.treat_with_compound("test", "nocodazole", dose_uM=0.3, potency_scalar=0.8, toxicity_scalar=0.3)

    # Timeline: measure at 6h, 12h, 18h, 24h
    timepoints = [6, 12, 18, 24]
    results = []

    for t in timepoints:
        # Advance to timepoint
        dt = t - vm.simulated_time
        if dt > 0:
            vm.advance_time(dt)

        # Measure
        result = vm.cell_painting_assay("test", batch_id='batch_test', plate_id='P001')
        actin_struct = result['morphology_struct']['actin']
        actin_measured = result['morphology']['actin']
        actin_fold = actin_struct / baseline_actin_struct

        # Decompose uncertainty
        vessel = vm.vessel_states["test"]
        uncertainty = decompose_uncertainty_budget(vessel, vm.simulated_time, baseline_actin_struct)

        # Mechanism hit threshold
        mechanism_hit = actin_fold >= 1.4

        results.append({
            'time': t,
            'actin_struct': actin_struct,
            'actin_measured': actin_measured,
            'actin_fold': actin_fold,
            'mechanism_hit': mechanism_hit,
            'uncertainty': uncertainty,
            'viability': vessel.viability,
            'transport_dysfunction': vessel.transport_dysfunction
        })

        print(f"--- {t}h ---")
        print(f"Transport dysfunction (latent): {vessel.transport_dysfunction:.3f}")
        print(f"Actin structural: {actin_struct:.1f} ({actin_fold:.2f}× baseline)")
        print(f"Actin measured: {actin_measured:.1f}")
        print(f"Mechanism hit (≥1.4×): {mechanism_hit}")
        print(f"\nUncertainty budget:")
        print(f"  Biological heterogeneity: {uncertainty['base_width']:.3f} ({uncertainty['bio_fraction']:.1%})")
        print(f"  Plating artifact inflation: {uncertainty['artifact_inflation']:.3f} ({uncertainty['artifact_fraction']:.1%})")
        print(f"  Total mixture width: {uncertainty['total_width']:.3f}")
        print(f"  Confidence: {uncertainty['confidence']:.3f}")
        print(f"Viability: {vessel.viability:.3f}")
        print()

    # Analysis: Does waiting buy information?
    print("="*80)
    print("RESCUE ANALYSIS")
    print("="*80)

    r12 = results[1]  # 12h
    r24 = results[3]  # 24h

    print(f"\n12h → 24h comparison:")
    print(f"\nMechanism signal:")
    print(f"  Actin fold: {r12['actin_fold']:.3f} → {r24['actin_fold']:.3f} (Δ = {r24['actin_fold']-r12['actin_fold']:+.3f})")
    print(f"  Mechanism hit: {r12['mechanism_hit']} → {r24['mechanism_hit']}")

    print(f"\nUncertainty reduction:")
    print(f"  Artifact inflation: {r12['uncertainty']['artifact_inflation']:.3f} → {r24['uncertainty']['artifact_inflation']:.3f} "
          f"({(r24['uncertainty']['artifact_inflation']/r12['uncertainty']['artifact_inflation']-1)*100:+.1f}%)")
    print(f"  Total width: {r12['uncertainty']['total_width']:.3f} → {r24['uncertainty']['total_width']:.3f} "
          f"({(r24['uncertainty']['total_width']/r12['uncertainty']['total_width']-1)*100:+.1f}%)")
    print(f"  Confidence: {r12['uncertainty']['confidence']:.3f} → {r24['uncertainty']['confidence']:.3f} "
          f"(Δ = {r24['uncertainty']['confidence']-r12['uncertainty']['confidence']:+.3f})")

    print(f"\nCost of waiting:")
    print(f"  Time: +12h")
    print(f"  Viability cost: {r12['viability']:.3f} → {r24['viability']:.3f} (Δ = {r24['viability']-r12['viability']:+.3f})")

    # Verdict
    print(f"\n{'='*80}")
    print("VERDICT:")

    confidence_gain = r24['uncertainty']['confidence'] - r12['uncertainty']['confidence']
    mechanism_rescued = (not r12['mechanism_hit']) and r24['mechanism_hit']

    if confidence_gain > 0.1:
        print(f"✓ GENUINE AMBIGUITY at 12h")
        print(f"  Waiting to 24h gains +{confidence_gain:.3f} confidence")
        print(f"  Artifact decay explains {(1 - r24['uncertainty']['artifact_inflation']/r12['uncertainty']['artifact_inflation'])*100:.1f}% reduction")
        if mechanism_rescued:
            print(f"  Mechanism RESCUED by waiting")
    elif confidence_gain > 0.01:
        print(f"≈ MARGINAL IMPROVEMENT from waiting")
        print(f"  Confidence gain +{confidence_gain:.3f} (small but real)")
    else:
        print(f"✗ PLANNER BLINDNESS")
        print(f"  Waiting doesn't help (Δ confidence = {confidence_gain:+.3f})")
        print(f"  Refusal at 12h was not justified by temporal rescue")

    # Decompose variance sources at 12h
    print(f"\n{'='*80}")
    print("UNCERTAINTY DECOMPOSITION @ 12h:")
    print(f"  Plating artifacts: {r12['uncertainty']['artifact_fraction']:.1%} of total variance")
    print(f"  Biological heterogeneity: {r12['uncertainty']['bio_fraction']:.1%} of total variance")
    print(f"  (Context/pipeline drift: not yet decomposed, part of measurement noise)")

    return results


if __name__ == "__main__":
    results = test_temporal_rescue()

    print("\n✓ Temporal rescue diagnostic complete")
