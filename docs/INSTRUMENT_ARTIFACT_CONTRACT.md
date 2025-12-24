# Instrument Artifact Contract

## Purpose

This contract prevents artifact sprawl and ensures separation of concerns. Every artifact module must explicitly declare its domain, what it affects, and what it must NOT depend on.

**If you can't fill out this contract, you don't have a clean artifact.**

---

## Contract Template

Every artifact module (`*_effects.py`) must expose an `ARTIFACT_SPEC` dict with:

```python
ARTIFACT_SPEC = {
    # 1. Domain (spatial, sequence, temporal, global)
    'domain': 'spatial' | 'sequence' | 'temporal' | 'global',

    # 2. State it mutates (what physical quantities change)
    'state_mutations': ['volume', 'effective_dose', 'edge_damage', ...],

    # 3. Observables it affects (what metrics see the artifact)
    'affected_observables': ['seg_yield', 'noise_mult', 'cp_quality', ...],

    # 4. Epistemic prior (parameter treated as non-identifiable)
    'epistemic_prior': {
        'parameter': 'gamma' | 'base_rate' | 'fraction' | ...,
        'distribution': 'Lognormal(mean=X, CV=Y)',
        'calibration_method': 'microscopy' | 'gravimetry' | 'dye_trace' | ...
    },

    # 5. Variance ledger terms (exactly 2: modeled + ridge)
    'ledger_terms': {
        'modeled': 'VAR_INSTRUMENT_*',
        'ridge': 'VAR_CALIBRATION_*',
    },

    # 6. Correlation group rules
    'correlation_groups': {
        'modeled': 'position' | 'tip_{id}' | 'plate' | ...,
        'ridge': 'ridge_name',
    },

    # 7. Anti-double-counting clause (what this artifact must NOT depend on)
    'forbidden_dependencies': ['serpentine_index', 'aspiration_angle', ...],

    # 8. Provenance
    'version': '1.0',
    'implemented': '2025-12-23',
    'tests': ['test_module_name.py']
}
```

---

## Current Artifact Contracts

### 1. Aspiration Effects

**File**: `src/cell_os/hardware/aspiration_effects.py`

```python
ARTIFACT_SPEC = {
    'domain': 'spatial',
    'state_mutations': ['edge_damage', 'debris_load'],
    'affected_observables': ['segmentation_yield', 'noise_mult'],
    'epistemic_prior': {
        'parameter': 'gamma',
        'distribution': 'Lognormal(mean=1.0, CV=0.35)',
        'calibration_method': 'microscopy'
    },
    'ledger_terms': {
        'modeled': 'VAR_INSTRUMENT_ASPIRATION_SPATIAL',
        'ridge': 'VAR_CALIBRATION_ASPIRATION_GAMMA',
    },
    'correlation_groups': {
        'modeled': 'aspiration_position',
        'ridge': 'aspiration_ridge',
    },
    'forbidden_dependencies': ['dispense_sequence', 'serpentine_index', 'time_since_start'],
    'version': '1.0',
    'implemented': '2025-12-23',
    'tests': ['test_aspiration_effects.py']
}
```

**Anti-double-counting clause**: Aspiration must NOT depend on dispense sequence or serpentine index. It is purely spatial (position + angle).

---

### 2. Evaporation Effects

**File**: `src/cell_os/hardware/evaporation_effects.py`

```python
ARTIFACT_SPEC = {
    'domain': 'spatial',
    'state_mutations': ['volume', 'effective_dose'],
    'affected_observables': ['effective_dose', 'concentration'],
    'epistemic_prior': {
        'parameter': 'base_evap_rate',
        'distribution': 'Lognormal(mean=0.5, CV=0.30)',
        'calibration_method': 'gravimetry'
    },
    'ledger_terms': {
        'modeled': 'VAR_INSTRUMENT_EVAPORATION_GEOMETRY',
        'ridge': 'VAR_CALIBRATION_EVAPORATION_RATE',
    },
    'correlation_groups': {
        'modeled': 'evaporation_geometry',
        'ridge': 'evaporation_ridge',
    },
    'forbidden_dependencies': ['dispense_sequence', 'sequence_index', 'aspiration_angle'],
    'version': '1.0',
    'implemented': '2025-12-23',
    'tests': ['test_evaporation_effects.py']
}
```

**Anti-double-counting clause**: Evaporation must NOT depend on dispense sequence or aspiration angle. It is purely spatial geometry + time.

---

### 3. Carryover Effects

**File**: `src/cell_os/hardware/carryover_effects.py`

```python
ARTIFACT_SPEC = {
    'domain': 'sequence',
    'state_mutations': ['effective_dose'],
    'affected_observables': ['effective_dose'],
    'epistemic_prior': {
        'parameter': 'carryover_fraction',
        'distribution': 'Lognormal(mean=0.005, CV=0.40)',
        'calibration_method': 'blank_after_hot'
    },
    'ledger_terms': {
        'modeled': 'VAR_INSTRUMENT_PIPETTE_CARRYOVER_SEQUENCE',
        'ridge': 'VAR_CALIBRATION_CARRYOVER_FRACTION',
    },
    'correlation_groups': {
        'modeled': 'carryover_tip_{tip_id}',
        'ridge': 'carryover_ridge',
    },
    'forbidden_dependencies': ['well_geometry', 'plate_position', 'edge_distance'],
    'version': '1.0',
    'implemented': '2025-12-23',
    'tests': ['test_carryover_effects.py']
}
```

**Anti-double-counting clause**: Carryover must NOT depend on well geometry or plate position. It is purely sequence + tip identity.

---

## Domain Definitions

### Spatial
- **Depends on**: Well position (row, column), plate geometry
- **Does NOT depend on**: Dispense order, time ordering, sequence adjacency
- **Examples**: Aspiration (angle), evaporation (edge-center), temperature (edge-center)

### Sequence
- **Depends on**: Dispense order, sequence adjacency, tip/channel identity
- **Does NOT depend on**: Well position, plate geometry
- **Examples**: Carryover (residual transfer), serial dilution error

### Temporal
- **Depends on**: Time since start, duration, incubation time
- **Does NOT depend on**: Position or sequence (time is independent axis)
- **Examples**: Reagent aging, instrument drift, incubation time drift

### Global
- **Depends on**: Plate-level or batch-level factors
- **Does NOT depend on**: Individual well position or sequence
- **Examples**: Stain batch variation, ambient temperature, reagent lot

---

## Integration Test Requirements

**File**: `tests/integration/test_artifact_contracts.py`

Must verify:

1. **Each artifact exposes `ARTIFACT_SPEC`**
   - aspiration_effects.ARTIFACT_SPEC exists
   - evaporation_effects.ARTIFACT_SPEC exists
   - carryover_effects.ARTIFACT_SPEC exists

2. **Required fields present**
   - domain, state_mutations, affected_observables
   - epistemic_prior, ledger_terms, correlation_groups
   - forbidden_dependencies, version, implemented, tests

3. **Domain-specific constraints**
   - spatial artifacts forbid sequence dependencies
   - sequence artifacts forbid geometry dependencies
   - exactly 2 ledger terms (modeled + ridge)

4. **Ledger term naming conventions**
   - modeled starts with `VAR_INSTRUMENT_`
   - ridge starts with `VAR_CALIBRATION_`

5. **Separation enforcement**
   - aspiration forbids dispense_sequence
   - carryover forbids well_geometry
   - evaporation forbids sequence_index

---

## Adding New Artifacts

To add a new artifact:

1. **Create module** `src/cell_os/hardware/new_artifact_effects.py`
2. **Implement 5-step pattern**:
   - Physics (deterministic + bounded)
   - Epistemic prior (non-identifiable parameter)
   - Ridge uncertainty (two-point bracket)
   - Calibration hook (Bayesian update)
   - Variance ledger integration
3. **Declare `ARTIFACT_SPEC`** at module level
4. **Write tests** with 100% coverage
5. **Update contract test** to include new artifact
6. **Document** in `docs/NEW_ARTIFACT_COMPLETE.md`

**If you can't declare the contract, you're not done.**

---

## Anti-Patterns (Do NOT Do This)

### ❌ Mixing Domains
```python
# BAD: Carryover depending on well position
def calculate_carryover(..., well_position: str):
    if well_position.startswith('A'):  # NO! This is spatial.
        ...
```

**Fix**: Carryover is sequence-only. Well position is irrelevant.

### ❌ Double-Counting
```python
# BAD: Evaporation depending on aspiration angle
def calculate_evaporation(..., aspiration_angle: float):
    exposure = base_exposure * (1 + aspiration_angle)  # NO!
```

**Fix**: Evaporation is independent of aspiration. Separate effects.

### ❌ Missing Ridge
```python
# BAD: Only recording modeled term
ledger.record(VAR_INSTRUMENT_THING)
# Missing: VAR_CALIBRATION_THING_RIDGE
```

**Fix**: Always record both modeled + ridge (even if ridge is zero).

### ❌ Wrong Correlation Group
```python
# BAD: Spatial artifact with sequence correlation group
ledger.record(VarianceContribution(
    term='VAR_INSTRUMENT_EVAPORATION',
    correlation_group='carryover_tip_A'  # NO! Wrong domain.
))
```

**Fix**: Spatial artifacts use position-based correlation groups.

---

## Versioning

**Version 1.0** (2025-12-23):
- Three artifacts: aspiration, evaporation, carryover
- 5-step pattern: physics → prior → ridge → calibration → ledger
- Correlation groups: spatial vs sequence
- Reporting scale: percent change + z-scores

**Future versions**:
- Add temporal domain (reagent aging, drift)
- Add global domain (stain batch, ambient conditions)
- Extend correlation groups (temporal adjacency, batch identity)

**Contract is stable** - new artifacts must conform to v1.0 contract.

---

## Conclusion

This contract ensures:

✓ **Separation**: Spatial ≠ sequence ≠ temporal ≠ global
✓ **No double-counting**: Forbidden dependencies enforced
✓ **Completeness**: All artifacts must declare modeled + ridge
✓ **Testability**: Integration test validates contract compliance
✓ **Extensibility**: New artifacts follow same 5-step pattern

**If it doesn't fit the contract, it doesn't go in the stack.**
