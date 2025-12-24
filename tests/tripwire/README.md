# Tripwire Tests: Enforcing STATE_MAP.md

**Status**: ✅ 9/10 passing, 1 skipped

These tests enforce the world model contract specified in `STATE_MAP.md` at the repo root.

## Purpose

Tripwire tests are designed to **fail loudly** if the implementation diverges from the specification.
They are:
- **Brutally minimal**: Test one invariant per test
- **Refactor-resistant**: Use `_harness.py` to abstract API changes
- **Fast**: Run in <10 seconds total

## Test Categories

### 1. `test_no_truth_leak.py`
Verifies no ground truth leakage to agent observations.

**Tests**:
- `test_debug_truth_disabled_by_default`: Debug gates are off by default
- `test_no_forbidden_keys_in_observations`: Blunt substring matching for oracle fields
- `test_observations_only_contain_known_keys`: Allowlist enforcement

**Failure mode**: Ground truth (viability, death fields, latent stress) is visible to agent.

### 2. `test_concentration_spine_consistency.py`
Verifies concentration/volume consistency between InjectionManager (authoritative) and VesselState (cached).

**Tests**:
- `test_compound_concentration_synced_after_treatment`: Cached == authoritative after treatment
- `test_concentration_synced_after_evaporation`: Cached == authoritative after evaporation
- `test_injection_manager_is_authoritative`: Meta-test documenting authority

**Failure mode**: Cached state has diverged from authoritative. World model is lying to itself.

### 3. `test_measurement_purity.py`
Verifies measurements NEVER mutate world state (observer independence).

**Tests**:
- `test_count_cells_does_not_mutate`: Cell count measurement is read-only
- `test_cell_painting_does_not_mutate`: Cell painting measurement is read-only
- `test_measurement_order_independence`: Measurement order doesn't affect state
- `test_wash_and_fixation_are_not_measurements`: Handling physics CAN mutate (intentional)

**Failure mode**: Measurements are backacting on physics. Breaks counterfactual reasoning.

## Test Harness

`_harness.py` provides stable API abstraction to survive refactors.

**Key functions**:
- `make_vm(seed)`: Create BiologicalVirtualMachine
- `seed_vm_vessel(vm, vessel_id, ...)`: Seed a vessel
- `make_world(seed, budget_wells)`: Create ExperimentalWorld
- `run_world(world, wells)`: Run experiment with simple well specs
- `get_vessel_state(vm, vessel_id)`: Get vessel state (handles different attribute names)
- `get_injection_manager_state(vm, vessel_id)`: Get injection manager state

**Why it exists**: API signatures change. All tripwire fragility is isolated to this one file.

## Running Tests

```bash
# All tripwire tests
pytest tests/tripwire/ -v

# Individual test file
pytest tests/tripwire/test_no_truth_leak.py -v

# Specific test
pytest tests/tripwire/test_no_truth_leak.py::test_no_forbidden_keys_in_observations -v
```

## Enforcement

**CI**: These tests run on every commit.
**Failure protocol**: If a tripwire fails, either:
1. Fix the bug (implementation diverged from spec)
2. Update `STATE_MAP.md` and tripwire (spec changed intentionally)

**Never silence a tripwire without updating both spec and test.**

## Adding New Tripwires

1. Add test to appropriate file (or create new file)
2. Use `_harness.py` functions only (no direct API calls)
3. Keep test brutally minimal (one invariant)
4. Document failure mode in docstring
5. Update `STATE_MAP.md` Section 8 (Enforcement)

## Known Limitations

- `test_wash_and_fixation_are_not_measurements`: Skipped (wash/fix not in current BVM API)
- Tests assume `seed=0` determinism (documented in STATE_MAP.md Section 6)
