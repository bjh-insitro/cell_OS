"""
Calibration Profile - Read-only accessor for calibration reports.

Provides safe, deterministic access to calibration data without side effects.
No config mutation, no auto-learning, no silent changes.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SUPPORTED_SCHEMA_VERSIONS = ["bead_plate_calibration_report_v1"]


class CalibrationProfile:
    """
    Read-only calibration profile loaded from calibration_report.json.

    Provides:
      - Vignette correction multipliers per well
      - Saturation-safe max values per channel
      - Quantization resolution per channel
      - Floor observability status

    All methods are pure functions (no state mutation).
    """

    def __init__(self, report_path: str | Path):
        """
        Load and validate calibration report.

        Args:
            report_path: Path to calibration_report.json

        Raises:
            ValueError: If schema version unsupported or report malformed
        """
        report_path = Path(report_path)
        if not report_path.exists():
            raise FileNotFoundError(f"Calibration report not found: {report_path}")

        with open(report_path) as f:
            self.report = json.load(f)

        # Validate schema version
        schema = self.report.get("schema_version")
        if schema not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"Unsupported calibration schema: {schema}. "
                f"Supported: {SUPPORTED_SCHEMA_VERSIONS}"
            )

        self.schema_version = schema
        self.channels = self.report.get("channels", ["er", "mito", "nucleus", "actin", "rna"])

        # Extract key calibration data
        self._vignette = self.report.get("vignette", {})
        self._saturation = self.report.get("saturation", {})
        self._quantization = self.report.get("quantization", {})
        self._floor = self.report.get("floor", {})
        self._exposure = self.report.get("exposure_recommendations", {})

    # ----------------------------
    # Vignette correction
    # ----------------------------

    def vignette_multiplier_for_well(self, well_id: str, channel: str) -> Optional[float]:
        """
        Compute vignette correction multiplier for a specific well and channel.

        Multiplier is derived from the radial model fit.
        To correct intensity: I_corrected = I_raw / multiplier

        Args:
            well_id: Well ID (e.g., "A1")
            channel: Channel name (e.g., "er")

        Returns:
            Correction multiplier in [0, 1], or None if vignette not observable
        """
        if not self._vignette.get("observable"):
            return None

        edge_mult = self._vignette.get("edge_multiplier", {}).get(channel)
        if edge_mult is None:
            return None

        # Compute normalized radius for this well
        try:
            r_norm = self._normalized_radius_for_well(well_id)
        except ValueError:
            return None

        # Radial model: multiplier(r) = center + (edge - center) * r^2
        # where center = 1.0 (by definition), edge = edge_multiplier
        center_mult = 1.0
        mult = center_mult + (edge_mult - center_mult) * r_norm**2

        return float(mult)

    def correct_morphology(
        self, morphology: Dict[str, float], well_id: str
    ) -> Dict[str, float]:
        """
        Apply vignette correction to morphology dict.

        Args:
            morphology: Raw morphology dict (5 channels)
            well_id: Well ID for spatial correction

        Returns:
            Corrected morphology dict (same keys as input)
        """
        if not self._vignette.get("observable"):
            # No correction available
            return morphology.copy()

        corrected = {}
        for ch, raw_val in morphology.items():
            mult = self.vignette_multiplier_for_well(well_id, ch)
            if mult is not None and mult > 0:
                # Divide by multiplier to boost edge wells
                corrected[ch] = raw_val / mult
            else:
                corrected[ch] = raw_val

        return corrected

    def _normalized_radius_for_well(self, well_id: str, n_rows: int = 16, n_cols: int = 24) -> float:
        """Compute normalized radial distance from plate center."""
        import re

        m = re.match(r"^([A-P])(\d{1,2})$", well_id.strip())
        if not m:
            raise ValueError(f"Invalid 384-well ID: {well_id}")

        row_idx = ord(m.group(1)) - ord("A")
        col_idx = int(m.group(2)) - 1

        # Plate center (0-indexed)
        center_r = (n_rows - 1) / 2.0
        center_c = (n_cols - 1) / 2.0

        # Distance from center
        dr = row_idx - center_r
        dc = col_idx - center_c
        dist = math.sqrt(dr**2 + dc**2)

        # Max possible distance (corner to center)
        max_dist = math.sqrt(center_r**2 + center_c**2)

        return dist / max_dist if max_dist > 0 else 0.0

    # ----------------------------
    # Saturation awareness
    # ----------------------------

    def safe_max(self, channel: str) -> Optional[float]:
        """
        Return saturation-safe max intensity for this channel.

        Based on 80% of estimated saturation threshold.

        Args:
            channel: Channel name

        Returns:
            Safe max intensity (AU), or None if not observable
        """
        if not self._saturation.get("observable"):
            return None

        per_ch = self._saturation.get("per_channel", {}).get(channel, {})
        # Prefer threshold_estimate, fallback to p99 * 0.8
        threshold = per_ch.get("threshold_estimate") or per_ch.get("p99")
        if threshold is None:
            return None

        # Already at 80% of cap if threshold_estimate, or compute 80% of p99
        safe = threshold * 0.80 if per_ch.get("threshold_estimate") is None else threshold
        return float(safe)

    def saturation_confidence(self, channel: str) -> str:
        """
        Return confidence level for saturation estimate.

        Returns:
            "high", "medium", "low", or "unknown"
        """
        if not self._saturation.get("observable"):
            return "unknown"

        per_ch = self._saturation.get("per_channel", {}).get(channel, {})
        return per_ch.get("confidence", "unknown")

    # ----------------------------
    # Exposure policy
    # ----------------------------

    def exposure_policy(self, sample_class: str = "normal") -> Tuple[float, List[str]]:
        """
        Get recommended exposure multiplier and warnings for sample class.

        Args:
            sample_class: "bright", "normal", or "dim"

        Returns:
            (recommended_multiplier, warnings_list)
        """
        if not self._exposure.get("observable"):
            return (1.0, ["Exposure recommendations not available"])

        # Global warnings (e.g., floor unobservable)
        global_warnings = self._exposure.get("global", {}).get("warnings", [])

        # Per-channel recommendations (use first channel as proxy for now)
        per_ch = self._exposure.get("per_channel", {})
        if not per_ch:
            return (1.0, global_warnings)

        # Average recommended multiplier across channels
        recs = [
            v.get("recommended_exposure_multiplier")
            for v in per_ch.values()
            if v.get("recommended_exposure_multiplier") is not None
        ]

        if not recs:
            return (1.0, global_warnings)

        avg_rec = sum(recs) / len(recs)

        # Simple policy: use recommendation for bright, 1.0 for normal, 1.3 for dim
        policy_map = {
            "bright": avg_rec,  # Usually < 1.0 (dim to avoid saturation)
            "normal": 1.0,
            "dim": min(1.3, 1.0 / avg_rec) if avg_rec < 1.0 else 1.3,  # Boost if safe
        }

        multiplier = policy_map.get(sample_class, 1.0)
        return (multiplier, global_warnings)

    # ----------------------------
    # Quantization awareness
    # ----------------------------

    def effective_resolution(self, channel: str) -> float:
        """
        Return effective resolution (quantization step) for this channel.

        Use this as minimum meaningful difference threshold.
        Differences below 2 * effective_resolution are likely noise.

        Args:
            channel: Channel name

        Returns:
            Effective resolution in AU (default: 0.1 if not observable)
        """
        if not self._quantization.get("observable"):
            return 0.1  # Conservative fallback

        per_ch = self._quantization.get("per_channel", {}).get(channel, {})
        step = per_ch.get("quant_step_estimate")

        if step is None or step <= 0:
            return 0.1

        return float(step)

    def is_significant_difference(self, delta: float, channel: str, threshold_lsb: float = 2.0) -> bool:
        """
        Check if intensity difference is significant (above quantization noise).

        Args:
            delta: Absolute intensity difference
            channel: Channel name
            threshold_lsb: Number of LSBs to consider significant (default: 2.0)

        Returns:
            True if delta is meaningful (> threshold * quant_step)
        """
        resolution = self.effective_resolution(channel)
        return abs(delta) > (threshold_lsb * resolution)

    # ----------------------------
    # Floor status
    # ----------------------------

    def floor_observable(self) -> bool:
        """Check if floor was observable in calibration."""
        return bool(self._floor.get("observable"))

    def floor_reason(self) -> Optional[str]:
        """Get reason why floor is not observable (if applicable)."""
        if not self.floor_observable():
            return self._floor.get("reason")
        return None

    def floor_mean(self, channel: str) -> Optional[float]:
        """
        Get floor mean for a channel (detector bias baseline).

        Args:
            channel: Channel name (e.g., "er")

        Returns:
            Floor mean in AU, or None if floor not observable
        """
        if not self.floor_observable():
            return None
        return self._floor.get("per_channel", {}).get(channel, {}).get("mean")

    def floor_sigma(self, channel: str) -> Optional[float]:
        """
        Get floor noise sigma for a channel.

        Note: Calibration report may show std=0.0 (computed across wells with single measurements).
        This method computes sigma from the range of unique values instead.

        Args:
            channel: Channel name (e.g., "er")

        Returns:
            Estimated floor noise sigma in AU, or None if floor not observable
        """
        if not self.floor_observable():
            return None

        unique_values = self._floor.get("per_channel", {}).get(channel, {}).get("unique_values", [])
        if len(unique_values) < 2:
            return None

        # Estimate sigma from range (assuming ~6-sigma spread in data)
        # With bias + 3-LSB noise, we expect range ~ 6 * sigma
        value_range = max(unique_values) - min(unique_values)
        sigma_estimate = value_range / 6.0

        return sigma_estimate

    def is_above_noise_floor(
        self, signal: float, channel: str, k: float = 5.0
    ) -> Tuple[bool, Optional[str]]:
        """
        SNR guardrail: Check if signal is sufficiently above noise floor.

        This prevents the agent from learning morphology shifts in sub-noise regimes.

        **Quantization-aware threshold**: When quantization step >> floor_sigma,
        the threshold is MAX(k*floor_sigma, 3*quant_step) to prevent declaring
        signals "detectable" when they're stuck on the same ADC code.

        Args:
            signal: Signal value in AU (corrected or raw)
            channel: Channel name (e.g., "er")
            k: SNR threshold multiplier (default 5σ)

        Returns:
            (is_above, reason):
                - is_above: True if signal > floor_mean + max(k*sigma, 3*quant_step)
                - reason: Explanation if floor not observable or signal too low

        Example:
            >>> profile.is_above_noise_floor(signal=0.5, channel="er", k=5.0)
            (True, None)  # Signal is 5σ above floor

            >>> profile.is_above_noise_floor(signal=0.3, channel="er", k=5.0)
            (False, "Signal 0.30 AU is below 5.0σ threshold (floor: 0.25 ± 0.05 AU)")
        """
        if not self.floor_observable():
            # Conservative: if floor unknown, cannot assess SNR
            return False, "Floor not observable - cannot assess SNR"

        # Defensive: Handle None signal (already masked upstream)
        if signal is None:
            return False, "Signal is None (already masked)"

        floor_m = self.floor_mean(channel)
        floor_s = self.floor_sigma(channel)

        if floor_m is None or floor_s is None:
            return False, f"Floor statistics missing for {channel}"

        # Quantization-aware threshold: max(k*sigma, 3*quant_step)
        # This prevents accepting signals that are indistinguishable from floor
        # due to ADC quantization, even if Gaussian noise is tiny.
        quant_step = self.effective_resolution(channel)
        gaussian_threshold = k * floor_s
        quantization_threshold = 3.0 * quant_step  # 3 LSB minimum

        # Use whichever is larger
        noise_margin = max(gaussian_threshold, quantization_threshold)
        threshold = floor_m + noise_margin

        # Track which noise source dominates (for diagnostic message)
        dominant_source = "Gaussian" if gaussian_threshold >= quantization_threshold else "quantization"

        if signal < threshold:
            return False, (
                f"Signal {signal:.2f} AU is below {k:.1f}σ threshold "
                f"(floor: {floor_m:.2f} ± {floor_s:.2f} AU, threshold: {threshold:.2f} AU, "
                f"dominant noise: {dominant_source})"
            )

        return True, None

    def minimum_detectable_signal(self, channel: str, k: float = 5.0) -> Optional[float]:
        """
        Compute minimum detectable signal for a channel.

        **Quantization-aware**: Returns floor_mean + MAX(k*floor_sigma, 3*quant_step)
        to prevent declaring signals "detectable" when quantization dominates.

        Args:
            channel: Channel name
            k: SNR threshold multiplier (default 5σ)

        Returns:
            Minimum signal in AU, or None if floor not observable

        Example:
            With floor_mean=0.25, floor_sigma=0.01, quant_step=0.015:
            - Gaussian contribution: 5*0.01 = 0.05 AU
            - Quantization contribution: 3*0.015 = 0.045 AU
            - MDS = 0.25 + max(0.05, 0.045) = 0.30 AU (Gaussian dominates)

            With floor_mean=0.25, floor_sigma=0.003, quant_step=0.05:
            - Gaussian contribution: 5*0.003 = 0.015 AU
            - Quantization contribution: 3*0.05 = 0.15 AU
            - MDS = 0.25 + max(0.015, 0.15) = 0.40 AU (quantization dominates)
        """
        if not self.floor_observable():
            return None

        floor_m = self.floor_mean(channel)
        floor_s = self.floor_sigma(channel)

        if floor_m is None or floor_s is None:
            return None

        # Quantization-aware: max(k*sigma, 3*quant_step)
        quant_step = self.effective_resolution(channel)
        gaussian_threshold = k * floor_s
        quantization_threshold = 3.0 * quant_step

        noise_margin = max(gaussian_threshold, quantization_threshold)
        return floor_m + noise_margin

    # ----------------------------
    # Metadata
    # ----------------------------

    def calibration_metadata(self) -> Dict[str, Any]:
        """
        Return metadata block for stamping calibrated observations.

        Includes:
          - schema_version
          - report hash (design + config)
          - applied corrections
        """
        return {
            "schema_version": self.schema_version,
            "report_created_utc": self.report.get("created_utc"),
            "design_sha256": self.report.get("inputs", {}).get("design_sha256"),
            "detector_config_sha256": self.report.get("inputs", {}).get("detector_config_sha256"),
            "vignette_applied": self._vignette.get("observable", False),
            "saturation_policy": "avoid" if self._saturation.get("observable") else None,
            "quantization_aware": self._quantization.get("observable", False),
            "floor_observable": self.floor_observable(),
        }
