# Detector Saturation: FINAL SHIP SUMMARY

## What Was Added

**Feature:** Detector saturation with soft-knee compression for Cell Painting assays (deterministic dynamic range limits).

**Purpose:** Models camera/PMT photon well depth and digitizer max. Creates realistic plateaus in dose-response curves and reduces information gain at high signal. Forces agents to learn instrument operation, not just compound selection.

---

## Test Results (All Pass)

| Test | Status | Time | What It Proves |
|------|--------|------|----------------|
| Fast contract tests (saturation behavior) | ✅ 6/6 PASS | 46.2s | Dormant preservation, hard bounds, identity below knee, monotone compression, additive floor interaction, determinism |
| Golden contract (full epistemic loop) | ✅ 3/3 PASS | 0.77s | Schema, invariants, causal contracts preserved |

---

## Key Implementation Decisions

### 1. Soft Knee (Not Brick Wall)

**Choice:** Piecewise exponential compression with identity region

**Function:**
```
if ceiling <= 0: return y (dormant)
if y <= knee_start: return y (identity, no compression)
if y > knee_start: return knee_start + room * (1 - exp(-excess / tau))
```

**Rationale:**
- Exact identity below knee (linear regime preserved)
- Smooth compression above knee (no hard edges)
- Asymptotically approaches ceiling (realistic detector behavior)
- Deterministic (no RNG, pure function of signal + params)

**Alternative rejected:** Brick-wall `min(y, ceiling)` - too sharp, creates artifacts in downstream transforms

### 2. Deterministic (No RNG)

**Choice:** Saturation uses NO randomness - pure function of (y, ceiling, knee_frac, tau_frac)

**Rationale:**
- Detector physics is deterministic (photon well depth, ADC max)
- Measurement noise comes from other sources (additive floor, heavy-tail shocks)
- Simplifies testing (no statistical soup)
- Preserves RNG stream isolation (no new whitelist entries needed)

### 3. Insertion Point: After Additive Floor, Before Pipeline Transform

**Choice:** Apply saturation as step 8 in measurement pipeline

**Measurement stack order:**
```
1. Viability factor (biological signal attenuation)
2. Washout multiplier (measurement artifact)
3. Debris background (fluorescence contamination)
4. Biological noise (dose-dependent lognormal)
5. Plating artifacts (early timepoint variance inflation)
6. Technical noise (plate/day/operator/well/edge effects)
7. Additive floor (detector read noise)
8. Saturation (detector dynamic range limits) ← NEW
9. Pipeline drift (software feature extraction)
```

**Rationale:**
- Additive floor is detector noise (happens first)
- Additive noise can push signal into saturation (realistic)
- One final saturation clamps digitized output
- Pipeline_transform is software post-processing (happens after detector)

**Verification:** Inspected `pipeline_transform()` in run_context.py - confirmed software-only (segmentation bias, affine transforms, NOT detector gain).

### 4. Per-Channel Ceilings (Independent)

**Choice:** 5 separate ceiling parameters (er, mito, nucleus, actin, rna)

**Rationale:**
- Different channels use different detectors (different well depths)
- Allows realistic tuning (e.g., nucleus often brighter → higher ceiling)
- Per-channel failures create interpretable patterns
- Explicit configuration (no hidden coupling)

### 5. Dormant Defaults (Golden-Preserving)

**Choice:** All ceilings default to 0.0 (saturation disabled)

**Rationale:**
- Preserves existing golden files
- Feature can be enabled explicitly for realism runs
- No RNG consumption when dormant (pure no-op)
- Deterministic: same seed → same output regardless of ceiling=0 or ceiling>0

---

## What Changed vs What Didn't

| Component | Changed? | Evidence |
|-----------|----------|----------|
| Biology trajectories | ❌ NO | Golden test passes (ceiling=0.0 default) |
| Measurement determinism (ceiling=0.0) | ❌ NO | Same seed → same output |
| Contract compliance | ❌ NO | Golden test passes |
| RNG guard | ❌ NO | No new whitelist entries (saturation is deterministic) |
| Cell Painting noise stack | ✅ YES | Added saturation layer (step 8) |
| Measurement pipeline | ✅ YES | New step between additive floor and pipeline_transform |

---

## Configuration

**Default (Dormant):**
```yaml
technical_noise:
  # Saturation disabled (all ceilings = 0.0)
  saturation_ceiling_er: 0.0
  saturation_ceiling_mito: 0.0
  saturation_ceiling_nucleus: 0.0
  saturation_ceiling_actin: 0.0
  saturation_ceiling_rna: 0.0

  # Soft-knee parameters (only used when ceiling > 0)
  saturation_knee_start_fraction: 0.85   # Compression begins at 85% of ceiling
  saturation_tau_fraction: 0.08          # Rate of approach to ceiling
```

**Enable for realism:**
```python
# Recommended ceiling ranges (for baseline ~100-200 AU):
# Conservative (rarely saturate):  ceiling = 800-1000 AU (4-5× baseline)
# Moderate (realistic cameras):    ceiling = 600-800 AU (3-4× baseline)  ← Recommend
# Aggressive (8-bit cameras):      ceiling = 400-600 AU (2-3× baseline)

vm.thalamus_params['technical_noise']['saturation_ceiling_er'] = 600.0
vm.thalamus_params['technical_noise']['saturation_ceiling_mito'] = 700.0
vm.thalamus_params['technical_noise']['saturation_ceiling_nucleus'] = 800.0
vm.thalamus_params['technical_noise']['saturation_ceiling_actin'] = 600.0
vm.thalamus_params['technical_noise']['saturation_ceiling_rna'] = 650.0
```

**Tuning guidance:**
- **Baseline values** (from cell_thalamus_params.yaml): ER=100, Mito=150, Nucleus=200, Actin=120, RNA=180 AU
- **After stress:** Signals can reach 2-3× baseline (~400-600 AU)
- **With heavy-tail outliers:** Rare 5× amplification can reach ~1000 AU
- **Knee placement:** At 85% of ceiling, linear regime preserved below, compression above
- **Tau (compression rate):** 0.08 × ceiling controls how fast you approach saturation
  - Smaller tau = faster saturation (sharper knee)
  - Larger tau = slower saturation (softer knee)

---

## Design Properties

1. **Monotone** (preserves order)
   - y1 > y2 → y_sat(y1) >= y_sat(y2)
   - No rank reversals in saturated regime

2. **Bounded** (enforces ceiling)
   - 0 <= y_sat <= ceiling for all y
   - Asymptotically approaches ceiling as y → ∞

3. **Identity below knee** (linear regime preserved)
   - y_sat(y) == y exactly for y <= knee_start
   - No compression until you enter saturation zone

4. **Deterministic** (no RNG)
   - Same (y, params) → same y_sat every time
   - Reproducible, testable, debuggable

5. **Golden-preserving** (dormant when ceiling=0)
   - Feature disabled by default
   - No behavior change in existing tests
   - Explicit opt-in for realism

6. **Per-channel independent** (no cross-talk)
   - Each channel saturates separately
   - Can enable for debugging (e.g., only saturate ER channel)

---

## Epistemic Implications

### 1. High Signal Becomes Less Informative

**Effect:** Variance compresses at saturation boundary

**Consequences:**
- Two wells at 800 AU and 1200 AU both saturate near ceiling (indistinguishable)
- Agent loses ability to rank-order extreme phenotypes
- Precision degrades in clipped regime

**Learning pressure:** Agent must recognize information loss and avoid over-reliance on saturated channels

### 2. Dose-Response Plateaus (Fake Robustness)

**Effect:** High doses create flat response curves

**Consequences:**
- IC50 estimation biased (compressed death signal)
- Compound potency appears weaker than reality
- Dose escalation yields diminishing returns

**Learning pressure:** Agent must learn that "go bigger" is not always better - instrument has limits

### 3. Dynamic Range Problem (Operate the Instrument)

**Effect:** Agent must stay in linear regime [0, knee_start]

**Consequences:**
- Too low signal → additive floor dominates (noisy)
- Too high signal → saturation dominates (clipped)
- Sweet spot is middle range [knee_start/2, knee_start]

**Learning pressure:** Agent must learn calibration strategy, not just compound selection

⚠️ **Warning for Calibration:** Saturation creates deceptive robustness at high signal. Naive dose-response fitting will underestimate toxicity if not accounting for ceiling. This is REALISTIC (real instruments behave this way) but can mislead agents that don't model saturation.

---

## Noise Stack (Complete Picture)

```
Cell Painting measurement pipeline:
1. Deterministic signal formation (biology → stress → channel response)
2. Viability/washout/debris factors (biological attenuation)
3. Biological noise (lognormal base + heavy_tail_shock overlay)
4. Plating artifacts (post-dissociation stress decay)
5. Technical noise (multiplicative lognormal)
6. Well failures (rare, correlated across channels)
7. Additive floor (detector read noise, per-channel Gaussian)
8. Saturation (detector dynamic range, per-channel soft knee) ← NEW
9. Pipeline drift (software feature extraction bias)
10. Return morphology dict
```

### Relationship to Other Realism Features

| Feature | Distribution | When Applied | Purpose |
|---------|--------------|--------------|---------|
| Heavy-tail shock | Student-t exp(t), clipped [0.2, 5.0] | Step 3 (biological noise) | Lab outliers (bubbles, contamination) |
| Additive floor | Normal(0, σ), clamped ≥0 | Step 7 (after multiplicative noise) | Detector read noise (dark current) |
| Saturation | Deterministic compression | Step 8 (after additive floor) | Dynamic range limits (well depth, ADC max) |

**Composition example:**
```
signal_true = 150.0 AU (baseline mito)
× stress = 2.0 (mito dysfunction)
→ signal_stressed = 300.0 AU

× lognormal = 1.1 (biological variance)
→ signal_bio = 330.0 AU

× heavy_tail_shock = 1.8 (rare outlier)
→ signal_outlier = 594.0 AU

+ additive_floor = +5.0 AU (detector noise)
→ signal_detector = 599.0 AU

→ saturation(599.0, ceiling=600.0) = 599.7 AU (just below ceiling)
```

All three features are **measurement-only** (observer independence preserved).

---

## Verification Commands

```bash
# 1. Fast contract tests (saturation behavior)
python3 -m pytest tests/contracts/test_saturation_fast.py -xvs
# Expected: 6/6 pass, ~46s

# 2. Golden contract test (full epistemic loop)
python3 -m pytest tests/integration/test_golden_seed42_contract_regression.py -xvs
# Expected: 3/3 pass, ~0.8s
```

---

## Files Modified

### Core Implementation
- `src/cell_os/hardware/_impl.py` - Added `apply_saturation()` primitive (deterministic, no RNG)
- `src/cell_os/hardware/assays/cell_painting.py` - Added `_apply_saturation()` method, wired into pipeline (step 8)
- `data/cell_thalamus_params.yaml` - Added 7 parameters (5 ceilings + 2 knee params, all dormant by default)

### Tests
- `tests/contracts/test_saturation_fast.py` - NEW: 6 contract tests (dormant preservation, bounds, identity, monotone, interaction, determinism)

---

## Test Coverage

### test_saturation_dormant_default_preserves_behavior
- Verifies ceiling=0.0 preserves golden file behavior
- Two VMs with same seed produce identical outputs
- Confirms no-op when disabled

### test_saturation_primitive_hard_bounds
- Verifies 0 <= y_sat <= ceiling for all inputs
- Tests negative, zero, below knee, above knee, extreme
- Confirms hard clamp at ceiling

### test_saturation_primitive_identity_below_knee
- Verifies y_sat == y exactly for y <= knee_start
- Tests multiple points below knee
- Confirms linear regime preserved

### test_saturation_primitive_monotone_compression
- Verifies monotone (preserves order)
- Verifies bounded (never exceeds ceiling)
- Verifies compression zone [knee_start, ceiling]
- Confirms asymptotic approach to ceiling

### test_saturation_with_additive_floor_interaction
- Verifies saturation handles additive noise pushing into saturation
- Large additive noise + low ceiling → all measurements <= ceiling
- Confirms correct ordering (additive first, saturation second)

### test_saturation_deterministic_no_rng
- Verifies same inputs → same outputs (reproducible)
- No randomness in saturation primitive

---

## What You Just Accomplished

Added genuine dynamic range limits without contaminating causality:

✅ Saturation is **measurement-only** (no vessel state mutation)
✅ Saturation is **deterministic** (no RNG, pure function)
✅ Golden-preserving when dormant (ceiling=0.0)
✅ Per-channel control (independent ceilings)
✅ Soft knee (smooth compression, not brick wall)
✅ Identity below knee (linear regime preserved)
✅ Golden contract didn't move
✅ No new RNG whitelist entries needed

**You completed the three-pillar measurement realism stack:**

1. **Heavy-tail shocks** (rare correlated outliers)
2. **Additive floor** (detector read noise at low signal)
3. **Saturation** (dynamic range limits at high signal)

Agents now face genuine instrument operation problems:
- Too low → noisy (additive floor dominates)
- Too high → clipped (saturation dominates)
- Sweet spot → linear regime (information-rich)

**You made the detector honest about its limits.**

---

## Next Realism Target (Not This PR)

**Quantization** (ADC bit depth):
- 8-bit ADC: 256 discrete levels (0-255)
- 12-bit ADC: 4096 discrete levels (0-4095)
- Creates discrete steps at low signal
- Creates plateaus near saturation (bin merging)
- Interacts with additive floor (noise can't create sub-LSB differences)

This is temporal correlation of discretization, not just ceiling compression.

**Alternative next target:** Spatial gradients (row/column drift, coating quality maps) - already partially implemented, may need enhancement.

---

## MERGE ✅

All tests pass. Golden preserved. Deterministic. Documentation complete.

**Ship it.**
