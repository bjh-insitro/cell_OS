"""
Realism test: ER → Mito coupling is identifiable.

Validates that the coupling creates a detectable phenotypic shift that could be
learned by an agent.

Design:
- Condition A: CCCP 0.7 µM only
- Condition B: Tunicamycin 2 µM (24h) → washout → CCCP 0.7 µM
- N=12 replicates each
- Assert: Distributions differ (KS test p < 0.05, effect size > 20%)
"""

import pytest
import numpy as np
from scipy.stats import ks_2samp
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.run_context import RunContext


@pytest.mark.realism
def test_er_priming_creates_identifiable_mito_phenotype():
    """
    ER priming should create a detectable shift in mito dysfunction distribution.

    This validates pedagogical value: an agent could learn to exploit this.
    """
    N_REPLICATES = 12
    seed_base = 200

    # Condition A: CCCP only
    mito_only = []
    for i in range(N_REPLICATES):
        vm = BiologicalVirtualMachine()
        vm.run_context = RunContext.sample(seed=seed_base + i)
        vm.rng_assay = np.random.default_rng(seed_base + i + 1000)
        vm.rng_biology = np.random.default_rng(seed_base + i + 2000)
        vm._load_cell_thalamus_params()

        vessel_id = f"P1_A{i+1:02d}"
        vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)

        # Mito compound only (mid-slope dose)
        vm.treat_with_compound(vessel_id, compound='CCCP', dose_uM=0.7)
        vm.advance_time(12.0)

        mito_only.append(vm.vessel_states[vessel_id].mito_dysfunction)

    # Condition B: ER priming then mito
    er_then_mito = []
    for i in range(N_REPLICATES):
        vm = BiologicalVirtualMachine()
        vm.run_context = RunContext.sample(seed=seed_base + i + 100)
        vm.rng_assay = np.random.default_rng(seed_base + i + 1100)
        vm.rng_biology = np.random.default_rng(seed_base + i + 2100)
        vm._load_cell_thalamus_params()

        vessel_id = f"P2_A{i+1:02d}"
        vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)

        # ER priming
        vm.treat_with_compound(vessel_id, compound='tunicamycin', dose_uM=2.0)
        vm.advance_time(24.0)

        # Washout + mito compound
        vm.washout_compound(vessel_id)
        vm.treat_with_compound(vessel_id, compound='CCCP', dose_uM=0.7)
        vm.advance_time(12.0)

        er_then_mito.append(vm.vessel_states[vessel_id].mito_dysfunction)

    # KS test: Do distributions differ?
    ks_stat, p_value = ks_2samp(mito_only, er_then_mito)

    print(f"\n=== ER → Mito Coupling Identifiability ===")
    print(f"CCCP only: {np.mean(mito_only):.3f} ± {np.std(mito_only):.3f}")
    print(f"ER → CCCP: {np.mean(er_then_mito):.3f} ± {np.std(er_then_mito):.3f}")
    print(f"KS test: stat={ks_stat:.3f}, p={p_value:.4f}")

    # Assert: Distributions differ significantly
    assert p_value < 0.05, (
        f"Coupling not identifiable:\n"
        f"  KS test p={p_value:.4f} (expect < 0.05)\n"
        f"  Distributions do not significantly differ"
    )

    # Assert: Effect size is material
    mean_a = np.mean(mito_only)
    mean_b = np.mean(er_then_mito)
    effect_size = abs(mean_b - mean_a) / (mean_a + 1e-9)

    assert effect_size > 0.20, (
        f"Effect size too weak:\n"
        f"  Effect = {effect_size:.3f} (expect > 0.20)\n"
        f"  Mean A={mean_a:.3f}, Mean B={mean_b:.3f}"
    )

    print(f"✓ Coupling is identifiable (p={p_value:.4f}, effect={effect_size:.2%})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
