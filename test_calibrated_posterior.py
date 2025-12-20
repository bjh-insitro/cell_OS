"""
Test calibrated posterior end-to-end.

Shows the full pipeline:
1. Generate experiment
2. Compute Bayesian posterior (Layer 1: Inference)
3. Apply calibrated confidence (Layer 2: Reality)
4. Compare raw vs calibrated
"""

import numpy as np
import pickle
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext
from cell_os.hardware.mechanism_posterior_v2 import (
    compute_mechanism_posterior_v2,
    NuisanceModel,
    Mechanism,
    MECHANISM_SIGNATURES_V2
)
from cell_os.hardware.confidence_calibrator import (
    ConfidenceCalibrator,
    BeliefState
)


def run_experiment_with_calibration(
    compound: str,
    true_mechanism: Mechanism,
    context_strength: float,
    timepoint: float,
    dose_multiplier: float,
    calibrator: ConfidenceCalibrator
):
    """
    Run single experiment and apply calibrated confidence.

    Returns:
        Dict with posterior, calibrated_confidence, and ground truth
    """
    # Setup
    ctx = RunContext.sample(seed=np.random.randint(0, 100000), config={'context_strength': context_strength})
    vm = BiologicalVirtualMachine(seed=np.random.randint(0, 100000), run_context=ctx)
    vm.seed_vessel("test", "A549", 1e6)

    baseline = vm.cell_painting_assay("test")

    # Treat
    base_doses = {'nocodazole': 0.3, 'tunicamycin': 0.5, 'cccp': 0.4}
    dose = base_doses[compound] * dose_multiplier

    vm.treat_with_compound("test", compound, dose_uM=dose,
                          potency_scalar=np.random.uniform(0.6, 1.0),
                          toxicity_scalar=np.random.uniform(0.3, 0.7))

    vm.advance_time(timepoint)

    result = vm.cell_painting_assay("test", batch_id='test_batch', plate_id='P001')
    vessel = vm.vessel_states["test"]

    # Compute features
    actin_fold = result['morphology_struct']['actin'] / baseline['morphology_struct']['actin']
    mito_fold = result['morphology_struct']['mito'] / baseline['morphology_struct']['mito']
    er_fold = result['morphology_struct']['er'] / baseline['morphology_struct']['er']

    # Nuisance model
    meas_mods = ctx.get_measurement_modifiers()
    context_shift = np.array([
        (meas_mods['channel_biases']['actin'] - 1.0) * 0.2 * context_strength,
        (meas_mods['channel_biases']['mito'] - 1.0) * 0.2 * context_strength,
        (meas_mods['channel_biases']['er'] - 1.0) * 0.2 * context_strength
    ])

    # Get heterogeneity
    if true_mechanism == Mechanism.MICROTUBULE:
        hetero_width = vessel.get_mixture_width('transport_dysfunction')
    elif true_mechanism == Mechanism.ER_STRESS:
        hetero_width = vessel.get_mixture_width('er_stress')
    else:
        hetero_width = vessel.get_mixture_width('mito_dysfunction')

    # Estimate artifact variance (depends on timepoint)
    artifact_var = 0.02 * np.exp(-timepoint / 10.0)  # Decays with time

    nuisance = NuisanceModel(
        context_shift=context_shift,
        pipeline_shift=np.array([0.02, -0.01, 0.02]),
        artifact_var=artifact_var,
        heterogeneity_var=hetero_width ** 2,
        context_var=(0.10 * context_strength) ** 2,
        pipeline_var=0.10 ** 2
    )

    # Compute posterior (Layer 1: Inference)
    posterior = compute_mechanism_posterior_v2(
        actin_fold=actin_fold,
        mito_fold=mito_fold,
        er_fold=er_fold,
        nuisance=nuisance
    )

    # Create belief state
    belief_state = BeliefState(
        top_probability=posterior.top_probability,
        margin=posterior.margin,
        entropy=posterior.entropy,
        nuisance_fraction=nuisance.nuisance_fraction,
        timepoint_h=timepoint,
        dose_relative=dose_multiplier,
        viability=vessel.viability
    )

    # Apply calibrated confidence (Layer 2: Reality)
    calibrated_conf = calibrator.predict_confidence(belief_state)

    # Set on posterior
    posterior.calibrated_confidence = calibrated_conf

    return {
        'posterior': posterior,
        'belief_state': belief_state,
        'true_mechanism': true_mechanism,
        'features': [actin_fold, mito_fold, er_fold],
        'nuisance_fraction': nuisance.nuisance_fraction,
        'context_strength': context_strength,
        'timepoint': timepoint
    }


def test_calibration_effects():
    """
    Test calibration on varied scenarios.

    Shows how calibrated confidence differs from raw posterior.
    """
    print("="*80)
    print("CALIBRATED POSTERIOR TEST")
    print("="*80)

    # Load learned signatures
    try:
        with open('/Users/bjh/cell_OS/data/learned_mechanism_signatures_quick.pkl', 'rb') as f:
            learned_sigs = pickle.load(f)
        MECHANISM_SIGNATURES_V2.update(learned_sigs)
        print("✓ Loaded learned signatures")
    except FileNotFoundError:
        print("⚠ Using default signatures")

    # Load calibrator
    try:
        calibrator = ConfidenceCalibrator.load('/Users/bjh/cell_OS/data/confidence_calibrator_v1.pkl')
        print("✓ Loaded calibrator\n")
    except FileNotFoundError:
        print("✗ Calibrator not found. Run train_confidence_calibrator.py first.\n")
        return

    # Test scenarios
    scenarios = [
        {
            'name': 'Easy case (clean context, early timepoint)',
            'compound': 'nocodazole',
            'mechanism': Mechanism.MICROTUBULE,
            'context_strength': 0.5,
            'timepoint': 10.0,
            'dose_multiplier': 1.0
        },
        {
            'name': 'Typical case (moderate context, mid timepoint)',
            'compound': 'tunicamycin',
            'mechanism': Mechanism.ER_STRESS,
            'context_strength': 1.0,
            'timepoint': 14.0,
            'dose_multiplier': 0.8
        },
        {
            'name': 'Hard case (cursed context, late timepoint, weak dose)',
            'compound': 'cccp',
            'mechanism': Mechanism.MITOCHONDRIAL,
            'context_strength': 2.5,
            'timepoint': 18.0,
            'dose_multiplier': 0.5
        }
    ]

    results = []
    for scenario in scenarios:
        print(f"\n{'='*80}")
        print(f"{scenario['name'].upper()}")
        print("="*80)

        result = run_experiment_with_calibration(
            compound=scenario['compound'],
            true_mechanism=scenario['mechanism'],
            context_strength=scenario['context_strength'],
            timepoint=scenario['timepoint'],
            dose_multiplier=scenario['dose_multiplier'],
            calibrator=calibrator
        )

        posterior = result['posterior']
        belief = result['belief_state']

        print(f"\nExperiment:")
        print(f"  Compound: {scenario['compound']}")
        print(f"  Context strength: {scenario['context_strength']}")
        print(f"  Timepoint: {scenario['timepoint']}h")
        print(f"  Dose: {scenario['dose_multiplier']:.1f}×")

        print(f"\nFeatures:")
        print(f"  actin={result['features'][0]:.3f}, mito={result['features'][1]:.3f}, er={result['features'][2]:.3f}")

        print(f"\nBelief state:")
        print(f"  Top probability: {belief.top_probability:.3f}")
        print(f"  Margin: {belief.margin:.3f}")
        print(f"  Entropy: {belief.entropy:.3f}")
        print(f"  Nuisance fraction: {belief.nuisance_fraction:.3f}")

        print(f"\nPosterior:")
        print(f"  Predicted: {posterior.top_mechanism.value}")
        print(f"  Ground truth: {result['true_mechanism'].value}")
        correct = (posterior.top_mechanism == result['true_mechanism'])
        print(f"  Correct: {correct}")

        print(f"\nConfidence:")
        print(f"  Raw posterior: {posterior.top_probability:.3f}")
        print(f"  Calibrated: {posterior.calibrated_confidence:.3f}")
        delta = posterior.calibrated_confidence - posterior.top_probability
        print(f"  Delta: {delta:+.3f}")

        if delta < -0.05:
            print(f"  → Calibrator REDUCED confidence (high nuisance)")
        elif delta > 0.05:
            print(f"  → Calibrator INCREASED confidence (low nuisance, high separation)")
        else:
            print(f"  → Calibrator agreed with posterior")

        results.append({
            'scenario': scenario['name'],
            'correct': correct,
            'raw_conf': posterior.top_probability,
            'calibrated_conf': posterior.calibrated_confidence,
            'nuisance_frac': belief.nuisance_fraction
        })

    # Summary
    print("\n\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\n{'Scenario':<50} {'Correct':<8} {'Raw':<8} {'Calib':<8} {'Delta':<8} {'Nuisance':<10}")
    print("-"*95)

    for r in results:
        delta = r['calibrated_conf'] - r['raw_conf']
        check = "✓" if r['correct'] else "✗"
        print(f"{r['scenario']:<50} {check:<8} {r['raw_conf']:.3f}    {r['calibrated_conf']:.3f}    {delta:+.3f}    {r['nuisance_frac']:.3f}")

    print("\n" + "="*80)
    print("INTERPRETATION")
    print("="*80)
    print("Calibrated confidence accounts for:")
    print("  - Nuisance fraction (high → reduce confidence)")
    print("  - Posterior separation (high margin → increase confidence)")
    print("  - Context-dependent failure modes (learned from data)")
    print("\nThis is epistemic maturity, not a bug.")


if __name__ == "__main__":
    test_calibration_effects()
