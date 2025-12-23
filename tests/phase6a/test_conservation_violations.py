"""
Test that conservation violations cause hard errors, not silent laundering.

Invariant: Any conservation violation either:
1. Is corrected by explicit, named repair with audit record, OR
2. Causes a hard error

"unknown" death is NEVER the sink for violations.
"""

import sys
import numpy as np
import pytest
from src.cell_os.hardware.biological_virtual import (
    BiologicalVirtualMachine,
    VesselState,
    ConservationViolationError
)


def test_ledger_overflow_causes_hard_error():
    """
    Force a scenario where tracked deaths exceed total death.

    This should raise ConservationViolationError, NOT silently renormalize into death_unknown.

    Scenario: Manually corrupt ledgers to violate conservation, then call _update_death_mode().
    """
    vm = BiologicalVirtualMachine(seed=42)

    # Create a vessel with some death
    vm.seed_vessel("test_well", "A549", 1e6)
    vessel = vm.vessel_states["test_well"]

    # Kill 30% of cells via proper mechanism
    vessel.viability = 0.70
    vessel.cell_count *= 0.70

    # Corrupt ledgers: allocate more death than actually occurred
    # This simulates a bug where multiple mechanisms over-credit death
    vessel.death_compound = 0.15
    vessel.death_er_stress = 0.10
    vessel.death_mito_dysfunction = 0.10
    # Total tracked: 0.35, but only 0.30 died (viability 0.70 means 0.30 dead)

    # This should FAIL LOUDLY, not silently renormalize
    try:
        vm._update_death_mode(vessel)
        # If we get here, the bug exists: violation was laundered
        print("❌ FAIL: Ledger overflow was silently laundered, did not raise")
        print(f"   Tracked: {vessel.death_compound + vessel.death_er_stress + vessel.death_mito_dysfunction:.3f}")
        print(f"   Total dead: {1.0 - vessel.viability:.3f}")
        print(f"   death_unknown: {vessel.death_unknown:.3f}")
        return False
    except ConservationViolationError as e:
        # This is what we want
        print(f"✓ PASS: Raised ConservationViolationError: {e}")
        return True
    except Exception as e:
        print(f"❌ FAIL: Wrong exception type: {type(e).__name__}: {e}")
        return False


def test_negative_viability_causes_hard_error():
    """
    Force viability to go negative (impossible).

    This should raise immediately, not get clamped silently.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_well", "A549", 1e6)
    vessel = vm.vessel_states["test_well"]

    # Manually corrupt viability (simulates bug where death is over-applied)
    vessel.viability = -0.1

    try:
        vm._update_death_mode(vessel)
        print("❌ FAIL: Negative viability was silently clamped, did not raise")
        print(f"   Viability after _update_death_mode: {vessel.viability:.3f}")
        return False
    except ConservationViolationError as e:
        print(f"✓ PASS: Raised ConservationViolationError: {e}")
        return True
    except Exception as e:
        print(f"❌ FAIL: Wrong exception type: {type(e).__name__}: {e}")
        return False


def test_renormalization_creates_audit_record():
    """
    If renormalization happens in _commit_step_death, it should be flagged.

    The _step_ledger_scale should be recorded and warnings logged.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_well", "A549", 1e6)
    vessel = vm.vessel_states["test_well"]

    # Set up hazards that will cause renormalization
    vessel._step_hazard_proposals = {
        "death_compound": 0.15,
        "death_er_stress": 0.10,
        "death_mito_dysfunction": 0.10,
    }
    vessel._step_viability_start = 0.80
    vessel._step_cell_count_start = vessel.cell_count

    # Manually inflate death to force conservation violation
    # Simulate a bug where ledgers drift
    vessel.death_compound = 0.20  # Already had some death

    # Commit step death (this will add more death from proposals)
    # This should now raise ConservationViolationError instead of renormalizing
    with pytest.raises(ConservationViolationError, match="Ledger overflow"):
        vm._commit_step_death(vessel, hours=1.0)


def test_unknown_death_is_only_for_seeding_stress_not_violations():
    """
    death_unknown should only capture:
    - Seeding stress (initial viability < 1.0)
    - Contamination events (explicit)

    It should NEVER be used to launder conservation violations.
    """
    vm = BiologicalVirtualMachine(seed=42)

    # Seed with perfect viability
    vm.seed_vessel("test_well", "A549", 1e6, initial_viability=1.0)
    vessel = vm.vessel_states["test_well"]

    # Manually corrupt ledgers to violate conservation
    vessel.viability = 0.70
    vessel.death_compound = 0.20
    vessel.death_er_stress = 0.15
    # Total tracked: 0.35, actual dead: 0.30

    # Call _update_death_mode() which currently fills death_unknown as residual
    # This should FAIL instead of silently laundering into death_unknown
    try:
        vm._update_death_mode(vessel)
        print("❌ FAIL: Violation was laundered into death_unknown")
        print(f"   death_unknown: {vessel.death_unknown:.3f}")
        return False
    except ConservationViolationError as e:
        print(f"✓ PASS: Raised ConservationViolationError: {e}")
        return True
    except Exception as e:
        print(f"❌ FAIL: Wrong exception type: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Conservation Violation Enforcement")
    print("=" * 70)
    print()

    tests = [
        ("Ledger overflow causes hard error", test_ledger_overflow_causes_hard_error),
        ("Negative viability causes hard error", test_negative_viability_causes_hard_error),
        ("Renormalization creates audit record", test_renormalization_creates_audit_record),
        ("unknown death not used for violations", test_unknown_death_is_only_for_seeding_stress_not_violations),
    ]

    results = []
    for name, test_func in tests:
        print(f"\nTest: {name}")
        print("-" * 70)
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ EXCEPTION: {type(e).__name__}: {e}")
            results.append((name, False))
        print()

    print("=" * 70)
    print("Summary:")
    print("=" * 70)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    print()
    print(f"Total: {passed}/{total} passed")
    print("=" * 70)

    sys.exit(0 if passed == total else 1)
