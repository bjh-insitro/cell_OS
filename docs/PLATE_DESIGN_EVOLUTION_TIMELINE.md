# Plate Design Evolution Timeline

**Purpose**: Historical record of plate design iterations and key learnings

**Period**: 2025-12-22 (investigation period)

---

## Evolution Map

```
V2 (row interleaving)
  │
  ├─ Problem: Column confounding (cell line || column)
  │
  ├─→ V3 (single-well checkerboard) ✅ SCREENING
  │    │
  │    ├─ Achievement: 49% spatial variance reduction
  │    ├─ Problem: High CV (71%) - is this fixable?
  │    │
  │    └─→ V5 (V3 + islands) ⏳ HYBRID
  │         └─ Status: Designed, pending testing
  │
  └─→ V4 (2×2 blocks + islands) ✅ CALIBRATION
       │
       ├─ Achievement: 13% island CV (81% reduction)
       ├─ Problem: +194% spatial variance in boring wells
       │
       └─→ Investigation: Why does V4 break spatial decorrelation?
            │
            ├─ Hypothesis 1: Neighbor coupling? ❌ Falsified (Moran's I ≈ 0)
            ├─ Hypothesis 2: Island contamination? ❌ Falsified (boundary wells better)
            ├─ Hypothesis 3: 2×2 blocks? ✅ Confirmed (mechanism identified)
            │
            └─→ Resolution: Two plate classes discovered
                 ├─ CALIBRATION (V4): Measure noise floor
                 └─ SCREENING (V3): Stress-test spatial model
```

---

## Chronological History

### V2: Row Interleaving (Baseline)

**Date**: Pre-investigation (baseline comparison)

**Design**:
- Cell lines assigned by row (A=HepG2, B=A549, C=HepG2...)
- Breaks row confound
- Column confound remains (cell line || column)

**Key Metrics**:
- Mixed tile CV: 66.58%
- Z-factor: -22.2
- Spatial variance: 6366 (high)

**Learnings**:
- Row interleaving alone insufficient
- Column confounding problematic
- Need 2D decorrelation

**Disposition**: Superseded by V3

---

### V3: Single-Well Checkerboard (Production Screening)

**Date**: 2025-12-22 (formalized as SCREENING class)

**Design**:
- Single-well alternating pattern (A1=A549, A2=HepG2, A3=A549...)
- Flips each row (B1=HepG2, B2=A549...)
- High-frequency mixing
- No homogeneous islands

**Key Metrics**:
- Mixed tile CV: 71.32%
- Z-factor: -12.3 (44% better than V2)
- Spatial variance: 3245 (49% reduction from V2)
- Boring wells variance: 1160 (baseline)

**Learnings**:
- ✅ Single-well alternation breaks row/column confounds
- ✅ Spatial decorrelation excellent
- ⚠️ High CV (71%) - but is this a problem or expected?

**Plate Class**: SCREENING

**Valid Metrics**: spatial_variance, z_factor, hit_robustness

**Invalid Metrics**: island_cv, absolute_cv_as_biological_noise

**Status**: ✅ Production ready (screening campaigns)

**Use For**:
- Hit validation
- Spatial model testing
- Robustness screening

---

### V4: 2×2 Blocks + Homogeneous Islands (Production Calibration)

**Date**: 2025-12-22

**Design**:
- 8× 3×3 homogeneous islands (6 vehicle, 2 anchor)
- 2×2 micro-checkerboard in non-island regions
- Exclusion rules (force NOMINAL density, no probes in islands)
- Per-well cell line enforcement

**Key Metrics**:
- Island CV: 13.28% (81% reduction from V3's 71%)
- Vehicle island CV: 2-4% (technical floor)
- Anchor island CV: 12-21% (perturbation effect)
- Spatial variance (all wells): 2194 (+538% from V3)
- Boring wells variance: 3409 (+194% from V3)

**Learnings**:
- ✅ Homogeneous islands work spectacularly (13% CV)
- ✅ Islands don't contaminate neighbors (boundary wells better)
- ❌ 2×2 blocks create low-frequency spatial patterns
- ❌ High spatial variance NOT fixable without removing 2×2 blocks
- 🔍 Revealed fundamental trade-off (CV vs spatial decorrelation)

**Investigation Triggered**: Why does V4 have +194% spatial variance?

**Mechanism Identified**:
- 2×2 blocks create periodic structure
- Cell lines have different means (~75 vs ~195)
- Row/column aggregation amplifies block boundaries
- NOT neighbor coupling (Moran's I ≈ 0)
- NOT island boundary effects (interior wells worse than boundary)

**Plate Class**: CALIBRATION

**Valid Metrics**: island_cv, technical_floor, perturbation_effect

**Invalid Metrics**: spatial_variance, row_column_decorrelation

**Status**: ✅ Production ready (QC and noise measurement)

**Use For**:
- Assay setup and QC
- Technical noise measurement
- Day-to-day reproducibility
- Perturbation characterization

---

### V5: Hybrid (V3 Base + V4 Islands) [Optional]

**Date**: 2025-12-22

**Design**:
- V3 single-well alternating checkerboard (base pattern)
- 8× 3×3 homogeneous islands overlaid
- Exclusion rules active in islands
- 36 wells updated for island cell line enforcement

**Hypothesis**:
- H1: Boring wells spatial variance ~1160 (V3-level)
- H2: Island CV ~13% (V4-level)
- H3: No 2×2 block artifacts (single-well alternation safer)

**Expected Metrics**:
- Island CV: ~13% (V4-like)
- Boring wells variance: ~1160 (V3-like)
- Mixed tile CV: 60-70% (between V3 and V4)

**Learnings** (pending testing):
- Test if single-well alternation + islands preserves spatial benefits
- Validate that islands don't interfere with checkerboard
- Confirm no new interaction artifacts

**Plate Class**: HYBRID (exploratory)

**Valid Metrics**: island_cv, boring_wells_spatial_variance

**Status**: ⏳ Designed, validation passed, testing optional

**Disposition**:
- If passes: Demonstrates both objectives achievable
- If fails: Confirms V3/V4 split necessary
- Either way: V3 + V4 already cover use cases

---

## The Key Discovery: Plate Classes

**Date**: 2025-12-22

**Insight**: Plate layout is an epistemic instrument, not just logistics.

### What We Thought

"V4 has high spatial variance - need to fix it"

### What We Discovered

Two fundamentally different questions require two different physical experiments:

1. **How noisy is the assay?** → CALIBRATION plate (homogeneous islands)
2. **How robust is the assay?** → SCREENING plate (spatial mixing)

### The Resolution

Not "V3 vs V4" but "V3 AND V4" - complementary instruments for different questions.

**Calibration Plates** (V4):
- Measure noise floor
- Homogeneous islands
- Spatial variance INVALID metric
- Island CV is gold standard

**Screening Plates** (V3):
- Stress-test robustness
- Spatial mixing
- Absolute CV INVALID metric
- Spatial variance is gold standard

### Impact

- ✅ Metrics no longer contradict
- ✅ Design objectives explicit
- ✅ Both plates production-ready
- ✅ Analysis becomes principled

---

## Metrics Evolution

### What Each Version Optimized

| Version | Optimized For | Sacrifice | Outcome |
|---------|---------------|-----------|---------|
| V2 | Break row confound | Column still confounded | Partial solution |
| V3 | Spatial decorrelation | Local CV precision | Excellent screening |
| V4 | CV measurement | Spatial mixing | Excellent calibration |
| V5 | Both (hypothesis) | TBD | Testing pending |

### Metric Validity by Plate

| Metric | V2 | V3 (SCREENING) | V4 (CALIBRATION) | V5 (HYBRID) |
|--------|----|----|----|----|
| Island CV | N/A | ❌ Invalid | ✅ Valid | ✅ Valid |
| Mixed Tile CV | ✅ Valid | ✅ Valid | ❌ Invalid | ⚠️ Context-dependent |
| Spatial Variance | ✅ Valid | ✅ Valid | ❌ Invalid | ✅ Valid (boring wells) |
| Z-Factor | ✅ Valid | ✅ Valid | ⚠️ Different context | ⚠️ Context-dependent |
| Technical Floor | N/A | ❌ Invalid | ✅ Valid | ✅ Valid (islands) |

---

## Key Learnings by Phase

### Phase 1: V2 → V3 (Spatial Decorrelation)

**Question**: Can we break column confounding?

**Answer**: Yes - single-well checkerboard achieves full 2D decorrelation

**Metrics**:
- Spatial variance: 49% reduction
- Z-factor: 44% improvement
- Mixed tile CV: +5% increase (trade-off)

**Learning**: Neighbor diversity slightly inflates local CV, but spatial benefits dominate

---

### Phase 2: V3 → V4 (CV Optimization)

**Question**: Can we measure true replicate precision?

**Answer**: Yes - homogeneous islands achieve 13% CV (81% reduction)

**Metrics**:
- Island CV: 13.3% (spectacular)
- Boring wells spatial variance: +194% (concerning)

**Learning**: CV optimization requires homogeneity, which breaks spatial mixing

---

### Phase 3: V4 Investigation (Mechanism)

**Question**: Why does V4 have high spatial variance?

**Hypotheses Tested**:
1. ❌ Neighbor coupling (Moran's I ≈ 0)
2. ❌ Island contamination (boundary wells better)
3. ✅ 2×2 blocks create periodic patterns

**Mechanism**:
- 2×2 tiling creates low-frequency checkerboard
- Cell line means differ (~75 vs ~195)
- Row/column aggregation amplifies block structure
- Spatial variance inflates even in boring wells

**Learning**: Layout geometry matters - 2×2 blocks fundamentally incompatible with spatial variance metric

---

### Phase 4: Plate Class Formalization

**Question**: Is this a design failure or fundamental trade-off?

**Answer**: Fundamental trade-off - two objectives require two instruments

**Resolution**:
- V3 → SCREENING plate class
- V4 → CALIBRATION plate class
- Define valid metrics per class
- Formalize epistemic contracts

**Learning**: "Plate layout is an epistemic instrument" - different questions need different physical experiments

---

## Design Principles Extracted

### From V2 → V3

1. **Full 2D decorrelation required**: Row interleaving alone insufficient
2. **High-frequency mixing safe**: Single-well alternation breaks confounds without artifacts
3. **Neighbor diversity acceptable**: 5% CV increase tolerable for spatial benefits

### From V4 Investigation

4. **Homogeneous islands work**: 3×3 tiles isolate technical from biological variance
5. **No simulator coupling**: Wells are independent (Moran's I ≈ 0)
6. **Islands don't contaminate**: Boundary wells better than interior (counter-intuitive!)
7. **Block size matters**: 2×2 creates low-frequency patterns, single-well does not

### From Plate Class Formalization

8. **Two epistemic purposes**: Noise measurement vs robustness testing
9. **Metrics are contextual**: Valid only within appropriate plate class
10. **Specialized > compromised**: Two optimized instruments better than one hybrid

---

## Files Generated (Timeline)

### Investigation Arc
1. `docs/V2_V3_COMPARISON_RESULTS.md` (2025-12-22)
2. `docs/V3_V4_FINAL_COMPARISON.md` (2025-12-22)
3. `docs/V4_MECHANISM_REPORT.md` (2025-12-22)
4. `docs/V5_DESIGN_SUMMARY.md` (2025-12-22)
5. `docs/PLATE_DESIGN_INVESTIGATION_SUMMARY.md` (2025-12-22)

### Plate Class Formalization
6. `docs/PLATE_CLASS_SPECIFICATION.md` (2025-12-22)
7. `docs/PLATE_CLASS_IMPLEMENTATION_COMPLETE.md` (2025-12-22)
8. `docs/PLATE_DESIGN_EVOLUTION_TIMELINE.md` (2025-12-22) - **This document**

### Analysis Scripts
- `scripts/compare_v2_v3_qc.py`
- `scripts/compare_v3_v4_qc.py`
- `scripts/compare_boring_wells.py` (decisive test)
- `scripts/analyze_spatial_autocorrelation.py`
- `scripts/analyze_neighbor_coupling.py`

### Validation Scripts
- `scripts/validate_v4_islands.py`
- `scripts/validate_v5_hybrid.py`
- `scripts/validate_plate_class.py`

### Design Scripts
- `scripts/fix_v4_best.py`
- `scripts/create_v5_hybrid.py`
- `scripts/add_plate_class_metadata.py`

---

## Current Production Status

### ✅ V3: SCREENING Plate
- **Status**: Production ready
- **Use For**: Hit validation, spatial model testing, screening campaigns
- **Trust**: spatial_variance (1160 baseline), z_factor, hit_robustness
- **Don't Trust**: absolute_cv, technical_floor

### ✅ V4: CALIBRATION Plate
- **Status**: Production ready
- **Use For**: Assay QC, noise measurement, reproducibility monitoring
- **Trust**: island_cv (13% achieved), technical_floor, perturbation_effect
- **Don't Trust**: spatial_variance (inflated by design), row_col_decorrelation

### ⏳ V5: HYBRID Plate
- **Status**: Designed, validation passed, testing optional
- **Use For**: Exploratory - testing if both objectives achievable
- **Notes**: V3 + V4 already cover use cases; V5 useful for understanding boundary

### 🗄️ V2: Row Interleaving
- **Status**: Archived (superseded by V3)
- **Historical Value**: Established need for 2D decorrelation

---

## Quick Reference: When to Use Which Plate

### Use CALIBRATION (V4) When...
- Setting up new assay
- Measuring technical noise
- Comparing instruments
- Debugging high variance
- Characterizing perturbations
- Establishing baseline reproducibility

### Use SCREENING (V3) When...
- Validating hits
- Testing spatial correction
- Running screening campaigns
- Measuring robustness
- Breaking row/column confounds
- Stress-testing under realistic conditions

### Test HYBRID (V5) When...
- Exploring if both objectives achievable
- Understanding interaction between islands and mixing
- Research purposes (not production)

---

## Unanswered Questions

### About V5
- Does single-well alternation + islands preserve V3's spatial benefits?
- Do islands interfere with checkerboard at all?
- Are there interaction artifacts we didn't predict?

### About Simulator
- How much does simulator underestimate baseline variance? (vehicle islands 2-4% too low)
- Will wet lab V4 island CV be 10-30% as expected?
- Do real plates show same mechanism (2×2 blocks → spatial artifacts)?

### About Plate Classes
- Are there other epistemic classes beyond CALIBRATION/SCREENING?
- Do we need dose-response calibration plates?
- Do we need multi-day reproducibility plates?

---

## Retrospective: What Made This Work

### 1. Adversarial Testing
- Boring wells test (decisive - removed all confounds)
- Masking test (falsified contamination hypothesis)
- Proximity analysis (falsified neighbor coupling)

### 2. Mechanism Investigation
- Spatial autocorrelation (Moran's I)
- Variogram (scale-invariant variance)
- Row/column pattern analysis

### 3. Falsifiable Hypotheses
- Each test could have proven V4 "working"
- Hypotheses stated before testing
- Results trusted even when uncomfortable

### 4. Conceptual Reframing
- User insight: "Two incompatible objectives"
- Recognized plate class as epistemic instrument
- Stopped fighting phantom trade-off

### 5. Principled Resolution
- Formalized plate classes
- Defined metric contracts
- Made assumptions explicit

---

## Future Directions

### Short-Term
1. Test V5 (optional - understanding boundary)
2. Implement Phase 2 (analysis pipeline metric contracts)
3. Update frontend (display plate class, filter metrics)

### Medium-Term
4. Wet lab validation (V3 and V4 on real hardware)
5. Expand plate classes (dose-response, multi-day)
6. Cross-instrument standardization

### Long-Term
7. Generalize epistemic instrument concept
8. Apply to other experimental systems
9. Formalize design principles for mature experimental platforms

---

## Conclusion

**The investigation succeeded not by finding a "better" plate, but by discovering structure in the design space itself.**

What looked like competing designs were actually complementary instruments for different epistemic purposes.

**Status as of 2025-12-22**:
- ✅ V3 production ready (SCREENING)
- ✅ V4 production ready (CALIBRATION)
- ✅ Plate class system formalized
- ✅ Metric contracts defined
- ⏳ V5 designed (testing optional)

**Both V3 and V4 are valid, necessary, and production-ready in their respective roles.**

---

**End of Timeline**

For detailed analysis, see:
- [PLATE_CLASS_SPECIFICATION.md](PLATE_CLASS_SPECIFICATION.md) - Foundational specification
- [PLATE_DESIGN_INVESTIGATION_SUMMARY.md](PLATE_DESIGN_INVESTIGATION_SUMMARY.md) - Complete investigation arc
- [V3_V4_FINAL_COMPARISON.md](V3_V4_FINAL_COMPARISON.md) - Decisive findings
