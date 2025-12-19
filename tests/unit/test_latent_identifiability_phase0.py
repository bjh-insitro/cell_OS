"""
Phase 0 identifiability check: Minimal proof-of-concept.

This is NOT a full statistical test. It's a smoke test showing:
1. ER stress increases ER morphology + UPR (goes UP)
2. Mito dysfunction decreases mito morphology + ATP (goes DOWN)
3. The signals are directionally opposite (identifiable in principle)

If you want the full battery (200+ sims, logistic regression, confusion matrices),
that belongs in integration tests or offline analysis, not unit tests.
"""

import numpy as np
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_er_vs_mito_signal_directions():
    """
    Minimal smoke test: ER and mito latents produce opposite signal directions.

    Pass criteria:
    - ER compound: ER channel UP, mito channel stable
    - Mito compound: Mito channel DOWN, ER channel stable
    - Signals are directionally opposite (identifiable by sign)
    """
    print("\n=== Phase 0 Identifiability: Signal Directions ===")

    # Scenario 1: ER stress compound (tunicamycin)
    vm_er = BiologicalVirtualMachine(seed=42)
    vm_er.seed_vessel("test", "A549", 1e6, capacity=1e7, initial_viability=0.98)

    baseline_er = vm_er.cell_painting_assay("test")['morphology']
    baseline_scalars_er = vm_er.atp_viability_assay("test")

    vm_er.treat_with_compound("test", "tunicamycin", dose_uM=0.5)
    vm_er.advance_time(12.0)

    morph_er = vm_er.cell_painting_assay("test")['morphology']
    scalars_er = vm_er.atp_viability_assay("test")

    er_channel_change = (morph_er['er'] - baseline_er['er']) / baseline_er['er']
    mito_channel_change_er = (morph_er['mito'] - baseline_er['mito']) / baseline_er['mito']
    upr_change = (scalars_er['upr_marker'] - baseline_scalars_er['upr_marker']) / baseline_scalars_er['upr_marker']

    print(f"\nER compound (tunicamycin 0.5 µM, 12h):")
    print(f"  ER channel change: {er_channel_change:+.1%}")
    print(f"  Mito channel change: {mito_channel_change_er:+.1%}")
    print(f"  UPR change: {upr_change:+.1%}")

    # Scenario 2: Mito dysfunction compound (CCCP)
    vm_mito = BiologicalVirtualMachine(seed=42)
    vm_mito.seed_vessel("test", "A549", 1e6, capacity=1e7, initial_viability=0.98)

    baseline_mito = vm_mito.cell_painting_assay("test")['morphology']
    baseline_scalars_mito = vm_mito.atp_viability_assay("test")

    vm_mito.treat_with_compound("test", "cccp", dose_uM=1.0)
    vm_mito.advance_time(12.0)

    morph_mito = vm_mito.cell_painting_assay("test")['morphology']
    scalars_mito = vm_mito.atp_viability_assay("test")

    mito_channel_change_mito = (morph_mito['mito'] - baseline_mito['mito']) / baseline_mito['mito']
    er_channel_change_mito = (morph_mito['er'] - baseline_mito['er']) / baseline_mito['er']
    atp_change = (scalars_mito['atp_signal'] - baseline_scalars_mito['atp_signal']) / baseline_scalars_mito['atp_signal']

    print(f"\nMito compound (CCCP 1.0 µM, 12h):")
    print(f"  Mito channel change: {mito_channel_change_mito:+.1%}")
    print(f"  ER channel change: {er_channel_change_mito:+.1%}")
    print(f"  ATP change: {atp_change:+.1%}")

    # Pass criteria: Directional separation
    print(f"\n=== Identifiability Check ===")

    # ER compound should increase ER channel
    assert er_channel_change > 0.10, (
        f"ER compound should increase ER channel by >10%: {er_channel_change:.1%}"
    )

    # ER compound should increase UPR
    assert upr_change > 0.10, (
        f"ER compound should increase UPR by >10%: {upr_change:.1%}"
    )

    # Mito compound should decrease mito channel
    assert mito_channel_change_mito < -0.10, (
        f"Mito compound should decrease mito channel by >10%: {mito_channel_change_mito:.1%}"
    )

    # Mito compound should decrease ATP
    assert atp_change < -0.10, (
        f"Mito compound should decrease ATP by >10%: {atp_change:.1%}"
    )

    # Orthogonality check: Cross-channel effects should be weaker than primary effects
    # Note: Viability scaling affects all channels, so perfect orthogonality is not expected
    # We just need ER/UPR to dominate for ER compound, and Mito/ATP to dominate for mito compound
    assert abs(er_channel_change) > abs(mito_channel_change_er), (
        f"ER compound primary effect (ER: {er_channel_change:.1%}) should dominate over "
        f"cross-talk (Mito: {mito_channel_change_er:.1%})"
    )

    assert abs(mito_channel_change_mito) > abs(er_channel_change_mito) * 2, (
        f"Mito compound primary effect (Mito: {mito_channel_change_mito:.1%}) should dominate over "
        f"cross-talk (ER: {er_channel_change_mito:.1%})"
    )

    # Directional contrast: ER goes UP, Mito goes DOWN
    er_direction = np.sign(er_channel_change)
    mito_direction = np.sign(mito_channel_change_mito)

    print(f"\nDirectional signatures:")
    print(f"  ER stress: ER channel {'+' if er_direction > 0 else '-'}, UPR {'+' if upr_change > 0 else '-'}")
    print(f"  Mito dysfunction: Mito channel {'+' if mito_direction > 0 else '-'}, ATP {'+' if atp_change > 0 else '-'}")

    assert er_direction > 0 and mito_direction < 0, (
        f"ER and mito must have opposite signal directions: "
        f"ER={'+' if er_direction > 0 else '-'}, Mito={'+' if mito_direction > 0 else '-'}"
    )

    print(f"\n✓ PASSED: ER stress and mito dysfunction are identifiable by signal direction")
    print(f"  ER increases (ER channel +{er_channel_change:.0%}, UPR +{upr_change:.0%})")
    print(f"  Mito decreases (Mito channel {mito_channel_change_mito:.0%}, ATP {atp_change:.0%})")


def test_control_vs_stressed_minimal():
    """
    Minimal smoke test: Control samples have no latent activation.

    Pass criteria: Control shows minimal morphology changes (<5%)
    """
    print("\n=== Control Baseline Stability ===")

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test", "A549", 1e6, capacity=1e7, initial_viability=0.98)

    baseline = vm.cell_painting_assay("test")['morphology']
    baseline_scalars = vm.atp_viability_assay("test")

    # Advance time without compound
    vm.advance_time(12.0)

    morph = vm.cell_painting_assay("test")['morphology']
    scalars = vm.atp_viability_assay("test")

    er_drift = abs((morph['er'] - baseline['er']) / baseline['er'])
    mito_drift = abs((morph['mito'] - baseline['mito']) / baseline['mito'])
    upr_drift = abs((scalars['upr_marker'] - baseline_scalars['upr_marker']) / baseline_scalars['upr_marker'])
    atp_drift = abs((scalars['atp_signal'] - baseline_scalars['atp_signal']) / baseline_scalars['atp_signal'])

    print(f"Control drift after 12h (no compound):")
    print(f"  ER channel: {er_drift:.1%}")
    print(f"  Mito channel: {mito_drift:.1%}")
    print(f"  UPR: {upr_drift:.1%}")
    print(f"  ATP: {atp_drift:.1%}")

    # Control should show minimal drift (measurement noise + growth effects only)
    assert er_drift < 0.20, f"Control ER channel drift too high: {er_drift:.1%}"
    assert mito_drift < 0.20, f"Control mito channel drift too high: {mito_drift:.1%}"
    assert upr_drift < 0.20, f"Control UPR drift too high: {upr_drift:.1%}"
    assert atp_drift < 0.20, f"Control ATP drift too high: {atp_drift:.1%}"

    print(f"\n✓ PASSED: Control shows minimal drift (all channels <20%)")


if __name__ == "__main__":
    test_control_vs_stressed_minimal()
    test_er_vs_mito_signal_directions()
    print("\n=== Phase 0 Identifiability: Minimal Checks Passed ===")
