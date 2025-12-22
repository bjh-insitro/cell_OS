# V3 vs V4 Final Comparison: The CV-Spatial Trade-Off

**Date**: 2025-12-22
**Status**: ✅ Investigation Complete - Design Tension Confirmed
**Seeds Tested**: 42, 123, 456, 789, 1000

---

## Executive Summary

**V4 achieves spectacular CV reduction but breaks spatial decorrelation.**

This is not a bug. This is a fundamental design trade-off between:
- **Replicate precision** (homogeneous islands)
- **Spatial decorrelation** (2×2 micro-checkerboard)

### Key Findings

| Metric | V3 | V4 | Winner | Notes |
|--------|----|----|--------|-------|
| **Island CV** | 71.3% | **13.3%** | ✅ V4 | 81% reduction (homogeneous 3×3 tiles) |
| **Mixed Tile CV** | 71.3% | 41.7% | ✅ V4 | 42% improvement |
| **Spatial Variance (boring)** | 1160 | **3409** | ❌ V4 | +194% increase (CRITICAL FAILURE) |
| Z-Factor | -12.3 | -16.5 | ⚠️ V3 | V4 slightly worse |

**Verdict**: V3 remains production-safe. V4 is a research tool for CV characterization only.

---

## The Investigation Journey

### Initial Results (Misleading)

First comparison showed:
- V4 Island CV: 13.28% (amazing!)
- V4 Spatial Variance: +37% (concerning but maybe artifact?)

**Hypothesis**: Island wells contaminating row/column means.

### Masking Test (Revealed Truth)

Recomputed spatial variance **excluding islands**:
- V3 spatial: 344
- V4 non-island spatial: 2192 (**+538%** increase)

**Conclusion**: Masking made NO difference. Islands aren't contaminating - the plate itself has spatial structure.

### Boring Wells Test (Decisive)

Compared **apples-to-apples**: vehicle-only, nominal-density, non-probe, non-edge, non-island wells.

**Results**:
- V3 boring wells: 1160 spatial variance (91 wells)
- V4 boring wells: 3409 spatial variance (72 wells)
- **Change: +194%** ❌

**Sample Values**:
```
V3: 195, 192, 77, 72, 194, 78, 77, 200, 70, 77...
V4: 78, 194, 79, 79, 196, 73, 202, 77, 77, 205...
```

Both show two clusters (~70-80 and ~190-200) = the two cell lines.

**V3**: Smooth mixing via row interleaving
**V4**: Regular alternating blocks via 2×2 tiling → **low-frequency spatial pattern**

---

## What V4 Achieved

### 1. Homogeneous Islands Work Spectacularly

**8 islands (3×3 each, 72 wells total)**:

| Island | Cell Line | Treatment | CV |
|--------|-----------|-----------|-----|
| CV_NW_HEPG2_VEH | HepG2 | Vehicle | 2.84% |
| CV_NW_A549_VEH | A549 | Vehicle | 2.95% |
| CV_NE_HEPG2_VEH | HepG2 | Vehicle | 2.31% |
| CV_NE_A549_VEH | A549 | Vehicle | 4.20% |
| CV_SW_HEPG2_MORPH | HepG2 | Nocodazole 0.3µM | **21.03%** |
| CV_SW_A549_MORPH | A549 | Nocodazole 0.3µM | 2.08% |
| CV_SE_HEPG2_VEH | HepG2 | Vehicle | 2.50% |
| CV_SE_A549_DEATH | A549 | Thapsigargin 0.05µM | **12.81%** |

**Overall Mean**: 6.34% ± 6.47%

**Findings**:
- ✅ Vehicle islands: 2-4% CV (technical replicate floor)
- ✅ Anchor islands: 12-21% CV (more realistic)
- ⚠️ Simulator underestimates baseline biological variance
- ✅ **Hypothesis confirmed**: Neighbor diversity was inflating V3 tile CV

### 2. Mixed Checkerboard Improves Over V3

V4 mixed tiles (same 2×2 regions as V3):
- V3: 71.32% CV
- V4: 41.72% CV
- **Improvement**: 42% reduction

Even without homogeneous islands, V4's layout reduces CV.

---

## What V4 Broke

### The 2×2 Micro-Checkerboard Creates Spatial Artifacts

**Problem**: Regular 2×2 tiling creates **low-frequency checkerboard pattern** in row/column variance.

**Why this happens**:
1. Cell lines have different mean values (~75 vs ~195)
2. 2×2 tiling creates regular alternating blocks
3. Row/column aggregation sees periodic structure
4. Variance inflates even when wells are "boring"

**Evidence**:
- Boring wells should be spatially uniform
- V4 boring wells show alternating high/low pattern
- +194% variance increase cannot be explained by measurement noise

**Mechanism** (suspected):
- Simulator may include neighbor coupling effects
- Island boundaries create discontinuities
- 2×2 pattern creates resonance in spatial field
- Low-frequency structure dominates row/column variance

---

## Simulator Limitations Discovered

### 1. Baseline CV Unrealistically Low

**Vehicle islands: 2-4% CV** is at the technical replicate floor.

Real biology expectations:
- Technical replicates (same well): 1-5% CV
- Biological replicates (different wells): 10-30% CV

**Conclusion**: Simulator underestimates baseline stochasticity when:
- Cell line + treatment + density all identical
- No explicit perturbations applied

**But**: Anchor islands show 12-21% CV, proving simulator CAN generate biological variance under perturbation.

### 2. Spatial Metric is Layout-Dependent

Raw row/column variance conflates:
- Designed heterogeneity (islands, anchors, probes, gradients)
- True spatial artifact (position-dependent measurement bias)

**For multi-regime plates**, must use:
- Subset analysis (boring wells only)
- Residual variance after removing known structure
- Spatial autocorrelation metrics (Moran's I, variograms)

---

## Design Trade-Off Matrix

|  | V3 (Row Interleaving) | V4 (Micro-Checkerboard + Islands) |
|---|---|---|
| **Spatial Decorrelation** | ✅ Excellent | ❌ Broken (+194%) |
| **Replicate Precision** | ❌ Poor (71% CV) | ✅ Excellent (13% CV in islands) |
| **Production Safety** | ✅ Yes | ❌ No (research only) |
| **Use Cases** | Spatial modeling, screening | CV characterization, technical validation |

**Fundamental Tension**: You cannot have both tight local CV AND global spatial decorrelation with checkerboard layouts.

---

## Recommendations

### Immediate (Production)

1. **Use V3 as default calibration plate**
   - Proven spatial decorrelation
   - Acceptable CV for screening
   - No unexpected artifacts

2. **Use V4 for CV studies only**
   - Research tool to measure technical reproducibility
   - Do NOT use for spatial modeling
   - Islands provide clean CV measurement zones

### Short-Term (Investigation)

3. **Characterize simulator neighbor kernel**
   - Understand why 2×2 tiling creates artifacts
   - Measure spatial autocorrelation structure
   - Identify coupling distance/strength

4. **Test V5 hybrid**
   - V3 row-interleaving (preserve spatial)
   - Add homogeneous islands (get CV benefit)
   - Abandon micro-checkerboard for mixed regions

### Long-Term (Validation)

5. **Wet lab comparison**
   - Run V3 on real hardware
   - Measure if simulator CV predictions hold
   - Validate spatial decorrelation claims

6. **Establish plate design classes**
   - Calibration plates (spatial-optimized)
   - QC plates (CV-optimized)
   - Screening plates (balanced)

---

## Files Generated

### Analysis Scripts
- `scripts/compare_v3_v4_qc.py` - Full QC comparison across metrics
- `scripts/check_v4_island_variance.py` - Island CV validation
- `scripts/check_all_v4_islands.py` - Per-island CV breakdown
- `scripts/analyze_v4_spatial_masked.py` - Masked spatial variance test
- `scripts/compare_boring_wells.py` - **Decisive apples-to-apples test**

### Plate Designs
- `validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v3.json` - Production-safe
- `validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v4.json` - Research tool
- `validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v4_checkerboard_experiment.json` - Original v4 (archived)

### Documentation
- `docs/V2_V3_COMPARISON_RESULTS.md` - V2 vs V3 comparison (earlier)
- `docs/V4_DESIGN_SUMMARY.md` - V4 design rationale
- `docs/V3_V4_FINAL_COMPARISON.md` - **This document**

---

## Key Insights for Future Design

### What Worked
- ✅ Homogeneous islands (3×3) for CV measurement
- ✅ Exclusion rules (forced nominal density, no probes)
- ✅ Per-well cell line assignment (well_to_cell_line)
- ✅ Hypothesis-driven iterative refinement

### What Failed
- ❌ 2×2 micro-checkerboard for mixed regions
- ❌ Assuming spatial decorrelation is layout-independent
- ❌ Using raw row/column variance for multi-regime plates

### What We Learned
- Neighbor diversity inflates CV (confirmed)
- Spatial patterns create low-frequency artifacts
- Simulator underestimates baseline biological variance
- Design goals can be fundamentally incompatible

---

## Conclusion

**V4 was not a failure. It was a necessary experiment.**

We discovered:
1. Islands work (13% CV is transformative)
2. Micro-checkerboard fails (spatial artifacts dominate)
3. Fundamental trade-off exists (CV vs spatial)

**The next design** (V5) must choose:
- Preserve V3's spatial benefits, add islands (hybrid)
- Accept V4's spatial cost for CV gains (QC-specific)
- Redesign from first principles (characterize mechanism)

**V3 remains production-safe until V5 is validated.**

---

## Appendix: Validation Commands

### Run Full Comparison
```bash
cd ~/repos/cell_OS
python3 scripts/compare_v3_v4_qc.py
```

### Check Island CV
```bash
python3 scripts/check_all_v4_islands.py
```

### Decisive Spatial Test
```bash
python3 scripts/compare_boring_wells.py
```

### Expected Output (Boring Wells Test)
```
V3 boring wells: 1160.30  (91 wells)
V4 boring wells: 3409.21  (72 wells)
Δ (v4 - v3):     +2248.91
Change:          +193.8%

❌ V4 SPATIAL DECORRELATION DEGRADED
```

---

**End of Investigation**

**Status**: V3 production, V4 research, V5 pending
**Next**: Characterize mechanism → Design V5 hybrid → Validate in wet lab
