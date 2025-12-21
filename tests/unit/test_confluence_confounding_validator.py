"""
Test confluence confounding validator.

This enforces density-matched design: comparisons across conditions must be
density-matched at readout time, or explicitly include a density sentinel arm.

Tests:
1. Reject confounded design (high delta_p across comparison arms)
2. Accept when density sentinel present (escape hatch)
3. Threshold boundary (designs just below threshold should pass)
"""

from src.cell_os.simulation.design_validation import ExperimentalDesignValidator


def test_reject_confounded_design():
    """
    Validator should reject designs with high delta_p across comparison arms.

    Setup: Two conditions at same (cell_line, time_h, assay):
    - Condition A: DMSO @ 0 µM (low pressure, grows to ~0.4 confluence)
    - Condition B: ToxicCompound @ 50 µM (higher pressure due to lower growth penalty)

    Expected: ValueError with violation_code "confluence_confounding"
    """
    validator = ExperimentalDesignValidator()

    # Design with obvious confluence confounding
    wells = [
        # Control arm: vehicle only
        {"cell_line": "A549", "compound": "DMSO", "dose_uM": 0.0, "time_h": 24.0, "assay": "cell_painting"},
        {"cell_line": "A549", "compound": "DMSO", "dose_uM": 0.0, "time_h": 24.0, "assay": "cell_painting"},
        {"cell_line": "A549", "compound": "DMSO", "dose_uM": 0.0, "time_h": 24.0, "assay": "cell_painting"},

        # Treatment arm: high dose compound (should predict lower confluence due to growth inhibition, but not enough to match)
        # Wait, actually with the dose penalty, high dose will REDUCE pressure by slowing growth
        # So to trigger confounding, we need one arm to grow a lot and one to grow less
        # Let me use different timepoints or different cell lines? No, that wouldn't be in same comparison group.
        # Actually, let me re-think: DMSO at 24h will grow to high confluence. A toxic compound will slow growth.
        # So DMSO will have HIGHER pressure than toxic compound.
        # But the validator uses a dose_penalty that reduces growth rate, so:
        # - DMSO: seed_frac=0.20, r=0.035, confluence at 24h = 0.20 * exp(0.035*24) = 0.20 * 2.32 = 0.464 → p ~ 0.12
        # - ToxicX @ 50µM: dose_penalty = min(0.6, 0.08*log10(51)) ~ 0.136, r = 0.035*(1-0.136) = 0.030,
        #   confluence = 0.20 * exp(0.030*24) = 0.20 * 2.05 = 0.41 → p ~ 0.08
        # That's only Δp = 0.04, not enough to trigger threshold of 0.15

        # To get a bigger delta, I need either:
        # a) Longer time (more growth)
        # b) Different cell line with different parameters
        # c) Or create a case where one arm has no compound and grows fast, while other is at different time

        # Let me use a longer timepoint: 48h instead of 24h
        # DMSO at 48h: 0.20 * exp(0.035*48) = 0.20 * 5.38 = 1.076 (capped at 1.2) → confluence = 1.076 → p ~ 0.85
        # ToxicX @ 1µM at 48h: dose_penalty = min(0.6, 0.08*log10(2)) ~ 0.024, r = 0.035*0.976 = 0.034,
        #   confluence = 0.20 * exp(0.034*48) = 0.20 * 5.15 = 1.03 → p ~ 0.82
        # Still not enough delta!

        # The issue is that the dose penalty is too small. Let me use a VERY high dose:
        # ToxicX @ 10000µM: dose_penalty = min(0.6, 0.08*log10(10001)) ~ 0.32, r = 0.035*0.68 = 0.024
        #   at 48h: confluence = 0.20 * exp(0.024*48) = 0.20 * 3.15 = 0.63 → p ~ 0.35
        # DMSO at 48h: p ~ 0.85
        # Δp = 0.85 - 0.35 = 0.50 > 0.15 ✓

        {"cell_line": "A549", "compound": "ToxicCompound", "dose_uM": 10000.0, "time_h": 48.0, "assay": "cell_painting"},
        {"cell_line": "A549", "compound": "ToxicCompound", "dose_uM": 10000.0, "time_h": 48.0, "assay": "cell_painting"},
        {"cell_line": "A549", "compound": "ToxicCompound", "dose_uM": 10000.0, "time_h": 48.0, "assay": "cell_painting"},
    ]

    # Update wells to use 48h for control too
    for w in wells[:3]:
        w["time_h"] = 48.0

    design_id = "test_confounded_design"

    # Should raise ValueError with structured details
    try:
        validator.validate_proposal_for_confluence_confounding(wells, design_id)
        raise AssertionError("Validator should have rejected confounded design")
    except ValueError as e:
        error_details = e.args[0]
        assert isinstance(error_details, dict), "Error should be structured dict"
        assert error_details["violation_code"] == "confluence_confounding"
        assert error_details["design_id"] == design_id
        assert error_details["delta_p"] > 0.15, f"delta_p should exceed threshold: {error_details['delta_p']}"
        assert "resolution_strategies" in error_details
        assert len(error_details["resolution_strategies"]) == 3

        print(f"✓ Rejected confounded design: Δp = {error_details['delta_p']:.3f} > 0.15")
        print(f"  Highest pressure: {error_details['highest_pressure']}")
        print(f"  Lowest pressure: {error_details['lowest_pressure']}")


def test_accept_with_density_sentinel():
    """
    Validator should accept designs with density sentinel escape hatch.

    Setup: Same as confounded design, but include a DENSITY_SENTINEL well
    Expected: No error (validator skips group with sentinel)
    """
    validator = ExperimentalDesignValidator()

    # Same design as above, but with density sentinel
    wells = [
        # Control arm
        {"cell_line": "A549", "compound": "DMSO", "dose_uM": 0.0, "time_h": 48.0, "assay": "cell_painting"},
        {"cell_line": "A549", "compound": "DMSO", "dose_uM": 0.0, "time_h": 48.0, "assay": "cell_painting"},

        # Treatment arm
        {"cell_line": "A549", "compound": "ToxicCompound", "dose_uM": 10000.0, "time_h": 48.0, "assay": "cell_painting"},
        {"cell_line": "A549", "compound": "ToxicCompound", "dose_uM": 10000.0, "time_h": 48.0, "assay": "cell_painting"},

        # Density sentinel (escape hatch)
        {"cell_line": "A549", "compound": "DENSITY_SENTINEL", "dose_uM": 0.0, "time_h": 48.0, "assay": "cell_painting"},
    ]

    design_id = "test_sentinel_design"

    # Should not raise
    try:
        validator.validate_proposal_for_confluence_confounding(wells, design_id)
        print("✓ Accepted design with density sentinel")
    except ValueError as e:
        raise AssertionError(f"Validator should not reject designs with DENSITY_SENTINEL: {e}")


def test_threshold_boundary():
    """
    Designs just below threshold should pass.

    Setup: Two conditions with delta_p slightly below 0.15
    Expected: No error
    """
    validator = ExperimentalDesignValidator()

    # Design with delta_p just below threshold
    # Use shorter time or milder dose to get smaller delta
    # DMSO at 24h: confluence ~ 0.46, p ~ 0.12
    # ToxicCompound @ 100µM at 24h: dose_penalty ~ min(0.6, 0.08*log10(101)) ~ 0.16
    #   r = 0.035 * 0.84 = 0.029, confluence = 0.20 * exp(0.029*24) = 0.20 * 2.01 = 0.40, p ~ 0.07
    # Δp = 0.12 - 0.07 = 0.05 < 0.15 ✓

    wells = [
        # Control arm
        {"cell_line": "A549", "compound": "DMSO", "dose_uM": 0.0, "time_h": 24.0, "assay": "cell_painting"},
        {"cell_line": "A549", "compound": "DMSO", "dose_uM": 0.0, "time_h": 24.0, "assay": "cell_painting"},

        # Treatment arm (mild dose, not enough to trigger confounding)
        {"cell_line": "A549", "compound": "ToxicCompound", "dose_uM": 100.0, "time_h": 24.0, "assay": "cell_painting"},
        {"cell_line": "A549", "compound": "ToxicCompound", "dose_uM": 100.0, "time_h": 24.0, "assay": "cell_painting"},
    ]

    design_id = "test_boundary_design"

    # Should not raise
    try:
        validator.validate_proposal_for_confluence_confounding(wells, design_id)
        print("✓ Accepted design at threshold boundary (Δp < 0.15)")
    except ValueError as e:
        error_details = e.args[0]
        raise AssertionError(f"Validator should not reject designs below threshold: Δp = {error_details.get('delta_p', 'unknown')}")


def test_single_condition_no_validation():
    """
    Groups with only one condition should not be validated (no comparison).

    Setup: All wells have same condition
    Expected: No error (nothing to compare)
    """
    validator = ExperimentalDesignValidator()

    # All wells same condition
    wells = [
        {"cell_line": "A549", "compound": "DMSO", "dose_uM": 0.0, "time_h": 24.0, "assay": "cell_painting"},
        {"cell_line": "A549", "compound": "DMSO", "dose_uM": 0.0, "time_h": 24.0, "assay": "cell_painting"},
        {"cell_line": "A549", "compound": "DMSO", "dose_uM": 0.0, "time_h": 24.0, "assay": "cell_painting"},
    ]

    design_id = "test_single_condition"

    # Should not raise
    try:
        validator.validate_proposal_for_confluence_confounding(wells, design_id)
        print("✓ Skipped validation for single-condition design")
    except ValueError as e:
        raise AssertionError(f"Validator should not validate single-condition groups: {e}")


def test_different_readout_groups_independent():
    """
    Different readout groups (cell_line, time, assay) should be validated independently.

    Setup: Two groups, one confounded and one not
    Expected: Only the confounded group should cause rejection
    """
    validator = ExperimentalDesignValidator()

    wells = [
        # Group 1: A549 @ 48h (confounded)
        {"cell_line": "A549", "compound": "DMSO", "dose_uM": 0.0, "time_h": 48.0, "assay": "cell_painting"},
        {"cell_line": "A549", "compound": "ToxicCompound", "dose_uM": 10000.0, "time_h": 48.0, "assay": "cell_painting"},

        # Group 2: HepG2 @ 24h (not confounded, mild delta)
        {"cell_line": "HepG2", "compound": "DMSO", "dose_uM": 0.0, "time_h": 24.0, "assay": "cell_painting"},
        {"cell_line": "HepG2", "compound": "CompoundB", "dose_uM": 10.0, "time_h": 24.0, "assay": "cell_painting"},
    ]

    design_id = "test_multi_group"

    # Should reject because Group 1 is confounded
    try:
        validator.validate_proposal_for_confluence_confounding(wells, design_id)
        raise AssertionError("Validator should have rejected confounded group")
    except ValueError as e:
        error_details = e.args[0]
        assert error_details["cell_line"] == "A549", "Should identify confounded group correctly"
        assert error_details["time_h"] == 48.0

        print("✓ Correctly rejected confounded group while ignoring non-confounded group")


if __name__ == "__main__":
    test_reject_confounded_design()
    test_accept_with_density_sentinel()
    test_threshold_boundary()
    test_single_condition_no_validation()
    test_different_readout_groups_independent()
    print("\n✅ All confluence confounding validator tests PASSED")
