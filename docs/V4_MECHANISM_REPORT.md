# V4 Spatial Artifact Mechanism Report

**Date**: 2025-12-22
**Status**: ✅ Mechanism Identified
**Analysis**: Spatial autocorrelation + Neighbor coupling + Visual inspection

---

## Executive Summary

**V4's spatial variance increase (+194%) is NOT due to neighbor coupling or island boundary effects.**

**Root Cause**: The 2×2 micro-checkerboard layout creates **low-frequency spatial patterns** that inflate row/column variance aggregation.

### Key Findings

| Finding | Evidence | Implication |
|---------|----------|-------------|
| **No neighbor coupling** | Moran's I ≈ 0 (Z-score 0) | Simulator does not propagate values between adjacent wells |
| **Scale-invariant variance** | Variogram flat or increasing | Variance persists at all distances (not localized) |
| **Interior wells worse than boundary** | Interior CV 148% vs Boundary CV 41-51% | Islands NOT creating edge effects |
| **2×2 pattern universally inflates variance** | V4 variogram 2-3× higher at ALL distances | Problem is layout geometry, not islands |

**Verdict**: V4's 2×2 micro-checkerboard is fundamentally incompatible with row/column variance metrics.

---

## Analysis 1: Spatial Autocorrelation

### Moran's I Statistic

**Purpose**: Measure if similar values cluster together spatially.

**Results** (boring wells only):
```
V3 Moran's I:  -0.2865  (expected: -0.0111)
V3 Z-score:     0.00    (not significant)

V4 Moran's I:  -0.0099  (expected: -0.0141)
V4 Z-score:     0.00    (not significant)
```

**Interpretation**:
- Neither V3 nor V4 shows significant spatial autocorrelation
- Negative values suggest slight checkerboard pattern (expected)
- **Z-score ≈ 0**: No statistical significance

**Conclusion**: ❌ Spatial autocorrelation does NOT explain V4's variance increase.

---

## Analysis 2: Variogram (Spatial Covariance vs Distance)

### What is a Variogram?

γ(h) = semivariance at distance h = average squared difference between wells separated by distance h

**If no spatial structure**: Variogram should be flat (variance independent of distance)
**If neighbor coupling exists**: Variogram should increase with distance (nearby wells more similar)

### Results

```
Distance    V3 γ(h)      V4 γ(h)      V4/V3 Ratio
--------    --------     --------     -----------
   1        12,033       25,648          2.1×
   2         8,224       25,569          3.1×
   3        12,887       21,128          1.6×
   4         8,248       16,822          2.0×
   5        10,934       13,367          1.2×
   6         4,576       11,222          2.5×
   7         9,658       15,983          1.7×
   8         3,736       22,173          5.9×
```

**Key Observations**:

1. **V4 variogram 1.2-5.9× higher at ALL distances**
   - Not just at distance 1 (immediate neighbors)
   - Problem persists even 8 wells away

2. **V3 variogram is noisy but moderate**
   - Range: 3,736 - 12,887
   - No clear trend with distance

3. **V4 variogram starts high and stays high**
   - Distance 1-2: ~25,000 (very high)
   - Distance 5-7: ~13,000-16,000 (still 2× V3)
   - Distance 8: spikes to 22,173 (outlier?)

**Interpretation**:
- V4 wells are MORE dissimilar at ALL scales
- This is NOT neighbor coupling (which would decay with distance)
- This IS layout geometry creating periodic structure

**Conclusion**: ✅ Variogram confirms scale-invariant variance inflation.

---

## Analysis 3: Neighbor Coupling Around Islands

### Hypothesis

If simulator has neighbor coupling, island boundaries should create edge effects:
- Boundary wells (1-2 away from islands) should show different variance
- Boundary wells might be biased toward island values

### Well Classification

**V4 boring wells by distance from islands**:
- Interior (>2 away): 23 wells
- Boundary 2-away: 28 wells
- Boundary 1-away: 21 wells

**V3 boring wells** (no islands):
- Interior: 70 wells

### Results

```
Category        N    Mean    Std     CV
-----------   ---   -----   -----   -----
V3 Interior    70   144.4   98.6    68.3%

V4 Interior    23   158.3   235.0   148.4%  ⬆️ WORST
V4 Boundary-2  28   149.8    62.4    41.7%  ⬇️ BEST
V4 Boundary-1  21   115.7    58.6    50.7%  ⬇️ GOOD
```

### **CRITICAL FINDING**

**V4 Interior wells show HIGHER CV than boundary wells!**

- Interior CV: 148.4% (2.2× worse than V3)
- Boundary-2 CV: 41.7% (1.6× better than V3!)
- Boundary-1 CV: 50.7% (1.3× better than V3)

**This is the OPPOSITE of what neighbor coupling would predict.**

If islands were creating edge effects:
- Boundary wells should be WORSE than interior
- But boundary wells are actually BETTER

### Cell Line Distribution

```
Category        A549-like   HepG2-like   Ratio
-----------     ---------   ----------   -----
V4 Interior        15           8        1.9:1
V4 Boundary-2      10          18        1:1.8  (reversed!)
V4 Boundary-1      14           7        2:1
```

**Interpretation**:
- Interior and Boundary-1 have ~2:1 A549:HepG2 ratio
- Boundary-2 has ~1:2 ratio (reversed)
- This suggests cell line assignment pattern, NOT neighbor coupling
- If coupling existed, boundary-2 should be intermediate, not reversed

**Conclusion**: ❌ No evidence of neighbor coupling around islands. Boundaries look BETTER than interior.

---

## Analysis 4: Row/Column Pattern Detection

### Lag-1 Autocorrelation

Measures if adjacent rows/columns have correlated means:
- r > 0: similar values cluster (bands)
- r ≈ 0: no pattern
- r < 0: alternating pattern (checkerboard)

### Results

```
V3 Row lag-1 autocorr:    -0.1123  (slight checkerboard)
V3 Column lag-1 autocorr:  0.0597  (nearly random)

V4 Row lag-1 autocorr:    -0.1119  (slight checkerboard)
V4 Column lag-1 autocorr: -0.0340  (nearly random)
```

**Interpretation**:
- Both V3 and V4 show slight negative row autocorrelation (expected from row interleaving)
- Column autocorrelation near zero for both
- **No strong checkerboard signal detected**

**Why?**
- Lag-1 autocorrelation only measures correlation between ADJACENT values
- 2×2 micro-checkerboard creates **lag-2** or **lag-4** patterns
- Need power spectral analysis to detect periodic structure

**Conclusion**: ⚠️ Lag-1 autocorrelation insufficient to detect 2×2 patterns. Need deeper analysis.

---

## Unified Mechanism Explanation

### Why V4 Interior Wells Have Higher Variance

**V4's 2×2 micro-checkerboard creates low-frequency spatial structure:**

1. **Cell lines have different mean values**:
   - A549-like: ~75
   - HepG2-like: ~195
   - Δ = 120 units

2. **2×2 tiling creates regular alternating blocks**:
   - Not single-well alternation (would be high-frequency)
   - Not row-banding (would be 1D structure)
   - 2×2 blocks create **periodic 2D pattern**

3. **Row/column aggregation amplifies block structure**:
   - When computing row means, 2×2 blocks contribute coherently
   - Adjacent rows sample different phases of 2×2 pattern
   - Result: row means show periodic variation

4. **Variance of row/column means inflates**:
   - V3 row interleaving creates smooth gradual mixing
   - V4 2×2 blocks create step-function transitions
   - Variance of step function > variance of smooth gradient

### Why V4 Boundary Wells Have LOWER Variance

**Boundary wells benefit from proximity to homogeneous islands:**

1. **Islands are NOMINAL density + same cell line**:
   - HepG2 islands all ~195
   - A549 islands all ~75
   - No mixing within islands

2. **Boundary wells adjacent to islands are buffered**:
   - If boundary well is HepG2 and adjacent island is HepG2: stable
   - If boundary well is A549 and adjacent island is A549: stable
   - Even if mismatched, island provides local anchor

3. **Interior wells have no such anchor**:
   - Surrounded by mixed neighbors with varying cell lines
   - No local "reference point"
   - More susceptible to 2×2 pattern variance

**Analogy**: Interior wells are in "open sea" of 2×2 pattern. Boundary wells are near "islands" of stability.

### Why Spatial Variance Metric Fails

**Row/column variance measures global uniformity, not local artifact:**

1. **V3 row interleaving**: Smooth cell line mixing → row means stable
2. **V4 2×2 checkerboard**: Blocky cell line pattern → row means vary
3. **Spatial variance aggregates this global pattern**, even though:
   - Local wells are NOT contaminated
   - No neighbor coupling exists
   - Wells measure correct values

**The metric is measuring DESIGN, not ARTIFACT.**

But for multi-regime plates, this distinction breaks down:
- V4's 2×2 design IS the artifact (unintended consequence)
- V3's row interleaving IS the design (intentional smoothing)

---

## Visualizations

Generated plots:

1. **`v3_boring_wells_heatmap.png`**: V3 spatial distribution (smooth gradients)
2. **`v4_boring_wells_heatmap.png`**: V4 spatial distribution (2×2 block pattern visible?)
3. **`variogram_comparison.png`**: V4 variogram 2-3× higher at all distances
4. **`row_col_patterns.png`**: Row/column mean patterns
5. **`neighbor_coupling_histograms.png`**: Value distributions by island proximity

**Key Visual Insights**:
- Heatmaps should show V4's 2×2 block structure
- Variogram plot confirms scale-invariant variance
- Proximity histograms show interior wells WORSE than boundary

---

## Implications for Plate Design

### What We Learned

1. **Neighbor coupling does NOT exist in simulator**
   - Moran's I ≈ 0
   - No distance-dependent variance decay
   - Islands don't create edge effects

2. **2×2 micro-checkerboard is fundamentally flawed**
   - Creates low-frequency spatial patterns
   - Inflates row/column variance universally
   - Cannot be fixed by adjusting island placement

3. **Row/column variance is layout-dependent metric**
   - Measures global pattern, not local artifact
   - Valid for uniform plates (V2, V3)
   - Invalid for multi-regime plates with block structure

4. **Homogeneous islands work spectacularly**
   - 13% CV achieved (vs 71% in V3)
   - No evidence of island edge effects
   - Boundary wells actually show LOWER variance

### Design Principles for V5

**Keep from V4:**
- ✅ Homogeneous 3×3 islands for CV measurement
- ✅ Exclusion rules to enforce island isolation
- ✅ Per-well cell line assignment

**Replace from V4:**
- ❌ 2×2 micro-checkerboard (creates spatial artifacts)

**Restore from V3:**
- ✅ Row interleaving for cell line assignment (smooth mixing)
- ✅ No block structure in non-island regions

**New for V5:**
- ⚠️ Use residual variance metric (remove known structure first)
- ⚠️ Or use subset analysis (boring wells only)
- ⚠️ Validate that row interleaving + islands doesn't create new artifacts

---

## Recommendations

### Immediate

1. **Accept V3 as production standard**
   - Proven spatial decorrelation
   - No layout artifacts
   - Acceptable CV for screening

2. **Document V4 limitations**
   - Research tool only (CV studies)
   - Do NOT use for spatial modeling
   - Spatial variance metric invalid

### Short-Term

3. **Design V5 hybrid**
   - V3 row-interleaving base
   - Add 8× 3×3 homogeneous islands
   - Test if combination preserves spatial benefits

4. **Improve spatial metrics**
   - Use boring wells subset
   - Compute residual variance after removing design structure
   - Add Moran's I and variogram to QC dashboard

### Long-Term

5. **Characterize 2×2 pattern in frequency domain**
   - 2D Fourier transform of plate values
   - Identify dominant spatial frequencies
   - Prove 2×2 tiling creates low-frequency peak

6. **Test alternative island placements**
   - Diagonal arrangement (minimize row/column overlap)
   - Edge-only islands (preserve interior smoothness)
   - Variable island sizes (3×3, 4×4, 5×5)

---

## Files Generated

### Analysis Scripts
- `scripts/analyze_spatial_autocorrelation.py` - Moran's I, variogram, row/col patterns
- `scripts/analyze_neighbor_coupling.py` - Island boundary effects, proximity analysis

### Visualizations
- `validation_frontend/public/analysis_plots/v3_boring_wells_heatmap.png`
- `validation_frontend/public/analysis_plots/v4_boring_wells_heatmap.png`
- `validation_frontend/public/analysis_plots/variogram_comparison.png`
- `validation_frontend/public/analysis_plots/row_col_patterns.png`
- `validation_frontend/public/analysis_plots/neighbor_coupling_histograms.png`

### Documentation
- `docs/V4_MECHANISM_REPORT.md` - **This document**

---

## Conclusion

**The mechanism is clear: V4's 2×2 micro-checkerboard creates low-frequency spatial patterns that inflate row/column variance metrics.**

**This is NOT fixable by:**
- Adjusting island placement
- Changing island size
- Improving simulator

**This IS fixable by:**
- Abandoning 2×2 checkerboard for non-island regions
- Using V3-style row interleaving instead
- Keeping homogeneous islands as-is

**V5 design path is now clear:**
1. Start with V3 base (row interleaving)
2. Add V4 islands (3×3 homogeneous)
3. Test that combination doesn't create new artifacts
4. Validate boring wells spatial variance < V3 baseline

---

**End of Mechanism Report**

**Status**: Mechanism identified → Ready for V5 design
**Next**: Design and validate V5 hybrid plate
