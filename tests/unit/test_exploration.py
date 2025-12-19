"""
Phase 4 Option 2: Exploration test (unknown compound axis).

Forces agent to explore by hiding stress_axis.
Agent must run assays and infer axis from signatures.

Reward includes information bonus for correct identification.
"""

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.masked_compound import (
    MASKED_COMPOUND_LIBRARY,
    exploration_policy_template,
    compute_exploration_reward
)


def test_masked_compound_exploration():
    """
    Test that agent can infer stress axis from assay signatures.

    Setup:
    - Three masked compounds (A, B, C) with hidden axes
    - Agent doses at 0h, assays at 12h, classifies axis
    - Reward includes bonus for correct identification

    Expected:
    - Agent correctly identifies all three axes
    - Information bonus incentivizes exploration
    - Misclassification is penalized
    """
    print("\n=== Masked Compound Exploration Test ===")

    results = {}

    for compound_id, masked_compound in MASKED_COMPOUND_LIBRARY.items():
        print(f"\n--- Testing {compound_id} (true axis: {masked_compound.true_stress_axis}) ---")

        # Initialize VM
        vm = BiologicalVirtualMachine(seed=42)
        vm.seed_vessel("explore", "A549", 1e6, capacity=1e7, initial_viability=0.98)

        # Run exploration policy
        predicted_axis, assay_data = exploration_policy_template(
            vm=vm,
            vessel_id="explore",
            masked_compound=masked_compound,
            dose_fraction=1.0
        )

        # Print assay signatures
        print(f"  ER fold: {assay_data['er_fold']:.2f}×, UPR fold: {assay_data['upr_fold']:.2f}×")
        print(f"  Mito fold: {assay_data['mito_fold']:.2f}×, ATP fold: {assay_data['atp_fold']:.2f}×")
        print(f"  Actin fold: {assay_data['actin_fold']:.2f}×, Trafficking fold: {assay_data['trafficking_fold']:.2f}×")

        # Classification result
        if predicted_axis is None:
            print(f"  Prediction: FAILED (ambiguous signatures)")
            correct = False
        else:
            print(f"  Prediction: {predicted_axis}")
            print(f"  Ground truth: {masked_compound.true_stress_axis}")
            correct = (predicted_axis == masked_compound.true_stress_axis)
            print(f"  Correct: {correct}")

        results[compound_id] = {
            'predicted': predicted_axis,
            'true': masked_compound.true_stress_axis,
            'correct': correct,
            'assay_data': assay_data
        }

    # Assertions

    # 1. All compounds should be classifiable (no ambiguity)
    for compound_id, result in results.items():
        assert result['predicted'] is not None, (
            f"{compound_id}: Prediction failed (signatures ambiguous or too weak)"
        )

    # 2. All axes should be correctly identified
    correct_count = sum(1 for r in results.values() if r['correct'])
    accuracy = correct_count / len(results)

    print(f"\n=== Classification Accuracy ===")
    print(f"Correct: {correct_count}/{len(results)} ({accuracy:.0%})")

    for compound_id, result in results.items():
        status = "✓" if result['correct'] else "✗"
        print(f"{status} {compound_id}: predicted={result['predicted']}, true={result['true']}")

    assert accuracy == 1.0, (
        f"All axes should be correctly identified: {correct_count}/{len(results)}"
    )

    print(f"\n✓ PASSED: All masked compounds correctly identified from signatures")


def test_exploration_reward_bonus():
    """
    Test that information bonus incentivizes correct axis identification.

    Scenario:
    - Agent explores compound_C (microtubule / paclitaxel)
    - Correct identification: +0.5 bonus
    - Incorrect identification: -0.5 penalty
    - No prediction: 0 bonus

    Expected:
    - Correct prediction increases reward
    - Incorrect prediction decreases reward
    - Bonus is meaningful relative to other components
    """
    print("\n=== Exploration Reward Bonus Test ===")

    # Initialize VM and run exploration
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("explore", "A549", 1e6, capacity=1e7, initial_viability=0.98)

    masked_compound = MASKED_COMPOUND_LIBRARY["compound_C"]
    predicted_axis, assay_data = exploration_policy_template(
        vm=vm,
        vessel_id="explore",
        masked_compound=masked_compound,
        dose_fraction=1.0
    )

    # Continue to 48h to measure death
    vm.advance_time(36.0)
    vessel = vm.vessel_states["explore"]
    viability_48h = vessel.viability
    washout_count = 0
    feed_count = 0

    # Compute mechanism hit (actin threshold)
    actin_fold = assay_data['actin_fold']
    mechanism_hit = (actin_fold >= 1.4)

    print(f"\nEpisode results:")
    print(f"  Mechanism hit: {mechanism_hit} (actin {actin_fold:.2f}×)")
    print(f"  Viability at 48h: {viability_48h:.1%}")
    print(f"  Predicted axis: {predicted_axis}")
    print(f"  True axis: {masked_compound.true_stress_axis}")

    # Compute rewards under three scenarios
    scenarios = {
        'Correct prediction': predicted_axis,
        'Incorrect prediction': 'er_stress' if predicted_axis != 'er_stress' else 'mitochondrial',
        'No prediction': None
    }

    print(f"\n{'='*70}")
    print(f"{'Scenario':<25} {'Info Bonus':<15} {'Total Reward':<15}")
    print(f"{'='*70}")

    rewards = {}
    for scenario_name, pred_axis in scenarios.items():
        reward, components = compute_exploration_reward(
            mechanism_hit=mechanism_hit,
            viability_48h=viability_48h,
            washout_count=washout_count,
            feed_count=feed_count,
            predicted_axis=pred_axis,
            true_axis=masked_compound.true_stress_axis
        )

        rewards[scenario_name] = reward
        info_bonus = components['reward_info_bonus']

        print(f"{scenario_name:<25} {info_bonus:>14.2f} {reward:>14.2f}")

    # Assertions

    # 1. Correct prediction should have highest reward
    assert rewards['Correct prediction'] > rewards['No prediction'], (
        f"Correct prediction should beat no prediction: "
        f"{rewards['Correct prediction']:.2f} vs {rewards['No prediction']:.2f}"
    )

    assert rewards['Correct prediction'] > rewards['Incorrect prediction'], (
        f"Correct prediction should beat incorrect prediction: "
        f"{rewards['Correct prediction']:.2f} vs {rewards['Incorrect prediction']:.2f}"
    )

    # 2. Incorrect prediction should be penalized (worse than no prediction)
    assert rewards['Incorrect prediction'] < rewards['No prediction'], (
        f"Incorrect prediction should be penalized: "
        f"{rewards['Incorrect prediction']:.2f} vs {rewards['No prediction']:.2f}"
    )

    # 3. Bonus magnitude should be meaningful (0.5 by default)
    bonus_magnitude = rewards['Correct prediction'] - rewards['No prediction']
    assert abs(bonus_magnitude - 0.5) < 0.01, (
        f"Info bonus should be 0.5: {bonus_magnitude:.2f}"
    )

    penalty_magnitude = rewards['No prediction'] - rewards['Incorrect prediction']
    assert abs(penalty_magnitude - 0.5) < 0.01, (
        f"Info penalty should be 0.5: {penalty_magnitude:.2f}"
    )

    print(f"\n=== Reward Deltas ===")
    print(f"Correct vs No prediction: +{bonus_magnitude:.2f}")
    print(f"No prediction vs Incorrect: +{penalty_magnitude:.2f}")

    print(f"\n✓ PASSED: Information bonus incentivizes exploration")


if __name__ == "__main__":
    test_masked_compound_exploration()
    test_exploration_reward_bonus()
    print("\n=== Phase 4 Option 2: Exploration Tests Complete ===")
