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


# Agent 2: Ambiguity detection constants
# These determine when to cap confidence and represent uncertainty explicitly
GAP_CLEAR = 0.15  # Likelihood ratio gap for "clear" classification
                  # If top-2 likelihoods are within this gap, posterior is ambiguous
MAX_PROB_AMBIGUOUS = 0.75  # Maximum probability allowed in ambiguous cases
                            # Prevents overconfidence when mechanisms overlap


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
    contact_shift: np.ndarray  # [actin, mito, ER] shifts from contact pressure (Δp)

    # Variance inflations (additive, not multiplicative)
    artifact_var: float  # Temporal (plating artifacts)
    heterogeneity_var: float  # Biological (subpopulations)
    context_var: float  # Context effects
    pipeline_var: float  # Pipeline drift
    contact_var: float  # Contact pressure uncertainty / model mismatch

    @property
    def total_mean_shift(self) -> np.ndarray:
        """Combined mean shift from context + pipeline + contact."""
        return self.context_shift + self.pipeline_shift + self.contact_shift

    @property
    def total_var_inflation(self) -> float:
        """Total additive variance from all nuisance sources."""
        return (
            self.artifact_var +
            self.heterogeneity_var +
            self.context_var +
            self.pipeline_var +
            self.contact_var
        )

    @property
    def inflation_share_nonhetero(self) -> float:
        """
        Fraction of variance inflation not due to heterogeneity.

        This is a bookkeeping ratio, NOT an observation-dependent nuisance probability.
        Do not use this as a calibrator feature.
        """
        nuisance = self.artifact_var + self.context_var + self.pipeline_var + self.contact_var
        total = self.total_var_inflation
        return nuisance / total if total > 0 else 0.0

    @property
    def nuisance_fraction(self):
        """DEPRECATED: Use nuisance_probability or inflation_share_nonhetero."""
        raise RuntimeError(
            "nuisance_fraction is deprecated. "
            "Use nuisance_probability (observation-aware) or inflation_share_nonhetero (bookkeeping)."
        )


def compute_mechanism_posterior_v2(
    actin_fold: float,
    mito_fold: float,
    er_fold: float,
    nuisance: NuisanceModel,
    prior: Optional[Dict[Mechanism, float]] = None,
    prior_posterior: Optional['MechanismPosterior'] = None
) -> 'MechanismPosterior':
    """
    Bayesian posterior with per-mechanism covariance and NUISANCE competing hypothesis.

    P(m | x) ∝ P(x | m) P(m)
    P(NUISANCE | x) ∝ P(x | NUISANCE) P(NUISANCE)

    Mechanisms do NOT get mean_shift (clean competition).
    NUISANCE hypothesis represents measurement drift.

    CAUSAL ATTRIBUTION:
    If prior_posterior provided, compute split-ledger:
      - Δposterior_from_new_evidence: recompute with prior_posterior.nuisance (old nuisance)
      - Δposterior_from_nuisance_reweighting: recompute with new nuisance (current nuisance)

    This prevents "simulator candy" where nuisance actions mint unjustified certainty.
    """
    observed = np.array([actin_fold, mito_fold, er_fold])

    # Uniform prior if not specified
    if prior is None:
        prior = {mech: 1.0 / len(MECHANISM_SIGNATURES_V2) for mech in MECHANISM_SIGNATURES_V2}

    # Compute likelihood for each mechanism (NO mean shift)
    likelihoods = {}
    for mech, signature in MECHANISM_SIGNATURES_V2.items():
        # Mean: mechanism signature only (no nuisance shift)
        mean_eff = signature.to_mean_vector()

        # Covariance: mechanism variance + heterogeneity only
        cov_m = signature.to_cov_matrix()
        cov_hetero = np.eye(3) * nuisance.heterogeneity_var
        cov_eff = cov_m + cov_hetero

        # Multivariate normal likelihood
        mvn = multivariate_normal(mean=mean_eff, cov=cov_eff, allow_singular=True)
        likelihood = mvn.pdf(observed)
        likelihoods[mech] = likelihood

    # Add NUISANCE hypothesis (competing explanation for measurement drift)
    sigma2_meas_floor = 0.005  # Measurement noise floor (slightly larger than UNKNOWN)
    mu_nuis = np.array([1.0, 1.0, 1.0]) + nuisance.total_mean_shift
    cov_nuis = np.eye(3) * (sigma2_meas_floor + nuisance.total_var_inflation)
    mvn_nuis = multivariate_normal(mean=mu_nuis, cov=cov_nuis, allow_singular=True)
    likelihoods["NUISANCE"] = mvn_nuis.pdf(observed)

    # Extend prior to include NUISANCE
    prior_nuis = 0.10  # Start with 10% prior on nuisance hypothesis
    mech_mass = 1.0 - prior_nuis
    prior_extended = {m: prior[m] * mech_mass for m in MECHANISM_SIGNATURES_V2}
    prior_extended["NUISANCE"] = prior_nuis

    # Bayes rule (include NUISANCE in normalization)
    unnormalized = {k: likelihoods[k] * prior_extended[k] for k in likelihoods.keys()}
    Z = sum(unnormalized.values())

    if Z == 0:
        # Degenerate: all likelihoods zero (data way outside support)
        n_hyp = len(MECHANISM_SIGNATURES_V2) + 1
        posterior_probs = {m: 1.0 / n_hyp for m in MECHANISM_SIGNATURES_V2}
        nuisance_prob = 1.0 / n_hyp
    else:
        posterior_probs = {m: unnormalized[m] / Z for m in MECHANISM_SIGNATURES_V2}
        nuisance_prob = unnormalized["NUISANCE"] / Z

    # Agent 2: Ambiguity detection (RE-ADDED after file state issue)
    # Compute gap between top-2 mechanism likelihoods (before posterior transformation)
    mech_likelihoods = {m: likelihoods[m] for m in MECHANISM_SIGNATURES_V2}
    sorted_likes = sorted(mech_likelihoods.values(), reverse=True)

    if len(sorted_likes) >= 2 and sorted_likes[0] > 0:
        # Normalized gap: (top1 - top2) / top1 (scale-invariant)
        likelihood_gap = (sorted_likes[0] - sorted_likes[1]) / sorted_likes[0]
    else:
        likelihood_gap = 1.0  # Degenerate case: treat as "clear"

    is_ambiguous = (likelihood_gap < GAP_CLEAR)

    # Cap max probability if ambiguous
    if is_ambiguous:
        top_mech = max(posterior_probs.items(), key=lambda x: x[1])[0]
        top_prob = posterior_probs[top_mech]

        if top_prob > MAX_PROB_AMBIGUOUS:
            # Cap and redistribute
            excess = top_prob - MAX_PROB_AMBIGUOUS
            other_mechs = [m for m in posterior_probs.keys() if m != top_mech]
            other_total = sum(posterior_probs[m] for m in other_mechs)

            posterior_probs[top_mech] = MAX_PROB_AMBIGUOUS

            if other_total > 0:
                for m in other_mechs:
                    posterior_probs[m] += excess * (posterior_probs[m] / other_total)
            else:
                for m in other_mechs:
                    posterior_probs[m] += excess / len(other_mechs)

    # Compute uncertainty metric (monotonic with gap)
    if likelihood_gap < GAP_CLEAR:
        uncertainty = 1.0 - (likelihood_gap / GAP_CLEAR)
    else:
        uncertainty = 0.0

    # CAUSAL ATTRIBUTION: Split-ledger accounting
    # Compute how much posterior change came from new evidence vs. nuisance reduction
    attribution_source = None
    if prior_posterior is not None:
        # Counterfactual: "What if we had these observations but OLD nuisance?"
        # This isolates the contribution of nuisance reduction
        prior_nuisance = prior_posterior.nuisance

        # Recompute likelihoods with prior nuisance (holding observations constant)
        likelihoods_old_nuisance = {}
        for mech, signature in MECHANISM_SIGNATURES_V2.items():
            mean_eff = signature.to_mean_vector()
            cov_m = signature.to_cov_matrix()
            cov_hetero = np.eye(3) * prior_nuisance.heterogeneity_var
            cov_eff = cov_m + cov_hetero
            mvn = multivariate_normal(mean=mean_eff, cov=cov_eff, allow_singular=True)
            likelihoods_old_nuisance[mech] = mvn.pdf(observed)

        # NUISANCE hypothesis with prior nuisance
        sigma2_meas_floor = 0.005
        mu_nuis = np.array([1.0, 1.0, 1.0]) + prior_nuisance.total_mean_shift
        cov_nuis = np.eye(3) * (sigma2_meas_floor + prior_nuisance.total_var_inflation)
        mvn_nuis = multivariate_normal(mean=mu_nuis, cov=cov_nuis, allow_singular=True)
        likelihoods_old_nuisance["NUISANCE"] = mvn_nuis.pdf(observed)

        # Recompute posterior with old nuisance
        prior_nuis = 0.10
        mech_mass = 1.0 - prior_nuis
        prior_extended_old = {m: prior[m] * mech_mass for m in MECHANISM_SIGNATURES_V2}
        prior_extended_old["NUISANCE"] = prior_nuis

        unnormalized_old = {k: likelihoods_old_nuisance[k] * prior_extended_old[k] for k in likelihoods_old_nuisance.keys()}
        Z_old = sum(unnormalized_old.values())

        if Z_old > 0:
            posterior_probs_old_nuisance = {m: unnormalized_old[m] / Z_old for m in MECHANISM_SIGNATURES_V2}
            top_mech_old = max(posterior_probs_old_nuisance.items(), key=lambda x: x[1])[0]
            top_prob_old = posterior_probs_old_nuisance[top_mech_old]

            # Compare: how much did posterior improve?
            prior_top_prob = prior_posterior.top_probability
            current_top_prob = max(posterior_probs.values())
            counterfactual_top_prob = top_prob_old

            # Decompose change:
            # Total change = current - prior
            # Nuisance contribution = current - counterfactual (with old nuisance)
            # Evidence contribution = counterfactual - prior
            total_change = current_top_prob - prior_top_prob
            nuisance_contrib = current_top_prob - counterfactual_top_prob
            evidence_contrib = counterfactual_top_prob - prior_top_prob

            # Attribute based on dominant contribution
            if abs(total_change) < 0.01:
                attribution_source = "none"  # No significant change
            elif abs(nuisance_contrib) > abs(evidence_contrib) * 2:
                attribution_source = "nuisance_reweight"  # Nuisance reduction dominates
            elif abs(evidence_contrib) > abs(nuisance_contrib) * 2:
                attribution_source = "evidence"  # New evidence dominates
            else:
                attribution_source = "both"  # Mixed contribution

    # Agent 2: Guardrail - prevent reintroduction of dishonesty
    if is_ambiguous:
        top_prob_check = max(posterior_probs.values())
        assert top_prob_check <= MAX_PROB_AMBIGUOUS + 1e-9, \
            f"Ambiguous classification violated confidence cap: {top_prob_check:.4f} > {MAX_PROB_AMBIGUOUS}"

    return MechanismPosterior(
        probabilities=posterior_probs,
        observed_features=observed,
        likelihood_scores=likelihoods,
        prior=prior,
        nuisance=nuisance,
        nuisance_probability=nuisance_prob,
        attribution_source=attribution_source,
        # Agent 2: Ambiguity fields
        uncertainty=uncertainty,
        is_ambiguous=is_ambiguous,
        likelihood_gap=likelihood_gap
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

    # Nuisance probability: P(NUISANCE | x) from competing hypothesis
    nuisance_probability: Optional[float] = None

    # CAUSAL ATTRIBUTION: Track where posterior concentration came from
    # Used to prevent "simulator candy" where nuisance actions mint unjustified certainty
    attribution_source: Optional[str] = None  # "evidence" | "nuisance_reweight" | "both"

    # Agent 2: Explicit ambiguity representation
    # uncertainty measures epistemic uncertainty when mechanisms overlap in morphology space
    # This is NOT measurement noise - it's "how well can we distinguish mechanisms?"
    uncertainty: Optional[float] = None  # 0.0 = clear separation, 1.0 = maximal ambiguity
    is_ambiguous: Optional[bool] = None  # True if gap < GAP_CLEAR
    likelihood_gap: Optional[float] = None  # Gap between top-2 likelihoods (normalized)

    @property
    def top_mechanism(self) -> Mechanism:
        return max(self.probabilities.items(), key=lambda x: x[1])[0]

    @property
    def top_probability(self) -> float:
        return self.probabilities[self.top_mechanism]

    @property
    def mechanism_entropy_bits(self) -> float:
        """
        Mechanism posterior entropy: uncertainty about WHICH mechanism is operating.

        Agent 3 hardening: Explicitly named to prevent conflation with calibration entropy.
        This measures epistemic uncertainty over biological mechanisms, NOT measurement noise.

        Returns:
            Entropy in bits (information-theoretic, from mechanism posterior)
        """
        H = 0.0
        for p in self.probabilities.values():
            if p > 0:
                H -= p * np.log(p)
        return H

    @property
    def entropy(self) -> float:
        """
        DEPRECATED: Use mechanism_entropy_bits for clarity.

        This returns mechanism entropy (uncertainty about which biological process).
        Do NOT confuse with calibration entropy (uncertainty about noise/bias).
        """
        return self.mechanism_entropy_bits

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
        return 1.0 - (self.mechanism_entropy_bits / max_entropy) if max_entropy > 0 else 1.0

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
        ]

        # Agent 2: Add ambiguity information
        if self.uncertainty is not None:
            lines.append(f"  Uncertainty: {self.uncertainty:.3f}")
        if self.is_ambiguous is not None:
            amb_str = "YES" if self.is_ambiguous else "NO"
            lines.append(f"  Ambiguous: {amb_str}")
        if self.likelihood_gap is not None:
            lines.append(f"  Likelihood gap: {self.likelihood_gap:.3f}")

        lines.extend([
            f"",
            f"Full posterior:"
        ])

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


# =============================================================================
# Agent 3: Mechanism Posterior Calibration Tracking (ECE)
# =============================================================================

@dataclass
class CalibrationEvent:
    """
    Single classification event for calibration tracking.

    Records:
    - confidence: max posterior probability (how sure was the agent?)
    - correct: was the prediction actually right?

    Agent 3: This is PURE INSTRUMENTATION. No policy coupling.
    """
    confidence: float
    correct: bool

    def __post_init__(self):
        """Validate bounds."""
        assert 0.0 <= self.confidence <= 1.0, f"Confidence must be in [0,1], got {self.confidence}"
        assert isinstance(self.correct, bool), f"Correct must be bool, got {type(self.correct)}"


class MechanismCalibrationTracker:
    """
    Track mechanism posterior calibration over time.

    Answers: "When the agent says '90% sure', is it actually right ~90% of the time?"

    Agent 3 principles:
    - Pure instrumentation (no policy changes)
    - No filtering (track ALL classifications, even low confidence)
    - Deterministic ECE computation
    - Small-sample guardrails (min 30 samples for stability)

    Usage:
        tracker = MechanismCalibrationTracker()

        # After each classification
        tracker.record(
            predicted=posterior.top_mechanism,
            true_mechanism=ground_truth,
            posterior=posterior.probabilities
        )

        # Compute calibration
        ece, is_stable = tracker.compute_ece()
        if is_stable and ece > 0.15:
            logger.warning(f"Mechanism posteriors miscalibrated: ECE={ece:.3f}")
    """

    def __init__(self, min_samples_for_stability: int = 30):
        """
        Initialize calibration tracker.

        Args:
            min_samples_for_stability: Minimum samples before ECE is considered stable
        """
        self.events: List[CalibrationEvent] = []
        self.min_samples_for_stability = min_samples_for_stability

    def record(
        self,
        predicted: Mechanism,
        true_mechanism: Mechanism,
        posterior: Dict[Mechanism, float]
    ) -> None:
        """
        Record a single classification event.

        Args:
            predicted: Agent's predicted mechanism (argmax of posterior)
            true_mechanism: Ground truth mechanism (from simulator)
            posterior: Full posterior distribution

        Agent 3: This MUST be called on EVERY classification, no filtering.
        """
        confidence = max(posterior.values())
        correct = (predicted == true_mechanism)

        event = CalibrationEvent(confidence=confidence, correct=correct)
        self.events.append(event)

    def compute_ece(self, n_bins: int = 10) -> Tuple[float, bool]:
        """
        Compute Expected Calibration Error (ECE).

        ECE measures calibration: does "90% confident" mean "90% correct"?

        Formula:
            ECE = Σ_k (|B_k| / N) * |acc(B_k) - conf(B_k)|

        Where:
        - B_k = bin k (confidence range)
        - acc(B_k) = accuracy in bin k
        - conf(B_k) = mean confidence in bin k
        - N = total samples

        Args:
            n_bins: Number of confidence bins (default: 10)

        Returns:
            (ece, is_stable):
            - ece: Expected Calibration Error in [0, 1]
            - is_stable: True if n_samples >= min_samples_for_stability

        Agent 3: Deterministic, pure function. No side effects.
        """
        if len(self.events) == 0:
            return 0.0, False

        is_stable = len(self.events) >= self.min_samples_for_stability

        # Bin edges: [0, 0.1, 0.2, ..., 1.0]
        bin_edges = np.linspace(0.0, 1.0, n_bins + 1)

        # Group events by bin
        bins: List[List[CalibrationEvent]] = [[] for _ in range(n_bins)]

        for event in self.events:
            # Find which bin this confidence falls into
            bin_idx = int(event.confidence * n_bins)
            # Handle edge case: confidence = 1.0 falls into last bin
            if bin_idx == n_bins:
                bin_idx = n_bins - 1
            bins[bin_idx].append(event)

        # Compute ECE
        ece = 0.0
        n_total = len(self.events)

        for bin_events in bins:
            if len(bin_events) == 0:
                continue  # Skip empty bins

            # Accuracy in this bin
            n_correct = sum(1 for e in bin_events if e.correct)
            accuracy = n_correct / len(bin_events)

            # Mean confidence in this bin
            mean_confidence = sum(e.confidence for e in bin_events) / len(bin_events)

            # Calibration gap
            gap = abs(accuracy - mean_confidence)

            # Weighted by bin size
            weight = len(bin_events) / n_total
            ece += weight * gap

        return ece, is_stable

    def get_statistics(self) -> Dict[str, any]:
        """
        Get summary statistics for diagnostics.

        Returns dict with:
        - n_samples: Total classification events
        - mean_confidence: Average confidence
        - accuracy: Overall accuracy
        - ece: Expected Calibration Error
        - is_stable: Whether ECE is stable
        """
        if len(self.events) == 0:
            return {
                "n_samples": 0,
                "mean_confidence": 0.0,
                "accuracy": 0.0,
                "ece": 0.0,
                "is_stable": False
            }

        n_correct = sum(1 for e in self.events if e.correct)
        accuracy = n_correct / len(self.events)
        mean_confidence = sum(e.confidence for e in self.events) / len(self.events)
        ece, is_stable = self.compute_ece()

        return {
            "n_samples": len(self.events),
            "mean_confidence": mean_confidence,
            "accuracy": accuracy,
            "ece": ece,
            "is_stable": is_stable
        }


def compute_ece(
    events: List[CalibrationEvent],
    n_bins: int = 10
) -> float:
    """
    Pure function: Compute Expected Calibration Error.

    Agent 3: This is the canonical ECE implementation.
    Use this for testing in isolation.

    Args:
        events: List of calibration events
        n_bins: Number of confidence bins

    Returns:
        ECE in [0, 1]

    Example:
        # Perfectly calibrated
        events = [CalibrationEvent(0.9, True) for _ in range(90)]
        events += [CalibrationEvent(0.9, False) for _ in range(10)]
        ece = compute_ece(events)
        assert ece < 0.05  # Should be near-zero

        # Overconfident
        events = [CalibrationEvent(0.9, True) for _ in range(60)]
        events += [CalibrationEvent(0.9, False) for _ in range(40)]
        ece = compute_ece(events)
        assert ece > 0.2  # Should be high
    """
    if len(events) == 0:
        return 0.0

    # Bin edges
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)

    # Group by bin
    bins: List[List[CalibrationEvent]] = [[] for _ in range(n_bins)]

    for event in events:
        bin_idx = int(event.confidence * n_bins)
        if bin_idx == n_bins:
            bin_idx = n_bins - 1
        bins[bin_idx].append(event)

    # Compute ECE
    ece = 0.0
    n_total = len(events)

    for bin_events in bins:
        if len(bin_events) == 0:
            continue

        # Accuracy and confidence in bin
        accuracy = sum(1 for e in bin_events if e.correct) / len(bin_events)
        mean_conf = sum(e.confidence for e in bin_events) / len(bin_events)

        # Weighted gap
        weight = len(bin_events) / n_total
        ece += weight * abs(accuracy - mean_conf)

    return ece


# =============================================================================
# Agent 2: Classification Diagnostics Emission (RE-ADDED)
# =============================================================================

def emit_mechanism_classification_diagnostic(
    posterior: MechanismPosterior,
    cycle_id: Optional[int] = None,
    design_id: Optional[str] = None,
) -> Dict[str, any]:
    """
    Create diagnostic event for mechanism classification.

    This event is emitted to diagnostics.jsonl to make classification observable.
    Enables auditability of overconfidence and ambiguity.

    Args:
        posterior: MechanismPosterior object
        cycle_id: Optional cycle number
        design_id: Optional design identifier

    Returns:
        Dict ready for JSON serialization to diagnostics.jsonl

    Example event:
        {
          "event": "mechanism_classification",
          "cycle_id": 5,
          "top1_mechanism": "er_stress",
          "top1_prob": 0.62,
          "top2_mechanism": "microtubule",
          "top2_prob": 0.28,
          "gap": 0.12,
          "uncertainty": 0.35,
          "is_ambiguous": true,
          "n_channels_used": 3
        }
    """
    # Get top 2 mechanisms
    sorted_mechs = sorted(posterior.probabilities.items(), key=lambda x: -x[1])
    top1_mech, top1_prob = sorted_mechs[0]
    top2_mech, top2_prob = sorted_mechs[1] if len(sorted_mechs) >= 2 else (None, 0.0)

    event = {
        "event": "mechanism_classification",
        "top1_mechanism": top1_mech.value,
        "top1_prob": float(top1_prob),
        "top2_mechanism": top2_mech.value if top2_mech else None,
        "top2_prob": float(top2_prob),
        "gap": float(posterior.likelihood_gap) if posterior.likelihood_gap is not None else None,
        "uncertainty": float(posterior.uncertainty) if posterior.uncertainty is not None else None,
        "is_ambiguous": posterior.is_ambiguous,
        "n_channels_used": len(posterior.observed_features),
    }

    if cycle_id is not None:
        event["cycle_id"] = cycle_id
    if design_id is not None:
        event["design_id"] = design_id

    return event


def emit_overconfidence_warning(
    posterior: MechanismPosterior,
    cycle_id: Optional[int] = None,
    design_id: Optional[str] = None,
) -> Optional[Dict[str, any]]:
    """
    Emit overconfidence warning if high confidence in ambiguous region.

    Returns None if no warning needed.

    Condition for warning:
    - top1_prob > 0.75 (high confidence claimed)
    - AND gap < GAP_CLEAR (mechanisms are not clearly separated)

    This is passive observational only - does NOT block execution.

    Args:
        posterior: MechanismPosterior object
        cycle_id: Optional cycle number
        design_id: Optional design identifier

    Returns:
        Warning event dict or None
    """
    if posterior.top_probability > 0.75 and posterior.is_ambiguous:
        warning = {
            "event": "mechanism_overconfidence_warning",
            "top_mechanism": posterior.top_mechanism.value,
            "claimed_prob": float(posterior.top_probability),
            "likelihood_gap": float(posterior.likelihood_gap) if posterior.likelihood_gap else None,
            "uncertainty": float(posterior.uncertainty) if posterior.uncertainty else None,
            "reason": f"High confidence ({posterior.top_probability:.2f}) claimed in ambiguous region (gap={posterior.likelihood_gap:.3f} < {GAP_CLEAR})",
        }

        if cycle_id is not None:
            warning["cycle_id"] = cycle_id
        if design_id is not None:
            warning["design_id"] = design_id

        return warning

    return None


if __name__ == "__main__":
    passed = cosplay_detector_test()
    if passed:
        print("\n✓ Cosplay detector: PASSED")
    else:
        print("\n✗ Cosplay detector: FAILED (still nearest-neighbor)")
