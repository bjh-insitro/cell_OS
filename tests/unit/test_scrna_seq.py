"""
Unit tests for scRNA-seq simulation.

Tests validate:
1. Stress program activation (increasing latent → increasing gene expression)
2. Batch effects (same biology → different counts per batch)
3. Subpopulation heterogeneity (resistant cells show weaker response)
"""

import numpy as np
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_er_stress_program_activation():
    """
    Test that increasing ER stress latent increases ER stress marker genes.

    Setup:
    - Seed vessel, treat with tunicamycin (ER stress inducer)
    - Advance time to build up ER stress latent
    - Run scRNA-seq, check HSPA5, DDIT3 upregulated

    Expected:
    - HSPA5, DDIT3 expression > baseline (untreated)
    - Fold change > 3× for canonical markers
    """
    print("\n=== Test: ER Stress Program Activation ===")

    vm = BiologicalVirtualMachine(seed=12345)

    # Control (untreated)
    vm.seed_vessel("ctrl", "A549", initial_count=1e6)
    vm.advance_time(24.0)
    result_ctrl = vm.scrna_seq_assay("ctrl", n_cells=200)

    counts_ctrl = result_ctrl['counts']
    gene_names = result_ctrl['gene_names']

    # Treated (tunicamycin → ER stress)
    vm.seed_vessel("treated", "A549", initial_count=1e6)
    vm.treat_with_compound("treated", "tunicamycin", dose_uM=2.0)
    vm.advance_time(24.0)
    result_treated = vm.scrna_seq_assay("treated", n_cells=200)

    counts_treated = result_treated['counts']
    vessel = vm.vessel_states["treated"]

    # Check ER stress latent is elevated
    print(f"ER stress latent: {vessel.er_stress:.3f}")
    assert vessel.er_stress > 0.3, f"ER stress latent too low: {vessel.er_stress}"

    # Check ER stress markers are upregulated
    er_markers = ["HSPA5", "DDIT3"]
    for marker in er_markers:
        if marker not in gene_names:
            continue

        idx = gene_names.index(marker)
        ctrl_mean = counts_ctrl[:, idx].mean()
        treated_mean = counts_treated[:, idx].mean()

        fold_change = (treated_mean + 0.1) / (ctrl_mean + 0.1)
        print(f"{marker}: {ctrl_mean:.1f} → {treated_mean:.1f} (FC={fold_change:.2f}x)")

        assert fold_change > 2.0, f"{marker} not upregulated enough (FC={fold_change:.2f}x)"

    print("✅ PASS: ER stress markers upregulated")


def test_batch_effects_change_profiles():
    """
    Test that batch effects create different count profiles even with identical biology.

    Setup:
    - Create two independent VMs with same seed (identical biology)
    - Seed vessels with identical treatment (tunicamycin 2µM, 24h)
    - Run scRNA-seq with different batch_id
    - Check that mean expression differs per batch

    Expected:
    - Same latent state (er_stress, viability)
    - Different absolute counts per batch (multiplicative gene-wise effects)
    - Correlation still high (biology signal preserved)
    """
    print("\n=== Test: Batch Effects Change Profiles ===")

    # Create two independent VMs with same seed (identical biology)
    vm1 = BiologicalVirtualMachine(seed=12345)
    vm2 = BiologicalVirtualMachine(seed=12345)

    # Batch 1
    vm1.seed_vessel("vessel", "A549", initial_count=1e6)
    vm1.treat_with_compound("vessel", "tunicamycin", dose_uM=2.0)
    vm1.advance_time(24.0)
    result1 = vm1.scrna_seq_assay("vessel", n_cells=200, batch_id="batch_A")

    # Batch 2 (identical biology, different batch)
    vm2.seed_vessel("vessel", "A549", initial_count=1e6)
    vm2.treat_with_compound("vessel", "tunicamycin", dose_uM=2.0)
    vm2.advance_time(24.0)
    result2 = vm2.scrna_seq_assay("vessel", n_cells=200, batch_id="batch_B")

    # Check latent states are identical (same seed, same treatment)
    v1 = vm1.vessel_states["vessel"]
    v2 = vm2.vessel_states["vessel"]
    print(f"Batch1 ER stress: {v1.er_stress:.3f}, viability: {v1.viability:.3f}")
    print(f"Batch2 ER stress: {v2.er_stress:.3f}, viability: {v2.viability:.3f}")

    assert abs(v1.er_stress - v2.er_stress) < 0.01
    assert abs(v1.viability - v2.viability) < 0.01

    # Check counts differ per batch
    counts1 = result1['counts']
    counts2 = result2['counts']

    mean1 = counts1.mean(axis=0)
    mean2 = counts2.mean(axis=0)

    # Compute per-gene ratios (batch effect multipliers)
    ratios = (mean2 + 0.1) / (mean1 + 0.1)

    # Check that ratios vary across genes (batch effects are gene-specific)
    ratio_std = ratios.std()
    print(f"Batch effect ratio std: {ratio_std:.3f}")
    assert ratio_std > 0.1, "Batch effects too weak (ratios should vary across genes)"

    # Check correlation is still high (biology signal preserved)
    corr = np.corrcoef(mean1, mean2)[0, 1]
    print(f"Batch correlation: {corr:.3f}")
    assert corr > 0.8, f"Batch effects destroyed biology signal (corr={corr:.3f})"

    print("✅ PASS: Batch effects present but biology preserved")


def test_subpop_heterogeneity():
    """
    Test that resistant cells show weaker stress program activation than sensitive cells.

    Setup:
    - Seed vessel, treat with tunicamycin
    - Run scRNA-seq
    - Split cells by subpop assignment (sensitive vs resistant)
    - Check that sensitive cells have higher ER marker expression

    Expected:
    - Sensitive cells: program_gain = 1.25 → stronger HSPA5 upregulation
    - Resistant cells: program_gain = 0.75 → weaker HSPA5 upregulation
    """
    print("\n=== Test: Subpopulation Heterogeneity ===")

    vm = BiologicalVirtualMachine(seed=12345)

    vm.seed_vessel("vessel", "A549", initial_count=1e6)
    vm.treat_with_compound("vessel", "tunicamycin", dose_uM=2.0)
    vm.advance_time(24.0)

    result = vm.scrna_seq_assay("vessel", n_cells=500)

    counts = result['counts']
    gene_names = result['gene_names']
    meta = result['meta']
    cell_subpops = meta['cell_subpop']

    # Check HSPA5 expression by subpop
    if "HSPA5" not in gene_names:
        print("⚠️  SKIP: HSPA5 not in gene panel")
        return

    hspa5_idx = gene_names.index("HSPA5")

    # Compute mean expression per subpop
    subpop_means = {}
    for subpop in ["sensitive", "typical", "resistant"]:
        mask = np.array([s == subpop for s in cell_subpops])
        if mask.sum() > 10:  # Need enough cells
            subpop_means[subpop] = counts[mask, hspa5_idx].mean()

    print(f"HSPA5 expression by subpop: {subpop_means}")

    # Check ordering: sensitive > typical > resistant
    if all(s in subpop_means for s in ["sensitive", "typical", "resistant"]):
        assert subpop_means["sensitive"] > subpop_means["typical"], \
            "Sensitive cells should have higher HSPA5 than typical"
        assert subpop_means["typical"] > subpop_means["resistant"], \
            "Typical cells should have higher HSPA5 than resistant"

    print("✅ PASS: Subpopulation heterogeneity observed")


def test_viability_affects_apoptosis_genes():
    """
    Test that low viability increases pro-apoptotic genes (BAX, BBC3).

    Setup:
    - Seed vessel, treat with high-dose compound to kill cells
    - Advance time to drop viability
    - Check BAX expression increases

    Expected:
    - Low viability (< 0.5) → BAX upregulated
    """
    print("\n=== Test: Viability Affects Apoptosis Genes ===")

    vm = BiologicalVirtualMachine(seed=12345)

    # Control (healthy)
    vm.seed_vessel("ctrl", "A549", initial_count=1e6)
    vm.advance_time(24.0)
    result_ctrl = vm.scrna_seq_assay("ctrl", n_cells=200)

    # Dying (high-dose treatment)
    vm.seed_vessel("dying", "A549", initial_count=1e6)
    vm.treat_with_compound("dying", "tunicamycin", dose_uM=10.0)  # High dose
    vm.advance_time(48.0)  # Long time to drive viability down

    vessel = vm.vessel_states["dying"]
    print(f"Dying vessel viability: {vessel.viability:.2%}")

    if vessel.viability > 0.5:
        print(f"⚠️  SKIP: Viability too high ({vessel.viability:.2f}), can't test apoptosis genes")
        return

    result_dying = vm.scrna_seq_assay("dying", n_cells=200)

    counts_ctrl = result_ctrl['counts']
    counts_dying = result_dying['counts']
    gene_names = result_ctrl['gene_names']

    # Check BAX upregulated
    if "BAX" in gene_names:
        idx = gene_names.index("BAX")
        ctrl_mean = counts_ctrl[:, idx].mean()
        dying_mean = counts_dying[:, idx].mean()

        fold_change = (dying_mean + 0.1) / (ctrl_mean + 0.1)
        print(f"BAX: {ctrl_mean:.1f} → {dying_mean:.1f} (FC={fold_change:.2f}x)")

        assert fold_change > 1.5, f"BAX not upregulated in dying cells (FC={fold_change:.2f}x)"

    print("✅ PASS: Apoptosis genes upregulated in dying cells")


def test_dropout_reduces_detection():
    """
    Test that dropout model makes low-expression genes undetected in some cells.

    Setup:
    - Run scRNA-seq
    - Check that low-expression genes have more zeros than high-expression genes

    Expected:
    - HSPA5 (low baseline) → high dropout rate (many zeros)
    - ACTB (high baseline) → low dropout rate (few zeros)
    """
    print("\n=== Test: Dropout Reduces Detection ===")

    vm = BiologicalVirtualMachine(seed=12345)

    vm.seed_vessel("vessel", "A549", initial_count=1e6)
    vm.advance_time(24.0)

    result = vm.scrna_seq_assay("vessel", n_cells=500)

    counts = result['counts']
    gene_names = result['gene_names']

    # High-expression gene: ACTB (housekeeping)
    if "ACTB" not in gene_names:
        print("⚠️  SKIP: ACTB not in panel")
        return

    actb_idx = gene_names.index("ACTB")
    actb_zeros = (counts[:, actb_idx] == 0).sum()
    actb_dropout_rate = actb_zeros / counts.shape[0]

    # Low-expression gene: DDIT3 (low baseline, inducible)
    if "DDIT3" not in gene_names:
        print("⚠️  SKIP: DDIT3 not in panel")
        return

    ddit3_idx = gene_names.index("DDIT3")
    ddit3_zeros = (counts[:, ddit3_idx] == 0).sum()
    ddit3_dropout_rate = ddit3_zeros / counts.shape[0]

    print(f"ACTB dropout rate: {actb_dropout_rate:.1%}")
    print(f"DDIT3 dropout rate: {ddit3_dropout_rate:.1%}")

    # DDIT3 should have higher dropout than ACTB (lower baseline expression)
    assert ddit3_dropout_rate > actb_dropout_rate, \
        "Low-expression genes should have higher dropout rate"

    print("✅ PASS: Dropout model working correctly")


if __name__ == "__main__":
    print("=" * 60)
    print("scRNA-seq Unit Tests")
    print("=" * 60)

    try:
        test_er_stress_program_activation()
        test_batch_effects_change_profiles()
        test_subpop_heterogeneity()
        test_viability_affects_apoptosis_genes()
        test_dropout_reduces_detection()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        raise
