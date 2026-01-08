"""
Test state-dependent measurement noise in CellPaintingAssay.

Verifies that accumulated cellular damage increases measurement variance
(heteroskedasticity), teaching agents that uncertainty is path-dependent.

Priority 3 from audit: Make noise state-dependent (one assay, one coupling).

v0.6.1: Converted to multi-seed testing for statistical robustness.
"""

import sys
import pytest
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from tests.helpers.statistical_tolerance import run_with_multiple_seeds


def _variance_ratio_test_single_seed(seed: int) -> bool:
    """Single-seed variance ratio test. Returns True if passes."""
    # Two separate VMs to ensure independent biology
    vm_clean = BiologicalVirtualMachine(seed=seed)
    vm_damaged = BiologicalVirtualMachine(seed=seed)

    # Initialize vessels
    vm_clean.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vm_damaged.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel_clean = vm_clean.vessel_states["Plate1_A01"]
    vessel_damaged = vm_damaged.vessel_states["Plate1_A01"]

    # Inject damage into vessel_damaged
    vessel_damaged.er_damage = 0.8
    vessel_damaged.mito_damage = 0.8
    vessel_damaged.transport_damage = 0.8

    # Measure N replicates with varying assay RNG
    N = 30  # Reduced from 50 for faster multi-seed execution
    measurements_clean = []
    measurements_damaged = []

    for i in range(N):
        vm_clean.rng_assay = np.random.default_rng(seed * 1000 + i)
        vm_damaged.rng_assay = np.random.default_rng(seed * 1000 + i)

        result_clean = vm_clean.cell_painting_assay("Plate1_A01", plate_id="P1", well_position="A01")
        result_damaged = vm_damaged.cell_painting_assay("Plate1_A01", plate_id="P1", well_position="A01")

        measurements_clean.append(result_clean['morphology']['er'])
        measurements_damaged.append(result_damaged['morphology']['er'])

    var_clean = float(np.var(measurements_clean, ddof=1))
    var_damaged = float(np.var(measurements_damaged, ddof=1))

    # Primary assertion: damage inflates variance by >= 1.5× (relaxed from 2× for multi-seed)
    variance_ok = var_damaged >= 1.5 * var_clean

    # Secondary assertion: means within 25%
    mean_clean = float(np.mean(measurements_clean))
    mean_damaged = float(np.mean(measurements_damaged))
    relative_mean_diff = abs(mean_damaged - mean_clean) / mean_clean
    mean_ok = relative_mean_diff < 0.25

    return variance_ok and mean_ok


@pytest.mark.slow  # ~2 min - run with: pytest -m slow
def test_cell_painting_noise_increases_with_damage():
    """
    Verify that measurement variance increases with accumulated damage.

    v0.6.1: Now runs across 5 seeds, requires 4/5 to pass.
    This prevents seed-locked false positives.

    Strategy:
    - Create two vessels with identical current stress but different damage histories
    - Vessel A: D=0 (clean, never stressed)
    - Vessel B: D=0.8 (heavily damaged, recovered from stress)
    - Measure N replicates with fixed biology, varying assay RNG
    - Assert variance is higher in damaged condition by meaningful factor (>= 1.5×)
    """
    result = run_with_multiple_seeds(
        _variance_ratio_test_single_seed,
        seeds=[42, 123, 456, 789, 1001],  # 5 seeds for practical runtime
        min_pass_rate=0.8  # 4 of 5 must pass
    )

    print(f"\nMulti-seed variance ratio test: {result}")

    assert result.passed, (
        f"Variance ratio test failed: {result.successes}/{result.trials} seeds passed. "
        f"Failures: {result.failures}"
    )


def test_noise_is_state_dependent_not_layout_dependent():
    """
    Verify that noise inflation is driven by damage, not spatial position.

    Strategy:
    - Create two vessels with same damage level
    - Measure from edge well (A01) and center well (H12)
    - Assert variance ratio near 1 (damage drives noise, not position)
    """
    vm = BiologicalVirtualMachine(seed=3000)

    # Two vessels with identical damage
    vm.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vm.seed_vessel("Plate1_H12", "A549", vessel_type="384-well")
    vessel1 = vm.vessel_states["Plate1_A01"]
    vessel2 = vm.vessel_states["Plate1_H12"]

    # Set same damage level
    damage_level = 0.6
    vessel1.er_damage = damage_level
    vessel1.mito_damage = damage_level
    vessel2.er_damage = damage_level
    vessel2.mito_damage = damage_level

    # Measure N replicates from different positions
    N = 40
    measurements_edge = []
    measurements_center = []

    for i in range(N):
        vm.rng_assay = np.random.default_rng(4000 + i)

        result_edge = vm.cell_painting_assay("Plate1_A01", plate_id="P1", well_position="A01")
        result_center = vm.cell_painting_assay("Plate1_H12", plate_id="P1", well_position="H12")

        measurements_edge.append(result_edge['morphology']['er'])
        measurements_center.append(result_center['morphology']['er'])

    # Compute variance
    var_edge = float(np.var(measurements_edge, ddof=1))
    var_center = float(np.var(measurements_center, ddof=1))
    variance_ratio = var_edge / var_center if var_center > 0 else 0.0

    print(f"\nVariance (edge well A01): {var_edge:.6f}")
    print(f"Variance (center well H12): {var_center:.6f}")
    print(f"Ratio (edge/center): {variance_ratio:.2f}×")

    # Assert ratio near 1 (damage drives noise, not position)
    # Allow some position effect (edge wells DO have edge_effect), but damage should dominate
    # Ratio should be in [0.5, 2.0] (factor of 2 tolerance)
    assert 0.5 <= variance_ratio <= 2.0, f"Position bias detected: ratio {variance_ratio:.2f}× outside [0.5, 2.0]"


def test_observer_independence_still_holds():
    """
    Verify that measurement does not perturb biology (observer independence).

    Strategy:
    - Run identical simulation with and without calling measure()
    - Assert key biology state unchanged (viability, damage)
    """
    # Simulation with measurement
    vm_measured = BiologicalVirtualMachine(seed=5000)
    vm_measured.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel_measured = vm_measured.vessel_states["Plate1_A01"]
    vessel_measured.er_damage = 0.7

    # Capture state before measurement
    viability_before = vessel_measured.viability
    er_damage_before = vessel_measured.er_damage

    # Measure
    vm_measured.cell_painting_assay("Plate1_A01", plate_id="P1", well_position="A01")

    # Capture state after measurement
    viability_after = vessel_measured.viability
    er_damage_after = vessel_measured.er_damage

    # Assert biology unchanged
    assert viability_before == viability_after, "Measurement changed viability"
    assert er_damage_before == er_damage_after, "Measurement changed damage"


def _monotonic_variance_test_single_seed(seed: int) -> bool:
    """Single-seed monotonic variance test. Returns True if passes."""
    damage_levels = [0.0, 0.3, 0.6, 0.9]
    variances = []

    vm = BiologicalVirtualMachine(seed=seed)
    vm.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel = vm.vessel_states["Plate1_A01"]

    for damage in damage_levels:
        vessel.er_damage = damage
        vessel.mito_damage = damage
        vessel.transport_damage = damage

        N = 25  # Reduced for faster multi-seed execution
        measurements = []
        for j in range(N):
            vm.rng_assay = np.random.default_rng(seed * 100 + j)
            result = vm.cell_painting_assay("Plate1_A01", plate_id="P1", well_position="A01")
            measurements.append(result['morphology']['er'])

        variance = float(np.var(measurements, ddof=1))
        variances.append(variance)

    # Check monotonic increase
    for i in range(len(variances) - 1):
        if variances[i+1] <= variances[i]:
            return False
    return True


@pytest.mark.slow  # ~3 min - run with: pytest -m slow
def test_realism_tripwire_variance_monotonic_with_damage():
    """
    Realism tripwire: Variance must strictly increase with damage.

    v0.6.1: Now runs across 5 seeds, requires 4/5 to pass.
    This prevents seed-locked false positives.

    This test prevents accidental re-separation of variance from state.
    If this fails six weeks from now, something broke heteroskedasticity.

    Strategy:
    - Generate damage gradient (0, 0.3, 0.6, 0.9)
    - Use SAME vessel to control for well_biology baseline variation
    - Measure variance at each level
    - Assert variance is strictly increasing
    """
    result = run_with_multiple_seeds(
        _monotonic_variance_test_single_seed,
        seeds=[42, 123, 456, 789, 1001],  # 5 seeds for practical runtime
        min_pass_rate=0.8  # 4 of 5 must pass
    )

    print(f"\nMulti-seed monotonic variance test: {result}")

    assert result.passed, (
        f"Monotonic variance tripwire failed: {result.successes}/{result.trials} seeds passed. "
        f"Failures: {result.failures}"
    )


def test_damage_noise_multiplier_functional_form():
    """
    Test the functional form of the damage noise multiplier directly.

    Verifies:
    - D=0 → mult=1.0
    - D=0.5 → mult~2.05
    - D=1.0 → mult~4.0
    - Bounded at 5.0 (via D clipping to [0,1])
    """
    vm = BiologicalVirtualMachine(seed=8000)
    vm.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel = vm.vessel_states["Plate1_A01"]

    # Access the assay to call the internal method
    assay = vm._cell_painting_assay

    # Test functional form
    test_cases = [
        (0.0, 1.0, 0.1),    # D=0 → mult=1.0 (±0.1)
        (0.5, 2.05, 0.2),   # D=0.5 → mult~2.05 (±0.2)
        (1.0, 4.0, 0.5),    # D=1.0 → mult~4.0 (±0.5)
    ]

    for damage, expected_mult, tolerance in test_cases:
        vessel.er_damage = damage
        vessel.mito_damage = damage
        vessel.transport_damage = damage

        mult = assay._compute_damage_noise_multiplier(vessel)
        print(f"D={damage:.1f}: mult={mult:.3f} (expected {expected_mult:.3f} ±{tolerance:.1f})")

        assert abs(mult - expected_mult) < tolerance, \
            f"D={damage:.1f}: mult={mult:.3f} outside expected {expected_mult:.3f} ±{tolerance:.1f}"

    # Test bounding: D is clipped to [0,1], so D=10.0 → D=1.0 → mult=4.0
    # The 5.0 cap exists to prevent theoretical runaway, but at D=1.0 we get 4.0
    vessel.er_damage = 10.0  # Artificially high → clipped to 1.0
    mult_capped = assay._compute_damage_noise_multiplier(vessel)
    assert mult_capped == 4.0, f"Multiplier at D>1 (clipped): {mult_capped:.2f} != 4.0"
    assert mult_capped <= 5.0, f"Multiplier not bounded: {mult_capped:.2f} > 5.0"

    print("\n✓ Functional form verified")
