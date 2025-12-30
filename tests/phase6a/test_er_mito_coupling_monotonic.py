"""
Test: ER → Mito susceptibility coupling is monotonic.

Validates that ER damage increases mito dysfunction susceptibility continuously.

Design (from pilot):
- CCCP 0.7 µM (mid-slope: median=0.384, IQR=[0.352, 0.425])
  WHY 0.7 µM: Pilot identified this as the sensitive operating point where
  mito_dysfunction ≈ 0.35-0.45 (mid-slope regime). Lower doses are too weak
  to detect coupling signal; higher doses saturate and mask the effect.
- ER damage levels: 0.0, 0.3, 0.6 (span sensitive region)
- Assert: Spearman ρ > 0.6

CI behavior:
- Default CI: Runs these tests (fast, deterministic)
- Not marked @pytest.mark.realism (unit/integration hybrid)
"""

import pytest
import numpy as np
from scipy.stats import spearmanr
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.run_context import RunContext


def test_er_damage_increases_mito_susceptibility_monotonically():
    """
    ER damage should monotonically increase mito dysfunction (Spearman ρ > 0.6).

    Protocol:
    1. Prime ER damage with tunicamycin (0, 1, 3 µM × 24h)
    2. Washout
    3. Expose to CCCP 0.7 µM × 12h (mid-slope dose from pilot)
    4. Measure mito_dysfunction
    """
    # ER priming doses
    tunicamycin_doses = [0.0, 1.0, 3.0]  # µM

    mito_dysfunction_values = []
    er_damage_values = []

    for tun_dose in tunicamycin_doses:
        vm = BiologicalVirtualMachine()
        vm.run_context = RunContext.sample(seed=42)
        vm.rng_assay = np.random.default_rng(1042)
        vm.rng_biology = np.random.default_rng(2042)
        vm._load_cell_thalamus_params()

        vessel_id = "P1_A01"
        vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)

        # Prime ER damage
        if tun_dose > 0:
            vm.treat_with_compound(vessel_id, compound='tunicamycin', dose_uM=tun_dose)
            vm.advance_time(24.0)
            vm.washout_compound(vessel_id)

        vessel = vm.vessel_states[vessel_id]
        er_damage_values.append(vessel.er_damage)

        # Expose to mito compound (mid-slope dose)
        vm.treat_with_compound(vessel_id, compound='CCCP', dose_uM=0.7)
        vm.advance_time(12.0)

        mito_dysfunction_values.append(vessel.mito_dysfunction)

    # Assert: Spearman rank correlation > 0.6
    rho, p_value = spearmanr(er_damage_values, mito_dysfunction_values)

    print(f"\nER damage: {[f'{x:.3f}' for x in er_damage_values]}")
    print(f"Mito dysfunction: {[f'{x:.3f}' for x in mito_dysfunction_values]}")
    print(f"Spearman ρ = {rho:.3f} (p={p_value:.4f})")

    assert rho > 0.6, (
        f"ER → mito coupling not monotonic:\n"
        f"  Spearman ρ = {rho:.3f} (expect > 0.6)\n"
        f"  ER damage: {er_damage_values}\n"
        f"  Mito dysfunction: {mito_dysfunction_values}"
    )

    # Sanity: effect size should be material
    ratio = max(mito_dysfunction_values) / (min(mito_dysfunction_values) + 1e-9)
    assert ratio > 1.3, f"Effect size too weak: {ratio:.2f}× (expect > 1.3×)"

    print(f"✓ Coupling is monotonic (ρ={rho:.3f}, effect={ratio:.2f}×)")


def test_coupling_does_not_trigger_at_floor_or_ceiling():
    """
    Control: Floor and ceiling doses should not show coupling effect.

    This proves the test isn't just measuring random noise.
    """
    test_cases = [
        {'dose': 0.5, 'regime': 'floor', 'expected_median': 0.285},
        {'dose': 2.0, 'regime': 'ceiling', 'expected_median': 0.887},
    ]

    for case in test_cases:
        mito_values = []

        for er_priming in [0.0, 3.0]:  # No damage vs high damage
            vm = BiologicalVirtualMachine()
            vm.run_context = RunContext.sample(seed=100)
            vm.rng_assay = np.random.default_rng(1100)
            vm.rng_biology = np.random.default_rng(2100)
            vm._load_cell_thalamus_params()

            vessel_id = "P1_A01"
            vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)

            if er_priming > 0:
                vm.treat_with_compound(vessel_id, compound='tunicamycin', dose_uM=er_priming)
                vm.advance_time(24.0)
                vm.washout_compound(vessel_id)

            vm.treat_with_compound(vessel_id, compound='CCCP', dose_uM=case['dose'])
            vm.advance_time(12.0)

            mito_values.append(vm.vessel_states[vessel_id].mito_dysfunction)

        delta = abs(mito_values[1] - mito_values[0])

        print(f"\n{case['regime'].upper()} control ({case['dose']} µM):")
        print(f"  No damage: {mito_values[0]:.3f}")
        print(f"  High damage: {mito_values[1]:.3f}")
        print(f"  Delta: {delta:.3f}")

        # At floor/ceiling, coupling effect should be weak
        if case['regime'] == 'floor':
            assert delta < 0.15, f"Floor shows coupling (delta={delta:.3f})"
        elif case['regime'] == 'ceiling':
            assert delta < 0.10, f"Ceiling shows coupling (delta={delta:.3f})"

    print("✓ Floor and ceiling controls pass")


if __name__ == "__main__":
    test_er_damage_increases_mito_susceptibility_monotonically()
    test_coupling_does_not_trigger_at_floor_or_ceiling()
    print("\n✓ All tests passed")
