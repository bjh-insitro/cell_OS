"""
Train confidence calibrator with stratified sampling.

Critical: Do NOT train on IID samples only.
Deliberately include:
- Low nuisance (clean contexts, early timepoints)
- Medium nuisance (typical experiments)
- High nuisance (cursed contexts, late timepoints, high heterogeneity)

This ensures calibrator is conservative where it needs to be.
"""

import numpy as np
import pickle
from pathlib import Path
from typing import List, Tuple

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
    BeliefState,
    CalibrationDatapoint,
    reliability_diagram
)


def generate_calibration_dataset(
    n_samples_per_strata: int = 50,
    seed_offset: int = 0
) -> List[CalibrationDatapoint]:
    """
    Generate calibration dataset with stratified sampling.

    Three strata:
    1. Low nuisance: Clean context, early timepoint, low heterogeneity
    2. Medium nuisance: Typical context, mid timepoint, moderate heterogeneity
    3. High nuisance: Cursed context, late timepoint, high heterogeneity

    For each stratum, vary:
    - Mechanism (MICROTUBULE, ER_STRESS, MITOCHONDRIAL)
    - Dose (weak, medium, strong)
    - Potency/toxicity
    """
    print("="*80)
    print("GENERATING CALIBRATION DATASET (STRATIFIED)")
    print("="*80)

    mechanisms = [
        (Mechanism.MICROTUBULE, 'nocodazole', 0.3),
        (Mechanism.ER_STRESS, 'tunicamycin', 0.5),
        (Mechanism.MITOCHONDRIAL, 'cccp', 0.4)
    ]

    datapoints = []

    # Stratum 1: Low nuisance
    print("\n1. LOW NUISANCE STRATUM")
    print("-"*80)
    print("Clean context (strength=0.5), early timepoint (10h), reference dose")

    for i in range(n_samples_per_strata):
        seed_run = seed_offset + i
        seed_context = seed_offset + i + 10000

        # Clean context
        ctx = RunContext.sample(seed=seed_context, config={'context_strength': 0.5})

        # Pick mechanism
        mech_idx = i % len(mechanisms)
        true_mech, compound, base_dose = mechanisms[mech_idx]

        vm = BiologicalVirtualMachine(seed=seed_run, run_context=ctx)
        vm.seed_vessel("test", "A549", 1e6)

        baseline = vm.cell_painting_assay("test")

        # Reference dose, moderate potency/toxicity
        dose = base_dose * np.random.uniform(0.8, 1.2)
        potency = np.random.uniform(0.7, 1.0)
        toxicity = np.random.uniform(0.3, 0.6)

        vm.treat_with_compound("test", compound, dose_uM=dose,
                              potency_scalar=potency, toxicity_scalar=toxicity)

        # Early timepoint (artifacts minimal)
        timepoint = 10.0
        vm.advance_time(timepoint)

        result = vm.cell_painting_assay("test", batch_id=f'batch_low_{i}', plate_id=f'P{i:03d}')
        vessel = vm.vessel_states["test"]

        # Compute features
        actin_fold = result['morphology_struct']['actin'] / baseline['morphology_struct']['actin']
        mito_fold = result['morphology_struct']['mito'] / baseline['morphology_struct']['mito']
        er_fold = result['morphology_struct']['er'] / baseline['morphology_struct']['er']

        # Nuisance model (low nuisance)
        meas_mods = ctx.get_measurement_modifiers()
        context_shift = np.array([
            (meas_mods['channel_biases']['actin'] - 1.0) * 0.1,
            (meas_mods['channel_biases']['mito'] - 1.0) * 0.1,
            (meas_mods['channel_biases']['er'] - 1.0) * 0.1
        ])

        # Get heterogeneity
        if true_mech == Mechanism.MICROTUBULE:
            hetero_width = vessel.get_mixture_width('transport_dysfunction')
        elif true_mech == Mechanism.ER_STRESS:
            hetero_width = vessel.get_mixture_width('er_stress')
        else:
            hetero_width = vessel.get_mixture_width('mito_dysfunction')

        nuisance = NuisanceModel(
            context_shift=context_shift,
            pipeline_shift=np.array([0.01, 0.01, 0.01]),  # Minimal pipeline drift
            artifact_var=0.005,  # Low artifacts at 10h
            heterogeneity_var=hetero_width ** 2,
            context_var=0.10 ** 2,  # Clean context
            pipeline_var=0.05 ** 2
        )

        # Compute posterior
        posterior = compute_mechanism_posterior_v2(
            actin_fold=actin_fold,
            mito_fold=mito_fold,
            er_fold=er_fold,
            nuisance=nuisance
        )

        # Create belief state
        belief = BeliefState(
            top_probability=posterior.top_probability,
            margin=posterior.margin,
            entropy=posterior.entropy,
            nuisance_fraction=nuisance.nuisance_fraction,
            timepoint_h=timepoint,
            dose_relative=dose / base_dose,
            viability=vessel.viability
        )

        datapoints.append(CalibrationDatapoint(
            belief_state=belief,
            predicted_mechanism=posterior.top_mechanism,
            true_mechanism=true_mech
        ))

        if (i + 1) % 15 == 0:
            print(f"  {i+1}/{n_samples_per_strata} samples...")

    # Stratum 2: Medium nuisance
    print("\n2. MEDIUM NUISANCE STRATUM")
    print("-"*80)
    print("Typical context (strength=1.0), mid timepoint (14h), varied dose")

    for i in range(n_samples_per_strata):
        seed_run = seed_offset + n_samples_per_strata + i
        seed_context = seed_offset + n_samples_per_strata + i + 20000

        # Typical context
        ctx = RunContext.sample(seed=seed_context, config={'context_strength': 1.0})

        mech_idx = i % len(mechanisms)
        true_mech, compound, base_dose = mechanisms[mech_idx]

        vm = BiologicalVirtualMachine(seed=seed_run, run_context=ctx)
        vm.seed_vessel("test", "A549", 1e6)

        baseline = vm.cell_painting_assay("test")

        # Varied dose
        dose = base_dose * np.random.uniform(0.5, 1.5)
        potency = np.random.uniform(0.6, 1.2)
        toxicity = np.random.uniform(0.3, 0.8)

        vm.treat_with_compound("test", compound, dose_uM=dose,
                              potency_scalar=potency, toxicity_scalar=toxicity)

        # Mid timepoint
        timepoint = 14.0
        vm.advance_time(timepoint)

        result = vm.cell_painting_assay("test", batch_id=f'batch_med_{i}', plate_id=f'P{i:03d}')
        vessel = vm.vessel_states["test"]

        actin_fold = result['morphology_struct']['actin'] / baseline['morphology_struct']['actin']
        mito_fold = result['morphology_struct']['mito'] / baseline['morphology_struct']['mito']
        er_fold = result['morphology_struct']['er'] / baseline['morphology_struct']['er']

        # Nuisance model (medium)
        meas_mods = ctx.get_measurement_modifiers()
        context_shift = np.array([
            (meas_mods['channel_biases']['actin'] - 1.0) * 0.15,
            (meas_mods['channel_biases']['mito'] - 1.0) * 0.15,
            (meas_mods['channel_biases']['er'] - 1.0) * 0.15
        ])

        if true_mech == Mechanism.MICROTUBULE:
            hetero_width = vessel.get_mixture_width('transport_dysfunction')
        elif true_mech == Mechanism.ER_STRESS:
            hetero_width = vessel.get_mixture_width('er_stress')
        else:
            hetero_width = vessel.get_mixture_width('mito_dysfunction')

        nuisance = NuisanceModel(
            context_shift=context_shift,
            pipeline_shift=np.array([0.02, -0.01, 0.03]),
            artifact_var=0.010,  # Moderate artifacts
            heterogeneity_var=hetero_width ** 2,
            context_var=0.15 ** 2,
            pipeline_var=0.10 ** 2
        )

        posterior = compute_mechanism_posterior_v2(
            actin_fold=actin_fold,
            mito_fold=mito_fold,
            er_fold=er_fold,
            nuisance=nuisance
        )

        belief = BeliefState(
            top_probability=posterior.top_probability,
            margin=posterior.margin,
            entropy=posterior.entropy,
            nuisance_fraction=nuisance.nuisance_fraction,
            timepoint_h=timepoint,
            dose_relative=dose / base_dose,
            viability=vessel.viability
        )

        datapoints.append(CalibrationDatapoint(
            belief_state=belief,
            predicted_mechanism=posterior.top_mechanism,
            true_mechanism=true_mech
        ))

        if (i + 1) % 15 == 0:
            print(f"  {i+1}/{n_samples_per_strata} samples...")

    # Stratum 3: High nuisance
    print("\n3. HIGH NUISANCE STRATUM")
    print("-"*80)
    print("Cursed context (strength=2.5), late timepoint (18h), weak dose")

    for i in range(n_samples_per_strata):
        seed_run = seed_offset + 2 * n_samples_per_strata + i
        seed_context = seed_offset + 2 * n_samples_per_strata + i + 30000

        # Cursed context (high strength, creates strong biases)
        ctx = RunContext.sample(seed=seed_context, config={'context_strength': 2.5})

        mech_idx = i % len(mechanisms)
        true_mech, compound, base_dose = mechanisms[mech_idx]

        vm = BiologicalVirtualMachine(seed=seed_run, run_context=ctx)
        vm.seed_vessel("test", "A549", 1e6)

        baseline = vm.cell_painting_assay("test")

        # Weak dose (partial engagement, ambiguous signal)
        dose = base_dose * np.random.uniform(0.3, 0.7)
        potency = np.random.uniform(0.5, 0.9)
        toxicity = np.random.uniform(0.4, 0.9)

        vm.treat_with_compound("test", compound, dose_uM=dose,
                              potency_scalar=potency, toxicity_scalar=toxicity)

        # Late timepoint (high heterogeneity from death)
        timepoint = 18.0
        vm.advance_time(timepoint)

        result = vm.cell_painting_assay("test", batch_id=f'batch_high_{i}', plate_id=f'P{i:03d}')
        vessel = vm.vessel_states["test"]

        actin_fold = result['morphology_struct']['actin'] / baseline['morphology_struct']['actin']
        mito_fold = result['morphology_struct']['mito'] / baseline['morphology_struct']['mito']
        er_fold = result['morphology_struct']['er'] / baseline['morphology_struct']['er']

        # Nuisance model (high)
        meas_mods = ctx.get_measurement_modifiers()
        context_shift = np.array([
            (meas_mods['channel_biases']['actin'] - 1.0) * 0.25,  # Strong context effects
            (meas_mods['channel_biases']['mito'] - 1.0) * 0.25,
            (meas_mods['channel_biases']['er'] - 1.0) * 0.25
        ])

        if true_mech == Mechanism.MICROTUBULE:
            hetero_width = vessel.get_mixture_width('transport_dysfunction')
        elif true_mech == Mechanism.ER_STRESS:
            hetero_width = vessel.get_mixture_width('er_stress')
        else:
            hetero_width = vessel.get_mixture_width('mito_dysfunction')

        nuisance = NuisanceModel(
            context_shift=context_shift,
            pipeline_shift=np.array([0.05, -0.03, 0.04]),  # Strong pipeline drift
            artifact_var=0.015,  # Some artifacts remain at 18h
            heterogeneity_var=hetero_width ** 2,  # High from death
            context_var=0.20 ** 2,  # Cursed context
            pipeline_var=0.15 ** 2
        )

        posterior = compute_mechanism_posterior_v2(
            actin_fold=actin_fold,
            mito_fold=mito_fold,
            er_fold=er_fold,
            nuisance=nuisance
        )

        belief = BeliefState(
            top_probability=posterior.top_probability,
            margin=posterior.margin,
            entropy=posterior.entropy,
            nuisance_fraction=nuisance.nuisance_fraction,
            timepoint_h=timepoint,
            dose_relative=dose / base_dose,
            viability=vessel.viability
        )

        datapoints.append(CalibrationDatapoint(
            belief_state=belief,
            predicted_mechanism=posterior.top_mechanism,
            true_mechanism=true_mech
        ))

        if (i + 1) % 15 == 0:
            print(f"  {i+1}/{n_samples_per_strata} samples...")

    print(f"\nTotal datapoints: {len(datapoints)}")
    print(f"  Low nuisance: {sum(1 for dp in datapoints if dp.nuisance_bin == 'low_nuisance')}")
    print(f"  Medium nuisance: {sum(1 for dp in datapoints if dp.nuisance_bin == 'medium_nuisance')}")
    print(f"  High nuisance: {sum(1 for dp in datapoints if dp.nuisance_bin == 'high_nuisance')}")

    return datapoints


if __name__ == "__main__":
    # Load learned signatures
    print("Loading learned signatures...")
    try:
        with open('/Users/bjh/cell_OS/data/learned_mechanism_signatures_quick.pkl', 'rb') as f:
            learned_sigs = pickle.load(f)
        MECHANISM_SIGNATURES_V2.update(learned_sigs)
        print("✓ Loaded learned signatures\n")
    except FileNotFoundError:
        print("⚠ No learned signatures found, using defaults\n")

    # Generate calibration dataset (stratified)
    datapoints = generate_calibration_dataset(n_samples_per_strata=50, seed_offset=50000)

    # Split train/test (stratified)
    calibrator = ConfidenceCalibrator(method='platt', include_context=True)
    train_data, test_data = calibrator.stratified_split(datapoints, test_fraction=0.2)

    print(f"\nTrain: {len(train_data)}, Test: {len(test_data)}")

    # Train calibrator
    calibrator.train(train_data, verbose=True)

    # Evaluate on test set (stratified)
    print("\n" + "="*80)
    print("TEST SET EVALUATION")
    print("="*80)
    test_metrics = calibrator.evaluate_stratified(test_data, verbose=True)

    # Generate reliability diagram
    print("\n" + "="*80)
    print("RELIABILITY DIAGRAM (Test Set)")
    print("="*80)
    rel_data = reliability_diagram(test_data, calibrator, n_bins=10)

    print(f"\n{'Bin':<6} {'Confidence':<12} {'Accuracy':<12} {'Count':<8} {'Gap':<8}")
    print("-"*52)
    for i, (conf, acc, count) in enumerate(zip(rel_data['bin_centers'],
                                                 rel_data['bin_accuracies'],
                                                 rel_data['bin_counts'])):
        gap = conf - acc
        marker = "!" if abs(gap) > 0.1 else ""
        print(f"{i:<6} {conf:.3f}        {acc:.3f}        {int(count):<8} {gap:+.3f} {marker}")

    # Check acceptance criteria
    print("\n" + "="*80)
    print("ACCEPTANCE CRITERIA")
    print("="*80)

    # 1. Reliability curves near diagonal (ECE < 0.1)
    ece_overall = sum(test_metrics[bin_name]['ece'] * test_metrics[bin_name]['n_samples']
                      for bin_name in test_metrics) / len(test_data)
    print(f"1. Overall ECE: {ece_overall:.4f} {'✓' if ece_overall < 0.1 else '✗'} (target < 0.1)")

    # 2. High-nuisance bins are conservative (not overconfident)
    if 'high_nuisance' in test_metrics:
        high_nuisance_overconfident = test_metrics['high_nuisance']['overconfident']
        print(f"2. High nuisance conservative: {'✓' if not high_nuisance_overconfident else '✗ OVERCONFIDENT'}")
    else:
        print(f"2. High nuisance conservative: ? (no high-nuisance samples in test)")

    # 3. Low-nuisance bins are accurate (maintain confidence when justified)
    if 'low_nuisance' in test_metrics:
        low_nuisance_acc = test_metrics['low_nuisance']['accuracy']
        low_nuisance_conf = test_metrics['low_nuisance']['mean_confidence']
        print(f"3. Low nuisance accuracy: {low_nuisance_acc:.3f}, confidence: {low_nuisance_conf:.3f}")
        print(f"   Well-calibrated: {'✓' if abs(low_nuisance_conf - low_nuisance_acc) < 0.1 else '✗'}")

    # Freeze and save
    print("\n" + "="*80)
    print("FREEZING CALIBRATOR")
    print("="*80)
    calibrator.freeze()
    save_path = "/Users/bjh/cell_OS/data/confidence_calibrator_v1.pkl"
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    calibrator.save(save_path)

    print("\n✓ Calibrator training complete")
    print(f"  Frozen: {calibrator.frozen}")
    print(f"  Saved to: {save_path}")
    print("\nTreat like labware. Do not retrain without versioning.")
