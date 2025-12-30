"""
Phase 2D.1: Contamination Identifiability - Experiment Design

Defines 3-regime design for contamination event identifiability:
- Regime A (clean baseline): 0.1× rate → false positive calibration
- Regime B (enriched): 10× rate → detector training
- Regime C (held-out): 5× rate → validation

Precondition: Expected events ≥10 (B) and ≥5 (C), else INSUFFICIENT_EVENTS.
"""

from typing import Dict, List, Tuple
import numpy as np
from scipy import stats


# Baseline rate from thalamus_params.yaml (0.005 per vessel-day)
BASELINE_RATE_PER_VESSEL_DAY = 0.005


def compute_expected_events(rate_per_vessel_day: float, n_vessels: int, duration_h: float) -> float:
    """
    Compute expected contamination events (Poisson λ).

    Args:
        rate_per_vessel_day: Event rate per vessel per day
        n_vessels: Number of vessels
        duration_h: Duration in hours

    Returns:
        Expected event count (λ for Poisson)
    """
    days = duration_h / 24.0
    return rate_per_vessel_day * n_vessels * days


def check_preconditions(n_vessels: int, duration_h: float) -> Tuple[bool, str, Dict[str, float]]:
    """
    Check if experiment design meets minimum event count requirements.

    Preconditions:
    - Regime B (10× enriched): Expected ≥ 10 events
    - Regime C (5× held-out): Expected ≥ 5 events

    Args:
        n_vessels: Number of vessels per regime
        duration_h: Duration in hours

    Returns:
        (passed, message, expected_counts_dict)
    """
    regime_rates = {
        'A_clean': BASELINE_RATE_PER_VESSEL_DAY * 0.1,
        'B_enriched': BASELINE_RATE_PER_VESSEL_DAY * 10.0,
        'C_held_out': BASELINE_RATE_PER_VESSEL_DAY * 5.0,
        'D_disabled': 0.0,
    }

    expected = {
        regime: compute_expected_events(rate, n_vessels, duration_h)
        for regime, rate in regime_rates.items()
    }

    # Check thresholds
    if expected['B_enriched'] < 10.0:
        return False, (
            f"INSUFFICIENT_EVENTS: Regime B expected {expected['B_enriched']:.2f} < 10. "
            f"Need more vessels or longer duration."
        ), expected

    if expected['C_held_out'] < 5.0:
        return False, (
            f"INSUFFICIENT_EVENTS: Regime C expected {expected['C_held_out']:.2f} < 5. "
            f"Need more vessels or longer duration."
        ), expected

    return True, "Preconditions satisfied", expected


def design_regime_configs() -> Dict[str, Dict]:
    """
    Define contamination configs for each regime.

    Returns dict with regime names → config dicts.
    """
    # Base config (same for all regimes except rate_multiplier)
    base_config = {
        'enabled': True,
        'baseline_rate_per_vessel_day': BASELINE_RATE_PER_VESSEL_DAY,
        'type_probs': {'bacterial': 0.5, 'fungal': 0.2, 'mycoplasma': 0.3},
        'severity_lognormal_cv': 0.5,
        'min_severity': 0.25,
        'max_severity': 3.0,
        'phase_params': {
            'bacterial': {'latent_h': 6, 'arrest_h': 6, 'death_rate_per_h': 0.4},
            'fungal': {'latent_h': 12, 'arrest_h': 12, 'death_rate_per_h': 0.2},
            'mycoplasma': {'latent_h': 24, 'arrest_h': 48, 'death_rate_per_h': 0.05},
        },
        'growth_arrest_multiplier': 0.05,
        'morphology_signature_strength': 1.0,
    }

    configs = {}

    # Regime A: Clean baseline (0.1× rate)
    configs['A_clean'] = {**base_config, 'rate_multiplier': 0.1}

    # Regime B: Enriched (10× rate, for detector training)
    configs['B_enriched'] = {**base_config, 'rate_multiplier': 10.0}

    # Regime C: Held-out validation (5× rate)
    configs['C_held_out'] = {**base_config, 'rate_multiplier': 5.0}

    # Regime D: Disabled (no hallucination check)
    configs['D_disabled'] = None  # Will set contamination_config=None in VM

    return configs


def design_vessel_ids(n_vessels: int, regime_label: str) -> List[str]:
    """
    Generate vessel IDs for a regime.

    Args:
        n_vessels: Number of vessels (must fit in 96-well plate grid)
        regime_label: Regime label (e.g., "A_clean", "B_enriched")

    Returns:
        List of vessel IDs like "Plate_A_A01", "Plate_A_A02", ...
        (Format matches "Plate{X}_{well}" so detector_stack can parse)
    """
    if n_vessels > 96:
        raise ValueError(f"n_vessels={n_vessels} exceeds 96-well plate capacity")

    # Use plate ID format that detector_stack can parse: "Plate{X}_{well}"
    plate_id = f"Plate_{regime_label[0]}"  # Plate_A, Plate_B, Plate_C, Plate_D

    vessel_ids = []
    for i in range(n_vessels):
        row = chr(65 + (i // 12))  # A-H
        col = (i % 12) + 1         # 1-12
        vessel_ids.append(f"{plate_id}_{row}{col:02d}")

    return vessel_ids


def design_sampling_times(duration_h: float, interval_h: float = 6.0) -> List[float]:
    """
    Generate sampling timepoints for time-series observations.

    Args:
        duration_h: Total duration (hours)
        interval_h: Sampling interval (default 6h)

    Returns:
        List of sampling times [0, 6, 12, 18, ...]
    """
    n_samples = int(duration_h / interval_h) + 1
    return [i * interval_h for i in range(n_samples)]


def compute_poisson_bounds(lambda_expected: float, quantile_low: float = 0.001, quantile_high: float = 0.999) -> Tuple[int, int]:
    """
    Compute Poisson confidence bounds for event count.

    Args:
        lambda_expected: Expected event count (Poisson λ)
        quantile_low: Lower quantile (default 0.001 → 99.9% lower bound)
        quantile_high: Upper quantile (default 0.999 → 99.9% upper bound)

    Returns:
        (lower_bound, upper_bound) as integers
    """
    lower = int(stats.poisson.ppf(quantile_low, lambda_expected))
    upper = int(stats.poisson.ppf(quantile_high, lambda_expected))
    return lower, upper


# Default experiment parameters (can be overridden in runner)
DEFAULT_N_VESSELS = 96  # Full plate per regime
DEFAULT_DURATION_H = 168.0  # 7 days (enough for mycoplasma to manifest)
DEFAULT_SAMPLING_INTERVAL_H = 6.0  # Every 6 hours
DEFAULT_CELL_LINE = "A549"
DEFAULT_INITIAL_COUNT = 5000


def print_design_summary(n_vessels: int = DEFAULT_N_VESSELS, duration_h: float = DEFAULT_DURATION_H):
    """Print experiment design summary with precondition checks."""
    passed, message, expected = check_preconditions(n_vessels, duration_h)

    print("=" * 80)
    print("Phase 2D.1: Contamination Identifiability - Design Summary")
    print("=" * 80)
    print(f"Vessels per regime: {n_vessels}")
    print(f"Duration: {duration_h:.1f}h ({duration_h/24:.1f} days)")
    print(f"Sampling interval: {DEFAULT_SAMPLING_INTERVAL_H:.1f}h")
    print()

    print("Expected Events per Regime:")
    print("-" * 80)
    for regime, count in expected.items():
        rate = BASELINE_RATE_PER_VESSEL_DAY * {
            'A_clean': 0.1, 'B_enriched': 10.0, 'C_held_out': 5.0, 'D_disabled': 0.0
        }[regime]
        lower, upper = compute_poisson_bounds(count)
        print(f"  {regime:15s}: λ={count:6.2f}  rate={rate:.4f}/vessel-day  bounds=[{lower:3d}, {upper:3d}]")

    print()
    print(f"Precondition Check: {message}")
    print("=" * 80)

    if not passed:
        print("\n⚠️  DESIGN DOES NOT MEET PRECONDITIONS")
        print("    Increase n_vessels or duration_h to meet minimum event counts.")
    else:
        print("\n✅  Design meets preconditions. Ready to run.")

    return passed


if __name__ == "__main__":
    # Print design summary with default parameters
    passed = print_design_summary()
    exit(0 if passed else 1)
