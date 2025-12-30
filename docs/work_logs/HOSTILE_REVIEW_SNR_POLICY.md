# Hostile Review: SNR Policy - Physics Denial Prevention

**Date:** 2025-12-27
**Status:** ✅ All hostile checks passing
**Test suite:** 24/24 tests pass

---

## Summary

The SNR policy implementation survived hostile review focused on preventing "physics denial" bugs - subtle ways the policy could be bypassed, gamed, or accidentally misconfigured to let the agent hallucinate competence.

---

## Hostile Check #1: No-Peeking Invariant ✅

**Attack:** Policy branches on treatment metadata (compound, dose, time) to "cheat" by condition identity.

**Defense implemented:**
- SNRPolicy only receives `(signal: float, channel: str)` - no treatment metadata
- Instrumented test verifies policy never sees compound/dose/time
- Same signal → same verdict regardless of context

**Test:** `test_snr_policy_never_peeks_at_treatment_metadata`
```python
# Policy sees only physics data
assert set(call.keys()) == {'signal', 'channel'}
# ✓ No peeking at compound, dose, time, cell_line, etc.
```

**Test:** `test_snr_policy_deterministic_across_conditions`
```python
# Same signal in different contexts → same verdict
signal=0.35 AU in {"DMSO", "CancerDrug", "Poison"} → all same verdict
# ✓ Policy is context-blind (physics-only)
```

---

## Hostile Check #2: Aggregation Correctness ✅

**Attack:** Rejected conditions leak into downstream aggregates via mixed-channel scalar means.

**Defense implemented:**
- **Strict mode:** Entire condition removed from observation (not just flagged)
- **Lenient mode:** Warnings are structured per-channel, not scalar
- Agent can parse which specific channels failed and by how much

**Test:** `test_strict_mode_rejects_entire_condition_not_channels`
```python
# Condition with 1 dim, 4 bright channels
# Strict mode: REMOVES condition (no leakage)
assert len(filtered["conditions"]) == 0
assert filtered["snr_policy_summary"]["n_conditions_rejected"] == 1
# ✓ No aggregate computed from mixed usable/unusable channels
```

**Test:** `test_per_channel_warnings_machine_readable`
```python
# Warnings are structured: "er: Signal X AU is below Y threshold..."
# Agent can parse: which channels, by how much, threshold value
dim_channels = ["er", "actin"]  # Parsed programmatically
# ✓ Not just log lines nobody reads
```

---

## Hostile Check #3: Quantization-Aware Threshold ✅ (The Killer Bug)

**Attack:** When quantization step >> floor_sigma, policy declares signals "detectable" even when stuck on same ADC code.

**Scenario:**
```python
floor_mean = 0.25 AU
floor_sigma ≈ 0.0 AU (all dark wells same code)
quant_step = 0.05 AU (coarse ADC)

# Bug: threshold = 0.25 + 5*0.0 = 0.25 AU → everything "detectable"
# Reality: signal at 0.26 AU indistinguishable from 0.25 AU (same ADC code)
```

**Defense implemented:**
```python
# Quantization-aware threshold: MAX(k*sigma, 3*quant_step)
gaussian_threshold = 5.0 * floor_sigma   # = 0.0 AU
quantization_threshold = 3.0 * quant_step  # = 0.15 AU
threshold = floor_mean + max(gaussian_threshold, quantization_threshold)
# → threshold = 0.25 + 0.15 = 0.40 AU (quantization dominates)
```

**Test:** `test_quantization_dominates_gaussian_noise`
```python
# Signal at 0.26 AU (1 LSB above floor):
is_above_tiny = False  # ✓ Rejected (stuck in quantization noise)

# Signal at 0.40 AU (3 LSB above floor):
is_above_3lsb = True  # ✓ Accepted (clearly distinguishable)
```

**Test:** `test_quantization_aware_minimum_detectable_signal`
```python
# With floor_sigma=0.003, quant_step=0.05:
# MDS = 0.25 + max(5*0.003, 3*0.05) = 0.40 AU
# ✓ Accounts for coarse ADC, not just tiny Gaussian noise
```

**Diagnostic message includes dominant noise source:**
```
Signal 0.26 AU is below 5.0σ threshold (floor: 0.25 ± 0.00 AU,
threshold: 0.40 AU, dominant noise: quantization)
```

---

## Hostile Check #4: Lenient Mode Loudness ✅

**Attack:** "Warn and proceed" degrades to log lines nobody reads; agent can't use metadata for decisions.

**Defense implemented:**
- Warnings propagate to `qc_struct["snr_policy"]` with structured metadata
- Each condition gets `snr_policy` field with:
  - `is_valid: bool` (True in lenient, agent must decide)
  - `warnings: List[str]` (per-channel details, machine-readable)
  - `threshold_sigma`, `strict_mode` (policy config)
- Observation-level summary: `n_conditions_rejected`, `n_conditions_accepted`

**Test:** `test_lenient_mode_warnings_in_qc_struct`
```python
# Condition-level metadata (per-condition):
cond["snr_policy"] = {
    "is_valid": True,  # Lenient: agent decides
    "warnings": [
        "er: Signal 0.28 AU is below 5.0σ threshold...",
        "mito: Signal 0.28 AU is below 5.0σ threshold...",
        # ... 5 warnings (all channels dim)
    ],
    "threshold_sigma": 5.0,
    "strict_mode": False
}

# Observation-level summary:
obs["snr_policy_summary"] = {
    "n_conditions_rejected": 0,  # Lenient rejects nothing
    "n_conditions_accepted": 1,
    "n_conditions_total": 1
}
```

**Test:** `test_lenient_mode_can_penalize_dim_conditions`
```python
# Agent can compute "SNR quality score" from warnings
quality_score = 1.0 - (n_dim_channels / n_total_channels)

# Results:
# DMSO: quality=0.00 (5/5 dim) → reject or request more exposure
# DrugA: quality=1.00 (0/5 dim) → accept
# DrugB: quality=0.80 (1/5 dim) → accept with caution
```

**Agent can penalize proposals that produce low-quality observations:**
```python
if expected_quality < 0.5:
    # Increase exposure, add replicates, or reject proposal
```

---

## Current qc_struct Schema

### Observation-level summary
```json
{
  "snr_policy": {
    "enabled": true,
    "threshold_sigma": 5.0,
    "strict_mode": false,
    "n_conditions_total": 2,
    "n_conditions_rejected": 0,
    "n_conditions_accepted": 2
  }
}
```

### Condition-level metadata
```json
{
  "compound": "DMSO",
  "dose_uM": 0.0,
  "time_h": 12.0,
  "feature_means": {"er": 0.28, "mito": 0.28, ...},
  "snr_policy": {
    "enabled": true,
    "threshold_sigma": 5.0,
    "strict_mode": false,
    "is_valid": true,
    "warnings": [
      "er: Signal 0.28 AU is below 5.0σ threshold (floor: 0.26 ± 0.03 AU, threshold: 0.41 AU, dominant noise: Gaussian)",
      "mito: Signal 0.28 AU is below 5.0σ threshold (floor: 0.28 ± 0.03 AU, threshold: 0.42 AU, dominant noise: Gaussian)",
      ...
    ]
  }
}
```

**Actionable fields for agent:**
- `is_valid`: Bool flag (lenient mode always true, agent decides)
- `warnings`: List of strings (parseable: channel name, signal, threshold, noise source)
- Can extract: `n_dim_channels`, `quality_score`, `dominant_noise_source`

**This is shaped for agent use, not moral theater.** ✅

---

## Test Summary

### Original tests (5 tests)
- `test_floor_statistics_accessible` ✅
- `test_is_above_noise_floor_guardrail` ✅
- `test_minimum_detectable_signal` ✅
- `test_snr_guardrails_in_apply_calibration` ✅
- `test_snr_guardrail_disabled_when_floor_not_observable` ✅

### Integration tests (11 tests)
- Policy enabled/disabled based on floor observable ✅
- Dim/bright signal rejection/acceptance ✅
- Minimum detectable signals computed correctly ✅
- Strict mode rejects entire conditions ✅
- Lenient mode warns but allows ✅
- Filter removes/annotates conditions ✅
- Policy summary shows configuration ✅

### Hostile tests (8 tests)
1. **No-peeking invariant** (2 tests) ✅
   - Policy uses only calibration + signal
   - Deterministic across contexts
2. **Aggregation correctness** (2 tests) ✅
   - Strict mode removes entire condition
   - Warnings are machine-readable
3. **Quantization-aware threshold** (2 tests) ✅
   - Rejects signals stuck in quantization noise
   - MDS accounts for coarse ADC
4. **Lenient mode loudness** (2 tests) ✅
   - Warnings in qc_struct (structured)
   - Agent can compute quality scores

**Total:** 24 tests, 24 passed ✅

---

## Files Modified

### Core implementation
- `src/cell_os/calibration/profile.py`
  - Added quantization-aware threshold: `max(k*sigma, 3*quant_step)`
  - Updated `is_above_noise_floor()` with dominant noise diagnostic
  - Updated `minimum_detectable_signal()` to respect ADC limits

### Tests
- `tests/contracts/test_snr_policy_hostile.py` (NEW, 8 tests)
  - Hostile checks for physics denial prevention
  - Quantization-aware threshold validation
  - No-peeking invariant
  - Aggregation correctness

---

## Key Fix: Quantization-Aware Threshold

**Before (BUG):**
```python
threshold = floor_mean + k * floor_sigma
# When sigma ≈ 0, threshold ≈ floor_mean → everything "detectable"
```

**After (FIXED):**
```python
gaussian_threshold = k * floor_sigma
quantization_threshold = 3.0 * quant_step
threshold = floor_mean + max(gaussian_threshold, quantization_threshold)
# When quantization dominates, threshold respects ADC limits
```

**Example:**
```
floor_mean = 0.25 AU
floor_sigma = 0.0 AU (all dark wells same code)
quant_step = 0.05 AU

Old: threshold = 0.25 + 5*0.0 = 0.25 AU ❌ (physics denial)
New: threshold = 0.25 + max(0.0, 3*0.05) = 0.40 AU ✅ (respects ADC)

Result:
- Signal 0.26 AU: REJECT (stuck in quantization noise)
- Signal 0.40 AU: ACCEPT (3 LSB above floor, distinguishable)
```

---

## Conclusion

All 4 hostile checks passing:
1. ✅ No-peeking invariant (physics-only, context-blind)
2. ✅ Aggregation correctness (no leakage, structured warnings)
3. ✅ Quantization-aware threshold (respects ADC limits)
4. ✅ Lenient mode loudness (structured for agent decisions)

**The SNR policy is robust against physics denial bugs.**

The system now refuses to learn from noise, respects detector physics (both Gaussian and quantization), and provides actionable metadata for agent decisions.

---

**Hostile review passed.** ✅
**Physics denial prevented.** ✅
**No silent scientific fraud.** ✅
