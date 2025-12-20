"""
Proper Bayesian mechanism posterior.

Invariant D: Confidence must be a proper probability.

Replaces threshold classifier with:
1. Likelihood model: P(features | mechanism, nuisance)
2. Prior: P(mechanism)
3. Posterior: P(mechanism | features) via Bayes
4. Confidence from posterior entropy (not heuristic)
5. Calibration metrics (ECE, Brier)
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
from enum import Enum
import numpy as np
from scipy.stats import multivariate_normal


class Mechanism(Enum):
    """Stress axis mechanisms."""
    MICROTUBULE = "microtubule"
    ER_STRESS = "er_stress"
    MITOCHONDRIAL = "mitochondrial"
    UNKNOWN = "unknown"  # No strong stress signature


@dataclass
class MechanismSignature:
    """
    Expected morphology signature for a mechanism.

    For each mechanism, we expect:
    - Specific channels to increase/decrease
    - Magnitude of change (fold-change from baseline)
    - Variance (biological + technical)
    """
    # Expected fold-changes from baseline
    actin_fold_mean: float
    mito_fold_mean: float
    er_fold_mean: float

    # Standard deviations (includes biological + technical variance)
    actin_fold_std: float
    mito_fold_std: float
    er_fold_std: float

    # Correlation structure (for multivariate likelihood)
    # Simplified: assume independence for now
    # TODO: add covariance matrix for coupled responses

    def to_mean_vector(self) -> np.ndarray:
        """Mean vector for multivariate normal."""
        return np.array([
            self.actin_fold_mean,
            self.mito_fold_mean,
            self.er_fold_mean
        ])

    def to_cov_matrix(self) -> np.ndarray:
        """Covariance matrix (diagonal for now, assuming independence)."""
        return np.diag([
            self.actin_fold_std ** 2,
            self.mito_fold_std ** 2,
            self.er_fold_std ** 2
        ])


# Expected signatures (learned from simulation or literature)
MECHANISM_SIGNATURES = {
    Mechanism.MICROTUBULE: MechanismSignature(
        actin_fold_mean=1.6,  # Strong actin increase (transport dysfunction)
        mito_fold_mean=1.0,   # Mito mostly unchanged
        er_fold_mean=1.0,     # ER mostly unchanged
        actin_fold_std=0.2,   # 20% CV
        mito_fold_std=0.15,   # 15% CV
        er_fold_std=0.15      # 15% CV
    ),
    Mechanism.ER_STRESS: MechanismSignature(
        actin_fold_mean=1.0,  # Actin mostly unchanged
        mito_fold_mean=1.0,   # Mito mostly unchanged
        er_fold_mean=1.5,     # Strong ER increase
        actin_fold_std=0.15,
        mito_fold_std=0.15,
        er_fold_std=0.2       # 20% CV on ER
    ),
    Mechanism.MITOCHONDRIAL: MechanismSignature(
        actin_fold_mean=1.0,  # Actin mostly unchanged
        mito_fold_mean=0.6,   # Mito decreases (dysfunction)
        er_fold_mean=1.0,     # ER mostly unchanged
        actin_fold_std=0.15,
        mito_fold_std=0.2,    # 20% CV on mito
        er_fold_std=0.15
    ),
    Mechanism.UNKNOWN: MechanismSignature(
        actin_fold_mean=1.0,  # No change
        mito_fold_mean=1.0,
        er_fold_mean=1.0,
        actin_fold_std=0.1,   # Tight variance (no perturbation)
        mito_fold_std=0.1,
        er_fold_std=0.1
    )
}


@dataclass
class MechanismPosterior:
    """
    Posterior distribution over mechanisms.

    P(mechanism | features) from Bayes rule.
    Confidence is posterior entropy (proper probability).
    """
    probabilities: Dict[Mechanism, float]  # P(mechanism | data)
    observed_features: np.ndarray  # [actin_fold, mito_fold, er_fold]

    # Metadata
    likelihood_scores: Dict[Mechanism, float]  # P(data | mechanism)
    prior: Dict[Mechanism, float]  # P(mechanism)

    @property
    def top_mechanism(self) -> Mechanism:
        """Most probable mechanism."""
        return max(self.probabilities.items(), key=lambda x: x[1])[0]

    @property
    def top_probability(self) -> float:
        """Probability of top mechanism."""
        return self.probabilities[self.top_mechanism]

    @property
    def entropy(self) -> float:
        """
        Posterior entropy: H = -Σ p log(p)

        Low entropy (peaked) = high confidence
        High entropy (flat) = low confidence

        Range: 0 (certain) to log(n_mechanisms) (uniform)
        """
        H = 0.0
        for p in self.probabilities.values():
            if p > 0:
                H -= p * np.log(p)
        return H

    @property
    def confidence(self) -> float:
        """
        Confidence as normalized inverse entropy.

        Maps entropy to [0, 1] where:
        - 0.0 = maximum entropy (uniform distribution)
        - 1.0 = zero entropy (delta distribution)

        This is a proper probability measure (unlike heuristic).
        """
        max_entropy = np.log(len(self.probabilities))  # Uniform distribution
        if max_entropy == 0:
            return 1.0
        # Normalize: (max - current) / max
        return 1.0 - (self.entropy / max_entropy)

    @property
    def margin(self) -> float:
        """
        Separation between top two mechanisms.

        High margin = clear winner
        Low margin = ambiguous
        """
        sorted_probs = sorted(self.probabilities.values(), reverse=True)
        if len(sorted_probs) < 2:
            return 1.0
        return sorted_probs[0] - sorted_probs[1]

    def summary(self) -> str:
        """Human-readable posterior."""
        lines = [f"MechanismPosterior (confidence={self.confidence:.3f}, entropy={self.entropy:.3f}):"]
        for mech, prob in sorted(self.probabilities.items(), key=lambda x: -x[1]):
            marker = "→" if mech == self.top_mechanism else " "
            lines.append(f"{marker} {mech.value}: {prob:.3f}")
        lines.append(f"Margin: {self.margin:.3f}")
        return "\n".join(lines)


def compute_mechanism_posterior(
    actin_fold: float,
    mito_fold: float,
    er_fold: float,
    prior: Dict[Mechanism, float] = None,
    nuisance_inflation: float = 1.0
) -> MechanismPosterior:
    """
    Compute Bayesian posterior over mechanisms.

    P(mechanism | features) ∝ P(features | mechanism) * P(mechanism)

    Args:
        actin_fold: Observed actin fold-change
        mito_fold: Observed mito fold-change
        er_fold: Observed ER fold-change
        prior: Prior distribution P(mechanism). If None, use uniform.
        nuisance_inflation: Inflate variance to account for nuisance (context, artifacts).
                           > 1.0 = more uncertain (wider likelihood)

    Returns:
        MechanismPosterior with probabilities and diagnostics
    """
    observed = np.array([actin_fold, mito_fold, er_fold])

    # Default to uniform prior
    if prior is None:
        prior = {mech: 1.0 / len(MECHANISM_SIGNATURES) for mech in MECHANISM_SIGNATURES}

    # Compute likelihood for each mechanism
    likelihoods = {}
    for mech, signature in MECHANISM_SIGNATURES.items():
        mean = signature.to_mean_vector()
        cov = signature.to_cov_matrix() * (nuisance_inflation ** 2)  # Inflate for nuisance

        # Multivariate normal likelihood
        mvn = multivariate_normal(mean=mean, cov=cov, allow_singular=True)
        likelihood = mvn.pdf(observed)
        likelihoods[mech] = likelihood

    # Bayes rule: posterior ∝ likelihood * prior
    unnormalized_posterior = {
        mech: likelihoods[mech] * prior[mech]
        for mech in MECHANISM_SIGNATURES
    }

    # Normalize
    Z = sum(unnormalized_posterior.values())
    if Z == 0:
        # Degenerate case: all likelihoods zero (data way outside support)
        # Fall back to uniform
        posterior_probs = {mech: 1.0 / len(MECHANISM_SIGNATURES) for mech in MECHANISM_SIGNATURES}
    else:
        posterior_probs = {mech: p / Z for mech, p in unnormalized_posterior.items()}

    return MechanismPosterior(
        probabilities=posterior_probs,
        observed_features=observed,
        likelihood_scores=likelihoods,
        prior=prior
    )


def compute_nuisance_inflation(
    artifact_width: float,
    heterogeneity_width: float,
    context_width: float,
    pipeline_width: float
) -> float:
    """
    Compute variance inflation factor from nuisance sources.

    Total variance = biological + artifact + context + pipeline
    Inflation factor = sqrt(total_var / biological_var)

    This inflates the likelihood covariance to account for nuisance uncertainty.

    Args:
        artifact_width: Standard deviation from plating artifacts
        heterogeneity_width: Standard deviation from biological heterogeneity
        context_width: Standard deviation from context effects
        pipeline_width: Standard deviation from pipeline drift

    Returns:
        Inflation factor (≥ 1.0) to apply to likelihood covariance
    """
    # Biological variance is the "true" variance
    bio_var = heterogeneity_width ** 2

    # Total variance includes all nuisance sources
    total_var = (
        heterogeneity_width ** 2 +
        artifact_width ** 2 +
        context_width ** 2 +
        pipeline_width ** 2
    )

    # Inflation factor
    if bio_var == 0:
        return 1.0
    inflation = np.sqrt(total_var / bio_var)
    return max(1.0, inflation)


# Calibration metrics

def expected_calibration_error(
    predicted_probs: List[float],
    actual_outcomes: List[bool],
    n_bins: int = 10
) -> float:
    """
    Expected Calibration Error (ECE).

    Measures calibration: when you say P=0.7, is the outcome correct 70% of the time?

    Args:
        predicted_probs: Predicted probabilities for top class
        actual_outcomes: True outcomes (1 if top class correct, 0 otherwise)
        n_bins: Number of bins for calibration curve

    Returns:
        ECE score (0.0 = perfect calibration, higher = worse)
    """
    predicted_probs = np.array(predicted_probs)
    actual_outcomes = np.array(actual_outcomes, dtype=float)

    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0

    for i in range(n_bins):
        bin_lower = bins[i]
        bin_upper = bins[i + 1]

        # Samples in this bin
        in_bin = (predicted_probs >= bin_lower) & (predicted_probs < bin_upper)
        if i == n_bins - 1:  # Last bin includes upper bound
            in_bin = (predicted_probs >= bin_lower) & (predicted_probs <= bin_upper)

        n_in_bin = in_bin.sum()
        if n_in_bin == 0:
            continue

        # Average predicted probability in bin
        avg_predicted = predicted_probs[in_bin].mean()

        # Empirical accuracy in bin
        avg_actual = actual_outcomes[in_bin].mean()

        # Bin contribution to ECE
        ece += (n_in_bin / len(predicted_probs)) * abs(avg_predicted - avg_actual)

    return ece


def brier_score(
    predicted_probs: List[float],
    actual_outcomes: List[bool]
) -> float:
    """
    Brier score: mean squared error of probability predictions.

    Lower is better (0.0 = perfect).

    Args:
        predicted_probs: Predicted probabilities for event
        actual_outcomes: True outcomes (1 if event happened, 0 otherwise)

    Returns:
        Brier score
    """
    predicted_probs = np.array(predicted_probs)
    actual_outcomes = np.array(actual_outcomes, dtype=float)

    return np.mean((predicted_probs - actual_outcomes) ** 2)
