# ADC Quantization: FINAL SHIP SUMMARY

## What Was Added

**Feature:** ADC quantization (analog-to-digital conversion) for Cell Painting assays (deterministic discretization).

**Purpose:** Models digitizer bit depth. Removes arbitrarily fine decimal precision that doesn't exist in real detectors. Creates visible banding at low signal, bin merging near saturation, and dead zones where signal changes don't affect output. **Completes the "honest detector" stack.**

---

## Test Results (All Pass)

| Test | Status | Time | What It Proves |
|------|--------|------|----------------|
| Fast contract tests (quantization behavior) | ✅ 10/10 PASS | 4.5s | Dormant no-op, step lattice, half-up rounding, bits-mode, ValueError on config error, idempotence, monotone, saturation interaction, end-to-end, visible banding |
| Golden contract (full epistemic loop) | ✅ 3/3 PASS | 0.83s | Schema, invariants, causal contracts preserved |

---

## Key Implementation Decisions

### 1. Dual-Mode Quantization (Step vs Bits)

**Choice:** Support both explicit `step` and `bits+ceiling` modes

**Priority order:**
1. **Bits-mode** (realistic): If `bits > 0` and `ceiling > 0`, derive `step = ceiling / (2^bits - 1)`
   - Example: 12-bit with 800 AU ceiling → step ≈ 0.2 AU (4095 codes)
   - **Raises ValueError** if `bits > 0` but `ceiling <= 0` (explicit contract violation, no silent fallback)
2. **Step-mode** (direct control): If `step > 0`, use explicit step size
   - Example: step=0.5 → quantize to 0.5 AU bins
3. **Dormant**: If `bits=0` and `step=0.0` → no-op (golden-preserving)

**Rationale:**
- Bits-mode is realistic (matches hardware specs: "12-bit ADC")
- Step-mode is debuggable (direct control: "quantize to 0.5 AU bins")
- Raising on config error prevents silent placebo (bits enabled but ceiling forgot to enable saturation)

**Alternative rejected:** Silent fallback to dormant when bits>0 but ceiling=0 - creates "quantization enabled" placebo

### 2. Round Half-Up (Not Banker's Rounding)

**Choice:** Implement `floor(y/step + 0.5) * step` (explicit half-up)

**Rationale:**
- Avoids Python `round()` banker's rounding (ties to even)
- Symmetric and predictable
- Matches most ADC behavior
- Tested explicitly: `quantize(0.5, step=1.0) == 1.0` (not 0.0)

### 3. Deterministic (No RNG)

**Choice:** Quantization uses NO randomness - pure function of (y, step/bits, ceiling)

**Rationale:**
- ADC conversion is electronics (deterministic)
- Measurement noise comes from other sources (additive floor, heavy-tail shocks)
- Simplifies testing (no statistical soup)
- No new RNG whitelist entries needed

### 4. Insertion Point: After Saturation, Before Pipeline Transform

**Choice:** Apply quantization as step 9 in measurement pipeline

**Measurement stack order:**
```
1. Viability factor (biological signal attenuation)
2. Washout multiplier (measurement artifact)
3. Debris background (fluorescence contamination)
4. Biological noise (dose-dependent lognormal)
5. Plating artifacts (early timepoint variance inflation)
6. Technical noise (plate/day/operator/well/edge effects)
7. Additive floor (detector read noise, stochastic)
8. Saturation (detector dynamic range, deterministic)
9. Quantization (ADC digitization, deterministic) ← NEW
10. Pipeline drift (software feature extraction)
```

**Rationale:**
- Saturation is analog compression (photon well depth)
- Quantization is digital conversion (ADC)
- Pipeline_transform is software post-processing (feature extraction)
- Physical order: analog → digital → software

### 5. Ceiling Source: Reads from Saturation Config

**Choice:** Quantization reads `saturation_ceiling_{ch}` for bits-mode

**Rationale:**
- Saturation ceiling IS the analog full-scale (photon well depth)
- ADC full-scale should match analog full-scale (realistic)
- No duplicate config
- **Explicit contract:** If bits>0 but ceiling=0, raises ValueError (no silent fallback)

**Consequence:** Bits-mode requires saturation to be enabled on same channel. This coupling is intentional and explicit.

### 6. Shared Defaults + Per-Channel Overrides

**Choice:** Shared `bits_default` + `step_default` with optional per-channel overrides

**Config structure:**
```yaml
adc_quant_bits_default: 0        # Shared (all channels, dormant)
adc_quant_step_default: 0.0      # Shared (all channels, dormant)
adc_quant_bits_er: 0             # Per-channel override (optional)
adc_quant_step_mito: 0.0         # Per-channel override (optional)
```

**Rationale:**
- Most users want same bit depth for all channels (simple)
- Per-channel overrides allow realism (e.g., nucleus has better ADC)
- Minimal config surface

### 7. Dormant Defaults (Golden-Preserving)

**Choice:** All params default to 0 (quantization disabled)

**Rationale:**
- Preserves existing golden files
- Feature can be enabled explicitly for realism runs
- Deterministic: no-op when dormant (not stochastic)

---

## What Changed vs What Didn't

| Component | Changed? | Evidence |
|-----------|----------|----------|
| Biology trajectories | ❌ NO | Golden test passes (bits=0, step=0.0 default) |
| Measurement determinism (dormant) | ❌ NO | Same seed → same output |
| Contract compliance | ❌ NO | Golden test passes |
| RNG guard | ❌ NO | No new whitelist entries (quantization is deterministic) |
| Cell Painting noise stack | ✅ YES | Added quantization layer (step 9) |
| Measurement pipeline | ✅ YES | New step between saturation and pipeline_transform |

---

## Configuration

**Default (Dormant):**
```yaml
technical_noise:
  # ADC quantization disabled (both modes dormant)
  adc_quant_bits_default: 0
  adc_quant_step_default: 0.0
  adc_quant_rounding_mode: "round_half_up"
```

**Enable for realism (requires saturation ceilings enabled):**
```python
# Enable saturation first (quantization needs ceilings for bits-mode)
vm.thalamus_params['technical_noise']['saturation_ceiling_er'] = 600.0
vm.thalamus_params['technical_noise']['saturation_ceiling_mito'] = 700.0
vm.thalamus_params['technical_noise']['saturation_ceiling_nucleus'] = 800.0
vm.thalamus_params['technical_noise']['saturation_ceiling_actin'] = 600.0
vm.thalamus_params['technical_noise']['saturation_ceiling_rna'] = 650.0

# Then enable quantization (bits-mode)
vm.thalamus_params['technical_noise']['adc_quant_bits_default'] = 12  # Moderate realism
```

**Tuning guidance (baseline ~150 AU, ceiling ~600-800 AU):**

| Bit Depth | Codes | Step (ceiling=600) | Step (ceiling=800) | Visibility | Use Case |
|-----------|-------|-------------------|-------------------|------------|----------|
| 16-bit | 65535 | ~0.009 AU | ~0.012 AU | Invisible | Overkill, effectively continuous |
| 12-bit | 4095 | ~0.15 AU | ~0.20 AU | Subtle | **Moderate realism (typical cameras)** ← Recommend |
| 10-bit | 1023 | ~0.59 AU | ~0.78 AU | Visible at low signal | Aggressive realism |
| 8-bit | 255 | ~2.35 AU | ~3.14 AU | **Banding visible** | Very aggressive (cheap cameras) |

**Alternative: Explicit step mode (no ceiling needed):**
```python
# Use explicit step (no saturation required)
vm.thalamus_params['technical_noise']['adc_quant_step_default'] = 0.5  # Quantize to 0.5 AU bins
```

---

## Design Properties

1. **Monotone** (preserves order within float precision)
   - y1 > y2 → y_q(y1) >= y_q(y2)
   - No rank reversals due to quantization

2. **Idempotent** (applying twice = applying once)
   - quantize(quantize(y)) == quantize(y)
   - Quantization is a projection onto discrete lattice

3. **Bounded** (respects ceiling)
   - 0 <= y_q <= ceiling (when ceiling provided)
   - Defensive clamping before quantization

4. **Deterministic** (no RNG)
   - Same (y, params) → same y_q every time
   - Reproducible, testable, debuggable

5. **Golden-preserving** (dormant when bits=0, step=0.0)
   - Feature disabled by default
   - No behavior change in existing tests

6. **Explicit failure on config error**
   - Raises ValueError if bits>0 but ceiling<=0
   - Prevents silent placebo ("I enabled quantization but nothing happened")

---

## Epistemic Implications (The Uncomfortable Parts)

### 1. Fake Precision Removed

**Effect:** Signal values are discretized into bins

**Consequences:**
- Agent cannot distinguish y=100.2 from y=100.3 if step=0.5 (both → 100.0)
- Sub-LSB differences vanish (information loss)
- "4th decimal place tea leaves" strategy breaks

**Learning pressure:** Agent must recognize that fine-grained signal differences may not be real

### 2. Dead Zones (Plateaus Where Nudging Has No Effect)

**Effect:** Small signal changes don't change digitized output

**Consequences:**
- Agent nudges condition, analog signal changes by 0.1 AU, but digitized output unchanged
- Gradients vanish locally
- Plateau feels like "nothing is happening" (but it is, detector just can't see it)

**Learning pressure:** Agent must learn when it's operating in quantization-limited regime

### 3. Visible Banding at Low Signal

**Effect:** Coarse steps at low intensities (step is large fraction of signal)

**Consequences:**
- At y~10 AU with step~2.5 AU (8-bit), signal jumps in discrete levels
- Looks "chunky" not smooth
- Increases apparent variance (neighboring wells hop between bins due to noise)

**Learning pressure:** Agent must recognize low-signal unreliability (both noisy AND coarse)

### 4. Bin Merging Near Saturation

**Effect:** Multiple analog values → same digital code

**Consequences:**
- At ceiling with 8-bit (step~3 AU), inputs differing by <3 AU indistinguishable
- Saturation + quantization compound to create plateau
- High-dose compounds look similar

**Learning pressure:** Agent must avoid saturation + quantization double-whammy (operate below knee)

⚠️ **Warning for Calibration:** Quantization removes information. Two wells with true signals 100.2 AU and 100.7 AU may both quantize to 100.0 AU (indistinguishable). Naive inference that treats measurements as continuous will be overconfident. This is REALISTIC (real ADCs behave this way) but can mislead agents that don't model discretization.

---

## Noise Stack (Complete "Honest Detector" Story)

```
Cell Painting measurement pipeline:
1. Deterministic signal formation (biology → stress → channel response)
2. Viability/washout/debris factors (biological attenuation)
3. Biological noise (lognormal base + heavy_tail_shock overlay)
4. Plating artifacts (post-dissociation stress decay)
5. Technical noise (multiplicative lognormal)
6. Well failures (rare, correlated across channels)
7. Additive floor (detector read noise, Gaussian) ← Low-signal regime
8. Saturation (detector dynamic range, soft knee) ← High-signal regime
9. Quantization (ADC bit depth, discrete levels) ← ALL signals ← NEW
10. Pipeline drift (software feature extraction bias)
11. Return morphology dict
```

### Four-Pillar Measurement Realism Stack (Complete)

| Pillar | Distribution | When Applied | Regime | Purpose |
|--------|--------------|--------------|--------|---------|
| **Heavy-tail shocks** | Student-t exp(t), clipped [0.2, 5.0] | Step 3 (biological noise) | Rare (1%) | Lab outliers (bubbles, contamination) |
| **Additive floor** | Normal(0, σ), clamped ≥0 | Step 7 (after multiplicative noise) | Low signal | Detector read noise (dark current) |
| **Saturation** | Deterministic soft knee | Step 8 (after additive floor) | High signal | Dynamic range limits (well depth, ADC max analog) |
| **Quantization** | Deterministic round_half_up | Step 9 (after saturation) | **ALL signals** | Digitization (removes fake precision) |

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

→ quantization(599.7, bits=12, ceiling=600.0) = 599.80 AU (12-bit: step≈0.15 AU)
   Final output: 599.80 AU (discrete, not 599.7123456...)
```

All four pillars are **measurement-only** (observer independence preserved).

---

## Verification Commands

```bash
# 1. Fast contract tests (quantization behavior)
python3 -m pytest tests/contracts/test_quantization_fast.py -xvs
# Expected: 10/10 pass, ~4.5s

# 2. Golden contract test (full epistemic loop)
python3 -m pytest tests/integration/test_golden_seed42_contract_regression.py -xvs
# Expected: 3/3 pass, ~0.8s
```

---

## Files Modified

### Core Implementation
- `src/cell_os/hardware/_impl.py` - Added `quantize_adc()` primitive (deterministic, no RNG, dual-mode, raises on config error)
- `src/cell_os/hardware/assays/cell_painting.py` - Added `_apply_adc_quantization()` method, wired into pipeline (step 9)
- `data/cell_thalamus_params.yaml` - Added 3 parameters (bits, step, mode - all dormant by default)

### Tests
- `tests/contracts/test_quantization_fast.py` - NEW: 10 contract tests (dormant no-op, step lattice, half-up rounding, bits-mode, ValueError, idempotence, monotone, saturation interaction, end-to-end, visible banding)

---

## Test Coverage

### test_quantization_dormant_default_noop
- Verifies bits=0, step=0.0 → no-op (golden-preserving)
- Tests primitive directly with various inputs

### test_quantization_step_lattice
- Verifies outputs are multiples of step (lattice structure)
- Tests explicit step-mode

### test_quantization_half_up_rounding
- Verifies round-half-up behavior (not banker's rounding)
- Explicit test: 0.5 → 1.0, 1.5 → 2.0, 2.5 → 3.0

### test_quantization_bits_mode_with_ceiling
- Verifies bits-mode derives step correctly from ceiling
- Tests 8-bit with ceiling=800 (step≈3.14 AU)

### test_quantization_bits_mode_requires_ceiling
- Verifies ValueError raised when bits>0 but ceiling<=0
- Tests explicit failure mode (no silent fallback)

### test_quantization_idempotence
- Verifies quantize(quantize(y)) == quantize(y)
- Tests multiple inputs

### test_quantization_monotone
- Verifies y1 > y2 → y_q(y1) >= y_q(y2)
- Tests ordered sequence

### test_quantization_with_saturation_interaction
- Verifies quantization handles saturated inputs correctly
- Tests ceiling boundary case (quantize(ceiling) == ceiling)

### test_quantization_end_to_end_measurement
- Verifies no crash in full Cell Painting pipeline
- Tests dormant mode in real workflow

### test_quantization_visible_banding_at_low_signal
- Verifies banding at low signal (coarse steps)
- Tests that consecutive inputs can map to same output

---

## What You Just Accomplished

Completed the "honest detector" four-pillar realism stack:

✅ Quantization is **measurement-only** (no vessel state mutation)
✅ Quantization is **deterministic** (no RNG, pure function)
✅ Golden-preserving when dormant (bits=0, step=0.0)
✅ Dual-mode (bits+ceiling OR explicit step)
✅ Raises on config error (bits>0 but ceiling=0)
✅ Round half-up (not banker's rounding)
✅ Idempotent and monotone
✅ Golden contract didn't move
✅ No new RNG whitelist entries needed

**The complete "honest detector" stack:**

1. **Low-signal honesty:** Additive floor (dark current, Gaussian noise)
2. **High-signal honesty:** Saturation (photon well depth, soft knee compression)
3. **Rare outliers honesty:** Heavy-tail shocks (lab artifacts, correlated across channels)
4. **Precision honesty:** Quantization (ADC bit depth, removes fake decimals) ← **NEW**

Agents now face genuine detector operation problems across ALL signal regimes:
- **Low signal:** Additive floor dominates (noisy) + quantization shows banding (coarse)
- **Mid signal:** Linear regime (information-rich) but still quantized (discrete)
- **High signal:** Saturation compresses (clipped) + quantization bins merge (plateau)

**You removed the last lie: decimal precision that doesn't exist.**

Agents stop reading tea leaves in imaginary decimal places. Low signal looks coarse and frustrating. High signal looks plateaued and ambiguous. The information-rich middle is the only honest regime.

**A simulator that's easy is usually lying. You made yours harder and more honest.**

---

## Design Notes

### Feature-Level vs Pixel-Level Quantization

**Implementation:** Applied to morphology features (aggregated channel intensities), not pixel-level ADCs.

**Interpretation:** This approximates the effect of digitization on aggregated features. It's not a full image ADC simulation (that would require pixel arrays). It's "feature-level quantization" - a pragmatic approximation.

**Consequence:** pipeline_transform (software feature extraction) happens after quantization, so it can reintroduce fractional values via affine transforms. This is acceptable because pipeline_transform produces "feature space" values, not raw ADC codes.

**Alternative:** For pixel-level ADC realism, quantization would need to happen at image formation (before aggregation). That's a different simulator architecture.

### Coupling to Saturation (Intentional)

**Design:** Bits-mode reads `saturation_ceiling_{ch}` for analog full-scale.

**Consequence:** Enabling bits-mode quantization requires saturation to be enabled on same channel.

**Rationale:** This coupling is intentional and explicit:
- Saturation ceiling IS the analog full-scale (detector physics)
- ADC full-scale should match analog full-scale (engineering reality)
- If you enable bits=12 but forget to set ceiling, you get ValueError (not silent no-op)

**Alternative:** Could add separate `adc_full_scale_{ch}` params (decoupled, more config). Rejected because it duplicates ceiling concept and allows inconsistent configs (saturation ceiling ≠ ADC full-scale).

---

## Next Realism Target (Not This PR)

**Spatial correlation** (already partially implemented):
- Row/column gradients (liquid handler drift during plating)
- Edge well artifacts (evaporation/temperature, already implemented)
- Coating quality heterogeneity (spatial maps for coated plates)

This is structured spatial correlation, not just per-well randomness.

**Alternative:** Background subtraction artifacts (negative values after background correction, requires different noise model).

---

## MERGE ✅

All tests pass. Golden preserved. Deterministic. Raises on config error (no silent fallback). Documentation complete.

**The "honest detector" stack is complete. Ship it.**
