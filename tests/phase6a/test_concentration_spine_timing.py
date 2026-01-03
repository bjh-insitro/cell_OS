"""
Phase 6a: Concentration spine timing exploit detection.

Tests whether evaporation vs biology timing creates dt-dependent behavior.

The crack: If biology reads POST-evaporation concentrations but integrates
over the full interval, it applies the wrong concentration trajectory.

Example:
- t0: dose = 1.0 µM
- t1: dose = 1.1 µM (after evaporation concentrates it)
- Fine steps: biology sees [1.0, 1.02, 1.04, ..., 1.1] gradually
- Coarse step: biology sees 1.1 and applies it to entire interval

Expected behavior (dt-independent):
- Biology should integrate using the concentration trajectory c(t) over [t0,t1]
- Not just c(t1) applied retroactively

Failure signature:
- Coarse steps produce MORE stress/damage than fine steps (phantom high dose)
- Or LESS if the snapshot timing is reversed
"""

import pytest
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_evaporation_schedule_invariance_stress_induction():
    """
    Test: Stress induction should be dt-independent despite evaporation.

    Attack 2 (stale snapshot exploit):
    - Treat at t=0 with compound that induces stress
    - Compare stress after 24h using different schedules
    - If biology reads post-evap concentration at interval end, coarse steps
      will apply higher concentration retroactively to whole interval

    Schedules:
    - Fine: 24 × 1h (sees gradual concentration increase)
    - Coarse: 1 × 24h (sees final concentration, applies to whole interval)
    """
    compound = "tunicamycin"  # ER stress compound
    dose_uM = 1.0  # Moderate dose
    duration = 24.0  # 24h exposure

    # ===== Fine schedule (24 × 1h) =====
    vm_fine = BiologicalVirtualMachine(seed=42)
    vm_fine.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    vm_fine.treat_with_compound("Plate1_A01", compound, dose_uM=dose_uM)

    # Track concentration and stress trajectory
    conc_trajectory_fine = [vm_fine.vessel_states["Plate1_A01"].compounds.get(compound, 0.0)]
    stress_trajectory_fine = [vm_fine.vessel_states["Plate1_A01"].er_stress]

    for _ in range(int(duration)):
        vm_fine.advance_time(1.0)
        conc_trajectory_fine.append(vm_fine.vessel_states["Plate1_A01"].compounds.get(compound, 0.0))
        stress_trajectory_fine.append(vm_fine.vessel_states["Plate1_A01"].er_stress)

    final_conc_fine = conc_trajectory_fine[-1]
    final_stress_fine = stress_trajectory_fine[-1]
    final_damage_fine = vm_fine.vessel_states["Plate1_A01"].er_damage

    # ===== Coarse schedule (1 × 24h) =====
    vm_coarse = BiologicalVirtualMachine(seed=42)
    vm_coarse.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    vm_coarse.treat_with_compound("Plate1_A01", compound, dose_uM=dose_uM)

    initial_conc_coarse = vm_coarse.vessel_states["Plate1_A01"].compounds.get(compound, 0.0)

    # Single 24h step
    vm_coarse.advance_time(duration)

    final_conc_coarse = vm_coarse.vessel_states["Plate1_A01"].compounds.get(compound, 0.0)
    final_stress_coarse = vm_coarse.vessel_states["Plate1_A01"].er_stress
    final_damage_coarse = vm_coarse.vessel_states["Plate1_A01"].er_damage

    # ===== Analysis =====
    print(f"\n=== Evaporation Schedule Invariance Test (Stress Induction) ===")
    print(f"Setup: {compound} {dose_uM}µM for {duration}h")
    print()
    print(f"Fine schedule (24 × 1h):")
    print(f"  Initial concentration: {conc_trajectory_fine[0]:.4f} µM")
    print(f"  Final concentration:   {final_conc_fine:.4f} µM (evaporated)")
    print(f"  Mean concentration:    {sum(conc_trajectory_fine) / len(conc_trajectory_fine):.4f} µM")
    print(f"  Final ER stress:       {final_stress_fine:.4f}")
    print(f"  Final ER damage:       {final_damage_fine:.4f}")
    print()
    print(f"Coarse schedule (1 × 24h):")
    print(f"  Initial concentration: {initial_conc_coarse:.4f} µM")
    print(f"  Final concentration:   {final_conc_coarse:.4f} µM (evaporated)")
    print(f"  Final ER stress:       {final_stress_coarse:.4f}")
    print(f"  Final ER damage:       {final_damage_coarse:.4f}")
    print()

    # Calculate differences
    stress_diff = abs(final_stress_coarse - final_stress_fine)
    damage_diff = abs(final_damage_coarse - final_damage_fine)
    stress_ratio = final_stress_coarse / final_stress_fine if final_stress_fine > 0 else 1.0
    damage_ratio = final_damage_coarse / final_damage_fine if final_damage_fine > 0 else 1.0

    print(f"Differences:")
    print(f"  Stress diff:  {stress_diff:.4f} (ratio: {stress_ratio:.4f})")
    print(f"  Damage diff:  {damage_diff:.4f} (ratio: {damage_ratio:.4f})")
    print()

    # ===== Diagnostic: Check concentration increase from evaporation =====
    evap_increase = (final_conc_fine - conc_trajectory_fine[0]) / conc_trajectory_fine[0]
    print(f"Evaporation effect:")
    print(f"  Concentration increase: {evap_increase * 100:.1f}% over {duration}h")
    print()

    # ===== Assertions =====
    # Tolerance: Allow ±5% difference in stress/damage
    # But systematic bias (coarse higher) indicates phantom concentration
    tolerance_stress = 0.05  # ±5% absolute stress difference
    tolerance_damage = 0.05  # ±5% absolute damage difference

    # If evaporation increases concentration by ~10%, and coarse step sees final
    # concentration retroactively, we expect coarse to produce MORE stress/damage
    if stress_ratio > 1.0 + tolerance_stress:
        pytest.fail(
            f"PHANTOM CONCENTRATION EXPLOIT: Coarse schedule produces {stress_ratio:.3f}× more stress "
            f"than fine schedule. This indicates biology reads POST-evaporation concentration "
            f"and applies it retroactively to entire interval [t0, t1). Biology should integrate "
            f"using concentration trajectory c(t), not just c(t1)."
        )

    if damage_ratio > 1.0 + tolerance_damage:
        pytest.fail(
            f"PHANTOM CONCENTRATION EXPLOIT: Coarse schedule produces {damage_ratio:.3f}× more damage "
            f"than fine schedule. Concentration: fine_mean={sum(conc_trajectory_fine) / len(conc_trajectory_fine):.4f}, "
            f"coarse_final={final_conc_coarse:.4f}. Biology applies wrong concentration trajectory."
        )

    # If differences are within tolerance
    if stress_diff <= tolerance_stress and damage_diff <= tolerance_damage:
        print(f"✓ Concentration spine timing is dt-independent")
    else:
        print(f"⚠ Differences exceed tolerance but no systematic exploit detected")


def test_concentration_trajectory_first_interval():
    """
    Test: First interval after treatment should be dt-independent.

    This is the most sensitive test - immediately after treatment, there's no
    evaporation history to integrate, so any dt-dependence is pure timing artifact.

    Compare:
    - 1h step: sees concentration at t=1h
    - 6h step: sees concentration at t=6h
    - 12h step: sees concentration at t=12h

    If biology uses interval-average concentration, all should produce similar
    cumulative stress. If biology uses endpoint concentration, longer steps will
    see higher (evaporated) concentration retroactively.
    """
    compound = "tunicamycin"
    dose_uM = 1.0
    test_durations = [1.0, 6.0, 12.0]  # Different first-step sizes

    results = []

    for dt in test_durations:
        vm = BiologicalVirtualMachine(seed=42)
        vm.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

        vm.treat_with_compound("Plate1_A01", compound, dose_uM=dose_uM)

        initial_conc = vm.vessel_states["Plate1_A01"].compounds.get(compound, 0.0)

        # Single step of varying size
        vm.advance_time(dt)

        final_conc = vm.vessel_states["Plate1_A01"].compounds.get(compound, 0.0)
        final_stress = vm.vessel_states["Plate1_A01"].er_stress
        final_damage = vm.vessel_states["Plate1_A01"].er_damage

        # Normalize by time to get "per-hour" rates
        stress_per_hour = final_stress / dt
        damage_per_hour = final_damage / dt

        results.append({
            'dt': dt,
            'initial_conc': initial_conc,
            'final_conc': final_conc,
            'evap_pct': (final_conc - initial_conc) / initial_conc * 100,
            'final_stress': final_stress,
            'final_damage': final_damage,
            'stress_per_hour': stress_per_hour,
            'damage_per_hour': damage_per_hour,
        })

    print(f"\n=== First Interval Concentration Trajectory Test ===")
    print(f"Setup: {compound} {dose_uM}µM, varying first-step duration")
    print()
    for r in results:
        print(f"dt={r['dt']:.1f}h:")
        print(f"  Concentration: {r['initial_conc']:.4f} → {r['final_conc']:.4f} µM (evap: {r['evap_pct']:+.1f}%)")
        print(f"  Stress:        {r['final_stress']:.4f} ({r['stress_per_hour']:.4f} /h)")
        print(f"  Damage:        {r['final_damage']:.4f} ({r['damage_per_hour']:.4f} /h)")
        print()

    # ===== Analysis =====
    # If biology uses interval-average concentration, stress_per_hour should be similar
    # If biology uses endpoint concentration, longer steps see higher evaporated concentration

    stress_per_hour_values = [r['stress_per_hour'] for r in results]
    damage_per_hour_values = [r['damage_per_hour'] for r in results]

    stress_per_hour_std = (max(stress_per_hour_values) - min(stress_per_hour_values)) / min(stress_per_hour_values)
    damage_per_hour_std = (max(damage_per_hour_values) - min(damage_per_hour_values)) / max(min(damage_per_hour_values), 1e-6)  # Avoid divide-by-zero

    print(f"Relative variation:")
    print(f"  Stress /h: {stress_per_hour_std * 100:.1f}% (range: {min(stress_per_hour_values):.4f}-{max(stress_per_hour_values):.4f})")
    print(f"  Damage /h: {damage_per_hour_std * 100:.1f}% (range: {min(damage_per_hour_values):.4f}-{max(damage_per_hour_values):.4f})")
    print()

    # ===== Assertions =====
    # Tolerance: ±15% variation in per-hour rates
    # (Accounts for nonlinear dynamics, but systematic trend indicates exploit)
    tolerance = 0.15

    if stress_per_hour_std > tolerance:
        # Check if it's a monotonic trend (longer dt → higher rate)
        if stress_per_hour_values[-1] > stress_per_hour_values[0] * (1 + tolerance):
            pytest.fail(
                f"CONCENTRATION TRAJECTORY EXPLOIT: Longer first-step produces {stress_per_hour_values[-1] / stress_per_hour_values[0]:.3f}× "
                f"higher stress per hour. Stress/h at dt=12h: {stress_per_hour_values[-1]:.4f}, "
                f"at dt=1h: {stress_per_hour_values[0]:.4f}. Biology likely reads endpoint concentration "
                f"(post-evaporation) and applies it to entire interval."
            )
        else:
            print(f"⚠ High variation ({stress_per_hour_std * 100:.1f}%) but no monotonic exploit trend")
    else:
        print(f"✓ First-interval stress induction is dt-independent ({stress_per_hour_std * 100:.1f}% variation)")

    if damage_per_hour_std > tolerance:
        if damage_per_hour_values[0] > 1e-6 and damage_per_hour_values[-1] > damage_per_hour_values[0] * (1 + tolerance):
            pytest.fail(
                f"CONCENTRATION TRAJECTORY EXPLOIT: Longer first-step produces {damage_per_hour_values[-1] / damage_per_hour_values[0]:.3f}× "
                f"higher damage per hour. Damage/h at dt=12h: {damage_per_hour_values[-1]:.4f}, "
                f"at dt=1h: {damage_per_hour_values[0]:.4f}."
            )
        else:
            print(f"⚠ High damage variation ({damage_per_hour_std * 100:.1f}%) - needs investigation")


def test_washout_boundary_ghost_compound():
    """
    Test: Washout should cleanly zero concentration at boundary.

    Attack 3 (ghost compound):
    - Treat at t=0
    - Run 6h
    - Washout
    - Run 24h more

    If washout timing is fuzzy relative to step boundaries, coarse steps might
    see "ghost compound" where concentration lingers when it shouldn't.
    """
    compound = "tunicamycin"
    dose_uM = 1.0

    # ===== Fine schedule (washout at exact boundary) =====
    vm_fine = BiologicalVirtualMachine(seed=42)
    vm_fine.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    vm_fine.treat_with_compound("Plate1_A01", compound, dose_uM=dose_uM)

    # Run 6h in 1h steps
    for _ in range(6):
        vm_fine.advance_time(1.0)

    conc_before_washout_fine = vm_fine.vessel_states["Plate1_A01"].compounds.get(compound, 0.0)
    stress_before_washout_fine = vm_fine.vessel_states["Plate1_A01"].er_stress

    # Washout
    vm_fine.washout_compound("Plate1_A01")

    conc_after_washout_fine = vm_fine.vessel_states["Plate1_A01"].compounds.get(compound, 0.0)

    # Run 24h post-washout in 1h steps
    stress_trajectory_post_washout_fine = []
    for _ in range(24):
        vm_fine.advance_time(1.0)
        stress_trajectory_post_washout_fine.append(vm_fine.vessel_states["Plate1_A01"].er_stress)

    final_stress_fine = stress_trajectory_post_washout_fine[-1]

    # ===== Coarse schedule (12h steps around washout) =====
    vm_coarse = BiologicalVirtualMachine(seed=42)
    vm_coarse.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    vm_coarse.treat_with_compound("Plate1_A01", compound, dose_uM=dose_uM)

    # Run 6h (coarse step)
    vm_coarse.advance_time(6.0)

    conc_before_washout_coarse = vm_coarse.vessel_states["Plate1_A01"].compounds.get(compound, 0.0)
    stress_before_washout_coarse = vm_coarse.vessel_states["Plate1_A01"].er_stress

    # Washout
    vm_coarse.washout_compound("Plate1_A01")

    conc_after_washout_coarse = vm_coarse.vessel_states["Plate1_A01"].compounds.get(compound, 0.0)

    # Run 24h post-washout in 12h steps
    for _ in range(2):
        vm_coarse.advance_time(12.0)

    final_stress_coarse = vm_coarse.vessel_states["Plate1_A01"].er_stress

    # ===== Analysis =====
    print(f"\n=== Washout Boundary Ghost Compound Test ===")
    print(f"Setup: {compound} {dose_uM}µM for 6h, washout, then 24h recovery")
    print()
    print(f"Fine schedule (1h steps):")
    print(f"  Before washout: conc={conc_before_washout_fine:.4f} µM, stress={stress_before_washout_fine:.4f}")
    print(f"  After washout:  conc={conc_after_washout_fine:.4f} µM")
    print(f"  Final stress (30h): {final_stress_fine:.4f}")
    print()
    print(f"Coarse schedule (6h/12h steps):")
    print(f"  Before washout: conc={conc_before_washout_coarse:.4f} µM, stress={stress_before_washout_coarse:.4f}")
    print(f"  After washout:  conc={conc_after_washout_coarse:.4f} µM")
    print(f"  Final stress (30h): {final_stress_coarse:.4f}")
    print()

    # ===== Assertions =====
    # 1. Concentration should be zero (or near-zero) after washout
    assert conc_after_washout_fine < 0.01, \
        f"Fine schedule: concentration after washout should be ~0, got {conc_after_washout_fine:.4f}"

    assert conc_after_washout_coarse < 0.01, \
        f"Coarse schedule: concentration after washout should be ~0, got {conc_after_washout_coarse:.4f}"

    # 2. Final stress should be similar across schedules
    stress_diff = abs(final_stress_coarse - final_stress_fine)
    tolerance = 0.05

    print(f"Final stress difference: {stress_diff:.4f} (tolerance: {tolerance})")

    if stress_diff > tolerance:
        if final_stress_coarse > final_stress_fine + tolerance:
            pytest.fail(
                f"GHOST COMPOUND EXPLOIT: Coarse schedule has {stress_diff:.4f} higher stress after washout. "
                f"This suggests concentration lingered when it shouldn't (ghost compound). "
                f"Washout boundary may not be cleanly handled across coarse timesteps."
            )
        else:
            print(f"⚠ Coarse stress is lower (diff: {stress_diff:.4f}). Possible over-decay.")
    else:
        print(f"✓ Washout boundary is dt-independent (stress diff: {stress_diff:.4f})")
