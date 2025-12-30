# Within-Run Measurement Drift Implementation

**Status**: Phase 1–2 Complete
**Date**: 2025-12-25
**Branch**: `feature/assumptions-hardening-non-aspiration`

---

## What Was Implemented

### Core Pathology: Time-Dependent Instrument Drift

Introduced **time as an adversary** in measurement without contaminating biology. Agents can no longer "calibrate once at t=0 and trust forever"—uncertainty grows with time, forcing strategic recalibration decisions under budget pressure.

### Design Principles

1. **Deterministic given seed**: Same seed → identical drift trajectory
2. **Observer-independent**: Drift affects measurements only, never biology
3. **Modality-specific**: Imaging and plate reader drift independently
4. **Structured, learnable**: Not random noise—smooth, bounded, with interpretable components
5. **Forced modal choice**: Agents must decide which instrument to trust/recalibrate

---

## Implementation Details

### DriftModel (`src/cell_os/hardware/drift_model.py`)

Three components combine multiplicatively:

1. **Aging**: Monotone saturating decay (lamp/detector degradation)
   - Imaging: k=0.0012/h, floor=0.92
   - Reader: k=0.0020/h, floor=0.88

2. **Thermal cycles**: Periodic wobble (different periods create cross-modal disagreement)
   - Imaging: ±0.6% amplitude, 6h period
   - Reader: ±0.4% amplitude, 4h period

3. **Smooth wander**: Cubic spline interpolation of random knots (main component)
   - Shared component (alpha=0.35): creates "cursed day" correlation
   - Modality-specific component (alpha=0.94): allows independent drift
   - Result: moderate positive correlation on average, but seed-dependent

**Bounds**: Soft-clamped to [0.90, 1.10] via tanh in log-space

**Noise inflation**: Separate upward trend (8% increase over 72h) with smooth wander

### RunContext Integration

- `get_measurement_modifiers(t_hours, modality)` returns time-dependent `gain` and `noise_inflation`
- `gain = base_batch_effect × drift_gain(t, modality)`
- Units assertion catches seconds vs hours confusion
- Feature flag: `drift_enabled=True` (can disable for legacy tests)

### Assay Integration

**Cell Painting** (`src/cell_os/hardware/assays/cell_painting.py:706,755`):
- Calls `get_measurement_modifiers(t_measure, 'imaging')`
- Applies `gain` at canonical location (line 755)
- All channels affected uniformly (shared gain)

**Scalar Assays** (`src/cell_os/hardware/assays/viability.py:207,212`):
- Calls `get_measurement_modifiers(t_measure, 'reader')`
- Applies `gain` at canonical location (line 212)
- All signals (LDH, ATP, UPR, trafficking) affected uniformly

---

## Validation Results (Seed 42)

### Component Correlations

```
shared_wander:  1.0000  ✓ Wiring correct (identical for both modalities)
total_wander:  -0.1112    Modality-specific dominates for this seed
aging:          1.0000  ✓ Both decay monotonically
cycle:         -0.0005  ✓ Independent (different periods/phases)
drift_gain:     0.1803  ✓ Positive (aging/multiplicative rescue wander)
```

### Drift Magnitude

```
Imaging gains over 72h: [1.014, 1.084] (range: 0.070)
Reader gains over 72h:  [1.005, 1.068] (range: 0.063)

Both ranges > 5%: drift is real and meaningful
Both bounded in [0.90, 1.10]: soft clamp working
```

### Invariant Tests (All Passing)

- ✓ Shared wander identical (corr=1.0000)
- ✓ Drift trajectory deterministic (same seed → exact match)
- ✓ Call-count independence (querying doesn't change drift)
- ✓ Bounds respected over 72h
- ✓ Drift magnitude > 1% (not flattened by clamp)

---

## Statistical Structure

### Correlation Behavior

**Expected**: Moderate positive correlation between imaging and reader drift (due to shared "cursed day" component).

**Observed (seed 42)**: Final gain correlation = 0.1803 (positive).

**Variance composition**:
- Shared wander contributes ~12% of total wander variance (alpha²=0.123)
- Modality-specific wander contributes ~88% (1-alpha²=0.877)
- For seed 42, modality-specific components happen to be weakly anti-correlated, but aging (corr=1.0) and multiplicative combination rescue overall correlation to positive

**Interpretation**: Some runs will have strong positive correlation (cursed day dominates), some will have weak or negative correlation due to dominance of independent modality-specific drift components. This is **emergent from variance composition**, not a designed-in antagonism. Agents cannot assume perfect correlation—must handle both.

### Data Characteristics

Datasets from this simulator will show:
- **Heteroskedastic**: Noise inflation increases with time (~8% over 72h)
- **Non-stationary**: Drift creates time-dependent mean shift
- **Smooth**: Cubic spline interpolation (or linear fallback if scipy unavailable)
- **Bounded**: Soft clamp prevents pathological runs
- **Modality-specific**: Cross-modal disagreement forces strategic choices

---

## What This Buys You

### Agent Learning Pressure

1. **Cannot front-load calibration**: t=0 measurements become stale by t=72h
2. **Uncertainty grows with time**: 5-7% drift over 72h is detectable
3. **Forced modal choice**: Budget limits → must prioritize imaging or reader recalibration
4. **Explore-exploit tradeoff**: Balance calibration cost vs uncertainty reduction

### Realistic Suffering

- Some runs have correlated drift (shared "cursed day")
- Some runs have uncorrelated or anti-correlated drift (modality-specific dominance)
- Agents cannot exploit a simple "both always drift together" heuristic
- Must learn to handle seed-dependent correlation structure

---

## Files Modified

```
✓ src/cell_os/hardware/drift_model.py              (NEW, 285 lines)
✓ src/cell_os/hardware/rng_guard.py                (snapshot/restore added)
✓ src/cell_os/hardware/run_context.py              (drift integration)
✓ src/cell_os/hardware/assays/cell_painting.py    (time-dependent modifiers)
✓ src/cell_os/hardware/assays/viability.py        (time-dependent modifiers)
✓ src/cell_os/hardware/biological_virtual.py      (RNG pattern update)
```

---

## Not Yet Implemented (Phase 3+)

**Not prerequisites for agent training**, but would sharpen forensics:

- `return_diagnostic=True` mode in assays (exposes `{raw, gain_applied, noise_inflation}`)
- MeasurementBudget with gate enforcement (choke point for observation creation)
- Formal test: gain applied exactly once (can audit with grep for now)
- Biology invariance test (blocked by pre-existing contract violations in Cell Painting)

**Why it's OK to proceed without these**:
- Agents will already experience drift punishment
- Determinism guarantees reproducible debugging later
- Diagnostics mode is forensics enhancement, not correctness requirement

---

## Key Design Decision: Decompose, Don't Tune

When seed 42 showed **negative total_wander correlation** (-0.11), the instinct was "increase alpha."

Instead, decomposed components to prove:
1. Shared wander is correctly wired (corr=1.0)
2. Modality-specific wander happens to dominate for this seed
3. Aging and multiplicative combination rescue final gain to positive (0.18)

**Lesson**: Negative correlation is not a bug—it's emergent from variance composition. Tuning alpha would have hidden the true structure: some runs are cursed in lockstep, some are cursed independently. This variance is **realistic** and **valuable for learning**.

---

## Testing Commands

```bash
# Test drift model in isolation
python test_drift_basic.py

# Test RunContext integration
python test_drift_integration.py

# Test component decomposition
python test_drift_decomposition.py

# Test invariants
python test_drift_invariants.py
```

---

## Next Steps

1. **Agent training**: Let agents touch the system and observe what they learn
2. **Forensics enhancement** (when needed): Add `return_diagnostic=True` mode
3. **Budget enforcement** (when ready): Implement MeasurementBudget with gate

**Do not**:
- Tune alpha to force positive correlation
- Add special-case "cursed day" logic
- Flatten drift to make it more "learnable"

The realism is in the structured variance. Keep it.

---

## Contact / Questions

This pathology forces agents to learn **temporal calibration strategies** under budget pressure. If agents exploit loopholes or learn surprising behaviors, the diagnostics mode will help debug "was this biology, drift, or budget?"

Phase 1–2 complete. Ready for agent training.
