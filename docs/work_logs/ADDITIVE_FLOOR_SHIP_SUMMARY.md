# Additive Noise Floor: FINAL SHIP SUMMARY

## What Was Added

**Feature:** Additive Gaussian detector read noise for Cell Painting assays (Normal distribution, per-channel sigmas).

**Purpose:** Models CCD/PMT dark current and electronics noise that dominates at low signal, independent of signal magnitude.

---

## Test Results (All Pass)

| Test | Status | Time | What It Proves |
|------|--------|------|----------------|
| Fast contract tests (additive floor behavior) | ✅ 5/5 PASS | 12.1s | Primitive correctness, clamp bias, biology isolation, golden-preserving, RNG isolation |
| Golden contract (full epistemic loop) | ✅ 3/3 PASS | 0.71s | Schema, invariants, causal contracts preserved |

---

## Key Implementation Decisions

### 1. Golden-Preserving (Not Draw-Count Invariant)

**Choice:** Conditional execution - only draw from RNG when sigma > 0

**Rationale:** Preserves existing golden files when feature is dormant (default sigma=0.0)

**Tradeoff:** Not draw-count invariant across configs (different sigmas consume different RNG draws).

⚠️ **Critical implication:** Turning on additive floor changes the RNG draw schedule, so trajectories are NOT pairwise comparable by seed across configs. Same seed with sigma=0.0 vs sigma=2.0 will have different measurement noise realizations (not just different amplitudes). This is acceptable for golden preservation but breaks A/B isolation for debugging.

### 2. Insertion Point: Before pipeline_transform()

**Choice:** Apply additive floor AFTER technical noise, BEFORE pipeline_transform()

**Rationale:**
- pipeline_transform() is software feature extraction (batch normalization, PCA rotation)
- Additive floor is detector-level physics (happens before software processing)
- Preserves noise layering semantics: detector → optics → software

**Verification:** Inspected `pipeline_transform()` in run_context.py - confirmed it applies:
- Channel-specific segmentation bias (software thresholding)
- Affine transforms in feature space (PCA rotation/scaling)
- Batch-dependent image analysis drift (NOT detector gain)

This is definitively post-processing, so additive floor placement is correct.

### 3. Per-Channel Sigmas (Not Unified)

**Choice:** 5 separate parameters (er, mito, nucleus, actin, rna)

**Rationale:**
- Different channels use different detectors (different dark currents)
- Allows channel-specific realism tuning
- Explicit configuration (no hidden coupling)

### 4. Clamp at 0 (Not Truncated Normal)

**Choice:** Apply `max(0.0, signal + noise)` after adding Gaussian noise

**Rationale:**
- Simpler than truncated Normal sampling
- Creates small positive bias at low signal (realistic detector behavior)
- Test explicitly verifies this bias exists

### 5. Canonical Channel List (Not morph.keys())

**Choice:** Hardcode channel list `['er', 'mito', 'nucleus', 'actin', 'rna']`

**Rationale:**
- Fails loudly if channel missing from morph dict
- Prevents silent skipping if measurement pipeline changes
- Explicit contract with config parameters

---

## What Changed vs What Didn't

| Component | Changed? | Evidence |
|-----------|----------|----------|
| Biology trajectories | ❌ NO | Golden test passes (sigma=0.0 default) |
| Measurement determinism (sigma=0.0) | ❌ NO | Same seed → same output |
| Contract compliance | ❌ NO | Golden test passes |
| RNG guard | ✅ YES | Added "additive_floor_noise" and "_sample_commitment_delays_for_treatment" |
| Cell Painting noise stack | ✅ YES | Added additive floor layer |

---

## Configuration

**Default (Dormant):**
```yaml
technical_noise:
  additive_floor_sigma_er: 0.0       # DORMANT (preserves golden files)
  additive_floor_sigma_mito: 0.0
  additive_floor_sigma_nucleus: 0.0
  additive_floor_sigma_actin: 0.0
  additive_floor_sigma_rna: 0.0
```

**Enable for realism:**
```python
# Recommended sigma ranges (for baseline ~150 AU):
# Conservative (0.5-1.0% noise):  sigma = 1.0-1.5
# Moderate (1-2% noise):          sigma = 1.5-3.0  ← Default recommendation
# Aggressive (2-4% noise):        sigma = 3.0-6.0

vm.thalamus_params['technical_noise']['additive_floor_sigma_er'] = 2.0
vm.thalamus_params['technical_noise']['additive_floor_sigma_mito'] = 2.5
vm.thalamus_params['technical_noise']['additive_floor_sigma_nucleus'] = 1.8
vm.thalamus_params['technical_noise']['additive_floor_sigma_actin'] = 2.2
vm.thalamus_params['technical_noise']['additive_floor_sigma_rna'] = 1.5
```

**Tuning guidance:**
- At low signal (y~10): additive floor dominates SNR
- At baseline (y~150): additive floor contributes ~1-2% CV
- At high signal (y~500): multiplicative noise dominates
- Per-channel tuning reflects detector quality (e.g., mito channel often noisier)

---

## Design Properties

1. **Additive (not multiplicative)** - noise independent of signal magnitude
   - At low signal: additive noise dominates SNR
   - At high signal: multiplicative noise (lognormal) dominates

2. **Clamp bias at low signal** (documented and tested)
   - `max(0.0, signal + noise)` creates positive bias
   - Test verifies bias exists and is substantial at y_true=1.0

3. **Measurement-only** (cannot affect biology)
   - Uses only `rng_assay`, not `rng_growth`
   - Observer independence preserved (tested)

4. **Golden-preserving** (deterministic when dormant)
   - sigma=0.0 → no RNG draws, identical to baseline
   - Different from draw-count invariance (explicit tradeoff)

5. **Per-channel control** (no hidden coupling)
   - Can enable individual channels for debugging
   - Reflects physical reality (different detectors)

---

## Noise Stack Order (Cell Painting)

```
1. Deterministic signal formation (biology → stress → channel response)
2. Viability/washout/debris factors
3. Biological noise (lognormal base + heavy_tail_shock overlay)
4. Plating artifacts (post-dissociation stress decay)
5. Technical noise (multiplicative lognormal)
6. **Additive floor** (detector read noise) ← NEW
7. Pipeline drift (software feature extraction bias)
8. Return morphology dict
```

---

## Verification Commands

```bash
# 1. Fast contract tests (additive floor behavior)
python3 -m pytest tests/contracts/test_additive_floor_fast.py -xvs
# Expected: 5/5 pass, ~12s

# 2. Golden contract test (full epistemic loop)
python3 -m pytest tests/integration/test_golden_seed42_contract_regression.py -xvs
# Expected: 3/3 pass, ~0.7s
```

---

## Files Modified

### Core Implementation
- `src/cell_os/hardware/_impl.py` - Added `additive_floor_noise()` primitive
- `src/cell_os/hardware/assays/cell_painting.py` - Added `_add_additive_floor()` method, wired into pipeline
- `data/cell_thalamus_params.yaml` - Added 5 sigma parameters (all 0.0 default)

### RNG Guard
- `src/cell_os/hardware/biological_virtual.py` - Updated rng_treatment whitelist with "_sample_commitment_delays_for_treatment"

**Why this became necessary:** The heavy-tail PR changed RNG guard from substring match to exact match (safety fix). Previously, `_sample_commitment_delays_for_treatment` passed because it contains `_treatment` as substring. With exact match, it needs explicit whitelisting.

**Is this legitimate?** YES. This function samples commitment delays (biological heterogeneity in apoptotic commitment timing) during compound treatment. It uses rng_treatment (biological variability stream), not rng_assay (measurement stream). This is correct stream usage.

### Tests
- `tests/contracts/test_additive_floor_fast.py` - NEW: 5 contract tests

---

## Test Coverage

### test_additive_floor_primitive_correctness
- Verifies mean ~0, std ~sigma for Gaussian samples
- Checks dormant mode returns 0.0 without drawing

### test_additive_floor_clamp_bias
- Verifies positive bias at low signal due to clamping
- Quantifies bias magnitude (y_true=1.0 → bias=0.78 with sigma=3.0)

### test_additive_floor_biology_isolation
- Verifies measurements vary but biology unchanged
- Observer independence (measurement purity contract)

### test_additive_floor_golden_preserving
- Verifies sigma=0.0 preserves deterministic behavior
- Two VMs with same seed produce identical outputs

### test_additive_floor_rng_stream_isolation
- Verifies only rng_assay is used (not rng_growth/treatment/operations)
- RNG stream segregation contract

---

## What You Just Accomplished

Added detector-level realism without contaminating causality:

✅ Additive floor is **measurement-only**
✅ Golden-preserving when dormant (sigma=0.0)
✅ Per-channel control (explicit configuration)
✅ Clamp bias tested and documented
✅ Golden contract didn't move
✅ RNG stream isolation preserved
✅ Inserted at correct point in noise stack

**You made the detector more realistic without making it dishonest.**

---

## Relationship to Heavy-Tail Noise

Both features are **measurement-only** and **dormant by default**:

| Feature | Distribution | Frequency | Purpose |
|---------|--------------|-----------|---------|
| Heavy-tail shock | Student-t exp(t), clipped [0.2, 5.0] | Rare (~1%) | Lab outliers (bubbles, contamination) |
| Additive floor | Normal(0, σ), clamped ≥0 | Always | Detector read noise (dark current) |

**Noise composition:**
```
signal_measured = (signal_true × base_lognormal × heavy_tail_shock) + additive_floor
```

Both features:
- Use only `rng_assay` (observer independence)
- Default to dormant (preserve golden files)
- Have fast contract tests (<15s total)
- Are documented with design rationale

---

## Next Realism Target (Not This PR)

**Spatial correlations** (plate-level structure):
- Row/column gradients (liquid handler drift)
- Edge well artifacts (evaporation/temperature)
- Coating quality heterogeneity (spatial maps)

This is already partially implemented - may need enhancement for structured non-stationarity.

---

## Merge Checklist ✅

- [x] `ADDITIVE_FLOOR_SHIP_SUMMARY.md` explicitly states the conditional-draw tradeoff
  - ⚠️ Warning added: "Turning on additive floor changes the RNG draw schedule, so trajectories are NOT pairwise comparable by seed across configs"
- [x] rng_guard whitelist change has justification and "why now"
  - Explained: Heavy-tail PR changed to exact match, exposing substring-match loophole
  - Confirmed: `_sample_commitment_delays_for_treatment` is legitimate (biological variability during treatment)
- [x] pipeline_transform semantics verified in code and described accurately
  - Inspected run_context.py: Confirmed software feature extraction (segmentation bias, affine transforms, NOT detector gain)
- [x] Recommended sigma ranges included with tuning guidance
  - Conservative/Moderate/Aggressive ranges documented
  - Per-channel tuning rationale provided

## MERGE ✅

All tests pass. Golden preserved. RNG guard is safe. Documentation complete.

**Ship it.**
