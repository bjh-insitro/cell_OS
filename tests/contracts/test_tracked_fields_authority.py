"""
Contract: TRACKED_DEATH_FIELDS is the single source of truth for proposable fields.

This enforces the operational rule:
- Proposable fields = TRACKED_DEATH_FIELDS (can be passed to _propose_hazard)
- Residual field = death_unattributed (computed, never proposed)
- Transport dysfunction = death_transport_dysfunction (stub, not active in Phase 2)

If this breaks:
- Someone added a new field without updating TRACKED_DEATH_FIELDS
- Someone made death_unattributed proposable (WRONG)
- Conservation checks will miss the new field (silent corruption)
"""

import pytest


def test_death_unattributed_excluded_from_tracked_fields():
    """
    death_unattributed must NOT be in TRACKED_DEATH_FIELDS.

    It's a computed residual, not a proposable cause.
    """
    from cell_os.hardware.constants import TRACKED_DEATH_FIELDS

    assert "death_unattributed" not in TRACKED_DEATH_FIELDS, \
        "death_unattributed is a residual field, not proposable"


def test_death_transport_dysfunction_excluded_from_tracked_fields():
    """
    death_transport_dysfunction must NOT be in TRACKED_DEATH_FIELDS (Phase 2 stub).

    This field exists in VesselState schema for forward compatibility but has no
    active hazard proposal. If you activate transport death, you MUST:
    1. Add to TRACKED_DEATH_FIELDS
    2. Add hazard proposal in _update_transport_dysfunction()
    3. Update _update_death_mode() threshold logic
    """
    from cell_os.hardware.constants import TRACKED_DEATH_FIELDS

    assert "death_transport_dysfunction" not in TRACKED_DEATH_FIELDS, \
        "death_transport_dysfunction is a Phase 2 stub (no hazard). See VesselState.__init__ for activation checklist."


def test_propose_hazard_rejects_death_unattributed():
    """
    _propose_hazard must raise ValueError for death_unattributed.

    This is the operational enforcement of "residual-only" semantics.
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, vessel_type='96-well')
    vessel = vm.vessel_states["P1_A01"]

    # Clean state
    vessel.viability = 1.0
    vessel._step_hazard_proposals = {}

    # Attempting to propose death_unattributed must fail
    with pytest.raises(ValueError, match="Unknown death_field"):
        vm._propose_hazard(vessel, 0.01, "death_unattributed")


def test_propose_hazard_rejects_death_transport_dysfunction():
    """
    _propose_hazard must raise ValueError for death_transport_dysfunction (Phase 2 stub).

    This field is in schema but not active. If you want to activate it:
    1. Add to TRACKED_DEATH_FIELDS
    2. This test will fail (update it to expect success)
    3. Add hazard proposal logic in stress mechanism
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, vessel_type='96-well')
    vessel = vm.vessel_states["P1_A01"]

    # Clean state
    vessel.viability = 1.0
    vessel._step_hazard_proposals = {}

    # Attempting to propose death_transport_dysfunction must fail (stub)
    with pytest.raises(ValueError, match="Unknown death_field"):
        vm._propose_hazard(vessel, 0.01, "death_transport_dysfunction")


def test_vessel_state_has_all_tracked_fields():
    """
    VesselState must have attributes for all TRACKED_DEATH_FIELDS.

    If this fails, someone added a field to TRACKED_DEATH_FIELDS but forgot
    to initialize it in VesselState.__init__.
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine, VesselState
    from cell_os.hardware.constants import TRACKED_DEATH_FIELDS

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, vessel_type='96-well')
    vessel = vm.vessel_states["P1_A01"]

    missing = []
    for field in TRACKED_DEATH_FIELDS:
        if not hasattr(vessel, field):
            missing.append(field)

    assert not missing, \
        f"VesselState missing attributes for TRACKED_DEATH_FIELDS: {missing}. " \
        f"Add initialization in VesselState.__init__."


def test_vessel_state_has_death_unattributed():
    """
    VesselState must have death_unattributed (residual field).

    This is the computed residual, not proposable but required for accounting.
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, vessel_type='96-well')
    vessel = vm.vessel_states["P1_A01"]

    assert hasattr(vessel, "death_unattributed"), \
        "VesselState missing death_unattributed (residual field)"


def test_tracked_fields_matches_vessel_state_death_fields():
    """
    TRACKED_DEATH_FIELDS should match active death_* fields in VesselState.

    This catches:
    - Field in TRACKED_DEATH_FIELDS but not in VesselState (typo)
    - Field in VesselState but not in TRACKED_DEATH_FIELDS (missing from list)

    Excluded: death_unattributed (residual), death_transport_dysfunction (stub)
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine, VesselState
    from cell_os.hardware.constants import TRACKED_DEATH_FIELDS

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, vessel_type='96-well')
    vessel = vm.vessel_states["P1_A01"]

    # Get all death_* attributes from VesselState
    vessel_death_fields = {
        attr for attr in dir(vessel)
        if attr.startswith("death_") and not attr.startswith("_")
    }

    # Excluded fields (residual + stubs + metadata)
    excluded = {
        "death_unattributed",  # Residual (computed, not proposed)
        "death_transport_dysfunction",  # Stub (not active in Phase 2)
        "death_total",  # Summary field
        "death_mode",  # Label field
        # Commitment metadata (not death fractions)
        "death_committed",  # Boolean flag
        "death_committed_at_h",  # Timestamp
        "death_commitment_mechanism",  # String label
        "death_commitment_stress_snapshot",  # Dict snapshot
    }

    active_vessel_fields = vessel_death_fields - excluded
    tracked_fields_set = set(TRACKED_DEATH_FIELDS)

    # Check for fields in VesselState but not tracked
    untracked = active_vessel_fields - tracked_fields_set
    if untracked:
        raise AssertionError(
            f"VesselState has death fields not in TRACKED_DEATH_FIELDS: {untracked}. "
            f"Add them to TRACKED_DEATH_FIELDS or mark as excluded if they are stubs/residuals."
        )

    # Check for fields in TRACKED_DEATH_FIELDS but not in VesselState
    missing = tracked_fields_set - active_vessel_fields
    if missing:
        raise AssertionError(
            f"TRACKED_DEATH_FIELDS contains fields not in VesselState: {missing}. "
            f"Add initialization in VesselState.__init__ or remove from TRACKED_DEATH_FIELDS if obsolete."
        )


def test_all_tracked_fields_are_proposable():
    """
    Every field in TRACKED_DEATH_FIELDS must be proposable (not raise ValueError).

    If this fails, TRACKED_DEATH_FIELDS contains a field that _propose_hazard rejects.
    This means either:
    - The field shouldn't be in TRACKED_DEATH_FIELDS (stub/residual)
    - The field is missing from _propose_hazard validation (bug)
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
    from cell_os.hardware.constants import TRACKED_DEATH_FIELDS

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, vessel_type='96-well')
    vessel = vm.vessel_states["P1_A01"]

    # Clean state
    vessel.viability = 1.0

    rejections = []
    for field in TRACKED_DEATH_FIELDS:
        vessel._step_hazard_proposals = {}
        try:
            vm._propose_hazard(vessel, 0.01, field)
        except ValueError as e:
            rejections.append((field, str(e)))

    assert not rejections, \
        f"TRACKED_DEATH_FIELDS contains non-proposable fields: {rejections}. " \
        f"Either remove from TRACKED_DEATH_FIELDS or fix _propose_hazard validation."


def test_tracked_fields_initialized_to_zero_at_seed():
    """
    All TRACKED_DEATH_FIELDS must be initialized to exactly 0.0 at seed time.

    This catches:
    - Forgot to initialize a field (None or missing)
    - Wrong type (np.float32 instead of float)
    - Non-zero initial value (leak from previous vessel)

    NOTE: death_unknown is an exception - it can be > 0 at seed due to seeding stress.
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
    from cell_os.hardware.constants import TRACKED_DEATH_FIELDS

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, vessel_type='96-well')
    vessel = vm.vessel_states["P1_A01"]

    # Special case: death_unknown can be > 0 due to seeding stress (realistic artifact)
    # All other fields must be exactly 0.0
    exceptions = {"death_unknown"}

    wrong_init = []
    for field in TRACKED_DEATH_FIELDS:
        if field in exceptions:
            continue

        value = getattr(vessel, field, None)

        # Check not None
        if value is None:
            wrong_init.append((field, "None", "forgot to initialize"))
            continue

        # Check exactly 0.0 (not just falsy)
        if value != 0.0:
            wrong_init.append((field, value, "non-zero initial value"))
            continue

        # Check type is float (not np.float32 or other)
        if not isinstance(value, float):
            wrong_init.append((field, value, f"wrong type: {type(value).__name__}"))

    assert not wrong_init, \
        f"TRACKED_DEATH_FIELDS have wrong initialization:\n" + \
        "\n".join(f"  {field}: {val} ({reason})" for field, val, reason in wrong_init) + \
        "\n\nAll fields must be initialized to exactly 0.0 (float) at seed time."


def test_tracked_fields_monotone_across_steps():
    """
    Death fields must be monotone non-decreasing across _step_vessel calls.

    Once a field is > 0, it can only increase (or stay same).
    Death is irreversible - no resurrection allowed.

    This catches:
    - Accidental reset during stepping
    - Negative hazard proposals
    - Conservation violations that decrease fields
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
    from cell_os.hardware.constants import TRACKED_DEATH_FIELDS, DEATH_EPS

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, vessel_type='96-well')
    vessel = vm.vessel_states["P1_A01"]

    # Apply treatment to cause death
    vm.treat_with_compound("P1_A01", "staurosporine", 0.5)

    # Capture initial state
    prev_values = {f: float(getattr(vessel, f, 0.0)) for f in TRACKED_DEATH_FIELDS}

    violations = []

    # Step through time and check monotonicity
    for step in range(5):
        vm.advance_time(1.0)  # 1h steps

        for field in TRACKED_DEATH_FIELDS:
            current = float(getattr(vessel, field, 0.0))
            previous = prev_values[field]

            # Allow small epsilon decrease for numerical noise
            if current < previous - DEATH_EPS:
                violations.append({
                    "field": field,
                    "step": step + 1,
                    "previous": previous,
                    "current": current,
                    "delta": current - previous
                })

            prev_values[field] = current

    assert not violations, \
        f"Death fields decreased (monotonicity violation):\n" + \
        "\n".join(
            f"  Step {v['step']}: {v['field']} went from {v['previous']:.6f} to {v['current']:.6f} (delta={v['delta']:.3e})"
            for v in violations
        ) + \
        "\n\nDeath is irreversible - fields must be monotone non-decreasing."
