# Noise Fix Implementation Plan

**Date:** 2025-12-22
**Status:** 📝 Design Phase
**Goal:** Add structured biological heterogeneity without "amplitude mush"

---

## Problem Statement

Current `cell_line_cv = 0.02` produces vehicle island CV of 2-4%.
Reality: Cell Painting shows 8-15% CV for biological replicates.

**❌ Wrong fix:** Increase `cell_line_cv` to 0.10
- Gets CV to right range
- But applies **independent** lognormal noise per channel
- No structure, no persistence, no coupling

**✅ Right fix:** Add **per-well latent biology** with structured heterogeneity

---

## Design: Three-Layer Noise Architecture

### Layer 1: Persistent Per-Well Biology (NEW) ⭐

**Purpose:** Wells have stable "cell state" independent of treatment

**Implementation:**
```python
# Add to VesselState.__init__() - sampled once at plating
def _sample_well_biology(self, rng_seed):
    """Sample persistent biological factors for this well."""
    # Use well-specific RNG (deterministic per well+seed)
    rng = np.random.default_rng(rng_seed)

    return {
        # Channel-specific baseline shifts (persistent heterogeneity)
        'er_baseline_shift': rng.normal(0, 0.08),      # ±8% ER variation
        'mito_baseline_shift': rng.normal(0, 0.10),    # ±10% mito variation
        'nucleus_baseline_shift': rng.normal(0, 0.06), # ±6% nucleus variation
        'actin_baseline_shift': rng.normal(0, 0.07),   # ±7% actin variation
        'rna_baseline_shift': rng.normal(0, 0.09),     # ±9% RNA variation

        # Stress response modulation (affects treatment gain)
        'stress_susceptibility': rng.lognormal(0, 0.15),  # 0.7-1.4× stress response

        # Confluence sensitivity (affects contact pressure bias)
        'confluence_sensitivity': rng.uniform(0.9, 1.1),
    }
```

**Apply in morphology baseline:**
```python
# In CellPaintingAssay.measure() - apply to baseline, not final
baseline = self.vm.thalamus_params['baseline_morphology'].get(cell_line)

# Apply per-well shifts to baseline (before treatment)
morph = {
    'er': baseline['er'] * (1.0 + vessel.well_biology['er_baseline_shift']),
    'mito': baseline['mito'] * (1.0 + vessel.well_biology['mito_baseline_shift']),
    'nucleus': baseline['nucleus'] * (1.0 + vessel.well_biology['nucleus_baseline_shift']),
    'actin': baseline['actin'] * (1.0 + vessel.well_biology['actin_baseline_shift']),
    'rna': baseline['rna'] * (1.0 + vessel.well_biology['rna_baseline_shift'])
}
```

**Apply to treatment response:**
```python
# In _apply_compound_effects() - modulate stress response gain
compound_effect_magnitude *= vessel.well_biology['stress_susceptibility']
```

**Expected impact:**
- Vehicle wells: Persistent 8-10% CV (from baseline shifts)
- Treatment wells: Additional variance from stress_susceptibility
- Replicates show stable differences (not RNG churn)

---

### Layer 2: Coupled Technical Noise (ENHANCEMENT)

**Purpose:** Shared factors affect multiple channels together

**Implementation:**
```python
def _add_technical_noise_coupled(self, vessel, morph, **kwargs):
    """Add technical noise with channel coupling."""

    # 1. Shared staining factor (affects ER, Mito, RNA together)
    stain_cv = 0.05  # 5% stain lot variation
    stain_factor = lognormal_multiplier(self.vm.rng_assay, stain_cv)
    morph['er'] *= stain_factor
    morph['mito'] *= stain_factor
    morph['rna'] *= stain_factor

    # 2. Shared focus factor (affects texture features)
    focus_offset = kwargs.get('focus_offset_um', 0.0)
    focus_quality = 1.0 + focus_offset * (-0.02)  # -2% per µm
    morph['nucleus'] *= focus_quality
    morph['actin'] *= focus_quality

    # 3. Independent well-to-well measurement noise (small)
    well_measurement_cv = 0.015  # 1.5% (keep current)
    for channel in morph:
        morph[channel] *= lognormal_multiplier(self.vm.rng_assay, well_measurement_cv)

    # 4. Existing plate/day/operator factors (already coupled)
    morph = self._apply_batch_factors(morph, **kwargs)

    return morph
```

**Expected impact:**
- Stain drift creates correlated ER+Mito+RNA movement
- Focus issues affect texture features together
- Outliers have characteristic "fingerprints"

---

### Layer 3: Structured Outliers (ENHANCEMENT)

**Purpose:** Failures have identifiable causes, not pure RNG

**Implementation:**
```python
def _apply_well_failure_structured(self, morph, well_position, **kwargs):
    """Apply well failures with position/provocation coupling."""

    # Base failure rate
    base_failure_rate = 0.02  # 2% baseline

    # Increase failure rate for edge wells
    if self._is_edge_well(well_position):
        failure_rate = base_failure_rate * 2.0  # 4% on edges
    else:
        failure_rate = base_failure_rate

    # Increase failure rate for poor focus/stain probes
    focus_offset = abs(kwargs.get('focus_offset_um', 0.0))
    stain_scale = kwargs.get('stain_scale', 1.0)

    if focus_offset > 2.0:  # Focus probe
        failure_rate *= 1.5
    if stain_scale < 0.7 or stain_scale > 1.3:  # Stain probe
        failure_rate *= 1.3

    # Sample failure
    if rng.random() > failure_rate:
        return None  # No failure

    # Select failure mode with position-dependent probabilities
    if self._is_edge_well(well_position):
        # Edge wells: more evaporation-related failures
        mode_probs = {
            'bubble': 0.20,
            'evaporation_artifact': 0.40,  # NEW
            'focus_failure': 0.25,
            'contamination': 0.15
        }
    else:
        # Interior wells: standard distribution
        mode_probs = {
            'bubble': 0.40,
            'focus_failure': 0.30,
            'contamination': 0.20,
            'pipetting_miss': 0.10
        }

    return self._apply_failure_effect(morph, selected_mode)
```

**Expected impact:**
- Edge wells fail more (evaporation, temperature)
- Focus/stain probes create correlated failures
- Outliers have causal stories, not RNG gremlins

---

## Implementation Steps (Ordered)

### Step 1: Add Per-Well Biology to VesselState ⭐

**Files to modify:**
- `src/cell_os/hardware/biological_virtual.py` (VesselState class)

**Changes:**
```python
class VesselState:
    def __init__(self, vessel_id: str, cell_line: str, initial_count: float = 0):
        # ... existing fields ...

        # NEW: Sample persistent well biology
        well_seed = stable_u32(f"well_biology_{vessel_id}_{self.seed}")
        self.well_biology = self._sample_well_biology(well_seed)

    def _sample_well_biology(self, seed: int) -> Dict[str, float]:
        """Sample persistent biological heterogeneity for this well."""
        rng = np.random.default_rng(seed)
        return {
            'er_baseline_shift': rng.normal(0, 0.08),
            'mito_baseline_shift': rng.normal(0, 0.10),
            'nucleus_baseline_shift': rng.normal(0, 0.06),
            'actin_baseline_shift': rng.normal(0, 0.07),
            'rna_baseline_shift': rng.normal(0, 0.09),
            'stress_susceptibility': rng.lognormal(0, 0.15),
            'confluence_sensitivity': rng.uniform(0.9, 1.1),
        }
```

**Effort:** ~30 lines
**Risk:** Low (new field, doesn't break existing)

---

### Step 2: Apply Per-Well Biology to Morphology

**Files to modify:**
- `src/cell_os/hardware/assays/cell_painting.py`

**Changes:**
```python
def measure(self, vessel, **kwargs):
    # Get baseline morphology
    baseline = self.vm.thalamus_params['baseline_morphology'].get(cell_line)

    # CHANGE: Apply per-well shifts to baseline (not to final)
    morph = {
        'er': baseline['er'] * (1.0 + vessel.well_biology['er_baseline_shift']),
        'mito': baseline['mito'] * (1.0 + vessel.well_biology['mito_baseline_shift']),
        'nucleus': baseline['nucleus'] * (1.0 + vessel.well_biology['nucleus_baseline_shift']),
        'actin': baseline['actin'] * (1.0 + vessel.well_biology['actin_baseline_shift']),
        'rna': baseline['rna'] * (1.0 + vessel.well_biology['rna_baseline_shift'])
    }

    # Apply compound effects (existing)
    morph, has_microtubule = self._apply_compound_effects(vessel, morph, baseline)

    # Apply latent stress (existing)
    morph = self._apply_latent_stress_effects(vessel, morph)

    # ... rest of measurement layer ...
```

**Changes to compound effects:**
```python
def _apply_compound_effects(self, vessel, morph, baseline):
    # ... compute compound response ...

    # NEW: Modulate treatment response by stress_susceptibility
    stress_response = vessel.well_biology['stress_susceptibility']

    # Apply stress axis effects scaled by susceptibility
    for channel in stress_axis_effects:
        channel_delta = morph[channel] - baseline[channel]
        morph[channel] = baseline[channel] + (channel_delta * stress_response)

    return morph, has_microtubule_compound
```

**Effort:** ~50 lines
**Risk:** Medium (changes core measurement, needs testing)

---

### Step 3: Add Channel Coupling to Technical Noise

**Files to modify:**
- `src/cell_os/hardware/assays/cell_painting.py`

**Changes:**
```python
def _add_technical_noise(self, vessel, morph, **kwargs):
    """Add technical noise with channel coupling."""

    # Shared staining factor (NEW)
    stain_cv = 0.05
    stain_factor = lognormal_multiplier(self.vm.rng_assay, stain_cv)
    morph['er'] *= stain_factor
    morph['mito'] *= stain_factor
    morph['rna'] *= stain_factor

    # Shared focus factor (NEW)
    focus_offset = kwargs.get('focus_offset_um', 0.0)
    focus_quality = 1.0 + focus_offset * (-0.02)
    morph['nucleus'] *= max(0.5, focus_quality)
    morph['actin'] *= max(0.5, focus_quality)

    # Existing factors (keep)
    morph = self._apply_batch_factors(morph, **kwargs)

    # Reduced independent well noise (now only 1.5%, not doing all the work)
    well_cv = 0.015
    for channel in morph:
        morph[channel] *= lognormal_multiplier(self.vm.rng_assay, well_cv)

    return morph
```

**Effort:** ~20 lines
**Risk:** Low (additive change)

---

### Step 4: Keep `cell_line_cv` Modest

**Files to modify:**
- `data/cell_thalamus_params.yaml`

**Changes:**
```yaml
biological_noise:
  cell_line_cv: 0.04  # Modest increase (was 0.02, NOT 0.10)
  stress_cv_multiplier: 2.0
```

**Rationale:**
- Per-well shifts provide 8-10% baseline CV
- Keep `cell_line_cv` small (4%) for residual within-measurement variation
- Total CV = sqrt(well_biology^2 + cell_line_cv^2) ≈ 8-12%

**Effort:** 1 line
**Risk:** Low

---

## Expected Outcomes (After Full Implementation)

### Vehicle Islands (NOMINAL conditions)

**Before (current):**
- CV: 2-4%
- Source: cell_line_cv=2% + technical noise=1-2%

**After (with per-well biology):**
- CV: 8-12%
- Sources:
  - Per-well baseline shifts: 8-10% (dominant)
  - Residual cell_line_cv: 4%
  - Technical noise: 2-3%
  - Coupled stain/focus drift: 5%

**Characteristics:**
- Replicates show **persistent differences** (not RNG churn)
- ER and Mito drift together (stain coupling)
- Texture features correlated (focus coupling)

---

### Treatment Wells (ANCHOR islands)

**Before (current):**
- CV: 8-15%
- Source: stress_cv_multiplier × cell_line_cv

**After (with per-well biology):**
- CV: 15-25%
- Sources:
  - Per-well baseline shifts: 8-10%
  - Stress_susceptibility variation: ±15% treatment gain
  - Stress-inflated cell_line_cv: 8% (2× baseline)
  - Technical noise: 2-3%

**Characteristics:**
- Wells respond differently to same treatment (heterogeneous susceptibility)
- Still see treatment effect clearly (signal > noise)

---

### Outliers

**Before (current):**
- Rate: 10% (4/40 in validation)
- Magnitude: 20-150% CV (pure RNG)
- Fingerprint: None (random channel effects)

**After (with structured failures):**
- Rate: 1-2% (edge wells higher)
- Magnitude: 30-50% CV (realistic failures)
- Fingerprints:
  - Bubble: all channels near-zero
  - Focus failure: texture features low, intensity OK
  - Stain failure: ER+Mito+RNA correlated drop
  - Edge evaporation: position-correlated

---

## Validation Plan

### Test 1: Vehicle Island CV

```bash
# Implement Step 1 + 2 (per-well biology)
# Re-run Phase 1
python3 scripts/run_v4_phase1.py --seeds 1000 1100 1200

# Check CV
python3 scripts/analyze_v4_phase1.py
```

**Success criteria:**
- Vehicle island CV: 8-12% (was 2-4%)
- Replicates show persistent differences (not pure RNG)

---

### Test 2: Channel Correlation

```python
# Check if channels couple appropriately
import json
import numpy as np

# Load results
with open('results.json') as f:
    data = json.load(f)

# Extract channel values for boring wells
boring_wells = [r for r in data['flat_results'] if is_boring(r)]

er_values = [r['morph_er'] for r in boring_wells]
mito_values = [r['morph_mito'] for r in boring_wells]
rna_values = [r['morph_rna'] for r in boring_wells]

# Check correlation (should be positive from stain coupling)
corr_er_mito = np.corrcoef(er_values, mito_values)[0,1]
corr_er_rna = np.corrcoef(er_values, rna_values)[0,1]

print(f"ER-Mito correlation: {corr_er_mito:.3f}")  # Should be 0.3-0.5
print(f"ER-RNA correlation: {corr_er_rna:.3f}")   # Should be 0.3-0.5
```

**Success criteria:**
- ER-Mito correlation: 0.3-0.5 (from stain coupling)
- Nucleus-Actin correlation: 0.2-0.4 (from focus coupling)

---

### Test 3: Replicate Persistence

```python
# Check if wells maintain identity across seeds
# (should be stable if well_biology is seed-deterministic)

seed1_results = load_results(seed=1000)
seed2_results = load_results(seed=1100)

# Same well in both seeds should have similar morphology
well_A1_seed1 = get_well(seed1_results, 'A1')
well_A1_seed2 = get_well(seed2_results, 'A1')

# Baseline should be similar (treatment and measurement noise vary)
baseline_correlation = check_baseline_stability(well_A1_seed1, well_A1_seed2)

print(f"Cross-seed well identity: {baseline_correlation:.3f}")  # Should be 0.7-0.9
```

**Success criteria:**
- Well identity preserved across seeds (baseline stable)
- But measurements still vary (from assay RNG)

---

## Risk Assessment

### Risk 1: Breaking Existing Validation

**Concern:** V3/V4/V5 comparisons used current noise levels

**Mitigation:**
- Per-well biology is **additive** (doesn't change relative comparisons)
- Plate design spatial structure unaffected
- Relative performance preserved

**Testing:**
- Re-run V3 vs V4 comparison with new noise
- Spatial variance ratio should stay similar

---

### Risk 2: Over-Noising Treatment Effects

**Concern:** Stress_susceptibility variation might wash out treatment signals

**Mitigation:**
- Keep stress_susceptibility CV modest (15%)
- 0.7-1.4× range preserves dose-response curves
- Signal-to-noise still strong (2-3×)

**Testing:**
- Check anchor Z-factors (should stay > 0.5)
- Dose-response curves should maintain Hill slope

---

### Risk 3: Parameter Tuning Complexity

**Concern:** Now have 7+ per-channel shift parameters to tune

**Mitigation:**
- Use biologically informed priors (literature CVs)
- Tune on wet lab data (when available)
- Start conservative (smaller CVs), increase if needed

**Strategy:**
- Step 1: Implement with conservative CVs (6-8%)
- Step 2: Validate against wet lab
- Step 3: Adjust if needed

---

## Timeline

**Phase 1: Per-Well Biology** (Priority)
- Implement VesselState.well_biology: 2h
- Apply to morphology baseline: 3h
- Apply to treatment response: 2h
- Test Phase 1 replication: 1h
- **Total: ~8 hours**

**Phase 2: Channel Coupling** (High value)
- Implement coupled technical noise: 2h
- Test channel correlations: 1h
- **Total: ~3 hours**

**Phase 3: Structured Outliers** (Lower priority)
- Implement position-dependent failures: 2h
- Test outlier fingerprints: 1h
- **Total: ~3 hours**

**Grand total: ~14 hours** (2 days)

---

## Decision Points

### Decision 1: Do Now or Wait for Wet Lab?

**Recommendation:** **Do Step 1 (per-well biology) now**

**Rationale:**
- Don't need wet lab to know 2-4% is too clean
- Persistent heterogeneity is missing regardless of exact CV
- Can tune magnitudes later with wet lab data

---

### Decision 2: All Steps or Just Step 1?

**Recommendation:** **Step 1 + 2 (biology + coupling), defer Step 3**

**Rationale:**
- Step 1 fixes baseline CV (critical)
- Step 2 adds realistic structure (high value)
- Step 3 is polish (nice-to-have)

---

## References

### Internal Docs
- `docs/NOISE_INJECTION_STATUS.md` - Current implementation
- `docs/V4_PHASE1_VALIDATION_RESULTS.md` - Observed 2-4% CV

### Code Locations
- `src/cell_os/hardware/biological_virtual.py` - VesselState
- `src/cell_os/hardware/assays/cell_painting.py` - Noise application
- `data/cell_thalamus_params.yaml` - Parameters

### Literature (Cell Painting CV ranges)
- Typical biological replicate CV: 8-15%
- Technical replicate CV: 3-5%
- Well-to-well variation: 5-10%

---

**Document Status:** Design Complete, Awaiting Implementation Decision
**Last Updated:** 2025-12-22
**Authors:** Claude Code + BJH + ChatGPT Critique
**Next Step:** Approve design and implement Step 1
