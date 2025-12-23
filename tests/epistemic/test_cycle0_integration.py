"""
Tests for Cycle 0 integration: instrument shape learning gates biology.

These tests prove two critical properties:
1. Gate locks biology: agent refuses biology when calibration_plate_run=False
2. Gate can flip: passing instrument shape summary earns noise gate
"""

from src.cell_os.epistemic_agent.beliefs.state import BeliefState
from src.cell_os.epistemic_agent.acquisition.chooser import TemplateChooser
from src.cell_os.epistemic_agent.schemas import InstrumentShapeSummary, Observation, ConditionSummary
from src.cell_os.epistemic_agent.calibration_constants import (
    CYCLE0_PLATE_ID,
    NOISE_SIGMA_THRESHOLD,
    EDGE_EFFECT_THRESHOLD,
    SPATIAL_RESIDUAL_THRESHOLD,
    REPLICATE_PRECISION_THRESHOLD,
    CHANNEL_COUPLING_THRESHOLD,
)
from datetime import datetime


def test_gate_locks_biology():
    """Test 1: Agent refuses biology when calibration_plate_run=False.

    This proves the Cycle 0 constraint is enforced.
    """
    # Setup: fresh agent with no calibration
    beliefs = BeliefState()
    chooser = TemplateChooser()

    # Verify preconditions
    assert beliefs.calibration_plate_run == False, "Calibration plate should not be run initially"
    assert beliefs.noise_sigma_stable == False, "Noise gate should not be earned initially"

    # Agent tries to choose next action
    decision = chooser.choose_next(
        beliefs=beliefs,
        budget_remaining_wells=384,
        cycle=1
    )

    # Assert: agent is FORCED to run calibration plate
    assert decision.chosen_template == "baseline_replicates", \
        "Agent must choose baseline_replicates template for calibration"

    assert decision.chosen_kwargs.get("purpose") == "instrument_shape_learning", \
        "Decision must be tagged as instrument_shape_learning"

    # Check decision provenance
    rationale = decision.rationale
    assert rationale is not None, "Decision must have rationale"

    # Look at selected_candidate from legacy decision event
    if hasattr(chooser, 'last_decision_event') and chooser.last_decision_event:
        candidate = chooser.last_decision_event.selected_candidate
        assert candidate.get("forced") == True, "Cycle 0 calibration must be forced"
        assert candidate.get("trigger") == "cycle0_required", "Trigger must be cycle0_required"
        assert candidate.get("enforcement_layer") == "global_pre_biology", \
            "Must be enforced at global_pre_biology layer"
        assert candidate.get("calibration_plate_id") == CYCLE0_PLATE_ID, \
            f"Must reference canonical calibration plate {CYCLE0_PLATE_ID}"

    print("✓ Test 1 passed: Gate locks biology (forces calibration when calibration_plate_run=False)")


def test_gate_can_flip_passing():
    """Test 2a: Passing instrument shape summary earns noise gate.

    This proves the gate update logic works correctly.
    """
    # Setup: agent that ran calibration but hasn't processed results yet
    beliefs = BeliefState()

    # Create a PASSING instrument shape summary (all metrics within thresholds)
    passing_summary = InstrumentShapeSummary(
        noise_sigma=0.10,  # < 0.15 threshold
        noise_sigma_ci_width=0.20,
        noise_sigma_df=95,
        edge_effect_strength=0.05,  # < 0.10 threshold
        edge_effect_confident=True,
        spatial_residual_metric=0.05,  # < 0.08 threshold
        spatial_structure_detected=False,
        replicate_precision_score=0.90,  # > 0.85 threshold
        replicate_n_pairs=48,
        channel_coupling_score=0.15,  # < 0.20 threshold
        channel_independence_ok=True,
        noise_gate_pass=True,  # Should pass all checks
        failed_checks=[],
        plate_id=CYCLE0_PLATE_ID,
        n_wells_analyzed=96,
        calibration_timestamp=datetime.now().isoformat()
    )

    # Verify summary passes (sanity check)
    assert passing_summary.noise_gate_pass == True, "Summary should pass all checks"
    assert len(passing_summary.failed_checks) == 0, "No checks should fail"

    # Verify preconditions
    assert beliefs.noise_sigma_stable == False, "Gate should not be earned initially"
    assert beliefs.instrument_shape_learned == False, "Shape not learned yet"
    assert beliefs.calibration_plate_run == False, "Calibration plate not run yet"

    # Update beliefs with instrument shape (this is the gate flip logic)
    beliefs.update_from_instrument_shape(passing_summary, cycle=1)

    # Assert: noise gate is now earned
    assert beliefs.noise_sigma_stable == True, \
        "Noise gate should be earned after passing instrument shape"

    assert beliefs.instrument_shape_learned == True, \
        "Instrument shape should be marked as learned"

    assert beliefs.calibration_plate_run == True, \
        "Calibration plate should be marked as run"

    assert beliefs.instrument_shape is not None, \
        "Instrument shape summary should be stored"

    # Check that events were emitted
    events = beliefs.end_cycle()
    assert len(events) > 0, "Events should be emitted"

    # Look for gate_event in events
    gate_events = [e for e in events if e.evidence and "gate_event" in e.evidence]
    assert len(gate_events) > 0, "Should emit gate_event when gate earned"

    print("✓ Test 2a passed: Gate flips to EARNED when instrument shape passes")


def test_gate_can_flip_failing():
    """Test 2b: Failing instrument shape summary does NOT earn noise gate.

    This proves the gate update logic correctly rejects failing calibrations.
    """
    # Setup: agent that ran calibration
    beliefs = BeliefState()

    # Create a FAILING instrument shape summary (noise sigma too high)
    failing_summary = InstrumentShapeSummary(
        noise_sigma=0.20,  # > 0.15 threshold (FAIL)
        noise_sigma_ci_width=0.30,
        noise_sigma_df=95,
        edge_effect_strength=0.05,  # passes
        edge_effect_confident=True,
        spatial_residual_metric=0.05,  # passes
        spatial_structure_detected=False,
        replicate_precision_score=0.90,  # passes
        replicate_n_pairs=48,
        channel_coupling_score=0.15,  # passes
        channel_independence_ok=True,
        noise_gate_pass=False,  # Should fail
        failed_checks=["noise_sigma"],
        plate_id=CYCLE0_PLATE_ID,
        n_wells_analyzed=96,
        calibration_timestamp=datetime.now().isoformat()
    )

    # Verify summary fails (sanity check)
    assert failing_summary.noise_gate_pass == False, "Summary should fail"
    assert "noise_sigma" in failing_summary.failed_checks, "Noise sigma should fail"

    # Update beliefs with failing shape
    beliefs.update_from_instrument_shape(failing_summary, cycle=1)

    # Assert: noise gate is NOT earned
    assert beliefs.noise_sigma_stable == False, \
        "Noise gate should NOT be earned when instrument shape fails"

    assert beliefs.instrument_shape_learned == True, \
        "Instrument shape still marked as learned (we measured it)"

    assert beliefs.calibration_plate_run == True, \
        "Calibration plate marked as run (even though it failed)"

    # Check events for gate_loss
    events = beliefs.end_cycle()
    gate_loss_events = [e for e in events if e.evidence and "gate_loss" in e.evidence]
    # Note: gate_loss only fires if gate was previously earned, so this might be 0

    print("✓ Test 2b passed: Gate stays LOST when instrument shape fails")


def test_gate_locks_biology_after_calibration_run():
    """Test 3: After calibration plate runs, Cycle 0 constraint no longer forces calibration.

    This proves calibration_plate_run flag properly unlocks biology.
    """
    # Setup: agent with calibration plate run AND gate earned (full success path)
    beliefs = BeliefState()
    beliefs.calibration_plate_run = True  # Marked as run
    beliefs.noise_sigma_stable = True     # Gate earned (so we can proceed to biology)
    beliefs.noise_rel_width = 0.20        # Good enough to maintain gate

    chooser = TemplateChooser()

    # Agent tries to choose next action
    decision = chooser.choose_next(
        beliefs=beliefs,
        budget_remaining_wells=384,
        cycle=2
    )

    # Assert: Cycle 0 constraint no longer forces calibration plate
    # Should proceed to biology template selection (dose ladder, exploration, etc.)
    assert decision.chosen_template != "abort_insufficient_cycle0_budget", \
        "Should not abort for Cycle 0 budget after calibration_plate_run=True"

    # Check that it's NOT a Cycle 0 decision
    if hasattr(chooser, 'last_decision_event') and chooser.last_decision_event:
        candidate = chooser.last_decision_event.selected_candidate
        assert candidate.get("trigger") != "cycle0_required", \
            "Should not trigger cycle0_required after calibration_plate_run=True"
        assert candidate.get("purpose") != "instrument_shape_learning", \
            "Should not be tagged as instrument_shape_learning"

    print("✓ Test 3 passed: Cycle 0 constraint unlocks after calibration_plate_run=True")


def test_instrument_shape_summary_computation():
    """Test 4: compute_instrument_shape_summary() correctly evaluates thresholds.

    This is a unit test for the shape learning function.
    """
    from src.cell_os.epistemic_agent.instrument_shape import compute_instrument_shape_summary

    # Create mock observation with DMSO controls
    dmso_conditions = [
        ConditionSummary(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=12.0,
            assay="cell_painting",
            position_tag="center",
            n_wells=12,
            mean=1.0,
            std=0.10,
            sem=0.03,
            cv=0.10,  # Good precision
            min_val=0.85,
            max_val=1.15,
            feature_means={"er": 1.0, "mito": 1.0, "nucleus": 1.0},
            feature_stds={"er": 0.1, "mito": 0.1, "nucleus": 0.1},
            n_failed=0,
            n_outliers=0,
            n_wells_total=12,
            n_wells_used=12,
            n_wells_dropped=0,
        ),
        ConditionSummary(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=12.0,
            assay="cell_painting",
            position_tag="edge",
            n_wells=12,
            mean=1.05,  # Slight edge effect
            std=0.12,
            sem=0.035,
            cv=0.11,
            min_val=0.88,
            max_val=1.20,
            feature_means={"er": 1.05, "mito": 1.05, "nucleus": 1.05},
            feature_stds={"er": 0.12, "mito": 0.12, "nucleus": 0.12},
            n_failed=0,
            n_outliers=0,
            n_wells_total=12,
            n_wells_used=12,
            n_wells_dropped=0,
        ),
    ]

    observation = Observation(
        design_id="test_calibration",
        conditions=dmso_conditions,
        wells_spent=24,
        budget_remaining=360
    )

    # Compute shape summary
    shape_summary = compute_instrument_shape_summary(
        observation=observation,
        plate_id=CYCLE0_PLATE_ID
    )

    # Verify metrics are computed
    assert shape_summary.noise_sigma > 0, "Noise sigma should be positive"
    assert shape_summary.edge_effect_strength >= 0, "Edge effect should be non-negative"
    assert shape_summary.spatial_residual_metric >= 0, "Spatial residual should be non-negative"
    assert 0 <= shape_summary.replicate_precision_score <= 1, "Precision score should be in [0,1]"
    assert 0 <= shape_summary.channel_coupling_score <= 1, "Coupling score should be in [0,1]"

    # Verify pass/fail logic
    if shape_summary.noise_gate_pass:
        assert len(shape_summary.failed_checks) == 0, "Passing summary should have no failed checks"
    else:
        assert len(shape_summary.failed_checks) > 0, "Failing summary should list failed checks"

    print(f"✓ Test 4 passed: Instrument shape computed correctly")
    print(f"  noise_sigma={shape_summary.noise_sigma:.4f}, "
          f"edge={shape_summary.edge_effect_strength:.4f}, "
          f"pass={shape_summary.noise_gate_pass}")


def test_spatial_residuals_gradient_attack():
    """Test 5a: Adversarial gradient attack should fail gate.

    Applies 15% top-to-bottom gradient to DMSO wells.
    Moran's I should detect spatial structure and fail the gate.
    """
    import numpy as np
    from src.cell_os.epistemic_agent.instrument_shape import compute_instrument_shape_summary

    # Create mock DMSO wells with 15% gradient (top to bottom)
    # 8x12 plate (96 wells)
    raw_wells = []
    base_value = 1.0

    for row_idx in range(8):
        row_letter = chr(ord('A') + row_idx)
        for col_idx in range(1, 13):
            # Apply 15% gradient: top rows (A-D) = 1.0, bottom rows (E-H) = 1.15
            gradient_factor = 1.0 + (row_idx / 7) * 0.15

            # Add small random noise so it's not perfectly linear
            noise = np.random.normal(0, 0.02)

            well_pos = f"{row_letter}{col_idx:02d}"
            raw_wells.append({
                'compound': 'DMSO',
                'position': well_pos,
                'readout': base_value * gradient_factor + noise,
                'cell_line': 'A549',
                'dose_uM': 0.0,
                'time_h': 12.0,
                'assay': 'cell_painting',
            })

    # Create DMSO condition summary (needed for shape computation)
    dmso_condition = ConditionSummary(
        cell_line="A549",
        compound="DMSO",
        dose_uM=0.0,
        time_h=12.0,
        assay="cell_painting",
        position_tag="any",
        n_wells=96,
        mean=1.075,  # Approximate mean with gradient
        std=0.06,
        sem=0.006,
        cv=0.056,
        min_val=0.98,
        max_val=1.17,
        feature_means={"channel_1": 1.075},
        feature_stds={"channel_1": 0.06},
        n_failed=0,
        n_outliers=0,
        n_wells_total=96,
        n_wells_used=96,
        n_wells_dropped=0,
    )

    # Create observation with raw wells (needed for Moran's I)
    observation = Observation(
        design_id="gradient_attack",
        conditions=[dmso_condition],  # Need at least one DMSO condition
        wells_spent=96,
        budget_remaining=288,
        raw_wells=raw_wells
    )

    # Compute instrument shape
    shape_summary = compute_instrument_shape_summary(
        observation=observation,
        plate_id="ADVERSARIAL_GRADIENT_TEST"
    )

    # Assert: gradient should be detected
    assert shape_summary.spatial_structure_detected == True, \
        f"Gradient should be detected (Moran's I={shape_summary.spatial_residual_metric:.4f})"

    # Assert: gate should FAIL
    assert shape_summary.noise_gate_pass == False, \
        "Gate should fail when spatial gradient present"

    assert "spatial_residual" in shape_summary.failed_checks, \
        "spatial_residual should be in failed checks"

    print(f"✓ Test 5a passed: 15% gradient detected (Moran's I={shape_summary.spatial_residual_metric:.4f}, failed)")


def test_spatial_residuals_stripe_attack():
    """Test 5b: Adversarial stripe attack (column banding) should fail gate.

    Applies 10% alternating column stripe pattern to DMSO wells.
    Moran's I should detect spatial structure (not just gradients).
    """
    import numpy as np
    from src.cell_os.epistemic_agent.instrument_shape import compute_instrument_shape_summary

    # Create mock DMSO wells with column striping
    # Even columns (2,4,6,8,10,12) = 1.0, Odd columns (1,3,5,7,9,11) = 1.10
    np.random.seed(99)
    raw_wells = []
    base_value = 1.0

    for row_idx in range(8):
        row_letter = chr(ord('A') + row_idx)
        for col_idx in range(1, 13):
            # Column stripe: every other column is +10%
            stripe_factor = 1.10 if col_idx % 2 == 1 else 1.0

            # Add small random noise
            noise = np.random.normal(0, 0.02)

            well_pos = f"{row_letter}{col_idx:02d}"
            raw_wells.append({
                'compound': 'DMSO',
                'position': well_pos,
                'readout': base_value * stripe_factor + noise,
                'cell_line': 'A549',
                'dose_uM': 0.0,
                'time_h': 12.0,
                'assay': 'cell_painting',
            })

    # Create DMSO condition summary
    dmso_condition = ConditionSummary(
        cell_line="A549",
        compound="DMSO",
        dose_uM=0.0,
        time_h=12.0,
        assay="cell_painting",
        position_tag="any",
        n_wells=96,
        mean=1.05,  # Approximate mean with stripe
        std=0.06,
        sem=0.006,
        cv=0.057,
        min_val=0.96,
        max_val=1.14,
        feature_means={"channel_1": 1.05},
        feature_stds={"channel_1": 0.06},
        n_failed=0,
        n_outliers=0,
        n_wells_total=96,
        n_wells_used=96,
        n_wells_dropped=0,
    )

    # Create observation with raw wells
    observation = Observation(
        design_id="stripe_attack",
        conditions=[dmso_condition],
        wells_spent=96,
        budget_remaining=288,
        raw_wells=raw_wells
    )

    # Compute instrument shape
    shape_summary = compute_instrument_shape_summary(
        observation=observation,
        plate_id="ADVERSARIAL_STRIPE_TEST"
    )

    # Assert: stripe should be detected
    assert shape_summary.spatial_structure_detected == True, \
        f"Column stripe should be detected (Moran's I={shape_summary.spatial_residual_metric:.4f})"

    # Assert: gate should FAIL
    assert shape_summary.noise_gate_pass == False, \
        "Gate should fail when spatial stripe present"

    assert "spatial_residual" in shape_summary.failed_checks, \
        "spatial_residual should be in failed checks"

    # Check pattern hint if available
    if shape_summary.spatial_diagnostic and 'pattern_hint' in shape_summary.spatial_diagnostic:
        pattern = shape_summary.spatial_diagnostic['pattern_hint']
        print(f"✓ Test 5b passed: Column stripe detected (Moran's I={shape_summary.spatial_residual_metric:.4f}, pattern={pattern})")
    else:
        print(f"✓ Test 5b passed: Column stripe detected (Moran's I={shape_summary.spatial_residual_metric:.4f})")


def test_spatial_residuals_random_noise():
    """Test 5c: Random i.i.d. noise should NOT trigger spatial detection.

    Wells with pure Gaussian noise (no spatial structure) should pass.
    """
    import numpy as np
    from src.cell_os.epistemic_agent.instrument_shape import compute_instrument_shape_summary

    # Create mock DMSO wells with i.i.d. Gaussian noise (no spatial structure)
    np.random.seed(42)  # Fix seed for reproducibility
    raw_wells = []
    base_value = 1.0
    noise_level = 0.10  # 10% noise

    for row_idx in range(8):
        row_letter = chr(ord('A') + row_idx)
        for col_idx in range(1, 13):
            # Pure random noise, no spatial pattern
            noise = np.random.normal(0, noise_level)

            well_pos = f"{row_letter}{col_idx:02d}"
            raw_wells.append({
                'compound': 'DMSO',
                'position': well_pos,
                'readout': base_value + noise,
                'cell_line': 'A549',
                'dose_uM': 0.0,
                'time_h': 12.0,
                'assay': 'cell_painting',
            })

    # Create DMSO condition summary
    dmso_condition = ConditionSummary(
        cell_line="A549",
        compound="DMSO",
        dose_uM=0.0,
        time_h=12.0,
        assay="cell_painting",
        position_tag="any",
        n_wells=96,
        mean=1.0,
        std=0.10,
        sem=0.01,
        cv=0.10,
        min_val=0.7,
        max_val=1.3,
        feature_means={"channel_1": 1.0},
        feature_stds={"channel_1": 0.10},
        n_failed=0,
        n_outliers=0,
        n_wells_total=96,
        n_wells_used=96,
        n_wells_dropped=0,
    )

    # Create observation
    observation = Observation(
        design_id="random_noise_baseline",
        conditions=[dmso_condition],
        wells_spent=96,
        budget_remaining=288,
        raw_wells=raw_wells
    )

    # Compute instrument shape
    shape_summary = compute_instrument_shape_summary(
        observation=observation,
        plate_id="RANDOM_NOISE_TEST"
    )

    # Assert: no spatial structure should be detected
    assert shape_summary.spatial_structure_detected == False, \
        f"Random noise should NOT be detected as spatial structure (Moran's I={shape_summary.spatial_residual_metric:.4f})"

    # Noise may still cause gate to fail (if CV is high), but NOT due to spatial structure
    if not shape_summary.noise_gate_pass:
        assert "spatial_residual" not in shape_summary.failed_checks, \
            "If gate fails on random noise, it should be due to noise_sigma, not spatial_residual"

    print(f"✓ Test 5c passed: Random noise NOT flagged as spatial (Moran's I={shape_summary.spatial_residual_metric:.4f})")


if __name__ == "__main__":
    print("="*70)
    print("CYCLE 0 INTEGRATION TESTS")
    print("="*70)

    print("\nTest 1: Gate locks biology...")
    test_gate_locks_biology()

    print("\nTest 2a: Gate can flip (passing)...")
    test_gate_can_flip_passing()

    print("\nTest 2b: Gate can flip (failing)...")
    test_gate_can_flip_failing()

    print("\nTest 3: Cycle 0 constraint unlocks after calibration...")
    test_gate_locks_biology_after_calibration_run()

    print("\nTest 4: Instrument shape computation...")
    test_instrument_shape_summary_computation()

    print("\nTest 5a: Adversarial gradient attack...")
    test_spatial_residuals_gradient_attack()

    print("\nTest 5b: Adversarial stripe attack...")
    test_spatial_residuals_stripe_attack()

    print("\nTest 5c: Random noise baseline...")
    test_spatial_residuals_random_noise()

    print("\n" + "="*70)
    print("ALL TESTS PASSED")
    print("Moran's I catches gradients AND stripes, ignores random noise.")
    print("="*70)
