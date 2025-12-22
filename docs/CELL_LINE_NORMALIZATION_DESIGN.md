# Cell Line Normalization Design

**Date:** December 22, 2024
**Problem:** Cell line baseline differences (77% of variance) dominate treatment effects (5%)
**Goal:** Enable agent to learn mechanism inference by controlling nuisance confounds

---

## Problem Statement

### Empirical Evidence
From variance analysis (CAL_384_RULES_WORLD_v2, seed 42, ER channel):

```
Cell Line Differences:          76.7% ← DOMINATES
Shot Noise (Measurement):       14.7%
Biological Signal (Treatments):  4.7% ← SMALL
Fixation Timing:                 1.6%
Focus Drift:                     1.1%
Cell Density:                    0.9%
```

**Signal-to-noise ratio: 5% signal vs 77% nuisance**

### Root Cause
Cell Painting starts with cell line-specific baselines:
- A549:   ER=100, Mito=150, Nucleus=200, Actin=120, RNA=180
- HepG2:  ER=130, Mito=180, Nucleus=190, Actin=110, RNA=200
- U2OS:   ER=95,  Mito=140, Nucleus=210, Actin=130, RNA=170

Treatment effects are **multiplicative modulations** on top of these baselines:
```python
morph[channel] *= (1.0 + dose_effect * axis_strength)
```

**Example:**
- A549 ER baseline: 100
- HepG2 ER baseline: 130
- Treatment effect: +20% → A549 gets +20, HepG2 gets +26
- Absolute difference: 6 points
- **Baseline difference: 30 points (5× larger!)**

The agent sees absolute values, so cell line identity is a **massive confounder**.

---

## Solution Space: Three Normalization Strategies

### Strategy 1: Baseline Subtraction (Additive Normalization)

**Transform:**
```python
normalized[ch] = raw[ch] - baseline[cell_line][ch]
```

**Properties:**
- ✅ Simplest interpretation: "change from baseline"
- ✅ Preserves treatment effect magnitudes
- ✅ Agent sees Δ directly
- ❌ Loses absolute magnitude information (can't tell A549 from HepG2)
- ❌ Assumes additive effects (biology is often multiplicative)

**Use case:** When treatment effects are small additive shifts (e.g., stain intensity drift)

**Pedagogical value:** LOW - Agent doesn't learn that baseline matters, just sees normalized values

---

### Strategy 2: Fold-Change (Multiplicative Normalization)

**Transform:**
```python
normalized[ch] = raw[ch] / baseline[cell_line][ch]
```

**Properties:**
- ✅ Biologically realistic (multiplicative dose-response)
- ✅ Dimensionless (fold-change = 1.2 means "20% increase")
- ✅ Comparable across cell lines and channels
- ❌ Heteroscedastic noise (high baseline → smaller relative variance)
- ❌ Sensitive to baseline near zero

**Use case:** When treatment effects are proportional to baseline (most morphology effects)

**Pedagogical value:** MEDIUM - Agent learns that effects are relative, but normalization is automatic

---

### Strategy 3: Z-Score Normalization (Standardized Units)

**Transform:**
```python
normalized[ch] = (raw[ch] - mean_vehicle[cell_line][ch]) / std_vehicle[cell_line][ch]
```

**Where:**
- `mean_vehicle[cell_line][ch]`: Mean of vehicle (DMSO) wells for this cell line + channel
- `std_vehicle[cell_line][ch]`: Std dev of vehicle wells (includes biological + technical noise)

**Properties:**
- ✅ Normalizes both mean and variance
- ✅ Makes channels comparable (all in units of "std deviations from vehicle")
- ✅ Agent can compare ER vs Mito directly
- ✅ Learns from data (vehicle wells define baseline)
- ❌ Requires vehicle controls in every experiment
- ❌ Requires multiple vehicle replicates to estimate std
- ❌ Early experiments have poor estimates (cold start problem)

**Use case:** When agent must compare across cell lines AND channels

**Pedagogical value:** HIGH - Agent must include vehicle controls, learns data-driven normalization

---

## Recommended Strategy: **Hybrid Approach**

Use **fold-change normalization** with **pedagogical scaffolding**:

1. **Default mode (training wheels OFF):** No normalization
   - Agent sees raw values
   - Must discover cell line confounding through failed experiments
   - Learns to include matched vehicle controls

2. **Normalized mode (training wheels ON):** Fold-change normalization
   - Agent sees fold-change from baseline
   - Baseline comes from `cell_thalamus_params.yaml` (known ground truth)
   - Reduces variance from 77% → ~5% (removes nuisance)

3. **Pedagogical contract:**
   - Early episodes: raw mode → agent fails due to cell line confounding
   - Agent learns to request normalization OR design matched experiments
   - Later episodes: agent designs experiments robust to cell line effects

---

## Implementation Plan

### Phase 1: Add Fold-Change Normalization (Low Risk)

**Location:** `observation_aggregator.py`

**Changes:**
```python
def _normalize_by_cell_line(
    raw_features: Dict[str, float],
    cell_line: str,
    normalization_mode: Literal["none", "fold_change", "zscore"]
) -> Dict[str, float]:
    """
    Normalize morphology features by cell line baseline.

    Args:
        raw_features: Raw channel values (ER, mito, nucleus, actin, RNA)
        cell_line: Cell line identifier (A549, HepG2, etc.)
        normalization_mode: Normalization strategy

    Returns:
        Normalized features
    """
    if normalization_mode == "none":
        return raw_features.copy()

    # Load baseline from thalamus params
    baseline = get_cell_line_baseline(cell_line)

    if normalization_mode == "fold_change":
        normalized = {}
        for ch, raw_val in raw_features.items():
            baseline_val = baseline.get(ch, 1.0)
            normalized[ch] = raw_val / baseline_val if baseline_val > 0 else raw_val
        return normalized

    elif normalization_mode == "zscore":
        # Requires vehicle statistics (implemented in Phase 2)
        raise NotImplementedError("Z-score normalization requires vehicle stats")

    else:
        raise ValueError(f"Unknown normalization mode: {normalization_mode}")
```

**Integration point:** In `_summarize_condition()`, apply normalization BEFORE computing statistics:
```python
# Extract features (currently line 308-310)
for ch in channels:
    ch_values = [v['features'][ch] for v in used_values]

    # NEW: Apply cell line normalization
    if normalization_mode != "none":
        ch_values = [normalize_value(val, key.cell_line, ch, normalization_mode)
                     for val in ch_values]

    feature_means[ch] = float(np.mean(ch_values))
    feature_stds[ch] = float(np.std(ch_values, ddof=1)) if n > 1 else 0.0
```

**Control:** Add parameter to `aggregate_observation()`:
```python
def aggregate_observation(
    proposal: Proposal,
    raw_results: Sequence[RawWellResult],
    budget_remaining: int,
    *,
    strategy: AggregationStrategy = "default_per_channel",
    normalization_mode: Literal["none", "fold_change", "zscore"] = "none"  # NEW
) -> Observation:
```

**Default:** `normalization_mode="none"` (agent must discover the problem)

---

### Phase 2: Add Z-Score Normalization (Medium Risk)

**Requires:**
1. Vehicle well identification (compound == "DMSO")
2. Pooling vehicle wells by cell line + channel
3. Computing mean and std per cell line per channel
4. Handling cold-start (not enough vehicle wells yet)

**Implementation:**
```python
def _estimate_vehicle_statistics(
    raw_results: Sequence[RawWellResult]
) -> Dict[str, Dict[str, Tuple[float, float]]]:
    """
    Estimate vehicle (DMSO) baseline statistics from raw results.

    Returns:
        {cell_line: {channel: (mean, std)}}
    """
    vehicle_values = defaultdict(lambda: defaultdict(list))

    for result in raw_results:
        if result.treatment.compound.lower() in ["dmso", "vehicle"]:
            cell_line = result.cell_line
            morph = result.readouts.get('morphology', {})
            for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']:
                vehicle_values[cell_line][ch].append(morph.get(ch, 0.0))

    # Compute mean and std
    vehicle_stats = {}
    for cell_line, channels in vehicle_values.items():
        vehicle_stats[cell_line] = {}
        for ch, values in channels.items():
            if len(values) >= 2:
                vehicle_stats[cell_line][ch] = (np.mean(values), np.std(values, ddof=1))
            else:
                # Fallback: use baseline as mean, assume 10% CV
                baseline = get_cell_line_baseline(cell_line)[ch]
                vehicle_stats[cell_line][ch] = (baseline, baseline * 0.1)

    return vehicle_stats
```

**Pedagogical value:** Agent must include ≥2 vehicle wells per cell line to enable z-score normalization

---

## Defeat Conditions

How does the agent **defeat** cell line confounding?

### Defeat Strategy 1: Within-Cell-Line Comparisons (Gold Standard)
- Design experiments with ONE cell line at a time
- Compare treatment vs vehicle WITHIN that cell line
- Baseline cancels out in the comparison
- **No normalization needed** - agent learns correct experimental design

### Defeat Strategy 2: Matched Pairs (Silver Standard)
- Include vehicle controls for EACH cell line tested
- Compute treatment effect as `(treatment - vehicle) / vehicle` manually
- Agent implements normalization in its own analysis
- **Requires fold-change normalization** - but agent does it explicitly

### Defeat Strategy 3: Request Normalization (Bronze Standard)
- Agent detects high variance across cell lines
- Requests `normalization_mode="fold_change"` from platform
- Platform applies normalization before returning observation
- **Least pedagogical** - platform does the work

**Ranking:**
1. Within-cell-line design (learns correct experimental structure)
2. Matched pairs (learns to normalize manually)
3. Request normalization (learns to use platform feature)

---

## Testing Plan

### Test 1: Variance Reduction
**Hypothesis:** Fold-change normalization reduces cell line variance from 77% → <10%

**Method:**
1. Run CAL_384_RULES_WORLD_v2 with 3 cell lines (A549, HepG2, U2OS)
2. Compute variance components on RAW values
3. Compute variance components on NORMALIZED values
4. Verify cell line variance drops dramatically

**Success:** Cell line variance <10% after normalization

---

### Test 2: Treatment Effect Preservation
**Hypothesis:** Fold-change normalization preserves treatment effect sizes

**Method:**
1. Run dose-response with compound X on A549 (ER stress)
2. Compute treatment effect on raw values: `Δ_raw = treated_mean - vehicle_mean`
3. Compute treatment effect on normalized values: `Δ_norm = (treated_mean / baseline) - (vehicle_mean / baseline)`
4. Verify `Δ_norm` reflects dose-response correctly

**Success:** Dose-response curve preserved after normalization

---

### Test 3: Cross-Cell-Line Comparability
**Hypothesis:** Fold-change normalization makes cell lines comparable

**Method:**
1. Run same compound on A549 and HepG2
2. WITHOUT normalization: compare means → large difference due to baseline
3. WITH normalization: compare means → difference only from treatment response
4. Verify normalized values are similar if mechanism is shared

**Success:** Normalized values cluster by mechanism, not cell line

---

## Metadata and Transparency

**Critical:** Agent must know if normalization is applied

Add to `Observation` schema:
```python
@dataclass
class Observation:
    design_id: str
    conditions: List[ConditionSummary]
    wells_spent: int
    budget_remaining: int
    qc_flags: List[str]
    aggregation_strategy: str
    normalization_mode: str  # NEW: "none", "fold_change", "zscore"
    normalization_metadata: Optional[Dict[str, Any]] = None  # NEW: baseline values used
```

**Example metadata:**
```python
normalization_metadata = {
    "mode": "fold_change",
    "baselines_used": {
        "A549": {"er": 100.0, "mito": 150.0, ...},
        "HepG2": {"er": 130.0, "mito": 180.0, ...}
    },
    "variance_reduction": 0.87  # 87% variance removed
}
```

This enables:
1. Agent auditing (did normalization help?)
2. Debugging (which baseline was used?)
3. Reproducibility (exact normalization parameters logged)

---

## Open Questions

1. **Should baseline come from params or from data?**
   - Params: Known ground truth, deterministic
   - Data (vehicle wells): Learns from experiments, adapts to batch effects
   - **Recommendation:** Start with params (simpler), add data-driven later

2. **Should agent control normalization mode?**
   - Yes: Agent learns when to use it (pedagogical)
   - No: Platform decides (simpler)
   - **Recommendation:** Agent controls it via experiment metadata

3. **Does normalization break temporal causality?**
   - No: Normalization happens AFTER measurement, doesn't affect time
   - Baseline is time-independent (cell line property)
   - **Safe:** No causality violations

4. **What about batch effects in baseline?**
   - Current: baseline is constant (from params)
   - Reality: baseline drifts across runs due to reagent lots, instruments
   - **Future:** Learn baseline from vehicle wells per-run (z-score mode)

---

## Success Metrics

Normalization is successful if:

1. **Variance reduction:** Cell line variance drops from 77% → <10%
2. **Effect preservation:** Treatment effect sizes unchanged
3. **Pedagogical value:** Agent learns to design within-cell-line experiments
4. **No regressions:** Existing tests still pass
5. **Transparency:** Agent can audit normalization decisions

---

## Status: Design Complete ✅

**Next step:** Implement Phase 1 (fold-change normalization) in `observation_aggregator.py`

**Files to modify:**
- `src/cell_os/epistemic_agent/observation_aggregator.py` (add normalization)
- `src/cell_os/epistemic_agent/schemas.py` (add normalization_mode to Observation)
- `tests/unit/test_cell_line_normalization.py` (new test file)

**Pedagogical contract:**
- Default = no normalization (agent must discover confound)
- Agent can request normalization OR design matched experiments
- Ultimate goal: agent learns within-cell-line design (no normalization needed)
