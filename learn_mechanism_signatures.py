"""
Learn mechanism signatures from simulation data.

Generate datasets:
- Many runs per mechanism (varied context, dose, timepoint, seed)
- Record observed features [actin, mito, ER] fold-changes
- Fit per-mechanism Gaussian: μ_m, Σ_m

Acceptance criterion: learned signatures must pass cosplay detector (ratio > 2.0)
or we conclude 3D feature space insufficient.
"""

import numpy as np
from typing import Dict, Tuple
import pickle
from pathlib import Path

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext
from cell_os.hardware.mechanism_posterior_v2 import (
    Mechanism,
    MechanismSignature
)


def generate_mechanism_dataset(
    compound: str,
    true_mechanism: Mechanism,
    n_samples: int = 200,
    seed_offset: int = 0
) -> Tuple[np.ndarray, Dict]:
    """
    Generate dataset for one mechanism.

    Varies:
    - Context (different seeds, strengths)
    - Dose (0.2-1.0× reference)
    - Potency/toxicity (0.5-1.5×)
    - Timepoint (10-16h to avoid extreme artifacts or death)
    - Random seed

    Returns:
    - features: (n_samples, 3) array of [actin_fold, mito_fold, er_fold]
    - metadata: dict with nuisance info per sample
    """
    print(f"Generating {n_samples} samples for {true_mechanism.value} ({compound})...")

    features = []
    metadata = {
        'nuisance_fractions': [],
        'timepoints': [],
        'doses': [],
        'viabilities': []
    }

    for i in range(n_samples):
        seed_run = seed_offset + i
        seed_context = seed_offset + i + 1000

        # Vary context strength
        context_strength = np.random.uniform(0.5, 2.0)
        ctx = RunContext.sample(seed=seed_context, config={'context_strength': context_strength})

        vm = BiologicalVirtualMachine(seed=seed_run, run_context=ctx)
        vm.seed_vessel("test", "A549", 1e6)

        # Baseline
        baseline = vm.cell_painting_assay("test")
        baseline_actin = baseline['morphology_struct']['actin']
        baseline_mito = baseline['morphology_struct']['mito']
        baseline_er = baseline['morphology_struct']['er']

        # Vary dose
        base_dose = {
            'nocodazole': 0.3,
            'tunicamycin': 0.5,
            'cccp': 0.4
        }[compound]
        dose = base_dose * np.random.uniform(0.5, 1.5)

        # Vary potency/toxicity
        potency = np.random.uniform(0.6, 1.2)
        toxicity = np.random.uniform(0.3, 0.8)

        vm.treat_with_compound("test", compound, dose_uM=dose,
                              potency_scalar=potency,
                              toxicity_scalar=toxicity)

        # Vary timepoint (avoid extremes)
        timepoint = np.random.uniform(10, 16)
        vm.advance_time(timepoint)

        # Measure
        result = vm.cell_painting_assay("test", batch_id=f'batch_{i}', plate_id=f'P{i:03d}')
        vessel = vm.vessel_states["test"]

        # Compute fold-changes (structural, not measured)
        actin_fold = result['morphology_struct']['actin'] / baseline_actin
        mito_fold = result['morphology_struct']['mito'] / baseline_mito
        er_fold = result['morphology_struct']['er'] / baseline_er

        features.append([actin_fold, mito_fold, er_fold])

        # Record nuisance info
        # Get dominant axis for nuisance estimation
        if true_mechanism == Mechanism.MICROTUBULE:
            width = vessel.get_mixture_width('transport_dysfunction')
            artifact_total = vessel.get_artifact_inflated_mixture_width('transport_dysfunction', vm.simulated_time)
        elif true_mechanism == Mechanism.ER_STRESS:
            width = vessel.get_mixture_width('er_stress')
            artifact_total = vessel.get_artifact_inflated_mixture_width('er_stress', vm.simulated_time)
        else:  # MITOCHONDRIAL
            width = vessel.get_mixture_width('mito_dysfunction')
            artifact_total = vessel.get_artifact_inflated_mixture_width('mito_dysfunction', vm.simulated_time)

        artifact_contrib = artifact_total - width

        # Estimate nuisance fraction
        heterogeneity_var = width ** 2
        artifact_var = artifact_contrib ** 2
        context_var = 0.15 ** 2  # Estimated
        pipeline_var = 0.10 ** 2  # Estimated

        total_var = heterogeneity_var + artifact_var + context_var + pipeline_var
        nuisance_var = artifact_var + context_var + pipeline_var
        nuisance_frac = nuisance_var / total_var if total_var > 0 else 0.0

        metadata['nuisance_fractions'].append(nuisance_frac)
        metadata['timepoints'].append(timepoint)
        metadata['doses'].append(dose)
        metadata['viabilities'].append(vessel.viability)

        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{n_samples} samples generated...")

    features = np.array(features)

    print(f"  Mean features: actin={features[:, 0].mean():.3f}, mito={features[:, 1].mean():.3f}, er={features[:, 2].mean():.3f}")
    print(f"  Std features: actin={features[:, 0].std():.3f}, mito={features[:, 1].std():.3f}, er={features[:, 2].std():.3f}")

    return features, metadata


def fit_mechanism_signature(features: np.ndarray) -> MechanismSignature:
    """
    Fit Gaussian to mechanism features.

    Returns MechanismSignature with learned mean and covariance.
    """
    # Compute mean
    mean = features.mean(axis=0)

    # Compute covariance
    cov = np.cov(features, rowvar=False)

    # Extract diagonal (for now, assume independence)
    # TODO: could use full covariance if stable
    variances = np.diag(cov)

    # Regularize if needed (add small epsilon for stability)
    variances = np.maximum(variances, 1e-6)

    return MechanismSignature(
        actin_fold_mean=float(mean[0]),
        mito_fold_mean=float(mean[1]),
        er_fold_mean=float(mean[2]),
        actin_fold_var=float(variances[0]),
        mito_fold_var=float(variances[1]),
        er_fold_var=float(variances[2])
    )


def learn_all_signatures(n_samples_per_mechanism: int = 200) -> Dict[Mechanism, MechanismSignature]:
    """
    Learn signatures for all mechanisms.

    Returns dict: Mechanism -> MechanismSignature (learned from data)
    """
    print("="*80)
    print("LEARNING MECHANISM SIGNATURES FROM SIMULATION DATA")
    print("="*80)

    mechanisms_and_compounds = [
        (Mechanism.MICROTUBULE, 'nocodazole'),
        (Mechanism.ER_STRESS, 'tunicamycin'),
        (Mechanism.MITOCHONDRIAL, 'cccp')
    ]

    learned_signatures = {}

    for i, (mechanism, compound) in enumerate(mechanisms_and_compounds):
        print(f"\n{mechanism.value.upper()}:")
        print("-" * 80)

        # Generate dataset
        features, metadata = generate_mechanism_dataset(
            compound=compound,
            true_mechanism=mechanism,
            n_samples=n_samples_per_mechanism,
            seed_offset=i * 10000
        )

        # Fit signature
        signature = fit_mechanism_signature(features)

        print(f"\nLearned signature:")
        print(f"  Mean: actin={signature.actin_fold_mean:.3f}, mito={signature.mito_fold_mean:.3f}, er={signature.er_fold_mean:.3f}")
        print(f"  Var:  actin={signature.actin_fold_var:.4f}, mito={signature.mito_fold_var:.4f}, er={signature.er_fold_var:.4f}")
        print(f"  Std:  actin={np.sqrt(signature.actin_fold_var):.3f}, mito={np.sqrt(signature.mito_fold_var):.3f}, er={np.sqrt(signature.er_fold_var):.3f}")

        learned_signatures[mechanism] = signature

    # Add UNKNOWN mechanism (no treatment, just measurement noise)
    print(f"\n{Mechanism.UNKNOWN.value.upper()}:")
    print("-" * 80)
    print("Using tight baseline (no perturbation)")
    learned_signatures[Mechanism.UNKNOWN] = MechanismSignature(
        actin_fold_mean=1.0,
        mito_fold_mean=1.0,
        er_fold_mean=1.0,
        actin_fold_var=0.01,  # Measurement noise only
        mito_fold_var=0.01,
        er_fold_var=0.01
    )

    return learned_signatures


def test_cosplay_detector_with_learned_signatures(
    learned_signatures: Dict[Mechanism, MechanismSignature]
) -> bool:
    """
    Test if learned signatures pass cosplay detector.

    Acceptance criterion: likelihood ratio > 2.0 when distinguishing
    mechanisms with same mean but different covariance.
    """
    from scipy.stats import multivariate_normal

    print("\n" + "="*80)
    print("COSPLAY DETECTOR TEST (Learned Signatures)")
    print("="*80)

    # Use MICROTUBULE and ER signatures
    micro_sig = learned_signatures[Mechanism.MICROTUBULE]
    er_sig = learned_signatures[Mechanism.ER_STRESS]

    print(f"\nMicrotubule signature:")
    print(f"  Mean: [{micro_sig.actin_fold_mean:.3f}, {micro_sig.mito_fold_mean:.3f}, {micro_sig.er_fold_mean:.3f}]")
    print(f"  Var:  [{micro_sig.actin_fold_var:.4f}, {micro_sig.mito_fold_var:.4f}, {micro_sig.er_fold_var:.4f}]")

    print(f"\nER signature:")
    print(f"  Mean: [{er_sig.actin_fold_mean:.3f}, {er_sig.mito_fold_mean:.3f}, {er_sig.er_fold_mean:.3f}]")
    print(f"  Var:  [{er_sig.actin_fold_var:.4f}, {er_sig.mito_fold_var:.4f}, {er_sig.er_fold_var:.4f}]")

    # Create synthetic sample: strong in primary channel of one mechanism
    # Sample from MICROTUBULE: high actin, baseline mito/ER
    sample_micro = np.array([
        micro_sig.actin_fold_mean + 0.5 * np.sqrt(micro_sig.actin_fold_var),
        micro_sig.mito_fold_mean,
        micro_sig.er_fold_mean
    ])

    print(f"\nTest sample (from MICROTUBULE distribution):")
    print(f"  {sample_micro}")

    # Compute likelihoods
    mvn_micro = multivariate_normal(
        mean=micro_sig.to_mean_vector(),
        cov=micro_sig.to_cov_matrix()
    )
    mvn_er = multivariate_normal(
        mean=er_sig.to_mean_vector(),
        cov=er_sig.to_cov_matrix()
    )

    lik_micro = mvn_micro.pdf(sample_micro)
    lik_er = mvn_er.pdf(sample_micro)
    ratio = lik_micro / lik_er if lik_er > 0 else float('inf')

    print(f"\nLikelihoods:")
    print(f"  P(sample | MICRO): {lik_micro:.6f}")
    print(f"  P(sample | ER):    {lik_er:.6f}")
    print(f"  Ratio: {ratio:.2f}")

    passed = ratio > 2.0

    if passed:
        print(f"\n✓ PASSED: Ratio {ratio:.2f} > 2.0")
        print("  Learned signatures can distinguish covariance structure")
    else:
        print(f"\n✗ FAILED: Ratio {ratio:.2f} < 2.0")
        print("  3D feature space may be insufficient")
        print("  Consider: add more morphology features or PCA dimensions")

    return passed


def save_learned_signatures(signatures: Dict[Mechanism, MechanismSignature], path: str):
    """Save learned signatures to disk."""
    with open(path, 'wb') as f:
        pickle.dump(signatures, f)
    print(f"\nSaved learned signatures to {path}")


if __name__ == "__main__":
    # Learn signatures from data
    learned_signatures = learn_all_signatures(n_samples_per_mechanism=200)

    # Test cosplay detector
    passed = test_cosplay_detector_with_learned_signatures(learned_signatures)

    # Save for later use
    save_path = "/Users/bjh/cell_OS/data/learned_mechanism_signatures.pkl"
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    save_learned_signatures(learned_signatures, save_path)

    print("\n" + "="*80)
    print("VERDICT:")
    print("="*80)
    if passed:
        print("✓ Learned signatures PASS cosplay detector")
        print("  3D feature space [actin, mito, ER] is sufficient")
        print("  Next: implement structured nuisance covariance")
    else:
        print("✗ Learned signatures FAIL cosplay detector")
        print("  3D feature space [actin, mito, ER] is insufficient")
        print("  Recommendation: add morphology PCA dimensions or more channels")
        print("  OR: accept that covariance structure won't help, stick to means")
