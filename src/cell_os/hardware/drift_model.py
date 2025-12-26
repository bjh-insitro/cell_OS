"""
Within-run measurement drift model.

Implements time-dependent instrument drift with:
- Lamp aging (monotone decay)
- Thermal cycles (periodic wobble)
- Smooth wander (random walk with cubic spline interpolation)

All drift is deterministic given seed and time (observer-independent).
"""

import numpy as np
from typing import Dict


class DriftModel:
    """
    Time-dependent measurement drift for imaging and plate reader modalities.

    Drift has three components:
    1. Aging: Monotone saturating decay (lamp/detector degradation)
    2. Cycle: Sinusoidal wobble (thermal cycles, different periods per modality)
    3. Wander: Smooth random walk (instrument instability, shared + modality-specific)

    All parameters sampled once at initialization. Drift evaluation is pure function of time.
    """

    # Aging parameters (per modality)
    AGING_RATE_IMAGING = 0.0012  # per hour
    AGING_RATE_READER = 0.0020   # per hour
    AGING_FLOOR_IMAGING = 0.92
    AGING_FLOOR_READER = 0.88

    # Cycle parameters (per modality)
    CYCLE_AMP_IMAGING = 0.006  # ±0.6%
    CYCLE_AMP_READER = 0.004   # ±0.4%
    CYCLE_PERIOD_IMAGING = 6.0  # hours
    CYCLE_PERIOD_READER = 4.0   # hours

    # Wander parameters (log-space sigma per knot)
    WANDER_SIGMA_SHARED = 0.010
    WANDER_SIGMA_IMAGING = 0.018
    WANDER_SIGMA_READER = 0.014

    # Noise inflation parameters
    NOISE_SIGMA_SHARED = 0.012
    NOISE_SIGMA_IMAGING = 0.016
    NOISE_SIGMA_READER = 0.014
    NOISE_UPTREND = 0.08  # 8% increase over 72h

    # Correlation structure
    ALPHA_SHARED = 0.35  # Shared wander contribution

    # Bounds (soft clamp in log-space)
    GAIN_LOWER = 0.90
    GAIN_UPPER = 1.10
    NOISE_LOWER = 1.00
    NOISE_UPPER = 1.25

    def __init__(self, seed: int):
        """
        Initialize drift model with sampled parameters.

        Args:
            seed: RNG seed for reproducibility
        """
        # Independent RNGs for each component
        rng_shared = np.random.default_rng(seed + 1)
        rng_imaging = np.random.default_rng(seed + 2)
        rng_reader = np.random.default_rng(seed + 3)
        rng_phase = np.random.default_rng(seed + 4)
        rng_noise_shared = np.random.default_rng(seed + 5)
        rng_noise_imaging = np.random.default_rng(seed + 6)
        rng_noise_reader = np.random.default_rng(seed + 7)

        # Knot times (13 knots from 0 to 72h, guaranteed endpoints)
        n_knots = 13
        self.knot_times = np.linspace(0.0, 72.0, n_knots)

        # Sample wander knot values in log-space
        self.shared_knots = rng_shared.normal(0.0, self.WANDER_SIGMA_SHARED, size=n_knots)
        self.imaging_knots = rng_imaging.normal(0.0, self.WANDER_SIGMA_IMAGING, size=n_knots)
        self.reader_knots = rng_reader.normal(0.0, self.WANDER_SIGMA_READER, size=n_knots)

        # Sample noise wander knot values
        self.noise_shared_knots = rng_noise_shared.normal(0.0, self.NOISE_SIGMA_SHARED, size=n_knots)
        self.noise_imaging_knots = rng_noise_imaging.normal(0.0, self.NOISE_SIGMA_IMAGING, size=n_knots)
        self.noise_reader_knots = rng_noise_reader.normal(0.0, self.NOISE_SIGMA_READER, size=n_knots)

        # Sample cycle phases (run-specific starting phase)
        self.imaging_phase = rng_phase.uniform(0, 2*np.pi)
        self.reader_phase = rng_phase.uniform(0, 2*np.pi)

        # Check if scipy is available for cubic spline
        try:
            from scipy.interpolate import CubicSpline
            self._use_cubic = True
        except ImportError:
            self._use_cubic = False

    def get_gain(self, t_hours: float, modality: str) -> float:
        """
        Compute multiplicative gain at time t for modality.

        Args:
            t_hours: Time in hours (float)
            modality: 'imaging' or 'reader'

        Returns:
            Gain multiplier in [GAIN_LOWER, GAIN_UPPER]
        """
        t = float(t_hours)

        # Compute components
        aging = self._compute_aging(t, modality)
        cycle = self._compute_cycle(t, modality)
        wander = self._compute_wander(t, modality)

        # Combine multiplicatively in log-space
        log_gain = np.log(aging) + np.log(cycle) + wander

        # Soft clamp to bounds
        L = np.log(self.GAIN_UPPER)
        log_gain_clamped = np.tanh(log_gain / L) * L

        return float(np.exp(log_gain_clamped))

    def get_noise_inflation(self, t_hours: float, modality: str) -> float:
        """
        Compute noise inflation factor at time t for modality.

        Args:
            t_hours: Time in hours (float)
            modality: 'imaging' or 'reader'

        Returns:
            Noise inflation multiplier in [NOISE_LOWER, NOISE_UPPER]
        """
        t = float(t_hours)

        # Upward trend over time (8% increase over 72h)
        uptrend = 1.0 + self.NOISE_UPTREND * (t / 72.0)

        # Smooth wander
        noise_wander = self._compute_noise_wander(t, modality)

        # Combine
        log_noise = np.log(uptrend) + noise_wander

        # Soft clamp to bounds
        L_lower = np.log(self.NOISE_LOWER)
        L_upper = np.log(self.NOISE_UPPER)
        log_noise_clamped = np.clip(log_noise, L_lower, L_upper)

        return float(np.exp(log_noise_clamped))

    def _compute_aging(self, t: float, modality: str) -> float:
        """Saturating exponential decay (lamp aging)."""
        if modality == 'imaging':
            k = self.AGING_RATE_IMAGING
            floor = self.AGING_FLOOR_IMAGING
        else:  # reader
            k = self.AGING_RATE_READER
            floor = self.AGING_FLOOR_READER

        return floor + (1.0 - floor) * np.exp(-k * t)

    def _compute_cycle(self, t: float, modality: str) -> float:
        """Sinusoidal thermal cycle."""
        if modality == 'imaging':
            amp = self.CYCLE_AMP_IMAGING
            period = self.CYCLE_PERIOD_IMAGING
            phase = self.imaging_phase
        else:  # reader
            amp = self.CYCLE_AMP_READER
            period = self.CYCLE_PERIOD_READER
            phase = self.reader_phase

        return 1.0 + amp * np.sin(2*np.pi * t / period + phase)

    def _compute_wander(self, t: float, modality: str) -> float:
        """
        Smooth wander in log-space (returns log multiplier).

        Combines shared + modality-specific wander with correlation alpha.
        """
        # Interpolate shared wander
        z_shared = self._interpolate_knots(t, self.shared_knots)

        # Interpolate modality-specific wander
        if modality == 'imaging':
            z_modality = self._interpolate_knots(t, self.imaging_knots)
        else:  # reader
            z_modality = self._interpolate_knots(t, self.reader_knots)

        # Combine with correlation structure
        alpha = self.ALPHA_SHARED
        z_total = alpha * z_shared + np.sqrt(1 - alpha**2) * z_modality

        return float(z_total)

    def _compute_noise_wander(self, t: float, modality: str) -> float:
        """Smooth noise wander in log-space (returns log multiplier)."""
        # Interpolate shared noise wander
        z_shared = self._interpolate_knots(t, self.noise_shared_knots)

        # Interpolate modality-specific noise wander
        if modality == 'imaging':
            z_modality = self._interpolate_knots(t, self.noise_imaging_knots)
        else:  # reader
            z_modality = self._interpolate_knots(t, self.noise_reader_knots)

        # Combine with correlation structure
        alpha = self.ALPHA_SHARED
        z_total = alpha * z_shared + np.sqrt(1 - alpha**2) * z_modality

        return float(z_total)

    def debug_components(self, t: float, modality: str) -> Dict[str, float]:
        """
        Return all drift components for debugging.

        Args:
            t: Time in hours
            modality: 'imaging' or 'reader'

        Returns:
            Dict with aging, cycle, wander components and final gain
        """
        t = float(t)

        aging = self._compute_aging(t, modality)
        cycle = self._compute_cycle(t, modality)

        # Wander components (in log-space)
        z_shared = self._interpolate_knots(t, self.shared_knots)

        if modality == 'imaging':
            z_modality = self._interpolate_knots(t, self.imaging_knots)
        else:
            z_modality = self._interpolate_knots(t, self.reader_knots)

        alpha = self.ALPHA_SHARED
        z_total = alpha * z_shared + np.sqrt(1 - alpha**2) * z_modality

        # Combine in log-space for raw gain
        log_gain_raw = np.log(aging) + np.log(cycle) + z_total

        # Soft clamp
        L = np.log(self.GAIN_UPPER)
        log_gain_clamped = np.tanh(log_gain_raw / L) * L

        return {
            'aging': float(aging),
            'cycle': float(cycle),
            'wander_shared': float(z_shared),
            'wander_modality': float(z_modality),
            'wander_total': float(z_total),
            'gain_raw_log': float(log_gain_raw),
            'gain_raw': float(np.exp(log_gain_raw)),
            'gain_clamped': float(np.exp(log_gain_clamped)),
        }

    def _interpolate_knots(self, t: float, knot_values: np.ndarray) -> float:
        """
        Interpolate knot values at time t.

        Uses cubic spline if scipy available, otherwise linear interpolation.

        Args:
            t: Time in hours
            knot_values: Array of knot values (log-space)

        Returns:
            Interpolated value at time t
        """
        # Clamp t to knot range
        t = float(np.clip(t, self.knot_times[0], self.knot_times[-1]))

        if self._use_cubic:
            # Use scipy cubic spline
            from scipy.interpolate import CubicSpline
            spline = CubicSpline(self.knot_times, knot_values, bc_type='natural')
            return float(spline(t))
        else:
            # Fall back to linear interpolation
            return float(np.interp(t, self.knot_times, knot_values))
