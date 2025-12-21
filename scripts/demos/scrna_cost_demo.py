#!/usr/bin/env python3
"""
Demo: scRNA-seq cost model in action.

Shows:
1. Time cost (4h) increases drift exposure vs imaging (2h)
2. Reagent cost ($200) vs imaging ($20)
3. Underpowered requests flagged (n_cells < min_cells)
4. Cell cycle confounder creates false "recovery" signal
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.assay_governance import (
    AssayJustification,
    allow_scrna_seq,
    estimate_scRNA_info_gain,
)
import yaml


def main():
    print("=" * 70)
    print("scRNA-seq Cost Model Demo")
    print("=" * 70)

    # Load params to show cost structure
    params_path = Path(__file__).parent.parent.parent / "data" / "scrna_seq_params.yaml"
    with open(params_path) as f:
        params = yaml.safe_load(f)

    costs = params["costs"]
    print("\n[Cost Structure]")
    print(f"  Time cost:       {costs['time_cost_h']}h (vs 2h for imaging)")
    print(f"  Reagent cost:    ${costs['reagent_cost_usd']} (vs ~$20 for imaging)")
    print(f"  Min cells:       {costs['min_cells']} (power requirement)")
    print(f"  Penalty if underpowered: {costs['soft_penalty_if_underpowered']:.2%}")

    # Create VM
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_well", "A549", initial_count=1e6)
    vm.advance_time(24.0)

    # Set moderate stress
    vessel = vm.vessel_states["test_well"]
    vessel.er_stress = 0.6
    vessel.viability = 0.9

    # Test 1: Underpowered request (should be flagged)
    print("\n" + "=" * 70)
    print("[Test 1] Underpowered Request")
    print("=" * 70)

    result_low = vm.scrna_seq_assay("test_well", n_cells=300)
    print(f"\nRequested: 300 cells")
    print(f"Minimum required: {result_low['min_cells_required']}")
    print(f"Is underpowered: {result_low['is_underpowered']}")
    print(f"Soft penalty: {result_low['soft_penalty_if_underpowered']:.2%}")
    print("\n⚠️  Agent should be penalized for ignoring power requirements")

    # Test 2: Proper powered request
    print("\n" + "=" * 70)
    print("[Test 2] Properly Powered Request")
    print("=" * 70)

    result_ok = vm.scrna_seq_assay("test_well", n_cells=1000)
    print(f"\nRequested: 1000 cells")
    print(f"Minimum required: {result_ok['min_cells_required']}")
    print(f"Is underpowered: {result_ok['is_underpowered']}")
    print(f"Time cost: {result_ok['time_cost_h']}h")
    print(f"Reagent cost: ${result_ok['reagent_cost_usd']}")
    print("\n✓ Agent pays full cost but gets reliable data")

    # Test 3: Justification gating
    print("\n" + "=" * 70)
    print("[Test 3] Justification Gating")
    print("=" * 70)

    # Bad justification: no failed modalities
    bad_justif = AssayJustification(
        ambiguity="ER vs oxidative",
        failed_modalities=(),  # EMPTY - didn't try cheaper assays
        expected_information_gain=0.5,
        min_cells=1000,
    )

    allowed, reason = allow_scrna_seq(bad_justif, params, drift_score=0.3)
    print(f"\nJustification 1: {bad_justif.ambiguity}")
    print(f"  Failed modalities: {bad_justif.failed_modalities}")
    print(f"  Allowed: {allowed}")
    print(f"  Reason: {reason}")

    # Good justification
    good_justif = AssayJustification(
        ambiguity="ER vs oxidative crosstalk",
        failed_modalities=("cell_painting", "atp_assay"),
        expected_information_gain=0.8,  # 0.8 bits / $200 = 0.004 bits/$
        min_cells=1000,
    )

    allowed, reason = allow_scrna_seq(good_justif, params, drift_score=0.3)
    print(f"\nJustification 2: {good_justif.ambiguity}")
    print(f"  Failed modalities: {good_justif.failed_modalities}")
    print(f"  Info gain: {good_justif.expected_information_gain:.2f} bits")
    print(f"  Info gain / $: {good_justif.expected_information_gain / costs['reagent_cost_usd']:.4f} bits/$")
    print(f"  Allowed: {allowed}")
    print(f"  Reason: {reason}")

    # High drift without replicate plan
    high_drift_justif = AssayJustification(
        ambiguity="ER stress magnitude",
        failed_modalities=("cell_painting",),
        expected_information_gain=0.6,
        min_cells=1000,
        replicate_strategy=None,  # No plan for high drift!
    )

    allowed, reason = allow_scrna_seq(high_drift_justif, params, drift_score=0.8)
    print(f"\nJustification 3 (high drift): {high_drift_justif.ambiguity}")
    print(f"  Drift score: 0.8 (HIGH)")
    print(f"  Replicate strategy: {high_drift_justif.replicate_strategy}")
    print(f"  Allowed: {allowed}")
    print(f"  Reason: {reason}")

    # Test 4: Cell cycle confounder
    print("\n" + "=" * 70)
    print("[Test 4] Cell Cycle Confounder")
    print("=" * 70)

    result_cc = vm.scrna_seq_assay("test_well", n_cells=1000)
    meta = result_cc["meta"]
    cycling_scores = meta.get("cycling_score")

    if cycling_scores:
        import numpy as np

        cycling_frac = np.mean([c > 0.5 for c in cycling_scores])
        print(f"\nCell line: A549 (lung cancer)")
        print(f"Cycling fraction: {cycling_frac:.1%}")
        print(f"\nEffect: Cycling cells suppress stress markers by 20-35%")
        print(f"  → False 'recovery' signal when population is proliferating")
        print(f"  → Naive averaging gives misleading low-stress estimate")
        print(f"  → Agent must model cell cycle as confounder")

    print("\n" + "=" * 70)
    print("Summary: scRNA is expensive, slow, and confounded")
    print("=" * 70)
    print("\nKey takeaways:")
    print("  • 10× more expensive than imaging ($200 vs $20)")
    print("  • 2× longer (4h vs 2h) → more drift exposure")
    print("  • Cell cycle confounds stress markers")
    print("  • Requires justification (failed cheaper assays)")
    print("  • High drift requires replicate strategy")
    print("\nConclusion: scRNA is not a ground truth oracle.")
    print("            Use it strategically, not by default.")


if __name__ == "__main__":
    main()
