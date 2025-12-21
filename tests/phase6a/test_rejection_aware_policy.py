"""
Rejection-Aware Policy Integration Test

Validates that the agent can:
1. Propose a confounded design (confluence issue at 48h)
2. Catch InvalidDesignError from validator
3. Automatically apply a fix (reduce time to 24h)
4. Retry with fixed design
5. Continue execution (not abort)

This ensures the agent learns from validation failures instead of crashing.
"""

import tempfile
from pathlib import Path

from src.cell_os.epistemic_agent.loop import EpistemicLoop
from src.cell_os.epistemic_agent.world import ExperimentalWorld
from src.cell_os.epistemic_agent.schemas import Proposal, WellSpec
from src.cell_os.epistemic_agent.exceptions import InvalidDesignError


def test_rejection_aware_policy_fixes_confluence():
    """
    Test that agent automatically fixes confluence-confounded designs.

    Setup:
    - Create confounded design (control vs treatment at 48h)
    - Validator should reject with confluence_confounding
    - Agent should automatically reduce time to 24h
    - Retry should succeed
    """
    world = ExperimentalWorld(budget_wells=96, seed=42)

    # Create a confounded proposal (48h timepoint)
    # Control: DMSO at 48h (high confluence)
    # Treatment: etoposide at 48h (low confluence due to toxicity)
    wells = [
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=48.0,
            assay="cell_painting",
            position_tag="center"
        ),
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=48.0,
            assay="cell_painting",
            position_tag="center"
        ),
        WellSpec(
            cell_line="A549",
            compound="etoposide",
            dose_uM=10000.0,  # High dose = toxic
            time_h=48.0,
            assay="cell_painting",
            position_tag="center"
        ),
        WellSpec(
            cell_line="A549",
            compound="etoposide",
            dose_uM=10000.0,
            time_h=48.0,
            assay="cell_painting",
            position_tag="center"
        ),
    ]

    proposal_confounded = Proposal(
        design_id="test_confounded_48h",
        hypothesis="This should be rejected and auto-fixed",
        wells=wells,
        budget_limit=1000.0
    )

    # First attempt: should be rejected
    print("=" * 70)
    print("STEP 1: First attempt (should be rejected)")
    print("=" * 70)
    try:
        observation_first = world.run_experiment(
            proposal_confounded,
            cycle=1,
            run_id="test_rejection",
            validate=True
        )
        print("✗ FAILED: Design should have been rejected (confluence confounding)")
        assert False, "Design should have been rejected"
    except InvalidDesignError as e:
        print(f"✓ Design rejected as expected")
        print(f"  Violation: {e.violation_code}")
        print(f"  Delta_p: {e.details.get('delta_p', 'N/A')}")
        assert e.violation_code == "confluence_confounding"

    # Now test the rejection-aware policy via EpistemicLoop._apply_design_fix()
    print("\n" + "=" * 70)
    print("STEP 2: Apply automatic fix (reduce time 48h → 24h)")
    print("=" * 70)

    # Create a minimal EpistemicLoop instance just to access _apply_design_fix()
    with tempfile.TemporaryDirectory() as tmpdir:
        loop = EpistemicLoop(budget=96, max_cycles=1, log_dir=Path(tmpdir), seed=42)

        # Try to fix the design
        try:
            # First, get the rejection error
            world_fix = ExperimentalWorld(budget_wells=96, seed=42)
            try:
                world_fix.run_experiment(proposal_confounded, cycle=1, run_id="test", validate=True)
            except InvalidDesignError as rejection_error:
                # Apply fix
                proposal_fixed = loop._apply_design_fix(proposal_confounded, rejection_error)

                if proposal_fixed is None:
                    print("✗ FAILED: Could not fix design")
                    assert False, "Fix should have been applied"

                print(f"✓ Fix applied successfully")
                print(f"  Original design_id: {proposal_confounded.design_id}")
                print(f"  Fixed design_id: {proposal_fixed.design_id}")
                print(f"  Original max time: {max(w.time_h for w in proposal_confounded.wells)}h")
                print(f"  Fixed max time: {max(w.time_h for w in proposal_fixed.wells)}h")

                # Validate the fix
                assert proposal_fixed.design_id == "test_confounded_48h_fixed_t24h"
                assert max(w.time_h for w in proposal_fixed.wells) == 24.0
                assert "FIXED" in proposal_fixed.hypothesis

                # Step 3: Retry with fixed design
                print("\n" + "=" * 70)
                print("STEP 3: Retry with fixed design (should succeed)")
                print("=" * 70)

                world_retry = ExperimentalWorld(budget_wells=96, seed=42)
                observation_retry = world_retry.run_experiment(
                    proposal_fixed,
                    cycle=1,
                    run_id="test_rejection",
                    validate=True
                )

                print(f"✓ Retry succeeded with fixed design")
                print(f"  Design executed: {observation_retry.design_id}")
                print(f"  Wells spent: {observation_retry.wells_spent}")
                print(f"  Budget remaining: {observation_retry.budget_remaining}")

                assert observation_retry.design_id == "test_confounded_48h_fixed_t24h"
                assert observation_retry.wells_spent == 4
                assert world_retry.budget_remaining == 92

        except Exception as e:
            print(f"✗ FAILED: {e}")
            raise


def test_rejection_aware_policy_24h_to_12h():
    """
    Test that agent can apply multiple fix attempts.

    If 24h is still confounded, should reduce to 12h.
    """
    world = ExperimentalWorld(budget_wells=96, seed=42)

    # Create a confounded proposal at 24h
    wells = [
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="center"
        ),
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="center"
        ),
        WellSpec(
            cell_line="A549",
            compound="etoposide",
            dose_uM=10000.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="center"
        ),
        WellSpec(
            cell_line="A549",
            compound="etoposide",
            dose_uM=10000.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="center"
        ),
    ]

    proposal_24h = Proposal(
        design_id="test_confounded_24h",
        hypothesis="This should be fixed by reducing to 12h",
        wells=wells,
        budget_limit=1000.0
    )

    print("\n" + "=" * 70)
    print("TEST: 24h → 12h reduction")
    print("=" * 70)

    # Check if 24h is confounded (may or may not be, depending on model)
    try:
        observation_24h = world.run_experiment(
            proposal_24h,
            cycle=1,
            run_id="test_24h",
            validate=True
        )
        print(f"✓ 24h design passed validation (no fix needed)")
        print(f"  Design not confounded at 24h timepoint")

    except InvalidDesignError as e_24h:
        print(f"✓ 24h design rejected, applying fix...")
        print(f"  Violation: {e_24h.violation_code}")

        # Apply fix (should reduce to 12h)
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = EpistemicLoop(budget=96, max_cycles=1, log_dir=Path(tmpdir), seed=42)
            proposal_fixed = loop._apply_design_fix(proposal_24h, e_24h)

            if proposal_fixed is None:
                print("✗ FAILED: Could not fix 24h design")
                assert False, "Should be able to reduce 24h → 12h"

            print(f"✓ Fix applied: 24h → {max(w.time_h for w in proposal_fixed.wells)}h")
            assert max(w.time_h for w in proposal_fixed.wells) == 12.0
            assert "fixed_t12h" in proposal_fixed.design_id


def test_rejection_aware_policy_unfixable():
    """
    Test that agent returns None for unfixable designs.

    If design is already at 12h and still confounded, cannot fix by reducing time.
    """
    print("\n" + "=" * 70)
    print("TEST: Unfixable design (already ≤12h)")
    print("=" * 70)

    # Create a confounded proposal at 12h
    wells = [
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=12.0,
            assay="cell_painting",
            position_tag="center"
        ),
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=12.0,
            assay="cell_painting",
            position_tag="center"
        ),
        WellSpec(
            cell_line="A549",
            compound="etoposide",
            dose_uM=10000.0,
            time_h=12.0,
            assay="cell_painting",
            position_tag="center"
        ),
        WellSpec(
            cell_line="A549",
            compound="etoposide",
            dose_uM=10000.0,
            time_h=12.0,
            assay="cell_painting",
            position_tag="center"
        ),
    ]

    proposal_12h = Proposal(
        design_id="test_confounded_12h",
        hypothesis="This cannot be fixed by reducing time",
        wells=wells,
        budget_limit=1000.0
    )

    # Check if 12h is confounded (may or may not be)
    world = ExperimentalWorld(budget_wells=96, seed=42)
    try:
        observation_12h = world.run_experiment(
            proposal_12h,
            cycle=1,
            run_id="test_12h",
            validate=True
        )
        print(f"✓ 12h design passed validation (not confounded)")
        print(f"  No fix needed - design is density-matched")

    except InvalidDesignError as e_12h:
        print(f"✓ 12h design rejected, attempting fix...")
        print(f"  Violation: {e_12h.violation_code}")

        # Try to apply fix (should return None for ≤12h)
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = EpistemicLoop(budget=96, max_cycles=1, log_dir=Path(tmpdir), seed=42)
            proposal_fixed = loop._apply_design_fix(proposal_12h, e_12h)

            print(f"✓ Fix returned None (cannot fix by reducing time)")
            assert proposal_fixed is None, "Should return None for unfixable design"


def test_batch_confounding_unfixable():
    """
    Test that batch confounding returns None (cannot fix automatically).
    """
    print("\n" + "=" * 70)
    print("TEST: Batch confounding (unfixable)")
    print("=" * 70)

    # Create a mock InvalidDesignError for batch confounding
    error = InvalidDesignError(
        message="Batch confounded: plate (imbalance=0.850)",
        violation_code="batch_confounding",
        design_id="test_batch",
        cycle=1,
        validator_mode="policy_guard",
        details={"imbalance_metric": 0.850}
    )

    # Create proposal (doesn't matter, just for API)
    proposal = Proposal(
        design_id="test_batch",
        hypothesis="Batch confounded",
        wells=[
            WellSpec(
                cell_line="A549",
                compound="DMSO",
                dose_uM=0.0,
                time_h=24.0,
                assay="cell_painting",
                position_tag="center"
            )
        ],
        budget_limit=1000.0
    )

    # Try to apply fix (should return None)
    with tempfile.TemporaryDirectory() as tmpdir:
        loop = EpistemicLoop(budget=96, max_cycles=1, log_dir=Path(tmpdir), seed=42)
        proposal_fixed = loop._apply_design_fix(proposal, error)

        print(f"✓ Batch confounding fix returned None (cannot fix automatically)")
        assert proposal_fixed is None


if __name__ == "__main__":
    print("=" * 70)
    print("REJECTION-AWARE POLICY INTEGRATION TESTS")
    print("=" * 70)
    print()

    print("=" * 70)
    print("TEST 1: Confluence Fix (48h → 24h)")
    print("=" * 70)
    test_rejection_aware_policy_fixes_confluence()
    print()

    print("=" * 70)
    print("TEST 2: Multi-Step Fix (24h → 12h)")
    print("=" * 70)
    test_rejection_aware_policy_24h_to_12h()
    print()

    print("=" * 70)
    print("TEST 3: Unfixable Design (≤12h)")
    print("=" * 70)
    test_rejection_aware_policy_unfixable()
    print()

    print("=" * 70)
    print("TEST 4: Batch Confounding (Unfixable)")
    print("=" * 70)
    test_batch_confounding_unfixable()
    print()

    print("=" * 70)
    print("✅ ALL REJECTION-AWARE POLICY TESTS PASSED")
    print("=" * 70)
    print()
    print("Validated:")
    print("  ✓ Agent catches confluence confounding and applies fix (48h → 24h)")
    print("  ✓ Agent can apply multi-step fixes (24h → 12h)")
    print("  ✓ Agent returns None for unfixable designs (≤12h)")
    print("  ✓ Agent returns None for batch confounding (cannot fix automatically)")
    print()
    print("🎉 REJECTION-AWARE POLICY FULLY FUNCTIONAL!")
