"""
Agent 2 Phase 2: Scenario A - Overconfident Mechanism Posterior Reproduction

Mission: Reproduce a case where system claims high confidence but is wrong.

Success criteria:
- Posterior confidence > 0.85 (high claimed confidence)
- Ground truth mechanism differs from predicted
- System does NOT refuse or hedge
- Extract evidence trajectory, confidence path, debt impact
"""

import numpy as np
from src.cell_os.hardware.mechanism_posterior_v2 import (
    compute_mechanism_posterior_v2,
    Mechanism,
    NuisanceModel,
    MechanismPosterior,
)


def test_overconfident_on_ambiguous_features():
    """
    Test: Create features near decision boundary between ER_STRESS and MICROTUBULE.

    Agent 2 ambiguity capping should prevent high confidence, but let's verify.
    """
    print("=" * 70)
    print("Scenario A: Overconfident Mechanism Posterior")
    print("=" * 70)

    # Construct observation near ER_STRESS/MICROTUBULE boundary
    # ER_STRESS signature: [1.0, 1.0, 1.5] (high ER)
    # MICROTUBULE signature: [1.6, 1.0, 1.0] (high actin)
    # Ambiguous: mix of both

    actin_fold = 1.3  # Between ER (1.0) and MICRO (1.6)
    mito_fold = 1.0   # Neutral
    er_fold = 1.25    # Between ER (1.5) and MICRO (1.0)

    # Low nuisance (clean observation)
    nuisance = NuisanceModel(
        context_shift=np.array([0.0, 0.0, 0.0]),
        pipeline_shift=np.array([0.0, 0.0, 0.0]),
        contact_shift=np.array([0.0, 0.0, 0.0]),
        artifact_var=0.01,
        heterogeneity_var=0.02,
        context_var=0.01,
        pipeline_var=0.01,
        contact_var=0.01,
    )

    posterior = compute_mechanism_posterior_v2(
        actin_fold=actin_fold,
        mito_fold=mito_fold,
        er_fold=er_fold,
        nuisance=nuisance,
    )

    print(f"\nObservation: actin={actin_fold:.2f}, mito={mito_fold:.2f}, er={er_fold:.2f}")
    print(f"\nPosterior probabilities:")
    for mech, prob in sorted(posterior.probabilities.items(), key=lambda x: -x[1]):
        print(f"  {mech.value:20s}: {prob:.4f}")

    print(f"\nTop mechanism: {posterior.top_mechanism.value}")
    print(f"Top probability: {posterior.top_probability:.4f}")
    print(f"Margin (top - 2nd): {posterior.margin:.4f}")

    # Agent 2 fields
    print(f"\nAgent 2 Ambiguity Detection:")
    print(f"  Uncertainty: {posterior.uncertainty:.4f}")
    print(f"  Is ambiguous: {posterior.is_ambiguous}")
    print(f"  Likelihood gap: {posterior.likelihood_gap:.4f}")

    # Check if ambiguity capping worked
    if posterior.is_ambiguous:
        print(f"\n✓ Ambiguity detected (gap={posterior.likelihood_gap:.3f} < 0.15)")
        if posterior.top_probability <= 0.75:
            print(f"✓ Confidence capped at {posterior.top_probability:.3f} ≤ 0.75")
        else:
            print(f"✗ FAILURE: Confidence NOT capped: {posterior.top_probability:.3f} > 0.75")
            print(f"   Agent 2 capping should have limited confidence to 0.75")
            return False
    else:
        print(f"\n⚠️  NOT ambiguous (gap={posterior.likelihood_gap:.3f} ≥ 0.15)")
        print(f"   Mechanisms are sufficiently separated")

    # Check if this would commit in governance
    from src.cell_os.epistemic_agent.governance.contract import (
        decide_governance,
        GovernanceInputs,
        GovernanceThresholds,
    )

    # Convert to governance inputs
    gov_inputs = GovernanceInputs(
        posterior={m.value: p for m, p in posterior.probabilities.items()},
        nuisance_prob=posterior.nuisance_probability,
        evidence_strength=0.8,  # Assume strong evidence
    )

    gov_decision = decide_governance(gov_inputs)

    print(f"\nGovernance Decision:")
    print(f"  Action: {gov_decision.action.value}")
    print(f"  Reason: {gov_decision.reason}")
    if gov_decision.blockers:
        print(f"  Blockers: {[b.value for b in gov_decision.blockers]}")

    # FAILURE MODE: If ambiguous but still commits
    if posterior.is_ambiguous and gov_decision.action.value == "COMMIT":
        print(f"\n✗ EPISTEMIC FAILURE DETECTED:")
        print(f"   Posterior is AMBIGUOUS (gap={posterior.likelihood_gap:.3f})")
        print(f"   But governance COMMITTED to {gov_decision.mechanism}")
        print(f"   Ambiguity information not integrated into governance!")
        return False

    print(f"\n✓ No overconfidence detected in this scenario")
    return True


def test_overconfident_with_high_nuisance():
    """
    Test: High nuisance should reduce confidence, but does it?

    Construct observation where mechanism signal is weak but nuisance doesn't
    fully explain it away.
    """
    print("\n" + "=" * 70)
    print("Scenario A.2: Overconfidence Despite High Nuisance")
    print("=" * 70)

    # Weak signal (near baseline)
    actin_fold = 1.1
    mito_fold = 1.05
    er_fold = 1.08

    # High nuisance (lots of variance inflation)
    nuisance = NuisanceModel(
        context_shift=np.array([0.05, 0.03, 0.04]),  # Small mean shifts
        pipeline_shift=np.array([0.02, 0.01, 0.02]),
        contact_shift=np.array([0.0, 0.0, 0.0]),
        artifact_var=0.05,      # High temporal noise
        heterogeneity_var=0.08,  # High biological variance
        context_var=0.04,
        pipeline_var=0.03,
        contact_var=0.02,
    )

    posterior = compute_mechanism_posterior_v2(
        actin_fold=actin_fold,
        mito_fold=mito_fold,
        er_fold=er_fold,
        nuisance=nuisance,
    )

    print(f"\nObservation: actin={actin_fold:.2f}, mito={mito_fold:.2f}, er={er_fold:.2f}")
    print(f"Nuisance total variance: {nuisance.total_var_inflation:.4f}")
    print(f"\nPosterior probabilities:")
    for mech, prob in sorted(posterior.probabilities.items(), key=lambda x: -x[1]):
        print(f"  {mech.value:20s}: {prob:.4f}")

    print(f"\nNuisance probability: {posterior.nuisance_probability:.4f}")
    print(f"Top mechanism: {posterior.top_mechanism.value}")
    print(f"Top probability: {posterior.top_probability:.4f}")

    # Check governance
    from src.cell_os.epistemic_agent.governance.contract import (
        decide_governance,
        GovernanceInputs,
    )

    gov_inputs = GovernanceInputs(
        posterior={m.value: p for m, p in posterior.probabilities.items()},
        nuisance_prob=posterior.nuisance_probability,
        evidence_strength=0.5,  # Weak signal
    )

    gov_decision = decide_governance(gov_inputs)

    print(f"\nGovernance Decision:")
    print(f"  Action: {gov_decision.action.value}")
    print(f"  Reason: {gov_decision.reason}")
    if gov_decision.blockers:
        print(f"  Blockers: {[b.value for b in gov_decision.blockers]}")

    # EXPECTED: Should be NO_COMMIT or NO_DETECTION (high nuisance, weak signal)
    if gov_decision.action.value == "COMMIT" and posterior.nuisance_probability > 0.35:
        print(f"\n✗ EPISTEMIC FAILURE DETECTED:")
        print(f"   High nuisance probability ({posterior.nuisance_probability:.3f} > 0.35)")
        print(f"   But governance COMMITTED to {gov_decision.mechanism}")
        return False

    print(f"\n✓ High nuisance correctly prevented commitment")
    return True


def test_construct_ground_truth_mismatch():
    """
    Test: Explicitly construct case where posterior is confident but wrong.

    This requires ground truth, which mechanism_posterior doesn't have.
    We simulate by:
    1. Creating observation from TRUE mechanism (e.g., ER_STRESS)
    2. Adding noise/nuisance to confuse classifier
    3. Checking if posterior picks wrong mechanism with high confidence
    """
    print("\n" + "=" * 70)
    print("Scenario A.3: Ground Truth Mismatch (Simulated)")
    print("=" * 70)

    # Ground truth: ER_STRESS [1.0, 1.0, 1.5]
    # But add noise + nuisance to make it look like MICROTUBULE

    # Start with ER signature
    true_actin = 1.0
    true_mito = 1.0
    true_er = 1.5

    # Add noise toward MICROTUBULE direction (high actin, low ER)
    noise = np.random.RandomState(42)
    actin_fold = true_actin + 0.4 + noise.normal(0, 0.1)  # Push toward 1.6 (MICRO)
    mito_fold = true_mito + noise.normal(0, 0.1)
    er_fold = true_er - 0.3 + noise.normal(0, 0.1)  # Pull away from 1.5

    print(f"\nGround truth mechanism: ER_STRESS")
    print(f"True signature: actin=1.0, mito=1.0, er=1.5")
    print(f"Noisy observation: actin={actin_fold:.2f}, mito={mito_fold:.2f}, er={er_fold:.2f}")

    # Low nuisance (so posterior will be confident)
    nuisance = NuisanceModel(
        context_shift=np.array([0.0, 0.0, 0.0]),
        pipeline_shift=np.array([0.0, 0.0, 0.0]),
        contact_shift=np.array([0.0, 0.0, 0.0]),
        artifact_var=0.01,
        heterogeneity_var=0.02,
        context_var=0.01,
        pipeline_var=0.01,
        contact_var=0.01,
    )

    posterior = compute_mechanism_posterior_v2(
        actin_fold=actin_fold,
        mito_fold=mito_fold,
        er_fold=er_fold,
        nuisance=nuisance,
    )

    print(f"\nPosterior probabilities:")
    for mech, prob in sorted(posterior.probabilities.items(), key=lambda x: -x[1]):
        marker = "→" if mech.value == "er_stress" else "  "
        print(f"{marker} {mech.value:20s}: {prob:.4f}")

    print(f"\nPredicted: {posterior.top_mechanism.value}")
    print(f"Confidence: {posterior.top_probability:.4f}")

    # Check if wrong
    if posterior.top_mechanism.value != "er_stress":
        print(f"\n✗ MISCLASSIFICATION:")
        print(f"   Ground truth: er_stress")
        print(f"   Predicted: {posterior.top_mechanism.value}")
        print(f"   Confidence: {posterior.top_probability:.4f}")

        if posterior.top_probability > 0.85:
            print(f"\n✗ OVERCONFIDENT MISCLASSIFICATION:")
            print(f"   System is WRONG (predicted {posterior.top_mechanism.value})")
            print(f"   But CONFIDENT ({posterior.top_probability:.3f} > 0.85)")
            print(f"   This is the failure mode Agent 2 must prevent!")
            return False
        else:
            print(f"\n⚠️  Misclassified but not overconfident ({posterior.top_probability:.3f} ≤ 0.85)")
    else:
        print(f"\n✓ Correct classification despite noise")

    return True


if __name__ == "__main__":
    print("Agent 2 Phase 2: Reproducing Overconfident Mechanism Posterior")
    print("\n")

    results = []

    results.append(("Ambiguous features", test_overconfident_on_ambiguous_features()))
    results.append(("High nuisance", test_overconfident_with_high_nuisance()))
    results.append(("Ground truth mismatch", test_construct_ground_truth_mismatch()))

    print("\n" + "=" * 70)
    print("SCENARIO A RESULTS")
    print("=" * 70)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    all_passed = all(p for _, p in results)

    if all_passed:
        print("\n✓ All scenarios passed - Agent 2 ambiguity capping prevents overconfidence")
    else:
        print("\n✗ FAILURES DETECTED - System can be overconfident when wrong")
        print("   Agent 2 must address these failure modes")
