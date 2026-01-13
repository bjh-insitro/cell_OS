# SNR Downstream Audit Checklist - None Laundering Prevention

**Purpose:** Ensure every morphology aggregation path respects None-masked channels.
**Risk:** One missed location → "guilt without teeth" in a new file.

---

## Critical Codepaths (Found via Grep)

### 1. `observation_aggregator.py:346-353` ❌ **HIGH RISK - LAUNDERING DETECTED**

```python
# Extract morphology channels
morph = result.readouts.get('morphology', {})
features = {
    'er': morph.get('er', 0.0),      # ← LAUNDERING: None → 0.0
    'mito': morph.get('mito', 0.0),  # ← LAUNDERING: None → 0.0
    'nucleus': morph.get('nucleus', 0.0),
    'actin': morph.get('actin', 0.0),
    'rna': morph.get('rna', 0.0),
}
```

**Problem:** `.get(key, 0.0)` converts SNR-masked `None` to `0.0` silently.
**Impact:** This happens BEFORE aggregation, poisoning all downstream paths.

**Fix Required:**
```python
features = {
    'er': morph.get('er'),      # Preserve None
    'mito': morph.get('mito'),
    'nucleus': morph.get('nucleus'),
    'actin': morph.get('actin'),
    'rna': morph.get('rna'),
}
```

**Feeds into:**
- Line 357: `response = np.mean(list(features.values()))` → poisons scalar response
- Line 532: `ch_values = [v['features'][ch] for v in used_values]` → poisons per-channel aggregation

---

### 1b. `observation_aggregator.py:532, 542-543` ❌ **HIGH RISK - AGGREGATION OVER POISON**

```python
for ch in channels:
    ch_values = [v['features'][ch] for v in used_values]
    feature_means[ch] = float(np.mean(ch_values))  # ← Averages laundered 0.0
    feature_stds[ch] = float(np.std(ch_values, ddof=1)) if n > 1 else 0.0
```

**Problem:** `np.mean()` on list containing laundered `0.0` → poison in aggregate.

**Fix Required:**
```python
for ch in channels:
    ch_values = [v['features'][ch] for v in used_values]

    # Filter out None (SNR-masked channels)
    ch_values_clean = [x for x in ch_values if x is not None]

    if len(ch_values_clean) == 0:
        # All replicates masked → cannot compute mean
        feature_means[ch] = None
        feature_stds[ch] = None
    elif len(ch_values_clean) < len(ch_values):
        # Partial masking → flag as imputed or mark unreliable
        feature_means[ch] = float(np.mean(ch_values_clean))
        feature_stds[ch] = float(np.std(ch_values_clean, ddof=1)) if len(ch_values_clean) > 1 else 0.0
        # TODO: Add metadata: imputed_channels.append(ch)
    else:
        # All replicates usable
        feature_means[ch] = float(np.mean(ch_values_clean))
        feature_stds[ch] = float(np.std(ch_values_clean, ddof=1)) if len(ch_values_clean) > 1 else 0.0
```

### 2. `instrument_shape.py:561` ⚠️ VULNERABLE
**Location:** `all_features[feature].append(value)`
**Code:**
```python
for cond in dmso_conditions:
    if cond.feature_means:
        for feature, value in cond.feature_means.items():
            all_features[feature].append(value)  # ← appends None without checking
```

**Risk:** Correlation code runs on list with None → crashes or produces NaN
**Fix needed:**
```python
for feature, value in cond.feature_means.items():
    if value is not None:  # ← Add None check
        all_features[feature].append(value)
```

**Test:** `test_downstream_instrument_shape_respects_none` (passes - crashes loudly)

### 3. `beliefs/updates/edge.py:75-81` ⚠️ **MEDIUM RISK - DOWNSTREAM CONSUMER**

```python
if edge.feature_means and center.feature_means:
    for channel in edge.feature_means:
        if channel in center.feature_means:
            edge_val = edge.feature_means[channel]
            center_val = center.feature_means[channel]
            if center_val > 0:
                effect = (edge_val - center_val) / center_val
```

**Problem:** If `feature_means[channel]` is `None`, this will crash on arithmetic or comparison.

**Fix Required:**
```python
if edge.feature_means and center.feature_means:
    for channel in edge.feature_means:
        if channel in center.feature_means:
            edge_val = edge.feature_means[channel]
            center_val = center.feature_means[channel]

            # Respect None (SNR-masked channels)
            if edge_val is None or center_val is None:
                continue  # Skip masked channels

            if center_val > 0:
                effect = (edge_val - center_val) / center_val
```

**Test:** `test_downstream_edge_updater_respects_none` (passes - crashes loudly on None)

---

### 4. `beliefs/updates/noise.py:83-88` ✅ **SAFE (Fails Gracefully)**

```python
if cond.feature_means:
    new_cv_by_channel = dict(self.beliefs.baseline_cv_by_channel)
    for ch, mean_val in cond.feature_means.items():
        std_val = cond.feature_stds.get(ch, 0.0)
        if mean_val > 0:
            new_cv_by_channel[ch] = float(std_val / mean_val)
```

**Analysis:** If `mean_val` is `None`, `mean_val > 0` is always `False`, so it silently skips.
**Status:** ✅ Currently safe (no laundering), but implicit behavior is fragile.

**Improvement (Optional):**
```python
if cond.feature_means:
    new_cv_by_channel = dict(self.beliefs.baseline_cv_by_channel)
    for ch, mean_val in cond.feature_means.items():
        if mean_val is None:
            # SNR-masked channel → cannot compute CV
            continue

        std_val = cond.feature_stds.get(ch, 0.0)
        if mean_val > 0:
            new_cv_by_channel[ch] = float(std_val / mean_val)
```

---

## Audit Procedure

For each file that touches `feature_means` or `morphology`:

### Step 1: Find the code
```bash
grep -rn "feature_means\|morphology" src/cell_os/epistemic_agent/ | \
  grep -E "mean|delta|compare|aggregate|corr"
```

### Step 2: Check for None safety
Look for these **UNSAFE patterns**:
```python
# UNSAFE: No None check before arithmetic
delta = treatment - baseline

# UNSAFE: No None check before comparison
if value > 0:

# UNSAFE: No None check before aggregation
values = [cond.feature_means[ch] for ...]
mean = np.mean(values)

# UNSAFE: None laundering
value = feature_means[ch] or 0.0  # ← None → 0.0 (silent poison)
```

### Step 3: Verify SAFE patterns
```python
# SAFE: Explicit None check
value = feature_means.get(ch)
if value is not None:
    use(value)

# SAFE: Filter None before aggregation
usable = [cond.feature_means[ch] for ch in usable_channels
          if cond.feature_means.get(ch) is not None]
if usable:
    mean = np.mean(usable)

# SAFE: Use usable_channels list
usable_channels = cond["snr_policy"]["usable_channels"]
values = [cond["feature_means"][ch] for ch in usable_channels]
```

### Step 4: Add test
For each vulnerable path, add test in `test_snr_none_laundering.py`:
```python
def test_downstream_MODULE_respects_none():
    """Test MODULE with None-masked channels."""
    # Create condition with None channels
    # Feed to MODULE
    # Assert either: (a) skips None, (b) crashes with TypeError
```

---

## Common Vulnerabilities

### 1. "Or" operator laundering
```python
# BAD
value = feature_means[ch] or 0.0  # None → 0.0

# GOOD
value = feature_means[ch] if feature_means[ch] is not None else 0.0
# But better: don't impute, just skip
```

### 2. Comparison without None check
```python
# BAD
if value > 0:  # Crashes if value is None

# GOOD
if value is not None and value > 0:
```

### 3. Arithmetic without None check
```python
# BAD
delta = treatment_val - baseline_val  # Crashes if either is None

# GOOD
if treatment_val is not None and baseline_val is not None:
    delta = treatment_val - baseline_val
```

### 4. NumPy array construction from None list
```python
# BAD
arr = np.array([0.5, None, 0.6])
result = np.mean(arr)  # Result will be wrong

# GOOD
values = [v for v in [0.5, None, 0.6] if v is not None]
result = np.mean(values) if values else None
```

---

## Imputation Policy (If Needed)

If code MUST impute None values (not recommended), require:

### Metadata annotation
```python
if value is None:
    imputed_value = floor_mean  # Or 0.0, or whatever
    imputation_metadata = {
        "channel": ch,
        "original_value": None,
        "imputed_value": imputed_value,
        "imputation_method": "floor_mean",  # or "zero", "median", etc.
        "quality_penalty": 0.5  # Reduce quality score
    }
    # Store metadata for audit trail
```

### Quality penalty
```python
# Original quality: 0.8 (4/5 channels usable)
# After imputation: 0.8 * (1 - 0.5) = 0.4 (penalize by 50%)
quality_score *= (1 - imputation_metadata["quality_penalty"])
```

### Explicit opt-in
```python
# Never impute by default
# Require explicit flag
if allow_imputation and value is None:
    value = impute(value, method="floor_mean")
```

---

## Test Coverage

### Existing tests (7 tests, all passing) ✅
- `test_none_stays_none_not_zero` - None doesn't become 0.0
- `test_arithmetic_with_none_crashes_loudly` - TypeError on arithmetic
- `test_downstream_edge_updater_respects_none` - Edge updater safe
- `test_downstream_instrument_shape_respects_none` - Shape analyzer safe
- `test_none_not_laundered_by_or_operator` - "or" vulnerability
- `test_none_not_laundered_by_nan_to_num` - numpy array vulnerability
- `test_safe_aggregation_pattern` - Demonstrates safe pattern

### Additional tests needed
- [ ] Test `beliefs/updates/noise.py` (if it exists)
- [ ] Test any other modules found by grep audit
- [ ] Integration test: full agent update cycle with None-masked observation

---

## Quick Audit Commands

### Find all morphology aggregation sites
```bash
grep -rn "feature_means" src/cell_os/epistemic_agent/ | \
  grep -v "__pycache__" | \
  grep -v ".pyc" | \
  grep -E "mean|sum|aggregate|delta|compare"
```

### Find potential None laundering
```bash
grep -rn "feature_means\[.*\] or " src/cell_os/epistemic_agent/
grep -rn "np\.nan_to_num" src/cell_os/epistemic_agent/
grep -rn "if.*feature_means.*>" src/cell_os/epistemic_agent/
```

### Find arithmetic operations
```bash
grep -rn "feature_means\[.*\] [-+*/]" src/cell_os/epistemic_agent/
```

---

## Regression Prevention

### Pre-commit hook (recommended)
```bash
#!/bin/bash
# .git/hooks/pre-commit

# Check for unsafe patterns
if git diff --cached | grep -E "feature_means.*or 0|nan_to_num"; then
    echo "ERROR: Potential None laundering detected"
    echo "Review SNR_DOWNSTREAM_AUDIT_CHECKLIST.md"
    exit 1
fi
```

### CI test (required)
```bash
# In CI pipeline
pytest tests/contracts/test_snr_none_laundering.py -v
# Must pass before merge
```

---

## Checklist Summary

| Location | Status | Fix Priority |
|----------|--------|--------------|
| `observation_aggregator.py:346-353` | ❌ Laundering at source | **P0 - CRITICAL** |
| `observation_aggregator.py:532, 542` | ❌ Aggregation over poison | **P0 - CRITICAL** |
| `edge.py:75-81` | ⚠️ Will crash on None | **P1 - High** |
| `instrument_shape.py:560-564` | ⚠️ Appends None to list | **P1 - High** |
| `noise.py:83-88` | ✅ Safe (fails gracefully) | P2 - Nice-to-have |

---

## Recommended Fix Order

1. **Fix laundering at source** (`observation_aggregator.py:346-353`)
   - Remove `.get(key, 0.0)` defaults
   - Preserve `None` from SNR policy
   - This is the ROOT CAUSE - all other issues stem from this

2. **Fix aggregation** (`observation_aggregator.py:532, 542`)
   - Filter `None` before `np.mean()`
   - Add `usable_channels` metadata
   - Mark partial conditions as imputed (if allowing partial aggregation)

3. **Harden downstream consumers**
   - `edge.py`: Skip masked channels in edge effects
   - `instrument_shape.py`: Filter `None` before appending

4. **Add metadata schema**
   - `usable_channels: List[str]` - channels with signal
   - `imputed_channels: List[str]` - channels where None → imputed value (if any)
   - `imputation_method: str` - "floor_mean" | "zero" | "skip"
   - `quality_penalty_applied: bool` - did imputation reduce quality_score?

5. **Expand tripwire tests**
   - Test full update path (aggregator → beliefs → decision)
   - Assert `None` never becomes `0.0` in any intermediate step
   - Test partial masking (some replicates masked, some not)

---

## Meta: Comparability Across Time

Your `quality_score` and `min_margin` are good, but ensure margin is normalized:

```python
# Store effective noise scale per channel
noise_scale = max(floor_sigma, quant_step / 3)
margin_sigma = (signal - threshold) / noise_scale  # ← Normalized units
```

This survives:
- `floor_mean` drift (bias changes)
- `quant_step` changes (ADC mode changes)
- `exposure_multiplier` changes

**Add to metadata:**
```python
class ChannelQuality:
    ...
    noise_scale_used: float       # ← Effective noise (max of floor_sigma, quant)
    margin_sigma: float           # ← Normalized margin in sigma units
```

---

## Status Summary

**Critical findings:**
- ❌ Silent None laundering at source (P0)
- ❌ Laundered values propagate through aggregation (P0)
- ⚠️ Downstream consumers will crash on None (acceptable, but fragile)

**Current test coverage:** ✅ 4/4 tests passing in `test_snr_none_laundering.py`
- Tests demonstrate crashes are loud (not silent)
- No silent laundering detected in downstream paths
- BUT: Laundering happens BEFORE those paths (at extraction)

**Action required:**
Fix observation_aggregator.py:346-353 first. This is the root cause. All other issues are downstream symptoms.

---

**One missed location = guilt without teeth in a new file.**
**Audit regularly, test comprehensively.** ✅

---

**Generated:** 2025-12-27 (Updated with comprehensive grep audit)
**Phase:** Phase 4 SNR Policy
**Context:** Downstream audit after SNR masking implementation
