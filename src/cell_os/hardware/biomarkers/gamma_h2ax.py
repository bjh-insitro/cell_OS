"""
γ-H2AX biomarker model.

γ-H2AX (phosphorylated histone H2A.X at Ser139) is a marker of DNA double-strand breaks.
It forms nuclear foci at sites of DNA damage and is used as a readout for:
- Genotoxic stress (DNA-damaging agents)
- Oxidative stress (ROS-induced DSBs)
- Replication stress

This model maps the latent dna_damage state to observable γ-H2AX signal.

Phase 0 Thalamus Use Case:
- Menadione (oxidative stress) → DNA damage → γ-H2AX phosphorylation
- Used as pathology exclusion gate (saturated damage regimes are excluded)
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from ..biological_virtual import VesselState


@dataclass
class GammaH2AXParams:
    """Parameters for γ-H2AX signal model."""

    # Baseline signal (vehicle control)
    baseline_intensity: float = 50.0  # AU (arbitrary units)
    baseline_cv: float = 0.15  # 15% CV in vehicle

    # Dose-response relationship (dna_damage → γ-H2AX)
    max_fold_induction: float = 15.0  # Max fold-increase at saturating damage
    hill_coefficient: float = 2.0  # Steepness of response curve
    ec50_damage: float = 0.3  # DNA damage level for 50% max response

    # Nuclear distribution (for per-nucleus analysis)
    nuclei_per_well: int = 500  # Typical nuclei count for analysis
    foci_count_per_nucleus_max: int = 30  # Max foci at saturating damage

    # Technical noise
    well_cv: float = 0.08  # Well-to-well variation
    plate_cv: float = 0.05  # Plate-to-plate variation


class GammaH2AXModel:
    """
    Model for γ-H2AX signal based on DNA damage state.

    Produces:
    - Mean nuclear intensity
    - Nuclear intensity distribution (for threshold analysis)
    - Foci count estimates
    - Pathology gate metrics
    """

    def __init__(self, params: GammaH2AXParams | None = None):
        """
        Initialize γ-H2AX model.

        Args:
            params: Model parameters (uses defaults if None)
        """
        self.params = params or GammaH2AXParams()

    def compute_signal(
        self, vessel: "VesselState", rng: np.random.Generator, **kwargs
    ) -> dict[str, Any]:
        """
        Compute γ-H2AX signal from vessel state.

        Args:
            vessel: Vessel state with dna_damage field
            rng: Random number generator for stochastic components
            **kwargs: Additional parameters (plate_id, well_position, etc.)

        Returns:
            Dict with:
                - mean_intensity: Mean nuclear γ-H2AX intensity
                - median_intensity: Median nuclear intensity
                - p95_intensity: 95th percentile intensity
                - pct_above_vehicle_p95: % nuclei above vehicle P95
                - foci_per_nucleus: Estimated foci count
                - nuclear_intensities: Array of per-nucleus intensities (for distribution)
                - pathology_flag: "PASS", "WARNING", or "EXCLUDED"
        """
        p = self.params

        # Get DNA damage level (0-1)
        dna_damage = getattr(vessel, "dna_damage", 0.0)
        dna_damage = float(np.clip(dna_damage, 0.0, 1.0))

        # Hill equation for dose-response
        # f(D) = D^n / (EC50^n + D^n)
        if dna_damage > 0:
            response_fraction = (dna_damage**p.hill_coefficient) / (
                p.ec50_damage**p.hill_coefficient + dna_damage**p.hill_coefficient
            )
        else:
            response_fraction = 0.0

        # Mean intensity = baseline * (1 + (max_fold - 1) * response)
        fold_induction = 1.0 + (p.max_fold_induction - 1.0) * response_fraction
        mean_intensity_true = p.baseline_intensity * fold_induction

        # Technical noise (plate and well effects)
        plate_id = kwargs.get("plate_id", "P1")

        # Deterministic plate effect (seeded by plate_id)
        plate_seed = hash(f"gamma_h2ax_plate_{plate_id}") & 0xFFFFFFFF
        plate_rng = np.random.default_rng(plate_seed)
        plate_factor = float(np.exp(plate_rng.normal(0, np.log1p(p.plate_cv**2) ** 0.5)))

        # Well effect (stochastic)
        well_factor = float(np.exp(rng.normal(0, np.log1p(p.well_cv**2) ** 0.5)))

        mean_intensity = mean_intensity_true * plate_factor * well_factor

        # Generate nuclear intensity distribution
        # Lognormal distribution with CV increasing with damage (heterogeneity)
        cv_nuclear = p.baseline_cv * (1.0 + 2.0 * dna_damage)  # CV increases with damage
        sigma_nuclear = np.sqrt(np.log1p(cv_nuclear**2))
        mu_nuclear = np.log(mean_intensity) - 0.5 * sigma_nuclear**2

        nuclear_intensities = rng.lognormal(mu_nuclear, sigma_nuclear, p.nuclei_per_well)

        # Compute distribution statistics
        median_intensity = float(np.median(nuclear_intensities))
        p95_intensity = float(np.percentile(nuclear_intensities, 95))
        mean_intensity_actual = float(np.mean(nuclear_intensities))

        # Estimate foci count (correlates with damage)
        foci_per_nucleus = p.foci_count_per_nucleus_max * response_fraction
        # Add some noise
        foci_per_nucleus = max(0.0, foci_per_nucleus + rng.normal(0, 1.0))

        # Compute pathology gate metrics (for vehicle comparison)
        # These will be compared against vehicle controls at analysis time
        result = {
            "mean_intensity": mean_intensity_actual,
            "median_intensity": median_intensity,
            "p95_intensity": p95_intensity,
            "fold_induction": fold_induction,
            "dna_damage_level": dna_damage,
            "response_fraction": response_fraction,
            "foci_per_nucleus": foci_per_nucleus,
            "nuclear_intensities": nuclear_intensities,
            "nuclei_count": len(nuclear_intensities),
            "cv_nuclear": float(np.std(nuclear_intensities) / np.mean(nuclear_intensities)),
        }

        return result

    @staticmethod
    def check_pathology_gate(
        treated_data: dict[str, Any], vehicle_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Check pathology exclusion gate for γ-H2AX.

        Phase 0 Thalamus criteria:
        - EXCLUDED if ≥60% of nuclei exceed vehicle P95, OR
        - EXCLUDED if ≥40% exceed P95 AND median is ≥3× vehicle

        Args:
            treated_data: γ-H2AX data from treated condition
            vehicle_data: γ-H2AX data from vehicle control

        Returns:
            Dict with:
                - status: "PASS", "WARNING", or "EXCLUDED"
                - reason: Explanation of status
                - pct_exceeding_p95: % nuclei above vehicle P95
                - median_ratio: Treated median / vehicle median
                - criteria_met: Which exclusion criteria were triggered
        """
        # Get vehicle P95 threshold
        vehicle_p95 = vehicle_data["p95_intensity"]
        vehicle_median = vehicle_data["median_intensity"]

        # Get treated nuclear intensities
        treated_intensities = treated_data["nuclear_intensities"]
        treated_median = treated_data["median_intensity"]

        # Calculate % exceeding vehicle P95
        pct_exceeding_p95 = float(np.mean(treated_intensities > vehicle_p95))

        # Calculate median ratio
        median_ratio = treated_median / max(vehicle_median, 1e-6)

        # Check exclusion criteria
        criteria_met = []

        # Criterion 1: ≥60% exceed P95
        if pct_exceeding_p95 >= 0.60:
            criteria_met.append("≥60% nuclei exceed vehicle P95")

        # Criterion 2: ≥40% exceed P95 AND median ≥3× vehicle
        if pct_exceeding_p95 >= 0.40 and median_ratio >= 3.0:
            criteria_met.append("≥40% exceed P95 AND median ≥3× vehicle")

        # Determine status
        if criteria_met:
            status = "EXCLUDED"
            reason = f"Saturated damage regime: {'; '.join(criteria_met)}"
        elif pct_exceeding_p95 >= 0.30 or median_ratio >= 2.0:
            status = "WARNING"
            reason = "Approaching pathology threshold"
        else:
            status = "PASS"
            reason = "Within acceptable damage range"

        return {
            "status": status,
            "reason": reason,
            "pct_exceeding_p95": pct_exceeding_p95,
            "median_ratio": median_ratio,
            "vehicle_p95_threshold": vehicle_p95,
            "vehicle_median": vehicle_median,
            "treated_median": treated_median,
            "criteria_met": criteria_met,
        }
