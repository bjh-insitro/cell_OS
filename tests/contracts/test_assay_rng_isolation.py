"""
Phase 4: Assay RNG Isolation Tests

WHAT IS PROVEN:
===============

These tests enforce the signal/noise separation contract at the VM level:

1. **Noise can be disabled on demand (CV=0)**
   - When cell_line_params have count_cv=0 and viability_cv=0,
     measurements equal ground truth exactly (no tolerance needed)
   - Contract: measurement = signal_function(state) + noise(rng_assay, CV)
   - When CV=0, noise term vanishes → measurement = signal

2. **Assay noise is independent of biology**
   - Swapping vm.rng_assay changes measurements but not ground truth
   - Biology uses rng_treatment (seed+2), assays use rng_assay (seed+3)
   - Streams do not leak into each other (observer independence covenant)

3. **Batch profiles change signal, not just noise**
   - Different RunBatchProfile → different EC50/hazard → different biology
   - Holding rng_assay constant while varying profile proves signal change
   - Batch effects live in biology layer, not measurement layer

WHAT IS NOT YET PROVEN:
========================

**Full deterministic assay mode** (Test 4 deferred):
- LDH/ATP assays have their own noise stack beyond biological_cv:
  * well_cv (technical variation per well)
  * batch_cv (plate-to-plate variation)
  * edge_effect (spatial bias at plate edges)
- The CV=0 hook works for count_cells (simple case) but not complex assays
- Achieving full determinism requires assay-level noise control
- This is an architectural feature (assays have layered realism), not a gap

If assay-level determinism becomes necessary (calibration routines, debugging
regressions, training pipelines), add assay_params override to measure().
For now, the three core proofs establish the observer independence boundary.

Test strategy:
1. Noise-off mode (CV=0) proves measurement = ground truth (count_cells, viability)
2. Swapping rng_assay proves noise independence from biology (ATP signal)
3. Fixed rng_assay with different profiles proves signal changes (batch effects)

This is not "call_count theater" - these are semantic contracts with teeth.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.run_context import RunContext
from src.cell_os.hardware.batch_effects import (
    RunBatchProfile,
    MediaLotEffect,
    IncubatorEffect,
    CellStateEffect,
)


def test_noise_off_count_cells_matches_ground_truth():
    """
    Test 1: Noise-off makes measurement equal ground truth.

    When CV=0, count_cells should return exactly vessel.cell_count.
    This proves: assay = signal_function(state) + noise(rng_assay, CV).
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("v", "A549", initial_count=123456, initial_viability=0.98)

    # Disable measurement noise
    params = vm.cell_line_params.setdefault("A549", {})
    params["cell_count_cv"] = 0.0
    params["viability_cv"] = 0.0

    # Measure
    obs = vm.count_cells("v", vessel_id="v")
    truth = vm.vessel_states["v"].cell_count

    # Assert exact match (no tolerance needed for CV=0)
    assert obs["status"] == "success"
    assert abs(obs["count"] - truth) < 1e-9, \
        f"Noise-off failed: measured {obs['count']:.2f} != truth {truth:.2f}"

    print(f"✓ Noise-off: measurement = {obs['count']:.2f}, truth = {truth:.2f}")


def test_noise_off_viability_matches_ground_truth():
    """
    Test 1b: Noise-off for viability measurement.

    When viability_cv=0, measured viability should match vessel.viability exactly.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.98)

    # Treat to create viability change
    vm.treat_with_compound("v", "tunicamycin", 1.0)
    vm.advance_time(12.0)

    # Disable measurement noise
    params = vm.cell_line_params.setdefault("A549", {})
    params["viability_cv"] = 0.0

    # Measure
    obs = vm.count_cells("v", vessel_id="v")
    truth = vm.vessel_states["v"].viability

    # Assert exact match
    assert obs["status"] == "success"
    assert abs(obs["viability"] - truth) < 1e-9, \
        f"Noise-off viability failed: measured {obs['viability']:.6f} != truth {truth:.6f}"

    print(f"✓ Noise-off viability: measurement = {obs['viability']:.6f}, truth = {truth:.6f}")


def test_assay_rng_changes_measurement_not_biology():
    """
    Test 2: Same biology seed, different assay RNG gives different measurements, identical truth.

    This proves:
    - rng_assay controls measurement noise
    - Biology does not depend on rng_assay (observer independence)
    """
    vm1 = BiologicalVirtualMachine(seed=42)
    vm2 = BiologicalVirtualMachine(seed=42)

    # Swap assay RNG to different seeds (biology seed=42 held constant)
    vm1.rng_assay = np.random.default_rng(1001)
    vm2.rng_assay = np.random.default_rng(1002)

    # Run identical biological trajectory
    for vm in (vm1, vm2):
        vm.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.98)
        vm.treat_with_compound("v", "tunicamycin", 1.0)
        vm.advance_time(12.0)

    # Ground truth must match exactly (biology seed=42 identical)
    v1_truth = vm1.vessel_states["v"].viability
    v2_truth = vm2.vessel_states["v"].viability
    assert abs(v1_truth - v2_truth) < 1e-12, \
        f"Biology differed despite same seed: {v1_truth:.10f} != {v2_truth:.10f}"

    # Measurement should differ (different rng_assay seeds)
    # Use atp_viability_assay which has higher CV than count_cells
    r1 = vm1.atp_viability_assay("v")
    r2 = vm2.atp_viability_assay("v")

    assert r1["status"] == "success"
    assert r2["status"] == "success"

    # ATP signal should differ (noise injected from different rng_assay streams)
    # Allow small chance of collision (would be ~1e-6 probability)
    assert abs(r1["atp_signal"] - r2["atp_signal"]) > 1e-6, \
        f"Measurements identical despite different rng_assay: {r1['atp_signal']:.4f} == {r2['atp_signal']:.4f}"

    print(f"✓ Assay RNG isolation:")
    print(f"  Truth: {v1_truth:.10f} (both VMs)")
    print(f"  ATP signal VM1: {r1['atp_signal']:.4f}")
    print(f"  ATP signal VM2: {r2['atp_signal']:.4f}")
    print(f"  Δ signal: {abs(r1['atp_signal'] - r2['atp_signal']):.4f}")


def test_assay_rng_affects_multiple_measurements():
    """
    Test 2b: Multiple measurements from same vessel with different rng_assay seeds differ.

    Strengthened version: call assay 5 times per VM and assert sequences differ.
    This avoids flakiness from single-draw comparisons.
    """
    vm1 = BiologicalVirtualMachine(seed=42)
    vm2 = BiologicalVirtualMachine(seed=42)

    # Different assay seeds
    vm1.rng_assay = np.random.default_rng(2001)
    vm2.rng_assay = np.random.default_rng(2002)

    for vm in (vm1, vm2):
        vm.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.98)
        vm.treat_with_compound("v", "tunicamycin", 1.0)
        vm.advance_time(12.0)

    # Draw 5 measurements from each VM (simulating technical replicates)
    signals1 = [vm1.atp_viability_assay("v")["atp_signal"] for _ in range(5)]
    signals2 = [vm2.atp_viability_assay("v")["atp_signal"] for _ in range(5)]

    # Sequences should differ (different noise streams)
    # Check at least one position differs by >1e-3 (very conservative)
    max_diff = max(abs(s1 - s2) for s1, s2 in zip(signals1, signals2))
    assert max_diff > 1e-3, \
        f"Measurement sequences too similar: max diff {max_diff:.6f}"

    print(f"✓ Multiple measurements differ:")
    print(f"  VM1 sequence: {[f'{s:.2f}' for s in signals1]}")
    print(f"  VM2 sequence: {[f'{s:.2f}' for s in signals2]}")
    print(f"  Max Δ: {max_diff:.4f}")


def test_batch_profile_changes_signal_with_fixed_assay_rng():
    """
    Test 3: Same assay RNG, different batch profile changes biology (signal).

    This proves:
    - Batch profile affects biology (EC50, hazard, etc.)
    - Assay noise stream is independent
    - Profile differences propagate to deterministic signal differences

    Strategy:
    - Use two different batch profiles (nominal vs bad media lot)
    - Fix rng_assay to identical seed (noise stream identical)
    - Biology will differ → ground truth viability differs
    - Measurements will reflect signal difference (noise held constant)
    """
    # Create two profiles: nominal vs bad media lot
    profile_nominal = RunBatchProfile.nominal(seed=100)

    profile_bad_media = RunBatchProfile(
        schema_version="1.0.0",
        mapping_version="1.0.0",
        seed=200,
        media_lot=MediaLotEffect(lot_id="BAD", log_potency_shift=-0.20),  # Negative shift → lower EC50
        incubator=IncubatorEffect.nominal(),
        cell_state=CellStateEffect.nominal(),
    )

    # Create VMs with different profiles but same biology seed
    # Use public test-only method to inject custom profiles
    ctx_nominal = RunContext.sample(seed=42)
    ctx_nominal.set_batch_profile_for_testing(profile_nominal)

    ctx_bad = RunContext.sample(seed=42)
    ctx_bad.set_batch_profile_for_testing(profile_bad_media)

    vm1 = BiologicalVirtualMachine(seed=42, run_context=ctx_nominal)
    vm2 = BiologicalVirtualMachine(seed=42, run_context=ctx_bad)

    # Fix assay RNG to identical sequence (noise identical)
    vm1.rng_assay = np.random.default_rng(3001)
    vm2.rng_assay = np.random.default_rng(3001)

    # Run identical protocol (different biology due to batch effects)
    for vm in (vm1, vm2):
        vm.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.98)
        vm.treat_with_compound("v", "tunicamycin", 1.0)
        vm.advance_time(12.0)

    # Ground truth should differ (batch profile changed biology)
    truth1 = vm1.vessel_states["v"].viability
    truth2 = vm2.vessel_states["v"].viability

    # Bad media lot has lower EC50 → more toxic → lower viability
    assert abs(truth1 - truth2) > 1e-6, \
        f"Batch profile didn't change biology: {truth1:.6f} == {truth2:.6f}"

    # Measure (noise stream identical, but signal differs)
    r1 = vm1.atp_viability_assay("v")
    r2 = vm2.atp_viability_assay("v")

    assert r1["status"] == "success"
    assert r2["status"] == "success"

    # ATP signal should differ (reflecting biology difference)
    assert abs(r1["atp_signal"] - r2["atp_signal"]) > 1e-3, \
        f"Measurements didn't reflect batch effect: {r1['atp_signal']:.4f} == {r2['atp_signal']:.4f}"

    print(f"✓ Batch profile changes signal (fixed noise):")
    print(f"  Truth (nominal): {truth1:.6f}")
    print(f"  Truth (bad media): {truth2:.6f}")
    print(f"  ATP signal (nominal): {r1['atp_signal']:.4f}")
    print(f"  ATP signal (bad media): {r2['atp_signal']:.4f}")
    print(f"  Δ truth: {abs(truth1 - truth2):.6f}")
    print(f"  Δ signal: {abs(r1['atp_signal'] - r2['atp_signal']):.4f}")


# ==============================================================================
# TEST 4 NOT IMPLEMENTED: Full Deterministic Assay Mode
# ==============================================================================
#
# DISCOVERY: LDH/ATP assays have their own noise stack beyond biological_cv:
#   - well_cv: technical variation per well (viability.py:197)
#   - batch_cv: plate-to-plate variation via stable_u32 RNG (viability.py:232)
#   - edge_effect: spatial bias at plate edges (viability.py:200)
#
# The CV=0 hook (lognormal_multiplier returns 1.0 if cv<=0) works for simple
# cases like count_cells, but complex assays require assay-level noise control.
#
# TO IMPLEMENT TEST 4 (if needed):
#   Option 1: Add assay_params override to LDHViabilityAssay.measure()
#             Allow passing {'well_cv': 0, 'batch_cv': 0, ...}
#   Option 2: Add global deterministic_mode flag to BiologicalVirtualMachine
#             (less recommended - can quietly neuter realism)
#
# WHEN TO IMPLEMENT:
#   - Calibration routines that require measurement = truth
#   - Debugging regression tests that should ignore observation noise
#   - Training pipelines isolating biology dynamics from measurement artifacts
#
# For now, Tests 1-3 establish the core observer independence boundary.
# ==============================================================================


if __name__ == "__main__":
    print("Running Phase 4: Assay RNG Isolation Tests\n")
    print("="*60)

    print("\nTest 1: Noise-off mode")
    print("-"*60)
    test_noise_off_count_cells_matches_ground_truth()
    test_noise_off_viability_matches_ground_truth()

    print("\n" + "="*60)
    print("\nTest 2: Assay RNG independence")
    print("-"*60)
    test_assay_rng_changes_measurement_not_biology()
    test_assay_rng_affects_multiple_measurements()

    print("\n" + "="*60)
    print("\nTest 3: Batch profile changes signal (fixed noise)")
    print("-"*60)
    test_batch_profile_changes_signal_with_fixed_assay_rng()

    print("\n" + "="*60)
    print("\n✓ All Phase 4 tests passed - Observer independence boundary verified")
    print("="*60)
    print("\nWhat was proven:")
    print("  1. Noise-off mode (CV=0) → measurement = ground truth exactly")
    print("  2. Assay RNG independence → swapping rng_assay changes noise, not biology")
    print("  3. Batch profile causality → profiles change signal even with fixed noise")
    print("\nTest 4 (full deterministic assays) not implemented:")
    print("  Discovery: Assays have layered noise (well_cv, batch_cv, edge effects)")
    print("  See test file header for details on when/how to implement if needed")
    print("="*60)
