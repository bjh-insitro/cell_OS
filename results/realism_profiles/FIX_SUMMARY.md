# Realism Profiles Demo Fix: Layout Confound → Pure Detector Diagnostic

## The Problem

The original demo had a fatal confound: **it was measuring where drugs were placed, not detector artifacts**.

### Original plate layout (WRONG):
- Rows A-B: DMSO (control, normal brightness)
- Rows C-D: Staurosporine @ 1 µM
- Rows E-F: Staurosporine @ 10 µM
- **Rows G-H: Paclitaxel @ 1 µM** ← Edge rows, bright phenotype

### Result:
- Edge wells had **paclitaxel** (bright microtubule phenotype)
- Center wells had **DMSO** (normal phenotype)
- Edge sensitivity came back **POSITIVE** (brighter edges)

This wasn't vignetting. This was the plate map.

Positive edge_sensitivity = brighter edges = "we put the bright drug near the edge"

Real vignetting (dimmer edges) would be **negative**.

---

## The Fix

Three design modes with `--design` flag:

1. **dmso_only** (default): All wells DMSO, A549. Pure detector diagnostic.
2. **single_condition**: One compound everywhere (e.g., all paclitaxel @ 1µM).
3. **mixed_randomized**: Multiple compounds, shuffled deterministically (biology uncorrelated with position).

### Safety features:
- `compute_plate_summary()` refuses to compute `edge_sensitivity` for mixed designs
- Returns `edge_sensitivity[ch] = None` for non-uniform designs
- `print_summary()` warns: "edge_sensitivity is only valid for dmso_only or single_condition"

---

## Results (DMSO-only plates, seed=42)

### Edge Sensitivity (correlation: edge_distance vs intensity)
**Negative = dimmer edges (real vignetting)**

| Channel | Clean   | Realistic | Hostile |
|---------|---------|-----------|---------|
| ER      | -0.137  | -0.313    | -0.353  |
| Mito    | -0.109  | -0.254    | -0.300  |
| Nucleus | -0.304  | -0.457    | -0.486  |
| Actin   | -0.344  | -0.481    | -0.510  |
| RNA     | -0.105  | -0.293    | -0.345  |

**Interpretation:**
- All values are **negative** (correct direction for vignetting)
- Magnitude increases: clean → realistic → hostile
- Actin and nucleus show strongest vignetting

### Edge vs Center Delta (%)
**Negative = dimmer edges**

| Channel | Clean  | Realistic | Hostile |
|---------|--------|-----------|---------|
| ER      | -6.9%  | -11.9%    | -14.0%  |
| Mito    | -5.2%  | -10.2%    | -12.4%  |
| Nucleus | -11.3% | -16.0%    | -18.1%  |
| Actin   | -8.9%  | -13.8%    | -15.9%  |
| RNA     | -1.5%  | -6.8%     | -9.0%   |

### Outlier Rates

| Profile   | Observed | Expected |
|-----------|----------|----------|
| Clean     | 0.00%    | 0%       |
| Realistic | 0.00%    | ~1%      |
| Hostile   | 2.08%    | ~3%      |

Realistic profile got lucky with RNG (no outliers), but hostile shows noise spikes and focus misses as expected.

---

## What This Actually Measures Now

**Before:** "Where did you put the paclitaxel?"
**After:** "How badly does your detector lie about position?"

### Clean profile:
- Mild vignetting (-5% to -11% edge dimming)
- No outliers
- Baseline for comparison

### Realistic profile:
- Moderate vignetting (-7% to -16% edge dimming)
- Rare outliers (~1% expected, got 0% by chance)
- Representative of a well-maintained core facility

### Hostile profile:
- Strong vignetting (-9% to -18% edge dimming)
- Detector pathologies (2% outliers: noise spikes, focus misses)
- Representative of "old scope in the corner of the lab"

---

## Usage

```bash
# Default: dmso_only (recommended for detector diagnostics)
python scripts/demo_realism_profiles.py --profile realistic --output results/realism_profiles --plot

# Single condition (e.g., all wells treated with paclitaxel)
python scripts/demo_realism_profiles.py --profile realistic --design single_condition

# Mixed randomized (biology uncorrelated with position, but no edge_sensitivity metric)
python scripts/demo_realism_profiles.py --profile realistic --design mixed_randomized
```

Generate comparison plots:
```bash
python scripts/compare_realism_profiles.py
```

---

## Files Generated

### Data:
- `results/realism_profiles/{profile}_{design}_wells.csv` - Per-well measurements
- `results/realism_profiles/{profile}_{design}_summary.json` - Plate-level metrics

### Plots:
- `results/realism_profiles/plots/{profile}_edge_vs_mean.png` - Edge distance vs mean intensity
- `results/realism_profiles/plots/{profile}_edge_vs_std.png` - Edge distance vs variance
- `results/realism_profiles/comparison_plots/edge_sensitivity_comparison.png` - Cross-profile comparison
- `results/realism_profiles/comparison_plots/outlier_rate_comparison.png` - Outlier rates
- `results/realism_profiles/comparison_plots/edge_delta_heatmap.png` - Edge vs center delta heatmap

---

## The Takeaway

Don't confound biology with position.

If your "detector artifact" metric has the wrong sign, you're not measuring the detector.

DMSO-only plates are your friend.
