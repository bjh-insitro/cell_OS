"""
Aspiration and dispense-induced cell detachment from fixed instrument positions.

Key physics:
1. EL406 aspiration manifold is ALWAYS at same position (9 o'clock = 270°)
2. Aspiration creates localized shear stress → mechanical detachment
3. This is PHYSICAL REMOVAL, not death (different accounting)
"""

import numpy as np
from typing import Dict, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
from ._impl import stable_u32


# Artifact contract specification
ARTIFACT_SPEC = {
    'domain': 'spatial',
    'state_mutations': ['edge_damage', 'debris_load'],
    'affected_observables': ['segmentation_yield', 'noise_mult'],
    'epistemic_prior': {
        'parameter': 'gamma',
        'distribution': 'Lognormal(mean=1.0, CV=0.35)',
        'calibration_method': 'microscopy'
    },
    'ledger_terms': {
        'modeled': 'VAR_INSTRUMENT_ASPIRATION_SPATIAL',
        'ridge': 'VAR_CALIBRATION_ASPIRATION_GAMMA',
    },
    'correlation_groups': {
        'modeled': 'aspiration_position',
        'ridge': 'aspiration_ridge',
    },
    'forbidden_dependencies': ['dispense_sequence', 'serpentine_index', 'time_since_start'],
    'version': '1.0',
    'implemented': '2025-12-23',
    'tests': ['test_aspiration_effects.py']
}


@dataclass
class GammaPrior:
    """
    Gamma (gradient shape) prior distribution with provenance tracking.

    Distribution: Lognormal(mu_log, sigma_log) clipped to [clip_min, clip_max]
    """
    mu_log: float = field(default_factory=lambda: np.log(1.0) - 0.5 * np.log(1.0 + 0.35**2))
    sigma_log: float = field(default_factory=lambda: np.sqrt(np.log(1.0 + 0.35**2)))
    clip_min: float = 0.3
    clip_max: float = 3.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    evidence_source: str = "default"
    evidence_summary: str = "Default prior: Lognormal(mean=1.0, CV=0.35)"
    calibration_history: list = field(default_factory=list)

    @property
    def mean(self) -> float:
        """Expected value of lognormal (before clipping)."""
        return float(np.exp(self.mu_log + 0.5 * self.sigma_log ** 2))

    @property
    def cv(self) -> float:
        """Coefficient of variation (before clipping)."""
        return float(np.sqrt(np.exp(self.sigma_log ** 2) - 1.0))

    def sample(self, seed: int, instrument_id: str = "biotek_el406_cell_dispenser") -> float:
        """Sample gamma deterministically."""
        gamma_seed = stable_u32(f"gamma_prior_{instrument_id}_{seed}")
        gamma_rng = np.random.default_rng(gamma_seed)
        gamma_sample = gamma_rng.lognormal(self.mu_log, self.sigma_log)
        return float(np.clip(gamma_sample, self.clip_min, self.clip_max))


def sample_gamma_from_prior(
    seed: int,
    instrument_id: str = "biotek_el406_cell_dispenser",
    gamma_mean: float = None,
    gamma_cv: float = None,
    prior: Optional[GammaPrior] = None
) -> float:
    """Sample gamma from prior distribution."""
    if prior is not None:
        return prior.sample(seed=seed, instrument_id=instrument_id)

    # Legacy path
    if gamma_mean is None:
        gamma_mean = 1.0
    if gamma_cv is None:
        gamma_cv = 0.35

    sigma_squared = np.log(1.0 + gamma_cv ** 2)
    sigma_log = np.sqrt(sigma_squared)
    mu_log = np.log(gamma_mean) - sigma_squared / 2.0

    temp_prior = GammaPrior(mu_log=mu_log, sigma_log=sigma_log)
    return temp_prior.sample(seed=seed, instrument_id=instrument_id)


def calculate_aspiration_detachment(
    well_position: str,
    cell_count: float,
    confluence: float,
    aspirated_fraction: float,
    aspiration_angle_deg: float = 270,
    aspiration_radius_fraction: float = 0.75,
    base_detach_rate: float = 0.015,
    post_fix_brittleness: float = 0.3,
    seed: int = 42,
    plate_id: str = "P1",
    mode: str = "normal",
    exposure_gamma: Optional[float] = None,
    instrument_id: str = "biotek_el406_cell_dispenser"
) -> Dict[str, float]:
    """Calculate cell detachment from aspiration at fixed manifold position."""
    # Sample gamma if not provided
    if exposure_gamma is None:
        exposure_gamma = sample_gamma_from_prior(seed=seed, instrument_id=instrument_id)
        gamma_was_sampled = True
    else:
        gamma_was_sampled = False

    if cell_count <= 0:
        result = {
            'detached_clean': 0.0,
            'detached_debris': 0.0,
            'detached_total': 0.0,
            'edge_damage_score': 0.0,
            'edge_tear_score': 0.0,
            'bulk_shear_score': 0.0
        }
        if gamma_was_sampled:
            result['sampled_gamma'] = exposure_gamma
        return result

    # Confluence scaling
    confluence_factor = (1.0 - confluence) ** 1.0
    confluence_factor = np.clip(confluence_factor, 0.3, 1.0)

    # Volume scaling
    volume_factor = np.sqrt(np.clip(aspirated_fraction, 0.0, 1.0))

    # Localized exposure (gamma-sensitive)
    tear_exposure = _calculate_manifold_exposure(
        well_position, aspiration_angle_deg, seed, plate_id, exposure_gamma
    )

    # Broad exposure (weakly gamma-sensitive)
    import re
    match = re.match(r'^([A-P])(\d{1,2})$', well_position)
    if match:
        col = int(match.group(2))
        normalized_col = (col - 1) / 23.0
        if 225 <= aspiration_angle_deg <= 315:  # Left side
            shear_exposure = 1.0 + (1.0 - normalized_col) * 0.3
        elif 45 <= aspiration_angle_deg <= 135:  # Right side
            shear_exposure = 1.0 + normalized_col * 0.3
        else:
            shear_exposure = 1.0
    else:
        shear_exposure = 1.0

    # Mode-dependent mixture
    mix_tear = 0.8 if mode == "normal" else 0.4
    mix_shear = 0.2 if mode == "normal" else 0.6

    # Compute latents
    tear_detach = base_detach_rate * confluence_factor * volume_factor * tear_exposure * mix_tear
    shear_detach = base_detach_rate * 0.5 * confluence_factor * volume_factor * shear_exposure * mix_shear

    # Total detachment
    detach_fraction = tear_detach + shear_detach
    detach_fraction = float(np.clip(detach_fraction, 0.0, 0.15))

    detached_total = cell_count * detach_fraction

    # Split into clean vs debris
    debris_fraction = 0.2 + 0.6 * post_fix_brittleness
    debris_fraction = float(np.clip(debris_fraction, 0.0, 0.9))

    detached_debris = detached_total * debris_fraction
    detached_clean = detached_total * (1.0 - debris_fraction)

    # Two latent damage scores
    edge_tear_score = float(np.clip(tear_detach * 2.0, 0.0, 1.0))
    bulk_shear_score = float(np.clip(shear_detach * 2.0, 0.0, 1.0))
    edge_damage_score = float(np.clip((edge_tear_score + bulk_shear_score) / 2.0, 0.0, 1.0))

    result = {
        'detached_clean': float(detached_clean),
        'detached_debris': float(detached_debris),
        'detached_total': float(detached_total),
        'edge_damage_score': edge_damage_score,
        'edge_tear_score': edge_tear_score,
        'bulk_shear_score': bulk_shear_score
    }

    if gamma_was_sampled:
        result['sampled_gamma'] = exposure_gamma

    return result


def _calculate_manifold_exposure(
    well_position: str,
    aspiration_angle_deg: float,
    seed: int,
    plate_id: str,
    exposure_gamma: float = 1.0
) -> float:
    """Calculate manifold exposure score with power-law gradient."""
    import re
    match = re.match(r'^([A-P])(\d{1,2})$', well_position)
    if not match:
        return 1.0

    col_number = int(match.group(2))
    max_col = 24
    normalized_col = (col_number - 1) / (max_col - 1)

    if 225 <= aspiration_angle_deg <= 315:  # Left side
        distance = normalized_col
        exposure_factor = (1.0 - distance) ** exposure_gamma
        exposure_base = 1.0 + exposure_factor * 0.5
    elif 45 <= aspiration_angle_deg <= 135:  # Right side
        distance = 1.0 - normalized_col
        exposure_factor = (1.0 - distance) ** exposure_gamma
        exposure_base = 1.0 + exposure_factor * 0.5
    else:
        exposure_base = 1.0

    # Add noise
    exposure_seed = stable_u32(f"exposure_{plate_id}_{well_position}_{seed}")
    exposure_rng = np.random.default_rng(exposure_seed)
    well_noise = exposure_rng.normal(0.0, 0.1)

    exposure_score = exposure_base + well_noise
    return float(np.clip(exposure_score, 0.5, 1.5))


def get_edge_damage_contribution_to_cp_quality(
    edge_damage_score: float = None,
    debris_load: float = 0.0,
    edge_tear_score: float = None,
    bulk_shear_score: float = None
) -> Dict[str, float]:
    """Convert edge damage into CP measurement degradation."""
    # Handle legacy calls
    if edge_tear_score is None and bulk_shear_score is None:
        if edge_damage_score is None:
            edge_damage_score = 0.0
        edge_tear_score = edge_damage_score * 0.6
        bulk_shear_score = edge_damage_score * 0.4

    # Segmentation yield penalty (primarily from edge_tear)
    seg_penalty = edge_tear_score * 0.20 + bulk_shear_score * 0.05
    seg_penalty = float(np.clip(seg_penalty, 0.0, 0.25))

    # Noise multiplier (primarily from bulk_shear)
    noise_mult = 1.0 + (bulk_shear_score * 0.6 + edge_tear_score * 0.2)
    noise_mult = float(np.clip(noise_mult, 1.0, 2.0))

    # Debris amplification
    debris_amp = 1.0 + (edge_tear_score * 0.25 + bulk_shear_score * 0.15)
    debris_amp = float(np.clip(debris_amp, 1.0, 1.5))

    return {
        'segmentation_yield_penalty': seg_penalty,
        'noise_multiplier': noise_mult,
        'debris_amplification': debris_amp
    }


def compute_gamma_ridge_uncertainty(
    edge_tear_score: float,
    bulk_shear_score: float,
    debris_load: float = 0.0,
    gamma_prior_cv: float = 0.35
) -> Dict[str, float]:
    """Compute uncertainty in CP metrics from gamma prior (two-point bracket)."""
    if gamma_prior_cv <= 0:
        return {
            'segmentation_yield_cv': 0.0,
            'noise_multiplier_cv': 0.0,
            'debris_amplification_cv': 0.0
        }

    # Two-point bracket: 5th and 95th percentiles
    scale = gamma_prior_cv / 0.35
    gamma_low = 1.0 / (1.0 + 1.73 * scale)
    gamma_high = 1.0 * (1.0 + 1.73 * scale)

    # Exposure sensitivity
    exposure_mid_low = 1.0 + (0.5 ** gamma_low) * 0.5
    exposure_mid_high = 1.0 + (0.5 ** gamma_high) * 0.5
    exposure_mid_nominal = 1.0 + (0.5 ** 1.0) * 0.5

    tear_scale_low = exposure_mid_low / exposure_mid_nominal
    tear_scale_high = exposure_mid_high / exposure_mid_nominal

    # Evaluate at both quantiles
    def eval_contribution(tear, shear):
        seg_penalty = tear * 0.20 + shear * 0.05
        seg_penalty = float(np.clip(seg_penalty, 0.0, 0.25))

        noise_mult = 1.0 + (shear * 0.6 + tear * 0.2)
        noise_mult = float(np.clip(noise_mult, 1.0, 2.0))

        debris_amp = 1.0 + (tear * 0.25 + shear * 0.15)
        debris_amp = float(np.clip(debris_amp, 1.0, 1.5))

        return seg_penalty, noise_mult, debris_amp

    tear_low = edge_tear_score * tear_scale_low
    tear_high = edge_tear_score * tear_scale_high
    shear_low = bulk_shear_score * 0.95
    shear_high = bulk_shear_score * 1.05

    seg_penalty_low, noise_mult_low, debris_amp_low = eval_contribution(tear_low, shear_low)
    seg_penalty_high, noise_mult_high, debris_amp_high = eval_contribution(tear_high, shear_high)

    # Half-range as uncertainty
    seg_penalty_half_range = abs(seg_penalty_high - seg_penalty_low) / 2.0
    noise_mult_half_range = abs(noise_mult_high - noise_mult_low) / 2.0
    debris_amp_half_range = abs(debris_amp_high - debris_amp_low) / 2.0

    # Convert to CV
    seg_penalty_nominal = (seg_penalty_low + seg_penalty_high) / 2.0
    noise_mult_nominal = (noise_mult_low + noise_mult_high) / 2.0
    debris_amp_nominal = (debris_amp_low + debris_amp_high) / 2.0

    seg_yield_cv = seg_penalty_half_range / (seg_penalty_nominal + 1e-9)
    noise_mult_cv = noise_mult_half_range / (noise_mult_nominal + 1e-9)
    debris_amp_cv = debris_amp_half_range / (debris_amp_nominal + 1e-9)

    return {
        'segmentation_yield_cv': float(seg_yield_cv),
        'noise_multiplier_cv': float(noise_mult_cv),
        'debris_amplification_cv': float(debris_amp_cv)
    }
