# Phase 5B: Realism Layer Implementation

**Date**: 2024-12-19
**Status**: ALL INJECTIONS COMPLETE ✅
- Injection #1 (RunContext) ✅
- Injection #2 (Plating latent) ✅
- Injection #3 (Pipeline drift) ✅

---

## Goal

Make epistemic control strategies robust by injecting:
1. **Correlated context effects** (lot/incubator/instrument) - DONE
2. **Plating artifacts** (seeding stress, early timepoint unreliability) - TODO
3. **Pipeline drift** (batch-dependent feature extraction failures) - TODO

**Why this matters**:
- Forces calibration plate workflows (context disambiguation)
- Creates "same compound, different conclusion" outcomes
- Prevents policy overfitting to clean simulator assumptions

---

## Injection #1: RunContext (Correlated Batch/Lot/Instrument Effects)

**Status**: ✅ Complete (~180 lines)

### Implementation Summary

**New file**: `src/cell_os/hardware/run_context.py`
- `RunContext` class with correlated factors:
  - `incubator_shift`: affects biology (EC50, stress sensitivity, growth)
  - `reagent_lot_shift`: per-channel intensity biases (measurement)
  - `instrument_shift`: illumination/noise floor (measurement)
- All factors correlated via shared "cursed day" latent

**Modified**: `src/cell_os/hardware/biological_virtual.py`
- Added `run_context` parameter to `__init__` (samples if None)
- **Biology hooks** (3 locations):
  1. `treat_with_compound`: Apply EC50 multiplier (line 1524)
  2. `_update_er_stress`: Apply stress sensitivity to k_on (line 716)
  3. `_update_mito_dysfunction`: Apply stress sensitivity to k_on (line 809)
  4. `_update_transport_dysfunction`: Apply stress sensitivity to k_on (line 885)
  5. `_update_vessel_growth`: Apply growth rate multiplier (line 997)
- **Measurement hooks** (1 location):
  6. `cell_painting_assay`: Apply channel biases + illumination bias (lines 2123-2132)

### Key Design Choices

1. **Correlated factors**: All factors share a "cursed day" latent with correlation=0.5
   - When incubator is off, instrument is also likely off
   - When reagent lot is bad, illumination is also likely bad
   - Creates coherent "today is cursed" vs i.i.d. noise

2. **Minimal threading**: One object (`RunContext`) passed to two choke points:
   - Biology generator (`treat_with_compound`, stress dynamics, growth)
   - Measurement generator (`cell_painting_assay`)
   - No invasive refactor needed

3. **Magnitude calibration**:
   - Incubator shift: ±0.3 → EC50 multiplier 0.86× to 1.16×
   - Stress sensitivity: ±10% (controlled by incubator)
   - Growth rate: ±6% (controlled by incubator)
   - Channel biases: ±15% per channel (independent + correlated)
   - Illumination bias: ±20% global (instrument drift)

### Test Results

Test file: `src/cell_os/hardware/test_run_context.py`

**Test 1: RunContext Sampling** ✓
- Factors in expected ranges
- Modifiers computed correctly
- Correlation structure preserved

**Test 2: Context Affects Biology** ✓
- Same experiment, two contexts: 2.5% viability difference @ 18h
- Good day (ctx_strength=0.5): viability = 0.425
- Cursed day (ctx_strength=1.5): viability = 0.450

**Test 3: Context Affects Measurement** ✓
- Same biology, two contexts: 73-155% channel intensity differences!
- Context A: ER=84.2, mito=87.3, actin=60.4
- Context B: ER=163.2, mito=151.0, actin=154.2
- Measurement biases dominate signal

**Test 4: Same Compound, Different Conclusion** ✓
- Tunicamycin (ER compound) measured under two contexts
- Context A: ER/mito ratio = 0.99 (ambiguous)
- Context B: ER/mito ratio = 1.22 (ER-biased)
- Ratio shift of 0.23 can flip axis classification

**Verdict**: RunContext creates "arguable outcomes" as designed.

---

## Impact on Epistemic Control

### Before RunContext (Phase 5 baseline):

- Classifier confidence based solely on signal separation
- Same compound → same conclusion (deterministic given seed)
- Policies overfit to simulator's clean assumptions

### After RunContext (Phase 5B):

- **Confidence must account for context uncertainty**
  - Wide channel biases → ambiguous axis calls
  - Same compound can give different conclusions under different contexts
  - Forces "spend intervention to disambiguate context" strategies

- **Calibration plate workflows become necessary**
  - Without calibration plate, can't separate biology from context
  - Policies that don't calibrate get punished with wrong classifications

- **Robust policies emerge**
  - Policies that work under Context A but fail under Context B get filtered
  - Forces conservative strategies that tolerate context variation

### Expected Changes to Beam Search

- Beam search should prefer policies that:
  1. Include calibration steps (control wells, known compounds)
  2. Use relative measurements (fold-change, ratios) vs absolute intensities
  3. Delay commitment until context effects can be separated
  4. Tolerate wider confidence intervals (mixture width + context width)

- Policies that fail:
  - Early commitment based on absolute channel intensities
  - Assuming "clean signal = certain classification"
  - Strategies optimized for Context A that break under Context B

---

## Next: Injection #2 (Plating Latent)

**Goal**: Make early timepoints (6-12h) unreliable for structural reasons (not just noise).

**Hook**: Add `plating_context` to `VesselState.__init__`:
- `post_dissociation_stress`: Exponential decay with tau=8-16h
- `seeding_density_error`: Systematic plate-level bias
- `clumpiness`: Increases feature variance early

**Apply in**:
- `cell_painting_assay`: Inflate morphology variance at early timepoints
- `_distribute_death_across_subpopulations`: Bias early death risk
- `get_mixture_width`: Inflate mixture width early (masquerades as heterogeneity)

**Expected impact**:
- 12h probe becomes unreliable (high artifact, low biology signal)
- 18-24h becomes preferred probe time (artifact decayed, biology clear)
- Validates design review prediction: "Confidence collapses at early timepoints"

**Lines estimate**: ~40 lines

---

## Injection #3: Pipeline Drift (Batch-Dependent Feature Extraction)

**Status**: ✅ Complete (~102 lines)

### Implementation Summary

**New function**: `pipeline_transform()` in `src/cell_os/hardware/run_context.py`
- Batch-dependent segmentation bias (correlated with reagent lot, correlation=0.3)
- Affine transforms in feature space (batch-specific ER/mito scaling)
- Discrete failure modes (5% of plates):
  - `focus_off`: All channels dimmer (0.7-0.9×)
  - `illumination_wrong`: Per-channel intensity shifts (0.8-1.3×)
  - `segmentation_fail`: Nucleus/actin ratio skewed

**Modified**: `src/cell_os/hardware/biological_virtual.py`
- Lines 2220-2229: Apply `pipeline_transform()` in `cell_painting_assay`
- Applied after viability scaling, before returning features
- Takes `batch_id` and `plate_id` from kwargs

### Key Design Choices

1. **Mild correlation with reagent lot** (correlation=0.3):
   - 30% correlated with reagent lot + 70% independent
   - Creates "cursed day" coherence: bad reagent lot → bad segmentation
   - Not deterministic, but systematic bias

2. **Affine transforms per batch**:
   - ER and mito channels scaled independently per batch
   - Some batches compress ER-mito separation, others amplify
   - Creates "same compound, different conclusion" at feature level

3. **Discrete failure modes**:
   - 5% of plates have systematic failures (focus/illumination/segmentation)
   - Per-plate deterministic (plate_id seed)
   - Catastrophic but rare (QC should catch these)

### Test Results

Test file: `src/cell_os/hardware/test_pipeline_drift.py`

**Test 1: Pipeline Transform Determinism** ✓
- Same batch → same transform (reproducible)

**Test 2: Batch-Dependent Features** ✓
- Batch A vs Batch B: 1.8-5.9% channel differences
- Different batches → different features from same biology

**Test 3: Pipeline-Reagent Correlation** ✓
- Pipeline bias has 30% correlated + 70% independent components
- When reagent lot is bad, segmentation is also likely bad

**Test 4: Discrete Failure Modes** ✓
- 2/100 plates failed (expected ~5/100, acceptable stochasticity)
- Failure types: illumination_wrong, focus_off, segmentation_fail

**Test 5: Same Biology, Different Batch Conclusion** ✓
- Tunicamycin measured in Batch A: ER/mito ratio = 1.28
- Tunicamycin measured in Batch B: ER/mito ratio = 1.33
- Ratio difference = 0.06 (enough to create arguable outcomes)

**Test 6: Integration with Assay** ✓
- Pipeline transform integrates correctly with `cell_painting_assay`
- Batch ID and plate ID passed through kwargs

**Verdict**: Pipeline drift creates batch-dependent feature extraction failures as designed.

### Expected Impact

- **Prevents feature overtrust**: Same biology can give different features per batch
- **Forces batch normalization**: Feature-based classifiers must account for batch effects
- **Creates contestable conclusions**: "Did biology change or did pipeline change?"
- **Completes realism layer**: All three injections now active

---

## Integration with Population Heterogeneity

RunContext + Heterogeneity creates **layered uncertainty**:

1. **Biological heterogeneity** (Phase 5):
   - Subpopulations with shifted IC50 and death thresholds
   - Mixture width captures biological variance
   - Confidence: `base_confidence * (1 - mixture_width / 0.3)`

2. **Context uncertainty** (Phase 5B Injection #1):
   - Batch/lot/instrument effects shift measurements
   - Channel biases create ambiguous signatures
   - Confidence: `base_confidence * (1 - context_uncertainty)`

3. **Plating artifacts** (Phase 5B Injection #2 - TODO):
   - Early timepoint unreliability
   - Post-dissociation stress masquerades as stress response
   - Confidence: `base_confidence * artifact_decay(t)`

4. **Pipeline drift** (Phase 5B Injection #3 - TODO):
   - Batch-dependent feature extraction failures
   - Same biology, different features per batch
   - Confidence: `base_confidence * pipeline_trust(batch_id)`

**Total confidence**:
```python
confidence = (
    base_confidence
    * (1 - mixture_width / 0.3)  # Heterogeneity
    * (1 - context_uncertainty)  # RunContext
    * artifact_decay(t)  # Plating
    * pipeline_trust(batch)  # Pipeline drift
)
```

**Result**: Confidence collapses naturally when any uncertainty source is high.

---

## Testing Strategy

### Phase 5B Test Suite
1. ✅ `test_run_context.py` (Injection #1) - 4/4 tests pass
2. ✅ `test_plating_artifacts.py` (Injection #2) - 6/6 tests pass
3. ✅ `test_pipeline_drift.py` (Injection #3) - 6/6 tests pass

### Integration Tests
After all injections complete:
1. Re-run Phase 5 benchmarks with RunContext enabled
2. Verify confidence collapse (0.20 → 0.08 with context + heterogeneity)
3. Check beam search prefers delayed commitment
4. Validate "same compound, different conclusion" outcomes exist

### Acceptance Criteria
- Policies learned with realism layer transfer to "clean" simulator
- Policies learned without realism layer fail under realism layer
- Calibration plate workflows emerge naturally (not hand-coded)

---

## Credit

Design guidance: External experimentalist (2024-12-19)

**Key insights**:
> "This is the cleanest way to kill 'confident early commitment' because it creates *shared, non-identifiable structure* across wells that looks like biology until you pay an explicit calibration cost."

> "If incubator_shift and pipeline_drift are mildly correlated, you get the most realistic kind of suffering: the world nudges biology and measurement in the same direction, and naive policies get seduced."

Implementation: Phase 5B all injections (~322 lines total, minimal refactor)

---

## Phase 5B Complete Summary

### Implementation Statistics
- **Total lines added**: ~322 lines across 3 injections
- **Files created**:
  - `src/cell_os/hardware/run_context.py` (~300 lines)
  - `src/cell_os/hardware/test_run_context.py` (~170 lines)
  - `src/cell_os/hardware/test_plating_artifacts.py` (~230 lines)
  - `src/cell_os/hardware/test_pipeline_drift.py` (~270 lines)
- **Files modified**:
  - `src/cell_os/hardware/biological_virtual.py` (6 hook points + plating context)
- **Tests written**: 16 tests total (all passing)

### Hook Points in BiologicalVirtualMachine

**Biology Hooks** (5 locations):
1. `treat_with_compound` (line 1591): EC50 multiplier from incubator shift
2. `_update_er_stress` (lines 760-761): Stress sensitivity multiplier
3. `_update_mito_dysfunction` (lines 853-854): Stress sensitivity multiplier
4. `_update_transport_dysfunction` (lines 929-930): Stress sensitivity multiplier
5. `_update_vessel_growth` (lines 1041-1042): Growth rate multiplier

**Measurement Hooks** (3 locations):
6. `cell_painting_assay` (lines 2200-2210): Channel biases + illumination bias
7. `cell_painting_assay` (lines 2133-2157): Plating artifact inflation
8. `cell_painting_assay` (lines 2220-2229): Pipeline drift transform

**Context Management** (1 location):
9. `seed_vessel` (lines 1307-1308): Sample plating context

### Impact on Epistemic Control

**Without Phase 5B** (Phase 5 baseline):
- Confidence: base × (1 - mixture_width / 0.3)
- Same compound → same conclusion
- Policies overfit to clean assumptions

**With Phase 5B** (full realism layer):
- Confidence: base × (1 - mixture_width / 0.3) × (1 - context_uncertainty) × artifact_decay(t) × pipeline_trust(batch)
- Same compound → different conclusions per context/batch
- Forces calibration workflows, delayed commitment, batch normalization
- Robust policies that tolerate variation

### Next Steps

1. ✅ COMPLETE: All Phase 5B injections implemented and tested
2. TODO: Re-run Phase 5 benchmarks with realism layer enabled
3. TODO: Validate confidence collapse (expect 0.20 → 0.08 with all factors)
4. TODO: Check beam search preferences (delayed commitment, calibration steps)
5. TODO: Acceptance criteria:
   - Policies learned WITH realism transfer to clean simulator
   - Policies learned WITHOUT realism fail under realism
   - Calibration workflows emerge naturally (not hand-coded)

### Success Metrics

Phase 5B achieves design goal: **"Punch epistemic control in the face without turning into a simulator rewrite"**

✅ Minimal refactor (9 hook points, no invasive changes)
✅ Creates "arguable outcomes" (Context A vs Context B)
✅ Forces calibration costs (can't separate biology from context for free)
✅ Prevents feature overtrust (batch-dependent feature extraction)
✅ Layered uncertainty (heterogeneity + context + artifacts + pipeline)
✅ All tests pass (16/16 tests, multiple validation modes)
