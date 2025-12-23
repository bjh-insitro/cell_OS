# Noise Injection Status

**Date:** 2025-12-22
**Status:** ⚠️ Under-Noised for Wet Lab Realism
**Recommendation:** Increase biological CV from 2% → 10%

---

## Executive Summary

The BiologicalVirtualMachine implements **multi-layer noise injection** to simulate realistic Cell Painting data. Current noise levels are **sufficient for plate design comparison** but **insufficient for absolute calibration**.

**Key finding:** Biological CV is set to 2%, producing vehicle island CV of 2-4%. Real Cell Painting shows 8-15% CV for biological replicates, even under "identical" conditions.

**Critical gap:** Missing **persistent per-well biological heterogeneity** - real wells vary due to cell cycle mix, plating variability, and stochastic protein expression.

---

## Current Implementation

### Noise Architecture (Multi-Layer)

The simulator applies noise in **6 sequential layers**:

```python
# From src/cell_os/hardware/assays/cell_painting.py:263-298
def _apply_measurement_layer(vessel, morph):
    # 1. Viability scaling (biological signal attenuation)
    viability_factor = 0.3 + 0.7 * vessel.viability

    # 2. Washout artifacts (measurement confound)
    washout_multiplier = compute_washout_multiplier(vessel)

    # 3. Biological noise (dose-dependent)
    morph = add_biological_noise(vessel, morph)

    # 4. Plating artifacts (early timepoint variance)
    morph = add_plating_artifacts(vessel, morph)

    # 5. Technical noise (plate/day/operator/well/edge)
    morph = add_technical_noise(vessel, morph)

    # 6. Pipeline drift (batch-dependent extraction)
    morph = pipeline_transform(morph, run_context)
```

---

## Layer 1: Viability Scaling

**Purpose:** Dying cells have weaker signal

**Implementation:**
```python
viability_factor = 0.3 + 0.7 * vessel.viability
# viability=1.0 → factor=1.0 (full signal)
# viability=0.5 → factor=0.65 (35% reduction)
# viability=0.0 → factor=0.3 (70% reduction)
```

**Status:** ✅ Realistic
- Matches observed signal attenuation in dying cells
- Dose-dependent (stressed cells show progressive loss)

---

## Layer 2: Washout Artifacts

**Purpose:** Operation-dependent measurement confounds

**Implementation:**
```python
# Deterministic recovery curve
if time_since_washout < WASHOUT_INTENSITY_RECOVERY_H:
    recovery_fraction = time_since_washout / WASHOUT_INTENSITY_RECOVERY_H
    penalty = WASHOUT_INTENSITY_PENALTY * (1.0 - recovery_fraction)
    washout_multiplier = 1.0 - penalty

# Stochastic contamination (per-well, time-decaying)
if vessel.washout_artifact_until_time:
    artifact_effect = vessel.washout_artifact_magnitude * decay_fraction
    washout_multiplier *= (1.0 - artifact_effect)
```

**Parameters:**
- `WASHOUT_INTENSITY_PENALTY = 0.15` (15% signal drop)
- `WASHOUT_INTENSITY_RECOVERY_H = 6.0` (6h recovery)

**Status:** ✅ Realistic
- Represents real phenomenon (cell stress post-wash)
- Time-dependent recovery matches biology

---

## Layer 3: Biological Noise ⚠️ **Under-Noised**

**Purpose:** Intrinsic cell-to-cell variation

**Implementation:**
```python
# From data/cell_thalamus_params.yaml:
biological_noise:
  cell_line_cv: 0.020  # 2% baseline CV
  stress_cv_multiplier: 2.0  # Stressed cells → 4% CV

# Applied as lognormal multiplier per channel
effective_bio_cv = cell_line_cv * (1.0 + stress_level * (stress_cv_multiplier - 1.0))
morph[channel] *= lognormal_multiplier(rng_assay, effective_bio_cv)
```

**Current behavior:**
- Vehicle wells: 2% CV
- Stressed wells (50% viability): 3% CV
- Stressed wells (0% viability): 4% CV

**Problem:** Real biological CV is 8-15%, not 2%

**Root cause:** Missing sources:
- Cell cycle heterogeneity (G1/S/G2 mix)
- Stochastic protein expression
- Local confluence/microenvironment variation
- Plating variability (clumping, uneven distribution)

**Observed impact:**
- Phase 1 vehicle islands: 2-4% CV (too tight)
- Should be: 8-12% CV

**Status:** ❌ **Under-noised** (2× - 5× too low)

---

## Layer 4: Plating Artifacts

**Purpose:** Early timepoint variance inflation (dissociation stress)

**Implementation:**
```python
# Time-decaying artifact from plating context
time_since_seed = t_measure - vessel.seed_time
artifact_magnitude = post_dissociation_stress * exp(-time_since_seed / tau_recovery)
clump_variance = clumpiness * exp(-time_since_seed / (tau_recovery * 0.5))

artifact_cv = artifact_magnitude + clump_variance
morph[channel] *= lognormal_multiplier(rng_assay, artifact_cv)
```

**Parameters (from RunContext sampling):**
- `post_dissociation_stress`: 0.05-0.15 (5-15% initial CV boost)
- `clumpiness`: 0.05-0.20
- `tau_recovery_h`: 8-24h (plating stress recovery)

**Status:** ✅ Realistic
- Represents real phenomenon (plating trauma)
- Decays appropriately over 24-48h
- Contributes ~5-10% CV at t=0, ~1-2% CV at t=48h

---

## Layer 5: Technical Noise

**Purpose:** Measurement system variation

**Implementation:**
```python
# From data/cell_thalamus_params.yaml:
technical_noise:
  plate_cv: 0.010      # 1% plate-to-plate
  day_cv: 0.015        # 1.5% day-to-day
  operator_cv: 0.008   # 0.8% operator-to-operator
  well_cv: 0.015       # 1.5% well-to-well (measurement)
  edge_effect: 0.12    # 12% signal drop on edges
  well_failure_rate: 0.02  # 2% random well failures

# Deterministic factors (seeded by batch ID)
plate_factor = lognormal_multiplier(rng_batch, plate_cv)
day_factor = lognormal_multiplier(rng_batch, day_cv)
operator_factor = lognormal_multiplier(rng_batch, operator_cv)

# Stochastic factor (per well)
well_factor = lognormal_multiplier(rng_assay, well_cv)

# Edge penalty (deterministic)
edge_factor = (1.0 - edge_effect) if is_edge_well else 1.0

# Combined
total_factor = plate_factor * day_factor * operator_factor * well_factor * edge_factor
```

**Status:** ✅ Realistic for technical noise
- Individual components match real systems
- Total technical CV ≈ 2-3% (reasonable)

**Edge effect:** ✅ Realistic
- 12% signal drop on edges matches evaporation + temperature effects

**Well failures:** ✅ Realistic
- 2% failure rate matches real plates
- Failure modes: bubbles (40%), contamination (25%), focus (20%), pipetting (15%)
- Effects: no_signal, outlier_high, outlier_low, partial_signal, mixed_signal

---

## Layer 6: Pipeline Drift (Batch Effects)

**Purpose:** Feature extraction variability across runs

**Implementation:**
```python
# From src/cell_os/hardware/run_context.py
# RunContext samples batch-level factors:
- illumination_bias: lognormal(σ=0.03)  # 3% illumination drift
- channel_biases: per-channel lognormal(σ=0.02)  # 2% per-channel
- pipeline_version_drift: discrete shifts in feature extraction

# Applied as multiplicative modifiers
morph[channel] *= illumination_bias * channel_biases[channel]
```

**Status:** ✅ Realistic
- Represents instrument drift, lot variability
- Batch-level correlation (same plate affected uniformly)

---

## Well Failure Modes (Adversarial Outliers)

**Purpose:** Discrete failure modes with identifiable fingerprints

**Implementation:**
```python
# From data/cell_thalamus_params.yaml:
well_failure_modes:
  bubble:
    probability: 0.40
    effect: "no_signal"  # All channels → near-zero

  contamination:
    probability: 0.25
    effect: "outlier_high"  # All channels × 5-20

  focus_failure:
    probability: 0.20
    effect: "outlier_low"  # All channels × 0.05-0.3

  pipetting_miss:
    probability: 0.15
    effect: "partial_signal"  # Random channels fail
```

**Trigger rate:** 2% of wells

**Status:** ⚠️ Partially realistic
- ✅ Failure modes exist and are categorized
- ✅ Effects have characteristic fingerprints
- ❌ No channel coupling (bubbles should affect focus-dependent features more)
- ❌ No position coupling (edge wells should fail more often)

---

## Segmentation Failure (Advanced)

**Purpose:** Adversarial measurement layer (not just noise)

**Implementation:**
```python
# From src/cell_os/hardware/injections/segmentation_failure.py
# Computes segmentation quality from:
- confluence (high → merges, low → drops)
- debris_level (high → false positives)
- focus_offset_um (poor focus → undersegmentation)
- stain_scale (poor stain → missed cells)

# Effects:
- cell_count_error (merges/splits/drops)
- texture_attenuation (smoothing from merging)
- size_bias (large cells over-represented)
```

**Status:** ✅ Highly realistic
- Changes sufficient statistics (not just noise)
- Confluence-dependent (matches real segmentation challenges)
- Focus/stain-dependent (matches imaging quality)

---

## Missing Noise Sources (ChatGPT's Critique)

### 1. **Persistent Per-Well Biological Heterogeneity** ❌

**What's missing:**
- Wells don't have persistent "cell state" factors
- All wells at same confluence + treatment are identical (except noise)
- Real wells vary due to: cell cycle distribution, clumping, local stress

**Impact:**
- Understimates true biological variance
- Makes replicates artificially tight

**Fix:**
```python
# Add to VesselState initialization:
self.cell_state_perturbation = {
    'er_shift': rng.normal(0, 0.08),  # ±8% ER baseline
    'mito_shift': rng.normal(0, 0.10),  # ±10% mito baseline
    'stress_susceptibility': rng.lognormal(0, 0.15)  # Stress response variability
}

# Apply in morphology:
morph['er'] *= (1.0 + vessel.cell_state_perturbation['er_shift'])
```

---

### 2. **Correlated Noise (Channel Coupling)** ⚠️

**What's missing:**
- Staining drift affects ER+Mito+RNA together (not independently)
- Focus affects all texture features similarly
- Segmentation errors create channel cross-talk

**Current:** Each channel gets independent noise
**Reality:** Shared factors affect multiple channels

**Impact:**
- Misses realistic noise structure
- Channel correlations too low

**Fix:**
```python
# Shared staining factor
stain_drift = lognormal_multiplier(rng, cv=0.05)
morph['er'] *= stain_drift
morph['mito'] *= stain_drift
morph['rna'] *= stain_drift

# Shared focus factor
focus_quality = 1.0 + focus_offset_um * (-0.02)
morph['nucleus'] *= focus_quality
morph['actin'] *= focus_quality
```

---

### 3. **Structured Outliers** ⚠️

**What's missing:**
- Outliers currently random (RNG gremlins)
- Real outliers have identifiable causes linked to position/batch/provocation

**Current behavior:**
- Seed 123, island CV_NE_A549_VEH: 154.8% (pure RNG)
- Seed 1000, island CV_NW_HEPG2_VEH: 56.4% (pure RNG)

**Reality:**
- Edge wells fail more (evaporation)
- Focus probes create correlated failures
- Stain probes affect ER+Mito together

**Status:** Well failures exist but not position/provocation-linked

---

## Observed Performance

### V4 Phase 1 Results (Current Noise)

| Metric | Observed | Real Cell Painting | Status |
|--------|----------|-------------------|--------|
| Vehicle island CV | 2-4% | 8-15% | ❌ Too low |
| Anchor island CV | 8-15% | 15-25% | ✅ Reasonable |
| Outlier rate | 10% (4/40) | ~10% | ✅ Reasonable |
| Outlier magnitude | 20-150% | 20-50% | ⚠️ Too extreme |
| Edge effect | 12% drop | 10-15% drop | ✅ Realistic |

### Analysis

**What works:**
- ✅ Technical noise levels (plate, day, operator, well)
- ✅ Edge effects (evaporation simulation)
- ✅ Outlier frequency (10% failure rate)
- ✅ Washout artifacts (operation-dependent)
- ✅ Segmentation failures (confluence-dependent)

**What's broken:**
- ❌ Biological CV too low (2% vs 8-15% reality)
- ❌ No persistent per-well heterogeneity
- ⚠️ Outliers too extreme (154% vs 30-50% reality)
- ⚠️ Channel noise uncorrelated (should couple)

---

## Impact on Plate Design Validation

### What Current Noise Was Good For

**✅ Relative comparisons:**
- V3 vs V4 plate design comparison
- V5 hybrid validation (+71% spatial variance detection)
- Geometry variant testing

**✅ Mechanism testing:**
- Stress axes working correctly
- Death accounting accurate
- Spatial effects detectable

**Conclusion:** Noise was **sufficient for plate design work** (relative comparisons)

---

### What Current Noise Is Insufficient For

**❌ Absolute calibration:**
- V4 baseline should be ~10% CV (observed: 6%)
- Cannot validate "earned trust" thresholds
- Under-estimates real assay difficulty

**❌ Wet lab prediction:**
- Sim suggests 2-4% is achievable (too optimistic)
- Real labs will see 8-15% (surprise)
- QC thresholds will be wrong

**Conclusion:** Noise **insufficient for absolute baseline setting**

---

## Recommended Fixes (Prioritized)

### Fix 1: Increase Biological CV (Immediate) ⭐⭐⭐

**Change:**
```yaml
# data/cell_thalamus_params.yaml
biological_noise:
  cell_line_cv: 0.10  # Was 0.020 (2%) → Now 10%
```

**Expected impact:**
- Vehicle island CV: 2-4% → 8-12%
- Anchor island CV: 8-15% → 15-20%
- Matches real Cell Painting performance

**Effort:** Single line change
**Risk:** Low (just scaling existing mechanism)
**Validation:** Re-run Phase 1, check if CV increases

---

### Fix 2: Add Per-Well Biological Heterogeneity (High Value) ⭐⭐

**Implementation:**
```python
# Add to VesselState.__init__()
def _sample_cell_state_perturbation(self, rng):
    """Sample persistent well-level biological factors."""
    return {
        'er_baseline_shift': rng.normal(0, 0.08),
        'mito_baseline_shift': rng.normal(0, 0.10),
        'stress_susceptibility': rng.lognormal(0, 0.15),
        'confluence_sensitivity': rng.uniform(0.9, 1.1)
    }

# Apply in CellPaintingAssay.measure()
morph['er'] *= (1.0 + vessel.cell_state_perturbation['er_baseline_shift'])
morph['mito'] *= (1.0 + vessel.cell_state_perturbation['mito_baseline_shift'])
```

**Expected impact:**
- Wells at same treatment show persistent differences
- Replicates less artificially tight
- Captures cell cycle / plating heterogeneity

**Effort:** ~50 lines of code
**Risk:** Medium (new state, needs testing)

---

### Fix 3: Add Noise Coupling (Lower Priority) ⭐

**Implementation:**
```python
# In _add_technical_noise()
# Shared staining factor (affects ER, Mito, RNA together)
stain_drift_factor = lognormal_multiplier(rng, cv=0.05)
morph['er'] *= stain_drift_factor
morph['mito'] *= stain_drift_factor
morph['rna'] *= stain_drift_factor

# Shared focus factor (affects texture features)
focus_quality = 1.0 + kwargs.get('focus_offset_um', 0) * (-0.02)
morph['nucleus'] *= focus_quality
morph['actin'] *= focus_quality
```

**Expected impact:**
- Channel correlations more realistic
- Provocation effects have characteristic patterns
- Outliers have "fingerprints"

**Effort:** ~30 lines of code
**Risk:** Low

---

### Fix 4: Reduce Outlier Extremity (Optional)

**Current:** Outliers can reach 150%+ CV (rare, RNG-driven)
**Reality:** Outliers typically 30-50% (identifiable failures)

**Change:**
```yaml
well_failure_modes:
  outlier_high:
    effect_multiplier: [3.0, 8.0]  # Was [5.0, 20.0]
  outlier_low:
    effect_multiplier: [0.10, 0.40]  # Was [0.05, 0.30]
```

**Effort:** Parameter tuning
**Risk:** Low

---

## Decision: Wait or Fix Now?

### Option A: Fix Now (Before Wet Lab)

**Pros:**
- More realistic baselines for "earned trust" thresholds
- Better wet lab prediction
- Catches issues early

**Cons:**
- Invalidates Phase 1 baseline (6% → 10%)
- Need to re-run validations
- Uncertainty about real wet lab CV

**Recommendation if:** You want to set QC thresholds now

---

### Option B: Wait for Wet Lab Data

**Pros:**
- Validate against real data first
- Know exact CV target
- One-time parameter tuning

**Cons:**
- Current thresholds may be wrong
- Might surprise users ("why is CV so high?")

**Recommendation if:** Wet lab data coming soon (< 2 months)

---

## Testing Protocol (If Fixing)

### Step 1: Increase Biological CV

```bash
# Edit data/cell_thalamus_params.yaml
cell_line_cv: 0.10

# Re-run Phase 1
python3 scripts/run_v4_phase1.py --seeds 600 700 800

# Check new baseline
python3 scripts/analyze_v4_phase1.py
```

**Expected:** Vehicle islands 8-12% CV (was 2-4%)

---

### Step 2: Validate Against Original

```bash
# Compare to current baseline
python3 << EOF
import json
import numpy as np
from pathlib import Path

# Load old Phase 1 (seeds 100,200,300) vs new (600,700,800)
# Compare distributions
# Expected: ~2.5× increase in mean CV
EOF
```

---

### Step 3: Update Documentation

- Update `V4_PHASE1_VALIDATION_RESULTS.md` with new baseline
- Update `PLATE_DESIGN_SYSTEM_STATUS.md` with corrected CV
- Note: "Increased biological CV to match real Cell Painting (2% → 10%)"

---

## Code Locations

### Noise Implementation

| Component | File | Line |
|-----------|------|------|
| Measurement layer | `src/cell_os/hardware/assays/cell_painting.py` | 263-298 |
| Biological noise | `src/cell_os/hardware/assays/cell_painting.py` | 321-333 |
| Technical noise | `src/cell_os/hardware/assays/cell_painting.py` | 354-392 |
| Well failures | `src/cell_os/hardware/assays/cell_painting.py` | 415-477 |
| Segmentation failures | `src/cell_os/hardware/injections/segmentation_failure.py` | - |
| Plating artifacts | `src/cell_os/hardware/run_context.py` | - |
| Pipeline drift | `src/cell_os/hardware/run_context.py` | - |

### Parameter Files

| Parameters | File | Section |
|------------|------|---------|
| Biological noise | `data/cell_thalamus_params.yaml` | `biological_noise` |
| Technical noise | `data/cell_thalamus_params.yaml` | `technical_noise` |
| Well failure modes | `data/cell_thalamus_params.yaml` | `well_failure_modes` |
| Compound effects | `data/cell_thalamus_params.yaml` | `compounds`, `stress_axes` |

---

## References

### Internal Documentation
- `docs/V4_PHASE1_VALIDATION_RESULTS.md` - Observed CV: 6% (2-4% vehicle)
- `docs/PLATE_DESIGN_SYSTEM_STATUS.md` - Production baselines
- `docs/guides/simulation_and_synthetic_data.md` - Noise architecture

### Key Findings
- ChatGPT analysis: "Too clean most of the time, too pathological sometimes"
- Phase 1 validation: 6.3% mean CV (too low)
- Typical validation (no outliers): 5.5% CV (should be 10-12%)

---

## Conclusion

**Current status:** ⚠️ Under-noised for absolute calibration

**Current noise is:**
- ✅ Sufficient for plate design comparison (relative)
- ✅ Sufficient for mechanism validation
- ❌ Insufficient for wet lab prediction
- ❌ Insufficient for "earned trust" thresholds

**Critical missing component:** Biological CV at 2% (should be 10%)

**Recommended action:**
1. **Immediate:** Increase `cell_line_cv` from 0.02 → 0.10
2. **Soon:** Add per-well biological heterogeneity
3. **Optional:** Add noise coupling, tune outlier extremity

**Decision point:** Fix now or wait for wet lab data?

---

**Document Status:** Current Assessment
**Last Updated:** 2025-12-22
**Authors:** Claude Code + BJH + ChatGPT Analysis
**Review Status:** Awaiting Decision (Fix Now vs Wait for Wet Lab)
