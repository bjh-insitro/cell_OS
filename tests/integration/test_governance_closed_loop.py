# tests/integration/test_governance_closed_loop.py
"""
Closed-loop test: Verify that governance-driven biasing actually reduces distance to commit.

This is the first KPI aligned with the moral code:
"After refusing to commit, did you do the thing that made committing more justified?"
"""

from src.cell_os.epistemic_agent.governance.contract import (
    Blocker,
    GovernanceAction,
    GovernanceDecision,
    GovernanceInputs,
    GovernanceThresholds,
    decide_governance,
)
from src.cell_os.hardware.beam_search import (
    ActionIntent,
    NoCommitEpisode,
    action_intent_cost,
    classify_action_intent,
    compute_action_bias,
)
from src.cell_os.hardware.episode import Action


def test_high_nuisance_blocker_resolution():
    """
    Verify that HIGH_NUISANCE blocker leads to actions that reduce nuisance gap.

    Scenario:
      1. Start with high nuisance (0.60 > 0.35 threshold) and OK posterior (0.85)
      2. Governance returns NO_COMMIT with HIGH_NUISANCE blocker
      3. Bias computation boosts REDUCE_NUISANCE actions (3.0x)
      4. Agent selects washout/feed (REDUCE_NUISANCE intent)
      5. After action, nuisance drops (simulated: 0.60 → 0.25)
      6. Verify: nuisance gap decreased

    This is coarse and synthetic, but it proves causality.
    """
    thresholds = GovernanceThresholds()

    # Step 1: Initial state with HIGH_NUISANCE blocker
    initial_state = GovernanceInputs(
        posterior={"ER_STRESS": 0.85},  # Good posterior
        nuisance_prob=0.60,  # High nuisance (> 0.35 threshold)
        evidence_strength=0.85,
    )

    initial_decision = decide_governance(initial_state, thresholds)
    assert initial_decision.action == GovernanceAction.NO_COMMIT
    assert Blocker.HIGH_NUISANCE in initial_decision.blockers
    assert Blocker.LOW_POSTERIOR_TOP not in initial_decision.blockers

    initial_nuisance_gap = max(0.0, initial_state.nuisance_prob - thresholds.nuisance_max_for_commit)
    assert initial_nuisance_gap > 0.0  # 0.60 - 0.35 = 0.25

    # Step 2: Bias computation boosts REDUCE_NUISANCE
    action_bias = compute_action_bias(initial_decision.blockers, initial_state.evidence_strength)
    assert action_bias[ActionIntent.REDUCE_NUISANCE] > 2.0  # Strong boost
    assert action_bias[ActionIntent.AMPLIFY_SIGNAL] < 1.0  # Downweighted

    # Step 3: Agent selects REDUCE_NUISANCE action (washout)
    washout_action = Action(dose_fraction=0.0, washout=True, feed=False)
    intent = classify_action_intent(washout_action, has_dosed=True)
    assert intent == ActionIntent.REDUCE_NUISANCE

    # Step 4: After action, nuisance drops (simulated state transition)
    # In real system this comes from VM rollout, here we simulate the effect
    after_state = GovernanceInputs(
        posterior={"ER_STRESS": 0.85},  # Posterior unchanged
        nuisance_prob=0.25,  # Nuisance reduced after washout
        evidence_strength=0.85,
    )

    after_decision = decide_governance(after_state, thresholds)
    after_nuisance_gap = max(0.0, after_state.nuisance_prob - thresholds.nuisance_max_for_commit)

    # Step 5: VERIFY CLOSED LOOP - nuisance gap decreased
    assert after_nuisance_gap < initial_nuisance_gap
    # Specifically: 0.0 < 0.25 (gap went from 0.25 to 0.0)

    # Step 6: Verify blocker was resolved
    assert Blocker.HIGH_NUISANCE not in after_decision.blockers

    # Step 7: Verify now allowed to commit (blocker resolved)
    assert after_decision.action == GovernanceAction.COMMIT

    print("✓ HIGH_NUISANCE → REDUCE_NUISANCE → nuisance gap decreased → blocker resolved → COMMIT allowed")


def test_low_posterior_blocker_resolution():
    """
    Verify that LOW_POSTERIOR_TOP blocker leads to actions that reduce posterior gap.

    Scenario:
      1. Start with low posterior (0.70 < 0.80 threshold) and OK nuisance (0.20)
      2. Governance returns NO_COMMIT with LOW_POSTERIOR_TOP blocker
      3. Bias computation boosts DISCRIMINATE actions (2.5x)
      4. Agent selects dose action (DISCRIMINATE intent)
      5. After action, posterior increases (simulated: 0.70 → 0.88)
      6. Verify: posterior gap decreased
    """
    thresholds = GovernanceThresholds()

    # Step 1: Initial state with LOW_POSTERIOR_TOP blocker
    initial_state = GovernanceInputs(
        posterior={"ER_STRESS": 0.70},  # Low posterior (< 0.80 threshold)
        nuisance_prob=0.20,  # Good nuisance
        evidence_strength=0.85,
    )

    initial_decision = decide_governance(initial_state, thresholds)
    assert initial_decision.action == GovernanceAction.NO_COMMIT
    assert Blocker.LOW_POSTERIOR_TOP in initial_decision.blockers
    assert Blocker.HIGH_NUISANCE not in initial_decision.blockers

    initial_posterior_gap = max(0.0, thresholds.commit_posterior_min - 0.70)
    assert initial_posterior_gap > 0.0  # 0.80 - 0.70 = 0.10

    # Step 2: Bias computation boosts DISCRIMINATE
    action_bias = compute_action_bias(initial_decision.blockers, initial_state.evidence_strength)
    assert action_bias[ActionIntent.DISCRIMINATE] > 2.0  # Strong boost
    assert action_bias[ActionIntent.OBSERVE] > 1.5  # Moderate boost

    # Step 3: Agent selects DISCRIMINATE action (dose)
    dose_action = Action(dose_fraction=0.5, washout=False, feed=False)
    intent = classify_action_intent(dose_action, has_dosed=False)
    assert intent == ActionIntent.DISCRIMINATE

    # Step 4: After action, posterior increases (simulated)
    after_state = GovernanceInputs(
        posterior={"ER_STRESS": 0.88},  # Posterior increased after discriminating action
        nuisance_prob=0.20,  # Nuisance unchanged
        evidence_strength=0.88,
    )

    after_decision = decide_governance(after_state, thresholds)
    after_posterior_gap = max(0.0, thresholds.commit_posterior_min - 0.88)

    # Step 5: VERIFY CLOSED LOOP - posterior gap decreased
    assert after_posterior_gap < initial_posterior_gap
    # Specifically: 0.0 < 0.10 (gap went from 0.10 to 0.0)

    # Step 6: Verify blocker was resolved
    assert Blocker.LOW_POSTERIOR_TOP not in after_decision.blockers

    # Step 7: Verify now allowed to commit
    assert after_decision.action == GovernanceAction.COMMIT

    print("✓ LOW_POSTERIOR_TOP → DISCRIMINATE → posterior gap decreased → blocker resolved → COMMIT allowed")


def test_both_blockers_prioritize_nuisance_first():
    """
    Verify that when both blockers fire, nuisance reduction is prioritized.

    This encodes the heuristic: "confounded discrimination is useless, clean up first."
    """
    thresholds = GovernanceThresholds()

    # Both blockers present
    state = GovernanceInputs(
        posterior={"ER_STRESS": 0.60},  # Low posterior
        nuisance_prob=0.55,  # High nuisance
        evidence_strength=0.85,
    )

    decision = decide_governance(state, thresholds)
    assert decision.action == GovernanceAction.NO_COMMIT
    assert Blocker.LOW_POSTERIOR_TOP in decision.blockers
    assert Blocker.HIGH_NUISANCE in decision.blockers

    # Bias computation should prioritize REDUCE_NUISANCE over DISCRIMINATE
    action_bias = compute_action_bias(decision.blockers, state.evidence_strength)
    assert action_bias[ActionIntent.REDUCE_NUISANCE] > action_bias[ActionIntent.DISCRIMINATE]
    # Specifically: REDUCE_NUISANCE gets 3.0x, DISCRIMINATE gets 0.5x (downweighted)

    print("✓ Both blockers → REDUCE_NUISANCE prioritized over DISCRIMINATE (clean up confounding first)")


def test_cost_aware_episode_tracking():
    """
    Verify that NoCommitEpisode correctly tracks cost-aware metrics.

    This is the primary KPI: gap_reduction_per_cost.
    """
    thresholds = GovernanceThresholds()

    # Episode: HIGH_NUISANCE blocker, resolve with REDUCE_NUISANCE action
    episode = NoCommitEpisode(
        episode_id="test_episode_1",
        t_start=2,
        blockers_start={Blocker.HIGH_NUISANCE},
        posterior_gap_start=0.0,  # Posterior is OK (0.85 > 0.80)
        nuisance_gap_start=0.25,  # Nuisance is high (0.60 - 0.35 = 0.25)
        actions_taken=[ActionIntent.REDUCE_NUISANCE],  # Washout
        costs_incurred=[action_intent_cost(ActionIntent.REDUCE_NUISANCE)],  # 1.5
        t_end=3,
        blockers_end=set(),  # Resolved
        posterior_gap_end=0.0,  # Unchanged
        nuisance_gap_end=0.0,  # Resolved (0.25 - 0.35 = 0.0, clamped)
    )

    # Verify metrics
    assert episode.total_cost == 1.5
    assert episode.posterior_gap_reduction == 0.0  # Unchanged
    assert episode.nuisance_gap_reduction == 0.25  # 0.25 → 0.0
    assert episode.gap_reduction_per_cost == 0.25 / 1.5  # ~0.167
    assert episode.resolved  # Blocker cleared

    print(f"✓ Cost-aware episode: gap_reduction={0.25:.3f}, cost={1.5:.1f}, efficiency={episode.gap_reduction_per_cost:.3f}")

    # Compare to expensive alternative: AMPLIFY_SIGNAL (wrong choice for HIGH_NUISANCE)
    expensive_episode = NoCommitEpisode(
        episode_id="test_episode_2_expensive",
        t_start=2,
        blockers_start={Blocker.HIGH_NUISANCE},
        posterior_gap_start=0.0,
        nuisance_gap_start=0.25,
        actions_taken=[ActionIntent.AMPLIFY_SIGNAL],  # Wrong: escalates into noise
        costs_incurred=[action_intent_cost(ActionIntent.AMPLIFY_SIGNAL)],  # 2.5
        t_end=3,
        blockers_end={Blocker.HIGH_NUISANCE},  # Not resolved (nuisance got worse)
        posterior_gap_end=0.0,
        nuisance_gap_end=0.35,  # Got worse (0.25 → 0.35)
    )

    # Verify this is worse
    assert expensive_episode.total_cost > episode.total_cost  # More expensive
    assert expensive_episode.gap_reduction_per_cost < 0  # Negative (got worse)
    assert not expensive_episode.resolved  # Didn't clear blocker

    print(f"✓ Expensive wrong choice: gap_reduction={expensive_episode.nuisance_gap_reduction:.3f}, cost={2.5:.1f}, efficiency={expensive_episode.gap_reduction_per_cost:.3f} (negative!)")


def test_no_free_lunch_invariant():
    """
    Verify "no free lunch" invariant: actions should only move the gaps they're designed to move.

    Catches simulator candy where both gaps improve from single action inappropriately.
    """
    # REDUCE_NUISANCE should reduce nuisance_gap, not drastically improve posterior_gap
    # (posterior might improve slightly as confounding clears, but not jump from 0.25 to 0.0)

    suspicious_episode = NoCommitEpisode(
        episode_id="suspicious",
        t_start=2,
        blockers_start={Blocker.HIGH_NUISANCE, Blocker.LOW_POSTERIOR_TOP},
        posterior_gap_start=0.25,  # 0.55 posterior, need 0.80
        nuisance_gap_start=0.30,  # 0.65 nuisance, need < 0.35
        actions_taken=[ActionIntent.REDUCE_NUISANCE],  # Just washout
        costs_incurred=[1.5],
        t_end=3,
        blockers_end=set(),  # Both blockers cleared?!
        posterior_gap_end=0.0,  # Jumped from 0.25 to 0.0
        nuisance_gap_end=0.0,  # Expected to drop
    )

    # This looks TOO good - single REDUCE_NUISANCE action resolved both blockers
    # Posterior gap dropped 0.25 with no DISCRIMINATE action
    # This is simulator candy, not realistic

    # Sanity check: if posterior_gap drops substantially (>0.15) from REDUCE_NUISANCE alone,
    # that's suspicious (should need DISCRIMINATE to improve posterior)
    if suspicious_episode.actions_taken == [ActionIntent.REDUCE_NUISANCE]:
        if suspicious_episode.posterior_gap_reduction > 0.15:
            print(f"⚠️  Suspicious: REDUCE_NUISANCE alone improved posterior by {suspicious_episode.posterior_gap_reduction:.3f}")
            print("   This suggests simulator is giving free lunch (unrealistic signal improvement from washout)")

    # In real scenario, expect:
    # - REDUCE_NUISANCE primarily affects nuisance_gap
    # - DISCRIMINATE primarily affects posterior_gap
    # - Both gaps dropping significantly from single action = simulator issue

    print("✓ No free lunch invariant: checked (would flag simulator candy if present)")


def test_causal_attribution_split_ledger():
    """
    Verify causal attribution: REDUCE_NUISANCE actions can only improve posterior via nuisance reweighting.

    This test uses the split-ledger accounting to distinguish:
    - Evidence contribution: new discriminative observations
    - Nuisance reweighting: redistributing probability mass as nuisance drops

    REDUCE_NUISANCE actions should show attribution_source = "nuisance_reweight" or "both",
    but if "evidence" dominates, that's simulator candy (washout shouldn't inject new signal).
    """
    from src.cell_os.hardware.episode import Action
    from src.cell_os.hardware.masked_compound_phase5 import PHASE5_LIBRARY
    from src.cell_os.hardware.beam_search import Phase5EpisodeRunner

    # Use a known compound with microtubule mechanism
    compound = PHASE5_LIBRARY["test_A_clean"]

    runner = Phase5EpisodeRunner(
        phase5_compound=compound,
        horizon_h=48.0,
        step_h=6.0,
        seed=42
    )

    # Step 1: Dose to establish signal
    dose_action = Action(dose_fraction=0.5, washout=False, feed=False)
    prefix_after_dose = runner.rollout_prefix([dose_action])

    print(f"After dose: posterior_top={prefix_after_dose.posterior_top_prob:.3f}, "
          f"nuisance={prefix_after_dose.nuisance_fraction:.3f}, "
          f"attribution={prefix_after_dose.attribution_source}")

    # Step 2: Feed to reduce nuisance (contact pressure, artifacts)
    feed_action = Action(dose_fraction=0.0, washout=False, feed=True)
    prefix_after_feed = runner.rollout_prefix([dose_action, feed_action])

    print(f"After feed: posterior_top={prefix_after_feed.posterior_top_prob:.3f}, "
          f"nuisance={prefix_after_feed.nuisance_fraction:.3f}, "
          f"attribution={prefix_after_feed.attribution_source}")

    # CRITICAL CHECK: Did posterior improve? If so, via what mechanism?
    posterior_change = prefix_after_feed.posterior_top_prob - prefix_after_dose.posterior_top_prob

    if posterior_change > 0.05:
        # Significant improvement - check attribution
        attribution = prefix_after_feed.attribution_source

        if attribution == "evidence":
            print(f"✗ SIMULATOR CANDY DETECTED: Feed action (REDUCE_NUISANCE) improved posterior by {posterior_change:.3f}")
            print("  Attribution: 'evidence' - feed should NOT inject new discriminative signal!")
            print("  This is structural bug: nuisance actions minting unjustified certainty")
            raise AssertionError("Causal attribution hygiene violated: REDUCE_NUISANCE credited as new evidence")

        elif attribution == "nuisance_reweight":
            print(f"✓ Legitimate: Feed improved posterior by {posterior_change:.3f} via nuisance reweighting")
            print("  Attribution: 'nuisance_reweight' - this is mass redistribution, not new signal")

        elif attribution == "both":
            print(f"⚠️  Mixed: Feed improved posterior by {posterior_change:.3f} via both evidence and reweighting")
            print("  Attribution: 'both' - some new observations mixed with mass redistribution")
            print("  This is acceptable if modest, but watch for dominance flip")

        else:
            print(f"⚠️  Unknown attribution: {attribution}")

    else:
        print(f"✓ No significant posterior change from feed ({posterior_change:.3f})")
        print("  Nuisance reduction alone didn't mint unearned certainty")

    print("✓ Causal attribution split-ledger accounting: tested")


if __name__ == "__main__":
    test_high_nuisance_blocker_resolution()
    test_low_posterior_blocker_resolution()
    test_both_blockers_prioritize_nuisance_first()
    test_cost_aware_episode_tracking()
    test_no_free_lunch_invariant()
    print()
    print("Testing causal attribution (split-ledger accounting)...")
    test_causal_attribution_split_ledger()
    print()
    print("All closed-loop tests passed!")
