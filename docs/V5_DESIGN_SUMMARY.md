# V5 Hybrid Plate Design Summary

**Date**: 2025-12-22
**Status**: ✅ Design Complete - Ready for Testing
**Validation**: All checks passed

---

## Executive Summary

**V5 combines the best of V3 and V4 while avoiding V4's spatial artifacts.**

### Design Philosophy

V5 is a **hybrid approach**:
- **Base**: V3's single-well alternating checkerboard (high-frequency pattern)
- **Overlay**: V4's 8× 3×3 homogeneous reproducibility islands
- **Protection**: V4's exclusion rules (force NOMINAL density, no probes in islands)

### Expected Performance

| Metric | V3 | V4 | V5 Expected | Rationale |
|--------|----|----|-------------|-----------|
| **Spatial Variance (boring)** | 1160 | 3409 (+194%) | **~1160** | V3-like checkerboard in mixed regions |
| **Island CV** | N/A | 13.3% | **~13%** | Same homogeneous islands as V4 |
| **Mixed Tile CV** | 71.3% | 41.7% | **60-70%** | Single-well alternation (neighbor diversity) |
| **Z-Factor** | -12.3 | -16.5 | **-12 to -13** | V3-like anchor performance |

**Key Hypothesis**: V5 will match V3's spatial decorrelation while gaining V4's CV measurement zones.

---

## Design Comparison Matrix

|  | V3 | V4 | V5 Hybrid |
|---|---|---|---|
| **Cell Line Pattern** | Single-well checkerboard | 2×2 block checkerboard | Single-well checkerboard |
| **Homogeneous Islands** | ❌ None | ✅ 8× 3×3 islands | ✅ 8× 3×3 islands |
| **Spatial Decorrelation** | ✅ Excellent | ❌ Broken (+194%) | ✅ Expected excellent |
| **Replicate Precision** | ❌ Poor (71% CV) | ✅ Excellent (13% CV) | ⚠️ Split: islands 13%, mixed 60-70% |
| **Production Safety** | ✅ Yes | ❌ No (research only) | ⚠️ Pending validation |

**V5 Goal**: Get V4's CV benefits without V4's spatial penalty.

---

## Technical Details

### 1. Base Pattern: V3 Single-Well Checkerboard

**Implementation**:
```
Row B: H A H A H A H A H A H A H A H A H A H A H A H A
Row C: A H A H A H A H A H A H A H A H A H A H A H A H
Row D: H A H A H A H A H A H A H A H A H A H A H A H A
Row E: A H A H A H A H A H A H A H A H A H A H A H A H
```

**Characteristics**:
- High-frequency alternation (lag-1 pattern)
- Fully decorrelates cell line from row/column position
- No block structure → no low-frequency spatial patterns
- Slight neighbor diversity → local CV ~60-70%

**Why this works**:
- V3 boring wells showed 1160 spatial variance (baseline)
- Single-well alternation creates smooth gradient in row/column means
- No periodic structure to inflate variance

### 2. Island Overlay: 8× 3×3 Homogeneous Regions

**Island Locations**:
```
        Cols 1-8         Cols 9-16        Cols 17-24
Rows D-F:
  - CV_NW_HEPG2_VEH (D4-F6)
  - CV_NW_A549_VEH (D8-F10)
  - CV_NE_HEPG2_VEH (D15-F17)
  - CV_NE_A549_VEH (D20-F22)

Rows K-M:
  - CV_SW_HEPG2_MORPH (K4-M6)
  - CV_SW_A549_MORPH (K8-M10)
  - CV_SE_HEPG2_VEH (K15-M17)
  - CV_SE_A549_DEATH (K20-M22)
```

**Island Assignments**:
```
6× Vehicle Islands:
  - 3× HepG2 + DMSO (CV_NW, CV_NE, CV_SE)
  - 3× A549 + DMSO (CV_NW, CV_NE in north; not in south due to anchor)

2× Anchor Islands:
  - CV_SW_HEPG2_MORPH: HepG2 + Nocodazole 0.3µM
  - CV_SE_A549_DEATH: A549 + Thapsigargin 0.05µM
```

**Why this works**:
- V4 achieved 13% island CV (spectacular)
- Homogeneous 3×3 tiles isolate technical from biological variance
- Mechanism analysis showed NO neighbor coupling around islands
- Boundary wells actually had LOWER variance than interior (islands act as anchors)

### 3. Exclusion Rules: Protect Island Purity

**Forced Fields** (override all probes/gradients in islands):
```json
"exclusion_rules": {
  "exclude_from": [
    "stain_scale_probes",
    "fixation_timing_probes",
    "imaging_focus_probes",
    "cell_density_gradient",
    "background_control"
  ],
  "forced_fields": {
    "cell_density": "NOMINAL",
    "stain_scale": 1.0,
    "fixation_timing_offset_min": 0,
    "imaging_focus_offset_um": 0
  }
}
```

**Why this matters**:
- Islands measure PURE cell line + treatment CV
- No confounding from density gradients or probe perturbations
- Enables apples-to-apples comparison within each island

### 4. Modifications from V3

**Cell Line Enforcement**:
- 36 wells updated to match island requirements
- Example: D4 was A549 in V3 checkerboard, now HepG2 for CV_NW_HEPG2_VEH island

**Contrastive Tiles Removed**:
- TILE_DEATH_LOCAL (overlapped with islands)
- TILE_DENSITY_STRESS_LOW (overlapped with islands)
- 2 tiles removed total

**No scattered anchors affected**:
- V3 had no scattered anchors in island positions
- No removal needed

---

## Validation Results

**All checks passed**:

1. ✅ **Non-island wells match V3 checkerboard**: All 312 non-island wells preserved
2. ✅ **Island wells have correct cell lines**: All 72 island wells enforced
3. ✅ **Exclusion rules configured**: All 4 forced fields set correctly
4. ✅ **No anchor overlap**: No scattered anchors in vehicle islands
5. ✅ **No tile overlap**: No contrastive tiles intersect islands

**V5 is structurally sound and ready for simulation testing.**

---

## Mechanism Justification

### Why V5 Should Work (And V4 Failed)

**V4's Fatal Flaw**: 2×2 block checkerboard
- Created low-frequency periodic structure
- Row/column aggregation amplified block boundaries
- Even "boring wells" (far from islands) showed 148% CV vs V3's 68%
- Spatial variance +194% increase

**V5's Advantage**: Single-well alternation
- High-frequency pattern (lag-1)
- Row/column aggregation sees smooth gradients, not step functions
- No block structure to create periodic artifacts
- Should match V3's 1160 spatial variance baseline

**Evidence from Mechanism Report**:
1. **No neighbor coupling exists**: Moran's I ≈ 0, Z-score ≈ 0
2. **Islands don't create edge effects**: Boundary wells had LOWER CV than interior in V4
3. **Problem was 2×2 blocking**: Interior wells (>2 away from islands) showed worst variance
4. **Single-well alternation is safe**: V3 boring wells had stable 1160 variance

**Conclusion**: By keeping V3's single-well pattern and only overlaying islands, V5 should inherit V3's spatial benefits while gaining V4's CV zones.

---

## Testing Plan

### Hypothesis

**H1**: V5 boring wells will show spatial variance ~1160 (similar to V3)
**H2**: V5 island CV will be ~13% (similar to V4)
**H3**: V5 mixed tile CV will be 60-70% (between V3's 71% and V4's 42%)

### Test Protocol

**Run V3 vs V5 comparison with 5 seeds**:
```bash
cd ~/cell_OS

# V3 (control)
for seed in 42 123 456 789 1000; do
  python3 scripts/run_calibration_plate.py \
    --plate_design validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v3.json \
    --seed $seed \
    --output validation_frontend/public/demo_results/calibration_plates/
done

# V5 (test)
for seed in 42 123 456 789 1000; do
  python3 scripts/run_calibration_plate.py \
    --plate_design validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v5.json \
    --seed $seed \
    --output validation_frontend/public/demo_results/calibration_plates/
done
```

**Run comparison analysis**:
```bash
python3 scripts/compare_v3_v5_qc.py
python3 scripts/compare_boring_wells_v3_v5.py
python3 scripts/check_all_v5_islands.py
```

### Success Criteria

**Must Pass**:
1. ✅ V5 boring wells spatial variance within 20% of V3 (930-1390 range)
2. ✅ V5 island CV ≤ 20% (acceptable technical floor)

**Should Pass**:
3. ⚠️ V5 mixed tile CV < 80% (better than V3, but neighbor diversity expected)
4. ⚠️ V5 Z-factor > -15 (V3-level or better)

**If V5 passes all criteria**: Adopt as production standard, retire V3 and V4

**If V5 fails boring wells test**: Single-well + islands may interact unexpectedly. Investigate or revert to V3.

**If V5 fails island CV test**: Island implementation issue. Debug or revert to V3.

---

## Design Rationale Summary

### What We Kept

**From V3**:
- ✅ Single-well alternating checkerboard (proven spatial decorrelation)
- ✅ Per-well cell line assignment strategy
- ✅ All non-island well assignments

**From V4**:
- ✅ 8× 3×3 homogeneous reproducibility islands
- ✅ Exclusion rules (NOMINAL density + no probes)
- ✅ Island positioning (quadrants, avoid edges)

### What We Rejected

**From V4**:
- ❌ 2×2 block micro-checkerboard (creates spatial artifacts)
- ❌ Block structure in non-island regions

**From V2**:
- ❌ Row-based cell line assignment (confounds column)

### Why This Should Work

**Spatial decorrelation**:
- Single-well alternation is high-frequency (no periodic structure)
- V3 proved this works (1160 spatial variance baseline)
- Mechanism analysis showed 2×2 blocks were the culprit, not islands

**CV measurement**:
- Homogeneous islands worked in V4 (13% CV achieved)
- No neighbor coupling exists to contaminate islands
- Boundary wells benefited from island proximity (stability)

**Risk mitigation**:
- If V5 fails, we still have V3 as fallback
- Testing on 5 seeds ensures robustness
- Boring wells test provides decisive metric

---

## Files Generated

### Plate Design
- `validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v5.json` - V5 hybrid design

### Scripts
- `scripts/create_v5_hybrid.py` - V5 generation script
- `scripts/validate_v5_hybrid.py` - V5 validation script

### Documentation
- `docs/V5_DESIGN_SUMMARY.md` - **This document**

### Pending (After Testing)
- `scripts/compare_v3_v5_qc.py` - Full QC comparison
- `scripts/compare_boring_wells_v3_v5.py` - Decisive spatial test
- `scripts/check_all_v5_islands.py` - Island CV validation
- `docs/V5_VALIDATION_RESULTS.md` - Test outcomes

---

## Recommendations

### Immediate

1. **Test V5 with 5 seeds**
   - Compare against V3 (control)
   - Run decisive boring wells test
   - Measure island CV

2. **Document results**
   - Create V5_VALIDATION_RESULTS.md
   - Update comparison if V5 passes

### If V5 Passes

3. **Adopt V5 as production standard**
   - Retire V3 (superseded by V5)
   - Archive V4 (research only)
   - Update frontend to default to V5

4. **Wet lab validation**
   - Run V5 on real hardware
   - Confirm simulator predictions hold
   - Measure actual island CV (should be 10-30%, not 2-4%)

### If V5 Fails

5. **Diagnose failure mode**
   - If spatial variance elevated: islands may affect checkerboard unexpectedly
   - If island CV elevated: implementation bug or simulator issue
   - If mixed CV very high: neighbor diversity unavoidable

6. **Fallback options**
   - Revert to V3 (proven spatial decorrelation)
   - Test alternative island placements (diagonal, edge-only)
   - Accept trade-off: V3 for screening, V4 for CV studies

---

## Design Evolution Timeline

```
V1 (deprecated) → uniform cell lines, no spatial decorrelation

V2 (baseline) → row interleaving, breaks row confound, keeps column confound

V3 (production) → single-well checkerboard, breaks both confounds
                → Spatial variance 1160 (boring wells)
                → Mixed tile CV 71%

V4 (research) → 2×2 block checkerboard + homogeneous islands
              → Island CV 13% ✅ (spectacular)
              → Spatial variance 3409 ❌ (+194% increase)
              → Mechanism: 2×2 blocks create low-frequency patterns

V5 (hybrid) → V3 checkerboard + V4 islands
            → Expected: V3-level spatial, V4-level CV
            → Status: Ready for testing
```

---

## Key Insights

### What We Learned

1. **Neighbor coupling does NOT exist in simulator**
   - Moran's I ≈ 0 (no spatial autocorrelation)
   - Islands don't contaminate neighbors
   - Boundary wells are BETTER than interior

2. **Layout geometry matters**
   - 2×2 blocks → low-frequency patterns
   - Single-well alternation → high-frequency patterns
   - Row/column variance amplifies periodic structure

3. **Homogeneous islands work**
   - 13% CV achieved (vs 71% in mixed tiles)
   - Proves neighbor diversity inflates CV
   - No edge effects detected

4. **Spatial metrics are layout-dependent**
   - Row/column variance measures DESIGN, not artifact
   - Must use subset analysis for multi-regime plates
   - Boring wells test is decisive

### Design Principles

1. **Prefer high-frequency patterns**
   - Single-well alternation over block tiling
   - Smooth gradients over step functions

2. **Isolate measurement zones**
   - Homogeneous islands for CV measurement
   - Exclusion rules to protect island purity
   - No probe/gradient contamination

3. **Validate spatial decorrelation**
   - Use boring wells subset (vehicle, nominal, no probes)
   - Compare against baseline (V3)
   - Accept ≤20% variance increase

4. **Design with trade-offs in mind**
   - CV vs spatial decorrelation (fundamental tension)
   - Local precision vs global uniformity
   - Measurement zones vs full-plate coverage

---

## Conclusion

**V5 represents the synthesis of V3/V4 investigation.**

**If V5 succeeds**:
- We achieve both CV measurement and spatial decorrelation
- V5 becomes production standard
- V4 investigation was worthwhile (revealed design principles)

**If V5 fails**:
- We accept fundamental trade-off (CV vs spatial)
- V3 remains production (screening)
- V4 remains research tool (CV studies)

**Either way, we've advanced understanding of plate design.**

---

**End of V5 Design Summary**

**Status**: Design complete → Ready for testing
**Next**: Run V3 vs V5 comparison with 5 seeds, analyze results
