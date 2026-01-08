"""
Advanced Biology Models for Synthetic Data Generation.

Features:
1. Biphasic/hormetic dose responses (low-dose stimulation)
2. Calibration framework (fit to real data)
3. Continuous time dynamics (ODE-based population models)
4. Cell density effects (confluence affects response)
5. Instrument artifacts (microscope-specific effects)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from scipy.integrate import odeint
from scipy.optimize import minimize


# =============================================================================
# 1. BIPHASIC / HORMETIC DOSE RESPONSES
# =============================================================================

@dataclass
class HormeticParams:
    """Parameters for hormetic (biphasic) dose-response."""
    ec50_inhibition: float = 10.0      # IC50 for inhibitory phase
    ec50_stimulation: float = 0.1      # EC50 for stimulatory phase
    max_stimulation: float = 1.3       # Max fold-increase at low dose (1.3 = 30% boost)
    hill_inhibition: float = 2.0       # Hill slope for inhibition
    hill_stimulation: float = 1.5      # Hill slope for stimulation
    baseline: float = 1.0              # Baseline response (no drug)


def hormetic_response(
    dose: float,
    params: HormeticParams
) -> float:
    """
    Compute hormetic (biphasic) dose-response.

    Low doses stimulate, high doses inhibit - common in biology:
    - Oxidative stress: low ROS promotes growth signaling
    - Heat shock: mild stress induces protective response
    - Many drugs show hormesis

    Model: response = baseline * stimulation_term * inhibition_term
    """
    if dose <= 0:
        return params.baseline

    # Stimulation term: peaks at low dose, returns to 1 at high dose
    # Uses inverse Hill: maximal at EC50_stim, decays at higher doses
    stim_ratio = dose / params.ec50_stimulation
    stimulation = 1.0 + (params.max_stimulation - 1.0) * (
        stim_ratio ** params.hill_stimulation /
        (1.0 + stim_ratio ** params.hill_stimulation)
    ) * (1.0 / (1.0 + (dose / params.ec50_inhibition) ** 2))

    # Inhibition term: standard Hill equation
    inhib_ratio = dose / params.ec50_inhibition
    inhibition = 1.0 / (1.0 + inhib_ratio ** params.hill_inhibition)

    return params.baseline * stimulation * inhibition


def biphasic_morphology_response(
    dose: float,
    channel: str,
    stress_axis: str,
    params: Optional[HormeticParams] = None
) -> float:
    """
    Compute biphasic morphology response for a specific channel.

    Different channels show different hormetic behaviors:
    - Mito: strong hormesis (mild stress triggers biogenesis)
    - ER: moderate hormesis (UPR is adaptive at low stress)
    - Nucleus: minimal hormesis
    """
    if params is None:
        # Default params vary by channel and stress axis
        params = _get_default_hormetic_params(channel, stress_axis)

    return hormetic_response(dose, params)


def _get_default_hormetic_params(channel: str, stress_axis: str) -> HormeticParams:
    """Get default hormetic parameters for channel/axis combination."""
    # Base parameters
    base = HormeticParams()

    # Channel-specific adjustments
    if channel == 'mito':
        base.max_stimulation = 1.4  # Strong hormesis
        base.ec50_stimulation = 0.05
    elif channel == 'er':
        base.max_stimulation = 1.25
        base.ec50_stimulation = 0.1
    elif channel == 'rna':
        base.max_stimulation = 1.2
    elif channel == 'nucleus':
        base.max_stimulation = 1.05  # Minimal hormesis
    elif channel == 'actin':
        base.max_stimulation = 1.15

    # Stress-axis-specific adjustments
    if stress_axis == 'oxidative':
        base.max_stimulation *= 1.2  # Oxidative stress shows strong hormesis
    elif stress_axis == 'er_stress':
        base.ec50_stimulation *= 0.5  # UPR activates at lower doses

    return base


# =============================================================================
# 2. CALIBRATION FRAMEWORK
# =============================================================================

@dataclass
class CalibrationData:
    """Container for real data used in calibration."""
    well_ids: List[str]
    plate_ids: List[str]
    values: np.ndarray  # Shape: (n_wells, n_channels) or (n_wells,)
    conditions: Optional[Dict[str, List]] = None  # dose, time, etc.


@dataclass
class CalibrationResult:
    """Results from parameter calibration."""
    fitted_params: Dict[str, float]
    loss: float
    n_iterations: int
    converged: bool
    residuals: Optional[np.ndarray] = None


class NoiseCalibrator:
    """
    Calibrate noise model parameters to match real data.

    Uses maximum likelihood or method of moments to fit:
    - Channel correlations
    - Spatial effect magnitudes
    - Row/column CVs
    - Batch drift rates
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def fit_channel_correlations(
        self,
        data: np.ndarray,
        channel_names: List[str]
    ) -> np.ndarray:
        """
        Fit channel correlation matrix from real data.

        Args:
            data: Shape (n_samples, n_channels)
            channel_names: List of channel names

        Returns:
            Correlation matrix (n_channels, n_channels)
        """
        # Compute empirical correlation
        corr = np.corrcoef(data.T)

        # Ensure positive semi-definite (required for Cholesky)
        eigvals, eigvecs = np.linalg.eigh(corr)
        eigvals = np.maximum(eigvals, 1e-6)
        corr = eigvecs @ np.diag(eigvals) @ eigvecs.T

        # Normalize diagonal to 1
        d = np.sqrt(np.diag(corr))
        corr = corr / np.outer(d, d)

        return corr

    def fit_spatial_effects(
        self,
        data: CalibrationData,
        n_rows: int = 8,
        n_cols: int = 12
    ) -> Dict[str, float]:
        """
        Fit spatial effect parameters from real plate data.

        Returns dict with:
        - edge_reduction: Estimated edge effect magnitude
        - row_cv: Row-to-row CV
        - col_cv: Column-to-column CV
        """
        from cell_os.sim.realistic_noise import _parse_well_position, _is_edge_well

        values = data.values.flatten() if data.values.ndim > 1 else data.values

        # Separate edge and center wells
        edge_vals, center_vals = [], []
        for well_id, val in zip(data.well_ids, values):
            row, col = _parse_well_position(well_id)
            if _is_edge_well(row, col, n_rows, n_cols):
                edge_vals.append(val)
            else:
                center_vals.append(val)

        # Estimate edge reduction
        edge_mean = np.mean(edge_vals) if edge_vals else 1.0
        center_mean = np.mean(center_vals) if center_vals else 1.0
        edge_reduction = 1.0 - (edge_mean / center_mean) if center_mean > 0 else 0.0

        # Estimate row/col CVs
        row_means = {}
        col_means = {}
        for well_id, val in zip(data.well_ids, values):
            row, col = _parse_well_position(well_id)
            row_means.setdefault(row, []).append(val)
            col_means.setdefault(col, []).append(val)

        row_avgs = [np.mean(v) for v in row_means.values()]
        col_avgs = [np.mean(v) for v in col_means.values()]

        row_cv = np.std(row_avgs) / np.mean(row_avgs) if row_avgs else 0.03
        col_cv = np.std(col_avgs) / np.mean(col_avgs) if col_avgs else 0.025

        return {
            'edge_reduction': max(0, min(0.3, edge_reduction)),
            'row_cv': max(0.01, min(0.1, row_cv)),
            'col_cv': max(0.01, min(0.1, col_cv)),
        }

    def fit_all(
        self,
        morphology_data: np.ndarray,
        plate_data: CalibrationData,
        channel_names: List[str]
    ) -> Dict[str, any]:
        """Fit all noise parameters from real data."""
        return {
            'channel_correlation': self.fit_channel_correlations(morphology_data, channel_names),
            'spatial': self.fit_spatial_effects(plate_data),
        }


# =============================================================================
# 3. CONTINUOUS TIME DYNAMICS (ODE-BASED)
# =============================================================================

@dataclass
class PopulationODEParams:
    """Parameters for ODE-based cell population model."""
    growth_rate: float = 0.03           # Per-hour growth rate (doubling ~24h)
    carrying_capacity: float = 1e6      # Max cells per well
    death_rate_base: float = 0.001      # Baseline death rate per hour
    drug_kill_rate: float = 0.1         # Max drug-induced death rate
    drug_ec50: float = 10.0             # Drug EC50 for killing
    drug_hill: float = 2.0              # Hill coefficient


class CellPopulationODE:
    """
    ODE-based cell population dynamics.

    Models:
    - Logistic growth with carrying capacity
    - Drug-induced death (dose-dependent)
    - Nutrient depletion effects
    - Time-dependent drug exposure
    """

    def __init__(self, params: Optional[PopulationODEParams] = None):
        self.params = params or PopulationODEParams()

    def _derivatives(
        self,
        y: np.ndarray,
        t: float,
        drug_dose: float,
        feed_times: List[float]
    ) -> np.ndarray:
        """
        Compute derivatives for population ODE.

        State vector y = [live_cells, dead_cells, nutrients]
        """
        live, dead, nutrients = y
        p = self.params

        # Nutrient-limited growth
        nutrient_factor = nutrients / (nutrients + 0.1)

        # Logistic growth
        growth = p.growth_rate * live * (1 - live / p.carrying_capacity) * nutrient_factor

        # Drug-induced death
        if drug_dose > 0:
            drug_effect = (drug_dose / p.drug_ec50) ** p.drug_hill
            drug_death_rate = p.drug_kill_rate * drug_effect / (1 + drug_effect)
        else:
            drug_death_rate = 0

        # Total death
        death = (p.death_rate_base + drug_death_rate) * live

        # Nutrient consumption (proportional to live cells)
        nutrient_consumption = 0.001 * live

        # Check for feeding events
        for feed_time in feed_times:
            if abs(t - feed_time) < 0.5:  # Within 30 min of feed
                nutrients = min(1.0, nutrients + 0.5)

        d_live = growth - death
        d_dead = death
        d_nutrients = -nutrient_consumption

        return np.array([d_live, d_dead, d_nutrients])

    def simulate(
        self,
        initial_cells: float,
        drug_dose: float,
        duration_h: float,
        feed_times: Optional[List[float]] = None,
        dt: float = 0.1
    ) -> Dict[str, np.ndarray]:
        """
        Simulate cell population over time.

        Returns dict with time series for live_cells, dead_cells, nutrients.
        """
        feed_times = feed_times or []

        # Initial state: [live, dead, nutrients]
        y0 = np.array([initial_cells, 0.0, 1.0])

        # Time points
        t = np.arange(0, duration_h + dt, dt)

        # Integrate ODE
        solution = odeint(
            self._derivatives, y0, t,
            args=(drug_dose, feed_times)
        )

        return {
            'time_h': t,
            'live_cells': solution[:, 0],
            'dead_cells': solution[:, 1],
            'nutrients': solution[:, 2],
            'viability': solution[:, 0] / (solution[:, 0] + solution[:, 1] + 1e-9),
        }

    def get_endpoint(
        self,
        initial_cells: float,
        drug_dose: float,
        timepoint_h: float
    ) -> Dict[str, float]:
        """Get population state at a specific timepoint."""
        result = self.simulate(initial_cells, drug_dose, timepoint_h)
        return {
            'live_cells': result['live_cells'][-1],
            'dead_cells': result['dead_cells'][-1],
            'viability': result['viability'][-1],
            'nutrients': result['nutrients'][-1],
        }


# =============================================================================
# 4. CELL DENSITY EFFECTS
# =============================================================================

@dataclass
class DensityEffectParams:
    """Parameters for cell density effects."""
    optimal_confluence: float = 0.7     # Optimal confluence for drug response
    low_density_cv_boost: float = 1.5   # CV multiplier at low density
    high_density_cv_boost: float = 1.3  # CV multiplier at high density
    confluence_drug_resistance: float = 0.3  # How much confluence increases IC50


def compute_density_effects(
    confluence: float,
    params: Optional[DensityEffectParams] = None
) -> Dict[str, float]:
    """
    Compute how cell density affects drug response and noise.

    Effects:
    - Low density: Higher variance (fewer cells per measurement)
    - High density: Drug resistance (reduced penetration, contact inhibition)
    - Optimal density: Best signal-to-noise
    """
    params = params or DensityEffectParams()

    # CV multiplier (U-shaped: higher at low and high density)
    if confluence < params.optimal_confluence:
        # Low density: higher variance
        cv_mult = 1 + params.low_density_cv_boost * (params.optimal_confluence - confluence)
    else:
        # High density: somewhat higher variance
        cv_mult = 1 + params.high_density_cv_boost * (confluence - params.optimal_confluence)

    # Drug sensitivity (decreases at high confluence)
    ic50_multiplier = 1 + params.confluence_drug_resistance * max(0, confluence - 0.5)

    # Signal intensity (peaks at optimal confluence)
    signal_factor = 1 - 0.2 * abs(confluence - params.optimal_confluence)

    return {
        'cv_multiplier': cv_mult,
        'ic50_multiplier': ic50_multiplier,
        'signal_factor': signal_factor,
    }


# =============================================================================
# 5. INSTRUMENT ARTIFACTS
# =============================================================================

@dataclass
class InstrumentParams:
    """Parameters for instrument-specific artifacts."""
    # Illumination uniformity
    vignetting_strength: float = 0.15   # Signal drop at corners
    illumination_gradient: float = 0.05  # Left-right gradient

    # Focus
    focus_drift_per_hour: float = 0.01  # Focus drift rate
    autofocus_accuracy: float = 0.02    # Autofocus error (CV)

    # Detection
    detector_noise_floor: float = 100   # Counts (affects low signals)
    detector_saturation: float = 65000  # Max counts before saturation
    dark_current: float = 50            # Background counts


class InstrumentModel:
    """
    Model instrument-specific artifacts.

    Simulates:
    - Vignetting (signal drop at edges/corners)
    - Illumination gradients
    - Focus variations
    - Detector characteristics
    """

    def __init__(
        self,
        params: Optional[InstrumentParams] = None,
        seed: int = 42
    ):
        self.params = params or InstrumentParams()
        self.rng = np.random.default_rng(seed)

    def compute_vignetting(
        self,
        row: int,
        col: int,
        n_rows: int = 8,
        n_cols: int = 12
    ) -> float:
        """Compute vignetting factor (signal reduction at corners)."""
        # Distance from center (normalized)
        center_row = (n_rows - 1) / 2
        center_col = (n_cols - 1) / 2
        max_dist = np.sqrt(center_row**2 + center_col**2)

        dist = np.sqrt((row - center_row)**2 + (col - center_col)**2)
        norm_dist = dist / max_dist

        # Vignetting: quadratic falloff from center
        vignetting = 1.0 - self.params.vignetting_strength * (norm_dist ** 2)

        return max(0.5, vignetting)

    def compute_illumination(
        self,
        row: int,
        col: int,
        n_rows: int = 8,
        n_cols: int = 12
    ) -> float:
        """Compute illumination gradient effect."""
        # Left-to-right gradient (common in many systems)
        gradient = 1.0 - self.params.illumination_gradient * (col / (n_cols - 1) - 0.5)
        return gradient

    def apply_focus_effect(
        self,
        signal: float,
        well_id: str,
        plate_id: str,
        time_in_run_h: float = 0.0
    ) -> float:
        """Apply focus-related signal variation."""
        import hashlib

        # Deterministic focus error per well
        h = hashlib.blake2s(f"focus_{plate_id}_{well_id}".encode(), digest_size=4).digest()
        seed = int.from_bytes(h, 'little')
        well_rng = np.random.default_rng(seed)

        # Autofocus error
        focus_error = well_rng.normal(0, self.params.autofocus_accuracy)

        # Focus drift over time
        drift = self.params.focus_drift_per_hour * time_in_run_h
        drift_error = well_rng.normal(drift, drift * 0.5)

        # Total focus effect (out of focus = reduced signal)
        total_defocus = abs(focus_error + drift_error)
        signal_reduction = np.exp(-total_defocus * 10)  # Exponential decay

        return signal * signal_reduction

    def apply_detector_effects(self, signal: float) -> float:
        """Apply detector noise and saturation."""
        p = self.params

        # Add dark current
        signal = signal + p.dark_current

        # Shot noise (Poisson)
        if signal > 0:
            signal = self.rng.poisson(signal)

        # Saturation
        signal = min(signal, p.detector_saturation)

        # Subtract dark current for final value
        signal = max(0, signal - p.dark_current)

        return float(signal)

    def apply_all_effects(
        self,
        signal: float,
        row: int,
        col: int,
        well_id: str,
        plate_id: str,
        time_in_run_h: float = 0.0,
        n_rows: int = 8,
        n_cols: int = 12
    ) -> float:
        """Apply all instrument effects to a signal."""
        # Vignetting
        signal *= self.compute_vignetting(row, col, n_rows, n_cols)

        # Illumination gradient
        signal *= self.compute_illumination(row, col, n_rows, n_cols)

        # Focus effects
        signal = self.apply_focus_effect(signal, well_id, plate_id, time_in_run_h)

        # Detector effects (for raw counts; skip if already normalized)
        # signal = self.apply_detector_effects(signal)

        return signal
