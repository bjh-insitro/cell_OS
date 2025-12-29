"""
Intrinsic biology stochasticity helper.

Enforces:
- Draw-count invariance (via isolated RNG substreams)
- Mean preservation (lognormal correction with proper CV→sigma conversion)
- Provenance key management (lineage-based, not spatial order-dependent)

Design:
- Plate and vessel random effects are sampled from deterministic RNG substreams
- Substreams are seeded by stable hashes of plate_id and lineage_id
- This makes REs independent of vessel/plate instantiation order
- Main rng_growth stream is never touched (perfect isolation)
"""

import numpy as np
import re
from typing import Dict, Optional
from ._impl import stable_u32


def sigma_from_cv(cv: float) -> float:
    """
    Convert coefficient of variation (CV) to log-space sigma for lognormal.

    For m ~ lognormal with E[m] = 1:
        CV(m) = sqrt(exp(sigma²) - 1)
        Therefore: sigma = sqrt(log(1 + CV²))

    This ensures that when we specify a CV in multiplier space,
    the resulting lognormal distribution has exactly that CV.

    Args:
        cv: Coefficient of variation in multiplier space

    Returns:
        Standard deviation in log-space
    """
    cv = max(float(cv), 0.0)
    return float(np.sqrt(np.log1p(cv * cv)))


def extract_plate_id_defensive(vessel_id: str) -> str:
    """
    Extract plate identifier from vessel_id with defensive fallback.

    Assumes format: "PlateN_WellPos" (e.g., "Plate1_A01").
    If well position pattern is found, use everything before it as plate_id.
    Otherwise, use full vessel_id (no sharing across plates).

    This prevents accidentally grouping unrelated vessels into the same
    plate_id due to unexpected vessel_id formats.

    Args:
        vessel_id: Vessel identifier

    Returns:
        Plate identifier (for shared plate-level random effects)

    TODO: Use PlateInventory.plate_id if available.
    """
    # Match well coordinates: A-P (96/384 well plates), followed by 01-24
    # Examples: A01, B12, P24
    well_pattern = r'([A-P]\d{2})$'
    match = re.search(well_pattern, vessel_id)

    if match:
        # Well position found, use prefix as plate_id
        well_start = match.start()
        if well_start > 0 and vessel_id[well_start - 1] == '_':
            # Has separator before well (e.g., "Plate1_A01")
            return vessel_id[:well_start - 1]
        else:
            # No separator (e.g., "PlateA01"), use everything before well
            return vessel_id[:well_start]

    # No well pattern found, use full vessel_id (no plate sharing)
    return vessel_id


class StochasticBiologyHelper:
    """
    Manages intrinsic biological random effects with hierarchical structure.

    Hierarchical model:
        plate latent ~ N(0, 1)
        vessel latent ~ N(0, 1)
        combined effect = exp(σ_plate * z_plate + σ_vessel * z_vessel - 0.5 * σ_total²)

    Where:
        σ_total = sigma_from_cv(CV)  # Proper lognormal conversion
        σ_plate² = plate_fraction * σ_total²
        σ_vessel² = (1 - plate_fraction) * σ_total²

    This ensures:
        - E[multiplier] = 1.0 (mean preserved in rate space)
        - CV[multiplier] = CV (as specified by user)
        - Plate and vessel effects are independent
        - REs are deterministic from provenance keys (plate_id, lineage_id)
        - No dependency on instantiation order

    TODO: Upgrade stable_u32 to stable_u64 for collision resistance at scale.
    """

    def __init__(self, config: Dict, run_seed: int):
        """
        Initialize stochastic biology helper.

        Args:
            config: Configuration dict with keys:
                - enabled: bool (default False)
                - growth_cv: float (CV for growth rate)
                - stress_sensitivity_cv: float (CV for stress accumulation)
                - hazard_scale_cv: float (CV for death hazard magnitude)
                - plate_level_fraction: float (fraction of variance at plate level)
            run_seed: Base run seed for substream generation
        """
        self.config = config
        self.run_seed = run_seed
        self.enabled = config.get('enabled', False)

        # CV parameters
        self.growth_cv = config.get('growth_cv', 0.0)
        self.stress_cv = config.get('stress_sensitivity_cv', 0.0)
        self.hazard_cv = config.get('hazard_scale_cv', 0.0)

        # Variance split
        self.plate_fraction = config.get('plate_level_fraction', 0.3)

        # Key mapping for consistent naming
        self.KEYMAP = {
            'growth': 'growth_rate_mult',
            'stress': 'stress_sensitivity_mult',
            'hazard': 'hazard_scale_mult',
        }

    def _make_substream_seed(self, offset: int, key: str) -> int:
        """
        Create deterministic substream seed from run seed and provenance key.

        Args:
            offset: Offset to add to run_seed (1 for plate, 2 for lineage)
            key: Provenance key (plate_id or lineage_id)

        Returns:
            64-bit seed for np.random.default_rng
        """
        # Mask run_seed to prevent overflow, XOR with stable hash of key
        seed64 = np.uint64(((self.run_seed + offset) & 0xFFFFFFFFFFFFFFFF) ^ stable_u32(key))
        return seed64

    def sample_random_effects(
        self,
        lineage_id: str,
        plate_id: str
    ) -> Dict[str, float]:
        """
        Sample hierarchical random effects for a vessel.

        Uses deterministic RNG substreams for both plate and lineage,
        making REs independent of instantiation order.

        Args:
            lineage_id: Stable vessel lineage identifier
            plate_id: Plate identifier for shared plate-level effects

        Returns:
            Dict with keys: growth_rate_mult, stress_sensitivity_mult, hazard_scale_mult
        """
        # Create per-plate RNG substream (deterministic from plate_id)
        rng_plate = np.random.default_rng(self._make_substream_seed(1, plate_id))
        plate_latents = {
            'growth': float(rng_plate.standard_normal()),
            'stress': float(rng_plate.standard_normal()),
            'hazard': float(rng_plate.standard_normal()),
        }

        # Create per-lineage RNG substream (deterministic from lineage_id)
        rng_lineage = np.random.default_rng(self._make_substream_seed(2, lineage_id))
        vessel_latents = {
            'growth': float(rng_lineage.standard_normal()),
            'stress': float(rng_lineage.standard_normal()),
            'hazard': float(rng_lineage.standard_normal()),
        }

        # Combine hierarchically with proper CV→sigma conversion
        re = {}
        for short_key, full_key in self.KEYMAP.items():
            # Get CV parameter
            if short_key == 'growth':
                total_cv = self.growth_cv
            elif short_key == 'stress':
                total_cv = self.stress_cv
            else:  # hazard
                total_cv = self.hazard_cv

            if self.enabled and total_cv > 0:
                # Convert CV to log-space sigma (proper lognormal parameterization)
                sigma_total = sigma_from_cv(total_cv)
                sigma_plate = sigma_total * np.sqrt(self.plate_fraction)
                sigma_vessel = sigma_total * np.sqrt(1.0 - self.plate_fraction)

                # Log-space sum with mean correction
                z_total = plate_latents[short_key] * sigma_plate + vessel_latents[short_key] * sigma_vessel
                correction = 0.5 * (sigma_plate**2 + sigma_vessel**2)
                mult = float(np.exp(z_total - correction))
            else:
                # Disabled or cv=0: return 1.0
                # No draws needed - substreams are isolated, nothing else depends on them
                mult = 1.0

            re[full_key] = mult

        return re
