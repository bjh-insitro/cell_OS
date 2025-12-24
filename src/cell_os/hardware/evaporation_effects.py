"""
Evaporation-induced volume loss and concentration drift.

Key physics:
1. Edge wells evaporate faster than center wells (spatial gradient)
2. Volume loss → concentration increase (dose amplification)
3. Bounded (can't evaporate below some minimum, saturates over time)
4. Separable from aspiration (different geometry, different timescale)

Variance-first implementation:
- base_evap_rate is epistemic prior (not uniquely identifiable)
- Spatial field is deterministic (modeled)
- Ridge uncertainty computed by bracket quantiles
"""

import numpy as np
from typing import Dict, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
from ._impl import stable_u32


# Artifact contract specification
ARTIFACT_SPEC = {
    'domain': 'spatial',
    'state_mutations': ['volume', 'effective_dose'],
    'affected_observables': ['effective_dose', 'concentration'],
    'epistemic_prior': {
        'parameter': 'base_evap_rate',
        'distribution': 'Lognormal(mean=0.5, CV=0.30)',
        'calibration_method': 'gravimetry'
    },
    'ledger_terms': {
        'modeled': 'VAR_INSTRUMENT_EVAPORATION_GEOMETRY',
        'ridge': 'VAR_CALIBRATION_EVAPORATION_RATE',
    },
    'correlation_groups': {
        'modeled': 'evaporation_geometry',
        'ridge': 'evaporation_ridge',
    },
    'forbidden_dependencies': ['dispense_sequence', 'sequence_index', 'aspiration_angle'],
    'version': '1.0',
    'implemented': '2025-12-23',
    'tests': ['test_evaporation_effects.py']
}


@dataclass
class EvaporationRatePrior:
    """
    Base evaporation rate prior distribution with provenance tracking.

    Distribution: Lognormal(mu_log, sigma_log) clipped to [clip_min, clip_max]
    Units: µL/hour/well baseline (scaled by exposure field)
    """
    mu_log: float = field(default_factory=lambda: np.log(0.5) - 0.5 * np.log(1.0 + 0.30**2))
    sigma_log: float = field(default_factory=lambda: np.sqrt(np.log(1.0 + 0.30**2)))
    clip_min: float = 0.1  # µL/h (very slow)
    clip_max: float = 2.0  # µL/h (very fast)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    evidence_source: str = "default"
    evidence_summary: str = "Default prior: Lognormal(mean=0.5 µL/h, CV=0.30)"
    calibration_history: list = field(default_factory=list)

    @property
    def mean(self) -> float:
        """Expected value of lognormal (before clipping)."""
        return float(np.exp(self.mu_log + 0.5 * self.sigma_log ** 2))

    @property
    def cv(self) -> float:
        """Coefficient of variation (before clipping)."""
        return float(np.sqrt(np.exp(self.sigma_log ** 2) - 1.0))

    def sample(self, seed: int, instrument_id: str = "plate_default") -> float:
        """Sample evaporation rate deterministically."""
        rate_seed = stable_u32(f"evap_rate_prior_{instrument_id}_{seed}")
        rate_rng = np.random.default_rng(rate_seed)
        rate_sample = rate_rng.lognormal(self.mu_log, self.sigma_log)
        return float(np.clip(rate_sample, self.clip_min, self.clip_max))


def sample_evaporation_rate_from_prior(
    seed: int,
    instrument_id: str = "plate_default",
    rate_mean: float = None,
    rate_cv: float = None,
    prior: Optional[EvaporationRatePrior] = None
) -> float:
    """Sample base evaporation rate from prior distribution."""
    if prior is not None:
        return prior.sample(seed=seed, instrument_id=instrument_id)

    # Legacy path
    if rate_mean is None:
        rate_mean = 0.5  # µL/h baseline
    if rate_cv is None:
        rate_cv = 0.30  # 30% CV

    sigma_squared = np.log(1.0 + rate_cv ** 2)
    sigma_log = np.sqrt(sigma_squared)
    mu_log = np.log(rate_mean) - sigma_squared / 2.0

    temp_prior = EvaporationRatePrior(mu_log=mu_log, sigma_log=sigma_log)
    return temp_prior.sample(seed=seed, instrument_id=instrument_id)


def calculate_evaporation_exposure(
    well_position: str,
    plate_format: int = 384
) -> float:
    """
    Calculate evaporation exposure field from plate geometry.

    Edge wells evaporate faster than center wells (temperature gradient,
    air flow patterns, meniscus effects).

    Args:
        well_position: e.g., "A1", "P24"
        plate_format: 384 or 96

    Returns:
        Exposure factor in [1.0, 1.5] where:
        - 1.0 = center (minimum evaporation)
        - 1.5 = corner (maximum evaporation)
    """
    import re
    match = re.match(r'^([A-P])(\d{1,2})$', well_position)
    if not match:
        return 1.0  # Fallback

    row_letter = match.group(1)
    col_number = int(match.group(2))

    # Get plate dimensions
    if plate_format == 384:
        max_row_idx = 15  # A=0, P=15
        max_col_idx = 23  # 1=0, 24=23
    elif plate_format == 96:
        max_row_idx = 7   # A=0, H=7
        max_col_idx = 11  # 1=0, 12=11
    else:
        return 1.0

    # Convert to indices
    row_idx = ord(row_letter) - ord('A')
    col_idx = col_number - 1

    # Normalize to [0, 1]
    row_normalized = row_idx / max_row_idx
    col_normalized = col_idx / max_col_idx

    # Distance from center (Manhattan distance in normalized coords)
    row_dist_from_center = abs(row_normalized - 0.5)
    col_dist_from_center = abs(col_normalized - 0.5)

    # Edge distance: max distance to nearest edge
    edge_distance = max(row_dist_from_center, col_dist_from_center)

    # Map to exposure: [0, 0.5] → [1.0, 1.5]
    # Corners (edge_distance=0.5) get 1.5×
    # Center (edge_distance=0.0) gets 1.0×
    exposure = 1.0 + edge_distance * 1.0

    return float(np.clip(exposure, 1.0, 1.5))


def calculate_volume_loss_over_time(
    initial_volume_ul: float,
    time_hours: float,
    base_evap_rate_ul_per_h: float,
    exposure: float,
    min_volume_fraction: float = 0.3
) -> Dict[str, float]:
    """
    Calculate volume loss from evaporation over time.

    Args:
        initial_volume_ul: Starting volume (e.g., 50 µL for 384-well)
        time_hours: Elapsed time since plating
        base_evap_rate_ul_per_h: Base evaporation rate (µL/hour)
        exposure: Spatial exposure factor (1.0-1.5)
        min_volume_fraction: Minimum volume as fraction of initial (default 0.3)

    Returns:
        Dict with:
        - volume_lost_ul: Total volume lost (µL)
        - volume_current_ul: Current volume (µL)
        - volume_fraction: Current volume as fraction of initial
        - concentration_multiplier: Factor by which concentrations increased
    """
    # Effective evaporation rate
    effective_rate = base_evap_rate_ul_per_h * exposure

    # Linear volume loss (simplified, could add saturation)
    volume_lost_ul = effective_rate * time_hours

    # Minimum volume constraint
    min_volume_ul = initial_volume_ul * min_volume_fraction
    volume_current_ul = max(min_volume_ul, initial_volume_ul - volume_lost_ul)

    # Actual volume lost (accounting for floor)
    volume_lost_ul = initial_volume_ul - volume_current_ul

    # Volume fraction
    volume_fraction = volume_current_ul / initial_volume_ul

    # Concentration multiplier (inverse of volume fraction)
    # If volume drops to 50%, concentration doubles
    concentration_multiplier = initial_volume_ul / volume_current_ul

    return {
        'volume_lost_ul': float(volume_lost_ul),
        'volume_current_ul': float(volume_current_ul),
        'volume_fraction': float(volume_fraction),
        'concentration_multiplier': float(concentration_multiplier)
    }


def get_evaporation_contribution_to_effective_dose(
    concentration_multiplier: float,
    baseline_dose_uM: float = 1.0
) -> Dict[str, float]:
    """
    Convert evaporation-induced concentration change into effective dose change.

    Args:
        concentration_multiplier: Factor by which concentration increased (>= 1.0)
        baseline_dose_uM: Baseline dose before evaporation (for delta computation)

    Returns:
        Dict with:
        - effective_dose_multiplier: Same as concentration_multiplier
        - dose_delta_uM: Absolute change in dose
        - dose_delta_fraction: Fractional change in dose
    """
    effective_dose_multiplier = concentration_multiplier

    # Delta in µM
    dose_delta_uM = baseline_dose_uM * (concentration_multiplier - 1.0)

    # Fractional change
    dose_delta_fraction = concentration_multiplier - 1.0

    return {
        'effective_dose_multiplier': float(effective_dose_multiplier),
        'dose_delta_uM': float(dose_delta_uM),
        'dose_delta_fraction': float(dose_delta_fraction)
    }


def compute_evaporation_ridge_uncertainty(
    exposure: float,
    time_hours: float,
    initial_volume_ul: float,
    rate_prior_cv: float = 0.30
) -> Dict[str, float]:
    """
    Compute uncertainty in evaporation effects from rate prior (two-point bracket).

    Args:
        exposure: Spatial exposure factor
        time_hours: Elapsed time
        initial_volume_ul: Starting volume
        rate_prior_cv: Prior CV for evaporation rate (default 0.30)

    Returns:
        Dict with:
        - volume_fraction_cv: CV in volume fraction
        - concentration_multiplier_cv: CV in concentration multiplier
        - effective_dose_cv: CV in effective dose
    """
    if rate_prior_cv <= 0:
        return {
            'volume_fraction_cv': 0.0,
            'concentration_multiplier_cv': 0.0,
            'effective_dose_cv': 0.0
        }

    # Two-point bracket: 5th and 95th percentiles
    # For lognormal with CV=0.30:
    # 5th ≈ 0.61 × mean, 95th ≈ 1.64 × mean
    scale = rate_prior_cv / 0.30
    rate_low = 0.5 / (1.0 + 1.64 * scale)   # ~0.30 for CV=0.30
    rate_high = 0.5 * (1.0 + 1.64 * scale)  # ~0.82 for CV=0.30

    # Evaluate at both quantiles
    def eval_evaporation(rate):
        result = calculate_volume_loss_over_time(
            initial_volume_ul=initial_volume_ul,
            time_hours=time_hours,
            base_evap_rate_ul_per_h=rate,
            exposure=exposure,
            min_volume_fraction=0.3
        )
        return result['volume_fraction'], result['concentration_multiplier']

    vol_frac_low, conc_mult_low = eval_evaporation(rate_low)
    vol_frac_high, conc_mult_high = eval_evaporation(rate_high)

    # Half-range as uncertainty estimate
    vol_frac_half_range = abs(vol_frac_high - vol_frac_low) / 2.0
    conc_mult_half_range = abs(conc_mult_high - conc_mult_low) / 2.0

    # Convert to CV
    vol_frac_nominal = (vol_frac_low + vol_frac_high) / 2.0
    conc_mult_nominal = (conc_mult_low + conc_mult_high) / 2.0

    vol_frac_cv = vol_frac_half_range / (vol_frac_nominal + 1e-9)
    conc_mult_cv = conc_mult_half_range / (conc_mult_nominal + 1e-9)

    # Effective dose CV = concentration multiplier CV (linear propagation)
    effective_dose_cv = conc_mult_cv

    return {
        'volume_fraction_cv': float(vol_frac_cv),
        'concentration_multiplier_cv': float(conc_mult_cv),
        'effective_dose_cv': float(effective_dose_cv)
    }


def update_evaporation_rate_prior_from_gravimetry(
    prior: EvaporationRatePrior,
    edge_loss_ul: float,
    center_loss_ul: float,
    time_hours: float,
    edge_exposure: float = 1.5,
    center_exposure: float = 1.0,
    measurement_uncertainty: float = 0.10,
    plate_id: str = "unknown",
    calibration_date: str = None
) -> Tuple[EvaporationRatePrior, dict]:
    """
    Update evaporation rate prior from gravimetric calibration.

    Evidence: Volume loss at edge vs center wells over time.

    Args:
        prior: Current evaporation rate prior
        edge_loss_ul: Measured volume loss at edge wells (µL)
        center_loss_ul: Measured volume loss at center wells (µL)
        time_hours: Measurement duration (hours)
        edge_exposure: Exposure factor for edge wells (default 1.5)
        center_exposure: Exposure factor for center wells (default 1.0)
        measurement_uncertainty: Measurement noise (default 0.10 = 10%)
        plate_id: Calibration plate identifier
        calibration_date: ISO date string

    Returns:
        (updated_prior, report)
    """
    if calibration_date is None:
        calibration_date = datetime.now().isoformat()

    # Forward model: predicted loss given rate
    def predict_loss(rate: float, exposure: float, time: float) -> float:
        return rate * exposure * time

    # Predict loss at edge and center for grid of rates
    rate_grid = np.linspace(prior.clip_min, prior.clip_max, 200)

    # Evaluate prior on grid
    log_prior = -0.5 * ((np.log(rate_grid) - prior.mu_log) / prior.sigma_log) ** 2
    log_prior -= np.log(prior.sigma_log * rate_grid * np.sqrt(2 * np.pi))

    # Evaluate likelihood: two observations (edge + center)
    predicted_edge = np.array([predict_loss(r, edge_exposure, time_hours) for r in rate_grid])
    predicted_center = np.array([predict_loss(r, center_exposure, time_hours) for r in rate_grid])

    # Likelihood: Normal(obs | pred, sigma)
    sigma_edge = edge_loss_ul * measurement_uncertainty
    sigma_center = center_loss_ul * measurement_uncertainty

    log_likelihood_edge = -0.5 * ((edge_loss_ul - predicted_edge) / sigma_edge) ** 2
    log_likelihood_center = -0.5 * ((center_loss_ul - predicted_center) / sigma_center) ** 2

    log_likelihood = log_likelihood_edge + log_likelihood_center

    # Posterior
    log_posterior = log_prior + log_likelihood
    log_posterior -= np.max(log_posterior)  # Numerical stability
    posterior = np.exp(log_posterior)

    # Normalize
    try:
        posterior_norm = np.trapezoid(posterior, rate_grid)
    except AttributeError:
        posterior_norm = np.trapz(posterior, rate_grid)
    posterior /= posterior_norm

    # Compute posterior moments
    try:
        posterior_mean = np.trapezoid(rate_grid * posterior, rate_grid)
        posterior_var = np.trapezoid((rate_grid - posterior_mean) ** 2 * posterior, rate_grid)
    except AttributeError:
        posterior_mean = np.trapz(rate_grid * posterior, rate_grid)
        posterior_var = np.trapz((rate_grid - posterior_mean) ** 2 * posterior, rate_grid)

    posterior_std = np.sqrt(posterior_var)
    posterior_cv = posterior_std / posterior_mean

    # Fit lognormal to posterior
    sigma_log_new = np.sqrt(np.log(1.0 + posterior_cv ** 2))
    mu_log_new = np.log(posterior_mean) - 0.5 * sigma_log_new ** 2

    # Create updated prior
    updated_prior = EvaporationRatePrior(
        mu_log=mu_log_new,
        sigma_log=sigma_log_new,
        clip_min=prior.clip_min,
        clip_max=prior.clip_max,
        created_at=prior.created_at,
        evidence_source=f"gravimetry_{plate_id}",
        evidence_summary=(
            f"Updated from gravimetric calibration: "
            f"edge_loss={edge_loss_ul:.2f}µL, center_loss={center_loss_ul:.2f}µL over {time_hours:.1f}h, "
            f"mean {prior.mean:.2f}→{posterior_mean:.2f} µL/h, "
            f"CV {prior.cv:.2f}→{posterior_cv:.2f}"
        ),
        calibration_history=prior.calibration_history + [
            {
                'date': calibration_date,
                'source': 'gravimetry',
                'plate_id': plate_id,
                'edge_loss_ul': float(edge_loss_ul),
                'center_loss_ul': float(center_loss_ul),
                'time_hours': float(time_hours),
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
        'edge_loss_ul': float(edge_loss_ul),
        'center_loss_ul': float(center_loss_ul),
        'time_hours': float(time_hours),
        'sigma_reduction': float(sigma_reduction),
        'provenance': (
            f"Prior updated: mean {prior.mean:.2f}→{posterior_mean:.2f} µL/h, "
            f"CV {prior.cv:.2f}→{posterior_cv:.2f} "
            f"(sigma reduced {sigma_reduction:.1%}) "
            f"based on gravimetry {plate_id}"
        ),
        'calibration_date': calibration_date,
        'plate_id': plate_id
    }

    return updated_prior, report
