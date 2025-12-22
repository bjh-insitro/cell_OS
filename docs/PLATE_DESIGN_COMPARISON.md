# Plate Design Comparison Guide

## Overview

This guide explains how to systematically compare different calibration plate designs using simulation to understand what information each design provides.

## Phase 1: v1 vs v2 Comparison

### Running the comparison

**On JupyterHub (recommended - 31 workers):**

```bash
cd ~/repos/cell_OS && PYTHONPATH=. python3 scripts/compare_plate_designs.py
```

This will:
1. Run CAL_384_RULES_WORLD_v1 with seeds: 42, 123, 456, 789, 1011
2. Run CAL_384_RULES_WORLD_v2 with seeds: 42, 123, 456, 789, 1011
3. Auto-pull latest code before each run (keeps simulation synced with latest code)
4. Auto-commit results after each run (saves results to git)
5. Take approximately 20-30 minutes total with parallel execution

**Note:** The script automatically pulls before each simulation to ensure you're using the latest code. This is especially important when running on JH where the repository might be updated between runs.

### What to compare

#### 1. Design Differences

**v1 (Simple calibration):**
- Blocked by cell line (all HepG2 together, all A549 together)
- DMSO vehicle controls
- Two anchor compounds (mild and strong)
- 2×2 tiles for local QC
- Simpler, fewer variables

**v2 (Advanced calibration):**
- Interleaved cell lines (breaks confounds)
- Density gradient (3 levels: low/medium/high)
- Stain probes (0.9x and 1.1x)
- Focus probes (stress-test autofocus)
- Timing probes (fixation jitter)
- More complex, more variables

#### 2. Key Questions to Answer

**Statistical Power:**
- Which design gives tighter confidence intervals for anchor separation?
- Which has better replication structure for detecting small effects?
- What's the signal-to-noise ratio in each?

**Confound Structure:**
- Does v1's blocked design confound cell line with spatial position?
- Does v2's interleaving successfully break the confound?
- What new confounds does v2 introduce?

**Information Content:**
- What can v2 measure that v1 cannot?
- Is v2's added complexity worth the interpretability cost?
- Do the stain/focus/timing probes in v2 actually provide actionable insights?

**Robustness:**
- Which design is more sensitive to batch effects?
- Which is more robust to edge effects?
- How consistent are results across the 5 seeds?

#### 3. Metrics to Extract

For each design and seed, extract:

**Spatial metrics:**
```python
# Edge vs interior variance
edge_wells = wells in rows A,P or cols 1,24
interior_wells = wells in rows D-M and cols 6-19

edge_variance = var(edge_wells)
interior_variance = var(interior_wells)
edge_ratio = edge_variance / interior_variance
```

**Anchor separation:**
```python
# How well do anchors separate?
dmso_features = features from DMSO wells
mild_anchor_features = features from 1µM anchor
strong_anchor_features = features from 100µM anchor

# Cohen's d between groups
mild_effect_size = (mean(mild) - mean(dmso)) / pooled_std
strong_effect_size = (mean(strong) - mean(dmso)) / pooled_std
```

**Replication quality:**
```python
# For v1: 2×2 tiles
# For v2: contrastive tiles
tile_cv = coefficient_of_variation(technical_replicates)
```

**Cross-seed consistency:**
```python
# Run same analysis on all 5 seeds
# Measure variance in conclusions across seeds
seed_robustness = std(effect_sizes_across_seeds)
```

#### 4. Visualization Ideas

**Heatmaps:**
- Side-by-side plate heatmaps for key features
- Show spatial patterns in v1 vs v2
- Highlight where designs differ

**PCA plots:**
- Does v2's interleaving create clearer clusters?
- Do anchors separate better in one design?

**Variance decomposition:**
```
Total variance = Spatial + Cell line + Treatment + Residual
```
- Which design attributes more to spatial vs biological?

**Consistency plots:**
- Plot same metric across 5 seeds
- Which design has tighter error bars?

### Results Location

All simulation results are saved to:
```
validation_frontend/public/demo_results/calibration_plates/
```

Files follow pattern:
```
{PLATE_ID}_run_{TIMESTAMP}_seed{SEED}.json
```

For example:
```
CAL_384_RULES_WORLD_v1_run_20251222_143022_seed42.json
CAL_384_RULES_WORLD_v2_run_20251222_145511_seed42.json
```

### Interpreting Results

**If v1 and v2 give similar answers:**
→ v2's complexity doesn't buy you much, stick with v1 for first physical plate

**If v2 reveals patterns v1 misses:**
→ The interleaving/gradients are valuable, worth the complexity

**If v2 is much noisier:**
→ Too many variables, not enough replication per condition

**If results vary wildly across seeds:**
→ Design is sensitive to batch effects, need more controls

### Limitations

Remember: **Simulations can't tell you about simulation gaps!**

These comparisons assume the measurement model is correct. You'll only discover model gaps when you:
1. Run at least one design physically
2. Compare simulation predictions to real data
3. Look for systematic discrepancies
4. Update the model with learned artifacts
5. Re-run simulations with improved model

### Next Steps After Phase 1

1. **Pick the better design** based on information content and robustness
2. **Run that design physically** ($2k investment)
3. **Calibrate simulation** by comparing to real data
4. **Phase 2:** Run all 7 designs with calibrated model
5. **Phase 3:** Pick optimal sequence of physical plates to run

## Phase 2: All Design Comparison (Future)

After calibrating simulation with real data from Phase 1:

```python
# Extend DESIGNS list in compare_plate_designs.py
DESIGNS = [
    "CAL_384_RULES_WORLD_v1",
    "CAL_384_RULES_WORLD_v2",
    "CAL_384_MICROSCOPE_BEADS_DYES_v1",
    "CAL_384_LH_ARTIFACTS_v1",
    "CAL_VARIANCE_PARTITION_v1",
    "CAL_EL406_WASH_DAMAGE_v1",
    "CAL_DYNAMIC_RANGE_v1",
]
```

This will take ~70-105 minutes (7 designs × 5 seeds × 2-3 min each).

## Custom Comparisons

To compare different designs or seeds:

```python
# Edit scripts/compare_plate_designs.py

# Compare different designs
DESIGNS = [
    "CAL_VARIANCE_PARTITION_v1",
    "CAL_DYNAMIC_RANGE_v1",
]

# Use more seeds for tighter confidence
SEEDS = [42, 123, 456, 789, 1011, 2048, 3141, 5926, 8979, 3238]

# Run without auto-commit (for testing)
AUTO_COMMIT = False
```

## Analysis Scripts (TODO)

Future work: Build analysis pipeline to automatically:
- Load all results for a design comparison
- Extract comparable metrics
- Generate comparison plots
- Output statistical summary

This could be a Jupyter notebook or a new frontend page.
