"""
SNR Policy - Agent-facing guardrails for signal-to-noise ratio.

Phase 4 feature: Requires floor.observable = true in calibration profile.

This module prevents the agent from learning morphology shifts in sub-noise regimes
by checking SNR thresholds before accepting measurements for belief updates.

Usage:
    profile = CalibrationProfile("calibration_report.json")
    policy = SNRPolicy(profile, threshold_sigma=5.0)

    # Check if a single measurement is above noise floor
    is_valid, reason = policy.check_measurement(signal=0.5, channel="er")

    # Check if a condition summary has sufficient SNR
    is_valid, warnings = policy.check_condition_summary(condition)

    # Filter observations to remove low-SNR conditions
    filtered_obs = policy.filter_observation(observation)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class SNRPolicy:
    """
    Agent-facing SNR policy enforcer.

    Prevents agent from learning morphology shifts when signals are below
    the minimum detectable signal (floor_mean + k*floor_sigma).

    Args:
        calibration_profile: CalibrationProfile instance (from calibration/profile.py)
        threshold_sigma: SNR threshold in units of floor sigma (default: 5.0)
        strict_mode: If True, reject entire condition if ANY channel below threshold.
                     If False, only warn and allow agent to decide.
    """

    def __init__(
        self,
        calibration_profile,
        threshold_sigma: float = 5.0,
        strict_mode: bool = False
    ):
        """Initialize SNR policy with calibration profile."""
        self.profile = calibration_profile
        self.threshold_sigma = threshold_sigma
        self.strict_mode = strict_mode

        # Check if floor is observable
        if not self.profile.floor_observable():
            logger.warning(
                "Floor not observable in calibration profile. "
                "SNR policy will be DISABLED (all measurements accepted). "
                f"Reason: {self.profile.floor_reason()}"
            )
            self.enabled = False
        else:
            logger.info(
                f"SNR policy enabled with {threshold_sigma:.1f}σ threshold "
                f"(strict_mode={strict_mode})"
            )
            self.enabled = True

    def check_measurement(
        self,
        signal: float,
        channel: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a single measurement is above noise floor.

        Args:
            signal: Signal value in AU (corrected or raw)
            channel: Channel name (e.g., "er")

        Returns:
            (is_above, reason):
                - is_above: True if signal is above threshold or policy disabled
                - reason: Explanation if signal too low or floor not observable
        """
        if not self.enabled:
            return True, None

        return self.profile.is_above_noise_floor(
            signal, channel, k=self.threshold_sigma
        )

    def check_condition_summary(
        self,
        condition: Dict[str, Any]
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Check if a condition summary has sufficient SNR across all channels.

        Args:
            condition: ConditionSummary dict with feature_means

        Returns:
            (is_valid, warnings, per_channel_details):
                - is_valid: True if all channels above threshold (or policy disabled)
                - warnings: List of human-readable channel warnings
                - per_channel_details: Machine-readable dict with numeric fields
        """
        if not self.enabled:
            return True, [], {}

        feature_means = condition.get("feature_means", {})
        if not feature_means:
            # No morphology data, cannot assess SNR
            return True, ["No morphology data to assess SNR"], {}

        warnings = []
        per_channel_details = {}
        all_above = True

        for channel, mean_val in feature_means.items():
            # Skip None values (already masked upstream)
            if mean_val is None:
                # Channel already masked - mark as unusable
                per_channel_details[channel] = {
                    "signal": None,
                    "floor_mean": None,
                    "floor_sigma": None,
                    "quant_step": None,
                    "threshold": None,
                    "dominant_noise": None,
                    "is_above": False,
                    "margin": None,
                    "margin_sigma": None,
                    "effective_noise_scale": None
                }
                all_above = False
                warnings.append(f"{channel}: Already masked (None)")
                continue

            is_above, reason = self.check_measurement(mean_val, channel)

            # Get numeric details for machine-readable output
            floor_mean = self.profile.floor_mean(channel)
            floor_sigma = self.profile.floor_sigma(channel)
            quant_step = self.profile.effective_resolution(channel)
            threshold = self.profile.minimum_detectable_signal(channel, k=self.threshold_sigma)

            # Compute margin (how far above/below threshold)
            margin = mean_val - threshold if threshold is not None else None

            # Determine dominant noise source and effective noise scale
            gaussian_threshold = self.threshold_sigma * floor_sigma if floor_sigma else 0.0
            quantization_threshold = 3.0 * quant_step if quant_step else 0.0
            dominant_noise = "gaussian" if gaussian_threshold >= quantization_threshold else "quantization"

            # Effective noise scale (for normalized margin)
            # This is the "unit" of noise: max(floor_sigma, quant_step/3)
            effective_noise_scale = max(floor_sigma if floor_sigma else 0.0,
                                       quant_step / 3.0 if quant_step else 0.0)

            # Normalized margin (in units of effective noise)
            # This stays comparable even if floor_mean drifts, quant_step changes, etc.
            margin_sigma = None
            if margin is not None and effective_noise_scale > 0:
                margin_sigma = margin / effective_noise_scale

            per_channel_details[channel] = {
                "signal": float(mean_val),
                "floor_mean": float(floor_mean) if floor_mean is not None else None,
                "floor_sigma": float(floor_sigma) if floor_sigma is not None else None,
                "quant_step": float(quant_step) if quant_step else None,
                "threshold": float(threshold) if threshold is not None else None,
                "dominant_noise": dominant_noise,
                "is_above": bool(is_above),
                "margin": float(margin) if margin is not None else None,
                "margin_sigma": float(margin_sigma) if margin_sigma is not None else None,
                "effective_noise_scale": float(effective_noise_scale) if effective_noise_scale else None
            }

            if not is_above:
                all_above = False
                warnings.append(f"{channel}: {reason}")

        # In strict mode, reject condition if ANY channel below threshold
        # In non-strict mode, allow but warn
        is_valid = all_above if self.strict_mode else True

        return is_valid, warnings, per_channel_details

    def filter_observation(
        self,
        observation: Dict[str, Any],
        annotate: bool = True,
        mask_dim_channels: bool = True
    ) -> Dict[str, Any]:
        """
        Filter observation to remove/flag low-SNR conditions.

        Args:
            observation: Observation dict with conditions list
            annotate: If True, add SNR metadata to conditions (default: True)
            mask_dim_channels: If True, mask dim channels in feature_means (default: True)

        Returns:
            Filtered observation dict with SNR policy applied
        """
        if not self.enabled:
            # Policy disabled, return observation unchanged
            return observation

        conditions = observation.get("conditions", [])
        filtered_conditions = []
        n_rejected = 0

        for cond in conditions:
            is_valid, warnings, per_channel_details = self.check_condition_summary(cond)

            # Compute quality metrics
            n_dim_channels = sum(1 for ch_detail in per_channel_details.values() if not ch_detail["is_above"])
            n_total_channels = len(per_channel_details)
            quality_score = 1.0 - (n_dim_channels / n_total_channels) if n_total_channels > 0 else 1.0

            # Identify usable and masked channels
            usable_channels = [ch for ch, detail in per_channel_details.items() if detail["is_above"]]
            masked_channels = [ch for ch, detail in per_channel_details.items() if not detail["is_above"]]

            # Compute minimum margin (most conservative channel)
            margins = [detail["margin"] for detail in per_channel_details.values() if detail["margin"] is not None]
            min_margin = min(margins) if margins else None

            # Compute minimum normalized margin (comparable across time/plates)
            margin_sigmas = [detail["margin_sigma"] for detail in per_channel_details.values() if detail.get("margin_sigma") is not None]
            min_margin_sigma = min(margin_sigmas) if margin_sigmas else None

            if annotate:
                # Add SNR metadata to condition (machine-readable + human-readable)
                cond["snr_policy"] = {
                    "enabled": True,
                    "threshold_sigma": self.threshold_sigma,
                    "strict_mode": self.strict_mode,
                    "is_valid": is_valid,
                    "warnings": warnings,  # Human-readable strings
                    "per_channel": per_channel_details,  # Machine-readable numerics
                    "n_dim_channels": n_dim_channels,
                    "n_total_channels": n_total_channels,
                    "quality_score": quality_score,
                    "min_margin": min_margin,
                    "min_margin_sigma": min_margin_sigma,  # Normalized, comparable across time
                    "usable_channels": usable_channels,
                    "masked_channels": masked_channels
                }

            # Mask dim channels in feature_means (lenient mode)
            if mask_dim_channels and not self.strict_mode and masked_channels:
                # Replace dim channel values with None (agent should not use)
                if "feature_means" in cond:
                    for ch in masked_channels:
                        cond["feature_means"][ch] = None

            if self.strict_mode and not is_valid:
                # Strict mode: reject condition entirely
                n_rejected += 1
                logger.warning(
                    f"SNR policy REJECTED condition: {cond.get('compound')} "
                    f"{cond.get('dose_uM')} µM @ {cond.get('time_h')} h. "
                    f"Warnings: {warnings}"
                )
            else:
                # Non-strict or valid: keep condition
                filtered_conditions.append(cond)

                if warnings:
                    logger.info(
                        f"SNR policy WARNING for condition: {cond.get('compound')} "
                        f"{cond.get('dose_uM')} µM @ {cond.get('time_h')} h. "
                        f"Warnings: {warnings} (quality={quality_score:.2f})"
                    )

        # Create filtered observation
        filtered_obs = observation.copy()
        filtered_obs["conditions"] = filtered_conditions

        # Add SNR policy summary to observation metadata
        if annotate:
            filtered_obs["snr_policy_summary"] = {
                "enabled": True,
                "threshold_sigma": self.threshold_sigma,
                "strict_mode": self.strict_mode,
                "mask_dim_channels": mask_dim_channels,
                "n_conditions_total": len(conditions),
                "n_conditions_rejected": n_rejected,
                "n_conditions_accepted": len(filtered_conditions)
            }

        if n_rejected > 0:
            logger.warning(
                f"SNR policy rejected {n_rejected}/{len(conditions)} conditions "
                f"due to sub-noise signals (strict_mode={self.strict_mode})"
            )

        return filtered_obs

    def minimum_detectable_signals(self) -> Dict[str, Optional[float]]:
        """
        Get minimum detectable signal for each channel.

        Returns:
            Dict mapping channel name to minimum signal in AU
        """
        if not self.enabled:
            return {}

        channels = ["er", "mito", "nucleus", "actin", "rna"]
        mds = {}

        for ch in channels:
            mds[ch] = self.profile.minimum_detectable_signal(ch, k=self.threshold_sigma)

        return mds

    def summary(self) -> Dict[str, Any]:
        """
        Get human-readable summary of SNR policy status.

        Returns:
            Dict with policy configuration and thresholds
        """
        if not self.enabled:
            return {
                "enabled": False,
                "reason": self.profile.floor_reason() if hasattr(self.profile, 'floor_reason') else "Floor not observable"
            }

        mds = self.minimum_detectable_signals()

        return {
            "enabled": True,
            "threshold_sigma": self.threshold_sigma,
            "strict_mode": self.strict_mode,
            "minimum_detectable_signals_AU": mds,
            "policy": (
                "STRICT: Reject conditions with ANY channel below threshold"
                if self.strict_mode
                else "LENIENT: Warn but allow agent to decide"
            )
        }
