#!/usr/bin/env python3
"""
Sanity checks for epistemic agent before adding Bayesian core.

Tests:
1. Replicate uniqueness - std > 0 for each morphology channel
2. Edge vs center bias detection
3. Determinism - same seed produces identical outputs
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cell_os.epistemic_agent.world import ExperimentalWorld
from cell_os.epistemic_agent.schemas import Proposal, WellSpec
import uuid


def test_1_replicate_uniqueness():
    """Test that replicates are actually independent (not clones)."""
    print("\n" + "="*60)
    print("TEST 1: Replicate Uniqueness")
    print("="*60)

    world = ExperimentalWorld(budget_wells=20, seed=42)

    # Propose 12 DMSO replicates, center
    proposal = Proposal(
        design_id=f"sanity_replicate_{uuid.uuid4().hex[:8]}",
        hypothesis="Test replicate independence",
        wells=[
            WellSpec('A549', 'DMSO', 0.0, 12.0, 'cell_painting', 'center')
            for _ in range(12)
        ],
        budget_limit=20
    )

    obs = world.run_experiment(proposal)
    cond = obs.conditions[0]

    print(f"Condition: {cond}")
    print(f"n={cond.n_wells}, scalar mean={cond.mean:.4f}, std={cond.std:.4f}, CV={cond.cv:.2%}")
    print(f"\nPer-channel stats:")
    for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        mean = cond.feature_means[ch]
        std = cond.feature_stds[ch]
        cv = std / mean if mean > 0 else 0
        print(f"  {ch:8s}: mean={mean:.4f}, std={std:.4f}, CV={cv:.2%}")

    # Check: ALL channels should have std > 0
    all_nonzero = all(cond.feature_stds[ch] > 0 for ch in ['er', 'mito', 'nucleus', 'actin', 'rna'])

    if all_nonzero:
        print("\n✅ PASS: All channels have std > 0 (replicates are independent)")
        return True
    else:
        print("\n❌ FAIL: Some channels have std = 0 (replicates are clones!)")
        return False


def test_2_edge_center_bias():
    """Test that edge vs center produces detectable difference."""
    print("\n" + "="*60)
    print("TEST 2: Edge vs Center Bias Detection")
    print("="*60)

    world = ExperimentalWorld(budget_wells=30, seed=42)

    # 12 DMSO center, 12 DMSO edge
    wells = []
    for _ in range(12):
        wells.append(WellSpec('A549', 'DMSO', 0.0, 12.0, 'cell_painting', 'center'))
    for _ in range(12):
        wells.append(WellSpec('A549', 'DMSO', 0.0, 12.0, 'cell_painting', 'edge'))

    proposal = Proposal(
        design_id=f"sanity_edge_{uuid.uuid4().hex[:8]}",
        hypothesis="Test edge bias",
        wells=wells,
        budget_limit=30
    )

    obs = world.run_experiment(proposal)

    # Find center and edge conditions
    center_cond = [c for c in obs.conditions if c.position_tag == 'center'][0]
    edge_cond = [c for c in obs.conditions if c.position_tag == 'edge'][0]

    print(f"Center: mean={center_cond.mean:.4f}, CV={center_cond.cv:.2%}")
    print(f"Edge:   mean={edge_cond.mean:.4f}, CV={edge_cond.cv:.2%}")
    print(f"Difference: {abs(center_cond.mean - edge_cond.mean):.4f} ({abs(center_cond.mean - edge_cond.mean) / center_cond.mean:.2%})")

    print(f"\nPer-channel edge bias:")
    for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        center_val = center_cond.feature_means[ch]
        edge_val = edge_cond.feature_means[ch]
        diff_pct = abs(edge_val - center_val) / center_val if center_val > 0 else 0
        print(f"  {ch:8s}: center={center_val:.4f}, edge={edge_val:.4f}, diff={diff_pct:.2%}")

    # Check: Edge should show ~12% lower signal (configured in simulator)
    diff_pct = abs(center_cond.mean - edge_cond.mean) / center_cond.mean
    edge_lower = edge_cond.mean < center_cond.mean

    if edge_lower and 0.08 < diff_pct < 0.16:  # Expect ~12% ± tolerance
        print(f"\n✅ PASS: Edge shows {diff_pct:.2%} reduction (expected ~12%)")
        return True
    else:
        print(f"\n⚠️  WARNING: Edge effect not as expected (got {diff_pct:.2%}, expected ~12%)")
        return False


def test_3_determinism():
    """Test that same seed produces identical outputs."""
    print("\n" + "="*60)
    print("TEST 3: Determinism")
    print("="*60)

    # CRITICAL: Use SAME design_id for both runs (it's part of RNG seed!)
    fixed_design_id = "sanity_determinism_fixed"

    # Run same experiment twice with seed=42
    results = []
    for run in [1, 2]:
        world = ExperimentalWorld(budget_wells=20, seed=42)

        proposal = Proposal(
            design_id=fixed_design_id,  # SAME ID for both runs!
            hypothesis="Test determinism",
            wells=[
                WellSpec('A549', 'DMSO', 0.0, 12.0, 'cell_painting', 'center')
                for _ in range(6)
            ],
            budget_limit=20
        )

        obs = world.run_experiment(proposal)
        cond = obs.conditions[0]

        results.append({
            'mean': cond.mean,
            'std': cond.std,
            'feature_means': cond.feature_means.copy(),
        })

        print(f"Run {run}: mean={cond.mean:.6f}, std={cond.std:.6f}")

    # Check: Should be IDENTICAL
    mean_diff = abs(results[0]['mean'] - results[1]['mean'])
    std_diff = abs(results[0]['std'] - results[1]['std'])

    print(f"\nDifferences: mean_diff={mean_diff:.10f}, std_diff={std_diff:.10f}")

    if mean_diff < 1e-10 and std_diff < 1e-10:
        print("✅ PASS: Identical outputs with same seed")
        return True
    else:
        print("❌ FAIL: Different outputs with same seed (not deterministic!)")
        return False


def main():
    print("="*60)
    print("EPISTEMIC AGENT - SANITY CHECKS")
    print("="*60)

    results = []

    try:
        results.append(("Replicate uniqueness", test_1_replicate_uniqueness()))
    except Exception as e:
        print(f"❌ Test 1 crashed: {e}")
        results.append(("Replicate uniqueness", False))

    try:
        results.append(("Edge bias detection", test_2_edge_center_bias()))
    except Exception as e:
        print(f"❌ Test 2 crashed: {e}")
        results.append(("Edge bias detection", False))

    try:
        results.append(("Determinism", test_3_determinism()))
    except Exception as e:
        print(f"❌ Test 3 crashed: {e}")
        results.append(("Determinism", False))

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(p for _, p in results)
    if all_passed:
        print("\n🎉 All sanity checks passed! Ready for Bayesian core.")
        return 0
    else:
        print("\n⚠️  Some checks failed. Fix before adding complexity.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
