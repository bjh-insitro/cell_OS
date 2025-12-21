"""
Test noise gate robustness: prevent premature/lucky gate earning.

These tests enforce that the calibration gate cannot be earned due to
luck-based low-variance samples. Gate must be statistically earned with:
1. Minimum sample size (N_min)
2. Sequential stability (K consecutive stable windows)
3. Bounded false-earn risk
"""

from cell_os.epistemic_agent.beliefs.state import BeliefState
from cell_os.epistemic_agent.schemas import ConditionSummary


def test_gate_requires_minimum_n():
    """Gate cannot be earned before minimum sample size, even with perfect data."""
    beliefs = BeliefState()
    diagnostics = []

    # Simulate 8 perfect replicates (unrealistically low variance)
    # This should NOT earn the gate - not enough information yet
    perfect_condition = ConditionSummary(
        cell_line="A549",
        compound="DMSO",
        dose_uM=0.0,
        time_h=24.0,
        assay="cell_painting",
        position_tag="center",
        n_wells=8,
        mean=1.0,
        std=0.01,  # Unrealistically low variance
        sem=0.0035,
        cv=0.01,
        min_val=0.99,
        max_val=1.01,
        feature_means={},
        feature_stds={},
        n_failed=0,
        n_outliers=0,
    )

    beliefs._update_noise_beliefs([perfect_condition], diagnostics)

    # Gate should NOT be stable yet - not enough samples
    assert not beliefs.noise_sigma_stable, \
        f"Gate earned prematurely at N={beliefs.noise_df_total} with perfect data! " \
        f"rel_width={beliefs.noise_rel_width:.4f}"


def test_gate_requires_sequential_stability():
    """Gate requires K consecutive stable observations, not one lucky window."""
    beliefs = BeliefState()
    diagnostics = []

    # First batch: 40 replicates with moderate variance (gate threshold)
    batch1 = ConditionSummary(
        cell_line="A549",
        compound="DMSO",
        dose_uM=0.0,
        time_h=24.0,
        assay="cell_painting",
        position_tag="center",
        n_wells=40,
        mean=1.0,
        std=0.05,
        sem=0.0079,
        cv=0.05,
        min_val=0.90,
        max_val=1.10,
        feature_means={},
        feature_stds={},
        n_failed=0,
        n_outliers=0,
    )

    beliefs._update_noise_beliefs([batch1], diagnostics)
    cycle1_df = beliefs.noise_df_total
    cycle1_rel_width = beliefs.noise_rel_width
    cycle1_stable = beliefs.noise_sigma_stable

    # Second batch: Another 12 replicates with VERY low variance (lucky!)
    # This single lucky batch should NOT earn the gate
    batch2_lucky = ConditionSummary(
        cell_line="A549",
        compound="DMSO",
        dose_uM=0.0,
        time_h=24.0,
        assay="cell_painting",
        position_tag="center",
        n_wells=12,
        mean=1.0,
        std=0.01,  # Suddenly very tight!
        sem=0.0029,
        cv=0.01,
        min_val=0.98,
        max_val=1.02,
        feature_means={},
        feature_stds={},
        n_failed=0,
        n_outliers=0,
    )

    beliefs._update_noise_beliefs([batch2_lucky], diagnostics)
    cycle2_df = beliefs.noise_df_total
    cycle2_rel_width = beliefs.noise_rel_width
    cycle2_stable = beliefs.noise_sigma_stable

    # Gate should NOT earn from one lucky batch
    # Must see stability across multiple batches
    assert not cycle2_stable, \
        f"Gate earned from ONE lucky batch! " \
        f"Cycle 1: df={cycle1_df}, rel_width={cycle1_rel_width:.4f}, stable={cycle1_stable}. " \
        f"Cycle 2: df={cycle2_df}, rel_width={cycle2_rel_width:.4f}, stable={cycle2_stable}. " \
        f"This is luck-based earning - violates sequential stability requirement."


def test_gate_earns_with_sustained_stability():
    """Gate SHOULD earn when stability is sustained across K cycles.

    Strategy: First cross df_min threshold (40), then accumulate K=3 consecutive stable observations.
    """
    beliefs = BeliefState()
    diagnostics = []

    # Batch 1: 25 replicates - still below df_min (df=24)
    stable_batch_large = ConditionSummary(
        cell_line="A549",
        compound="DMSO",
        dose_uM=0.0,
        time_h=24.0,
        assay="cell_painting",
        position_tag="center",
        n_wells=25,
        mean=1.0,
        std=0.04,  # Consistently narrow variance
        sem=0.0080,
        cv=0.04,
        min_val=0.92,
        max_val=1.08,
        feature_means={},
        feature_stds={},
        n_failed=0,
        n_outliers=0,
    )
    beliefs._update_noise_beliefs([stable_batch_large], diagnostics)
    assert not beliefs.noise_sigma_stable, "Not stable yet (df < 40)"
    assert beliefs.noise_gate_streak == 0, "Streak should be 0 (not enough data)"

    # Batch 2: Another 25 replicates - now df=48 >= 40, start counting streak
    beliefs._update_noise_beliefs([stable_batch_large], diagnostics)
    assert not beliefs.noise_sigma_stable, "Not stable yet (streak=1, need 3)"
    assert beliefs.noise_gate_streak == 1, f"Streak should be 1, got {beliefs.noise_gate_streak}"

    # Batch 3: Another 25 replicates - streak=2
    beliefs._update_noise_beliefs([stable_batch_large], diagnostics)
    assert not beliefs.noise_sigma_stable, "Not stable yet (streak=2, need 3)"
    assert beliefs.noise_gate_streak == 2, f"Streak should be 2, got {beliefs.noise_gate_streak}"

    # Batch 4: Another 25 replicates - streak=3, gate earned!
    beliefs._update_noise_beliefs([stable_batch_large], diagnostics)
    assert beliefs.noise_sigma_stable, \
        f"Gate should be earned after K=3 consecutive stable observations! " \
        f"df={beliefs.noise_df_total}, rel_width={beliefs.noise_rel_width:.4f}, streak={beliefs.noise_gate_streak}"


def test_gate_revokes_on_instability():
    """Gate should revoke when confidence degrades (rel_width exceeds exit threshold).

    Note: With pooled variance and high df, variance increases don't easily trigger revocation
    because confidence stays high. Revocation happens when:
    1. Drift is detected (requires 10+ cycles of history), OR
    2. Confidence degrades (rel_width >= exit_threshold)

    This test demonstrates case 2 by introducing high variance that pushes rel_width over 0.40.
    """
    beliefs = BeliefState()
    diagnostics = []

    # First, earn the gate with moderate sample sizes
    stable_batch = ConditionSummary(
        cell_line="A549",
        compound="DMSO",
        dose_uM=0.0,
        time_h=24.0,
        assay="cell_painting",
        position_tag="center",
        n_wells=15,  # Smaller batches for faster test
        mean=1.0,
        std=0.04,
        sem=0.0103,
        cv=0.04,
        min_val=0.92,
        max_val=1.08,
        feature_means={},
        feature_stds={},
        n_failed=0,
        n_outliers=0,
    )

    # Need more batches with smaller n_wells to cross df_min and earn gate
    # 15 wells → df=14 per batch. Need 3 batches to get df=42, then 3 more for streak
    for i in range(6):
        beliefs._update_noise_beliefs([stable_batch], diagnostics)

    assert beliefs.noise_sigma_stable, f"Gate should be earned, streak={beliefs.noise_gate_streak}"

    # Now introduce very high variance with small sample (degrades confidence)
    # This combination should push rel_width over exit_threshold (0.40)
    unstable_batch = ConditionSummary(
        cell_line="A549",
        compound="DMSO",
        dose_uM=0.0,
        time_h=24.0,
        assay="cell_painting",
        position_tag="center",
        n_wells=8,  # Small sample
        mean=1.0,
        std=0.50,  # Very high variance!
        sem=0.177,
        cv=0.50,
        min_val=0.00,
        max_val=2.00,
        feature_means={},
        feature_stds={},
        n_failed=0,
        n_outliers=0,
    )

    # Add multiple high-variance batches to degrade confidence
    for _ in range(4):
        beliefs._update_noise_beliefs([unstable_batch], diagnostics)
        if not beliefs.noise_sigma_stable:
            break  # Gate revoked

    # Gate should revoke when rel_width crosses exit_threshold
    assert not beliefs.noise_sigma_stable, \
        f"Gate should revoke when confidence degrades! " \
        f"rel_width={beliefs.noise_rel_width:.4f}, exit_threshold=0.40"


def test_gate_streak_resets_on_instability():
    """Stability streak should reset if an unstable batch is observed."""
    beliefs = BeliefState()
    diagnostics = []

    # Batch 1: stable
    stable_batch = ConditionSummary(
        cell_line="A549",
        compound="DMSO",
        dose_uM=0.0,
        time_h=24.0,
        assay="cell_painting",
        position_tag="center",
        n_wells=20,
        mean=1.0,
        std=0.04,
        sem=0.0089,
        cv=0.04,
        min_val=0.92,
        max_val=1.08,
        feature_means={},
        feature_stds={},
        n_failed=0,
        n_outliers=0,
    )
    beliefs._update_noise_beliefs([stable_batch], diagnostics)

    # Batch 2: unstable (high variance)
    unstable_batch = ConditionSummary(
        cell_line="A549",
        compound="DMSO",
        dose_uM=0.0,
        time_h=24.0,
        assay="cell_painting",
        position_tag="center",
        n_wells=20,
        mean=1.0,
        std=0.12,  # Too wide
        sem=0.0268,
        cv=0.12,
        min_val=0.76,
        max_val=1.24,
        feature_means={},
        feature_stds={},
        n_failed=0,
        n_outliers=0,
    )
    beliefs._update_noise_beliefs([unstable_batch], diagnostics)

    assert not beliefs.noise_sigma_stable, "Not stable yet"

    # Batch 3: stable again
    beliefs._update_noise_beliefs([stable_batch], diagnostics)
    assert not beliefs.noise_sigma_stable, "Still not stable (streak was reset)"

    # Batch 4: stable again
    beliefs._update_noise_beliefs([stable_batch], diagnostics)
    assert not beliefs.noise_sigma_stable, "Still not stable (need one more)"

    # Batch 5: stable again (3rd consecutive)
    beliefs._update_noise_beliefs([stable_batch], diagnostics)
    assert beliefs.noise_sigma_stable, \
        "NOW stable after 3 consecutive stable batches (streak reset counted correctly)"


if __name__ == "__main__":
    # Run tests manually for debugging
    print("Testing gate robustness...")

    try:
        test_gate_requires_minimum_n()
        print("✓ test_gate_requires_minimum_n PASSED")
    except AssertionError as e:
        print(f"✗ test_gate_requires_minimum_n FAILED: {e}")

    try:
        test_gate_requires_sequential_stability()
        print("✓ test_gate_requires_sequential_stability PASSED")
    except AssertionError as e:
        print(f"✗ test_gate_requires_sequential_stability FAILED: {e}")

    try:
        test_gate_earns_with_sustained_stability()
        print("✓ test_gate_earns_with_sustained_stability PASSED")
    except AssertionError as e:
        print(f"✗ test_gate_earns_with_sustained_stability FAILED: {e}")

    try:
        test_gate_revokes_on_instability()
        print("✓ test_gate_revokes_on_instability PASSED")
    except AssertionError as e:
        print(f"✗ test_gate_revokes_on_instability FAILED: {e}")

    try:
        test_gate_streak_resets_on_instability()
        print("✓ test_gate_streak_resets_on_instability PASSED")
    except AssertionError as e:
        print(f"✗ test_gate_streak_resets_on_instability FAILED: {e}")
