"""
Test epistemic controller integration with agent workflow.

This validates that:
1. Claims are tracked when designs are proposed
2. Gains are measured when observations arrive
3. Debt accumulates from miscalibration
4. Costs inflate with accumulated debt
5. System prevents overclaiming through economic pressure
"""

import numpy as np
from dataclasses import dataclass
from src.cell_os.epistemic_agent.controller_integration import EpistemicIntegration


@dataclass
class MockPosterior:
    """Mock posterior for testing (only needs entropy attribute)."""
    entropy: float


def test_claim_and_resolve_cycle():
    """
    Basic claim-resolve cycle: agent claims gain, gets measured, debt accumulates.
    """
    integration = EpistemicIntegration(enable=True)

    # Create mock posteriors (simple high-confidence ER stress)
    prior = MockPosterior(entropy=1.485  # ~1.5 bits uncertainty
    )

    # After observation, narrow to ER stress
    posterior = MockPosterior(entropy=0.569  # ~0.6 bits uncertainty
    )

    # Realized gain: 1.485 - 0.569 = 0.916 bits

    # Agent claims 0.8 bits (close to realized, should have minimal debt)
    claim_id = integration.claim_design(
        design_id="test_001",
        cycle=1,
        expected_gain_bits=0.8,
        hypothesis="ER stress mechanism",
        modalities=("cell_painting",),
        wells_count=16,
        estimated_cost_usd=50.0
    )

    assert claim_id == "claim_1_test_001"
    assert len(integration.pending_claims) == 1

    # Resolve claim
    result = integration.resolve_design(
        claim_id=claim_id,
        prior_posterior=prior,
        posterior=posterior
    )

    assert result["realized_gain"] > 0.5  # Actually gained information
    assert abs(result["debt_increment"]) < 0.2  # Well-calibrated, minimal debt
    assert len(integration.pending_claims) == 0  # Claim resolved

    print(f"✓ Claim-resolve cycle validated")
    print(f"  Realized gain: {result['realized_gain']:.3f} bits")
    print(f"  Debt increment: {result['debt_increment']:.3f}")
    print(f"  Total debt: {result['total_debt']:.3f}")


def test_overclaiming_accumulates_debt():
    """
    Agent overclaims gain → debt accumulates → costs inflate.
    """
    integration = EpistemicIntegration(enable=True)

    # Prior: uncertain
    prior = MockPosterior(entropy=1.485
    )

    # Posterior: still uncertain (didn't learn much)
    posterior = MockPosterior(entropy=1.352  # Only gained 0.133 bits
    )

    # Agent claims 0.8 bits (overclaim by 0.667 bits!)
    claim_id = integration.claim_design(
        design_id="test_002",
        cycle=2,
        expected_gain_bits=0.8,
        hypothesis="ER stress mechanism",
        modalities=("cell_painting",),
        wells_count=16,
        estimated_cost_usd=50.0
    )

    result = integration.resolve_design(
        claim_id=claim_id,
        prior_posterior=prior,
        posterior=posterior
    )

    assert result["realized_gain"] < 0.8  # Gained less than claimed
    assert result["debt_increment"] > 0  # Debt accumulated
    assert result["total_debt"] > 0  # Positive debt

    print(f"\n✓ Overclaiming accumulates debt")
    print(f"  Claimed: 0.800 bits")
    print(f"  Realized: {result['realized_gain']:.3f} bits")
    print(f"  Debt increment: +{result['debt_increment']:.3f}")
    print(f"  Total debt: {result['total_debt']:.3f}")


def test_debt_inflates_costs():
    """
    After overclaiming, future actions become more expensive.
    """
    integration = EpistemicIntegration(enable=True)

    # Build up debt through repeated overclaiming
    prior = MockPosterior(entropy=1.485
    )

    posterior_weak = MockPosterior(entropy=1.450  # Minimal gain (~0.035 bits)
    )

    # Overclaim 3 times
    for i in range(3):
        claim_id = integration.claim_design(
            design_id=f"test_00{i+3}",
            cycle=i+3,
            expected_gain_bits=0.8,  # Claim 0.8
            hypothesis="Test hypothesis",
            modalities=("cell_painting",),
            wells_count=16,
            estimated_cost_usd=50.0
        )

        integration.resolve_design(
            claim_id=claim_id,
            prior_posterior=prior,
            posterior=posterior_weak  # Actually gain ~0.035 bits
        )

    # Check cost inflation
    base_cost = 200.0
    inflated_cost, details = integration.get_inflated_cost(base_cost, "scrna_seq")

    assert inflated_cost > base_cost  # Cost inflated
    assert details["multiplier"] > 1.0  # Multiplier > 1
    assert details["inflation_amount"] > 0  # Positive inflation

    print(f"\n✓ Debt inflates costs")
    print(f"  Base cost: ${base_cost:.0f}")
    print(f"  Inflated cost: ${inflated_cost:.0f}")
    print(f"  Multiplier: {details['multiplier']:.2f}×")
    print(f"  Total debt: {details['total_debt']:.3f} bits")
    print(f"  Economic pressure: ${details['inflation_amount']:.0f} penalty")


def test_widening_measured_correctly():
    """
    If observation widens posterior (negative gain), debt accumulates heavily.
    """
    integration = EpistemicIntegration(enable=True)

    # Prior: confident
    prior = MockPosterior(entropy=0.569)

    # Posterior: contradictory observation widens
    posterior = MockPosterior(entropy=1.485  # Widened by 0.916 bits!
    )

    # Agent claimed positive gain
    claim_id = integration.claim_design(
        design_id="test_006",
        cycle=6,
        expected_gain_bits=0.5,  # Claimed narrowing
        hypothesis="ER stress confirmation",
        modalities=("cell_painting",),
        wells_count=16,
        estimated_cost_usd=50.0
    )

    result = integration.resolve_design(
        claim_id=claim_id,
        prior_posterior=prior,
        posterior=posterior
    )

    assert result["realized_gain"] < 0  # Negative gain (widened)
    assert result["debt_increment"] > 0.5  # Heavy debt penalty
    assert result["total_debt"] > 0

    print(f"\n✓ Widening measured correctly")
    print(f"  Claimed: +0.500 bits")
    print(f"  Realized: {result['realized_gain']:.3f} bits (WIDENING)")
    print(f"  Debt increment: +{result['debt_increment']:.3f} (HEAVY PENALTY)")
    print(f"  Total debt: {result['total_debt']:.3f}")


def test_calibrated_claims_no_debt():
    """
    Well-calibrated claims don't accumulate debt.
    """
    integration = EpistemicIntegration(enable=True)

    prior = MockPosterior(entropy=1.485
    )

    posterior = MockPosterior(entropy=1.157  # Gain ~0.328 bits
    )

    # Agent claims 0.3 bits (well-calibrated)
    claim_id = integration.claim_design(
        design_id="test_007",
        cycle=7,
        expected_gain_bits=0.3,
        hypothesis="ER stress mechanism",
        modalities=("cell_painting",),
        wells_count=16,
        estimated_cost_usd=50.0
    )

    result = integration.resolve_design(
        claim_id=claim_id,
        prior_posterior=prior,
        posterior=posterior
    )

    # Should have minimal debt (< 0.1 bits)
    assert abs(result["debt_increment"]) < 0.1  # Well-calibrated
    assert result["total_debt"] < 0.1  # Low total debt

    print(f"\n✓ Calibrated claims accumulate minimal debt")
    print(f"  Claimed: 0.300 bits")
    print(f"  Realized: {result['realized_gain']:.3f} bits")
    print(f"  Debt increment: {result['debt_increment']:.3f} (minimal)")
    print(f"  Total debt: {result['total_debt']:.3f}")


def test_disabled_mode_no_tracking():
    """
    When disabled, integration doesn't track debt (for testing/debugging).
    """
    integration = EpistemicIntegration(enable=False)

    prior = MockPosterior(entropy=1.485
    )

    posterior = MockPosterior(entropy=0.569
    )

    # Claim and resolve
    claim_id = integration.claim_design(
        design_id="test_008",
        cycle=8,
        expected_gain_bits=0.8,
        hypothesis="Test",
        modalities=("cell_painting",),
        wells_count=16,
        estimated_cost_usd=50.0
    )

    result = integration.resolve_design(
        claim_id=claim_id,
        prior_posterior=prior,
        posterior=posterior
    )

    # No debt accumulation
    assert result["total_debt"] == 0.0
    assert result["debt_increment"] == 0.0
    assert result["realized_gain"] == 0.0

    # No cost inflation
    base_cost = 200.0
    inflated_cost, details = integration.get_inflated_cost(base_cost)
    assert inflated_cost == base_cost
    assert details["multiplier"] == 1.0

    print(f"\n✓ Disabled mode: no tracking")
    print(f"  Debt: {result['total_debt']:.3f} (zero)")
    print(f"  Cost inflation: {details['multiplier']:.2f}× (none)")


if __name__ == "__main__":
    print("=" * 70)
    print("EPISTEMIC CONTROLLER INTEGRATION TESTS")
    print("=" * 70)
    print()

    test_claim_and_resolve_cycle()
    test_overclaiming_accumulates_debt()
    test_debt_inflates_costs()
    test_widening_measured_correctly()
    test_calibrated_claims_no_debt()
    test_disabled_mode_no_tracking()

    print("\n" + "=" * 70)
    print("✅ ALL EPISTEMIC CONTROLLER INTEGRATION TESTS PASSED")
    print("=" * 70)
    print("\nValidated:")
    print("  ✓ Claim-resolve cycle tracks debt correctly")
    print("  ✓ Overclaiming accumulates debt")
    print("  ✓ Debt inflates future costs (economic pressure)")
    print("  ✓ Widening heavily penalized")
    print("  ✓ Calibrated claims minimize debt")
    print("  ✓ Disabled mode for testing/debugging")
