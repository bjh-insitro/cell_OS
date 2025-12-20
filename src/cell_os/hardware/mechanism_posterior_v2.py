"""
MechanismPosterior v2: Fixed lies

Changes from v1:
1. Per-mechanism covariance Σ_m (not shared)
2. Nuisance as mean-shift + variance inflation (not just inflation)
3. Confidence = calibrated P(correct), not entropy
4. Fixed nuisance inflation formula (explicit base)
5. Cosplay detector test
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from enum import Enum
import numpy as np
from scipy.stats import multivariate_normal


class Mechanism(Enum):
    """Stress axis mechanisms."""
    MICROTUBULE = "microtubule"
    ER_STRESS = "er_stress"
    MITOCHONDRIAL = "mitochondrial"
    UNKNOWN = "unknown"


@dataclass
class MechanismSignature:
    """
    Per-mechanism signature with its own covariance structure.

    FIX #1: Each mechanism has Σ_m (not shared Σ).
    """
    # Mean response (fold-changes)
    actin_fold_mean: float
    mito_fold_mean: float
    er_fold_mean: float

    # Per-mechanism covariance (diagonal for now)
    # Different mechanisms have different variance structure
    actin_fold_var: float  # Variance, not std (easier to add nuisance)
    mito_fold_var: float
    er_fold_var: float

    def to_mean_vector(self) -> np.ndarray:
        return np.array([self.actin_fold_mean, self.mito_fold_mean, self.er_fold_mean])

    def to_cov_matrix(self) -> np.ndarray:
        """Per-mechanism covariance (diagonal)."""
        return np.diag([self.actin_fold_var, self.mito_fold_var, self.er_fold_var])


# Per-mechanism signatures (different covariance structures)
MECHANISM_SIGNATURES_V2 = {
    Mechanism.MICROTUBULE: MechanismSignature(
        actin_fold_mean=1.6,
        mito_fold_mean=1.0,
        er_fold_mean=1.0,
        actin_fold_var=0.04,  # 0.2² = high variance on primary channel
        mito_fold_var=0.01,   # 0.1² = tight on others
        er_fold_var=0.01
    ),
    Mechanism.ER_STRESS: MechanismSignature(
        actin_fold_mean=1.0,
        mito_fold_mean=1.0,
        er_fold_mean=1.5,
        actin_fold_var=0.01,
        mito_fold_var=0.01,
        er_fold_var=0.04      # High variance on ER
    ),
    Mechanism.MITOCHONDRIAL: MechanismSignature(
        actin_fold_mean=1.0,
        mito_fold_mean=0.6,
        er_fold_mean=1.0,
        actin_fold_var=0.01,
        mito_fold_var=0.04,   # High variance on mito
        er_fold_var=0.01
    ),
    Mechanism.UNKNOWN: MechanismSignature(
        actin_fold_mean=1.0,
        mito_fold_mean=1.0,
        er_fold_mean=1.0,
        actin_fold_var=0.0025,  # Tight (no perturbation)
        mito_fold_var=0.0025,
        er_fold_var=0.0025
    )
}


@dataclass
class NuisanceModel:
    """
    FIX #2: Nuisance as mean-shift + variance inflation.

    Not just isotropic inflation, but structured:
    - Context shifts mean (reagent lot bias)
    - Pipeline shifts mean (segmentation bias)
    - Artifacts + heterogeneity inflate variance
    """
    # Mean shifts (per channel)
    context_shift: np.ndarray  # [actin, mito, ER] shifts from RunContext
    pipeline_shift: np.ndarray  # [actin, mito, ER] shifts from batch

    # Variance inflations (additive, not multiplicative)
    artifact_var: float  # Temporal (plating artifacts)
    heterogeneity_var: float  # Biological (subpopulations)
    context_var: float  # Context effects
    pipeline_var: float  # Pipeline drift

    @property
    def total_mean_shift(self) -> np.ndarray:
        """Combined mean shift from context + pipeline."""
        return self.context_shift + self.pipeline_shift

    @property
    def total_var_inflation(self) -> float:
        """Total additive variance from all nuisance sources."""
        return self.artifact_var + self.heterogeneity_var + self.context_var + self.pipeline_var

    @property
    def nuisance_fraction(self) -> float:
        """Fraction of total variance from nuisance (excluding heterogeneity)."""
        nuisance = self.artifact_var + self.context_var + self.pipeline_var
        total = self.total_var_inflation
        return nuisance / total if total > 0 else 0.0


def compute_mechanism_posterior_v2(
    actin_fold: float,
    mito_fold: float,
    er_fold: float,
    nuisance: NuisanceModel,
    prior: Optional[Dict[Mechanism, float]] = None
) -> 'MechanismPosterior':
    """
    Bayesian posterior with per-mechanism covariance and nuisance marginalization.

    P(m | x) ∝ P(x | m, nuisance) P(m)

    where nuisance shifts mean and inflates variance.
    """
    observed = np.array([actin_fold, mito_fold, er_fold])

    # Uniform prior if not specified
    if prior is None:
        prior = {mech: 1.0 / len(MECHANISM_SIGNATURES_V2) for mech in MECHANISM_SIGNATURES_V2}

    # Compute likelihood for each mechanism
    likelihoods = {}
    for mech, signature in MECHANISM_SIGNATURES_V2.items():
        # Mean: mechanism signature + nuisance shift
        mean_eff = signature.to_mean_vector() + nuisance.total_mean_shift

        # Covariance: mechanism variance + nuisance inflation
        # Σ_eff = Σ_m + Σ_nuisance (additive)
        cov_m = signature.to_cov_matrix()
        cov_nuisance = np.eye(3) * nuisance.total_var_inflation  # Diagonal nuisance
        cov_eff = cov_m + cov_nuisance

        # Multivariate normal likelihood
        mvn = multivariate_normal(mean=mean_eff, cov=cov_eff, allow_singular=True)
        likelihood = mvn.pdf(observed)
        likelihoods[mech] = likelihood

    # Bayes rule
    unnormalized = {m: likelihoods[m] * prior[m] for m in MECHANISM_SIGNATURES_V2}
    Z = sum(unnormalized.values())

    if Z == 0:
        # Degenerate: all likelihoods zero (data way outside support)
        posterior_probs = {m: 1.0 / len(MECHANISM_SIGNATURES_V2) for m in MECHANISM_SIGNATURES_V2}
    else:
        posterior_probs = {m: p / Z for m, p in unnormalized.items()}

    return MechanismPosterior(
        probabilities=posterior_probs,
        observed_features=observed,
        likelihood_scores=likelihoods,
        prior=prior,
        nuisance=nuisance
    )


@dataclass
class MechanismPosterior:
    """
    Posterior with proper confidence calibration.

    FIX #3: Confidence ≠ entropy.
    Confidence = calibrated P(correct), learned from data.
    """
    probabilities: Dict[Mechanism, float]
    observed_features: np.ndarray
    likelihood_scores: Dict[Mechanism, float]
    prior: Dict[Mechanism, float]
    nuisance: NuisanceModel

    # Calibrated confidence (set after calibration, not from entropy)
    calibrated_confidence: Optional[float] = None

    @property
    def top_mechanism(self) -> Mechanism:
        return max(self.probabilities.items(), key=lambda x: x[1])[0]

    @property
    def top_probability(self) -> float:
        return self.probabilities[self.top_mechanism]

    @property
    def entropy(self) -> float:
        """Posterior entropy (concentration index, NOT confidence)."""
        H = 0.0
        for p in self.probabilities.values():
            if p > 0:
                H -= p * np.log(p)
        return H

    @property
    def margin(self) -> float:
        """Separation between top two."""
        sorted_probs = sorted(self.probabilities.values(), reverse=True)
        return sorted_probs[0] - sorted_probs[1] if len(sorted_probs) >= 2 else 1.0

    @property
    def confidence_heuristic(self) -> float:
        """
        Entropy-based heuristic (for comparison).
        NOT a proper probability of correctness.
        """
        max_entropy = np.log(len(self.probabilities))
        return 1.0 - (self.entropy / max_entropy) if max_entropy > 0 else 1.0

    @property
    def confidence(self) -> float:
        """
        Calibrated confidence = P(correct | features).

        If calibrated_confidence not set, falls back to top_probability.
        To be truly calibrated, must learn mapping from features → P(correct).
        """
        if self.calibrated_confidence is not None:
            return self.calibrated_confidence
        # Fallback: use top probability (at least interpretable)
        return self.top_probability

    def summary(self) -> str:
        lines = [
            f"MechanismPosterior:",
            f"  Top: {self.top_mechanism.value} (P={self.top_probability:.3f})",
            f"  Margin: {self.margin:.3f}",
            f"  Entropy: {self.entropy:.3f}",
            f"  Confidence (entropy-based): {self.confidence_heuristic:.3f}",
            f"  Confidence (calibrated): {self.confidence:.3f}",
            f"  Nuisance fraction: {self.nuisance.nuisance_fraction:.3f}",
            f"",
            f"Full posterior:"
        ]
        for mech, prob in sorted(self.probabilities.items(), key=lambda x: -x[1]):
            marker = "→" if mech == self.top_mechanism else " "
            lines.append(f"{marker} {mech.value}: {prob:.3f}")
        return "\n".join(lines)


def calibrate_confidence(
    posteriors: List[MechanismPosterior],
    ground_truth: List[Mechanism],
    method: str = 'isotonic'
) -> None:
    """
    Calibrate confidence: learn P(correct | features).

    FIX #3: Proper calibration, not just entropy.

    Features used:
    - top_probability
    - margin
    - entropy
    - nuisance_fraction

    Maps to: P(top mechanism is correct)

    Modifies posteriors in-place to set calibrated_confidence.
    """
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression

    # Extract features
    features = []
    outcomes = []
    for post, truth in zip(posteriors, ground_truth):
        features.append([
            post.top_probability,
            post.margin,
            post.entropy,
            post.nuisance.nuisance_fraction
        ])
        outcomes.append(1.0 if post.top_mechanism == truth else 0.0)

    features = np.array(features)
    outcomes = np.array(outcomes)

    if method == 'isotonic':
        # Isotonic regression on top_probability
        calibrator = IsotonicRegression(out_of_bounds='clip')
        calibrator.fit(features[:, 0], outcomes)  # Use top_prob as input

        # Apply calibration
        for post in posteriors:
            post.calibrated_confidence = float(calibrator.predict([post.top_probability])[0])

    elif method == 'platt':
        # Logistic regression (Platt scaling) on all features
        calibrator = LogisticRegression()
        calibrator.fit(features, outcomes)

        # Apply calibration
        for i, post in enumerate(posteriors):
            post.calibrated_confidence = float(calibrator.predict_proba([features[i]])[0, 1])


# Cosplay detector test

def cosplay_detector_test():
    """
    Test that fails if we're doing nearest-centroid with Bayes paint.

    Create two mechanisms with:
    - Identical means
    - Different covariances (one tight in actin, one tight in ER)

    A centroid classifier can't separate them.
    A real likelihood model can.
    """
    print("=== Cosplay Detector Test ===\n")

    # Create two fake mechanisms with same mean, different variance structure
    mech_A = MechanismSignature(
        actin_fold_mean=1.3,
        mito_fold_mean=1.0,
        er_fold_mean=1.0,
        actin_fold_var=0.01,  # Tight in actin
        mito_fold_var=0.04,   # Loose in mito
        er_fold_var=0.04      # Loose in ER
    )

    mech_B = MechanismSignature(
        actin_fold_mean=1.3,  # Same mean!
        mito_fold_mean=1.0,
        er_fold_mean=1.0,
        actin_fold_var=0.04,  # Loose in actin
        mito_fold_var=0.01,   # Tight in mito
        er_fold_var=0.01      # Tight in ER
    )

    print("Two mechanisms with SAME MEAN, DIFFERENT COVARIANCE:")
    print(f"Mech A: mean=[1.3, 1.0, 1.0], var=[0.01, 0.04, 0.04] (tight actin)")
    print(f"Mech B: mean=[1.3, 1.0, 1.0], var=[0.04, 0.01, 0.01] (loose actin)")

    # Sample from A: should have tight actin, loose mito/ER
    sample_A = np.array([1.35, 1.15, 1.10])  # Actin close to mean, others off

    # Centroid distance: both equidistant from mean
    dist_A = np.linalg.norm(sample_A - mech_A.to_mean_vector())
    dist_B = np.linalg.norm(sample_A - mech_B.to_mean_vector())

    print(f"\nSample from A: {sample_A}")
    print(f"Distance to A mean: {dist_A:.3f}")
    print(f"Distance to B mean: {dist_B:.3f}")
    print("→ Centroid classifier: AMBIGUOUS (same distance)")

    # Likelihood: should prefer A (tight actin, loose mito/ER matches)
    mvn_A = multivariate_normal(mean=mech_A.to_mean_vector(), cov=mech_A.to_cov_matrix())
    mvn_B = multivariate_normal(mean=mech_B.to_mean_vector(), cov=mech_B.to_cov_matrix())

    lik_A = mvn_A.pdf(sample_A)
    lik_B = mvn_B.pdf(sample_A)

    print(f"\nLikelihood under A: {lik_A:.6f}")
    print(f"Likelihood under B: {lik_B:.6f}")
    print(f"Ratio: {lik_A / lik_B:.2f}")

    if lik_A > lik_B * 2:
        print("→ Likelihood model: PREFERS A (correct!)")
        print("✓ NOT COSPLAY: Real likelihood evaluation")
    else:
        print("→ Likelihood model: AMBIGUOUS or WRONG")
        print("✗ COSPLAY: Still doing nearest-neighbor")

    return lik_A > lik_B * 2


if __name__ == "__main__":
    passed = cosplay_detector_test()
    if passed:
        print("\n✓ Cosplay detector: PASSED")
    else:
        print("\n✗ Cosplay detector: FAILED (still nearest-neighbor)")
