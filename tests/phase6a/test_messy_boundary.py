"""
Messy boundary case test: where posterior either holds up or breaks.

Not the easy 0.96 case. The ugly 0.55 vs 0.55 tie with:
- Actin moderately up
- ER moderately up
- Mito moderately down
- High heterogeneity widening clouds
- Context and pipeline adding structured bias

This is where we find out if we're doing inference or cosplay.
"""

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext
from cell_os.hardware.mechanism_posterior_v2 import (
    compute_mechanism_posterior_v2,
    NuisanceModel,
    Mechanism,
    cosplay_detector_test
)
import numpy as np


def create_messy_boundary_case():
    """
    Engineer a messy case where multiple mechanisms plausible.

    Strategy:
    - Weak dose (partial engagement of multiple axes)
    - Strong context/pipeline bias (shifts features)
    - High heterogeneity (wide mixture)
    - Moderate timepoint (artifacts not fully decayed)
    """

    print("=== MESSY BOUNDARY CASE ===\n")
    print("Creating ambiguous scenario where multiple mechanisms plausible...")

    # Setup with strong context effects
    ctx = RunContext.sample(seed=999, config={'context_strength': 2.5})
    vm = BiologicalVirtualMachine(seed=888, run_context=ctx)
    vm.seed_vessel("test", "A549", 1e6)

    # Baseline
    baseline = vm.cell_painting_assay("test")
    baseline_actin = baseline['morphology_struct']['actin']
    baseline_mito = baseline['morphology_struct']['mito']
    baseline_er = baseline['morphology_struct']['er']

    print(f"Baseline: actin={baseline_actin:.1f}, mito={baseline_mito:.1f}, er={baseline_er:.1f}")

    # Treat with compound that has MIXED effects (weak multi-axis perturbation)
    # Use tunicamycin (ER) but with reduced potency to get partial signatures
    vm.treat_with_compound("test", "tunicamycin", dose_uM=0.4,
                          potency_scalar=0.5,  # Weak potency
                          toxicity_scalar=0.4)  # Moderate death

    # Measure at intermediate timepoint (artifacts partially present)
    vm.advance_time(14.0)  # Not 12h (too early) or 24h (too late)

    # Measure with batch/pipeline effects
    result = vm.cell_painting_assay("test", batch_id='batch_messy', plate_id='P_messy')
    vessel = vm.vessel_states["test"]

    # Get structural features (before viability scaling)
    actin_struct = result['morphology_struct']['actin']
    mito_struct = result['morphology_struct']['mito']
    er_struct = result['morphology_struct']['er']

    actin_fold = actin_struct / baseline_actin
    mito_fold = mito_struct / baseline_mito
    er_fold = er_struct / baseline_er

    print(f"\n@ 14h (messy boundary):")
    print(f"  Actin: {actin_struct:.1f} ({actin_fold:.3f}×) [expect 1.6 for micro, 1.0 for ER]")
    print(f"  Mito:  {mito_struct:.1f} ({mito_fold:.3f}×) [expect 1.0 for micro, 0.6 for mito]")
    print(f"  ER:    {er_struct:.1f} ({er_fold:.3f}×) [expect 1.0 for micro, 1.5 for ER]")
    print(f"  Viability: {vessel.viability:.3f}")

    # Get uncertainty budget
    transport_width = vessel.get_mixture_width('transport_dysfunction')
    er_width = vessel.get_mixture_width('er_stress')
    mito_width = vessel.get_mixture_width('mito_dysfunction')

    artifact_total = vessel.get_artifact_inflated_mixture_width('er_stress', vm.simulated_time)
    artifact_contrib = artifact_total - er_width

    print(f"\nUncertainty budget:")
    print(f"  Heterogeneity (ER axis): {er_width:.4f}")
    print(f"  Artifact contribution: {artifact_contrib:.4f}")
    print(f"  Transport heterogeneity: {transport_width:.4f}")
    print(f"  Mito heterogeneity: {mito_width:.4f}")

    # Get context/pipeline biases (from RunContext)
    bio_mods = ctx.get_biology_modifiers()
    meas_mods = ctx.get_measurement_modifiers()

    print(f"\nContext effects:")
    print(f"  EC50 multiplier: {bio_mods['ec50_multiplier']:.3f}")
    print(f"  Illumination bias: {meas_mods['illumination_bias']:.3f}")
    print(f"  Channel biases:")
    for ch in ['actin', 'mito', 'er']:
        print(f"    {ch}: {meas_mods['channel_biases'][ch]:.3f}×")

    # Build NuisanceModel with mean shifts from context/pipeline
    # Estimate mean shifts from channel biases (rough approximation)
    context_shift = np.array([
        (meas_mods['channel_biases']['actin'] - 1.0) * 0.2,  # Shift proportional to bias
        (meas_mods['channel_biases']['mito'] - 1.0) * 0.2,
        (meas_mods['channel_biases']['er'] - 1.0) * 0.2
    ])

    # Pipeline shift (batch-dependent, estimated)
    pipeline_shift = np.array([0.05, -0.03, 0.02])  # Arbitrary batch effect

    nuisance = NuisanceModel(
        context_shift=context_shift,
        pipeline_shift=pipeline_shift,
        artifact_var=artifact_contrib ** 2,
        heterogeneity_var=max(transport_width, er_width, mito_width) ** 2,
        context_var=0.15 ** 2,  # Estimated from RunContext biases
        pipeline_var=0.10 ** 2   # Estimated from batch effects
    )

    print(f"\nNuisance model:")
    print(f"  Mean shift (total): {nuisance.total_mean_shift}")
    print(f"  Variance inflation: {nuisance.total_var_inflation:.4f}")
    print(f"  Nuisance fraction: {nuisance.nuisance_fraction:.3f}")

    # Compute posterior
    posterior = compute_mechanism_posterior_v2(
        actin_fold=actin_fold,
        mito_fold=mito_fold,
        er_fold=er_fold,
        nuisance=nuisance
    )

    print(f"\n{'='*80}")
    print("POSTERIOR:")
    print("="*80)
    print(posterior.summary())

    # Analyze if this is actually ambiguous or if posterior hallucinates certainty
    print(f"\n{'='*80}")
    print("ANALYSIS:")
    print("="*80)

    top_prob = posterior.top_probability
    margin = posterior.margin
    entropy = posterior.entropy
    nuisance_frac = nuisance.nuisance_fraction

    print(f"Top probability: {top_prob:.3f}")
    print(f"Margin (top - second): {margin:.3f}")
    print(f"Entropy: {entropy:.3f}")
    print(f"Nuisance fraction: {nuisance_frac:.3f}")

    # Diagnostic: is this appropriately uncertain or hallucinated certainty?
    if top_prob > 0.8 and nuisance_frac > 0.5:
        verdict = "SUSPICIOUS CERTAINTY"
        explanation = "High confidence ({:.3f}) despite high nuisance ({:.1%}). Likely hallucinating certainty.".format(
            top_prob, nuisance_frac
        )
    elif top_prob < 0.6 and margin < 0.2:
        verdict = "APPROPRIATELY UNCERTAIN"
        explanation = "Low confidence ({:.3f}), small margin ({:.3f}). Correctly reports ambiguity.".format(
            top_prob, margin
        )
    elif top_prob > 0.7 and margin > 0.4:
        verdict = "CONFIDENT AND SEPARATED"
        explanation = "High confidence ({:.3f}), large margin ({:.3f}). Clear winner.".format(
            top_prob, margin
        )
    else:
        verdict = "MODERATE UNCERTAINTY"
        explanation = "Confidence {:.3f}, margin {:.3f}. Reasonable uncertainty given nuisance.".format(
            top_prob, margin
        )

    print(f"\nVerdict: {verdict}")
    print(f"Explanation: {explanation}")

    # Ground truth check
    true_mechanism = Mechanism.ER_STRESS  # We treated with tunicamycin
    predicted = posterior.top_mechanism

    print(f"\nGround truth: {true_mechanism.value}")
    print(f"Predicted: {predicted.value}")
    correct = (predicted == true_mechanism)
    print(f"Correct: {correct}")

    if correct and top_prob > 0.7:
        print("✓ Correct AND confident (good)")
    elif correct and top_prob < 0.6:
        print("≈ Correct but uncertain (appropriate given ambiguity)")
    elif not correct and top_prob > 0.7:
        print("✗ Wrong AND confident (bad! hallucinated certainty)")
    elif not correct and top_prob < 0.6:
        print("≈ Wrong but uncertain (at least honest about uncertainty)")

    return {
        'posterior': posterior,
        'nuisance': nuisance,
        'ground_truth': true_mechanism,
        'correct': correct,
        'verdict': verdict
    }


if __name__ == "__main__":
    # Load learned signatures
    import pickle
    from cell_os.hardware.mechanism_posterior_v2 import MECHANISM_SIGNATURES_V2

    try:
        with open('/Users/bjh/cell_OS/data/learned_mechanism_signatures_quick.pkl', 'rb') as f:
            learned_sigs = pickle.load(f)
        print("✓ Loaded learned signatures\n")
        MECHANISM_SIGNATURES_V2.update(learned_sigs)
    except FileNotFoundError:
        print("⚠ No learned signatures found, using defaults\n")

    # First run cosplay detector
    print("Step 1: Cosplay Detector Test")
    print("="*80)
    cosplay_passed = cosplay_detector_test()

    print("\n\n")
    print("Step 2: Messy Boundary Case")
    print("="*80)
    result = create_messy_boundary_case()

    print("\n\n" + "="*80)
    print("FINAL VERDICT:")
    print("="*80)
    if cosplay_passed:
        print("✓ Cosplay detector: PASSED (real likelihood evaluation)")
    else:
        print("✗ Cosplay detector: FAILED (still nearest-neighbor)")

    print(f"\nMessy boundary case: {result['verdict']}")
    print(f"Ground truth correct: {result['correct']}")

    if cosplay_passed and result['verdict'] in ['APPROPRIATELY UNCERTAIN', 'MODERATE UNCERTAINTY']:
        print("\n✓ SYSTEM BEHAVING LIKE REAL INFERENCE")
        print("  - Distinguishes covariance structure (not just centroids)")
        print("  - Reports appropriate uncertainty in ambiguous cases")
        print("  - Not hallucinating certainty when nuisance high")
    else:
        print("\n? SYSTEM NEEDS MORE SCRUTINY")
        print("  - Check if confidence matches actual correctness rate")
        print("  - Run calibration curve test (ECE, Brier)")
        print("  - Test on more boundary cases")
