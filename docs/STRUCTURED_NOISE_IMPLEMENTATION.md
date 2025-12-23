# Structured Noise Implementation

**Date:** 2025-12-22
**Status:** ✅ Implemented, Ready for Validation
**Goal:** Add realistic biological heterogeneity with proper structure (not "amplitude mush")

---

## Executive Summary

Refactored noise injection from **"independent per-channel RNG"** to **"persistent per-well latent biology with coupled technical factors"**.

This crosses the line from:
> "a simulator that can compare plate designs"

to:
> **"a simulator that can teach an agent what an instrument feels like."**

---

## Problem Statement

### Before (Wrong)

```python
# Old _add_biological_noise() - applies AFTER biology
for channel in morph:
    morph[channel] *= lognormal_multiplier(rng_assay, cell_line_cv)  # Independent per channel!
```

**Problems:**
1. ❌ Vehicle islands at 2-4% CV (too clean)
2. ❌ Independent noise per channel → no structure → "amplitude mush"
3. ❌ Wells have no persistent identity (RNG churn across measurements)
4. ❌ Outliers are pure RNG gremlins (154% CV from random seed)
5. ❌ No channel coupling (stain/focus factors don't exist)

**Result:** Calibration was "easy mode" - agent could average noise away in one plate.

---

## Solution: Three-Layer Structured Noise

### Layer 1: Persistent Per-Well Latent Biology (NEW) ⭐

**Purpose:** Wells have stable "cell state" independent of treatment

**Implementation:**
```python
# Added to VesselState (biological_virtual.py lines 247-250)
self.well_biology = None  # Sampled once, persists forever
self.rng_well = None      # Deterministic per-well RNG

# Initialized in seed_vessel() (line 1395-1398)
well_seed = stable_u32(f"well_biology_{run_context.seed}_{vessel_id}")
state.rng_well = np.random.default_rng(well_seed)

# Sampled in _ensure_well_biology() (cell_painting.py lines 171-198)
vessel.well_biology = {
    "er_baseline_shift": rng.normal(0.0, 0.08),       # ~8% sd
    "mito_baseline_shift": rng.normal(0.0, 0.10),     # ~10% sd
    "rna_baseline_shift": rng.normal(0.0, 0.06),      # ~6% sd
    "nucleus_baseline_shift": rng.normal(0.0, 0.04),  # ~4% sd
    "actin_baseline_shift": rng.normal(0.0, 0.05),    # ~5% sd
    "stress_susceptibility": rng.lognormal(0.0, 0.15),  # treatment gain variation
}

# Applied EARLY in measure() - before compound effects! (lines 98-101)
self._ensure_well_biology(vessel)
morph = self._apply_well_biology_baseline(vessel, morph)
```

**Why this works:**
- Sampled **once** at seeding → persistent across assays
- Deterministic per `(run_seed, vessel_id)` → stable across days
- Applied to **baseline** not final morphology → affects vehicle wells
- Dominant driver of vehicle island CV (8-10%)

**Expected impact:**
- Vehicle wells show **persistent differences** (not RNG churn)
- Same well stays "weird" across measurements
- CV dominated by biology, not measurement noise

---

### Layer 2: Coupled Technical Noise (ENHANCED)

**Purpose:** Shared factors affect multiple channels together

**Implementation:**
```python
# Plate-level stain factor (lines 413-415, 464)
stain_factor = self._get_plate_stain_factor(plate_id, batch_id, stain_cv=0.05)

# Tile-level focus factor (4×4 blocks) (lines 417-429, 465)
focus_factor = self._get_tile_focus_factor(plate_id, batch_id, well_position, focus_cv=0.04)

# Weighted exponential coupling (lines 474-503)
# Stain weights: ER=1.0, Mito=1.0, RNA=0.9, Nucleus=0.5, Actin=0.2
if channel in ("er", "mito"):
    coupled = stain_factor
elif channel == "rna":
    coupled = stain_factor ** 0.9
elif channel == "nucleus":
    coupled = stain_factor ** 0.5
elif channel == "actin":
    coupled = stain_factor ** 0.2

# Focus weights: Nucleus=1.0, Actin=1.0, others=0.2
if channel in ("nucleus", "actin"):
    coupled *= focus_factor
else:
    coupled *= focus_factor ** 0.2

morph[channel] *= coupled

# Focus-induced variance inflation (fingerprint!)
if channel in ("nucleus", "actin") and focus_badness > 0:
    extra_cv = min(0.25, 0.05 + 0.4 * focus_badness)
    morph[channel] *= lognormal_multiplier(rng_assay, extra_cv)
```

**Why weighted exponents:**
- Nucleus is "bridge channel" (affected by both stain and focus)
- Partial membership via `factor ** weight` (not hard grouping)
- Focus inflates variance for structure channels (not just scales mean)

**Expected impact:**
- ER-Mito correlation: 0.3-0.5 (stain coupling)
- Nucleus-Actin correlation: 0.2-0.4 (focus coupling)
- Outliers have **identifiable fingerprints** (stain-like vs focus-like)

---

### Layer 3: Stress Susceptibility (FIXED)

**Purpose:** Wells respond differently to same treatment

**Implementation:**
```python
# In _add_biological_noise() (lines 364-392)
# Stress susceptibility affects GAIN, not baseline
stress_level = max(0.0, min(1.0, 1.0 - vessel.viability))
sus = vessel.well_biology["stress_susceptibility"]

if stress_level > 0:
    gain = 1.0 + (sus - 1.0) * stress_level
    for ch in morph:
        morph[ch] *= gain  # Amplifies stress-driven deviation

# Residual noise kept modest (4% not 10%)
effective_cv = base_residual_cv * (1.0 + stress_level * (stress_multiplier - 1.0))
```

**Why this works:**
- Susceptibility modulates **treatment response** (not vehicle baseline)
- Vehicle wells unaffected → CV stays low
- Treatment wells show heterogeneous responses → CV increases
- Realistic: some cells more sensitive to stress

---

## Parameter Changes

### `data/cell_thalamus_params.yaml`

```yaml
biological_noise:
  cell_line_cv: 0.04  # Was 0.02 → Now 4% (modest residual)
  # Per-well biology does heavy lifting (8-10% baseline shifts)

technical_noise:
  stain_cv: 0.05      # NEW: 5% plate-level stain variation
  focus_cv: 0.04      # NEW: 4% tile-level focus variation
```

---

## Implementation Architecture

### Time Structure of Noise (Critical!)

```
1. Baseline morphology (cell_line)
2. ⭐ Persistent per-well biology (BEFORE compound effects)
3. Mechanistic perturbations (stress axes, transport dysfunction)
4. Stress susceptibility (gain modulation)
5. Viability scaling + washout artifacts
6. Residual biological noise (small)
7. Plating artifacts (time-decaying)
8. ⭐ Coupled technical noise (stain, focus, edge, illumination)
9. Pipeline drift
```

**Key insight:** Per-well biology applied **before** compound effects (line 98-101) so it affects **baseline**, not just measurement.

---

## Expected Outcomes

### Vehicle Islands (NOMINAL conditions)

**Before:**
- CV: 2-4%
- Source: cell_line_cv=2% + technical noise=1-2%
- Problem: Too clean, RNG churn

**After:**
- CV: 8-12%
- Sources:
  - Per-well baseline shifts: 8-10% (dominant)
  - Residual cell_line_cv: 4%
  - Coupled stain/focus drift: 5%
  - Technical noise: 2-3%
- Characteristics:
  - Replicates show **persistent differences**
  - ER and Mito drift together (stain coupling)
  - Texture features correlated (focus coupling)

---

### Treatment Wells (ANCHOR islands)

**Before:**
- CV: 8-15%
- Source: stress_cv_multiplier × cell_line_cv

**After:**
- CV: 15-25%
- Sources:
  - Per-well baseline shifts: 8-10%
  - Stress_susceptibility variation: ±15% treatment gain
  - Stress-inflated cell_line_cv: 8% (2× baseline)
  - Technical noise: 2-3%
- Characteristics:
  - Wells respond differently to same treatment
  - Still see treatment effect clearly (signal > noise)

---

### Outliers

**Before:**
- Rate: 10% (4/40 in validation)
- Magnitude: 20-150% CV (pure RNG)
- Fingerprint: None (random channel effects)

**After:**
- Rate: Still ~10% (seed-dependent)
- Magnitude: 30-50% CV (realistic failures)
- Fingerprints:
  - **Stain-like**: ER+Mito+RNA correlated drop
  - **Focus-like**: Nucleus+Actin variance inflation + correlation
  - **Edge-like**: position-dependent (existing edge_effect)
  - **Batch-like**: plate/day/operator factors

---

## Validation Criteria

### Check 1: Vehicle Island CV
- **Expected:** 8-12% (was 2-4%)
- **Measure:** `calculate_cv(vehicle_island_er_values)`
- **Pre-structured:** 12.4% ± 31.5% (huge spread, RNG gremlins)
- **Post-structured:** Should be 8-12% ± 2-3% (stable, structured)

### Check 2: Channel Correlations
- **Expected:** ER-Mito > 0.3, Nucleus-Actin > 0.2
- **Measure:** `np.corrcoef(er, mito)[0,1]`
- **Pre-structured:** 0.964 (very high, might be batch effects)
- **Post-structured:** 0.3-0.5 (stain), 0.2-0.4 (focus)

### Check 3: Cross-Seed Well Identity ⭐ **Critical**
- **Expected:** Within-well CV < 15% across seeds
- **Measure:** CV of same well_id across different seeds
- **Pre-structured:** 26% (FAIL - no persistent identity)
- **Post-structured:** <15% (wells maintain identity)

### Check 4: Outlier Fingerprints
- **Expected:** Top 5% outliers cluster by stain or focus signature
- **Measure:** Stain/focus consistency scores
- **Pre-structured:** 0.59 (marginal)
- **Post-structured:** >0.7 (clear fingerprints)

---

## Validation Script

**Location:** `scripts/validate_structured_noise.py`

**Usage:**
```bash
# Test on existing validation data (pre-structured)
python3 scripts/validate_structured_noise.py

# Test on new runs (post-structured)
python3 scripts/validate_structured_noise.py 2000 2100 2200
```

**What it checks:**
1. Vehicle island CV in realistic range
2. Channel correlations (stain/focus coupling)
3. Cross-seed well persistence (critical test!)
4. Outlier fingerprints (classifiable causes)

---

## Code Locations

### Core Implementation

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| VesselState.well_biology | `biological_virtual.py` | 247-250 | Persistent state fields |
| Initialize rng_well | `biological_virtual.py` | 1395-1398 | Deterministic per-well RNG |
| _ensure_well_biology() | `cell_painting.py` | 171-198 | Lazy initialization |
| _apply_well_biology_baseline() | `cell_painting.py` | 200-207 | Apply baseline shifts |
| Call in measure() | `cell_painting.py` | 98-101 | Early application (before compounds) |
| _add_biological_noise() | `cell_painting.py` | 364-392 | Stress susceptibility + residual |
| _get_plate_stain_factor() | `cell_painting.py` | 413-415 | Plate-level stain |
| _get_tile_focus_factor() | `cell_painting.py` | 417-429 | Tile-level focus |
| Weighted coupling | `cell_painting.py` | 474-503 | Exponential weights + variance inflation |

### Parameters

| Parameter | File | Line | Value | Purpose |
|-----------|------|------|-------|---------|
| cell_line_cv | `cell_thalamus_params.yaml` | 270 | 0.04 | Residual biological noise |
| stain_cv | `cell_thalamus_params.yaml` | 249 | 0.05 | Plate-level stain variation |
| focus_cv | `cell_thalamus_params.yaml` | 250 | 0.04 | Tile-level focus variation |

---

## Why This Is Correct

### 1. Time Structure of Noise ✅

**Per-well biology is sampled once and persists.**

- Vehicle CV is no longer RNG churn
- Replicates across days make sense
- "Some wells are just weird" becomes a learnable fact

**This is exactly what real plates feel like.**

---

### 2. Biology vs Measurement Separation ✅

**Clean stack:**
1. Baseline morphology (cell line)
2. **Persistent per-well biology** (dominant CV driver)
3. Mechanistic perturbations (stress axes)
4. **Susceptibility modulation** (gain, not offset)
5. **Residual biology noise** (small, honest)
6. **Technical structure** (stain, focus, edge, illumination)
7. Pipeline drift

**That ordering is exactly right.**

Most sims collapse 2-6 into one knob. We didn't.

---

### 3. Channel Semantics Internally Consistent ✅

**Given our simplified intensity-only model:**

**Stain coupling:**
- ER, Mito, RNA strongly (intensity/staining-dependent)
- Nucleus moderately (bridge channel)
- Actin weakly (structure-dependent)

**Focus coupling:**
- Nucleus, Actin strongly (structure/texture-dependent)
- Everything else weakly (intensity less affected)

**This matches reality as seen through a low-dimensional proxy.**

---

### 4. Outliers Have Fingerprints ✅

**Moved from:**
> "154% CV because RNG felt spicy"

**To:**
> "ER+Mito+RNA collapsed together" (stain-like)
> "Nucleus+Actin blew up together" (focus-like)
> "Edge wells drifted in a gradient" (position-like)

**That means:**
- Outliers are classifiable
- QC metrics can reason about **cause**
- An agent can learn **which failures are ignorable**

**That's instrument learning, not just simulation.**

---

## What This Enables

### Calibration Is No Longer "Easy Mode"

An agent can't earn the gate by averaging noise away in one plate.

**It has to:**
- Recognize persistent structure
- Separate biology from instrument
- Decide when replication is worth it
- Learn which wells to mistrust

**This is exactly the behavior we wanted.**

---

### Wells Have Identity

**Before:**
- Every measurement = fresh universe
- No learning possible

**After:**
- Wells have persistent quirks
- Agent can remember mistrust
- "Bad wells stay bad" is learnable

**If an agent can remember mistrust, we've succeeded.**

---

### Instrument Learning

The simulator can now teach:
- What stain drift feels like
- What focus degradation looks like
- Which artifacts are spatial vs temporal
- When to trust vs replicate

**This is the frontier.**

---

## Next Steps

### 1. Validate Structure (Not Parameters)

**Run:**
```bash
# Generate new runs with structured noise
python3 scripts/run_v4_phase1.py --seeds 2000 2100 2200

# Validate structure
python3 scripts/validate_structured_noise.py 2000 2100 2200
```

**Success criteria:**
- ✅ Vehicle CV: 8-12%
- ✅ Channel correlations present
- ✅ **Wells maintain identity across seeds** (critical!)
- ✅ Outliers have fingerprints

**If these pass: stop tuning numbers.**

---

### 2. Stop Tuning Noise

The next frontier is NOT noise amplitude.

**It's:**
> **Can the agent explain WHY it trusts or distrusts the instrument?**

---

### 3. Wire Fingerprints Into QC Ontology

Now that outliers have identifiable causes:
- Stain-like failures
- Focus-like failures
- Edge-like failures
- Batch-like failures

**QC metrics can classify them.**

---

### 4. Test Agent Difficulty

**Does the agent still earn the gate too easily?**

If yes, the problem is NOT noise.
The problem is:
- QC thresholds
- Earned trust criteria
- Budget constraints

**But now we have realistic instrument behavior to test against.**

---

## Conclusion

**We've crossed from:**
> "a simulator that can compare plate designs"

**To:**
> **"a simulator that can teach an agent what an instrument feels like."**

**That's the distinction that matters.**

Everything else is tuning.

---

**Document Status:** Implementation Complete, Ready for Validation
**Last Updated:** 2025-12-22
**Authors:** Claude Code + BJH
**Review Status:** Structure Validated by Expert

