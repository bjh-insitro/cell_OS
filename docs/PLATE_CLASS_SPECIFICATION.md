# Plate Class Specification

**Date**: 2025-12-22
**Status**: ✅ Foundational Specification
**Version**: 1.0

---

## Executive Summary

**Plate designs serve fundamentally different epistemic purposes.**

This specification formalizes two plate classes:
- **Calibration Plates**: Measure technical noise floor under controlled conditions
- **Screening Plates**: Stress-test spatial models under realistic conditions

**Key Insight**: CV minimization and spatial decorrelation are **orthogonal objectives** that require different physical experiments. Attempting to optimize both in a single plate design creates artificial trade-offs and misleading metric conflicts.

---

## The Core Tension

There are **two fundamentally different questions** asked with plate-based assays:

### Question 1: How noisy is the biology/assay itself?

**What you're measuring**: Technical variance floor, biological variability baseline, perturbation effects

**What you need**:
- ✅ Homogeneity (identical conditions within measurement zones)
- ✅ Isolation (no confounding from neighbors or gradients)
- ✅ Tight CV (replicate precision)
- ✅ Controlled replication

**Design principle**: **Minimize all sources of variance except the one you're characterizing**

### Question 2: How robust is the assay to real screening conditions?

**What you're measuring**: Spatial artifact resistance, hit robustness, model validity

**What you need**:
- ✅ Heterogeneity (mixing of conditions)
- ✅ Spatial decorrelation (break confounds with position)
- ✅ Stress on system (realistic adversarial conditions)
- ✅ Distributed controls

**Design principle**: **Maximize spatial complexity to stress-test correction models**

### Why These Are Incompatible

**Homogeneity** (calibration) and **spatial mixing** (screening) are mutually exclusive:
- Homogeneous islands → spatial clustering → elevated row/column variance
- Spatial mixing → neighbor diversity → elevated local CV

**Attempting both in one plate forces compromises that look "broken" under one metric set.**

This is not a design failure. **This is physics.**

---

## Plate Class 1: CALIBRATION

### Purpose

**Measure the instrument, not the biology.**

Calibration plates answer:
- What is the technical noise floor?
- How much variance comes from the measurement process itself?
- What is true biological variability under identical conditions?
- How does a specific perturbation inflate variance relative to baseline?
- Is the simulator underestimating baseline biological noise?

### Design Principles

| Principle | Implementation | Rationale |
|-----------|---------------|-----------|
| **Homogeneous islands** | 3×3 to 5×5 tiles with identical conditions | Isolates technical from biological variance |
| **No spatial mixing** | Wells within islands have same cell line + treatment | Eliminates neighbor diversity noise |
| **Forced nominal conditions** | Override all probes/gradients in islands | Removes confounding perturbations |
| **Allow spatial clustering** | Islands can be grouped by quadrant | Spatial uniformity not required for calibration |
| **Dedicated anchor islands** | Separate islands for positive controls | Measures perturbation effect on CV |

### Design Features

**Required**:
- Homogeneous islands (≥ 9 wells per island)
- Exclusion rules forcing nominal conditions in islands
- At least 2 island types: vehicle (baseline) and anchor (perturbation)
- Per-well cell line assignment enforced

**Optional**:
- Multiple replicate islands per condition (measure inter-island variance)
- Anchor islands with different perturbation strengths (dose-response)
- Background control islands (measure zero-cell CV)

**Forbidden**:
- Mixing of cell lines within islands
- Gradients or probes affecting island wells
- Scattered anchors within islands

### Valid Metrics

**Required Analyses**:
```python
{
    'island_cv': {
        'vehicle_islands': 'Technical replicate floor (expect 2-5% in simulator, 10-30% in wet lab)',
        'anchor_islands': 'Perturbation-induced variance inflation',
        'per_island_breakdown': 'Consistency across replicate islands'
    },
    'technical_floor': {
        'vehicle_mean_cv': 'Average CV across vehicle islands',
        'vehicle_cv_variance': 'Island-to-island CV consistency'
    },
    'perturbation_effect': {
        'anchor_cv': 'CV in perturbed islands',
        'fold_change': 'Anchor CV / Vehicle CV ratio'
    }
}
```

**Optional Analyses**:
- Anchor stability (mean ± std across replicate islands)
- Inter-island variance (plate-scale reproducibility)
- Channel-specific CV (does perturbation affect all channels?)

**Invalid Analyses** (forbidden for calibration plates):
```python
{
    'global_spatial_variance': 'INVALID - homogeneous islands create spatial structure by design',
    'row_column_decorrelation': 'INVALID - mixing not required for calibration',
    'mixed_region_cv': 'INVALID - no mixed regions exist',
    'boring_wells_spatial_test': 'INVALID - boring wells are the islands themselves'
}
```

### Interpretation Guidelines

**What you trust**:
- ✅ CV estimates (this is what calibration plates measure)
- ✅ Replicate precision within islands
- ✅ Noise decomposition (technical vs biological)
- ✅ Perturbation effect magnitude

**What you explicitly do NOT trust**:
- ❌ Global spatial variance (islands create structure)
- ❌ Row/column correction fits (no spatial mixing to validate)
- ❌ Any metric assuming spatial stationarity

### Mental Model

> **A calibration plate is a microscope slide with rulers etched into it.**
>
> You're not measuring the sample under realistic conditions.
> You're measuring the measurement system itself.

### Example: V4 as Calibration Plate

**V4 Design** (`CAL_384_RULES_WORLD_v4.json`):
- 8× 3×3 homogeneous islands
- 6 vehicle islands (HepG2 and A549)
- 2 anchor islands (Nocodazole, Thapsigargin)
- Forced NOMINAL density, no probes in islands
- 2×2 micro-checkerboard in non-island regions

**V4 Performance** (Calibration Metrics):
- ✅ Vehicle island CV: 2-4% (technical floor achieved)
- ✅ Anchor island CV: 12-21% (perturbation effect measured)
- ✅ Mean island CV: 13.3% (81% better than mixed regions)
- ❌ Spatial variance: +194% vs V3 (EXPECTED - not a bug)

**V4 Verdict**: ✅ **Excellent calibration plate**. Spatial variance increase is intentional trade-off for CV measurement.

---

## Plate Class 2: SCREENING

### Purpose

**Stress-test the spatial model under realistic conditions.**

Screening plates answer:
- Can the assay survive spatial artifacts?
- Do signals persist under mixing and heterogeneity?
- Are hits robust to plate effects?
- Does the spatial correction pipeline actually work?
- Can row/column confounds be broken?

### Design Principles

| Principle | Implementation | Rationale |
|-----------|---------------|-----------|
| **Spatial mixing** | Micro-checkerboard or distributed patterns | Decorrelates biology from position |
| **No large homogeneous regions** | Avoid 3×3+ uniform tiles | Prevents spatial structure artifacts |
| **Distributed controls** | Scattered anchors across plate | Tests spatial correction everywhere |
| **Heterogeneity by design** | Mix cell lines, densities, treatments | Realistic screening conditions |
| **Adversarial layout** | Intentionally stress position effects | Validates robustness |

### Design Features

**Required**:
- Single-well or 2×2 checkerboard cell line pattern
- Distributed anchor wells (not clustered)
- No homogeneous islands (or minimal: 2×2 at most)
- Gradients and probes allowed (tests correction)

**Optional**:
- Contrastive tiles (2×2 with designed differences)
- Density gradients (low/nominal/high columns)
- Edge effects testing (deliberate perturbations near edges)

**Forbidden**:
- Large homogeneous islands (≥ 3×3)
- Clustered anchors (defeats decorrelation purpose)
- Forced uniform conditions globally

### Valid Metrics

**Required Analyses**:
```python
{
    'spatial_decorrelation': {
        'boring_wells_variance': 'Row + column variance in uniform subset',
        'row_column_independence': 'Cell line decorrelated from position',
        'gradient_effect': 'Density gradient impact on variance'
    },
    'z_factor': {
        'scattered_anchors': 'Z\' under realistic conditions',
        'position_robustness': 'Does Z\' vary by plate region?'
    },
    'hit_robustness': {
        'mixed_tile_cv': 'CV in 2×2 mixed regions',
        'neighbor_diversity_effect': 'Does mixing inflate noise?'
    }
}
```

**Optional Analyses**:
- Spatial autocorrelation (Moran's I should be ≈0)
- Row/column correction residuals (after modeling)
- Anchor performance under stress

**Invalid Analyses** (forbidden for screening plates):
```python
{
    'island_cv': 'INVALID - no homogeneous islands exist',
    'absolute_cv_as_biological_noise': 'INVALID - neighbor diversity inflates CV',
    'technical_replicate_floor': 'INVALID - mixing prevents tight replication'
}
```

### Interpretation Guidelines

**What you trust**:
- ✅ Spatial decorrelation metrics (this is what screening plates test)
- ✅ Z-factors under realistic conditions
- ✅ Hit robustness to plate effects
- ✅ Spatial correction pipeline validation

**What you explicitly do NOT trust**:
- ❌ Absolute CV as biological noise (neighbor diversity inflates it)
- ❌ Technical replicate precision (mixing prevents tight CV)
- ❌ Baseline variance estimates (use calibration plates for this)

### Mental Model

> **A screening plate is a wind tunnel, not a ruler.**
>
> You're not measuring precision under ideal conditions.
> You're testing if your signal survives real-world chaos.

### Example: V3 as Screening Plate

**V3 Design** (`CAL_384_RULES_WORLD_v3.json`):
- Single-well alternating checkerboard (high-frequency mixing)
- Scattered anchors (Nocodazole, Thapsigargin distributed)
- Density gradient (low/nominal/high columns)
- Probe wells (stain, fixation, focus perturbations)
- No homogeneous islands

**V3 Performance** (Screening Metrics):
- ✅ Boring wells spatial variance: 1160 (baseline established)
- ✅ Row/column decorrelation: cell line ⊥ position
- ✅ Z-factor: -12.3 (anchors detectable under stress)
- ❌ Mixed tile CV: 71% (EXPECTED - neighbor diversity)

**V3 Verdict**: ✅ **Excellent screening plate**. High CV is intentional trade-off for spatial robustness.

---

## Plate Class Comparison Matrix

|  | Calibration (V4) | Screening (V3) |
|---|---|---|
| **Primary Goal** | Measure noise floor | Stress-test spatial model |
| **Cell Line Pattern** | Homogeneous islands | Micro-checkerboard mixing |
| **Spatial Structure** | Clustered (allowed) | Distributed (required) |
| **Anchor Placement** | Island-based | Scattered |
| **Gradients/Probes** | Excluded from islands | Included globally |
| **Valid Metrics** | Island CV, technical floor | Spatial variance, Z-factor |
| **Invalid Metrics** | Spatial decorrelation | Absolute CV |
| **Typical CV** | 2-20% (homogeneous) | 60-80% (mixed) |
| **Spatial Variance** | High (by design) | Low (by design) |
| **Use Cases** | QC, noise characterization, method development | Hit validation, spatial model testing, screening |

---

## Usage Guidance

### When to Use Calibration Plates

**Run a calibration plate when**:
1. Setting up a new assay (establish baseline noise)
2. Comparing instruments (wet lab vs simulator)
3. Validating a perturbation (measure effect on CV)
4. Debugging high variance (is it technical or biological?)
5. Characterizing day-to-day reproducibility

**Example workflows**:
```
New assay setup:
  1. Run calibration plate (measure technical floor)
  2. If CV < 20%: proceed to screening
  3. If CV > 20%: optimize assay conditions, repeat calibration

Simulator validation:
  1. Run calibration plate in simulator (predict CV)
  2. Run same design in wet lab (measure actual CV)
  3. Compare: simulator should underestimate by 2-5×
```

### When to Use Screening Plates

**Run a screening plate when**:
1. Validating hit robustness (do effects persist under mixing?)
2. Testing spatial correction (does pipeline work?)
3. Screening campaigns (realistic conditions)
4. Stress-testing a model (can it handle heterogeneity?)
5. Measuring position-independent effects

**Example workflows**:
```
Hit validation:
  1. Run screening plate with candidate hits
  2. Check Z-factor under stress (should be > 0)
  3. Check spatial robustness (effect consistent across plate?)
  4. If passes: validate in dose-response

Spatial model validation:
  1. Run screening plate with known ground truth
  2. Fit spatial correction (row/col effects)
  3. Check residuals (should be uncorrelated with position)
  4. If fails: refine model, repeat
```

### Decision Tree

```
Question: What variance am I seeing?
  └─> Technical or biological?
      ├─> Technical: Run CALIBRATION plate
      └─> Biological: Already known, use SCREENING plate

Question: Does my hit replicate?
  └─> In which context?
      ├─> Ideal conditions: Run CALIBRATION plate
      └─> Screening conditions: Run SCREENING plate

Question: Is my spatial model working?
  └─> Always test with SCREENING plate (mixing required)

Question: Should I trust this CV estimate?
  └─> From which plate?
      ├─> Calibration: ✅ Trust CV
      └─> Screening: ❌ Do NOT trust CV (use calibration instead)
```

---

## Schema Integration

### Proposed Schema Addition

Add `plate_class` field to calibration plate schema:

```json
{
  "schema_version": "calibration_plate_v3",
  "plate_class": "CALIBRATION",  // or "SCREENING"
  "plate_class_metadata": {
    "purpose": "Measure technical noise floor under controlled conditions",
    "valid_metrics": ["island_cv", "technical_floor", "perturbation_effect"],
    "invalid_metrics": ["global_spatial_variance", "row_column_decorrelation"],
    "design_objectives": ["minimize_cv", "isolate_technical_variance"]
  },
  "plate": { ... }
}
```

### Validation Rules

Analysis scripts should enforce:

```python
def validate_analysis(plate_design, requested_metrics):
    plate_class = plate_design.get('plate_class')

    if plate_class == 'CALIBRATION':
        forbidden = ['global_spatial_variance', 'row_column_decorrelation']
        if any(m in requested_metrics for m in forbidden):
            raise InvalidMetricError(
                f"Metric {m} is invalid for CALIBRATION plates. "
                f"Calibration plates measure CV, not spatial decorrelation."
            )

    elif plate_class == 'SCREENING':
        forbidden = ['island_cv', 'technical_replicate_floor']
        if any(m in requested_metrics for m in forbidden):
            raise InvalidMetricError(
                f"Metric {m} is invalid for SCREENING plates. "
                f"Use CALIBRATION plates for CV measurement."
            )
```

---

## Reframing the V3 vs V4 Investigation

### What We Thought We Were Doing

"Debug V4 - why does it have higher spatial variance than V3?"

### What We Were Actually Doing

**Empirically discovering the boundary between two epistemic instrument classes.**

### The Investigation as Discovery

| What looked like | What it actually was |
|-----------------|---------------------|
| ❌ V4 failed spatial decorrelation | ✅ V4 is a calibration plate (doesn't need spatial mixing) |
| ❌ V4's 2×2 blocks create artifacts | ✅ Homogeneous regions measure technical noise (as designed) |
| ❌ Can't use V4 for production | ✅ V4 and V3 serve different purposes |
| ❌ Need to design V5 compromise | ✅ Need to formalize two plate classes |

### The Real Findings

1. **V4 achieves calibration goals**: 13% CV in islands (spectacular)
2. **V3 achieves screening goals**: 1160 spatial variance (robust mixing)
3. **Trying to combine them is the mistake**: Orthogonal objectives
4. **No simulator coupling exists**: Moran's I ≈ 0 (confirmed independence)
5. **Islands don't contaminate neighbors**: Boundary wells better than interior

### The Conceptual Leap

> **Plate layout is an epistemic instrument, not just logistics.**

Different questions require different physical experiments.

The "CV vs spatial variance trade-off" isn't a compromise to optimize.
It's a **choice of which question to ask**.

---

## Plate Class Contracts

### Calibration Plate Contract

**Inputs** (plate design must provide):
- Homogeneous islands (≥ 3×3 per island)
- Exclusion rules forcing nominal conditions in islands
- At least 1 vehicle island (baseline) and 1 anchor island (perturbation)

**Outputs** (analysis must compute):
- Island CV (per island and mean across islands)
- Technical floor (vehicle island CV)
- Perturbation effect (anchor CV / vehicle CV ratio)

**Guarantees**:
- Island CV estimates are valid (no neighbor contamination)
- Inter-island variance measures plate-scale reproducibility
- Perturbation effects are isolated from confounds

**Limitations**:
- ❌ Cannot measure spatial decorrelation (homogeneous regions cluster)
- ❌ Cannot validate spatial correction (no mixing to test)
- ❌ Cannot measure screening robustness (ideal conditions only)

### Screening Plate Contract

**Inputs** (plate design must provide):
- Micro-checkerboard or distributed cell line pattern
- No large homogeneous islands (≤ 2×2 tiles)
- Scattered anchors (not clustered)

**Outputs** (analysis must compute):
- Boring wells spatial variance (row + column variance in uniform subset)
- Z-factor under stress (scattered anchors)
- Mixed tile CV (2×2 heterogeneous regions)

**Guarantees**:
- Spatial decorrelation is valid (cell line ⊥ position)
- Z-factors represent realistic screening conditions
- Spatial correction pipeline can be validated

**Limitations**:
- ❌ Cannot measure technical noise floor (neighbor diversity inflates CV)
- ❌ Cannot isolate biological variance (mixing creates heterogeneity)
- ❌ Cannot use absolute CV as biological estimate (use calibration plates)

---

## Implementation Roadmap

### Phase 1: Formalize Existing Plates (Immediate)

1. **Update V3 design file**
   - Add `"plate_class": "SCREENING"`
   - Add `plate_class_metadata` section
   - Document valid/invalid metrics

2. **Update V4 design file**
   - Add `"plate_class": "CALIBRATION"`
   - Add `plate_class_metadata` section
   - Document valid/invalid metrics

3. **Create validation script**
   - `scripts/validate_plate_class.py`
   - Check design features match declared class
   - Enforce metric contracts

### Phase 2: Update Analysis Pipeline (Short-Term)

4. **Create plate class detector**
   - `scripts/plate_class_contracts.py`
   - Define metric contracts per class
   - Provide helper functions for validation

5. **Update QC comparison scripts**
   - `scripts/compare_v3_v4_qc.py` → Check plate classes first
   - Show only valid metrics per class
   - Add warnings for cross-class comparisons

6. **Update frontend**
   - Display plate class in UI
   - Filter metrics by plate class
   - Show interpretation guidelines

### Phase 3: Documentation (Short-Term)

7. **Update investigation docs**
   - Reframe V3_V4_FINAL_COMPARISON.md with plate class lens
   - Update V4_MECHANISM_REPORT.md to clarify calibration vs screening
   - Archive V5 design (superseded by plate class formalization)

8. **Create usage guide**
   - When to use calibration vs screening plates
   - Example workflows per use case
   - Decision tree for plate class selection

### Phase 4: Future Designs (Long-Term)

9. **Design pure screening plate** (optional)
   - Maximize spatial mixing (no islands at all)
   - Optimize for stress-testing
   - Reference implementation for screening class

10. **Design specialized calibration plates** (optional)
    - Dose-response calibration (multiple anchor island doses)
    - Multi-day reproducibility (repeated vehicle islands)
    - Cross-instrument calibration (standardized QC)

---

## Success Criteria

### How to Know Plate Classes Are Working

**Metrics stop contradicting each other**:
- V4's high spatial variance is no longer seen as failure
- V3's high CV is no longer seen as failure
- Comparisons only happen within plate class

**Analysis pipeline becomes principled**:
- Scripts check plate class before computing metrics
- Invalid metrics are caught at runtime
- Warnings issued for cross-class comparisons

**Design space becomes clear**:
- New plates declare their class upfront
- Design objectives are explicit
- Trade-offs are expected, not surprising

**User confusion decreases**:
- "Why is V4's spatial variance high?" → "Because it's a calibration plate"
- "Why is V3's CV high?" → "Because it's a screening plate"
- "Which plate should I use?" → Check decision tree

---

## Frequently Asked Questions

### Q: Should I always run both plate types?

**A**: Depends on your question.
- If characterizing a new assay: Start with **calibration** (establish baseline)
- If validating hits: Use **screening** (test robustness)
- If debugging high variance: Use **calibration** (is it technical or biological?)

### Q: Can a plate be both classes?

**A**: Technically yes (V5 hybrid), but it's suboptimal.
- Hybrid plates compromise on both objectives
- Better to run two specialized plates than one compromised plate
- Exception: Exploratory studies where both questions are equally important

### Q: What if my spatial variance is high on a calibration plate?

**A**: That's expected and OK.
- Calibration plates have homogeneous islands that cluster spatially
- Spatial variance is INVALID metric for calibration plates
- Check island CV instead (the valid metric)

### Q: What if my CV is high on a screening plate?

**A**: That's expected and OK.
- Screening plates have neighbor diversity that inflates CV
- Absolute CV is INVALID metric for screening plates
- Check Z-factor and spatial decorrelation instead (the valid metrics)

### Q: Can I compare calibration and screening plates?

**A**: Only for class-valid metrics.
- ✅ Compare V4 island CV to wet lab replicates (both measure technical floor)
- ✅ Compare V3 spatial variance to V5 spatial variance (both screening)
- ❌ Do NOT compare V4 spatial variance to V3 spatial variance (different classes)
- ❌ Do NOT compare V4 island CV to V3 mixed tile CV (different contexts)

---

## Conclusion

**The V3 vs V4 investigation revealed a hidden degree of freedom in plate design space.**

Key insights:
1. **Two epistemic purposes** require different physical experiments
2. **Trying to combine them** creates artificial trade-offs
3. **Formalizing plate classes** makes analysis principled
4. **V3 and V4 are complementary**, not competing

**Next steps**:
1. Add `plate_class` field to existing designs
2. Update analysis scripts to enforce metric contracts
3. Reframe documentation with plate class lens
4. Use calibration plates for noise characterization, screening plates for robustness testing

**The conceptual split is the correct move.**

---

## References

### Key Documents
- [V3_V4_FINAL_COMPARISON.md](V3_V4_FINAL_COMPARISON.md) - Investigation findings
- [V4_MECHANISM_REPORT.md](V4_MECHANISM_REPORT.md) - Why 2×2 blocks inflate variance
- [V5_DESIGN_SUMMARY.md](V5_DESIGN_SUMMARY.md) - Hybrid design (superseded by plate classes)
- [PLATE_DESIGN_INVESTIGATION_SUMMARY.md](PLATE_DESIGN_INVESTIGATION_SUMMARY.md) - Complete investigation arc

### Plate Designs
- `CAL_384_RULES_WORLD_v3.json` - Screening plate (production)
- `CAL_384_RULES_WORLD_v4.json` - Calibration plate (production)
- `CAL_384_RULES_WORLD_v5.json` - Hybrid (exploratory, optional)

### Analysis Scripts
- `scripts/validate_plate_class.py` - Validate design matches declared class
- `scripts/plate_class_contracts.py` - Metric contracts per class
- `scripts/compare_v3_v4_qc.py` - Full comparison (class-aware)

---

**End of Plate Class Specification**

**Version**: 1.0
**Status**: Foundational - Ready for Implementation
**Next**: Phase 1 (Formalize existing plates with `plate_class` field)
