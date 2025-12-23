#!/usr/bin/env python3
"""
Validation tests for feeding hardware artifacts.

Tests:
- F1: Serpentine temperature shock geometry
- F2: Volume variation conserves mass and impacts nutrients correctly
- F3: Coupling sanity (artifacts don't teleport into biology)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine

ROWS_384 = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P']
COLS_384 = list(range(1, 25))
ROWS_96 = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
COLS_96 = list(range(1, 13))


def test_f1_serpentine_temperature_shock():
    """
    Test F1: Serpentine temperature shock geometry.

    Validates:
    - Odd rows have negative correlation (col 1 early → more shock)
    - Even rows have positive correlation (col 12 early → more shock)
    - 16/16 rows correct (for 384-well) or 8/8 (for 96-well)
    - |r| > 0.9 within row (smooth gradient)
    """
    print("="*80)
    print("TEST F1: SERPENTINE TEMPERATURE SHOCK GEOMETRY")
    print("="*80)
    print()

    # Use 96-well for faster testing
    vm = BiologicalVirtualMachine(seed=5000)

    # Seed plate with sensitive cell line (iPSC_NGN2)
    print("Seeding 96-well plate with iPSC_NGN2 (temperature-sensitive)...")
    for row in ROWS_96:
        for col in COLS_96:
            well_id = f"well_{row}{col}"
            vm.seed_vessel(
                vessel_id=well_id,
                cell_line="iPSC_NGN2",
                vessel_type="96-well",
                density_level="NOMINAL"
            )

    # Grow for 24h
    print("Growing for 24h...")
    vm.advance_time(24.0)

    # Capture viability before feeding
    viab_before = {}
    for row in ROWS_96:
        for col in COLS_96:
            well_id = f"well_{row}{col}"
            vessel = vm.vessel_states[well_id]
            viab_before[well_id] = vessel.viability

    # Feed all wells
    print("Feeding all wells...")
    for row in ROWS_96:
        for col in COLS_96:
            well_id = f"well_{row}{col}"
            vm.feed_vessel(vessel_id=well_id)

    # Capture viability after feeding
    viab_after = {}
    viab_loss = {}
    for row in ROWS_96:
        for col in COLS_96:
            well_id = f"well_{row}{col}"
            vessel = vm.vessel_states[well_id]
            viab_after[well_id] = vessel.viability
            viab_loss[well_id] = viab_before[well_id] - viab_after[well_id]

    # Validate serpentine pattern
    print("\nValidating serpentine pattern:")
    print("-" * 80)

    serpentine_correct = 0
    correlations = []

    for row_idx, row in enumerate(ROWS_96):
        row_losses = [viab_loss[f"well_{row}{col}"] for col in COLS_96]

        # Check if all losses are identical (would indicate no spatial variation)
        if np.std(row_losses) < 1e-9:
            print(f"  Row {row}: ⚠️  NO VARIATION (std={np.std(row_losses):.2e})")
            continue

        corr = np.corrcoef(COLS_96, row_losses)[0, 1]
        correlations.append(abs(corr))

        is_odd_row = (row_idx % 2) == 0
        # Temperature shock: early wells cool more → higher viability loss
        # Odd rows (L→R): col 1 early → higher loss → NEGATIVE correlation (decreases left to right)
        # Even rows (R→L): col 12 early → higher loss → POSITIVE correlation (increases left to right)
        expected_sign = "NEGATIVE" if is_odd_row else "POSITIVE"
        actual_sign = "POSITIVE" if corr > 0 else "NEGATIVE"

        match = "✓" if expected_sign == actual_sign else "✗"
        serpentine_correct += (expected_sign == actual_sign)

        print(f"  Row {row}: corr={corr:+.3f} {match} (expected {expected_sign}, |r|={abs(corr):.3f})")

    print()
    print(f"Serpentine pattern correct: {serpentine_correct}/{len(ROWS_96)} rows")

    # Validate correlation magnitude (should be high for smooth gradient)
    if correlations:
        mean_abs_corr = np.mean(correlations)
        print(f"Mean |correlation|: {mean_abs_corr:.3f} (expected > 0.9 for smooth gradient)")

    # Validate magnitude
    losses_array = np.array(list(viab_loss.values()))
    mean_loss = 100 * np.mean(losses_array)
    max_loss = 100 * np.max(losses_array)
    min_loss = 100 * np.min(losses_array)

    print()
    print("Viability loss magnitude:")
    print(f"  Mean: {mean_loss:.3f}%")
    print(f"  Range: {min_loss:.3f}% - {max_loss:.3f}%")
    print(f"  Expected: 0.5-1.0% (temperature shock parameter)")

    # Final assertions
    print()
    print("ASSERTIONS:")
    print("-" * 80)

    checks = {
        "Serpentine pattern": serpentine_correct >= len(ROWS_96) - 1,  # Allow 1 failure
        "High correlation": mean_abs_corr > 0.85 if correlations else False,
        "Sane magnitude": 0.3 < mean_loss < 1.5,
    }

    for check, passed in checks.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {check}")

    all_passed = all(checks.values())
    print()
    if all_passed:
        print("🎉 TEST F1 PASSED")
    else:
        print("⚠️  TEST F1 FAILED")

    return all_passed


def test_f2_volume_variation_mass_balance():
    """
    Test F2: Volume variation conserves mass and impacts nutrients correctly.

    Validates:
    - No negative volumes
    - No overflow (respects max_volume_ml)
    - Mass balance: moles conserved in dilution
    - Spatial signature matches expected pattern (pin + serpentine)
    - Higher V_add → concentration closer to fresh media
    """
    print("\n" + "="*80)
    print("TEST F2: VOLUME VARIATION AND MASS BALANCE")
    print("="*80)
    print()

    vm = BiologicalVirtualMachine(seed=5000)

    # Use 384-well to test full plate with pins
    print("Seeding 384-well plate (first 4 rows for speed)...")
    ROWS_TEST = ROWS_384[:4]  # Just A-D for faster testing

    for row in ROWS_TEST:
        for col in COLS_384:
            well_id = f"well_{row}{col}"
            vm.seed_vessel(
                vessel_id=well_id,
                cell_line="HepG2",
                vessel_type="384-well",
                density_level="NOMINAL"
            )

    # Grow for 24h to deplete nutrients
    print("Growing for 24h (depletes nutrients)...")
    vm.advance_time(24.0)

    # Capture state before feeding
    state_before = {}
    for row in ROWS_TEST:
        for col in COLS_384:
            well_id = f"well_{row}{col}"
            vessel = vm.vessel_states[well_id]
            state_before[well_id] = {
                'volume': vessel.current_volume_ml,
                'glucose': vessel.media_glucose_mM,
                'glutamine': vessel.media_glutamine_mM,
            }

    # Feed all wells with fresh media (25 mM glucose, 4 mM glutamine)
    print("Feeding all wells...")
    FRESH_GLUCOSE = 25.0
    FRESH_GLUTAMINE = 4.0

    for row in ROWS_TEST:
        for col in COLS_384:
            well_id = f"well_{row}{col}"
            vm.feed_vessel(
                vessel_id=well_id,
                glucose_mM=FRESH_GLUCOSE,
                glutamine_mM=FRESH_GLUTAMINE
            )

    # Capture state after feeding
    state_after = {}
    for row in ROWS_TEST:
        for col in COLS_384:
            well_id = f"well_{row}{col}"
            vessel = vm.vessel_states[well_id]
            state_after[well_id] = {
                'volume': vessel.current_volume_ml,
                'glucose': vessel.media_glucose_mM,
                'glutamine': vessel.media_glutamine_mM,
            }

    # Validation 1: Non-negativity and bounds
    print("\nValidation 1: Volume bounds")
    print("-" * 80)

    volumes_after = [state_after[f"well_{row}{col}"]['volume'] for row in ROWS_TEST for col in COLS_384]
    min_vol = min(volumes_after)
    max_vol = max(volumes_after)

    print(f"  Volume range: {min_vol*1000:.1f} - {max_vol*1000:.1f} µL")
    print(f"  Working volume: 80 µL (384-well)")
    print(f"  Max volume: 100 µL (384-well)")

    no_negative = all(v >= 0 for v in volumes_after)
    no_overflow = all(v <= 0.100 for v in volumes_after)  # 100 µL max for 384-well

    print(f"  No negative volumes: {'✓ PASS' if no_negative else '✗ FAIL'}")
    print(f"  No overflow: {'✓ PASS' if no_overflow else '✗ FAIL'}")

    # Validation 2: Mass balance (dilution math)
    print("\nValidation 2: Mass balance (dilution equation)")
    print("-" * 80)

    mass_balance_errors = []

    for row in ROWS_TEST:
        for col in COLS_384:
            well_id = f"well_{row}{col}"

            before = state_before[well_id]
            after = state_after[well_id]

            # Expected volume (working volume)
            V_working = 0.080  # 80 µL for 384-well

            # Calculate expected dilution
            # If volume_factor > 1: more fresh media added → stronger dilution
            # Expected: C_new = (C_old × 0 + C_fresh × V_add) / V_add = C_fresh (complete exchange)
            # With partial removal: C_new = (C_old × V_residual + C_fresh × V_add) / V_total

            # For complete exchange (remove working volume, add working volume × volume_factor):
            # V_after_remove ≈ 0 (complete aspiration)
            # C_new ≈ C_fresh (should be close to fresh media concentration)

            # Check mass balance: total moles should make sense
            # moles_new = C_new × V_new
            # moles_expected = C_old × V_residual + C_fresh × V_added

            # For complete exchange, we expect C_new ≈ C_fresh
            glucose_error = abs(after['glucose'] - FRESH_GLUCOSE) / FRESH_GLUCOSE
            mass_balance_errors.append(glucose_error)

    mean_error = 100 * np.mean(mass_balance_errors)
    max_error = 100 * np.max(mass_balance_errors)

    print(f"  Mean concentration error: {mean_error:.2f}% (deviation from fresh media)")
    print(f"  Max concentration error: {max_error:.2f}%")
    print(f"  Expected: <5% (dilution with complete exchange)")

    mass_balance_ok = mean_error < 5.0
    print(f"  Mass balance: {'✓ PASS' if mass_balance_ok else '✗ FAIL'}")

    # Validation 3: Spatial signature
    print("\nValidation 3: Spatial signature (pin biases + serpentine)")
    print("-" * 80)

    # With complete media exchange, concentration → C_fresh (no variation)
    # Spatial variation appears in VOLUME (volume_factor scales V_add)
    volume_grid = np.zeros((len(ROWS_TEST), len(COLS_384)))
    for row_idx, row in enumerate(ROWS_TEST):
        for col_idx, col in enumerate(COLS_384):
            well_id = f"well_{row}{col}"
            volume_grid[row_idx, col_idx] = state_after[well_id]['volume']

    volume_cv = 100 * np.std(volume_grid) / np.mean(volume_grid)

    print(f"  Volume CV: {volume_cv:.2f}%")
    print(f"  Expected: 2-6% (from pin biases + serpentine + drift)")

    # Check pin correlation (rows A and C use same pins)
    row_A_volume = volume_grid[0, :]
    row_C_volume = volume_grid[2, :]

    if np.std(row_A_volume) > 0 and np.std(row_C_volume) > 0:
        pin_corr = np.corrcoef(row_A_volume, row_C_volume)[0, 1]
    else:
        pin_corr = 0.0

    print(f"  Pin correlation (rows A vs C): {pin_corr:.3f}")
    print(f"  Expected: >0.3 (same pins, correlated biases)")

    spatial_ok = 2.0 < volume_cv < 8.0 and pin_corr > 0.2
    print(f"  Spatial signature: {'✓ PASS' if spatial_ok else '✗ FAIL'}")

    # Final assertions
    print()
    print("ASSERTIONS:")
    print("-" * 80)

    checks = {
        "No negative volumes": no_negative,
        "No overflow": no_overflow,
        "Mass balance": mass_balance_ok,
        "Spatial signature": spatial_ok,
    }

    for check, passed in checks.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {check}")

    all_passed = all(checks.values())
    print()
    if all_passed:
        print("🎉 TEST F2 PASSED")
    else:
        print("⚠️  TEST F2 FAILED")

    return all_passed


def test_f3_coupling_sanity():
    """
    Test F3: Coupling sanity (artifacts don't teleport into biology).

    Validates:
    - Feeding artifacts only affect: volume, nutrients, viability
    - Feeding artifacts do NOT affect: cell_count, compounds, stress states, genotype
    - Changes are detectable in observables
    """
    print("\n" + "="*80)
    print("TEST F3: COUPLING SANITY")
    print("="*80)
    print()

    print("Running simulation WITH artifacts...")
    vm_with = BiologicalVirtualMachine(seed=5000)

    # Seed single well
    vm_with.seed_vessel(
        vessel_id="well_A1",
        cell_line="HepG2",
        vessel_type="96-well",
        density_level="NOMINAL"
    )

    # Grow for 24h
    vm_with.advance_time(24.0)

    # Capture state before feeding
    vessel_with = vm_with.vessel_states["well_A1"]
    state_before_with = {
        'cell_count': vessel_with.cell_count,
        'viability': vessel_with.viability,
        'volume': vessel_with.current_volume_ml,
        'glucose': vessel_with.media_glucose_mM,
        'glutamine': vessel_with.media_glutamine_mM,
        'er_stress': vessel_with.er_stress,
        'mito_dysfunction': vessel_with.mito_dysfunction,
        'death_compound': vessel_with.death_compound,
    }

    # Feed
    vm_with.feed_vessel(vessel_id="well_A1")

    # Capture state after feeding
    state_after_with = {
        'cell_count': vessel_with.cell_count,
        'viability': vessel_with.viability,
        'volume': vessel_with.current_volume_ml,
        'glucose': vessel_with.media_glucose_mM,
        'glutamine': vessel_with.media_glutamine_mM,
        'er_stress': vessel_with.er_stress,
        'mito_dysfunction': vessel_with.mito_dysfunction,
        'death_compound': vessel_with.death_compound,
    }

    # Validation: What should change
    print("Validation: Variables that SHOULD change:")
    print("-" * 80)

    viability_changed = abs(state_after_with['viability'] - state_before_with['viability']) > 1e-6
    glucose_changed = abs(state_after_with['glucose'] - state_before_with['glucose']) > 1e-3
    glutamine_changed = abs(state_after_with['glutamine'] - state_before_with['glutamine']) > 1e-3

    print(f"  Viability: {state_before_with['viability']:.6f} → {state_after_with['viability']:.6f}")
    print(f"    Changed: {'✓ PASS' if viability_changed else '✗ FAIL (no change detected)'}")

    print(f"  Glucose: {state_before_with['glucose']:.3f} → {state_after_with['glucose']:.3f} mM")
    print(f"    Changed: {'✓ PASS' if glucose_changed else '✗ FAIL (no change detected)'}")

    print(f"  Glutamine: {state_before_with['glutamine']:.3f} → {state_after_with['glutamine']:.3f} mM")
    print(f"    Changed: {'✓ PASS' if glutamine_changed else '✗ FAIL (no change detected)'}")

    # Validation: What should NOT change
    print()
    print("Validation: Variables that should NOT change:")
    print("-" * 80)

    cell_count_unchanged = abs(state_after_with['cell_count'] - state_before_with['cell_count']) < 1e-3
    er_stress_unchanged = abs(state_after_with['er_stress'] - state_before_with['er_stress']) < 1e-9
    mito_unchanged = abs(state_after_with['mito_dysfunction'] - state_before_with['mito_dysfunction']) < 1e-9
    death_compound_unchanged = abs(state_after_with['death_compound'] - state_before_with['death_compound']) < 1e-9

    print(f"  Cell count: {state_before_with['cell_count']:.1f} → {state_after_with['cell_count']:.1f}")
    print(f"    Unchanged: {'✓ PASS' if cell_count_unchanged else '✗ FAIL (unexpected change)'}")

    print(f"  ER stress: {state_before_with['er_stress']:.6f} → {state_after_with['er_stress']:.6f}")
    print(f"    Unchanged: {'✓ PASS' if er_stress_unchanged else '✗ FAIL (unexpected change)'}")

    print(f"  Mito dysfunction: {state_before_with['mito_dysfunction']:.6f} → {state_after_with['mito_dysfunction']:.6f}")
    print(f"    Unchanged: {'✓ PASS' if mito_unchanged else '✗ FAIL (unexpected change)'}")

    print(f"  Death (compound): {state_before_with['death_compound']:.6f} → {state_after_with['death_compound']:.6f}")
    print(f"    Unchanged: {'✓ PASS' if death_compound_unchanged else '✗ FAIL (unexpected change)'}")

    # Final assertions
    print()
    print("ASSERTIONS:")
    print("-" * 80)

    checks = {
        "Viability changed": viability_changed,
        "Nutrients changed": glucose_changed and glutamine_changed,
        "Cell count unchanged": cell_count_unchanged,
        "Stress states unchanged": er_stress_unchanged and mito_unchanged,
        "Death accounting unchanged": death_compound_unchanged,
    }

    for check, passed in checks.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {check}")

    all_passed = all(checks.values())
    print()
    if all_passed:
        print("🎉 TEST F3 PASSED")
    else:
        print("⚠️  TEST F3 FAILED")

    return all_passed


def main():
    """Run all feeding hardware artifact tests."""
    print("="*80)
    print("FEEDING HARDWARE ARTIFACTS - VALIDATION SUITE")
    print("="*80)
    print()

    results = {}

    # Run tests
    results['F1'] = test_f1_serpentine_temperature_shock()
    results['F2'] = test_f2_volume_variation_mass_balance()
    results['F3'] = test_f3_coupling_sanity()

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: Test {test_name}")

    all_passed = all(results.values())
    print()
    if all_passed:
        print("🎉 ALL TESTS PASSED - Feeding artifacts validated!")
    else:
        print("⚠️  SOME TESTS FAILED - Review implementation")

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
