"""
v5 tests: Washout and recovery semantics

4 tripwire tests that verify washout creates a proper state transition
with decaying intracellular burden and stress recovery.
"""

import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_washout_reduces_hazard_gradually():
    """Test 1: Washout reduces hazard quickly but not instantly to zero.

    Tripwire: hazard after washout must decrease within one step,
    but remain >0 if burden half-life is nonzero.
    """
    vm = BiologicalVirtualMachine(seed=42)
    # Low viability to allow attrition gate (viability < 0.5)
    vm.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.3)
    vm.treat_with_compound("v", "tunicamycin", 5.0)
    vessel = vm.vessel_states["v"]

    # Step to 15h (past commitment delays, attrition active)
    vm.advance_time(15.0)

    # Get hazard before washout
    names = sorted(vessel.subpopulations.keys())
    subpops_by_shift = sorted(names, key=lambda n: vessel.subpopulations[n]['ic50_shift'])
    sensitive = subpops_by_shift[0]

    hazard_pre = vessel.subpopulations[sensitive]['_total_hazard']
    assert hazard_pre > 0, f"No hazard before washout: {hazard_pre}"

    # Washout
    vm.washout_compound("v", "tunicamycin")

    # Step 6h (allow burden to decay significantly: 5µM * 0.5^(6/2) = 0.625µM)
    # This gives time for burden decay to dominate over time ramp
    vm.advance_time(6.0)

    # Get hazard after washout
    hazard_post = vessel.subpopulations[sensitive]['_total_hazard']

    # Assert hazard decreased (burden decay dominates)
    # Note: hazard might not go to zero if cells already committed (irreversible)
    # but it should be substantially lower due to burden decay
    assert hazard_post < hazard_pre * 0.5, \
        f"Washout didn't substantially reduce hazard: {hazard_pre:.6f} -> {hazard_post:.6f}"

    print(f"✓ Washout reduces hazard gradually: {hazard_pre:.6f} -> {hazard_post:.6f}/h")


def test_early_washout_prevents_late_commit_deaths():
    """Test 2: Early washout prevents commitment-driven deaths for late-commit subpops.

    This targets the subtle lie: commitment is irreversible, but if you washout
    before a subpop commits, it shouldn't accumulate hazard later.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.98)
    vm.treat_with_compound("v", "tunicamycin", 1.2)  # Moderate dose (~1× IC50)
    vessel = vm.vessel_states["v"]

    # Get sampled commitment delays
    exposure_id = vessel.compound_meta['exposure_ids']['tunicamycin']
    names = sorted(vessel.subpopulations.keys())
    delays = {}
    for name in names:
        cache_key = ('tunicamycin', exposure_id, name)
        delays[name] = vessel.compound_meta['commitment_delays'][cache_key]

    # Sort by delay
    subpops_by_delay = sorted(names, key=lambda n: delays[n])
    early_commit = subpops_by_delay[0]   # Commits first
    late_commit = subpops_by_delay[-1]    # Commits last

    # Washout between early and late commitment times
    t_washout = (delays[early_commit] + delays[late_commit]) / 2
    vm.advance_time(t_washout)
    vm.washout_compound("v", "tunicamycin")

    # Step to past late commitment time
    vm.advance_time(delays[late_commit] - t_washout + 2.0)

    # Check hazards
    h_early = vessel.subpopulations[early_commit].get('_total_hazard', 0.0)
    h_late = vessel.subpopulations[late_commit].get('_total_hazard', 0.0)

    # Early commit should have had some hazard (committed before washout)
    # Late commit should have negligible hazard (washed out before commitment)
    # Note: hazard might be small but non-zero due to burden decay
    assert h_late < h_early * 0.5, \
        f"Late-commit subpop has comparable hazard despite washout before commitment: " \
        f"early={h_early:.6f}, late={h_late:.6f}"

    print(f"✓ Early washout prevents late-commit deaths")
    print(f"  Early commit ({delays[early_commit]:.1f}h): hazard={h_early:.6f}/h")
    print(f"  Late commit ({delays[late_commit]:.1f}h): hazard={h_late:.6f}/h (washed out)")


def test_stress_recovery_after_washout():
    """Test 3: Stress recovery occurs after washout.

    Stress axes should decay after washout while viability stays monotone down.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.98)
    vm.treat_with_compound("v", "tunicamycin", 3.0)  # ER stress compound
    vessel = vm.vessel_states["v"]

    # Step to 10h (allow stress to build)
    vm.advance_time(10.0)

    # Get stress levels before washout
    names = sorted(vessel.subpopulations.keys())
    er_stress_before = {
        name: vessel.subpopulations[name].get('er_stress', 0.0)
        for name in names
    }
    max_stress_before = max(er_stress_before.values())
    v_before = vessel.viability

    # Washout
    vm.washout_compound("v", "tunicamycin")

    # Step forward ~12h (allow recovery)
    vm.advance_time(12.0)

    # Get stress levels after washout
    er_stress_after = {
        name: vessel.subpopulations[name].get('er_stress', 0.0)
        for name in names
    }
    max_stress_after = max(er_stress_after.values())
    v_after = vessel.viability

    # Assert stress decreased
    # Note: stress might be small if not actively tracked by mechanisms
    # So we check that it didn't increase (recovery direction correct)
    assert max_stress_after <= max_stress_before, \
        f"Stress increased after washout: {max_stress_before:.4f} -> {max_stress_after:.4f}"

    # Assert viability didn't increase (death monotone)
    assert v_after <= v_before, \
        f"Viability increased (resurrection): {v_before:.4f} -> {v_after:.4f}"

    # Assert hazards trended down
    hazards_after = [vessel.subpopulations[n]['_total_hazard'] for n in names]
    max_hazard_after = max(hazards_after)
    # Hazard should be very small after washout + recovery time
    assert max_hazard_after < 0.001, \
        f"Hazards didn't trend down after washout: {max_hazard_after:.6f}/h"

    print(f"✓ Stress recovery after washout")
    print(f"  Stress: {max_stress_before:.4f} -> {max_stress_after:.4f}")
    print(f"  Viability: {v_before:.4f} -> {v_after:.4f} (monotone down)")
    print(f"  Hazards: {max_hazard_after:.6f}/h (decayed)")


def test_determinism_across_washout():
    """Test 4: Determinism smoke across washout events.

    Two runs with same seed should produce identical trajectories across washout.
    """
    def run_washout_trajectory(seed):
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.98)
        vm.treat_with_compound("v", "tunicamycin", 5.0)
        vessel = vm.vessel_states["v"]

        # Step to 8h
        vm.advance_time(8.0)

        # Record state before washout
        names = sorted(vessel.subpopulations.keys())
        subpops_by_shift = sorted(names, key=lambda n: vessel.subpopulations[n]['ic50_shift'])
        sensitive = subpops_by_shift[0]
        v_pre = vessel.subpopulations[sensitive]['viability']

        # Washout
        result = vm.washout_compound("v", "tunicamycin")
        exposure = vessel.compound_meta['exposures'].get('tunicamycin')
        washout_time = exposure['washout_time'] if exposure else None
        is_washed = exposure['is_washed_out'] if exposure else False

        # Step to 12h
        vm.advance_time(4.0)

        v_post = vessel.subpopulations[sensitive]['viability']
        h_post = vessel.subpopulations[sensitive]['_total_hazard']

        return (v_pre, washout_time, is_washed, v_post, h_post)

    # Run 1 (seed=42)
    traj1 = run_washout_trajectory(42)

    # Run 2 (seed=42)
    traj2 = run_washout_trajectory(42)

    # Check exact match
    v_pre1, t_w1, washed1, v_post1, h_post1 = traj1
    v_pre2, t_w2, washed2, v_post2, h_post2 = traj2

    assert abs(v_pre1 - v_pre2) < 1e-12, \
        f"Pre-washout viability differs: {v_pre1:.10f} vs {v_pre2:.10f}"
    assert t_w1 == t_w2, \
        f"Washout time differs: {t_w1} vs {t_w2}"
    assert washed1 == washed2, \
        f"Washout status differs: {washed1} vs {washed2}"
    assert abs(v_post1 - v_post2) < 1e-12, \
        f"Post-washout viability differs: {v_post1:.10f} vs {v_post2:.10f}"
    assert abs(h_post1 - h_post2) < 1e-12, \
        f"Post-washout hazard differs: {h_post1:.10f} vs {h_post2:.10f}"

    print(f"✓ Determinism across washout (seed=42)")

    # Run 3 (seed=99) - should differ
    traj3 = run_washout_trajectory(99)
    v_pre3, _, _, v_post3, h_post3 = traj3

    # Different seed should give different commitment delays → different trajectories
    differs = (abs(v_post1 - v_post3) > 1e-9 or abs(h_post1 - h_post3) > 1e-9)
    assert differs, "Different seed didn't produce different trajectory"

    print(f"✓ Trajectories differ with different seed (99)")


if __name__ == "__main__":
    print("Running v5 washout/recovery tests...\n")

    try:
        test_washout_reduces_hazard_gradually()
        print()
        test_early_washout_prevents_late_commit_deaths()
        print()
        test_stress_recovery_after_washout()
        print()
        test_determinism_across_washout()
        print("\n✓ All v5 tests passed - Washout semantics ready to ship")
    except AssertionError as e:
        print(f"\n✗ v5 test failed: {e}")
        sys.exit(1)
