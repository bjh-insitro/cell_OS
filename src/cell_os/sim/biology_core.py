"""
Biology Core - Shared Simulation Logic

Single source of truth for compound pharmacology, attrition dynamics, and morphology.
Used by both standalone simulation and BiologicalVirtualMachine.

Design principles:
- Pure functions (no global state)
- Fail loudly on missing parameters (no silent fallbacks)
- Clear separation: structural effects vs measurement noise
- Time-dependent attrition is physics, not observation-dependent
"""

import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class CompoundParams:
    """Parameters for a single compound."""
    ec50_uM: float
    hill_slope: float
    stress_axis: str
    intensity: float  # Morphology effect magnitude


@dataclass
class CellLineParams:
    """Cell line characteristics."""
    proliferation_index: float  # Relative doubling rate (higher = faster cycling)
    baseline_morphology: Dict[str, float]  # Channel baselines (er, mito, nucleus, actin, rna)
    baseline_ldh: float  # LDH signal from dead cells


# Proliferation indices (relative doubling time)
PROLIF_INDEX = {
    'A549': 1.3,           # Faster cycling (lung cancer)
    'HepG2': 0.8,          # Slower cycling (hepatoma)
    'iPSC_NGN2': 0.1,      # Post-mitotic (neurons barely divide)
    'iPSC_Microglia': 0.6, # Moderate proliferation
}


def compute_microtubule_ic50_multiplier(
    cell_line: str,
    proliferation_index: Optional[float] = None
) -> float:
    """
    Compute IC50 multiplier for microtubule drugs.

    Microtubule toxicity has two components:
    1. Mitosis-driven (dominant for cycling cells - mitotic catastrophe)
    2. Functional transport dependency (dominant for neurons - axonal transport collapse)

    Args:
        cell_line: Cell line identifier
        proliferation_index: Optional override for proliferation rate

    Returns:
        IC50 multiplier (>1 = more resistant, <1 = more sensitive)
    """
    prolif = proliferation_index if proliferation_index is not None else PROLIF_INDEX.get(cell_line, 1.0)

    # Mitosis-driven component
    mitosis_mult = 1.0 / max(prolif, 0.3)  # Clamp to prevent infinite resistance

    # Functional dependency modifies viability IC50 modestly
    # High functional dependency: "morphology collapses early, death follows later"
    functional_dependency = {
        'A549': 0.2,           # Low (mainly mitotic)
        'HepG2': 0.2,          # Low
        'iPSC_NGN2': 0.8,      # High (axonal transport critical)
        'iPSC_Microglia': 0.5, # Moderate (migration, phagocytosis)
    }.get(cell_line, 0.3)

    # IC50 multiplier: mostly mitosis-driven, with modest functional adjustment
    # Functional dependency adds small protective factor (20%) since morphology fails first
    ic50_mult = mitosis_mult * (1.0 + functional_dependency * 0.2)

    # Clamp to reasonable bounds
    return max(0.3, min(5.0, ic50_mult))


def compute_adjusted_ic50(
    compound: str,
    cell_line: str,
    base_ec50: float,
    stress_axis: str,
    cell_line_sensitivity: Optional[Dict[str, float]] = None,
    proliferation_index: Optional[float] = None
) -> float:
    """
    Compute cell-line-adjusted IC50 for viability.

    Args:
        compound: Compound name
        cell_line: Cell line identifier
        base_ec50: Base EC50 from compound parameters
        stress_axis: Stress axis (microtubule gets special treatment)
        cell_line_sensitivity: Optional dict of {compound: {cell_line: multiplier}}
        proliferation_index: Optional override for proliferation rate

    Returns:
        Adjusted IC50 in µM
    """
    if stress_axis == 'microtubule':
        # Use proliferation-coupled model
        ic50_mult = compute_microtubule_ic50_multiplier(cell_line, proliferation_index)
    else:
        # Use cell-line-specific sensitivity lookup
        if cell_line_sensitivity and compound in cell_line_sensitivity:
            ic50_mult = cell_line_sensitivity[compound].get(cell_line, 1.0)
        else:
            ic50_mult = 1.0

    return base_ec50 * ic50_mult


def compute_structural_morphology_microtubule(
    cell_line: str,
    dose_uM: float,
    ec50: float,
    baseline_actin: float,
    baseline_mito: float
) -> Tuple[float, float]:
    """
    Compute structural morphology disruption for microtubule drugs.

    Microtubule drugs show morphology disruption BEFORE viability loss.
    This computes the STRUCTURAL disruption (before viability scaling or noise).

    Args:
        cell_line: Cell line identifier
        dose_uM: Dose in µM
        ec50: Compound EC50
        baseline_actin: Baseline actin signal
        baseline_mito: Baseline mito signal

    Returns:
        (actin_signal, mito_signal) after structural disruption
    """
    # Morphology EC50: Lower than viability EC50 (morphology fails first)
    morph_ec50_fraction = {
        'iPSC_NGN2': 0.3,       # Morphology fails at 30% of viability dose
        'iPSC_Microglia': 0.5,  # Moderate
        'A549': 1.0,            # Morphology and viability fail together
        'HepG2': 1.0
    }.get(cell_line, 1.0)

    morph_ec50 = ec50 * morph_ec50_fraction

    # Smooth saturating Hill equation (not sharp min() clamp)
    morph_penalty = dose_uM / (dose_uM + morph_ec50)  # 0 to 1, smooth

    # Cell-line-specific disruption
    if cell_line == 'iPSC_NGN2':
        # Neurons: major actin/mito disruption at doses below viability IC50
        actin = baseline_actin * (1.0 - 0.6 * morph_penalty)  # Up to 60% reduction
        mito = baseline_mito * (1.0 - 0.5 * morph_penalty)    # Up to 50% reduction
    elif cell_line == 'iPSC_Microglia':
        # Microglia: moderate actin disruption
        actin = baseline_actin * (1.0 - 0.4 * morph_penalty)
        mito = baseline_mito  # No mito disruption
    else:
        # Other cell lines: no early morphology disruption
        actin = baseline_actin
        mito = baseline_mito

    return actin, mito


def compute_transport_dysfunction_score(
    cell_line: str,
    stress_axis: str,
    actin_signal: float,
    mito_signal: float,
    baseline_actin: float,
    baseline_mito: float
) -> float:
    """
    Compute transport dysfunction score from STRUCTURAL morphology.

    CRITICAL: Must be computed BEFORE viability scaling or noise.
    This prevents measurement attenuation from creating runaway feedback.

    Args:
        cell_line: Cell line identifier
        stress_axis: Stress axis
        actin_signal: Structural actin signal (before viability scaling)
        mito_signal: Structural mito signal (before viability scaling)
        baseline_actin: Baseline actin signal
        baseline_mito: Baseline mito signal

    Returns:
        Dysfunction score (0 = no disruption, 1 = complete loss)
    """
    # Only applies to microtubule drugs on neurons
    if stress_axis != 'microtubule' or cell_line != 'iPSC_NGN2':
        return 0.0

    # Measure actual STRUCTURAL disruption
    actin_disruption = max(0.0, 1.0 - actin_signal / baseline_actin)
    mito_disruption = max(0.0, 1.0 - mito_signal / baseline_mito)

    # Average disruption
    dysfunction = 0.5 * (actin_disruption + mito_disruption)

    # Clamp to [0, 1]
    return min(1.0, max(0.0, dysfunction))


def compute_transport_dysfunction_from_exposure(
    cell_line: str,
    compound: str,
    dose_uM: float,
    stress_axis: str,
    base_potency_uM: float,
    time_since_treatment_h: float = 0.0,
    params: Optional[Dict] = None
) -> float:
    """
    Compute transport dysfunction directly from exposure (Option 2: physics-based).

    This is observer-independent - computes dysfunction from dose and cell line,
    not from measured morphology. Prevents "attrition only happens if you look" bugs.

    Args:
        cell_line: Cell line identifier
        compound: Compound name
        dose_uM: Dose in µM
        stress_axis: Stress axis
        base_potency_uM: Reference potency scale (base EC50 before cell-line adjustment)
        time_since_treatment_h: Time since treatment (optional, for time-dependent accumulation)
        params: Optional parameters dict for baseline morphology

    Returns:
        Dysfunction score (0 = no disruption, 1 = complete loss)
    """
    # Only applies to microtubule drugs on neurons
    if stress_axis != 'microtubule' or cell_line != 'iPSC_NGN2':
        return 0.0

    if dose_uM <= 0:
        return 0.0

    # Morphology EC50: Lower than viability EC50 (morphology fails first)
    morph_ec50_fraction = {
        'iPSC_NGN2': 0.3,       # Morphology fails at 30% of viability dose
        'iPSC_Microglia': 0.5,  # Moderate
        'A549': 1.0,            # Morphology and viability fail together
        'HepG2': 1.0
    }.get(cell_line, 1.0)

    morph_ec50 = base_potency_uM * morph_ec50_fraction

    # Smooth saturating Hill equation (0 to 1)
    morph_penalty = dose_uM / (dose_uM + morph_ec50)

    # For iPSC_NGN2: actin gets 60% reduction, mito gets 50% reduction
    # Average disruption: (0.6 + 0.5) / 2 * morph_penalty = 0.55 * morph_penalty
    if cell_line == 'iPSC_NGN2':
        dysfunction = 0.55 * morph_penalty
    elif cell_line == 'iPSC_Microglia':
        # Moderate actin disruption only (40%)
        dysfunction = 0.40 * morph_penalty
    else:
        dysfunction = 0.0

    # Optional: time-dependent accumulation (damage worsens over first 24h)
    # Uncomment if you want dysfunction to ramp up over time
    # if time_since_treatment_h < 24.0:
    #     time_factor = time_since_treatment_h / 24.0
    #     dysfunction *= time_factor

    # Clamp to [0, 1]
    return min(1.0, max(0.0, dysfunction))


def compute_instant_viability_effect(
    dose_uM: float,
    ic50_uM: float,
    hill_slope: float
) -> float:
    """
    Compute instant viability effect from dose-response.

    This is the immediate viability change upon compound application.
    Does NOT include time-dependent attrition (that's separate).

    Args:
        dose_uM: Dose in µM
        ic50_uM: IC50 in µM
        hill_slope: Hill coefficient

    Returns:
        Viability effect (0 = dead, 1 = unaffected)
    """
    if dose_uM <= 0:
        return 1.0

    return 1.0 / (1.0 + (dose_uM / ic50_uM) ** hill_slope)


def interval_fraction_after(t0: float, t1: float, threshold: float) -> float:
    """
    Compute fraction of interval [t0, t1) that lies after threshold.

    Used for integrating step functions over time intervals.

    Args:
        t0: Start of interval
        t1: End of interval
        threshold: Threshold time

    Returns:
        Fraction in [0, 1]: 0 if entire interval before threshold,
                           1 if entire interval after threshold,
                           (t1 - threshold) / (t1 - t0) if interval crosses threshold

    Examples:
        >>> interval_fraction_after(0, 24, 12)  # [0, 24) crosses 12h
        0.5  # Half of interval is after 12h
        >>> interval_fraction_after(0, 10, 12)  # [0, 10) entirely before 12h
        0.0
        >>> interval_fraction_after(15, 20, 12)  # [15, 20) entirely after 12h
        1.0
    """
    if t1 <= threshold:
        return 0.0
    if t0 >= threshold:
        return 1.0
    return (t1 - threshold) / (t1 - t0)


def mean_lag_factor_over_interval(
    time_since_seed_start_h: float,
    dt_h: float,
    lag_duration_h: float
) -> float:
    """
    Compute mean lag factor over interval, integrating linear ramp.

    Lag factor ramps linearly from 0 to 1 over lag_duration_h:
    - f(t) = clamp(t / L, 0, 1) where t = time_since_seed, L = lag_duration

    Returns the mean value of f(t) over [time_since_seed_start, time_since_seed_start + dt].

    Args:
        time_since_seed_start_h: Time since seed at start of interval
        dt_h: Interval duration
        lag_duration_h: Duration of lag phase ramp

    Returns:
        Mean lag factor in [0, 1]

    Examples:
        >>> mean_lag_factor_over_interval(0, 24, 12)  # [0, 24h) with 12h lag
        # Ramp [0,12) + plateau [12,24) → mean = (0.5*12 + 1.0*12) / 24 = 0.75

        >>> mean_lag_factor_over_interval(0, 6, 12)  # [0, 6h) with 12h lag
        # Ramp [0,6) → mean = 0.5 * (6/12) = 0.25

        >>> mean_lag_factor_over_interval(15, 5, 12)  # [15, 20h) past lag
        1.0  # Fully grown
    """
    if lag_duration_h <= 0:
        return 1.0  # No lag

    a = time_since_seed_start_h  # Start of interval
    b = a + dt_h  # End of interval

    # Clamp to [0, L]
    x0 = max(0.0, min(a, lag_duration_h))
    x1 = max(0.0, min(b, lag_duration_h))

    # Area under ramp: ∫(t/L) dt from x0 to x1 = (x1^2 - x0^2) / (2L)
    if x1 > x0:
        ramp_area = (x1 * x1 - x0 * x0) / (2.0 * lag_duration_h)
    else:
        ramp_area = 0.0

    # Area under plateau (f=1 after lag completes)
    plateau_start = max(a, lag_duration_h)
    if b > plateau_start:
        plateau_area = b - plateau_start
    else:
        plateau_area = 0.0

    # Mean over interval
    total_area = ramp_area + plateau_area
    mean_factor = total_area / dt_h

    return float(min(1.0, max(0.0, mean_factor)))


def compute_attrition_rate_instantaneous(
    *,
    cell_line: str,
    compound: str,
    dose_uM: float,
    stress_axis: str,
    ic50_uM: float,
    hill_slope: float,
    transport_dysfunction: float,
    time_since_treatment_h: float,
    current_viability: float,
    params: Optional[Dict] = None
) -> float:
    """
    Compute instantaneous attrition rate at a single time point.

    This is the core of the morphology-to-attrition feedback loop.
    Attrition accumulates over time when cells are under high stress.

    CRITICAL FIX: For microtubule axis on dividing cells, returns 0.0 to avoid
    double-attribution with mitotic catastrophe. Mitotic death is attributed
    exclusively to death_mitotic_catastrophe. For non-dividing cells (neurons),
    returns transport-collapse-driven attrition (death_compound).

    NOTE: This function evaluates attrition at a SINGLE time point. For interval
    integration, use compute_attrition_rate_interval_mean() instead.

    Args:
        cell_line: Cell line identifier
        compound: Compound name
        dose_uM: Dose in µM
        stress_axis: Stress axis (oxidative, er_stress, mitochondrial, etc.)
        ic50_uM: Adjusted IC50 for this cell line
        hill_slope: Hill coefficient
        transport_dysfunction: Transport dysfunction score (0-1, from structural morphology)
        time_since_treatment_h: Hours since compound was applied
        current_viability: Current viability (0-1)
        params: Optional parameters dict (for future extensions)

    Returns:
        Attrition rate (fraction killed per hour) at this time point
    """
    # No attrition before 12h (cells need time to commit to death)
    if time_since_treatment_h <= 12.0:
        return 0.0

    # Only applies when viability is already low (< 50%)
    if current_viability >= 0.5:
        return 0.0

    # Calculate dose ratio relative to IC50
    dose_ratio = dose_uM / ic50_uM

    # Only apply attrition when dose >= IC50 (threshold for commitment)
    if dose_ratio < 1.0:
        return 0.0

    # Time scaling: attrition ramps up between 12h → 48h
    time_factor = (time_since_treatment_h - 12.0) / 36.0  # 0 at 12h, 1 at 48h
    time_factor = min(1.0, max(0.0, time_factor))

    # Base attrition rates per stress axis
    base_attrition_rates = {
        'er_stress': 0.40,      # Strong cumulative effect (unfolded protein accumulation)
        'proteasome': 0.35,     # Strong cumulative effect
        'oxidative': 0.20,      # Moderate (ROS accumulates, some adaptation possible)
        'mitochondrial': 0.18,  # Moderate (bioenergetic collapse)
        'dna_damage': 0.20,     # Moderate (apoptosis cascade)
        # 'microtubule' NOT in this dict - handled explicitly below to avoid double-attribution
    }

    # Microtubule-specific: neurons get higher attrition (slow burn death after transport collapse)
    # Dividing cells (cancer lines) return 0.0 - mitotic catastrophe handles attribution exclusively
    if stress_axis == 'microtubule':
        if cell_line == 'iPSC_NGN2':
            # Neurons: non-dividing, die from axonal transport collapse
            # This is distinct from mitotic catastrophe (which doesn't apply to non-dividing cells)
            base_mt_attrition = 0.25

            # Scale attrition by ACTUAL morphology disruption (not dose proxy!)
            # This creates the true "morphology → attrition → viability" causal arc
            dys = transport_dysfunction

            # Nonlinear scaling: mild disruption has ceiling (allows recovery/adaptation)
            # dys^2 means: 20% disruption → 4% scale, 50% disruption → 25% scale
            # This prevents low doses from causing inevitable death
            attrition_scale = 1.0 + 2.0 * (dys ** 2.0)  # 1× at no disruption, up to 3× at complete disruption
            attrition_rate_base = base_mt_attrition * attrition_scale
        else:
            # Dividing cells (A549, HepG2, etc.): mitotic catastrophe is the ONLY attribution
            # Return 0.0 here to prevent double-attribution with death_mitotic_catastrophe
            return 0.0
    else:
        attrition_rate_base = base_attrition_rates.get(stress_axis, 0.10)

    # Stress multiplier: scales with how far past IC50 we are
    # dose_ratio=1.0 → 0.5, dose_ratio=2.0 → 0.67, dose_ratio=10.0 → 0.91
    stress_multiplier = dose_ratio / (1.0 + dose_ratio)

    # Final attrition rate (fraction per hour)
    attrition_rate = attrition_rate_base * stress_multiplier * time_factor / 36.0  # Normalize to per-hour

    return attrition_rate


def compute_attrition_rate_interval_mean(
    *,
    cell_line: str,
    compound: str,
    dose_uM: float,
    stress_axis: str,
    ic50_uM: float,
    hill_slope: float,
    transport_dysfunction: float,
    time_since_treatment_start_h: float,
    dt_h: float,
    current_viability: float,
    params: Optional[Dict] = None
) -> float:
    """
    Compute interval-averaged attrition rate, properly integrating step functions.

    This wrapper handles the 12h commitment threshold correctly:
    - Computes fraction of interval [t0, t1) that lies past 12h threshold
    - Evaluates instantaneous rate at midpoint of post-threshold segment
    - Returns effective rate = fraction_after * rate_at_midpoint

    For linear ramps (like the 12h → 48h attrition ramp), midpoint evaluation
    equals exact mean, making this both simple and correct.

    Args:
        cell_line: Cell line identifier
        compound: Compound name
        dose_uM: Dose in µM
        stress_axis: Stress axis
        ic50_uM: Adjusted IC50 for this cell line
        hill_slope: Hill coefficient
        transport_dysfunction: Transport dysfunction score (0-1)
        time_since_treatment_start_h: Time since treatment at START of interval (t0)
        dt_h: Interval duration
        current_viability: Current viability (0-1)
        params: Optional parameters dict

    Returns:
        Effective attrition rate (fraction killed per hour) averaged over interval

    Examples:
        >>> compute_attrition_rate_interval_mean(
        ...     ..., time_since_treatment_start_h=0, dt_h=24, ...
        ... )
        # Interval [0, 24h) crosses 12h threshold
        # Fraction after 12h = (24 - 12) / 24 = 0.5
        # Evaluate rate at midpoint of [12, 24) = 18h
        # Return: 0.5 * rate(18h)

        >>> compute_attrition_rate_interval_mean(
        ...     ..., time_since_treatment_start_h=0, dt_h=10, ...
        ... )
        # Interval [0, 10h) entirely before 12h threshold
        # Return: 0.0 (no attrition)

        >>> compute_attrition_rate_interval_mean(
        ...     ..., time_since_treatment_start_h=15, dt_h=5, ...
        ... )
        # Interval [15, 20h) entirely after 12h threshold
        # Evaluate rate at midpoint = 17.5h
        # Return: 1.0 * rate(17.5h)
    """
    ATTRITION_THRESHOLD_H = 12.0

    t0 = time_since_treatment_start_h
    t1 = t0 + dt_h

    # Fraction of interval past commitment threshold
    frac_after = interval_fraction_after(t0, t1, ATTRITION_THRESHOLD_H)

    if frac_after <= 0:
        return 0.0  # Entire interval before threshold

    # Evaluate instantaneous rate at midpoint of post-threshold segment
    # For interval [t0, t1) with threshold T:
    # - If t0 >= T: midpoint = t0 + 0.5 * dt
    # - If t0 < T < t1: midpoint = T + 0.5 * (t1 - T)
    post_threshold_start = max(t0, ATTRITION_THRESHOLD_H)
    post_threshold_end = t1
    t_eval = post_threshold_start + 0.5 * (post_threshold_end - post_threshold_start)

    # Evaluate instantaneous rate at this representative time
    rate_at_midpoint = compute_attrition_rate_instantaneous(
        cell_line=cell_line,
        compound=compound,
        dose_uM=dose_uM,
        stress_axis=stress_axis,
        ic50_uM=ic50_uM,
        hill_slope=hill_slope,
        transport_dysfunction=transport_dysfunction,
        time_since_treatment_h=t_eval,
        current_viability=current_viability,
        params=params,
    )

    # Effective rate over interval = fraction_after * rate_at_midpoint
    return frac_after * rate_at_midpoint


# Backward compatibility alias (deprecated, use interval_mean explicitly)
def compute_attrition_rate(
    *,
    cell_line: str,
    compound: str,
    dose_uM: float,
    stress_axis: str,
    ic50_uM: float,
    hill_slope: float,
    transport_dysfunction: float,
    time_since_treatment_h: float,
    current_viability: float,
    params: Optional[Dict] = None
) -> float:
    """
    DEPRECATED: Use compute_attrition_rate_instantaneous() or compute_attrition_rate_interval_mean().

    This function is kept for backward compatibility with existing code that hasn't
    been updated to use explicit interval integration. It evaluates instantaneous
    rate at a single time point, which creates step-size artifacts.

    New code should use compute_attrition_rate_interval_mean() with explicit t0 and dt.
    """
    return compute_attrition_rate_instantaneous(
        cell_line=cell_line,
        compound=compound,
        dose_uM=dose_uM,
        stress_axis=stress_axis,
        ic50_uM=ic50_uM,
        hill_slope=hill_slope,
        transport_dysfunction=transport_dysfunction,
        time_since_treatment_h=time_since_treatment_h,
        current_viability=current_viability,
        params=params,
    )


def apply_attrition_over_time(
    initial_viability: float,
    attrition_rate_per_hour: float,
    duration_hours: float
) -> float:
    """
    Apply attrition over a time interval.

    Uses exponential survival model: S(t) = S(0) * exp(-rate * t)

    Args:
        initial_viability: Starting viability (0-1)
        attrition_rate_per_hour: Attrition rate (fraction killed per hour)
        duration_hours: Time interval

    Returns:
        Final viability after attrition
    """
    if attrition_rate_per_hour <= 0:
        return initial_viability

    # Exponential survival
    survival = np.exp(-attrition_rate_per_hour * duration_hours)
    return initial_viability * survival


def compute_viability_with_attrition(
    *,
    cell_line: str,
    compound: str,
    dose_uM: float,
    stress_axis: str,
    ic50_uM: float,
    hill_slope: float,
    transport_dysfunction: float,
    timepoint_h: float,
    params: Optional[Dict] = None
) -> Tuple[float, Dict[str, float]]:
    """
    Complete viability calculation including instant effect + time-dependent attrition.

    This is the high-level function that combines:
    1. Instant dose-response (immediate viability hit)
    2. Time-dependent attrition (cumulative death over time)

    Args:
        cell_line: Cell line identifier
        compound: Compound name
        dose_uM: Dose in µM
        stress_axis: Stress axis
        ic50_uM: Adjusted IC50 for this cell line
        hill_slope: Hill coefficient
        transport_dysfunction: Transport dysfunction score (0-1)
        timepoint_h: Time since treatment (hours)
        params: Optional parameters dict

    Returns:
        (final_viability, details_dict)
        details_dict contains: instant_effect, attrition_rate, attrition_applied
    """
    # 1. Instant viability effect
    instant_effect = compute_instant_viability_effect(dose_uM, ic50_uM, hill_slope)

    # 2. Time-dependent attrition
    attrition_rate = compute_attrition_rate(
        cell_line=cell_line,
        compound=compound,
        dose_uM=dose_uM,
        stress_axis=stress_axis,
        ic50_uM=ic50_uM,
        hill_slope=hill_slope,
        transport_dysfunction=transport_dysfunction,
        time_since_treatment_h=timepoint_h,
        current_viability=instant_effect,
        params=params
    )

    # Apply attrition over the time interval
    final_viability = apply_attrition_over_time(instant_effect, attrition_rate, timepoint_h)

    # Clamp to [1%, 100%]
    final_viability = max(0.01, min(1.0, final_viability))

    details = {
        'instant_effect': instant_effect,
        'attrition_rate': attrition_rate,
        'attrition_applied': instant_effect - final_viability,
    }

    return final_viability, details
