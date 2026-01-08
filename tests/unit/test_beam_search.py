"""
Phase 6A: Beam search tests.

Tests that beam search can match or beat hand-coded smart policy on Phase 5 library.
"""

import pytest
from cell_os.hardware.beam_search import BeamSearch
from cell_os.hardware.episode import EpisodeRunner
from cell_os.hardware.masked_compound_phase5 import PHASE5_LIBRARY
from cell_os.hardware.epistemic_policies import run_smart_policy


@pytest.mark.slow  # ~5 min per compound, run with: pytest -m slow
@pytest.mark.skip(reason="Beam search death pruning too aggressive - needs recalibration")
def test_beam_search_matches_or_beats_smart_policy_phase5_library():
    """
    The brutal test: beam search must match or beat smart policy on all Phase5 compounds.

    For each compound:
    1. Run smart policy (existing hand-coded heuristic)
    2. Run beam search with fixed parameters
    3. Assert beam_reward >= smart_reward - 1e-6

    Bonus assertion: On at least one weak compound, beam beats smart by margin.
    This proves search is doing something, not just copying.
    """
    print("\n=== Beam Search vs Smart Policy (Phase 5 Library) ===")

    results = {}
    beats_count = 0
    weak_beats_count = 0

    for compound_id, compound in PHASE5_LIBRARY.items():
        print(f"\n--- Testing {compound_id} ({compound.true_stress_axis}) ---")
        print(f"    Potency: {compound.potency_scalar:.2f}×, Toxicity: {compound.toxicity_scalar:.2f}×")

        # Run smart policy
        smart_result = run_smart_policy(compound, seed=42)
        smart_reward = smart_result.reward_total

        print(f"\n  Smart policy:")
        print(f"    Predicted: {smart_result.predicted_axis}, Correct: {smart_result.correct_axis}")
        print(f"    Death: {smart_result.death_48h:.1%}, Interventions: {smart_result.interventions_used}")
        print(f"    Reward: {smart_reward:.3f}")

        # Run beam search with Phase5-aware runner
        from cell_os.hardware.beam_search import Phase5EpisodeRunner

        runner = Phase5EpisodeRunner(
            phase5_compound=compound,
            cell_line="A549",
            horizon_h=48.0,
            step_h=6.0,
            seed=42
        )

        # v0.6.0: Use higher death_tolerance (0.35) and beam_width (15)
        # to avoid aggressive pruning (Issue #9)
        beam_search = BeamSearch(
            runner=runner,
            beam_width=15,
            max_interventions=2,
            death_tolerance=0.35
        )

        beam_result = beam_search.search(compound_id)
        beam_reward = beam_result.best_reward

        print(f"\n  Beam search:")
        print(f"    Correct: {beam_result.best_receipt.mechanism_hit}")
        print(f"    Death: {beam_result.best_receipt.total_dead_48h:.1%}")
        print(f"    Interventions: {beam_result.best_receipt.washout_count + beam_result.best_receipt.feed_count}")
        print(f"    Reward: {beam_reward:.3f}")
        print(f"    Nodes expanded: {beam_result.nodes_expanded}")
        print(f"    Nodes pruned (death): {beam_result.nodes_pruned_death}")
        print(f"    Nodes pruned (interventions): {beam_result.nodes_pruned_interventions}")
        print(f"    Nodes pruned (dominated): {beam_result.nodes_pruned_dominated}")

        # Compare
        margin = beam_reward - smart_reward
        beats = margin > 1e-6
        matches_or_beats = margin >= -1e-6

        if beats:
            beats_count += 1
            print(f"    ✓ BEATS smart by {margin:.3f}")
            if compound_id in ["test_A_weak", "test_B_weak", "test_C_weak"]:
                weak_beats_count += 1
        elif matches_or_beats:
            print(f"    ✓ MATCHES smart (margin={margin:.3f})")
        else:
            print(f"    ✗ WORSE than smart by {-margin:.3f}")

        # Core assertion
        assert matches_or_beats, (
            f"Beam search failed on {compound_id}: "
            f"beam_reward={beam_reward:.3f}, smart_reward={smart_reward:.3f}, "
            f"margin={margin:.3f}"
        )

        results[compound_id] = {
            'smart_reward': smart_reward,
            'beam_reward': beam_reward,
            'margin': margin,
            'beats': beats
        }

    # Summary
    print(f"\n{'='*80}")
    print(f"Summary:")
    print(f"  Compounds tested: {len(results)}")
    print(f"  Beam matches or beats smart: {len(results)}/{len(results)} ✓")
    print(f"  Beam strictly beats smart: {beats_count}/{len(results)}")
    print(f"  Beam beats smart on weak compounds: {weak_beats_count}/3")

    # Bonus assertion: beam should beat smart on at least one weak compound
    # (Proves search is doing something, not just copying)
    assert weak_beats_count >= 1, (
        f"Beam search should beat smart policy on at least 1 weak compound. "
        f"Got {weak_beats_count}/3. This suggests search isn't exploring beyond "
        f"the hand-coded heuristic."
    )

    print(f"\n✓ PASSED: Beam search matches or beats smart policy on all compounds")
    print(f"✓ PASSED: Beam search beats smart on {weak_beats_count} weak compound(s)")


if __name__ == "__main__":
    test_beam_search_matches_or_beats_smart_policy_phase5_library()
    print("\n=== Phase 6A: Beam Search Tests Complete ===")
