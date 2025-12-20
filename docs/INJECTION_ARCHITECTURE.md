# Realism Injection Architecture

**Date**: 2025-01-20
**Status**: Architecture defined, Injection A implemented and tested

---

## Overview

The Injection System provides a consistent interface for adding coupled, low-level realities to the biological simulator. Each injection module follows the same pattern to ensure clean integration and composability.

**Design Philosophy**: Realism comes from interfaces between subsystems (biology ↔ environment ↔ operations ↔ measurement ↔ analysis), not from adding more knobs in isolation.

**Guiding Question**: "What would a smart agent exploit that a real lab would punish?"

---

## Architecture Components

### 1. Base Interface (`injections/base.py`)

All injections implement the `Injection` protocol:

```python
class Injection(ABC):
    def create_state(vessel_id, context) -> InjectionState
    def apply_time_step(state, dt, context) -> None
    def on_event(state, context) -> None
    def get_biology_modifiers(state, context) -> Dict
    def get_measurement_modifiers(state, context) -> Dict
    def pipeline_transform(observation, state, context) -> Dict
```

### 2. Injection State

Each injection defines its own `InjectionState` dataclass with:
- State variables (volume, masses, latents, etc.)
- `check_invariants()` method (conservation laws, fail-fast)
- Derived properties (concentrations, stresses, etc.)

### 3. Injection Manager

Orchestrates multiple injections:
- Registers injections
- Initializes vessel states
- Composes modifiers from all injections
- Ensures invariants checked after every update

### 4. Injection Context

Provides read-only access to:
- Simulated time
- Run context (batch effects)
- Event metadata (operation type, params)
- Spatial context (well position, plate ID)
- Operator/instrument context

---

## Five Priority Injections

Based on behavioral impact, implement in this order:

### A. Volume + Evaporation Field ✅ IMPLEMENTED

**Status**: Implemented and tested (4/4 tests passing)

**State Variables**:
- `vol_uL`: Liquid volume
- `compound_mass`, `nutrient_mass`, `waste_mass`: Solute amounts
- `evap_field[x,y]`: Position-dependent evaporation rate

**Invariants**:
- Non-negativity (volume, masses >= 0)
- Mass accounting (evaporation removes volume only)
- Concentration honesty (always mass/volume)

**Exploits Blocked**:
- "Ignore position effects" → Edge wells drift in dose/nutrients
- "Perfect concentration control" → Dose changes over time
- "Infinite micro-operations" → Dilution chaos

**New Pathologies**:
- Edge wells systematically weird
- Late timepoints drift without intervention
- Accidental dilution from over-washing
- Osmolality stress masquerades as mechanism signals

**Tests**: `test_volume_evaporation_injection.py` (4/4 passing)

---

### B. Operation Scheduling + Queueing ⏳ NEXT

**State Variables**:
- `event_queue`: Operations with start/end times, sequence index
- `incubator_state`: Door open indicator, temp/CO2 transients
- `outside_incubator_time_s[t]`: Cumulative exposure
- `handling_stress[t]`: Latent accumulated stress

**Invariants**:
- Time is real (operations consume time, not instantaneous)
- Order is real (first vs last well different exposure)
- Queue contention (one instrument can't multitask)

**Exploits Blocked**:
- "Batch all operations instantly"
- "High-frequency micro-cycling"
- "Perfectly timed interventions across all wells"

**New Pathologies**:
- Non-stationary conditions after door openings
- Position-in-queue artifacts masquerade as biology
- Scheduling becomes real decision variable

**Dependencies**: Should come early (defines action semantics)

---

### C. Washout Efficiency + Reservoir ⏳ PENDING

**State Variables**:
- `free_compound_mass`: Free in solution
- `adsorbed_compound_mass`: Plastic-bound reservoir
- `intracellular_compound_proxy`: Optional single compartment
- `washout_efficiency`: Function of volume exchange, mixing, compound stickiness

**Invariants**:
- Washout cannot exceed physics (removes only free fraction)
- Reservoir dynamics causal (adsorption → desorption over time)
- No magical reset (washout ≠ zero exposure)

**Exploits Blocked**:
- "Pulse dose then washout perfectly"
- "Use washout as free observation hack"

**New Pathologies**:
- Hysteresis (same concentration, different behavior due to history)
- Sticky compounds behave like long tails
- "I washed, why is it still happening?"

**Dependencies**: Depends on Injection A (mass-based concentrations)

---

### D. MNAR Missingness + Segmentation Distortion ⏳ PENDING

**State Variables**:
- `image_quality_latents`: Focus, illumination, debris
- `segmentation_error_mode`: Under/over segmentation probability
- `missingness_flags`: Per-readout missing indicators
- `missingness_mechanism`: Tied to confluence, death, edge, stress
- `feature_distortion_model`: Maps true → observed features

**Invariants**:
- Observation ≠ truth (never alter biology to explain missing feature)
- MNAR is causal (missingness depends on latent states)
- Distortion is systematic (not just extra noise)

**Exploits Blocked**:
- "Trust segmentation-based features always"
- "Choose regimes that produce clean readouts only"
- "Assume missing data is ignorable"

**New Pathologies**:
- Selection bias (only see survivors)
- Edge wells fail more (spatially structured missingness)
- Failure cascades (bad handling → more missingness → more interventions → worse handling)

**Dependencies**: Can add after A + B (handling stress), but also works standalone

---

### E. Lineage-Correlated Drift ⏳ PENDING

**State Variables**:
- `lineage_id`: Persistent across passages
- `drift_latents`: Growth bias, stress sensitivity, morphology offset per axis
- `passage_number`: Tracked per lineage
- `drift_process`: Random walk variance, occasional jump probability

**Invariants**:
- Within-lineage continuity (successive passages correlated)
- Between-lineage diversity (different lineages diverge)
- Drift ≠ context (don't let RunContext explain away lineage effects)

**Exploits Blocked**:
- "Assume perfect reproducibility across runs"
- "Overfit to one run's quirks"
- "Reset the world by restarting"

**New Pathologies**:
- Apparent non-reproducibility that is actually real
- Slow degradation/improvement trends confound causal attribution
- False "discoveries" unless inference models lineage

**Dependencies**: Can implement after core biology stable. Becomes more meaningful once A-D active.

---

## Integration with BiologicalVirtualMachine

### Current Architecture

```
BiologicalVirtualMachine
├── vessel_states: Dict[str, VesselState]
├── run_context: RunContext
├── rng_* : Separate RNG streams
└── Methods: seed_vessel, advance_time, treat_with_compound, etc.
```

### After Injection Integration

```
BiologicalVirtualMachine
├── vessel_states: Dict[str, VesselState]
├── run_context: RunContext
├── injection_manager: InjectionManager  ← NEW
│   ├── Registered injections (A, B, C, D, E)
│   └── Per-vessel injection states
├── rng_* : Separate RNG streams
└── Methods: (modified to call injection hooks)
```

### Hook Points

1. **Vessel Creation** (`seed_vessel`):
   ```python
   self.injection_manager.initialize_vessel(vessel_id, context)
   ```

2. **Time Step** (`_step_vessel`):
   ```python
   # Before biology updates
   self.injection_manager.apply_time_step(vessel_id, hours, context)

   # Get modifiers for biology
   bio_mods = self.injection_manager.get_biology_modifiers(vessel_id, context)
   # Apply to compound concentrations, nutrients, stress, etc.
   ```

3. **Operations** (`treat_with_compound`, `feed_vessel`, `washout_compound`):
   ```python
   context = InjectionContext(
       simulated_time=self.simulated_time,
       run_context=self.run_context,
       event_type='dispense',  # or 'feed', 'washout', etc.
       event_params={'volume_uL': 100.0, 'compound_mass': dose_amount}
   )
   self.injection_manager.on_event(vessel_id, context)
   ```

4. **Assays** (`cell_painting_assay`, `atp_viability_assay`):
   ```python
   # Get measurement modifiers
   meas_mods = self.injection_manager.get_measurement_modifiers(vessel_id, context)
   # Apply to intensity, segmentation quality, noise

   # Apply pipeline transforms
   observation = self.injection_manager.pipeline_transform(observation, vessel_id, context)
   ```

---

## Critical Path and Implementation Order

### Phase 1: Foundation (DONE)
- ✅ Define base interface (`base.py`)
- ✅ Implement Injection A (Volume + Evaporation)
- ✅ Create keeper-of-honesty tests
- ✅ Verify pattern works (all tests passing)

### Phase 2: Integration (NEXT)
1. Add `InjectionManager` to `BiologicalVirtualMachine.__init__`
2. Add injection hooks to `seed_vessel`, `_step_vessel`, operations, assays
3. Register Injection A and verify integration tests pass
4. Update existing tests to handle injection modifiers

### Phase 3: Expand (Sequential)
1. **Injection B** (Operation Scheduling)
   - Defines action semantics
   - Adds time/order realism
   - Required before C and D make sense

2. **Injection A + B Integration**
   - Verify volume and scheduling compose correctly
   - Test edge cases (queue + evaporation)

3. **Injection C** (Washout Efficiency)
   - Depends on A (mass accounting)
   - Benefits from B (timing matters)

4. **Injection D** (MNAR + Segmentation)
   - Depends on A + B (handling stress)
   - Forces robust inference

5. **Injection E** (Lineage Drift)
   - Long-horizon texture
   - Most meaningful when A-D already biting

---

## Testing Strategy

Each injection follows the same test pattern:

### 1. Invariant Tests
- Non-negativity (no negative values)
- Conservation laws (mass, volume accounting)
- Causal ordering (effects follow causes)

### 2. Exploit Tests
- Verify agent can't bypass realism
- Show that naive policies fail
- Demonstrate failure modes are realistic

### 3. Composition Tests (Integration)
- Multiple injections compose correctly
- Modifiers don't double-apply
- Invariants hold under all injection combinations

### 4. Keeper-of-Honesty Tests
- Prevent semantic drift (like `test_microtubule_double_counting.py`)
- Catch regressions in realism
- Guard against "feel right while being wrong"

---

## Uncomfortable Questions (Keep Asking)

1. **If the agent starts losing, will we fix the reward or fix the world?**
   - These injections will make agents look worse before better
   - That's the point
   - Treat agent failure as information, not bug

2. **What would a smart agent exploit that a real lab would punish?**
   - Use this to discover missing injections
   - Every exploit is a gap in realism

3. **Are we optimizing for belief integrity or action selection?**
   - Always choose belief integrity
   - False certainty transfers nowhere
   - Better to learn slowly on hard problems than quickly on lies

---

## File Structure

```
src/cell_os/hardware/injections/
├── __init__.py                    # Package exports
├── base.py                        # Base interfaces (InjectionState, Injection, InjectionManager)
├── volume_evaporation.py         # Injection A (IMPLEMENTED)
├── operation_scheduling.py       # Injection B (TODO)
├── washout_reservoir.py          # Injection C (TODO)
├── mnar_segmentation.py          # Injection D (TODO)
└── lineage_drift.py              # Injection E (TODO)

test_*_injection.py               # Keeper-of-honesty tests per injection
```

---

## Next Steps

1. **Integrate Injection A** into `BiologicalVirtualMachine`
   - Add `InjectionManager` to `__init__`
   - Add hooks to vessel lifecycle
   - Update existing tests

2. **Implement Injection B** (Operation Scheduling)
   - Define `OperationSchedulingState`
   - Implement queue mechanics
   - Create keeper-of-honesty tests

3. **Test A + B Composition**
   - Verify volume and scheduling interact correctly
   - No double-application of effects
   - Invariants hold under both

4. **Continue with C, D, E** following same pattern

---

## Success Metrics

The injection system is working when:

1. **Agent can't cheat anymore**: Naive policies fail in realistic ways
2. **Failures are informative**: Can distinguish artifact from biology
3. **Invariants never violated**: Conservation laws enforced everywhere
4. **Composition is clean**: Multiple injections don't interfere
5. **Tests prevent regression**: Keeper-of-honesty tests catch semantic drift

**Ultimate test**: Policies trained in simulator transfer to real wet lab.

---

## References

- [Epistemic Honesty Philosophy](EPISTEMIC_HONESTY_PHILOSOPHY.md)
- [Phase 6 Realism Roadmap](PHASE_6_REALISM_ROADMAP.md)
- [Final Sharp Edges Fixed](../FINAL_SHARP_EDGES_FIXED.md)

**Last Updated**: 2025-01-20
