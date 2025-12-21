"""
Test batch confounding validator.

This validates that:
1. Totally confounded designs are rejected (control Plate A, treatment Plate B)
2. Balanced designs are accepted (50/50 split across plates)
3. Resolution strategies are provided
4. Multiple batch types detected (plate + day + operator)
"""

from src.cell_os.simulation.batch_confounding_validator import (
    BatchConfoundingValidator,
    validate_batch_confounding,
    BatchConfoundingResult
)


def test_plate_confounded_design():
    """
    Totally confounded design: control on Plate A, treatment on Plate B.

    Expected: Rejected with plate_imbalance = 1.0
    """
    design = {
        "design_id": "test_plate_confounded",
        "wells": [
            # Control arm: All on Plate A
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "PlateA", "day": 1, "operator": "OP1"},
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "PlateA", "day": 1, "operator": "OP1"},
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "PlateA", "day": 1, "operator": "OP1"},
            # Treatment arm: All on Plate B
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "PlateB", "day": 1, "operator": "OP1"},
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "PlateB", "day": 1, "operator": "OP1"},
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "PlateB", "day": 1, "operator": "OP1"},
        ]
    }

    result = validate_batch_confounding(design, imbalance_threshold=0.7)

    assert result.is_confounded, "Should detect plate confounding"
    assert result.violation_type == "plate", f"Expected plate confounding, got {result.violation_type}"
    assert result.imbalance_metric > 0.9, f"Plate imbalance should be near 1.0, got {result.imbalance_metric:.3f}"
    assert result.confounded_arms == ("DMSO", "DrugX")

    print(f"✓ Plate confounded design rejected")
    print(f"  Imbalance: {result.imbalance_metric:.3f}")
    print(f"  Violation type: {result.violation_type}")
    print(f"  Resolution strategies: {len(result.resolution_strategies)}")


def test_balanced_design_accepted():
    """
    Balanced design: control and treatment split 50/50 across plates.

    Expected: Accepted with low imbalance
    """
    design = {
        "design_id": "test_balanced",
        "wells": [
            # Control: 2 on Plate A, 2 on Plate B
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "PlateA", "day": 1, "operator": "OP1"},
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "PlateA", "day": 1, "operator": "OP1"},
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "PlateB", "day": 1, "operator": "OP1"},
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "PlateB", "day": 1, "operator": "OP1"},
            # Treatment: 2 on Plate A, 2 on Plate B
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "PlateA", "day": 1, "operator": "OP1"},
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "PlateA", "day": 1, "operator": "OP1"},
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "PlateB", "day": 1, "operator": "OP1"},
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "PlateB", "day": 1, "operator": "OP1"},
        ]
    }

    result = validate_batch_confounding(design, imbalance_threshold=0.7)

    assert not result.is_confounded, "Should accept balanced design"
    assert result.imbalance_metric < 0.5, f"Imbalance should be low, got {result.imbalance_metric:.3f}"

    print(f"\n✓ Balanced design accepted")
    print(f"  Imbalance: {result.imbalance_metric:.3f} (threshold: 0.7)")
    print(f"  Confounded: {result.is_confounded}")


def test_day_confounded_design():
    """
    Day confounded: control on Day 1, treatment on Day 2.

    Expected: Rejected with day_imbalance = 1.0
    """
    design = {
        "design_id": "test_day_confounded",
        "wells": [
            # Control: All on Day 1
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "Plate1", "day": 1, "operator": "OP1"},
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "Plate1", "day": 1, "operator": "OP1"},
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "Plate1", "day": 1, "operator": "OP1"},
            # Treatment: All on Day 2
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "Plate1", "day": 2, "operator": "OP1"},
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "Plate1", "day": 2, "operator": "OP1"},
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "Plate1", "day": 2, "operator": "OP1"},
        ]
    }

    result = validate_batch_confounding(design, imbalance_threshold=0.7)

    assert result.is_confounded, "Should detect day confounding"
    assert result.violation_type == "day", f"Expected day confounding, got {result.violation_type}"
    assert result.imbalance_metric > 0.9, f"Day imbalance should be near 1.0, got {result.imbalance_metric:.3f}"

    print(f"\n✓ Day confounded design rejected")
    print(f"  Imbalance: {result.imbalance_metric:.3f}")
    print(f"  Violation type: {result.violation_type}")


def test_operator_confounded_design():
    """
    Operator confounded: control by OP1, treatment by OP2.

    Expected: Rejected with operator_imbalance = 1.0
    """
    design = {
        "design_id": "test_operator_confounded",
        "wells": [
            # Control: All by OP1
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "Plate1", "day": 1, "operator": "OP1"},
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "Plate1", "day": 1, "operator": "OP1"},
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "Plate1", "day": 1, "operator": "OP1"},
            # Treatment: All by OP2
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "Plate1", "day": 1, "operator": "OP2"},
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "Plate1", "day": 1, "operator": "OP2"},
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "Plate1", "day": 1, "operator": "OP2"},
        ]
    }

    result = validate_batch_confounding(design, imbalance_threshold=0.7)

    assert result.is_confounded, "Should detect operator confounding"
    assert result.violation_type == "operator", f"Expected operator confounding, got {result.violation_type}"
    assert result.imbalance_metric > 0.9, f"Operator imbalance should be near 1.0, got {result.imbalance_metric:.3f}"

    print(f"\n✓ Operator confounded design rejected")
    print(f"  Imbalance: {result.imbalance_metric:.3f}")
    print(f"  Violation type: {result.violation_type}")


def test_multiple_batch_confounding():
    """
    Multiple confounding: plate + day + operator all confounded.

    Expected: Rejected with violation_type = "multiple"
    """
    design = {
        "design_id": "test_multiple_confounded",
        "wells": [
            # Control: PlateA, Day1, OP1
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "PlateA", "day": 1, "operator": "OP1"},
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "PlateA", "day": 1, "operator": "OP1"},
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "PlateA", "day": 1, "operator": "OP1"},
            # Treatment: PlateB, Day2, OP2 (all different!)
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "PlateB", "day": 2, "operator": "OP2"},
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "PlateB", "day": 2, "operator": "OP2"},
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "PlateB", "day": 2, "operator": "OP2"},
        ]
    }

    result = validate_batch_confounding(design, imbalance_threshold=0.7)

    assert result.is_confounded, "Should detect multiple confounding"
    assert result.violation_type == "multiple", f"Expected multiple confounding, got {result.violation_type}"
    assert result.imbalance_metric > 0.9, f"Imbalance should be near 1.0, got {result.imbalance_metric:.3f}"

    # Check details contain all three types
    assert "plate_imbalance" in result.details
    assert "day_imbalance" in result.details
    assert "operator_imbalance" in result.details

    assert result.details["plate_imbalance"] > 0.9, "Plate should be confounded"
    assert result.details["day_imbalance"] > 0.9, "Day should be confounded"
    assert result.details["operator_imbalance"] > 0.9, "Operator should be confounded"

    print(f"\n✓ Multiple batch confounding detected")
    print(f"  Overall imbalance: {result.imbalance_metric:.3f}")
    print(f"  Plate imbalance: {result.details['plate_imbalance']:.3f}")
    print(f"  Day imbalance: {result.details['day_imbalance']:.3f}")
    print(f"  Operator imbalance: {result.details['operator_imbalance']:.3f}")
    print(f"  Confounded types: {result.details['confounded_types']}")


def test_partial_imbalance():
    """
    Partial imbalance: 75% control on Plate A, 25% on Plate B.

    Imbalance calculation:
    - Control: 75% PlateA, 25% PlateB
    - Treatment: 25% PlateA, 75% PlateB
    - Overlap: min(0.75, 0.25) + min(0.25, 0.75) = 0.25 + 0.25 = 0.50
    - Imbalance: 1 - 0.50 = 0.50

    Expected: Accepted with threshold 0.7 (imbalance = 0.50 < 0.7)
              Rejected with threshold 0.4 (imbalance = 0.50 > 0.4)
    """
    design = {
        "design_id": "test_partial_imbalance",
        "wells": [
            # Control: 3 on Plate A, 1 on Plate B (75% on A)
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "PlateA", "day": 1, "operator": "OP1"},
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "PlateA", "day": 1, "operator": "OP1"},
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "PlateA", "day": 1, "operator": "OP1"},
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "PlateB", "day": 1, "operator": "OP1"},
            # Treatment: 1 on Plate A, 3 on Plate B (75% on B)
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "PlateA", "day": 1, "operator": "OP1"},
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "PlateB", "day": 1, "operator": "OP1"},
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "PlateB", "day": 1, "operator": "OP1"},
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "PlateB", "day": 1, "operator": "OP1"},
        ]
    }

    # Test with lenient threshold (0.7) - should accept (0.50 < 0.7)
    result_lenient = validate_batch_confounding(design, imbalance_threshold=0.7)
    assert not result_lenient.is_confounded, f"Should accept with threshold 0.7 (imbalance={result_lenient.imbalance_metric:.3f})"

    # Test with strict threshold (0.4) - should reject (0.50 > 0.4)
    result_strict = validate_batch_confounding(design, imbalance_threshold=0.4)
    assert result_strict.is_confounded, f"Should reject with threshold 0.4 (imbalance={result_strict.imbalance_metric:.3f})"

    print(f"\n✓ Partial imbalance threshold validated")
    print(f"  Imbalance: {result_lenient.imbalance_metric:.3f}")
    print(f"  Rejected at threshold 0.4: {result_strict.is_confounded}")
    print(f"  Rejected at threshold 0.7: {result_lenient.is_confounded}")


def test_resolution_strategies():
    """
    Confounded design should provide resolution strategies.

    Expected: 3 strategies for plate confounding
    """
    design = {
        "design_id": "test_strategies",
        "wells": [
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "PlateA", "day": 1, "operator": "OP1"},
            {"compound": "DMSO", "dose_uM": 0.0, "plate_id": "PlateA", "day": 1, "operator": "OP1"},
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "PlateB", "day": 1, "operator": "OP1"},
            {"compound": "DrugX", "dose_uM": 10.0, "plate_id": "PlateB", "day": 1, "operator": "OP1"},
        ]
    }

    result = validate_batch_confounding(design, imbalance_threshold=0.7)

    assert result.is_confounded
    assert len(result.resolution_strategies) >= 2, "Should provide resolution strategies"

    print(f"\n✓ Resolution strategies provided")
    for i, strategy in enumerate(result.resolution_strategies, 1):
        print(f"  {i}. {strategy}")


if __name__ == "__main__":
    print("="*70)
    print("BATCH CONFOUNDING VALIDATOR TESTS")
    print("="*70)
    print()

    test_plate_confounded_design()
    test_balanced_design_accepted()
    test_day_confounded_design()
    test_operator_confounded_design()
    test_multiple_batch_confounding()
    test_partial_imbalance()
    test_resolution_strategies()

    print("\n" + "="*70)
    print("✅ ALL BATCH CONFOUNDING VALIDATOR TESTS PASSED")
    print("="*70)
    print()
    print("Validated:")
    print("  ✓ Plate confounding detected (imbalance = 1.0)")
    print("  ✓ Day confounding detected (imbalance = 1.0)")
    print("  ✓ Operator confounding detected (imbalance = 1.0)")
    print("  ✓ Multiple batch confounding detected")
    print("  ✓ Balanced designs accepted (imbalance < 0.5)")
    print("  ✓ Threshold tuning validated")
    print("  ✓ Resolution strategies provided")
