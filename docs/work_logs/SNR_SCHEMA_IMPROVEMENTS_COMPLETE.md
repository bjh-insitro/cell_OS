# SNR Schema Improvements - Machine-Readable + Channel Masking

**Date:** 2025-12-27
**Status:** ✅ Complete
**Test suite:** 29/29 tests passing

---

## Summary of Improvements

Based on hostile review feedback, two critical improvements were made to prevent the SNR policy from becoming "guilt without teeth":

1. **Machine-readable schema** - Numeric fields alongside human-readable warnings
2. **Channel masking** - Dim channels set to None in lenient mode (prevents learning from poison)

---

## Problem 1: Prose-Heavy Schema

**Before:** Warnings were strings, agents had to parse English
```json
{
  "warnings": ["er: Signal 0.28 AU is below 5.0σ threshold (floor: 0.26 ± 0.03 AU)"]
}
```

**After:** Numeric fields enable analytics
```json
{
  "warnings": ["er: Signal 0.28 AU is below..."],  // Keep for humans
  "per_channel": {
    "er": {
      "signal": 0.28,
      "floor_mean": 0.26,
      "floor_sigma": 0.03,
      "quant_step": 0.015,
      "threshold": 0.41,
      "dominant_noise": "gaussian",
      "is_above": false,
      "margin": -0.13  // How far below threshold
    }
  },
  "n_dim_channels": 2,
  "quality_score": 0.6,
  "min_margin": -0.13,
  "usable_channels": ["nucleus", "actin", "rna"],
  "masked_channels": ["er", "mito"]
}
```

**Why it matters:**
- Agent can track margins across cycles (detector degradation)
- Agent can compute quality scores without regex
- Agent can identify most conservative channel (min margin)
- Analytics over cycles don't require parsing English

---

## Problem 2: "Guilt-Labeled Poison"

**Before:** Lenient mode warned but didn't mask
```python
# Agent saw:
feature_means = {'er': 0.28, 'mito': 0.28, ...}  # ← poisoned data
warnings = ["er below threshold", ...]            # ← guilt label

# Agent could still compute:
mean_morphology = np.mean(list(feature_means.values()))  # ← WRONG
# → 0.28 (includes dim channels)
```

**After:** Dim channels are masked (set to None)
```python
# Agent sees:
feature_means = {'er': None, 'mito': None, 'nucleus': 0.60, ...}  # ← dim channels unusable
usable_channels = ['nucleus', 'actin', 'rna']                      # ← explicit list
masked_channels = ['er', 'mito']                                   # ← explicit list

# Agent must compute:
usable_values = [feature_means[ch] for ch in usable_channels if feature_means[ch] is not None]
mean_morphology = np.mean(usable_values)  # ← CORRECT
# → 0.643 (only usable channels)
```

**Why it matters:**
- Without masking: "Add warning label to poison, agent still drinks it"
- With masking: "Remove poison from bottle, agent can't drink it"

---

## New Schema (Complete)

### Observation-level summary
```json
{
  "snr_policy_summary": {
    "enabled": true,
    "threshold_sigma": 5.0,
    "strict_mode": false,
    "mask_dim_channels": true,
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
  "feature_means": {
    "er": null,      // ← Dim channel masked
    "mito": null,    // ← Dim channel masked
    "nucleus": 0.60, // ← Bright channel preserved
    "actin": 0.65,
    "rna": 0.68
  },
  "snr_policy": {
    "enabled": true,
    "threshold_sigma": 5.0,
    "strict_mode": false,
    "is_valid": true,  // Lenient mode: agent decides

    // Human-readable (keep for debugging)
    "warnings": [
      "er: Signal 0.28 AU is below 5.0σ threshold (floor: 0.26 ± 0.03 AU, threshold: 0.41 AU, dominant noise: gaussian)",
      "mito: Signal 0.28 AU is below..."
    ],

    // Machine-readable (agent uses this)
    "per_channel": {
      "er": {
        "signal": 0.28,
        "floor_mean": 0.26,
        "floor_sigma": 0.03,
        "quant_step": 0.015,
        "threshold": 0.41,
        "dominant_noise": "gaussian",
        "is_above": false,
        "margin": -0.13
      },
      // ... other channels
    },

    // Aggregate metrics
    "n_dim_channels": 2,
    "n_total_channels": 5,
    "quality_score": 0.6,  // (5-2)/5 = 0.6
    "min_margin": -0.13,    // Most conservative channel

    // Explicit channel lists
    "usable_channels": ["nucleus", "actin", "rna"],
    "masked_channels": ["er", "mito"]
  }
}
```

---

## Agent Usage Patterns

### Pattern 1: Compute safe morphology deltas
```python
# Get usable channels from both conditions
baseline_usable = set(baseline["snr_policy"]["usable_channels"])
treatment_usable = set(treatment["snr_policy"]["usable_channels"])
safe_channels = baseline_usable & treatment_usable

# Compute delta only from safe channels
deltas = {}
for ch in safe_channels:
    baseline_val = baseline["feature_means"][ch]
    treatment_val = treatment["feature_means"][ch]
    if baseline_val is not None and treatment_val is not None:
        deltas[ch] = treatment_val - baseline_val

mean_delta = np.mean(list(deltas.values()))
```

### Pattern 2: Track detector degradation
```python
# Collect margins across cycles
margin_history = []
for cycle in range(n_cycles):
    obs = observations[cycle]
    for cond in obs["conditions"]:
        for ch, detail in cond["snr_policy"]["per_channel"].items():
            margin_history.append({
                "cycle": cycle,
                "channel": ch,
                "margin": detail["margin"]
            })

# Alert if margins decreasing (detector degrading)
recent_margins = [m["margin"] for m in margin_history if m["cycle"] > n_cycles - 5]
if np.mean(recent_margins) < -0.1:
    print("WARNING: Detector degradation detected")
```

### Pattern 3: Filter proposals by expected quality
```python
# Before running experiment, estimate quality
def estimate_quality(proposal, profile):
    expected_signals = predict_signals(proposal)  # Agent's model

    quality_scores = []
    for cond in expected_signals:
        n_above = sum(1 for ch, sig in cond.items()
                     if profile.is_above_noise_floor(sig, ch)[0])
        quality = n_above / len(cond)
        quality_scores.append(quality)

    return np.mean(quality_scores)

# Reject low-quality proposals
if estimate_quality(proposal, profile) < 0.5:
    print("Proposal likely to produce dim conditions, request more exposure")
```

---

## Test Coverage

### Original tests (5 tests) ✅
- Floor statistics accessible
- is_above_noise_floor guardrail
- Minimum detectable signal
- SNR warnings in apply_calibration
- Disabled when floor not observable

### Integration tests (11 tests) ✅
- Policy enabled/disabled based on floor
- Dim/bright signal rejection/acceptance
- Minimum detectable signals
- Strict/lenient modes
- Filter removes/annotates conditions
- Policy summary

### Hostile tests (8 tests) ✅
- No-peeking invariant (physics-only)
- Aggregation correctness (no leakage)
- Quantization-aware threshold
- Lenient mode loudness

### Channel masking tests (5 tests) ✅ NEW
- `test_lenient_mode_masks_dim_channels` - Dim channels set to None
- `test_lenient_mode_preserves_bright_channels` - Bright channels preserved
- `test_masking_disabled_preserves_all_channels` - Debug mode
- `test_agent_can_compute_usable_morphology_delta` - Safe delta computation
- `test_machine_readable_schema_enables_analytics` - Cross-cycle analytics

**Total: 29 tests, 29 passing** ✅

---

## API Changes

### check_condition_summary()
**Before:** Returns (is_valid, warnings)
**After:** Returns (is_valid, warnings, per_channel_details)

```python
is_valid, warnings, per_channel = policy.check_condition_summary(condition)
```

### filter_observation()
**New parameter:** `mask_dim_channels: bool = True`

```python
filtered = policy.filter_observation(
    obs,
    annotate=True,
    mask_dim_channels=True  # ← NEW: Set dim channels to None
)
```

---

## Behavior Comparison

### Scenario: Condition with 2 dim, 3 bright channels

| Mode | Behavior | feature_means | usable_channels | Agent can learn? |
|------|----------|---------------|-----------------|------------------|
| **Strict** | Reject entire condition | Not in observation | N/A | ❌ No (condition removed) |
| **Lenient + mask** | Keep with masking | `{'er': None, 'mito': None, 'nucleus': 0.60, ...}` | `['nucleus', 'actin', 'rna']` | ✅ Yes (from usable channels only) |
| **Lenient + no mask** | Keep without masking | `{'er': 0.28, 'mito': 0.28, 'nucleus': 0.60, ...}` | `['nucleus', 'actin', 'rna']` | ⚠️ Risky (agent must filter manually) |

**Default:** Lenient + mask (safest for agent autonomy)

---

## Files Modified

### Core implementation
- `src/cell_os/epistemic_agent/snr_policy.py`
  - Added machine-readable per_channel details
  - Added channel masking (set dim channels to None)
  - Added quality_score, min_margin, usable/masked lists
  - Changed return signature: (is_valid, warnings) → (is_valid, warnings, per_channel)

### Tests
- `tests/contracts/test_snr_channel_masking.py` (NEW, 5 tests)
  - Demonstrates masking prevents learning from poison
  - Shows agent computes safe morphology deltas
  - Validates machine-readable schema enables analytics
- `tests/contracts/test_snr_policy_hostile.py` (updated signatures)
- `tests/contracts/test_snr_policy_integration.py` (updated signatures)

---

## Key Insight

**Before:** "Add warning label to poison, hope agent doesn't drink it"
```python
# Lenient mode (before):
feature_means = {'er': 0.28, ...}  # ← agent sees dim values
warnings = ["er below threshold"]  # ← guilt label
# Agent might still compute mean(feature_means.values()) ← WRONG
```

**After:** "Remove poison from bottle, agent physically can't drink it"
```python
# Lenient mode (after):
feature_means = {'er': None, ...}        # ← dim values masked
usable_channels = ['nucleus', 'actin']   # ← explicit safe list
# Agent must compute mean([feature_means[ch] for ch in usable_channels]) ← CORRECT
```

---

## Conclusion

The SNR policy is now **machine-readable** and has **teeth**:

1. ✅ **No parsing required** - Numeric fields, not prose
2. ✅ **No learning from poison** - Dim channels physically masked
3. ✅ **Cross-cycle analytics** - Track margins, quality, degradation
4. ✅ **Explicit channel lists** - usable_channels, masked_channels
5. ✅ **Quality-aware decisions** - Filter proposals by expected quality

**The schema is shaped for agent decisions, not moral theater.** ✅

---

**All 29 tests passing.** Ready for production.
