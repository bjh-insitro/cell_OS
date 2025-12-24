"""
Tripwire Test: Concentration Spine Consistency

Enforces STATE_MAP.md Section 4: Single Source of Truth Rules

Tests the known smear: concentration/volume duality between
InjectionManager (authoritative) and VesselState (cached).

FAILURE MODE: If this test fails, cached state has diverged from authoritative.
World model is lying to itself.
"""

import pytest
from tests.tripwire._harness import (
    make_vm,
    seed_vm_vessel,
    get_vessel_state,
    get_injection_manager_state,
)


def test_compound_concentration_synced_after_treatment():
    """
    Verify cached compound concentration matches authoritative after treatment.

    STATE_MAP.md: VesselState.compounds is MIRRORED from InjectionManager.
    """
    vm = make_vm(seed=0)
    seed_vm_vessel(vm, 'v1')

    # Treat with compound
    vm.treat_with_compound('v1', compound='staurosporine', dose_uM=1.0)

    # Get both states
    vessel = get_vessel_state(vm, 'v1')
    exposure = get_injection_manager_state(vm, 'v1')

    # Check consistency
    authoritative_conc = exposure.compounds_uM.get('staurosporine', 0.0)
    cached_conc = vessel.compounds.get('staurosporine', 0.0)

    assert abs(cached_conc - authoritative_conc) < 1e-9, \
        f"Concentration desync: cached={cached_conc}, authoritative={authoritative_conc}"


def test_concentration_synced_after_evaporation():
    """
    Verify concentrations stay synced after evaporation.

    STATE_MAP.md: Evaporation concentrates compounds. Cached values must update.
    """
    vm = make_vm(seed=0)
    seed_vm_vessel(vm, 'v1')

    # Treat
    vm.treat_with_compound('v1', compound='staurosporine', dose_uM=1.0)

    # Advance time (evaporation occurs)
    vm.advance_time(hours=24.0)

    # Get both states
    vessel = get_vessel_state(vm, 'v1')
    exposure = get_injection_manager_state(vm, 'v1')

    # Check consistency
    authoritative_conc = exposure.compounds_uM['staurosporine']
    cached_conc = vessel.compounds['staurosporine']

    assert abs(cached_conc - authoritative_conc) < 1e-9, \
        f"Concentration desync after evaporation: cached={cached_conc}, " \
        f"authoritative={authoritative_conc}"


def test_injection_manager_is_authoritative():
    """
    Meta-test: Verify InjectionManager is the single source of truth.

    Documents that InjectionManager.get_state() is authoritative,
    and VesselState fields are views/caches.
    """
    vm = make_vm(seed=0)
    seed_vm_vessel(vm, 'v1')

    # Verify InjectionManager has state
    exposure = get_injection_manager_state(vm, 'v1')
    assert exposure is not None, "InjectionManager must have vessel state"

    # Verify it's authoritative
    assert hasattr(exposure, 'compounds_uM'), \
        "InjectionManager must have compounds_uM (authoritative)"
    assert hasattr(exposure, 'nutrients_mM'), \
        "InjectionManager must have nutrients_mM (authoritative)"
    assert hasattr(exposure, 'volume_mult'), \
        "InjectionManager must have volume_mult (authoritative)"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
