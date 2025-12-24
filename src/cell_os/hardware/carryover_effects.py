"""
Pipette carryover-induced dose contamination.

Key physics:
1. Pipette tips/channels retain residual volume after dispense
2. Residual contaminates next dispense in sequence
3. This is SEQUENCE-DEPENDENT (not geometry-dependent)
4. Creates "why is column 7 cursed" pathology (blank after hot dispense)

Variance-first implementation:
- carryover_fraction is epistemic prior (not uniquely identifiable)
- Sequence contamination is deterministic (modeled)
- Ridge uncertainty computed by bracket quantiles
"""

import numpy as np
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from ._impl import stable_u32


# Artifact contract specification
ARTIFACT_SPEC = {
    'domain': 'sequence',
    'state_mutations': ['effective_dose'],
    'affected_observables': ['effective_dose'],
    'epistemic_prior': {
        'parameter': 'carryover_fraction',
        'distribution': 'Lognormal(mean=0.005, CV=0.40)',
        'calibration_method': 'blank_after_hot'
    },
    'ledger_terms': {
        'modeled': 'VAR_INSTRUMENT_PIPETTE_CARRYOVER_SEQUENCE',
        'ridge': 'VAR_CALIBRATION_CARRYOVER_FRACTION',
    },
    'correlation_groups': {
        'modeled': 'carryover_tip_{tip_id}',
        'ridge': 'carryover_ridge',
    },
    'forbidden_dependencies': ['well_geometry', 'plate_position', 'edge_distance'],
    'version': '1.0',
    'implemented': '2025-12-23',
    'tests': ['test_carryover_effects.py']
}


@dataclass
class CarryoverFractionPrior:
    """
    Carryover fraction prior distribution with provenance tracking.

    Distribution: Lognormal(mu_log, sigma_log) clipped to [clip_min, clip_max]
    Units: Fraction of previous dose retained and transferred
    """
    mu_log: float = field(default_factory=lambda: np.log(0.005) - 0.5 * np.log(1.0 + 0.40**2))
    sigma_log: float = field(default_factory=lambda: np.sqrt(np.log(1.0 + 0.40**2)))
    clip_min: float = 0.0001  # 0.01% (very clean)
    clip_max: float = 0.05    # 5% (very dirty)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    evidence_source: str = "default"
    evidence_summary: str = "Default prior: Lognormal(mean=0.5%, CV=0.40)"
    calibration_history: list = field(default_factory=list)

    @property
    def mean(self) -> float:
        """Expected value of lognormal (before clipping)."""
        return float(np.exp(self.mu_log + 0.5 * self.sigma_log ** 2))

    @property
    def cv(self) -> float:
        """Coefficient of variation (before clipping)."""
        return float(np.sqrt(np.exp(self.sigma_log ** 2) - 1.0))

    def sample(self, seed: int, tip_id: str = "tip_default") -> float:
        """Sample carryover fraction deterministically."""
        frac_seed = stable_u32(f"carryover_frac_prior_{tip_id}_{seed}")
        frac_rng = np.random.default_rng(frac_seed)
        frac_sample = frac_rng.lognormal(self.mu_log, self.sigma_log)
        return float(np.clip(frac_sample, self.clip_min, self.clip_max))


def sample_carryover_fraction_from_prior(
    seed: int,
    tip_id: str = "tip_default",
    frac_mean: float = None,
    frac_cv: float = None,
    prior: Optional[CarryoverFractionPrior] = None
) -> float:
    """Sample carryover fraction from prior distribution."""
    if prior is not None:
        return prior.sample(seed=seed, tip_id=tip_id)

    # Legacy path
    if frac_mean is None:
        frac_mean = 0.005  # 0.5%
    if frac_cv is None:
        frac_cv = 0.40  # 40% CV

    sigma_squared = np.log(1.0 + frac_cv ** 2)
    sigma_log = np.sqrt(sigma_squared)
    mu_log = np.log(frac_mean) - sigma_squared / 2.0

    temp_prior = CarryoverFractionPrior(mu_log=mu_log, sigma_log=sigma_log)
    return temp_prior.sample(seed=seed, tip_id=tip_id)


def calculate_carryover_contamination(
    previous_dose_uM: float,
    carryover_fraction: float,
    wash_efficiency: float = 0.0
) -> Dict[str, float]:
    """
    Calculate dose contamination from carryover.

    Args:
        previous_dose_uM: Dose in previous dispense (µM)
        carryover_fraction: Fraction retained and transferred (e.g., 0.005 = 0.5%)
        wash_efficiency: Fraction of carryover removed by wash (0-1, default 0 = no wash)

    Returns:
        Dict with:
        - carryover_dose_uM: Contamination dose added to next well
        - effective_carryover_fraction: After wash (if any)
    """
    # Wash reduces carryover
    effective_carryover = carryover_fraction * (1.0 - wash_efficiency)

    # Contamination dose
    carryover_dose_uM = previous_dose_uM * effective_carryover

    return {
        'carryover_dose_uM': float(carryover_dose_uM),
        'effective_carryover_fraction': float(effective_carryover)
    }


def apply_carryover_to_sequence(
    dose_sequence_uM: List[float],
    carryover_fraction: float,
    wash_efficiency: float = 0.0
) -> List[float]:
    """
    Apply carryover contamination across a dispense sequence.

    CRITICAL: This is SEQUENCE-DEPENDENT, not geometry-dependent.
    A well's contamination depends on what was dispensed BEFORE it,
    not on its spatial position.

    Args:
        dose_sequence_uM: List of intended doses in dispense order
        carryover_fraction: Fraction carried over between dispenses
        wash_efficiency: Wash effectiveness (0-1)

    Returns:
        List of effective doses including carryover contamination
    """
    if len(dose_sequence_uM) == 0:
        return []

    effective_doses = []
    previous_dose = 0.0  # First dispense has no carryover

    for intended_dose in dose_sequence_uM:
        # Calculate contamination from previous dispense
        result = calculate_carryover_contamination(
            previous_dose_uM=previous_dose,
            carryover_fraction=carryover_fraction,
            wash_efficiency=wash_efficiency
        )

        # Effective dose = intended + carryover
        effective_dose = intended_dose + result['carryover_dose_uM']
        effective_doses.append(effective_dose)

        # Update for next iteration
        previous_dose = intended_dose  # What was INTENDED, not effective

    return effective_doses


def compute_carryover_ridge_uncertainty(
    previous_dose_uM: float,
    frac_prior_cv: float = 0.40
) -> Dict[str, float]:
    """
    Compute uncertainty in carryover contamination from fraction prior (two-point bracket).

    Args:
        previous_dose_uM: Dose in previous dispense
        frac_prior_cv: Prior CV for carryover fraction (default 0.40)

    Returns:
        Dict with:
        - carryover_dose_cv: CV in contamination dose
    """
    if frac_prior_cv <= 0:
        return {'carryover_dose_cv': 0.0}

    # Two-point bracket: 5th and 95th percentiles
    # For lognormal with CV=0.40:
    # 5th ≈ 0.47 × mean, 95th ≈ 2.13 × mean
    scale = frac_prior_cv / 0.40
    frac_low = 0.005 / (1.0 + 2.13 * scale)   # ~0.0024 for CV=0.40
    frac_high = 0.005 * (1.0 + 2.13 * scale)  # ~0.0107 for CV=0.40

    # Evaluate at both quantiles
    carryover_low = previous_dose_uM * frac_low
    carryover_high = previous_dose_uM * frac_high

    # Half-range as uncertainty estimate
    carryover_half_range = abs(carryover_high - carryover_low) / 2.0

    # Convert to CV
    carryover_nominal = (carryover_low + carryover_high) / 2.0
    carryover_dose_cv = carryover_half_range / (carryover_nominal + 1e-9)

    return {
        'carryover_dose_cv': float(carryover_dose_cv)
    }


def update_carryover_fraction_prior_from_blank_after_hot(
    prior: CarryoverFractionPrior,
    hot_dose_uM: float,
    blank_observed_dose_uM: float,
    measurement_uncertainty_uM: float = 0.01,
    plate_id: str = "unknown",
    calibration_date: str = None
) -> Tuple[CarryoverFractionPrior, dict]:
    """
    Update carryover fraction prior from blank-after-hot calibration.

    Evidence: Blank well dispensed after high-dose well shows contamination.

    Args:
        prior: Current carryover fraction prior
        hot_dose_uM: Dose in previous (hot) dispense (µM)
        blank_observed_dose_uM: Measured dose in blank well (µM)
        measurement_uncertainty_uM: Measurement noise (default 0.01 µM)
        plate_id: Calibration plate identifier
        calibration_date: ISO date string

    Returns:
        (updated_prior, report)
    """
    if calibration_date is None:
        calibration_date = datetime.now().isoformat()

    # Forward model: predicted blank dose given carryover fraction
    def predict_blank_dose(frac: float, hot: float) -> float:
        return frac * hot

    # Predict blank dose for grid of fractions
    frac_grid = np.linspace(prior.clip_min, prior.clip_max, 200)

    # Evaluate prior on grid
    log_prior = -0.5 * ((np.log(frac_grid) - prior.mu_log) / prior.sigma_log) ** 2
    log_prior -= np.log(prior.sigma_log * frac_grid * np.sqrt(2 * np.pi))

    # Evaluate likelihood: observation
    predicted_blank = np.array([predict_blank_dose(f, hot_dose_uM) for f in frac_grid])

    # Likelihood: Normal(obs | pred, sigma)
    log_likelihood = -0.5 * ((blank_observed_dose_uM - predicted_blank) / measurement_uncertainty_uM) ** 2
    log_likelihood -= np.log(measurement_uncertainty_uM * np.sqrt(2 * np.pi))

    # Posterior
    log_posterior = log_prior + log_likelihood
    log_posterior -= np.max(log_posterior)  # Numerical stability
    posterior = np.exp(log_posterior)

    # Normalize
    try:
        posterior_norm = np.trapezoid(posterior, frac_grid)
    except AttributeError:
        posterior_norm = np.trapz(posterior, frac_grid)
    posterior /= posterior_norm

    # Compute posterior moments
    try:
        posterior_mean = np.trapezoid(frac_grid * posterior, frac_grid)
        posterior_var = np.trapezoid((frac_grid - posterior_mean) ** 2 * posterior, frac_grid)
    except AttributeError:
        posterior_mean = np.trapz(frac_grid * posterior, frac_grid)
        posterior_var = np.trapz((frac_grid - posterior_mean) ** 2 * posterior, frac_grid)

    posterior_std = np.sqrt(posterior_var)
    posterior_cv = posterior_std / posterior_mean

    # Fit lognormal to posterior
    sigma_log_new = np.sqrt(np.log(1.0 + posterior_cv ** 2))
    mu_log_new = np.log(posterior_mean) - 0.5 * sigma_log_new ** 2

    # Create updated prior
    updated_prior = CarryoverFractionPrior(
        mu_log=mu_log_new,
        sigma_log=sigma_log_new,
        clip_min=prior.clip_min,
        clip_max=prior.clip_max,
        created_at=prior.created_at,
        evidence_source=f"blank_after_hot_{plate_id}",
        evidence_summary=(
            f"Updated from blank-after-hot calibration: "
            f"hot={hot_dose_uM:.2f}µM, blank_obs={blank_observed_dose_uM:.3f}µM, "
            f"mean {prior.mean:.4f}→{posterior_mean:.4f}, "
            f"CV {prior.cv:.2f}→{posterior_cv:.2f}"
        ),
        calibration_history=prior.calibration_history + [
            {
                'date': calibration_date,
                'source': 'blank_after_hot',
                'plate_id': plate_id,
                'hot_dose_uM': float(hot_dose_uM),
                'blank_observed_dose_uM': float(blank_observed_dose_uM),
                'prior_mean': float(prior.mean),
                'prior_cv': float(prior.cv),
                'posterior_mean': float(posterior_mean),
                'posterior_cv': float(posterior_cv)
            }
        ]
    )

    # Generate report
    sigma_reduction = (prior.sigma_log - sigma_log_new) / prior.sigma_log
    report = {
        'prior_mean': float(prior.mean),
        'prior_cv': float(prior.cv),
        'posterior_mean': float(posterior_mean),
        'posterior_cv': float(posterior_cv),
        'hot_dose_uM': float(hot_dose_uM),
        'blank_observed_dose_uM': float(blank_observed_dose_uM),
        'sigma_reduction': float(sigma_reduction),
        'provenance': (
            f"Prior updated: mean {prior.mean:.4f}→{posterior_mean:.4f}, "
            f"CV {prior.cv:.2f}→{posterior_cv:.2f} "
            f"(sigma reduced {sigma_reduction:.1%}) "
            f"based on blank-after-hot {plate_id}"
        ),
        'calibration_date': calibration_date,
        'plate_id': plate_id
    }

    return updated_prior, report


def get_dispense_sequence_for_plate(
    plate_format: int = 384,
    dispense_pattern: str = "row_wise"
) -> List[str]:
    """
    Get dispense sequence (well order) for a plate.

    CRITICAL: Carryover depends on DISPENSE ORDER, not spatial position.

    Args:
        plate_format: 384 or 96
        dispense_pattern: "row_wise" (A1, A2, ..., A24, B1, B2, ...) or
                         "column_wise" (A1, B1, C1, ..., P1, A2, B2, ...)

    Returns:
        List of well IDs in dispense order
    """
    if plate_format == 384:
        rows = 16  # A-P
        cols = 24  # 1-24
    elif plate_format == 96:
        rows = 8   # A-H
        cols = 12  # 1-12
    else:
        raise ValueError(f"Unsupported plate format: {plate_format}")

    sequence = []

    if dispense_pattern == "row_wise":
        for row_idx in range(rows):
            for col_idx in range(cols):
                row_letter = chr(ord('A') + row_idx)
                col_number = col_idx + 1
                sequence.append(f"{row_letter}{col_number}")

    elif dispense_pattern == "column_wise":
        for col_idx in range(cols):
            for row_idx in range(rows):
                row_letter = chr(ord('A') + row_idx)
                col_number = col_idx + 1
                sequence.append(f"{row_letter}{col_number}")

    else:
        raise ValueError(f"Unsupported dispense pattern: {dispense_pattern}")

    return sequence
