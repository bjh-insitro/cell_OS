"""
Tests for mitochondrial dysfunction latent state.

These tests verify morphology-first, death-later behavior and clean separation
from other latents (ER stress).
"""

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_mito_dysfunction_morphology_first():
    """
    Test that mito dysfunction shifts morphology BEFORE death hazard kicks in.

    Setup: Low dose mitochondrial stress compound (e.g., CCCP at 0.25× IC50)
    Expected:
    - At 12h: mito morphology drops 20-30%, viability drops <10%
    - This creates "readouts disagree" wedge (mito signal down, cell still mostly viable)
    """
    vm = BiologicalVirtualMachine(seed=0)
    vm.seed_vessel("test", "A549", initial_count=1e6, capacity=1e7, initial_viability=0.98)

    # CCCP is a mitochondrial uncoupler (stress_axis="mitochondrial")
    # Use 0.25× IC50 to see morphology shift without overwhelming death
    vm.treat_with_compound("test", "cccp", dose_uM=0.5)  # IC50 ~2 µM, so 0.25×

    # Advance 12h (enough for latent induction, not enough for death threshold)
    vm.advance_time(12.0)

    vessel = vm.vessel_states["test"]

    # Get morphology readout
    morph_result = vm.cell_painting_assay("test")
    mito_signal = morph_result['morphology']['mito']
    baseline_mito = vm.thalamus_params['baseline_morphology']['A549']['mito']

    # Mito signal should drop significantly (20-40% reduction)
    mito_change = (mito_signal - baseline_mito) / baseline_mito
    print(f"Mito signal change at 12h: {mito_change:.1%}")
    print(f"Viability at 12h: {vessel.viability:.3f}")
    print(f"Mito dysfunction latent: {vessel.mito_dysfunction:.3f}")
    print(f"Death_mito_dysfunction: {vessel.death_mito_dysfunction:.3f}")

    # Morphology should shift early (mito signal drops)
    assert mito_change < -0.15, (
        f"Mito morphology should drop by >15% at 12h: {mito_change:.1%}"
    )

    # Viability should remain mostly intact (morphology-first)
    assert vessel.viability > 0.90, (
        f"Viability should remain >90% at 12h: {vessel.viability:.3f}"
    )

    # Mito dysfunction latent should be elevated
    assert vessel.mito_dysfunction > 0.25, (
        f"Mito dysfunction latent should be >0.25 at 12h: {vessel.mito_dysfunction:.3f}"
    )

    # Death hazard should be minimal (below theta=0.6)
    assert vessel.death_mito_dysfunction < 0.05, (
        f"Mito death should be <5% at 12h: {vessel.death_mito_dysfunction:.3f}"
    )

    print("✓ PASSED: Mito dysfunction shows morphology-first behavior")


def test_mito_dysfunction_persistent_vs_transient():
    """
    Test that washout reverses mito dysfunction (latent decays).

    Setup: Two vessels, both exposed to CCCP for 12h
    - Vessel A: continuous exposure (24h total)
    - Vessel B: washout at 12h, then 12h recovery

    Expected:
    - Vessel A: mito dysfunction stays high, death accumulates
    - Vessel B: mito dysfunction decays, viability stabilizes
    """
    vm_persistent = BiologicalVirtualMachine(seed=0)
    vm_transient = BiologicalVirtualMachine(seed=0)

    # Seed identical vessels
    vm_persistent.seed_vessel("persistent", "A549", 1e6, capacity=1e7, initial_viability=0.98)
    vm_transient.seed_vessel("transient", "A549", 1e6, capacity=1e7, initial_viability=0.98)

    # Apply CCCP to both
    vm_persistent.treat_with_compound("persistent", "cccp", dose_uM=1.0)
    vm_transient.treat_with_compound("transient", "cccp", dose_uM=1.0)

    # Advance 12h
    vm_persistent.advance_time(12.0)
    vm_transient.advance_time(12.0)

    # Washout transient vessel
    vm_transient.washout_compound("transient", "cccp")

    # Advance another 12h (24h total)
    vm_persistent.advance_time(12.0)
    vm_transient.advance_time(12.0)

    vessel_persistent = vm_persistent.vessel_states["persistent"]
    vessel_transient = vm_transient.vessel_states["transient"]

    print(f"Persistent mito dysfunction at 24h: {vessel_persistent.mito_dysfunction:.3f}")
    print(f"Transient mito dysfunction at 24h: {vessel_transient.mito_dysfunction:.3f}")
    print(f"Persistent viability: {vessel_persistent.viability:.3f}")
    print(f"Transient viability: {vessel_transient.viability:.3f}")
    print(f"Persistent death_mito: {vessel_persistent.death_mito_dysfunction:.3f}")
    print(f"Transient death_mito: {vessel_transient.death_mito_dysfunction:.3f}")

    # Transient should show decay (latent drops after washout)
    assert vessel_transient.mito_dysfunction < vessel_persistent.mito_dysfunction, (
        f"Transient mito dysfunction should be lower after washout: "
        f"transient={vessel_transient.mito_dysfunction:.3f} vs persistent={vessel_persistent.mito_dysfunction:.3f}"
    )

    # Latent decay should be substantial (persistent continues to rise, transient decays)
    # With k_off=0.05, decay half-life is ~14h, so 12h should show ~40% decay from peak
    assert vessel_transient.mito_dysfunction < vessel_persistent.mito_dysfunction * 0.6, (
        f"Transient mito dysfunction should decay to <60% of persistent: "
        f"transient={vessel_transient.mito_dysfunction:.3f} vs persistent={vessel_persistent.mito_dysfunction:.3f}"
    )

    # Note: At this dose/time, death threshold (theta=0.6) not reached yet
    # This is correct morphology-first behavior: latent rises, morphology shifts, death comes later

    print("✓ PASSED: Washout reverses mito dysfunction")


def test_mito_dysfunction_orthogonal_to_er_stress():
    """
    Test that ER stress and mito dysfunction are independent (different axes).

    Setup: Two vessels
    - Vessel A: ER stressor (tunicamycin)
    - Vessel B: Mito stressor (CCCP)

    Expected:
    - Vessel A: ER stress high, mito dysfunction low
    - Vessel B: Mito dysfunction high, ER stress low
    """
    vm = BiologicalVirtualMachine(seed=0)
    vm.seed_vessel("er_vessel", "A549", 1e6, capacity=1e7, initial_viability=0.98)
    vm.seed_vessel("mito_vessel", "A549", 1e6, capacity=1e7, initial_viability=0.98)

    # Apply ER stressor to vessel A
    vm.treat_with_compound("er_vessel", "tunicamycin", dose_uM=0.25)

    # Apply mito stressor to vessel B
    vm.treat_with_compound("mito_vessel", "cccp", dose_uM=1.0)

    # Advance 12h
    vm.advance_time(12.0)

    vessel_er = vm.vessel_states["er_vessel"]
    vessel_mito = vm.vessel_states["mito_vessel"]

    print(f"ER vessel: er_stress={vessel_er.er_stress:.3f}, mito_dysfunction={vessel_er.mito_dysfunction:.3f}")
    print(f"Mito vessel: er_stress={vessel_mito.er_stress:.3f}, mito_dysfunction={vessel_mito.mito_dysfunction:.3f}")

    # ER vessel should have ER stress, not mito dysfunction
    assert vessel_er.er_stress > 0.3, (
        f"ER vessel should have ER stress: {vessel_er.er_stress:.3f}"
    )
    assert vessel_er.mito_dysfunction < 0.1, (
        f"ER vessel should have minimal mito dysfunction: {vessel_er.mito_dysfunction:.3f}"
    )

    # Mito vessel should have mito dysfunction, not ER stress
    assert vessel_mito.mito_dysfunction > 0.3, (
        f"Mito vessel should have mito dysfunction: {vessel_mito.mito_dysfunction:.3f}"
    )
    assert vessel_mito.er_stress < 0.1, (
        f"Mito vessel should have minimal ER stress: {vessel_mito.er_stress:.3f}"
    )

    print("✓ PASSED: ER stress and mito dysfunction are orthogonal")


def test_mito_dysfunction_atp_signal():
    """
    Test that ATP signal decreases with mito dysfunction (second readout).

    Setup: Apply CCCP, measure ATP signal at different timepoints
    Expected: ATP signal drops as mito dysfunction increases
    """
    vm = BiologicalVirtualMachine(seed=0)
    vm.seed_vessel("test", "A549", 1e6, capacity=1e7, initial_viability=0.98)

    # Baseline ATP (no compound)
    atp_baseline = vm.atp_viability_assay("test")['atp_signal']

    # Apply CCCP
    vm.treat_with_compound("test", "cccp", dose_uM=1.0)
    vm.advance_time(12.0)

    # ATP after 12h exposure
    atp_12h = vm.atp_viability_assay("test")['atp_signal']

    vessel = vm.vessel_states["test"]

    print(f"ATP baseline: {atp_baseline:.1f}")
    print(f"ATP at 12h: {atp_12h:.1f}")
    print(f"Mito dysfunction: {vessel.mito_dysfunction:.3f}")

    # ATP should drop with mito dysfunction
    atp_change = (atp_12h - atp_baseline) / atp_baseline
    assert atp_change < -0.15, (
        f"ATP signal should drop by >15%: {atp_change:.1%}"
    )

    # ATP drop should correlate with mito dysfunction latent
    assert vessel.mito_dysfunction > 0.3, (
        f"Mito dysfunction should be >0.3: {vessel.mito_dysfunction:.3f}"
    )

    print("✓ PASSED: ATP signal drops with mito dysfunction")


def test_mito_dysfunction_monotone_invariant():
    """
    Test that mito dysfunction doesn't increase without mitochondrial compounds.

    This catches sign errors in dynamics.
    """
    vm = BiologicalVirtualMachine(seed=0)
    vm.seed_vessel("test", "A549", 1e6, capacity=1e7, initial_viability=0.98)

    # Apply CCCP, build up mito dysfunction
    vm.treat_with_compound("test", "cccp", dose_uM=1.0)
    vm.advance_time(12.0)

    vessel = vm.vessel_states["test"]
    mito_before = vessel.mito_dysfunction

    print(f"Mito dysfunction before washout: {mito_before:.3f}")

    # Washout compound
    vm.washout_compound("test", "cccp")

    # Advance time (mito dysfunction should decay, not increase)
    vm.advance_time(12.0)

    mito_after = vessel.mito_dysfunction

    print(f"Mito dysfunction after washout: {mito_after:.3f}")

    # Monotone invariant: no compounds → mito dysfunction should not increase
    assert mito_after <= mito_before + 1e-9, (
        f"Mito dysfunction increased without compounds: {mito_before:.3f} → {mito_after:.3f}"
    )

    # Should decay
    assert mito_after < mito_before * 0.8, (
        f"Mito dysfunction should decay significantly: {mito_before:.3f} → {mito_after:.3f}"
    )

    print("✓ PASSED: Mito dysfunction decays without compounds (monotone invariant)")
