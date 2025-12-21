#!/usr/bin/env python3
"""
Minimal scRNA-seq demo: validates that stress programs activate correctly.

Tests:
1. Baseline (untreated) → housekeeping genes dominate
2. ER stress (tunicamycin) → HSPA5, DDIT3, ATF4 upregulated
3. Batch effects → same biology, different counts per batch
"""

import numpy as np
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def print_top_genes(counts: np.ndarray, gene_names: list, top_n: int = 10, label: str = ""):
    """Print top expressed genes by mean UMI count."""
    mean_expr = counts.mean(axis=0)
    top_idx = np.argsort(mean_expr)[::-1][:top_n]

    print(f"\n{label} - Top {top_n} genes:")
    print("Gene\tMean UMI\tStd")
    print("-" * 40)
    for idx in top_idx:
        gene = gene_names[idx]
        mean = mean_expr[idx]
        std = counts[:, idx].std()
        print(f"{gene}\t{mean:.1f}\t{std:.1f}")


def compute_fold_change(treated_counts, control_counts, gene_names):
    """Compute fold changes (treated / control) with pseudocount."""
    pseudocount = 0.1
    treated_mean = treated_counts.mean(axis=0) + pseudocount
    control_mean = control_counts.mean(axis=0) + pseudocount
    fc = treated_mean / control_mean

    # Sort by fold change
    sorted_idx = np.argsort(fc)[::-1]

    print("\nTop 10 upregulated genes (treated / control):")
    print("Gene\tFold Change\tControl\tTreated")
    print("-" * 50)
    for idx in sorted_idx[:10]:
        gene = gene_names[idx]
        print(f"{gene}\t{fc[idx]:.2f}x\t{control_mean[idx]:.1f}\t{treated_mean[idx]:.1f}")

    print("\nTop 10 downregulated genes:")
    print("Gene\tFold Change\tControl\tTreated")
    print("-" * 50)
    for idx in sorted_idx[-10:]:
        gene = gene_names[idx]
        print(f"{gene}\t{fc[idx]:.2f}x\t{control_mean[idx]:.1f}\t{treated_mean[idx]:.1f}")


def main():
    print("=" * 60)
    print("scRNA-seq Demo: Stress Program Activation")
    print("=" * 60)

    # Initialize VM with deterministic seed
    vm = BiologicalVirtualMachine(seed=42)

    # === Test 1: Baseline (untreated) ===
    print("\n[Test 1] Baseline (untreated)")
    print("-" * 60)

    vm.seed_vessel("well_ctrl", "A549", initial_count=1e6)
    vm.advance_time(24.0)  # 24h growth

    result_ctrl = vm.scrna_seq_assay("well_ctrl", n_cells=500, batch_id="batch1")
    print(f"Status: {result_ctrl['status']}")
    print(f"Cells profiled: {result_ctrl['n_cells']}")
    print(f"Genes: {result_ctrl['n_genes']}")

    counts_ctrl = result_ctrl['counts']
    gene_names = result_ctrl['gene_names']

    print_top_genes(counts_ctrl, gene_names, top_n=10, label="Control")

    # === Test 2: ER stress (tunicamycin) ===
    print("\n[Test 2] ER stress (tunicamycin 2 µM, 24h)")
    print("-" * 60)

    vm.seed_vessel("well_tuni", "A549", initial_count=1e6)
    vm.treat_with_compound("well_tuni", "tunicamycin", dose_uM=2.0)
    vm.advance_time(24.0)  # 24h treatment

    result_tuni = vm.scrna_seq_assay("well_tuni", n_cells=500, batch_id="batch1")
    print(f"Status: {result_tuni['status']}")
    print(f"Viability: {vm.vessel_states['well_tuni'].viability:.2%}")
    print(f"ER stress latent: {vm.vessel_states['well_tuni'].er_stress:.3f}")

    counts_tuni = result_tuni['counts']

    print_top_genes(counts_tuni, gene_names, top_n=10, label="Tunicamycin")

    # Compute fold changes
    compute_fold_change(counts_tuni, counts_ctrl, gene_names)

    # === Test 3: Batch effects ===
    print("\n[Test 3] Batch effects (same biology, different batches)")
    print("-" * 60)

    vm.seed_vessel("well_batch2", "A549", initial_count=1e6)
    vm.treat_with_compound("well_batch2", "tunicamycin", dose_uM=2.0)
    vm.advance_time(24.0)

    result_batch2 = vm.scrna_seq_assay("well_batch2", n_cells=500, batch_id="batch2")
    counts_batch2 = result_batch2['counts']

    # Compare batch1 vs batch2 (same treatment, different batch)
    print("\nBatch effect check (tunicamycin, batch1 vs batch2):")
    print("Gene\tBatch1 Mean\tBatch2 Mean\tRatio")
    print("-" * 50)

    # Show batch effects for a few marker genes
    marker_genes = ["HSPA5", "DDIT3", "ACTB", "GAPDH"]
    for gene in marker_genes:
        if gene in gene_names:
            idx = gene_names.index(gene)
            batch1_mean = counts_tuni[:, idx].mean()
            batch2_mean = counts_batch2[:, idx].mean()
            ratio = batch2_mean / (batch1_mean + 0.1)  # Avoid div by zero
            print(f"{gene}\t{batch1_mean:.1f}\t{batch2_mean:.1f}\t{ratio:.2f}x")

    # === Test 4: Subpopulation heterogeneity ===
    print("\n[Test 4] Subpopulation heterogeneity")
    print("-" * 60)

    meta = result_tuni['meta']
    cell_subpops = meta['cell_subpop']
    library_sizes = meta['library_size']

    # Count cells per subpop
    from collections import Counter
    subpop_counts = Counter(cell_subpops)
    print("\nCells per subpopulation:")
    for subpop, count in sorted(subpop_counts.items()):
        print(f"  {subpop}: {count} ({count/len(cell_subpops)*100:.1f}%)")

    # Compare HSPA5 expression per subpop (sensitive should be higher)
    if "HSPA5" in gene_names:
        hspa5_idx = gene_names.index("HSPA5")
        print("\nHSPA5 expression by subpopulation:")
        for subpop in ["sensitive", "typical", "resistant"]:
            mask = np.array([s == subpop for s in cell_subpops])
            if mask.sum() > 0:
                hspa5_mean = counts_tuni[mask, hspa5_idx].mean()
                print(f"  {subpop}: {hspa5_mean:.1f} UMI")

    print("\n" + "=" * 60)
    print("Demo complete! Check that:")
    print("1. Control shows housekeeping genes (ACTB, GAPDH)")
    print("2. Tunicamycin upregulates HSPA5, DDIT3, ATF4 (ER stress)")
    print("3. Batch2 has different absolute counts vs Batch1")
    print("4. Sensitive cells show higher stress marker expression")
    print("=" * 60)


if __name__ == "__main__":
    main()
