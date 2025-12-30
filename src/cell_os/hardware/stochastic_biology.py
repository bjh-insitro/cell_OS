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

        # Phase 3.0: IC50 heterogeneity (bugfix - was always 1.0)
        self.ic50_cv = config.get('ic50_cv', 0.20)  # 20% CV for induction sensitivity

        # Phase 3.1: Death threshold heterogeneity (correlated with IC50)
        self.death_threshold_cv = config.get('death_threshold_cv', 0.25)  # 25% CV for apoptotic priming
        self.sensitivity_correlation = config.get('sensitivity_correlation', 0.5)  # ρ = 0.5 (moderate)

        # Variance split
        self.plate_fraction = config.get('plate_level_fraction', 0.3)

        # Phase 2A.1: ER commitment event parameters (default OFF)
        self.er_commitment_enabled = config.get('er_commitment_enabled', False)
        self.er_commitment_threshold = config.get('er_commitment_threshold', 0.60)
        self.er_commitment_baseline_hazard_per_h = config.get('er_commitment_baseline_hazard_per_h', 0.01)
        self.er_commitment_sharpness_p = config.get('er_commitment_sharpness_p', 2.0)
        self.er_commitment_hazard_cap_per_h = config.get('er_commitment_hazard_cap_per_h', 0.10)
        self.er_committed_death_hazard_per_h = config.get('er_committed_death_hazard_per_h', 0.50)
        self.er_commitment_track_snapshot = config.get('er_commitment_track_snapshot', True)

        # Phase 2A.2: Mito commitment event parameters (default OFF, same defaults as ER)
        self.mito_commitment_enabled = config.get('mito_commitment_enabled', False)
        self.mito_commitment_threshold = config.get('mito_commitment_threshold', 0.60)
        self.mito_commitment_baseline_hazard_per_h = config.get('mito_commitment_baseline_hazard_per_h', 0.01)
        self.mito_commitment_sharpness_p = config.get('mito_commitment_sharpness_p', 2.0)
        self.mito_commitment_hazard_cap_per_h = config.get('mito_commitment_hazard_cap_per_h', 0.10)
        self.mito_committed_death_hazard_per_h = config.get('mito_committed_death_hazard_per_h', 0.50)
        self.mito_commitment_track_snapshot = config.get('mito_commitment_track_snapshot', True)

        # Key mapping for consistent naming
        self.KEYMAP = {
            'growth': 'growth_rate_mult',
            'stress': 'stress_sensitivity_mult',
            'hazard': 'hazard_scale_mult',
            'ic50': 'ic50_shift_mult',  # Phase 3.0: IC50 heterogeneity (induction sensitivity)
            'death_theta': 'death_threshold_shift_mult',  # Phase 3.1: Death threshold heterogeneity
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

        Phase 3.1: IC50 and death threshold are correlated (ρ ≈ 0.5).
        - Shared latent component: vessels sensitive to induction are also fragile
        - Independent noise: correlation is moderate, not synonymous
        - Applied at both plate and vessel levels

        Args:
            lineage_id: Stable vessel lineage identifier
            plate_id: Plate identifier for shared plate-level effects

        Returns:
            Dict with keys: growth_rate_mult, stress_sensitivity_mult, hazard_scale_mult,
                           ic50_shift_mult, death_threshold_shift_mult
        """
        # Create per-plate RNG substream (deterministic from plate_id)
        rng_plate = np.random.default_rng(self._make_substream_seed(1, plate_id))

        # Phase 3.1: Sample shared latent for IC50/death_theta correlation
        z_plate_shared = float(rng_plate.standard_normal())  # Shared fragility component
        z_plate_theta_indep = float(rng_plate.standard_normal())  # Death threshold-specific noise

        # Construct correlated latents with unit marginal variance:
        #   z_ic50 = z_shared (variance = 1)
        #   z_theta = ρ*z_shared + sqrt(1-ρ²)*z_indep (variance = ρ² + (1-ρ²) = 1)
        #   Corr(z_ic50, z_theta) = ρ
        rho = self.sensitivity_correlation
        sqrt_1_minus_rho_sq = np.sqrt(1.0 - rho * rho)

        plate_latents = {
            'growth': float(rng_plate.standard_normal()),
            'stress': float(rng_plate.standard_normal()),
            'hazard': float(rng_plate.standard_normal()),
            'ic50': z_plate_shared,  # Phase 3.0: IC50 heterogeneity
            'death_theta': rho * z_plate_shared + sqrt_1_minus_rho_sq * z_plate_theta_indep,  # Phase 3.1
        }

        # Create per-lineage RNG substream (deterministic from lineage_id)
        rng_lineage = np.random.default_rng(self._make_substream_seed(2, lineage_id))

        # Phase 3.1: Sample shared latent at vessel level too
        z_vessel_shared = float(rng_lineage.standard_normal())
        z_vessel_theta_indep = float(rng_lineage.standard_normal())

        vessel_latents = {
            'growth': float(rng_lineage.standard_normal()),
            'stress': float(rng_lineage.standard_normal()),
            'hazard': float(rng_lineage.standard_normal()),
            'ic50': z_vessel_shared,  # Phase 3.0: IC50 heterogeneity
            'death_theta': rho * z_vessel_shared + sqrt_1_minus_rho_sq * z_vessel_theta_indep,  # Phase 3.1
        }

        # Combine hierarchically with proper CV→sigma conversion
        re = {}
        for short_key, full_key in self.KEYMAP.items():
            # Get CV parameter
            if short_key == 'growth':
                total_cv = self.growth_cv
            elif short_key == 'stress':
                total_cv = self.stress_cv
            elif short_key == 'hazard':
                total_cv = self.hazard_cv
            elif short_key == 'ic50':
                total_cv = self.ic50_cv
            elif short_key == 'death_theta':
                total_cv = self.death_threshold_cv
            else:
                total_cv = 0.0  # Unknown key, disable

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

    def make_event_rng(self, lineage_id: str, event_name: str, mechanism: str) -> np.random.Generator:
        """
        Create deterministic RNG substream for discrete stochastic events.

        Uses lineage-based keying to ensure events are deterministic from
        provenance keys, independent of vessel instantiation order.

        Args:
            lineage_id: Stable vessel lineage identifier
            event_name: Event type (e.g., "commitment")
            mechanism: Mechanism name (e.g., "er_stress")

        Returns:
            np.random.Generator seeded deterministically from lineage + event + mechanism
        """
        # Combine lineage_id, event_name, and mechanism into unique key
        key = f"{lineage_id}|{event_name}|{mechanism}"

        # Use offset 100 to avoid collision with plate (offset 1) and vessel (offset 2) RE substreams
        seed = self._make_substream_seed(100, key)
        return np.random.default_rng(seed)

    @staticmethod
    def compute_commitment_hazard(
        S: float,
        S_commit: float,
        lambda0: float,
        p: float,
        cap: float
    ) -> float:
        """
        Compute commitment hazard rate as function of stress level.

        Model: λ_commit = min(cap, λ0 * ((S - S_commit) / (1 - S_commit))^p)

        This gives:
        - No commitment below threshold (S <= S_commit)
        - Monotonically increasing hazard as stress rises above threshold
        - Bounded by cap to prevent runaway rates

        Args:
            S: Current stress level in [0, 1]
            S_commit: Commitment threshold in [0, 1)
            lambda0: Baseline hazard rate at threshold (per hour)
            p: Sharpness parameter (>0, typically 1-3)
            cap: Maximum hazard rate (per hour)

        Returns:
            Commitment hazard rate (per hour), in [0, cap]
        """
        if S <= S_commit:
            return 0.0

        # Normalized distance above threshold, in (0, 1]
        u = (S - S_commit) / (1.0 - S_commit)

        # Power law with cap
        lambda_commit = lambda0 * (u ** p)
        return float(min(cap, lambda_commit))

    @staticmethod
    def sample_poisson_event(lambda_rate: float, dt_h: float, rng: np.random.Generator) -> bool:
        """
        Sample whether a Poisson event occurs in time interval dt.

        For Poisson process with rate λ, probability of event in interval dt is:
            P(event) = 1 - exp(-λ * dt)

        Args:
            lambda_rate: Event rate (per hour)
            dt_h: Time interval (hours)
            rng: Random number generator

        Returns:
            True if event occurs, False otherwise
        """
        if lambda_rate <= 0 or dt_h <= 0:
            return False

        # Probability of event in this timestep
        p_event = 1.0 - np.exp(-lambda_rate * dt_h)

        # Sample uniform and compare
        u = rng.random()
        return u < p_event

    def maybe_trigger_commitment(
        self,
        vessel,
        mechanism: str,
        stress_S: float,
        sim_time_h: float,
        dt_h: float
    ) -> None:
        """
        Phase 2A.3: Shared commitment event sampler (mechanism-agnostic).

        Samples stochastic commitment event and mutates vessel fields if triggered.
        Does nothing if commitment already occurred or mechanism not enabled.

        Args:
            vessel: VesselState to potentially mutate
            mechanism: Mechanism name ("er_stress" or "mito")
            stress_S: Current stress level in [0, 1]
            sim_time_h: Current simulated time (hours)
            dt_h: Time interval (hours)

        Mutates vessel fields if commitment occurs:
            - death_committed = True
            - death_committed_at_h = sim_time_h + dt_h (end of step)
            - death_commitment_mechanism = mechanism
            - death_commitment_stress_snapshot (if tracking enabled)

        Returns:
            None (mutates vessel state directly)
        """
        # Skip if already committed or lineage_id missing
        if vessel.death_committed or vessel.lineage_id is None:
            return

        # Get mechanism-specific config (ER or mito)
        if mechanism == "er_stress":
            enabled = self.er_commitment_enabled
            threshold = self.er_commitment_threshold
            baseline_hazard = self.er_commitment_baseline_hazard_per_h
            sharpness = self.er_commitment_sharpness_p
            cap = self.er_commitment_hazard_cap_per_h
            track_snapshot = self.er_commitment_track_snapshot
        elif mechanism == "mito":
            enabled = self.mito_commitment_enabled
            threshold = self.mito_commitment_threshold
            baseline_hazard = self.mito_commitment_baseline_hazard_per_h
            sharpness = self.mito_commitment_sharpness_p
            cap = self.mito_commitment_hazard_cap_per_h
            track_snapshot = self.mito_commitment_track_snapshot
        else:
            raise ValueError(f"Unknown commitment mechanism: {mechanism}")

        # Skip if not enabled for this mechanism
        if not enabled:
            return

        # Compute commitment hazard
        lambda_commit = self.compute_commitment_hazard(
            S=stress_S,
            S_commit=threshold,
            lambda0=baseline_hazard,
            p=sharpness,
            cap=cap
        )

        # Sample event
        if lambda_commit > 0:
            rng_event = self.make_event_rng(
                lineage_id=vessel.lineage_id,
                event_name="commitment",
                mechanism=mechanism
            )

            event_occurred = self.sample_poisson_event(
                lambda_rate=lambda_commit,
                dt_h=dt_h,
                rng=rng_event
            )

            if event_occurred:
                # Commit is irreversible - set fields exactly once
                vessel.death_committed = True
                vessel.death_committed_at_h = float(sim_time_h + dt_h)
                vessel.death_commitment_mechanism = mechanism

                # Optionally record stress snapshot
                if track_snapshot:
                    stress_field = "er_stress" if mechanism == "er_stress" else "mito_dysfunction"
                    vessel.death_commitment_stress_snapshot = {
                        stress_field: float(stress_S)
                    }

    @staticmethod
    def add_committed_hazard(
        vessel,
        mechanism: str,
        base_hazard_per_h: float,
        committed_hazard_per_h: float
    ) -> float:
        """
        Phase 2A.3: Shared committed hazard augmentation (mechanism-agnostic).

        Returns total hazard with committed hazard added if this mechanism committed.
        Otherwise returns base hazard unchanged.

        Args:
            vessel: VesselState to check
            mechanism: Mechanism name ("er_stress" or "mito")
            base_hazard_per_h: Base hazard from smooth accumulation
            committed_hazard_per_h: Additional hazard if committed

        Returns:
            Total hazard (base + committed if this mechanism committed, else base)
        """
        if vessel.death_committed and vessel.death_commitment_mechanism == mechanism:
            return base_hazard_per_h + committed_hazard_per_h
        return base_hazard_per_h
