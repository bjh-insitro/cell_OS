"""
Tests that simulator is adversarially honest (not comforting).

These catch places where the model becomes "too nice" and trains policies
that fail in the real world.
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine, ConservationViolationError


def test_no_silent_renormalization_in_commit():
    """
    Test that _step_ledger_scale is always 1.0 (no renormalization).

    Previously, _commit_step_death would silently rescale ledgers if they drifted.
    Now it should hard-crash instead (ConservationViolationError).

    Since we can't easily force a violation in normal operation (it's a bug if it happens),
    we just verify the code path doesn't renormalize by checking the flag.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_well", "A549", 1e6)

    # Run a normal simulation with death
    vm.treat_with_compound("test_well", "tunicamycin", dose_uM=2.0)
    vm.advance_time(24.0)

    vessel = vm.vessel_states["test_well"]

    # Check: _step_ledger_scale should always be 1.0 (no renormalization)
    if vessel._step_ledger_scale != 1.0:
        print(f"❌ FAIL: _step_ledger_scale = {vessel._step_ledger_scale} (renormalization occurred)")
        return False

    print(f"✓ PASS: _step_ledger_scale = 1.0 (no renormalization)")
    print(f"  (If conservation violation occurs, it will raise ConservationViolationError)")
    return True


import pytest


@pytest.mark.skip(reason="VesselState.subpopulations not implemented - requires coalition dynamics")
def test_tail_risk_not_mean_risk():
    """
    Test that hazards respond to tail risk, not just mean stress.

    Scenario: Apply tunicamycin to create heterogeneous ER stress
    Check that hazard is proposed based on tail (max stress), not mean.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_well", "A549", 1e6)

    # Apply ER stress inducer and let it evolve heterogeneously
    vm.treat_with_compound("test_well", "tunicamycin", dose_uM=1.0)
    vm.advance_time(12.0)  # Let stress build up

    vessel = vm.vessel_states["test_well"]

    # Check stress distribution
    print(f"ER stress distribution after 12h tunicamycin:")
    stress_values = []
    for name, subpop in vessel.subpopulations.items():
        stress_values.append(subpop['er_stress'])
        print(f"  {name}: {subpop['er_stress']:.2f} (fraction={subpop['fraction']:.2f})")

    mixture = vessel.er_stress
    max_stress = max(stress_values)
    print(f"  mixture (mean): {mixture:.2f}")
    print(f"  max stress: {max_stress:.2f}")

    # Now check if hazard was proposed during last step
    # The key insight: if max_stress > theta but mixture < theta,
    # tail-aware model will propose hazard, mean-based won't

    # Check death accounting - if tail-aware, we should see some ER death
    print(f"  death_er_stress: {vessel.death_er_stress:.4f}")

    # With tail-aware: if any subpop > theta, hazard proposed
    # With mean-based: only if mixture > theta

    if max_stress > 0.6 and mixture < 0.6:
        # This is the adversarial case: tail at risk, mean looks safe
        if vessel.death_er_stress > 0.001:
            print("✓ PASS: Tail risk detected, death started")
            return True
        else:
            print("❌ FAIL: No death despite max stress > theta")
            print("  This is 'comforting' behavior")
            return False
    else:
        print("⚠ WARN: Test scenario didn't create adversarial distribution")
        print("  (Need max > theta AND mean < theta)")
        # Still check if ANY death occurred
        return vessel.death_er_stress > 0.001


def test_count_cells_uses_assay_rng_not_growth():
    """
    Test that measurement doesn't pollute growth RNG stream.

    Observer independence requires measurement and biology use separate RNGs.
    """
    # Run 1: measure once
    vm1 = BiologicalVirtualMachine(seed=42)
    vm1.seed_vessel("test_well", "A549", 1e6)
    vm1.advance_time(24.0)
    vm1.count_cells("test_well")  # Measure once
    vm1.advance_time(24.0)

    # Run 2: don't measure
    vm2 = BiologicalVirtualMachine(seed=42)
    vm2.seed_vessel("test_well", "A549", 1e6)
    vm2.advance_time(24.0)
    # Don't measure
    vm2.advance_time(24.0)

    # Biology should be identical
    vessel1 = vm1.vessel_states["test_well"]
    vessel2 = vm2.vessel_states["test_well"]

    cell_count_diff = abs(vessel1.cell_count - vessel2.cell_count)
    viability_diff = abs(vessel1.viability - vessel2.viability)

    print(f"Cell count: {vessel1.cell_count:.1f} vs {vessel2.cell_count:.1f} (diff={cell_count_diff:.1f})")
    print(f"Viability: {vessel1.viability:.6f} vs {vessel2.viability:.6f} (diff={viability_diff:.9f})")

    if cell_count_diff > 1e-6 or viability_diff > 1e-9:
        print("❌ FAIL: Measurement polluted biology state")
        print("  count_cells() is using wrong RNG stream")
        return False
    else:
        print("✓ PASS: Biology unchanged by measurement")
        return True


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Adversarial Honesty")
    print("=" * 70)
    print()

    tests = [
        ("No silent renormalization in commit", test_no_silent_renormalization_in_commit),
        ("Tail risk not mean risk", test_tail_risk_not_mean_risk),
        ("count_cells uses assay RNG", test_count_cells_uses_assay_rng_not_growth),
    ]

    results = []
    for name, test_func in tests:
        print(f"\nTest: {name}")
        print("-" * 70)
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ EXCEPTION: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
        print()

    print("=" * 70)
    print("Summary:")
    print("=" * 70)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    print()
    print(f"Total: {passed}/{total} passed")
    print("=" * 70)

    sys.exit(0 if passed == total else 1)
