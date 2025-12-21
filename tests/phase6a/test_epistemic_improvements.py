"""
Test: Epistemic system improvements (entropy source + marginal gain + provisional penalties).

Tests the three Tier 1 improvements:
1. Entropy source tracking (exploration vs confusion)
2. Marginal info gain (prevents redundancy spam)
3. Provisional penalties (multi-step credit assignment)
"""

import numpy as np
from pathlib import Path

from cell_os.epistemic_control import EpistemicController, EntropySource
from cell_os.epistemic_provisional import ProvisionalPenaltyTracker


def test_entropy_source_distinguishes_exploration_vs_confusion():
    """
    Test that prior uncertainty is NOT penalized, but measurement-induced
    widening IS penalized.
    """
    controller = EpistemicController()

    # Scenario 1: High prior entropy (exploration - not measured yet)
    prior_entropy = 2.5  # High (haven't measured)
    posterior_entropy = 2.5  # Still high after measurement

    # Measure with PRIOR source (exploration)
    gain = controller.measure_information_gain(
        prior_entropy=prior_entropy,
        posterior_entropy=posterior_entropy,
        entropy_source=EntropySource.PRIOR
    )

    # Compute penalty
    penalty = controller.compute_penalty(action_type="scrna_seq")

    # CRITICAL: Should NOT penalize high prior entropy
    assert penalty.entropy_penalty == 0.0, "Should not penalize exploration uncertainty"
    print("✓ Prior uncertainty (exploration) is not penalized")

    # Scenario 2: Measurement-induced widening (confusion - measured and got worse)
    controller.reset()
    prior_entropy = 1.0  # Low (confident)
    posterior_entropy = 2.0  # High (confused after measurement!)

    # Measure with MEASUREMENT_CONTRADICTORY source
    gain = controller.measure_information_gain(
        prior_entropy=prior_entropy,
        posterior_entropy=posterior_entropy,
        entropy_source=EntropySource.MEASUREMENT_CONTRADICTORY
    )

    # Compute penalty
    penalty = controller.compute_penalty(action_type="scrna_seq")

    # Should penalize measurement-induced confusion
    assert penalty.entropy_penalty > 0.5, f"Should penalize widening, got {penalty.entropy_penalty}"
    print(f"✓ Measurement-induced confusion IS penalized: {penalty.entropy_penalty:.2f}")

    # Scenario 3: Measurement narrowing (good!)
    controller.reset()
    prior_entropy = 2.0
    posterior_entropy = 1.0  # Narrowed!

    gain = controller.measure_information_gain(
        prior_entropy=prior_entropy,
        posterior_entropy=posterior_entropy,
        entropy_source=EntropySource.MEASUREMENT_NARROWING
    )

    penalty = controller.compute_penalty(action_type="scrna_seq")

    # Should not penalize narrowing
    assert penalty.entropy_penalty == 0.0, "Should not penalize narrowing"
    print("✓ Measurement narrowing is not penalized")


def test_marginal_info_gain_prevents_redundancy():
    """
    Test that agents can claim marginal info gain accounting for prior measurements.
    """
    controller = EpistemicController()

    # Agent measures imaging first
    controller.claim_action(
        action_id="imaging_001",
        action_type="cell_painting",
        expected_gain_bits=0.8,
    )
    controller.resolve_action("imaging_001", 0.8)

    # Now agent wants scRNA, but must account for imaging overlap
    controller.claim_action(
        action_id="scrna_001",
        action_type="scrna_seq",
        expected_gain_bits=0.5,  # Total gain if measured alone
        prior_modalities=("cell_painting",),
        claimed_marginal_gain=0.2,  # Marginal gain after imaging
    )

    # Check that claim includes marginal info
    claim = controller.ledger.claims[-1]
    assert claim.prior_modalities == ("cell_painting",)
    assert claim.claimed_marginal_gain == 0.2

    print("✓ Marginal info gain tracking works")
    print(f"  Total gain: {claim.claimed_gain_bits:.2f} bits")
    print(f"  Marginal gain: {claim.claimed_marginal_gain:.2f} bits (after imaging)")


def test_provisional_penalties_enable_productive_uncertainty():
    """
    Test that provisional penalties allow multi-step credit assignment.

    Scenario:
    - scRNA widens entropy temporarily (reveals subpopulations)
    - But enables targeted follow-up that collapses entropy
    - Initial widening should be refunded
    """
    controller = EpistemicController()
    controller.set_baseline_entropy(1.0)

    # Step 1: scRNA widens entropy (reveals heterogeneity)
    prior_entropy = 1.0
    posterior_entropy = 1.5  # Widened by 0.5 bits

    controller.claim_action("scrna_001", "scrna_seq", expected_gain_bits=0.5)

    gain = controller.measure_information_gain(
        prior_entropy=prior_entropy,
        posterior_entropy=posterior_entropy,
        entropy_source=EntropySource.MEASUREMENT_AMBIGUOUS
    )

    controller.resolve_action("scrna_001", gain, "scrna_seq")

    # Compute penalty
    penalty = controller.compute_penalty()
    assert penalty.entropy_penalty > 0, "Widening should be penalized initially"

    # But make it provisional (might be productive)
    controller.add_provisional_penalty(
        action_id="scrna_001_provisional",
        penalty_amount=penalty.entropy_penalty,
        settlement_horizon=2,
    )

    print(f"✓ Added provisional penalty: {penalty.entropy_penalty:.2f}")

    # Step 2: Follow-up action (doesn't help)
    controller.posterior_entropy = 1.6  # Still high
    finalized = controller.step_provisional_penalties()
    assert finalized == 0.0, "Should not finalize yet (horizon=2)"

    # Step 3: Another action collapses entropy below prior!
    controller.posterior_entropy = 0.8  # Collapsed below prior (1.0)
    finalized = controller.step_provisional_penalties()

    # Penalty should be refunded (entropy collapsed)
    stats = controller.get_statistics()
    assert stats["provisional_total_refunded"] > 0, "Penalty should be refunded"
    print(f"✓ Provisional penalty refunded: {stats['provisional_total_refunded']:.2f}")
    print("  Reason: entropy collapsed below prior (productive uncertainty)")


def test_provisional_penalties_finalize_on_failure():
    """
    Test that provisional penalties finalize if entropy stays high.
    """
    controller = EpistemicController()

    # Widen entropy
    prior_entropy = 1.0
    posterior_entropy = 1.5

    controller.measure_information_gain(prior_entropy, posterior_entropy)

    # Add provisional penalty with short horizon
    controller.add_provisional_penalty(
        action_id="scrna_bad",
        penalty_amount=0.5,
        settlement_horizon=1,
    )

    # Step forward, but entropy stays high
    controller.posterior_entropy = 1.6  # Still high
    finalized = controller.step_provisional_penalties()

    # Penalty should finalize (entropy didn't collapse)
    assert finalized > 0, "Penalty should finalize"

    stats = controller.get_statistics()
    assert stats["provisional_total_finalized"] > 0, "Should have finalized penalties"
    print(f"✓ Provisional penalty finalized: {stats['provisional_total_finalized']:.2f}")
    print("  Reason: entropy stayed high (not productive)")


def test_integrated_workflow_with_improvements():
    """
    Test full workflow with all three improvements working together.
    """
    controller = EpistemicController()
    controller.set_baseline_entropy(1.5)

    print("\n" + "="*60)
    print("Integrated Workflow Test")
    print("="*60)

    # Episode 1: Imaging (baseline measurement)
    print("\n[Episode 1] Imaging")
    prior = 1.8  # High prior (haven't measured)
    post = 1.2   # Narrowed

    controller.claim_action("imaging_001", "cell_painting", 0.6)
    gain = controller.measure_information_gain(
        prior, post, entropy_source=EntropySource.MEASUREMENT_NARROWING
    )
    controller.resolve_action("imaging_001", gain)
    penalty = controller.compute_penalty(action_type="cell_painting")

    print(f"  Info gain: {gain:.2f} bits")
    print(f"  Penalty: {penalty.entropy_penalty:.2f} (none for narrowing)")
    print(f"  Debt: {controller.get_total_debt():.2f} bits")

    # Episode 2: scRNA with marginal gain claim
    print("\n[Episode 2] scRNA (accounting for imaging)")
    prior = 1.2
    post = 1.4  # Widens temporarily (reveals subpops)

    controller.claim_action(
        "scrna_001",
        "scrna_seq",
        expected_gain_bits=0.4,  # Total if alone
        prior_modalities=("cell_painting",),
        claimed_marginal_gain=0.2,  # After imaging
    )

    gain = controller.measure_information_gain(
        prior, post, entropy_source=EntropySource.MEASUREMENT_AMBIGUOUS
    )
    controller.resolve_action("scrna_001", gain, "scrna_seq")
    penalty = controller.compute_penalty(action_type="scrna_seq")

    # Make penalty provisional (might be productive)
    if penalty.entropy_penalty > 0:
        controller.add_provisional_penalty(
            "scrna_001_prov",
            penalty.entropy_penalty,
            settlement_horizon=2,
        )

    print(f"  Info gain: {gain:.2f} bits (WIDENED)")
    print(f"  Provisional penalty: {penalty.entropy_penalty:.2f}")
    print(f"  Debt: {controller.get_total_debt():.2f} bits")

    # Step 1 time (horizon=2, need 2 steps to settle)
    controller.posterior_entropy = 1.3
    finalized = controller.step_provisional_penalties()
    print(f"\n  Step 1: finalized={finalized:.2f}, entropy still 1.3")

    # Episode 3: Targeted follow-up collapses entropy
    print("\n[Episode 3] Targeted follow-up")
    prior = 1.3
    post = 0.8  # Collapsed below initial prior (1.2)!

    controller.claim_action("followup_001", "cell_painting", 0.6)
    gain = controller.measure_information_gain(
        prior, post, entropy_source=EntropySource.MEASUREMENT_NARROWING
    )
    controller.resolve_action("followup_001", gain)

    # Step provisional penalties again (should settle now)
    finalized = controller.step_provisional_penalties()

    print(f"  Info gain: {gain:.2f} bits (collapsed!)")
    print(f"  Provisional settled (refunded): {finalized == 0.0}")

    # Final stats
    stats = controller.get_statistics()
    print("\n" + "-"*60)
    print("Final Statistics:")
    print(f"  Total debt: {stats['total_debt']:.2f} bits")
    print(f"  Provisional refunded: {stats['provisional_total_refunded']:.2f}")
    print(f"  Cost multiplier: {stats['cost_multiplier']:.2f}×")

    assert stats["provisional_total_refunded"] > 0, "Should have refunded provisional penalty"
    print("\n✓ Full workflow successful: productive uncertainty was not penalized")


if __name__ == "__main__":
    print("="*60)
    print("Epistemic System Improvements Tests")
    print("="*60)

    test_entropy_source_distinguishes_exploration_vs_confusion()
    print()
    test_marginal_info_gain_prevents_redundancy()
    print()
    test_provisional_penalties_enable_productive_uncertainty()
    print()
    test_provisional_penalties_finalize_on_failure()
    print()
    test_integrated_workflow_with_improvements()

    print("\n" + "="*60)
    print("✓ All improvement tests passed")
    print("="*60)
    print("\nKey capabilities demonstrated:")
    print("  1. Entropy source tracking: exploration ≠ confusion")
    print("  2. Marginal gain tracking: prevents redundancy spam")
    print("  3. Provisional penalties: enables productive uncertainty")
    print("\nThese close critical loopholes in epistemic control.")
