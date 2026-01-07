"""
Phase 5: Epistemic Control tests.

Verifies that:
1. Naive/greedy policies fail deterministically on weak signature compounds
2. Smart probe-then-commit policy succeeds on all compounds

This is where the substrate stops being a lookup table in a tux and starts
forcing temporal information-risk tradeoffs.
"""

from cell_os.hardware.masked_compound_phase5 import (
    PHASE5_LIBRARY,
    WEAK_SIGNATURE_SUBSET,
    CLEAN_SIGNATURE_SUBSET
)
from cell_os.hardware.epistemic_policies import (
    run_naive_policy,
    run_greedy_policy,
    run_smart_policy
)


def test_epistemic_control_baselines_fail_on_weak_subset():
    """
    Verify that naive and greedy policies fail deterministically on weak compounds.

    Weak compounds (potency ~0.3-0.5) have ambiguous signatures at 12h.
    Greedy classifies from weak early signals → forced guess → misclassification.
    Naive waits 48h at high dose → violates death budget (>20% death).

    This test proves that temporal structure matters - you can't just
    "dose and measure" without thinking about when.
    """
    print("\n=== Epistemic Control: Baseline Failures (Weak Subset) ===")

    for compound_id in WEAK_SIGNATURE_SUBSET:
        compound = PHASE5_LIBRARY[compound_id]
        print(f"\n--- Testing {compound_id} ({compound.true_stress_axis}) ---")
        print(f"    Potency: {compound.potency_scalar:.1f}×, Toxicity: {compound.toxicity_scalar:.1f}×")

        # Test naive policy
        naive_result = run_naive_policy(compound)
        print(f"\n  Naive (dose 1.0×, wait 48h):")
        print(f"    Predicted: {naive_result.predicted_axis}, Correct: {naive_result.correct_axis}")
        print(f"    Death: {naive_result.death_48h:.1%}, Viability: {naive_result.viability_48h:.1%}")
        print(f"    Reward: {naive_result.reward_total:.2f}")

        # Naive should fail (death budget OR misclassification)
        naive_fails = (naive_result.death_48h > 0.20) or (not naive_result.correct_axis)
        assert naive_fails, (
            f"Naive should fail on weak compound {compound_id}: "
            f"death={naive_result.death_48h:.1%} (should be >20%), "
            f"correct={naive_result.correct_axis} (should be False)"
        )
        print(f"    ✓ Naive fails: {'death budget' if naive_result.death_48h > 0.20 else 'misclassification'}")

        # Test greedy policy
        greedy_result = run_greedy_policy(compound)
        print(f"\n  Greedy (dose 0.25×, classify at 12h):")
        print(f"    Predicted: {greedy_result.predicted_axis}, Correct: {greedy_result.correct_axis}")
        print(f"    Confidence: {greedy_result.confidence:.2f}")
        print(f"    Death: {greedy_result.death_48h:.1%}, Viability: {greedy_result.viability_48h:.1%}")
        print(f"    Reward: {greedy_result.reward_total:.2f}")

        # Greedy should misclassify (ambiguous signatures at 12h with weak compounds)
        assert not greedy_result.correct_axis, (
            f"Greedy should misclassify weak compound {compound_id}: "
            f"predicted={greedy_result.predicted_axis}, true={compound.true_stress_axis}"
        )
        print(f"    ✓ Greedy fails: misclassification (confidence={greedy_result.confidence:.2f})")

    print(f"\n✓ PASSED: Baseline policies fail deterministically on weak subset")


import pytest


@pytest.mark.slow
def test_epistemic_control_smart_policy_succeeds_on_all():
    """
    Verify that probe-then-commit strategy succeeds on all compounds.

    Smart policy:
        1. Probe at 0.5× to 12h
        2. Classify from moderate signatures
        3. Commit based on axis:
           - Microtubule: continue to 24h, washout
           - ER/Mito: washout immediately

    Should succeed on both clean and weak compounds:
        - Moderate dose disambiguates weak signatures by 12h
        - Targeted washout prevents death budget violation
        - Uses 1 intervention (within budget of 2)
        - Valid attempt gate satisfied
    """
    print("\n=== Epistemic Control: Smart Policy Success (All Compounds) ===")

    results = {}

    for compound_id, compound in PHASE5_LIBRARY.items():
        print(f"\n--- Testing {compound_id} ({compound.true_stress_axis}) ---")
        print(f"    Potency: {compound.potency_scalar:.1f}×, Toxicity: {compound.toxicity_scalar:.1f}×")

        smart_result = run_smart_policy(compound)
        print(f"\n  Smart (probe 0.5× @ 12h, commit based on axis):")
        print(f"    Predicted: {smart_result.predicted_axis}, Correct: {smart_result.correct_axis}")
        print(f"    Confidence: {smart_result.confidence:.2f}")
        print(f"    Mechanism engaged: {smart_result.mechanism_engaged} (actin {smart_result.actin_fold_12h:.2f}×)")
        print(f"    Death: {smart_result.death_48h:.1%}, Viability: {smart_result.viability_48h:.1%}")
        print(f"    Interventions: {smart_result.interventions_used}/2")
        print(f"    Valid attempt: {smart_result.valid_attempt}")
        print(f"    Reward: {smart_result.reward_total:.2f}")

        # Smart should succeed on all criteria
        assert smart_result.correct_axis, (
            f"Smart should correctly identify {compound_id}: "
            f"predicted={smart_result.predicted_axis}, true={compound.true_stress_axis}"
        )

        assert smart_result.death_48h <= 0.20, (
            f"Smart should stay within death budget for {compound_id}: "
            f"death={smart_result.death_48h:.1%} (should be ≤20%)"
        )

        assert smart_result.interventions_used <= 2, (
            f"Smart should stay within intervention budget for {compound_id}: "
            f"interventions={smart_result.interventions_used} (should be ≤2)"
        )

        assert smart_result.valid_attempt, (
            f"Smart should make valid attempt for {compound_id}"
        )

        # For microtubule axis, should engage mechanism
        if compound.true_stress_axis == "microtubule":
            assert smart_result.mechanism_engaged, (
                f"Smart should engage mechanism for microtubule compound {compound_id}: "
                f"actin_fold_12h={smart_result.actin_fold_12h:.2f}× (should be ≥1.20×)"
            )

        results[compound_id] = smart_result
        print(f"    ✓ Smart succeeds on all criteria")

    # Verify smart dominates naive and greedy on weak subset
    print(f"\n=== Smart vs Naive/Greedy Comparison (Weak Subset) ===")
    for compound_id in WEAK_SIGNATURE_SUBSET:
        compound = PHASE5_LIBRARY[compound_id]

        smart_reward = results[compound_id].reward_total
        naive_reward = run_naive_policy(compound).reward_total
        greedy_reward = run_greedy_policy(compound).reward_total

        print(f"\n{compound_id}:")
        print(f"  Smart:  {smart_reward:>6.2f}")
        print(f"  Naive:  {naive_reward:>6.2f}")
        print(f"  Greedy: {greedy_reward:>6.2f}")

        assert smart_reward > naive_reward, (
            f"Smart should beat naive on {compound_id}: "
            f"{smart_reward:.2f} vs {naive_reward:.2f}"
        )

        assert smart_reward > greedy_reward, (
            f"Smart should beat greedy on {compound_id}: "
            f"{smart_reward:.2f} vs {greedy_reward:.2f}"
        )

    print(f"\n✓ PASSED: Smart policy succeeds on all compounds and dominates baselines")


if __name__ == "__main__":
    test_epistemic_control_baselines_fail_on_weak_subset()
    test_epistemic_control_smart_policy_succeeds_on_all()
    print("\n=== Phase 5: Epistemic Control Tests Complete ===")
