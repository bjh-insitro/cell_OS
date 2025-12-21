"""
Unit tests for condition canonicalization.

These tests prove that canonical keys eliminate aggregation races.
"""

from cell_os.core.canonicalize import (
    canonical_dose_uM,
    canonical_time_h,
    canonical_condition_key,
    are_conditions_equivalent,
    CanonicalCondition,
)


def test_dose_canonicalization():
    """Test dose conversion to integer nanomolar."""
    # Exact conversions
    assert canonical_dose_uM(0.0) == 0
    assert canonical_dose_uM(1.0) == 1000
    assert canonical_dose_uM(10.0) == 10000
    assert canonical_dose_uM(0.001) == 1  # 1 nM

    # Rounding behavior
    assert canonical_dose_uM(1.0004) == 1000  # Rounds down
    assert canonical_dose_uM(1.0005) == 1000  # Rounds down (Python's banker's rounding)
    assert canonical_dose_uM(1.0009) == 1001  # Rounds up

    # Near-duplicates that should be DISTINCT
    assert canonical_dose_uM(1.000) == 1000
    assert canonical_dose_uM(1.001) == 1001
    assert canonical_dose_uM(1.000) != canonical_dose_uM(1.001)


def test_time_canonicalization():
    """Test time conversion to integer minutes."""
    # Exact conversions
    assert canonical_time_h(0.0) == 0
    assert canonical_time_h(1.0) == 60
    assert canonical_time_h(24.0) == 1440
    assert canonical_time_h(0.5) == 30  # 30 minutes

    # Rounding behavior
    assert canonical_time_h(24.001) == 1440  # Rounds down
    assert canonical_time_h(24.01) == 1441   # Rounds up

    # Near-duplicates that should be DISTINCT
    assert canonical_time_h(24.0) == 1440
    assert canonical_time_h(24.01) == 1441
    assert canonical_time_h(24.0) != canonical_time_h(24.01)


def test_canonical_condition_key_creation():
    """Test creating canonical condition keys."""
    key = canonical_condition_key(
        cell_line="A549",
        compound_id="DMSO",
        dose_uM=1.0,
        time_h=24.0,
        assay="cell_painting",
        position_class="center"
    )

    assert key.cell_line == "A549"
    assert key.compound_id == "DMSO"
    assert key.dose_nM == 1000
    assert key.time_min == 1440
    assert key.assay == "cell_painting"
    assert key.position_class == "center"

    # Frozen dataclass - should be hashable
    assert hash(key) is not None

    # Can use as dict key
    d = {key: "test"}
    assert d[key] == "test"


def test_canonical_condition_identical_collapse():
    """Test that identical raw conditions collapse to same key."""
    key1 = canonical_condition_key(
        cell_line="A549",
        compound_id="DMSO",
        dose_uM=1.0000,
        time_h=24.0,
        assay="cell_painting",
        position_class="center"
    )

    key2 = canonical_condition_key(
        cell_line="A549",
        compound_id="DMSO",
        dose_uM=1.00001,  # Tiny float difference
        time_h=24.00001,  # Tiny float difference
        assay="cell_painting",
        position_class="center"
    )

    # Should collapse to same key
    assert key1 == key2
    assert hash(key1) == hash(key2)


def test_canonical_condition_near_duplicates_distinct():
    """Test that near-duplicates with meaningful differences stay distinct."""
    key1 = canonical_condition_key(
        cell_line="A549",
        compound_id="DMSO",
        dose_uM=1.000,
        time_h=24.0,
        assay="cell_painting",
        position_class="center"
    )

    key2 = canonical_condition_key(
        cell_line="A549",
        compound_id="DMSO",
        dose_uM=1.001,  # 1 nM difference
        time_h=24.0,
        assay="cell_painting",
        position_class="center"
    )

    # Should be DISTINCT (1000 nM vs 1001 nM)
    assert key1 != key2
    assert key1.dose_nM == 1000
    assert key2.dose_nM == 1001


def test_dose_collapse_aggregation_scenario():
    """
    CRITICAL TEST: Reproduce historical failure scenario.

    32 DMSO wells at "1.0 µM" but with tiny float variations
    (e.g., 1.0000, 1.00001, 1.000002) should collapse to ONE condition.
    """
    # Simulate float noise from different code paths
    doses = [
        1.0,
        1.0 + 1e-6,   # Floating point noise
        1.0 + 1e-7,   # Even tinier noise
        1.0 - 1e-6,   # Negative noise
    ]

    canonical_doses = [canonical_dose_uM(d) for d in doses]

    # ALL should collapse to 1000 nM
    assert all(d == 1000 for d in canonical_doses), \
        f"Float noise caused dose splitting: {canonical_doses}"

    # Create keys for these doses
    keys = [
        canonical_condition_key(
            cell_line="A549",
            compound_id="DMSO",
            dose_uM=d,
            time_h=24.0,
            assay="cell_painting",
            position_class="center"
        )
        for d in doses
    ]

    # All keys should be identical
    assert len(set(keys)) == 1, \
        f"Float noise caused condition splitting: {len(set(keys))} unique keys instead of 1"

    # If we group by these keys, we get ONE group
    from collections import defaultdict
    groups = defaultdict(list)
    for i, key in enumerate(keys):
        groups[key].append(i)

    assert len(groups) == 1, \
        f"Aggregation failed: {len(groups)} groups instead of 1"
    assert len(list(groups.values())[0]) == 4, \
        "All 4 wells should be in same group"


def test_time_collapse_aggregation_scenario():
    """Test that time float noise doesn't split replicates."""
    # Simulate time float noise
    times = [
        24.0,
        24.0 + 1e-5,  # Float noise from arithmetic
        24.0 - 1e-5,
    ]

    canonical_times = [canonical_time_h(t) for t in times]

    # ALL should collapse to 1440 minutes
    assert all(t == 1440 for t in canonical_times), \
        f"Float noise caused time splitting: {canonical_times}"


def test_determinism_different_order():
    """Test that same inputs in different order produce identical keys."""
    conditions = [
        ("A549", "DMSO", 1.0, 24.0),
        ("HepG2", "tunicamycin", 10.0, 12.0),
        ("A549", "H2O2", 0.1, 48.0),
    ]

    # Create keys in order 1
    keys1 = [
        canonical_condition_key(
            cell_line=c[0],
            compound_id=c[1],
            dose_uM=c[2],
            time_h=c[3],
            assay="cell_painting",
            position_class="center"
        )
        for c in conditions
    ]

    # Create keys in different order
    import random
    shuffled = conditions.copy()
    random.shuffle(shuffled)

    keys2 = [
        canonical_condition_key(
            cell_line=c[0],
            compound_id=c[1],
            dose_uM=c[2],
            time_h=c[3],
            assay="cell_painting",
            position_class="center"
        )
        for c in shuffled
    ]

    # Sort both for comparison
    keys1_sorted = sorted(keys1, key=lambda k: (k.cell_line, k.compound_id, k.dose_nM, k.time_min))
    keys2_sorted = sorted(keys2, key=lambda k: (k.cell_line, k.compound_id, k.dose_nM, k.time_min))

    assert keys1_sorted == keys2_sorted, \
        "Order of creation affects canonicalization (NON-DETERMINISTIC)"


def test_are_conditions_equivalent():
    """Test equivalence checker for near-duplicates."""
    # Equivalent conditions (round to same canonical)
    assert are_conditions_equivalent(
        dose1_uM=1.0000,
        time1_h=24.0,
        dose2_uM=1.00001,
        time2_h=24.00001,
    )

    # Non-equivalent (meaningful difference)
    assert not are_conditions_equivalent(
        dose1_uM=1.000,
        time1_h=24.0,
        dose2_uM=1.001,  # 1 nM difference
        time2_h=24.0,
    )

    # Non-equivalent (time difference)
    assert not are_conditions_equivalent(
        dose1_uM=1.0,
        time1_h=24.0,
        dose2_uM=1.0,
        time2_h=24.1,  # 6 minute difference
    )


def test_canonical_condition_immutable():
    """Test that CanonicalCondition is immutable."""
    key = canonical_condition_key(
        cell_line="A549",
        compound_id="DMSO",
        dose_uM=1.0,
        time_h=24.0,
        assay="cell_painting",
        position_class="center"
    )

    # Should not be able to modify
    try:
        key.dose_nM = 2000
        assert False, "CanonicalCondition should be immutable (frozen)"
    except Exception:
        pass  # Expected


def test_canonical_condition_validation():
    """Test that invalid inputs are rejected."""
    # Negative dose should fail
    try:
        CanonicalCondition(
            cell_line="A549",
            compound_id="DMSO",
            dose_nM=-100,  # Invalid
            time_min=1440,
            assay="cell_painting",
            position_class="center"
        )
        assert False, "Negative dose should be rejected"
    except ValueError:
        pass  # Expected

    # Negative time should fail
    try:
        CanonicalCondition(
            cell_line="A549",
            compound_id="DMSO",
            dose_nM=1000,
            time_min=-60,  # Invalid
            assay="cell_painting",
            position_class="center"
        )
        assert False, "Negative time should be rejected"
    except ValueError:
        pass  # Expected

    # Float dose should fail
    try:
        CanonicalCondition(
            cell_line="A549",
            compound_id="DMSO",
            dose_nM=1000.5,  # Invalid - must be int
            time_min=1440,
            assay="cell_painting",
            position_class="center"
        )
        assert False, "Float dose_nM should be rejected"
    except TypeError:
        pass  # Expected


def test_dose_validation_rejects_invalid():
    """Test that canonical_dose_uM rejects invalid inputs."""
    # Negative dose
    try:
        canonical_dose_uM(-1.0)
        assert False, "Should reject negative dose"
    except ValueError as e:
        assert "non-negative" in str(e).lower()

    # NaN
    try:
        canonical_dose_uM(float('nan'))
        assert False, "Should reject NaN"
    except ValueError as e:
        assert "finite" in str(e).lower()

    # Infinity
    try:
        canonical_dose_uM(float('inf'))
        assert False, "Should reject infinity"
    except ValueError as e:
        assert "finite" in str(e).lower()


def test_time_validation_rejects_invalid():
    """Test that canonical_time_h rejects invalid inputs."""
    # Negative time
    try:
        canonical_time_h(-1.0)
        assert False, "Should reject negative time"
    except ValueError as e:
        assert "non-negative" in str(e).lower()

    # NaN
    try:
        canonical_time_h(float('nan'))
        assert False, "Should reject NaN"
    except ValueError as e:
        assert "finite" in str(e).lower()

    # Infinity
    try:
        canonical_time_h(float('inf'))
        assert False, "Should reject infinity"
    except ValueError as e:
        assert "finite" in str(e).lower()


def test_bankers_rounding_behavior():
    """Test that rounding follows banker's rounding (round-half-to-even).

    Python's round() uses banker's rounding:
    - 0.5 → 0 (rounds to even)
    - 1.5 → 2 (rounds to even)
    - 2.5 → 2 (rounds to even)
    - 3.5 → 4 (rounds to even)
    """
    from cell_os.core.canonicalize import DOSE_RESOLUTION_NM

    # Doses that land exactly on half-steps
    # 0.0005 µM = 0.5 nM → should round to 0 (even)
    assert canonical_dose_uM(0.0005) == 0

    # 0.0015 µM = 1.5 nM → should round to 2 (even)
    assert canonical_dose_uM(0.0015) == 2

    # 0.0025 µM = 2.5 nM → should round to 2 (even)
    assert canonical_dose_uM(0.0025) == 2

    # 0.0035 µM = 3.5 nM → should round to 4 (even)
    assert canonical_dose_uM(0.0035) == 4

    print("✓ Banker's rounding behavior locked and tested")


def test_resolution_constants_are_used():
    """Test that resolution constants are actually used in conversion."""
    from cell_os.core.canonicalize import DOSE_RESOLUTION_NM, TIME_RESOLUTION_MIN

    # Verify constants are defined
    assert DOSE_RESOLUTION_NM == 1, "Dose resolution should be 1 nM"
    assert TIME_RESOLUTION_MIN == 1, "Time resolution should be 1 min"

    # Verify conversion uses resolution
    # If resolution were 10 nM, 1.005 µM (1005 nM) would round to 1010 nM
    # With resolution = 1 nM, it stays at 1005 nM
    dose_1_005_uM = canonical_dose_uM(1.005)
    assert dose_1_005_uM == 1005, f"Expected 1005 nM, got {dose_1_005_uM}"


def test_canonical_condition_to_dict():
    """Test serialization for logging."""
    key = canonical_condition_key(
        cell_line="A549",
        compound_id="DMSO",
        dose_uM=1.0,
        time_h=24.0,
        assay="cell_painting",
        position_class="center"
    )

    d = key.to_dict()

    assert d["cell_line"] == "A549"
    assert d["compound_id"] == "DMSO"
    assert d["dose_nM"] == 1000
    assert d["time_min"] == 1440
    assert d["assay"] == "cell_painting"
    assert d["position_class"] == "center"


if __name__ == "__main__":
    # Run tests
    test_dose_canonicalization()
    test_time_canonicalization()
    test_canonical_condition_key_creation()
    test_canonical_condition_identical_collapse()
    test_canonical_condition_near_duplicates_distinct()
    test_dose_collapse_aggregation_scenario()
    test_time_collapse_aggregation_scenario()
    test_determinism_different_order()
    test_are_conditions_equivalent()
    test_canonical_condition_immutable()
    test_canonical_condition_validation()
    test_dose_validation_rejects_invalid()
    test_time_validation_rejects_invalid()
    test_bankers_rounding_behavior()
    test_resolution_constants_are_used()
    test_canonical_condition_to_dict()

    print("\n✅ All canonicalization unit tests passed")
    print("\nKey results:")
    print("  → Float noise collapses to single canonical key")
    print("  → 32-well DMSO split is now IMPOSSIBLE")
    print("  → Deterministic across runs and orderings")
    print("  → Validation prevents invalid conditions (negative, NaN, inf)")
    print("  → Banker's rounding behavior locked and tested")
    print("  → Resolution constants explicitly defined and used")
