# Agent vs Standalone Discrepancy

## Problem

The Cell Thalamus system has **two separate simulation implementations** that have diverged:

1. **Standalone simulation** (`standalone_cell_thalamus.py`) - Used for production runs
2. **Agent class** (`biological_virtual.py`) - Used by test scripts and agent execution

## Key Differences

### Compound Parameters

**Standalone**:
- Embedded parameters (lines 420-448)
- Nocodazole EC50: 0.5 µM with cell-line-specific multipliers
- iPSC_NGN2: IC50 = 0.5 × 3.867 = **1.93 µM**

**Agent**:
- Loads from `simulation_parameters.yaml`
- Nocodazole not defined for iPSC_NGN2 → uses default IC50 = **40.0 µM**
- Result: Compound has almost no effect (99.93% viability at 0.3 µM)

### Time-Dependent Death

**Standalone**:
- Has full time-dependent death continuation logic (lines 920-967)
- Applies attrition when `dose_ratio >= 1.0` and `viability < 0.5`
- For microtubule drugs on neurons: uses morphology-to-attrition feedback

**Agent**:
- NO time-dependent death continuation
- Only instant dose-response
- Death at long timepoints comes from overconfluence, not compound effects

### Morphology-to-Attrition Feedback

**Standalone**:
- Computes `transport_dysfunction_score` from structural morphology (lines 785-796)
- Uses it to scale attrition rate (lines 940-953)
- Nonlinear scaling: `attrition_scale = 1.0 + 2.0 * (dys^2)`

**Agent**:
- Computes `transport_dysfunction_score` (biological_virtual.py lines 812-825)
- Stores it in `vessel.transport_dysfunction`
- But NEVER USES IT - no attrition logic at all

## Impact on Tests

Test scripts use the agent class, so they don't benefit from the biology improvements:

### test_low_dose_recovery.py
- **Expected**: Low doses (<1 µM) should show high viability at 96h (dose << IC50)
- **Actual**: Shows 0% viability due to overconfluence (cells overgrow well capacity)
- **Root cause**: Compound has no effect (IC50 = 40 µM), cells grow unchecked

### test_neuron_death_arc.py
- **Expected**: High-dose nocodazole should show morphology-driven death (proper arc)
- **Actual**: Shows overconfluence-driven death (wrong mechanism)
- **Root cause**: No attrition logic in agent class

### debug_morphology_accumulation.py
- **Expected**: Structural morphology stays constant at fixed dose
- **Actual**: Observed morphology drops as cells die from overconfluence
- **Root cause**: Tests run agent class, not standalone simulation

## Solution Options

### Option 1: Port Biology Improvements to Agent Class

Add to `biological_virtual.py`:

1. **Update compound parameters**:
   - Add nocodazole, paclitaxel for iPSC_NGN2, iPSC_Microglia to `simulation_parameters.yaml`
   - Or load from embedded dict like standalone

2. **Add time-dependent death continuation**:
   - Port lines 920-967 from standalone to `treat_with_compound`
   - Apply attrition during `advance_time` or as modifier to viability

3. **Use morphology-to-attrition feedback**:
   - Already computes `transport_dysfunction`
   - Add logic to use it for attrition scaling

### Option 2: Make Tests Use Standalone Simulation

- Modify test scripts to call `standalone_cell_thalamus.simulate_well` directly
- Pros: Tests the actual production code
- Cons: Agent class remains incomplete

### Option 3: Unify Implementations

- Make agent class call standalone simulation internally
- Keep single source of truth for biology logic
- Pros: No duplication
- Cons: Refactoring required

## Recommendation

**Option 1** (port improvements to agent class) is best because:

1. Agent class needs to work correctly for autonomous loops
2. Test scripts should test agent behavior, not just standalone
3. biology improvements are well-defined and can be ported cleanly

## Biology Improvements to Port

From standalone_cell_thalamus.py:

### 1. IC50 Coupling Fix (lines 715-726)
```python
if stress_axis == 'microtubule':
    prolif = PROLIF_INDEX.get(well.cell_line, 1.0)
    mitosis_mult = 1.0 / max(prolif, 0.3)
    functional_dependency = {...}.get(well.cell_line, 0.3)
    ic50_mult = mitosis_mult * (1.0 + functional_dependency * 0.2)
```

### 2. Structural Dysfunction Calculation (lines 785-796)
```python
# CRITICAL: Compute BEFORE noise and viability scaling
transport_dysfunction_score = 0.0
if stress_axis == 'microtubule' and well.cell_line == 'iPSC_NGN2':
    actin_disruption = max(0.0, 1.0 - morph['actin'] / base['actin'])
    mito_disruption = max(0.0, 1.0 - morph['mito'] / base['mito'])
    transport_dysfunction_score = 0.5 * (actin_disruption + mito_disruption)
```

### 3. Time-Dependent Death Continuation (lines 920-967)
```python
# Apply attrition at late timepoints for high stress
if timepoint_h > 12 and viability_effect < 0.5:
    dose_ratio = dose_uM / ic50_viability
    time_factor = (timepoint_h - 12.0) / 36.0

    if stress_axis == 'microtubule' and cell_line == 'iPSC_NGN2':
        # Use morphology-derived dysfunction
        dys = transport_dysfunction_score
        attrition_scale = 1.0 + 2.0 * (dys ** 2.0)
        attrition_rate = 0.25 * attrition_scale
    else:
        attrition_rate = base_rates.get(stress_axis, 0.10)

    if dose_ratio >= 1.0:
        stress_multiplier = dose_ratio / (1.0 + dose_ratio)
        additional_death = attrition_rate * stress_multiplier * time_factor
        viability_effect *= (1.0 - additional_death)
```

## Implementation Status

- ✅ Standalone simulation: ALL FIXES IMPLEMENTED
- ❌ Agent class (biological_virtual.py): STRUCTURAL DYSFUNCTION COMPUTED BUT NOT USED
- ❌ Agent class: NO TIME-DEPENDENT DEATH CONTINUATION
- ❌ Agent class: IC50 PARAMETERS INCOMPLETE

## Next Steps

1. Add nocodazole/paclitaxel parameters for iPSC_NGN2, iPSC_Microglia to simulation_parameters.yaml
2. Port time-dependent death continuation to biological_virtual.py treat_with_compound
3. Add attrition logic that uses transport_dysfunction_score
4. Validate with test scripts that now show correct behavior
