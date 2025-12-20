"""
Context Mimic Test: The teeth check.

Test if "non-ER mechanism + context shift" can fool posterior into thinking it's ER.

If posterior stays at P(ER)=0.90 when context created the ER signal,
we've proven the exact failure mode we care about.

Expected behavior:
- Posterior should spread mass (uncertain), OR
- Calibrated confidence should drop due to high nuisance_fraction

Failure mode: stays confident despite nuisance creating the signal.
"""

import numpy as np
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext


def create_context_mimic():
    """
    Create case where context shift mimics ER signature.

    Setup:
    - Use MICROTUBULE compound (nocodazole)
    - Add strong UPWARD context bias on ER channel
    - Result: ER channel increased, but NOT from ER stress mechanism

    Question: Does posterior attribute this to ER mechanism or to context?
    """

    print("="*80)
    print("CONTEXT MIMIC TEST: Can nuisance fool the posterior?")
    print("="*80)

    print("\nSetup:")
    print("- Compound: nocodazole (MICROTUBULE mechanism)")
    print("- Context: STRONG upward bias on ER channel")
    print("- Expected: actin up (true), ER up (fake from context)")
    print("- Question: Does posterior say 'ER mechanism' or detect context?")

    # Create context with strong ER channel bias
    # Normally RunContext samples randomly, but we want specific bias
    ctx = RunContext.sample(seed=12345)

    # Manually modify ER channel bias (simulate cursed day with ER reagent lot issue)
    ctx.reagent_lot_shift['er'] = 0.35  # Strong upward bias (35% increase)

    meas_mods = ctx.get_measurement_modifiers()
    print(f"\nContext modifiers:")
    print(f"  ER channel bias: {meas_mods['channel_biases']['er']:.3f}× (STRONG UPWARD)")
    print(f"  Actin channel bias: {meas_mods['channel_biases']['actin']:.3f}×")
    print(f"  Mito channel bias: {meas_mods['channel_biases']['mito']:.3f}×")

    # Run experiment
    vm = BiologicalVirtualMachine(seed=42, run_context=ctx)
    vm.seed_vessel("test", "A549", 1e6)

    baseline = vm.cell_painting_assay("test")
    baseline_actin = baseline['morphology_struct']['actin']
    baseline_mito = baseline['morphology_struct']['mito']
    baseline_er = baseline['morphology_struct']['er']

    # Treat with MICROTUBULE compound
    vm.treat_with_compound("test", "nocodazole", dose_uM=0.3, potency_scalar=0.8, toxicity_scalar=0.3)
    vm.advance_time(12.0)

    result = vm.cell_painting_assay("test", batch_id='batch_mimic', plate_id='P_mimic')
    vessel = vm.vessel_states["test"]

    # Get structural (before context/pipeline) and measured (after) features
    actin_struct = result['morphology_struct']['actin']
    mito_struct = result['morphology_struct']['mito']
    er_struct = result['morphology_struct']['er']

    actin_measured = result['morphology']['actin']
    mito_measured = result['morphology']['mito']
    er_measured = result['morphology']['er']

    actin_fold_struct = actin_struct / baseline_actin
    mito_fold_struct = mito_struct / baseline_mito
    er_fold_struct = er_struct / baseline_er

    actin_fold_measured = actin_measured / baseline['morphology']['actin']
    mito_fold_measured = mito_measured / baseline['morphology']['mito']
    er_fold_measured = er_measured / baseline['morphology']['er']

    print(f"\n@ 12h results:")
    print(f"\nStructural (TRUE biology, before context):")
    print(f"  Actin: {actin_fold_struct:.3f}× [expect 1.6 for microtubule]")
    print(f"  Mito:  {mito_fold_struct:.3f}× [expect 1.0 for microtubule]")
    print(f"  ER:    {er_fold_struct:.3f}× [expect 1.0 for microtubule]")

    print(f"\nMeasured (OBSERVED, after context bias):")
    print(f"  Actin: {actin_fold_measured:.3f}×")
    print(f"  Mito:  {mito_fold_measured:.3f}×")
    print(f"  ER:    {er_fold_measured:.3f}× [INFLATED by context!]")

    print(f"\nContext effect on ER:")
    print(f"  True ER: {er_fold_struct:.3f}×")
    print(f"  Measured ER: {er_fold_measured:.3f}×")
    print(f"  Context added: {er_fold_measured - er_fold_struct:+.3f}×")

    # Now test old threshold classifier
    print(f"\n{'='*80}")
    print("OLD THRESHOLD CLASSIFIER:")
    print("="*80)

    # Old way: just look at which channel increased most
    channels = {'actin': actin_fold_measured, 'mito': mito_fold_measured, 'er': er_fold_measured}
    max_channel = max(channels, key=channels.get)
    mechanism_guess = {
        'actin': 'MICROTUBULE',
        'er': 'ER_STRESS',
        'mito': 'MITOCHONDRIAL'
    }[max_channel]

    print(f"Max channel: {max_channel} ({channels[max_channel]:.3f}×)")
    print(f"Classification: {mechanism_guess}")
    print(f"Ground truth: MICROTUBULE")

    if mechanism_guess != 'MICROTUBULE':
        print(f"✗ WRONG: Fooled by context bias")
        print(f"  Context made ER look high → misclassified as ER stress")
    else:
        print(f"✓ Correct despite context")

    # What SHOULD happen with proper posterior + nuisance model
    print(f"\n{'='*80}")
    print("WHAT PROPER POSTERIOR SHOULD DO:")
    print("="*80)
    print("1. See ER elevated (1.3×)")
    print("2. Check nuisance_fraction (high due to context)")
    print("3. Either:")
    print("   a) Spread mass: P(MICRO)=0.5, P(ER)=0.5 (uncertain)")
    print("   b) Attribute to MICRO but low calibrated confidence")
    print("   c) Explicitly model context shift in mean")
    print("\nFailure mode: P(ER)=0.90 (overconfident, fooled by context)")

    return {
        'true_mechanism': 'MICROTUBULE',
        'measured_features': [actin_fold_measured, mito_fold_measured, er_fold_measured],
        'structural_features': [actin_fold_struct, mito_fold_struct, er_fold_struct],
        'threshold_guess': mechanism_guess,
        'context_er_bias': meas_mods['channel_biases']['er']
    }


def test_posterior_with_context_mimic(result):
    """
    Test if posterior can handle context mimic.

    This requires:
    - Learned signatures with per-mechanism covariance
    - Nuisance model with mean shifts (not just variance inflation)
    - Posterior that accounts for context when computing likelihoods
    """
    import pickle
    from cell_os.hardware.mechanism_posterior_v2 import (
        compute_mechanism_posterior_v2,
        NuisanceModel,
        Mechanism,
        MECHANISM_SIGNATURES_V2
    )

    print("\n\n" + "="*80)
    print("PROPER POSTERIOR TEST (with learned signatures)")
    print("="*80)

    # Load learned signatures
    try:
        with open('/Users/bjh/cell_OS/data/learned_mechanism_signatures_quick.pkl', 'rb') as f:
            learned_sigs = pickle.load(f)
        print("✓ Loaded learned signatures")

        # Update global signatures to use learned ones
        MECHANISM_SIGNATURES_V2.update(learned_sigs)
    except FileNotFoundError:
        print("⚠ No learned signatures found, using defaults")

    # Get features
    actin_fold, mito_fold, er_fold = result['measured_features']
    actin_struct, mito_struct, er_struct = result['structural_features']
    context_er_bias = result['context_er_bias']

    print(f"\nMeasured features (with context bias):")
    print(f"  actin={actin_fold:.3f}, mito={mito_fold:.3f}, er={er_fold:.3f}")
    print(f"\nStructural features (true biology):")
    print(f"  actin={actin_struct:.3f}, mito={mito_struct:.3f}, er={er_struct:.3f}")

    # Build nuisance model with context shift
    # Context shifted ER channel up by context_er_bias - 1.0
    context_shift = np.array([0.0, 0.0, context_er_bias - 1.0])

    nuisance = NuisanceModel(
        context_shift=context_shift,
        pipeline_shift=np.array([0.0, 0.0, 0.0]),
        artifact_var=0.01,
        heterogeneity_var=0.04,
        context_var=0.15 ** 2,
        pipeline_var=0.10 ** 2
    )

    print(f"\nNuisance model:")
    print(f"  Context shift: {nuisance.context_shift}")
    print(f"  Total mean shift: {nuisance.total_mean_shift}")
    print(f"  Nuisance fraction: {nuisance.nuisance_fraction:.3f}")

    # Compute posterior
    posterior = compute_mechanism_posterior_v2(
        actin_fold=actin_fold,
        mito_fold=mito_fold,
        er_fold=er_fold,
        nuisance=nuisance
    )

    print(f"\n{'='*80}")
    print("POSTERIOR WITH LEARNED SIGNATURES:")
    print("="*80)
    print(posterior.summary())

    # Verdict
    print(f"\n{'='*80}")
    print("VERDICT:")
    print("="*80)
    print(f"Ground truth: {result['true_mechanism']}")
    print(f"Posterior prediction: {posterior.top_mechanism.value}")
    print(f"Posterior confidence: {posterior.top_probability:.3f}")

    correct = (posterior.top_mechanism.value.upper() == result['true_mechanism'].upper())

    if correct and posterior.top_probability > 0.7:
        print("\n✓ CORRECT AND CONFIDENT")
        print("  Posterior correctly identified MICROTUBULE despite context bias on ER")
        print("  This means nuisance model successfully explained away the ER signal")
    elif correct and posterior.top_probability < 0.6:
        print("\n≈ CORRECT BUT UNCERTAIN")
        print("  Posterior identified MICROTUBULE but low confidence")
        print("  Appropriate given strong context effects")
    elif not correct and posterior.top_probability > 0.7:
        print("\n✗ WRONG AND CONFIDENT (FOOLED BY CONTEXT)")
        print("  Posterior misclassified as ER due to context bias")
        print("  Nuisance model failed to explain away context shift")
    else:
        print("\n✗ WRONG BUT UNCERTAIN")
        print("  Posterior misclassified but at least uncertain")

    return {
        'posterior': posterior,
        'correct': correct,
        'confidence': posterior.top_probability
    }


if __name__ == "__main__":
    result = create_context_mimic()

    print("\n\n" + "="*80)
    print("CONTEXT MIMIC TEST RESULTS:")
    print("="*80)
    print(f"Ground truth: {result['true_mechanism']}")
    print(f"Threshold classifier: {result['threshold_guess']}")

    if result['threshold_guess'] == result['true_mechanism']:
        print("\n? Threshold classifier got it right (may be luck)")
    else:
        print(f"\n✗ Threshold classifier FOOLED by context")
        print(f"  Context ER bias: {result['context_er_bias']:.3f}×")
        print(f"  Structural ER: {result['structural_features'][2]:.3f}×")
        print(f"  Measured ER: {result['measured_features'][2]:.3f}×")
        print(f"  → Misclassified as ER when true mechanism is MICROTUBULE")

    print("\nThis is the exact failure mode we need to guard against.")
    print("Proper posterior with structured nuisance should handle this.")

    posterior_result = test_posterior_with_context_mimic(result)

    print("\n\n" + "="*80)
    print("FINAL COMPARISON:")
    print("="*80)
    print(f"Threshold classifier: {result['threshold_guess']}")
    print(f"Bayesian posterior: {posterior_result['posterior'].top_mechanism.value}")
    print(f"Ground truth: {result['true_mechanism']}")
    print(f"\nThreshold correct: {result['threshold_guess'] == result['true_mechanism']}")
    print(f"Posterior correct: {posterior_result['correct']}")
    print(f"Posterior confidence: {posterior_result['confidence']:.3f}")
