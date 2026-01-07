"""
Enforcement tests: Temporal causality is non-negotiable.

These tests prove that the system REJECTS causally invalid experiments.

Guards against:
- Negative observation times
- Negative treatment times
- Observations before treatments (time paradox)
- Legacy adapters bypassing validation

All violations must raise TemporalCausalityError, not warnings.
"""

import sys
import traceback
from cell_os.core.experiment import Well, Treatment, SpatialLocation
from cell_os.core.observation import RawWellResult
from cell_os.core.assay import AssayType
from cell_os.core.temporal_causality import TemporalCausalityError
from cell_os.core.legacy_adapters import well_spec_to_well


def assert_raises(exception_type, func):
    """Helper to assert that a function raises a specific exception."""
    try:
        func()
        return False, None
    except exception_type as e:
        return True, e
    except Exception as e:
        print(f"  Wrong exception type: expected {exception_type.__name__}, got {type(e).__name__}: {e}")
        return False, e


# ============================================================================
# Well construction tests
# ============================================================================

def test_well_rejects_negative_observation_time():
    """Well with negative observation_time_h must be rejected."""
    raised, exc = assert_raises(TemporalCausalityError, lambda: Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=-1.0,  # INVALID: negative time
        assay=AssayType.CELL_PAINTING,
        treatment_start_time_h=0.0,
    ))

    assert raised, "Should raise TemporalCausalityError for negative observation_time_h"
    assert "negative" in str(exc).lower()
    assert "-1.0" in str(exc)


def test_well_rejects_negative_treatment_start_time():
    """Well with negative treatment_start_time_h must be rejected."""
    raised, exc = assert_raises(TemporalCausalityError, lambda: Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=24.0,
        assay=AssayType.CELL_PAINTING,
        treatment_start_time_h=-5.0,  # INVALID: negative time
    ))

    assert raised, "Should raise TemporalCausalityError for negative treatment_start_time_h"
    assert "negative" in str(exc).lower()
    assert "-5.0" in str(exc)


def test_well_rejects_observation_before_treatment():
    """Observation before treatment (time paradox) must be rejected."""
    raised, exc = assert_raises(TemporalCausalityError, lambda: Well(
        cell_line="A549",
        treatment=Treatment(compound="tunicamycin", dose_uM=1.0),
        observation_time_h=10.0,
        assay=AssayType.CELL_PAINTING,
        treatment_start_time_h=24.0,  # INVALID: treatment after observation
    ))

    assert raised, "Should raise TemporalCausalityError for observation before treatment"
    assert "before treatment" in str(exc).lower()
    assert "10.0" in str(exc)
    assert "24.0" in str(exc)


def test_well_rejects_exact_negative_boundary():
    """Even slightly negative times must be rejected (no epsilon tolerance)."""
    raised, _ = assert_raises(TemporalCausalityError, lambda: Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=-0.001,  # INVALID: even tiny negative
        assay=AssayType.CELL_PAINTING,
    ))

    assert raised, "Should raise TemporalCausalityError for tiny negative observation_time_h"


def test_well_rejects_observation_before_treatment_by_epsilon():
    """Even tiny causality violations must be rejected (no tolerance)."""
    raised, _ = assert_raises(TemporalCausalityError, lambda: Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=23.999,
        assay=AssayType.CELL_PAINTING,
        treatment_start_time_h=24.0,  # INVALID: observation 0.001h before treatment
    ))

    assert raised, "Should raise TemporalCausalityError for tiny causality violation"


# ============================================================================
# Valid Well construction tests (boundary cases)
# ============================================================================

def test_well_accepts_zero_observation_time():
    """observation_time_h=0 is valid (observation at t=0)."""
    well = Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=0.0,  # VALID: t=0
        assay=AssayType.CELL_PAINTING,
        treatment_start_time_h=0.0,
    )
    assert well.observation_time_h == 0.0


def test_well_accepts_observation_equals_treatment_start():
    """Observation at exactly treatment_start_time_h is valid (boundary)."""
    well = Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=24.0,
        assay=AssayType.CELL_PAINTING,
        treatment_start_time_h=24.0,  # VALID: observation at treatment moment
    )
    assert well.observation_time_h == 24.0
    assert well.treatment_start_time_h == 24.0


def test_well_accepts_observation_after_treatment():
    """Normal case: observation after treatment (causal consistency)."""
    well = Well(
        cell_line="A549",
        treatment=Treatment(compound="tunicamycin", dose_uM=1.0),
        observation_time_h=48.0,
        assay=AssayType.CELL_PAINTING,
        treatment_start_time_h=24.0,  # VALID: treatment at 24h, observe at 48h
    )
    assert well.observation_time_h == 48.0
    assert well.treatment_start_time_h == 24.0


def test_well_defaults_treatment_start_to_zero():
    """Default treatment_start_time_h=0.0 (most common case)."""
    well = Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=24.0,
        assay=AssayType.CELL_PAINTING,
        # treatment_start_time_h not specified → defaults to 0.0
    )
    assert well.treatment_start_time_h == 0.0
    assert well.observation_time_h == 24.0


# ============================================================================
# RawWellResult tests
# ============================================================================

def test_raw_well_result_rejects_negative_observation_time():
    """RawWellResult with negative observation_time_h must be rejected."""
    raised, exc = assert_raises(TemporalCausalityError, lambda: RawWellResult(
        location=SpatialLocation(plate_id="P1", well_id="A01"),
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        assay=AssayType.CELL_PAINTING,
        observation_time_h=-2.0,  # INVALID: negative time
        readouts={"viability": 0.95},
    ))

    assert raised, "Should raise TemporalCausalityError for negative observation_time_h"
    assert "negative" in str(exc).lower()
    assert "-2.0" in str(exc)


def test_raw_well_result_accepts_valid_time():
    """RawWellResult with valid observation_time_h is accepted."""
    result = RawWellResult(
        location=SpatialLocation(plate_id="P1", well_id="A01"),
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        assay=AssayType.CELL_PAINTING,
        observation_time_h=24.0,  # VALID
        readouts={"viability": 0.95},
    )
    assert result.observation_time_h == 24.0


# ============================================================================
# Legacy adapter tests (ensure validation NOT bypassed)
# ============================================================================

class DummyWellSpec:
    """Mock WellSpec for testing legacy adapter."""
    def __init__(self, time_h=24.0):
        self.cell_line = "A549"
        self.compound = "DMSO"
        self.dose_uM = 0.0
        self.time_h = time_h
        self.assay = "cell_painting"
        self.position_tag = "center"


def test_legacy_adapter_does_not_bypass_negative_time_validation():
    """Legacy adapter must NOT bypass temporal causality validation.

    If WellSpec has invalid time_h, adapter translation MUST fail
    because Well.__post_init__ validates.
    """
    spec = DummyWellSpec(time_h=-1.0)  # INVALID: negative time

    raised, exc = assert_raises(TemporalCausalityError, lambda: well_spec_to_well(spec))

    assert raised, "Legacy adapter should not bypass temporal validation"
    assert "negative" in str(exc).lower()


def test_legacy_adapter_accepts_valid_time():
    """Legacy adapter with valid time_h produces valid Well."""
    spec = DummyWellSpec(time_h=24.0)
    well = well_spec_to_well(spec)

    assert well.observation_time_h == 24.0
    assert well.treatment_start_time_h == 0.0  # Default


# ============================================================================
# Error message quality tests
# ============================================================================

def test_error_message_includes_observation_time():
    """Error messages must include observation_time_h for debugging."""
    raised, exc = assert_raises(TemporalCausalityError, lambda: Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=-3.5,
        assay=AssayType.CELL_PAINTING,
    ))

    assert raised, "Should raise TemporalCausalityError"
    msg = str(exc)
    assert "observation_time_h=-3.5" in msg or "-3.5" in msg


def test_error_message_includes_treatment_compound():
    """Error messages should include treatment compound for context."""
    raised, exc = assert_raises(TemporalCausalityError, lambda: Well(
        cell_line="A549",
        treatment=Treatment(compound="tunicamycin", dose_uM=2.0),
        observation_time_h=-1.0,
        assay=AssayType.CELL_PAINTING,
    ))

    assert raised, "Should raise TemporalCausalityError"
    msg = str(exc)
    assert "tunicamycin" in msg


def test_error_message_includes_both_times_for_causality_violation():
    """Causality violation error must show both observation and treatment times."""
    raised, exc = assert_raises(TemporalCausalityError, lambda: Well(
        cell_line="A549",
        treatment=Treatment(compound="DMSO", dose_uM=0.0),
        observation_time_h=10.0,
        assay=AssayType.CELL_PAINTING,
        treatment_start_time_h=20.0,
    ))

    assert raised, "Should raise TemporalCausalityError"
    msg = str(exc)
    # Must show both times for debugging
    assert ("10.0" in msg or "observation_time_h=10.0" in msg)
    assert ("20.0" in msg or "treatment_start_time_h=20.0" in msg)


# ============================================================================
# Documentation/contract tests
# ============================================================================

def test_temporal_causality_module_exists():
    """Temporal causality module must exist and be importable."""
    from cell_os.core import temporal_causality
    assert temporal_causality is not None


def test_temporal_causality_error_is_exception():
    """TemporalCausalityError must be an Exception subclass."""
    assert issubclass(TemporalCausalityError, Exception)


def test_well_docstring_documents_temporal_invariants():
    """Well docstring must document temporal invariants."""
    doc = Well.__doc__.lower()
    assert "treatment_start_time_h" in doc
    assert "observation_time_h" in doc
    assert "invariant" in doc or "causality" in doc


# ============================================================================
# Test runner
# ============================================================================

def run_all_tests():
    """Run all tests and report results."""
    tests = [
        ("Reject negative observation time", test_well_rejects_negative_observation_time),
        ("Reject negative treatment start time", test_well_rejects_negative_treatment_start_time),
        ("Reject observation before treatment", test_well_rejects_observation_before_treatment),
        ("Reject tiny negative observation time", test_well_rejects_exact_negative_boundary),
        ("Reject tiny causality violation", test_well_rejects_observation_before_treatment_by_epsilon),
        ("Accept zero observation time", test_well_accepts_zero_observation_time),
        ("Accept observation equals treatment start", test_well_accepts_observation_equals_treatment_start),
        ("Accept observation after treatment", test_well_accepts_observation_after_treatment),
        ("Default treatment start to zero", test_well_defaults_treatment_start_to_zero),
        ("RawWellResult rejects negative time", test_raw_well_result_rejects_negative_observation_time),
        ("RawWellResult accepts valid time", test_raw_well_result_accepts_valid_time),
        ("Legacy adapter does not bypass validation", test_legacy_adapter_does_not_bypass_negative_time_validation),
        ("Legacy adapter accepts valid time", test_legacy_adapter_accepts_valid_time),
        ("Error message includes observation time", test_error_message_includes_observation_time),
        ("Error message includes compound", test_error_message_includes_treatment_compound),
        ("Error message includes both times", test_error_message_includes_both_times_for_causality_violation),
        ("Temporal causality module exists", test_temporal_causality_module_exists),
        ("TemporalCausalityError is Exception", test_temporal_causality_error_is_exception),
        ("Well docstring documents invariants", test_well_docstring_documents_temporal_invariants),
    ]

    print("=" * 80)
    print("Temporal Causality Enforcement Tests")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            print(f"Running: {name}")
            result = test_func()
            if result:
                print(f"  ✓ PASS\n")
                passed += 1
            else:
                print(f"  ✗ FAIL: Test returned False\n")
                failed += 1
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}\n")
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()
            print()
            failed += 1

    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 80)

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
