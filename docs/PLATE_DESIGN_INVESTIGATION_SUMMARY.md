# Plate Design Investigation Summary

**Date**: 2025-12-22
**Investigation**: V3 vs V4 comparison, mechanism analysis, V5 hybrid design
**Status**: ✅ Complete - V5 ready for testing

---

## Quick Navigation

1. **[V3_V4_FINAL_COMPARISON.md](V3_V4_FINAL_COMPARISON.md)** - Complete findings and verdict
2. **[V4_MECHANISM_REPORT.md](V4_MECHANISM_REPORT.md)** - Why V4's 2×2 checkerboard fails
3. **[V5_DESIGN_SUMMARY.md](V5_DESIGN_SUMMARY.md)** - Hybrid design combining V3 + V4

---

## The Story in 3 Acts

### Act 1: The Discovery (V3 vs V4 Comparison)

**Goal**: Test if V4's homogeneous islands improve CV without breaking spatial decorrelation.

**Results**:
- ✅ **Island CV**: 13.3% (spectacular - 81% reduction from V3's 71%)
- ❌ **Spatial Variance**: +194% increase in boring wells (critical failure)

**Key Finding**: V4 achieves amazing CV but breaks spatial decorrelation.

**Decisive Test**: Boring wells only (vehicle, nominal density, no probes, non-island)
```
V3 boring wells: 1160 spatial variance (91 wells)
V4 boring wells: 3409 spatial variance (72 wells)
Change: +194% ❌
```

**Verdict**: V3 remains production-safe. V4 is research tool only.

---

### Act 2: The Investigation (Mechanism Analysis)

**Goal**: Understand WHY V4's 2×2 micro-checkerboard creates spatial artifacts.

**Hypotheses Tested**:
1. ❌ Neighbor coupling? → **No**: Moran's I ≈ 0, no spatial autocorrelation
2. ❌ Island boundary effects? → **No**: Boundary wells BETTER than interior
3. ✅ 2×2 blocking creates low-frequency patterns? → **YES**: Confirmed

**Analyses Performed**:
- **Moran's I**: Global spatial autocorrelation (Z-score ≈ 0 for both V3 and V4)
- **Variogram**: V4 shows 2-3× higher semivariance at ALL distances (not just neighbors)
- **Neighbor coupling**: Interior wells (>2 away) show WORSE variance than boundary
- **Row/column patterns**: Lag-1 autocorrelation similar for both

**Key Insights**:

1. **No simulator neighbor coupling**
   - Wells don't propagate values to neighbors
   - Islands don't contaminate adjacent wells
   - Boundary wells actually show 41-51% CV vs interior 148% CV

2. **2×2 blocks create periodic structure**
   - Cell lines have different means (~75 vs ~195)
   - 2×2 tiling creates regular alternating blocks
   - Row/column aggregation amplifies block boundaries
   - Result: spatial variance inflates even in uniform regions

3. **Single-well alternation is safe**
   - V3 uses high-frequency pattern (lag-1)
   - Creates smooth gradients, not step functions
   - No periodic structure to inflate variance

**Conclusion**: V4's problem is fundamental geometry, not fixable without redesign.

---

### Act 3: The Solution (V5 Hybrid Design)

**Goal**: Combine V3's spatial decorrelation with V4's CV measurement zones.

**Strategy**: Keep best of both, reject 2×2 blocking
- ✅ V3 single-well alternating checkerboard (base)
- ✅ V4's 8× 3×3 homogeneous islands (overlay)
- ✅ V4's exclusion rules (protection)
- ❌ V4's 2×2 block checkerboard (reject)

**V5 Design**:
```
Base:    V3 checkerboard (H A H A H A... per row, flipped each row)
Islands: 8× 3×3 homogeneous regions (6 vehicle, 2 anchor)
Rules:   Force NOMINAL density, exclude all probes from islands
```

**Expected Performance**:
| Metric | V3 | V4 | V5 Expected |
|--------|----|----|-------------|
| Spatial Variance (boring) | 1160 | 3409 | ~1160 ✅ |
| Island CV | N/A | 13.3% | ~13% ✅ |
| Mixed Tile CV | 71.3% | 41.7% | 60-70% |

**Validation**: All structural checks passed ✅

**Status**: Ready for simulation testing (5 seeds)

---

## Key Takeaways

### Technical Findings

1. **Geometry matters more than we thought**
   - Layout creates spatial patterns that metrics capture
   - 2×2 blocks = low-frequency (bad)
   - Single-well alternation = high-frequency (good)

2. **Simulator has NO neighbor coupling**
   - Moran's I near zero
   - Islands don't contaminate neighbors
   - Confirms simulator independence assumption

3. **Homogeneous islands work spectacularly**
   - 13% CV achieved (vs 71% in mixed tiles)
   - No edge effects detected
   - Boundary wells actually benefit from proximity

4. **Spatial metrics are layout-dependent**
   - Row/column variance measures DESIGN + ARTIFACT
   - Must use boring wells subset for fair comparison
   - Raw metric invalid for multi-regime plates

### Design Principles Learned

1. **Prefer high-frequency patterns**
   - Smooth mixing over block tiling
   - Gradients over step functions

2. **Isolate measurement zones**
   - Homogeneous regions for technical replicates
   - Exclusion rules for purity
   - Protect from probes/gradients

3. **Validate with subset analysis**
   - Boring wells test (vehicle, nominal, no probes)
   - Apples-to-apples comparison
   - Accept ≤20% variance increase

4. **Accept fundamental trade-offs**
   - CV vs spatial decorrelation (tension exists)
   - V5 attempts to have both, but may need compromise

---

## Files Generated

### Documentation
- `docs/V3_V4_FINAL_COMPARISON.md` - Complete investigation findings
- `docs/V4_MECHANISM_REPORT.md` - Spatial artifact mechanism analysis
- `docs/V5_DESIGN_SUMMARY.md` - Hybrid design specification
- `docs/PLATE_DESIGN_INVESTIGATION_SUMMARY.md` - **This document**

### Analysis Scripts
- `scripts/compare_v3_v4_qc.py` - Full QC comparison across metrics
- `scripts/compare_boring_wells.py` - Decisive spatial test
- `scripts/check_all_v4_islands.py` - Per-island CV breakdown
- `scripts/analyze_v4_spatial_masked.py` - Masking test
- `scripts/analyze_spatial_autocorrelation.py` - Moran's I, variogram, patterns
- `scripts/analyze_neighbor_coupling.py` - Island boundary effects

### Plate Designs
- `validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v3.json` - Production (current)
- `validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v4.json` - Research only
- `validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v5.json` - **New hybrid (testing)**

### Scripts for V5
- `scripts/create_v5_hybrid.py` - V5 generation
- `scripts/validate_v5_hybrid.py` - V5 structural validation

### Visualizations
- `validation_frontend/public/analysis_plots/v3_boring_wells_heatmap.png`
- `validation_frontend/public/analysis_plots/v4_boring_wells_heatmap.png`
- `validation_frontend/public/analysis_plots/variogram_comparison.png`
- `validation_frontend/public/analysis_plots/row_col_patterns.png`
- `validation_frontend/public/analysis_plots/neighbor_coupling_histograms.png`

---

## Next Steps

### Immediate: Test V5

**Run comparison** (on JupyterHub or locally):
```bash
cd ~/cell_OS

# V3 (control) - 5 seeds
for seed in 42 123 456 789 1000; do
  python3 scripts/run_calibration_plate.py \
    --plate_design validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v3.json \
    --seed $seed \
    --output validation_frontend/public/demo_results/calibration_plates/
done

# V5 (test) - 5 seeds
for seed in 42 123 456 789 1000; do
  python3 scripts/run_calibration_plate.py \
    --plate_design validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v5.json \
    --seed $seed \
    --output validation_frontend/public/demo_results/calibration_plates/
done
```

**Analyze results**:
```bash
# Create comparison scripts (adapted from V3 vs V4)
python3 scripts/compare_v3_v5_qc.py
python3 scripts/compare_boring_wells_v3_v5.py
python3 scripts/check_all_v5_islands.py
```

**Success Criteria**:
1. ✅ V5 boring wells spatial variance within 20% of V3 (930-1390)
2. ✅ V5 island CV ≤ 20%
3. ⚠️ V5 mixed tile CV < 80%
4. ⚠️ V5 Z-factor > -15

### If V5 Passes

1. **Adopt V5 as production standard**
   - Update frontend default to V5
   - Retire V3 (superseded)
   - Archive V4 (research tool)

2. **Document outcomes**
   - Create `docs/V5_VALIDATION_RESULTS.md`
   - Update QC dashboard with V5 metrics
   - Share findings with wet lab team

3. **Plan wet lab validation**
   - Run V5 on real hardware
   - Confirm simulator predictions
   - Measure actual island CV (expect 10-30%, not 2-4%)

### If V5 Fails

1. **Diagnose failure mode**
   - Spatial variance elevated → islands + checkerboard interact
   - Island CV elevated → implementation bug
   - Mixed CV very high → neighbor diversity unavoidable

2. **Fallback options**
   - **Option A**: Revert to V3 (proven, safe)
   - **Option B**: Test alternative island placements (diagonal, edge-only)
   - **Option C**: Accept trade-off (V3 for screening, V4 for CV)

3. **Document lessons**
   - Update design principles
   - Characterize failure mechanism
   - Define plate design classes (calibration vs QC vs screening)

---

## Design Evolution Summary

```
V2 (row interleaving)
  ├─→ V3 (single-well checkerboard) ✅ Production (spatial-optimized)
  │    └─→ V5 (V3 + islands) ⏳ Testing (hybrid approach)
  │
  └─→ V4 (2×2 blocks + islands) ❌ Research only (CV-optimized, spatial broken)
       └─→ Mechanism identified → informed V5 design
```

**Current Status**:
- V3: Production standard (proven safe)
- V4: Research tool (CV studies only)
- V5: Testing (best-of-both hypothesis)

---

## What We Proved

1. **Homogeneous islands work** (13% CV is achievable)
2. **2×2 blocking fails** (creates low-frequency spatial artifacts)
3. **Simulator has no neighbor coupling** (wells are independent)
4. **Single-well alternation is safe** (V3 baseline 1160 variance)
5. **Islands don't contaminate neighbors** (boundary wells better than interior)

## What We Don't Know Yet

1. **Does V5 preserve V3's spatial decorrelation?** (needs testing)
2. **Does V5 achieve V4's island CV?** (needs testing)
3. **Do islands + checkerboard interact?** (could create new artifacts)
4. **Will wet lab match simulator?** (simulator may underestimate variance)

---

## Conclusion

**This investigation was highly productive.**

We:
- ✅ Characterized V4's spectacular CV achievement (13%)
- ✅ Identified V4's critical spatial failure (+194%)
- ✅ Diagnosed the mechanism (2×2 blocking creates periodic patterns)
- ✅ Proved no neighbor coupling exists (Moran's I ≈ 0)
- ✅ Designed V5 hybrid to get best of both worlds
- ✅ Validated V5 structure (all checks passed)

**V5 represents synthesis of investigation insights.**

**If V5 succeeds**: We achieve both CV measurement and spatial decorrelation → production win

**If V5 fails**: We accept fundamental trade-off → use case-specific designs (calibration vs QC)

**Either way**: Investigation advanced plate design understanding significantly.

---

**End of Investigation Summary**

**Status**: Investigation complete → V5 ready for testing
**Decision Point**: After V5 testing → adopt or fallback
**Timeline**: Test V5 → Document results → Update production

---

## Appendix: Command Reference

### Run Single Plate
```bash
python3 scripts/run_calibration_plate.py \
  --plate_design validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v5.json \
  --seed 42 \
  --output validation_frontend/public/demo_results/calibration_plates/
```

### Validate Plate Design
```bash
python3 scripts/validate_v5_hybrid.py
```

### Compare Designs
```bash
# Full comparison
python3 scripts/compare_v3_v5_qc.py

# Boring wells test (decisive)
python3 scripts/compare_boring_wells_v3_v5.py

# Island CV check
python3 scripts/check_all_v5_islands.py
```

### Mechanism Analysis
```bash
# Spatial autocorrelation
python3 scripts/analyze_spatial_autocorrelation.py

# Neighbor coupling
python3 scripts/analyze_neighbor_coupling.py
```

### View Plots
```bash
open validation_frontend/public/analysis_plots/v3_boring_wells_heatmap.png
open validation_frontend/public/analysis_plots/v4_boring_wells_heatmap.png
open validation_frontend/public/analysis_plots/variogram_comparison.png
```
