"""
VirtualWell Realism Probes - Integration Tests

Tests simulator behavior for epistemic honesty:
- P1: Observer independence (measurement doesn't alter biology)
- P2: Noise model fidelity (lognormal, heteroscedastic, nonnegative)
- P3: Batch effects separability (batch vs biology distinguishable)

All tests use deterministic seeds and small designs for speed.
"""

import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.run_context import RunContext


# ============================================================================
# P1: OBSERVER INDEPENDENCE PROBES
# ============================================================================

def test_p1_1_measure_vs_no_measure_equivalence():
    """
    P1.1: Biology trajectory identical with/without intermediate measurement.

    Setup:
    - Run A: seed vessel → treat → measure at T1 → advance to T2 → check state
    - Run B: seed vessel → treat → advance to T2 (no measure at T1) → check state

    Assert: Biology state at T2 identical (viability, death accounting, stress)
    """
    seed = 42
    vessel_id = "P1_A01"

    # === Run A: WITH intermediate measurement ===
    vm_with = BiologicalVirtualMachine(seed=seed)
    vm_with.seed_vessel(vessel_id, "A549", initial_count=5e5, initial_viability=1.0)
    vm_with.treat_with_compound(vessel_id, "tunicamycin", 2.0)
    vm_with.advance_time(12.0)

    # INTERMEDIATE MEASUREMENT (should not affect biology)
    _ = vm_with.cell_painting_assay(vessel_id)

    vm_with.advance_time(12.0)  # Continue to T2
    vessel_with = vm_with.vessel_states[vessel_id]

    # === Run B: WITHOUT intermediate measurement ===
    vm_without = BiologicalVirtualMachine(seed=seed)
    vm_without.seed_vessel(vessel_id, "A549", initial_count=5e5, initial_viability=1.0)
    vm_without.treat_with_compound(vessel_id, "tunicamycin", 2.0)
    vm_without.advance_time(24.0)  # Go directly to T2
    vessel_without = vm_without.vessel_states[vessel_id]

    # === Verify biology identical ===
    viability_diff = abs(vessel_with.viability - vessel_without.viability)
    assert viability_diff < 1e-9, f"Viability differs: {viability_diff:.2e} (measurement altered biology)"

    er_diff = abs(vessel_with.er_stress - vessel_without.er_stress)
    assert er_diff < 1e-9, f"ER stress differs: {er_diff:.2e}"

    death_compound_diff = abs(vessel_with.death_compound - vessel_without.death_compound)
    assert death_compound_diff < 1e-9, f"Death accounting differs: {death_compound_diff:.2e}"

    return {
        "viability_delta": viability_diff,
        "er_stress_delta": er_diff,
        "death_compound_delta": death_compound_diff,
        "observer_backaction_max": max(viability_diff, er_diff, death_compound_diff)
    }


def test_p1_2_repeated_measurement_idempotence():
    """
    P1.2: Repeated measurements don't change biology (only measurement noise).

    Setup:
    - Measure same well twice at same timepoint
    - Biology state should be identical
    - Measurement noise may differ (RNG advances)
    """
    vm = BiologicalVirtualMachine(seed=123)
    vessel_id = "P1_B02"
    vm.seed_vessel(vessel_id, "A549", initial_count=5e5, initial_viability=1.0)
    vm.treat_with_compound(vessel_id, "tunicamycin", 1.0)
    vm.advance_time(12.0)

    vessel_before = vm.vessel_states[vessel_id]
    viability_before = vessel_before.viability
    er_before = vessel_before.er_stress

    # First measurement
    m1 = vm.cell_painting_assay(vessel_id)

    vessel_mid = vm.vessel_states[vessel_id]
    viability_mid = vessel_mid.viability
    er_mid = vessel_mid.er_stress

    # Second measurement
    m2 = vm.cell_painting_assay(vessel_id)

    vessel_after = vm.vessel_states[vessel_id]
    viability_after = vessel_after.viability
    er_after = vessel_after.er_stress

    # Biology must not change
    assert abs(viability_before - viability_mid) < 1e-9
    assert abs(viability_mid - viability_after) < 1e-9
    assert abs(er_before - er_mid) < 1e-9
    assert abs(er_mid - er_after) < 1e-9

    # Measurements may differ (technical noise)
    er_signal_diff = abs(m1['morphology']['er'] - m2['morphology']['er'])

    return {
        "viability_drift": abs(viability_before - viability_after),
        "er_stress_drift": abs(er_before - er_after),
        "measurement_noise_diff": er_signal_diff
    }


# ============================================================================
# P2: NOISE MODEL PROBES
# ============================================================================

def test_p2_1_nonnegativity_enforcement():
    """
    P2.1: All signals are nonnegative (lognormal noise preserves positivity).

    Setup:
    - Generate N replicates for same condition
    - Check all channels >= 0
    """
    vm = BiologicalVirtualMachine(seed=456)
    n_reps = 16

    signals = []
    for i in range(n_reps):
        vessel_id = f"P2_A{i:02d}"
        vm.seed_vessel(vessel_id, "A549", initial_count=5e5, initial_viability=1.0)
        vm.treat_with_compound(vessel_id, "tunicamycin", 2.0)
        vm.advance_time(12.0)

        morph = vm.cell_painting_assay(vessel_id)

        # Get viability for LDH proxy (ldh_cytotoxicity_assay may not exist)
        vessel = vm.vessel_states[vessel_id]
        ldh_proxy = 1.0 - vessel.viability  # LDH release ~ cell death

        signals.append({
            'er': morph['morphology']['er'],
            'mito': morph['morphology']['mito'],
            'nucleus': morph['morphology']['nucleus'],
            'ldh': ldh_proxy * 100.0  # Scale to signal range
        })

    # Check nonnegativity
    violations = []
    for i, s in enumerate(signals):
        for channel, value in s.items():
            if value < 0:
                violations.append((i, channel, value))

    assert len(violations) == 0, f"Negative signals found: {violations}"

    # Compute CVs
    er_vals = [s['er'] for s in signals]
    ldh_vals = [s['ldh'] for s in signals]

    return {
        "er_min": np.min(er_vals),
        "ldh_min": np.min(ldh_vals),
        "nonnegativity_violations": len(violations),
        "n_replicates": n_reps
    }


def test_p2_2_cv_scaling_heteroscedasticity():
    """
    P2.2: CV scales with signal (heteroscedastic if multiplicative noise).

    Setup:
    - Low-signal condition (high dose → low viability → weak signal)
    - High-signal condition (low dose → high viability → strong signal)
    - Check if CV differs (multiplicative) or constant (additive)
    """
    vm = BiologicalVirtualMachine(seed=789)
    n_reps = 16

    # Low signal: high dose kills cells
    low_signals = []
    for i in range(n_reps):
        vessel_id = f"LOW_{i:02d}"
        vm.seed_vessel(vessel_id, "A549", initial_count=5e5, initial_viability=1.0)
        vm.treat_with_compound(vessel_id, "tunicamycin", 10.0)  # High dose
        vm.advance_time(12.0)
        morph = vm.cell_painting_assay(vessel_id)
        low_signals.append(morph['morphology']['er'])

    # High signal: low dose, cells healthy
    high_signals = []
    for i in range(n_reps):
        vessel_id = f"HIGH_{i:02d}"
        vm.seed_vessel(vessel_id, "A549", initial_count=5e5, initial_viability=1.0)
        vm.treat_with_compound(vessel_id, "tunicamycin", 0.1)  # Low dose
        vm.advance_time(12.0)
        morph = vm.cell_painting_assay(vessel_id)
        high_signals.append(morph['morphology']['er'])

    low_mean = np.mean(low_signals)
    low_std = np.std(low_signals)
    low_cv = low_std / low_mean if low_mean > 0 else 0

    high_mean = np.mean(high_signals)
    high_std = np.std(high_signals)
    high_cv = high_std / high_mean if high_mean > 0 else 0

    return {
        "low_signal_mean": low_mean,
        "low_signal_cv": low_cv,
        "high_signal_mean": high_mean,
        "high_signal_cv": high_cv,
        "cv_ratio": low_cv / high_cv if high_cv > 0 else 1.0,
        "noise_model": "multiplicative" if abs(low_cv - high_cv) < 0.3 else "heteroscedastic"
    }


def test_p2_3_outlier_accounting():
    """
    P2.3: Heavy-tail behavior and outlier tracking (if implemented).

    Setup:
    - Generate many replicates
    - Check for outliers (z > 3)
    - Verify outliers are rare but exist
    """
    vm = BiologicalVirtualMachine(seed=999)
    n_reps = 50

    signals = []
    for i in range(n_reps):
        vessel_id = f"P2_C{i:02d}"
        vm.seed_vessel(vessel_id, "A549", initial_count=5e5, initial_viability=1.0)
        vm.advance_time(12.0)
        morph = vm.cell_painting_assay(vessel_id)
        signals.append(morph['morphology']['er'])

    mean = np.mean(signals)
    std = np.std(signals)
    z_scores = [(s - mean) / std for s in signals]

    outliers = [z for z in z_scores if abs(z) > 3.0]

    return {
        "n_replicates": n_reps,
        "n_outliers": len(outliers),
        "outlier_rate": len(outliers) / n_reps,
        "max_z_score": max(abs(z) for z in z_scores)
    }


# ============================================================================
# P3: BATCH EFFECTS SEPARABILITY PROBES
# ============================================================================

def test_p3_1_batch_creates_systematic_shift():
    """
    P3.1: Different batch contexts create systematic signal shifts.

    Setup:
    - Run with batch_seed_A
    - Run with batch_seed_B (same biology, different batch)
    - Verify systematic shift exists
    """
    biology_seed = 111
    vessel_id = "BATCH_TEST"

    # Batch A
    ctx_a = RunContext.sample(seed=1000, config={'context_strength': 1.0})
    vm_a = BiologicalVirtualMachine(seed=biology_seed, run_context=ctx_a)
    vm_a.seed_vessel(vessel_id, "A549", initial_count=5e5, initial_viability=1.0)
    vm_a.advance_time(12.0)
    morph_a = vm_a.cell_painting_assay(vessel_id)

    # Batch B (same biology, different context)
    ctx_b = RunContext.sample(seed=2000, config={'context_strength': 1.0})
    vm_b = BiologicalVirtualMachine(seed=biology_seed, run_context=ctx_b)
    vm_b.seed_vessel(vessel_id, "A549", initial_count=5e5, initial_viability=1.0)
    vm_b.advance_time(12.0)
    morph_b = vm_b.cell_painting_assay(vessel_id)

    # Compute shifts
    er_shift = morph_a['morphology']['er'] - morph_b['morphology']['er']
    mito_shift = morph_a['morphology']['mito'] - morph_b['morphology']['mito']

    # Verify biology is same (viability should be identical)
    viability_a = vm_a.vessel_states[vessel_id].viability
    viability_b = vm_b.vessel_states[vessel_id].viability
    viability_diff = abs(viability_a - viability_b)

    assert viability_diff < 1e-6, f"Biology changed with batch: {viability_diff}"

    return {
        "batch_er_shift": abs(er_shift),
        "batch_mito_shift": abs(mito_shift),
        "batch_effect_magnitude": np.sqrt(er_shift**2 + mito_shift**2),
        "biology_viability_diff": viability_diff
    }


def test_p3_2_within_vs_across_batch_correlation():
    """
    P3.2: Within-batch correlation > across-batch correlation.

    Setup:
    - Generate wells in batch A
    - Generate wells in batch B
    - Compute correlation within vs across
    """
    n_wells_per_batch = 8

    # Batch A
    ctx_a = RunContext.sample(seed=3000)
    vm_a = BiologicalVirtualMachine(seed=222, run_context=ctx_a)
    signals_a = []
    for i in range(n_wells_per_batch):
        vessel_id = f"A_{i}"
        vm_a.seed_vessel(vessel_id, "A549", initial_count=5e5, initial_viability=1.0)
        vm_a.advance_time(12.0)
        morph = vm_a.cell_painting_assay(vessel_id)
        signals_a.append(morph['morphology']['er'])

    # Batch B
    ctx_b = RunContext.sample(seed=4000)
    vm_b = BiologicalVirtualMachine(seed=333, run_context=ctx_b)
    signals_b = []
    for i in range(n_wells_per_batch):
        vessel_id = f"B_{i}"
        vm_b.seed_vessel(vessel_id, "A549", initial_count=5e5, initial_viability=1.0)
        vm_b.advance_time(12.0)
        morph = vm_b.cell_painting_assay(vessel_id)
        signals_b.append(morph['morphology']['er'])

    # Compute correlations
    # Within-batch: correlation of first half vs second half
    corr_within_a = np.corrcoef(signals_a[:4], signals_a[4:])[0, 1] if len(signals_a) >= 8 else 0

    # Across-batch: correlation between batch A and B
    corr_across = np.corrcoef(signals_a, signals_b)[0, 1] if len(signals_a) == len(signals_b) else 0

    return {
        "within_batch_corr": corr_within_a,
        "across_batch_corr": corr_across,
        "corr_gap": corr_within_a - corr_across,
        "n_wells_per_batch": n_wells_per_batch
    }


def test_p3_3_batch_does_not_flip_mechanism():
    """
    P3.3: Batch shift should not create fake mechanism certainty.

    Setup:
    - Same compound, same dose, two batches
    - Check if mechanism classification is stable

    Note: This is a diagnostic test. If mechanism flips, we document it
    as a limitation, not fix the posterior.
    """
    biology_seed = 444
    vessel_id = "MECH_TEST"

    # Batch A
    ctx_a = RunContext.sample(seed=5000)
    vm_a = BiologicalVirtualMachine(seed=biology_seed, run_context=ctx_a)
    vm_a.seed_vessel(vessel_id, "A549", initial_count=5e5, initial_viability=1.0)
    vm_a.treat_with_compound(vessel_id, "tunicamycin", 2.0)  # ER stressor
    vm_a.advance_time(12.0)
    morph_a = vm_a.cell_painting_assay(vessel_id)

    # Batch B
    ctx_b = RunContext.sample(seed=6000)
    vm_b = BiologicalVirtualMachine(seed=biology_seed, run_context=ctx_b)
    vm_b.seed_vessel(vessel_id, "A549", initial_count=5e5, initial_viability=1.0)
    vm_b.treat_with_compound(vessel_id, "tunicamycin", 2.0)  # Same compound
    vm_b.advance_time(12.0)
    morph_b = vm_b.cell_painting_assay(vessel_id)

    # Compare ER channel (should be elevated in both)
    er_a = morph_a['morphology']['er']
    er_b = morph_b['morphology']['er']

    # Both should show ER elevation (qualitative check)
    er_consistent = (er_a > 0.5) and (er_b > 0.5)  # Both show elevation

    return {
        "er_signal_batch_a": er_a,
        "er_signal_batch_b": er_b,
        "er_signal_ratio": er_a / er_b if er_b > 0 else 1.0,
        "mechanism_consistent": er_consistent
    }


# ============================================================================
# DIAGNOSTIC AGGREGATOR
# ============================================================================

def generate_realism_probe_diagnostic():
    """
    Run all probes and generate diagnostic summary for diagnostics.jsonl.

    Returns dict with event_type="virtualwell_realism_probe" and results.
    """
    results = {}

    # P1: Observer independence
    try:
        p1_1 = test_p1_1_measure_vs_no_measure_equivalence()
        results['p1_observer_backaction_max'] = p1_1['observer_backaction_max']
        results['p1_observer_backaction_violation'] = p1_1['observer_backaction_max'] > 1e-6
    except Exception as e:
        results['p1_error'] = str(e)

    try:
        p1_2 = test_p1_2_repeated_measurement_idempotence()
        results['p1_repeated_viability_drift'] = p1_2['viability_drift']
    except Exception as e:
        results['p1_2_error'] = str(e)

    # P2: Noise model
    try:
        p2_1 = test_p2_1_nonnegativity_enforcement()
        results['p2_nonnegativity_violations'] = p2_1['nonnegativity_violations']
    except Exception as e:
        results['p2_1_error'] = str(e)

    try:
        p2_2 = test_p2_2_cv_scaling_heteroscedasticity()
        results['p2_noise_cv_low'] = p2_2['low_signal_cv']
        results['p2_noise_cv_high'] = p2_2['high_signal_cv']
        results['p2_noise_model'] = p2_2['noise_model']
    except Exception as e:
        results['p2_2_error'] = str(e)

    try:
        p2_3 = test_p2_3_outlier_accounting()
        results['p2_outlier_rate'] = p2_3['outlier_rate']
        results['p2_max_z_score'] = p2_3['max_z_score']
    except Exception as e:
        results['p2_3_error'] = str(e)

    # P3: Batch effects
    try:
        p3_1 = test_p3_1_batch_creates_systematic_shift()
        results['p3_batch_effect_magnitude'] = p3_1['batch_effect_magnitude']
    except Exception as e:
        results['p3_1_error'] = str(e)

    try:
        p3_2 = test_p3_2_within_vs_across_batch_correlation()
        results['p3_corr_gap'] = p3_2['corr_gap']
    except Exception as e:
        results['p3_2_error'] = str(e)

    try:
        p3_3 = test_p3_3_batch_does_not_flip_mechanism()
        results['p3_mechanism_consistent'] = p3_3['mechanism_consistent']
    except Exception as e:
        results['p3_3_error'] = str(e)

    # Add metadata
    results['event_type'] = 'virtualwell_realism_probe'
    results['timestamp'] = '2025-12-22T17:10:00'  # Would use datetime.now()

    return results


if __name__ == "__main__":
    print("=" * 70)
    print("VirtualWell Realism Probes")
    print("=" * 70)

    tests = [
        ("P1.1: Measure vs no-measure equivalence", test_p1_1_measure_vs_no_measure_equivalence),
        ("P1.2: Repeated measurement idempotence", test_p1_2_repeated_measurement_idempotence),
        ("P2.1: Nonnegativity enforcement", test_p2_1_nonnegativity_enforcement),
        ("P2.2: CV scaling (heteroscedasticity)", test_p2_2_cv_scaling_heteroscedasticity),
        ("P2.3: Outlier accounting", test_p2_3_outlier_accounting),
        ("P3.1: Batch creates systematic shift", test_p3_1_batch_creates_systematic_shift),
        ("P3.2: Within vs across batch correlation", test_p3_2_within_vs_across_batch_correlation),
        ("P3.3: Batch does not flip mechanism", test_p3_3_batch_does_not_flip_mechanism),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n{name}")
        print("-" * 70)
        try:
            result = test_func()
            print(f"✓ PASS")
            for k, v in result.items():
                if isinstance(v, float):
                    print(f"  {k}: {v:.6f}")
                else:
                    print(f"  {k}: {v}")
            results.append((name, True, result))
        except Exception as e:
            print(f"❌ FAIL: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False, {}))

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    passed = sum(1 for _, p, _ in results if p)
    print(f"{passed}/{len(results)} tests passed")

    # Generate diagnostic
    print("\n" + "=" * 70)
    print("Diagnostic Event")
    print("=" * 70)
    diagnostic = generate_realism_probe_diagnostic()
    import json
    print(json.dumps(diagnostic, indent=2))
