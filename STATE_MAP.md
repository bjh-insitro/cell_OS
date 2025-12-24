# State Map: World Model Contract

**Status**: Enforced by tripwire tests
**Last Updated**: 2025-12-23

This is the authoritative specification of the world model implementation.
The code MUST NOT lie about this document.

---

## 1. Entities and Authority

| Entity | Authority | Category | Notes |
|--------|-----------|----------|-------|
| **VesselState** | `src/cell_os/hardware/biological_virtual.py:152` | Physical | Core biological reality: cells, viability, stress |
| **VesselExposureState** | `src/cell_os/hardware/injection_manager.py:35` | Physical | **Authoritative concentration spine** |
| **VesselLifetime** | `src/cell_os/epistemic_agent/world.py:42` | Physical | Vessel usage tracking (assays, destruction) |
| **PlateInventory** | `src/cell_os/epistemic_agent/world.py:66` | Physical | Plate consumption and well allocation |
| **ExperimentalWorld** | `src/cell_os/epistemic_agent/world.py:118` | Control | World interface (NOT ground truth) |
| **BeliefState** | `src/cell_os/epistemic_agent/beliefs/state.py:103` | Belief | Agent epistemic state with provenance |
| **RawWellResult** | `src/cell_os/core/observation.py:18` | Observation | Immutable measurement output |
| **Subpopulations** | `VesselState.subpopulations:222` | Physical | **NOT epistemic: drives physics, visible to agent via scRNA** |

---

## 2. Mutation Rules

### VesselState (`biological_virtual.py`)

**Allowed Mutators**:
- `_update_vessel_growth()` (line 1243): Mutates `cell_count`, `confluence`
- `_commit_step_death()` (line 909): Mutates `viability`, `cell_count`, all `death_*` fields
- `_apply_instant_kill()` (line 839): Mutates `viability`, `cell_count`, one `death_*` field
  - **GUARDRAIL**: Cannot be called during `_step_vessel()` (enforced lines 861-865)
- `feed_vessel()` (line 1825): Mutates `current_volume_ml` (synced to InjectionManager)
- `treat_with_compound()` (line 2656): Mutates `compounds`, `compound_start_time`, `compound_meta`

**Forbidden Mutations**:
- **NEVER mutate during measurement** (`count_cells`, `cell_painting_assay`, `atp_viability_assay`)
- **NEVER mutate `current_volume_ml` directly** (must sync via InjectionManager)
- **NEVER mutate death fields outside death accounting functions**

**Death Accounting Invariants** (enforced by `_assert_conservation()`, line 994):
```python
sum(death_*) + viability == 1.0  (within 1e-6)
```

### VesselExposureState (`injection_manager.py`)

**Allowed Mutators**:
- `process_event()` (line 207): Event-driven mutations (SEED, TREAT, FEED, WASHOUT)
- `step()` (line 274): Time-evolution mutations (evaporation, concentration)

**Authoritative Fields**:
- `compounds_uM`: Ground truth compound concentrations
- `nutrients_mM`: Ground truth nutrient concentrations
- `volume_mult`: Evaporation drift multiplier

### BeliefState (`beliefs/state.py`)

**Allowed Mutators**:
- All mutations via `_set()` (line 302): Records provenance, validates causality
- `update()` (line 800): Processes observations
- `record_refusal()` (line 210): Tracks epistemic insolvency

**Immutable After Gate**:
- Once `noise_sigma_stable = True`, `noise_sigma_hat` cannot change (enforced line 115)

### RawWellResult (`observation.py`)

**IMMUTABLE**: `@dataclass(frozen=True)`

---

## 3. Observability Surface

### Agent-Visible (Through `ExperimentalWorld.run_experiment()`)

**Returned in RawWellResult**:
- Spatial location (`plate_id`, `well_id`)
- Treatment (`compound`, `dose`)
- Assay type
- Observation time
- Readouts dict:
  - Cell Painting: morphology channels, segmentation QC
  - LDH: `ldh_signal`, `atp_signal`, `upr_marker`, `trafficking_marker`
  - scRNA: gene counts, subpopulation fractions (VISIBLE)
- QC flags:
  - `well_failure`: Random instrument failures (deterministic by seed)
  - `qc_flag`: "FAIL" or "SEGMENTATION_FAIL"
  - Segmentation metadata: `merge_count`, `split_count`, `size_bias`, `segmentation_quality`

**QC fields are measurement artifacts, NOT ground truth**:
- Computed from observable quantities (confluence, debris)
- Do not directly expose viability, death causes, or latent states

### Hidden Ground Truth (NEVER exposed to agent)

**VesselState fields**:
- `viability` (line 159)
- `cell_count` (line 158)
- `death_compound`, `death_confluence`, `death_unknown`, `death_unattributed`, `death_starvation`, `death_mitotic_catastrophe`, `death_er_stress`, `death_mito_dysfunction` (lines 186-204)
- `er_stress`, `mito_dysfunction`, `transport_dysfunction` (lines 215-217)
- `compound_meta` (IC50 values, line 180)

**VesselExposureState fields**:
- `volume_mult` (evaporation multiplier)
- True compound concentrations (observable only via proxy measurements)

### Debug Gates

**Debug truth exposure** (lines 126-143 in `viability.py`):
- Gated by `run_context.debug_truth_enabled`
- **ONLY used in tests** (verified by grep)
- Returns `_debug_truth` dict with ground truth fields

**Diagnostic methods** (not for agent):
- `get_volume_diagnostics()`, `get_plate_diagnostics()`, `get_vessel_lifetime_diagnostics()` (`world.py`)
- `get_vessel_state()`, `get_rng_audit()` (`biological_virtual.py`)

**TRIPWIRE**: Test must verify `debug_truth_enabled` is never True in production runs

---

## 4. Single Source of Truth Rules

### Known Smear: Concentration/Volume Duality

**Problem** (`biological_virtual.py:169-177`):
- `VesselState.current_volume_ml` is a **cached copy** from InjectionManager
- `VesselState.compounds` is **mirrored** from `VesselExposureState.compounds_uM`
- Comment warns: "DO NOT mutate directly" (line 172)

**Current Mitigation**:
- Mirrored during `_step_vessel()` (line 1172, 1179)
- Synced explicitly during `feed_vessel()` (line 2071)

**Rule to Prevent Worsening**:
1. **NEVER read `VesselState.current_volume_ml` without checking InjectionManager first**
2. **NEVER mutate `VesselState.compounds` directly** (always via InjectionManager)
3. **New code MUST query InjectionManager, not cached fields**

**Future Fix** (not implemented):
- Move all concentration/volume state to InjectionManager
- VesselState becomes pure biology (cell_count, viability, stress)
- Eliminate caching/mirroring code

### Subpopulations: Physical, Not Epistemic

**CORRECTION**: `VesselState.subpopulations` (line 222) is **physical reality**, not belief.

**Any code that calls them "epistemic" is a bug, not a naming issue.**

**Evidence**:
- Evolves stress states independently (`er_stress.py:53-97`)
- Computes death hazards independently (line 105-109)
- IC50 shifts affect dose-response (line 84)
- **Visible to agent** (scRNA seq exposes fractions as part of observation surface, `scrna_seq.py:88-91`)

**Observation Surface**:
- **Subpopulation fractions ARE part of the scRNA observation**
- This is NOT a leak - it's real biology the agent should learn from
- IC50 shifts and stress thresholds remain hidden (as intended)

**Semantics**:
- 3 subpopulations: sensitive (25%), typical (50%), resistant (25%)
- `ic50_shift`: Scales compound potency (0.5 = 2× more sensitive)
- `stress_threshold_shift`: Scales death thresholds (0.8 = die earlier)
- Fractions are **fixed** (do not evolve over time)

**Implication for Counterfactuals**:
Since subpopulations shift IC50 and death hazards, they affect counterfactual dynamics.
Combined with "no rollback" (Section 7), this means branching across heterogeneous dynamics requires full replay from seed.

---

## 5. Causal Processes

### Growth

- **Implementation**: `_update_vessel_growth()` (`biological_virtual.py:1243`)
- **Equation**: Logistic ODE: `dN/dt = r_eff × N × (1 - N/K)`
- **Modulators**: lag, edge, context, contact, nutrients, stress (lines 1275-1318)
- **When**: Every `_step_vessel()` call during `advance_time()`

### Death

- **Compound attrition**: `_update_vessel_attrition()` (line 1354)
  - Uses `biology_core.compute_attrition_rate_interval_mean()` (line 1422)
- **Nutrient depletion**: `NutrientDepletionMechanism` (line 1202)
- **ER stress**: `ERStressMechanism` (line 1206)
- **Mito dysfunction**: `MitoDysfunctionMechanism` (line 1209)
- **Transport dysfunction**: `TransportDysfunctionMechanism` (line 1211)
- **All deaths committed**: `_commit_step_death()` (line 909) - ONCE per step

### Evaporation

- **Implementation**: `InjectionManager.step()` (`injection_manager.py:274`)
- **Equation**: `volume_new = volume_old × (1 - rate × dt)` (line 304)
- **Effect**: Concentrates all compounds and nutrients (lines 315-324)
- **When**: Every `advance_time()` call

### Handling Physics

- **Wash-induced detachment**: `wash_fix_core.wash_step_v2()` (line 2334)
  - **NOT death**: Cells removed to `cells_lost_to_handling`, `debris_cells` (lines 2363-2364)
- **Fixation**: `wash_fix_core.fixation_step_v2()` (line 2441)
  - Terminal operation: `is_destroyed = True` (line 2468)

---

## 6. Invariants

### Conservation Laws

**Death accounting** (enforced by `_assert_conservation()`, line 994):
```python
death_compound + death_confluence + death_unknown + death_unattributed +
death_starvation + death_mitotic_catastrophe + death_er_stress + death_mito_dysfunction +
viability == 1.0  (within 1e-6)
```

**Subpopulation fractions** (fixed at initialization):
```python
sum(subpop['fraction'] for subpop in vessel.subpopulations.values()) == 1.0
```

### Measurement Purity

**Enforced by assertions** (`count_cells`, line 2525-2532):
```python
assert vessel.cell_count == state_before[0]
assert vessel.viability == state_before[1]
assert vessel.confluence == state_before[2]
```

**Contract enforcement** (`@enforce_measurement_contract`, line 44 in `viability.py`):
- Reads allowed fields from whitelist
- Blocks writes to all fields
- Logs violations

### Determinism

**Seed contract** (`standalone_cell_thalamus.py:183-230`):
- `seed=0`: Fully deterministic (physics + measurements)
- Three isolated RNG streams: growth, treatment, assay (lines 197-199)
- Stable hashing for cross-machine determinism (lines 157-172)

**Eliminated non-determinism**:
- Python `hash()` replaced with `stable_u32()` (uses Blake2s)
- Set iteration order: sorted lists
- RNG stream isolation: observer cannot perturb physics

---

## 7. Counterfactual Reasoning Constraint

**No rollback mechanism exists**.

**State is**:
- Forward-propagated only
- Not checkpointed for rewind
- Irreversible (destroyed vessels stay destroyed)

**To reconstruct state**:
- Must replay from seed with same event sequence
- No incremental rollback support

**Implication**: Counterfactual reasoning is currently an **external replay capability**, not an internal world-model feature. Agent policy cannot compare branches without re-running the simulation.

---

## 8. Enforcement

This document is enforced by three tripwire tests in `tests/tripwire/`:

1. **`test_no_truth_leak.py`**
   - Verifies `debug_truth_enabled` is False in production
   - Asserts RawWellResult contains no forbidden keys

2. **`test_concentration_spine_consistency.py`**
   - After every `advance_time()` + event, asserts:
     - InjectionManager concentration == mirrored VesselState (within tolerance)

3. **`test_measurement_purity.py`**
   - Intentionally attempts mutation during measurement
   - Proves contract enforcement catches violations

**Tests run on every commit** (CI enforcement).

**Test Harness**: `tests/tripwire/_harness.py` provides stable API abstraction to survive refactors.

**CI Gate**: Tripwire tests run **first** in CI (`.github/workflows/ci.yml`).
All other tests blocked until tripwires pass.
Failure is not a bug—it's a signal that the world model contract has changed.

---

## Revision History

- **2025-12-23**: Initial contract based on forensic audit
- Subpopulations clarified as physical, not epistemic
- Ground truth leakage audit confirmed (QC fields are measurement artifacts)
- Concentration spine smear documented as known technical debt
