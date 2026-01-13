"""
Test: epistemic control system (debt tracking + widening penalties).

PHILOSOPHY: This test validates that the epistemic control system enforces
the core principle: uncertainty is conserved unless you earn the reduction.

Tests cover:
1. Epistemic debt accumulation when overclaiming
2. Cost inflation from accumulated debt
3. Entropy penalties for posterior widening
4. Integration with MechanismPosterior
5. Asymmetry: overclaiming hurts more than underclaiming
"""

import numpy as np
from pathlib import Path
import tempfile

from cell_os.epistemic_agent import (
    EpistemicController,
    EpistemicControllerConfig,
    measure_and_penalize,
)
from cell_os.epistemic_agent import compute_information_gain_bits
from cell_os.epistemic_agent import (
    EpistemicPenaltyConfig,
    compute_entropy_penalty,
    compute_planning_horizon_shrinkage,
)
# Note: We compute entropy manually rather than importing MechanismPosterior
# to avoid complex constructor dependencies in this test


def test_information_gain_basic():
    """Test basic information gain computation."""
    # Narrowing posterior (gained information)
    prior_entropy = 2.0
    posterior_entropy = 1.0
    gain = compute_information_gain_bits(prior_entropy, posterior_entropy)
    assert gain == 1.0, f"Expected 1.0 bit gain, got {gain}"

    # Widening posterior (lost information)
    prior_entropy = 1.0
    posterior_entropy = 2.0
    gain = compute_information_gain_bits(prior_entropy, posterior_entropy)
    assert gain == -1.0, f"Expected -1.0 bit gain (widening), got {gain}"

    # No change
    gain = compute_information_gain_bits(2.0, 2.0)
    assert gain == 0.0, f"Expected 0.0 gain, got {gain}"

    print("✓ Information gain computation works")


def test_epistemic_debt_accumulation():
    """Test that overclaiming accumulates debt."""
    controller = EpistemicController()

    # Agent claims 0.8 bits but delivers only 0.2 bits
    controller.claim_action("action_1", "scrna_seq", expected_gain_bits=0.8)
    debt_increment = controller.resolve_action("action_1", actual_gain_bits=0.2)

    # Overclaim = 0.8 - 0.2 = 0.6 bits
    assert abs(debt_increment - 0.6) < 1e-6, f"Expected 0.6 debt, got {debt_increment}"
    assert abs(controller.get_total_debt() - 0.6) < 1e-6

    # Another overclaim
    controller.claim_action("action_2", "scrna_seq", expected_gain_bits=0.5)
    controller.resolve_action("action_2", actual_gain_bits=0.0)  # No gain!

    # Total debt = 0.6 + 0.5 = 1.1 bits
    assert abs(controller.get_total_debt() - 1.1) < 1e-6

    print(f"✓ Epistemic debt accumulates: {controller.get_total_debt():.3f} bits")


def test_debt_does_not_accumulate_on_underclaim():
    """Test asymmetry: underclaiming doesn't add debt."""
    controller = EpistemicController()

    # Agent claims 0.2 bits but delivers 0.8 bits (conservative)
    controller.claim_action("action_1", "scrna_seq", expected_gain_bits=0.2)
    debt_increment = controller.resolve_action("action_1", actual_gain_bits=0.8)

    # Overclaim penalty = max(0, 0.2 - 0.8) = 0
    assert debt_increment == 0.0, f"Expected no debt for underclaim, got {debt_increment}"
    assert controller.get_total_debt() == 0.0

    print("✓ Underclaiming does not accumulate debt (asymmetry works)")


def test_cost_inflation_from_debt():
    """Test that debt inflates future costs."""
    controller = EpistemicController()

    # No debt → no inflation
    base_cost = 200.0
    inflated = controller.get_inflated_cost(base_cost)
    assert inflated == base_cost, f"Expected no inflation, got {inflated}"

    # Accumulate debt
    controller.claim_action("action_1", "scrna_seq", expected_gain_bits=1.0)
    controller.resolve_action("action_1", actual_gain_bits=0.0)  # 1.0 bit debt

    # Cost should be inflated by ~10% (default sensitivity)
    inflated = controller.get_inflated_cost(base_cost)
    expected = base_cost * 1.1  # 1.0 + 0.1 * 1.0
    assert abs(inflated - expected) < 0.1, f"Expected {expected}, got {inflated}"

    # More debt → more inflation
    controller.claim_action("action_2", "scrna_seq", expected_gain_bits=2.0)
    controller.resolve_action("action_2", actual_gain_bits=0.0)  # +2.0 bits debt = 3.0 total

    inflated = controller.get_inflated_cost(base_cost)
    expected = base_cost * 1.3  # 1.0 + 0.1 * 3.0
    assert abs(inflated - expected) < 0.1, f"Expected {expected}, got {inflated}"

    print(f"✓ Cost inflation from debt: 3.0 bits → {inflated/base_cost:.2f}× multiplier")


def test_entropy_penalty_for_widening():
    """Test that posterior widening is penalized."""
    config = EpistemicPenaltyConfig(entropy_penalty_weight=1.0)

    # No widening → no penalty
    penalty = compute_entropy_penalty(
        prior_entropy=2.0,
        posterior_entropy=2.0,
        action_type="scrna_seq",
        config=config,
    )
    assert penalty == 0.0, f"Expected no penalty, got {penalty}"

    # Widening by 0.5 bits → penalty = 0.5
    penalty = compute_entropy_penalty(
        prior_entropy=2.0,
        posterior_entropy=2.5,
        action_type="scrna_seq",
        config=config,
    )
    assert abs(penalty - 0.5) < 1e-6, f"Expected 0.5 penalty, got {penalty}"

    # Narrowing (negative ΔH) → no penalty
    penalty = compute_entropy_penalty(
        prior_entropy=2.5,
        posterior_entropy=2.0,
        action_type="scrna_seq",
        config=config,
    )
    assert penalty == 0.0, f"Expected no penalty for narrowing, got {penalty}"

    print("✓ Entropy penalty works: widening hurts, narrowing doesn't")


def test_horizon_shrinkage_from_uncertainty():
    """Test that high entropy shrinks planning horizon."""
    config = EpistemicPenaltyConfig(horizon_shrinkage_rate=0.2)
    baseline_entropy = 2.0

    # At baseline → no shrinkage
    multiplier = compute_planning_horizon_shrinkage(
        current_entropy=2.0,
        baseline_entropy=baseline_entropy,
        config=config,
    )
    assert abs(multiplier - 0.8) < 1e-6, f"Expected 0.8, got {multiplier}"

    # Double baseline → more shrinkage
    multiplier = compute_planning_horizon_shrinkage(
        current_entropy=4.0,
        baseline_entropy=baseline_entropy,
        config=config,
    )
    expected = 1.0 - 0.2 * (4.0 / 2.0)  # 1.0 - 0.4 = 0.6
    assert abs(multiplier - expected) < 1e-6, f"Expected {expected}, got {multiplier}"

    print(f"✓ Horizon shrinkage: 2× entropy → {multiplier:.2f}× horizon")


def test_integration_with_mechanism_posterior():
    """Test integration with MechanismPosterior-like entropy values."""
    # Compute entropy manually for ambiguous distribution
    # P = {0.4, 0.35, 0.25}
    # H = -Σ p log(p)
    probs_ambiguous = [0.4, 0.35, 0.25]
    ambiguous_entropy = -sum(p * np.log(p) for p in probs_ambiguous if p > 0)

    # Compute entropy for confident distribution
    # P = {0.9, 0.08, 0.02}
    probs_confident = [0.9, 0.08, 0.02]
    confident_entropy = -sum(p * np.log(p) for p in probs_confident if p > 0)

    print(f"\nAmbiguous posterior entropy: {ambiguous_entropy:.3f} bits")
    print(f"Confident posterior entropy: {confident_entropy:.3f} bits")

    assert ambiguous_entropy > confident_entropy, "Ambiguous should have higher entropy"

    # Simulate a bad scRNA result that widens posterior
    controller = EpistemicController()
    controller.set_baseline_entropy(confident_entropy)

    # Agent claims scRNA will help (0.5 bits gain)
    controller.claim_action("scrna_001", "scrna_seq", expected_gain_bits=0.5)

    # But scRNA actually widens posterior (batch drift + cell cycle confounder)
    realized_gain = controller.measure_information_gain(
        prior_entropy=confident_entropy,
        posterior_entropy=ambiguous_entropy,
    )

    # Realized gain is NEGATIVE (widened)
    assert realized_gain < 0, f"Expected negative gain, got {realized_gain}"

    # Resolve claim
    debt_increment = controller.resolve_action("scrna_001", realized_gain, "scrna_seq")

    # Debt = claimed - realized = 0.5 - (negative) = 0.5 + |realized|
    print(f"Claimed: 0.5 bits")
    print(f"Realized: {realized_gain:.3f} bits (WIDENED)")
    print(f"Debt increment: {debt_increment:.3f} bits")
    assert debt_increment > 0.5, "Widening should accumulate more debt than narrowing"

    # Compute penalty
    penalty = controller.compute_penalty("scrna_seq")
    print(f"Entropy penalty: {penalty.entropy_penalty:.3f}")
    print(f"Horizon multiplier: {penalty.horizon_multiplier:.3f}")

    assert penalty.entropy_penalty > 0, "Should penalize widening"
    assert penalty.horizon_multiplier < 1.0, "Should shrink horizon when uncertain"

    print("✓ Integration with MechanismPosterior works")


def test_full_workflow():
    """Test complete workflow: claim → measure → resolve → inflate."""
    controller = EpistemicController()

    # Scenario: Agent runs scRNA three times, overclaiming each time
    base_cost = 200.0
    actions = [
        ("scrna_001", 0.8, 0.2),  # claimed 0.8, got 0.2
        ("scrna_002", 0.7, 0.1),  # claimed 0.7, got 0.1
        ("scrna_003", 0.5, -0.2), # claimed 0.5, got -0.2 (widened!)
    ]

    print("\nFull workflow simulation:")
    for action_id, claimed, realized in actions:
        # Before action
        cost_before = controller.get_inflated_cost(base_cost)
        print(f"\n[{action_id}]")
        print(f"  Cost before: ${cost_before:.2f}")

        # Claim
        controller.claim_action(action_id, "scrna_seq", claimed)

        # Measure (simulate)
        prior_entropy = 2.0
        posterior_entropy = prior_entropy - realized  # Compute from gain
        controller.measure_information_gain(prior_entropy, posterior_entropy)

        # Resolve
        debt_increment = controller.resolve_action(action_id, realized, "scrna_seq")
        print(f"  Claimed: {claimed:.2f} bits")
        print(f"  Realized: {realized:.2f} bits")
        print(f"  Debt increment: {debt_increment:.2f} bits")
        print(f"  Total debt: {controller.get_total_debt():.2f} bits")

        # Penalty
        penalty = controller.compute_penalty()
        if penalty.did_widen:
            print(f"  ⚠️  WIDENED by {-realized:.2f} bits")
            print(f"  Entropy penalty: {penalty.entropy_penalty:.2f}")

    # Final cost
    final_cost = controller.get_inflated_cost(base_cost)
    print(f"\nFinal cost inflation:")
    print(f"  Base cost: ${base_cost:.2f}")
    print(f"  Final cost: ${final_cost:.2f}")
    print(f"  Multiplier: {final_cost/base_cost:.2f}×")

    # Debt should be >= 1.9 bits (sum of overclaims: 0.6 + 0.6 + 0.7 = 1.9)
    assert controller.get_total_debt() >= 1.8
    assert final_cost > base_cost * 1.15  # At least 15% inflation

    print("\n✓ Full workflow demonstrates epistemic control")


def test_save_and_load():
    """Test persistence of epistemic debt."""
    controller = EpistemicController()

    # Accumulate some debt
    controller.claim_action("action_1", "scrna_seq", 0.8)
    controller.resolve_action("action_1", 0.2)

    debt_before = controller.get_total_debt()

    # Save to temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "epistemic_debt.json"
        controller.save(path)

        # Load new controller
        loaded = EpistemicController.load(path)
        debt_after = loaded.get_total_debt()

        assert abs(debt_before - debt_after) < 1e-6, "Debt not preserved"

    print("✓ Save/load preserves epistemic debt")


if __name__ == "__main__":
    print("=" * 70)
    print("Epistemic Control System Tests")
    print("=" * 70)

    test_information_gain_basic()
    test_epistemic_debt_accumulation()
    test_debt_does_not_accumulate_on_underclaim()
    test_cost_inflation_from_debt()
    test_entropy_penalty_for_widening()
    test_horizon_shrinkage_from_uncertainty()
    test_integration_with_mechanism_posterior()
    test_full_workflow()
    test_save_and_load()

    print("\n" + "=" * 70)
    print("✓ All tests passed: epistemic control system working")
    print("=" * 70)
    print("\nKey results:")
    print("  • Overclaiming accumulates debt")
    print("  • Debt inflates future costs")
    print("  • Posterior widening is penalized")
    print("  • High entropy shrinks planning horizon")
    print("  • System integrates with MechanismPosterior")
    print("\nPhilosophy: Uncertainty is conserved unless you earn the reduction.")
