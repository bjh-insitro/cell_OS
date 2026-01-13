# Hardware Artifacts - Seeding Complete

## ✅ PRODUCTION-READY: Seeding Artifacts

**Status**: VALIDATED and COMPLETE
**Validation Date**: 2024-12-23
**Process Modeled**: EL406 8-channel manifold, sequential row processing (median_manual_8ch preset)

---

## Implementation Summary

### 7 Artifact Components (All Working)

1. **Pin/valve biases** (8-channel manifold)
   - Each pin has deterministic volume offset
   - Observed CV: 2.74% (expected ~3%)
   - Pin 1 → rows A/I, Pin 2 → rows B/J, etc.

2. **Serpentine temporal gradient** (within-row)
   - ±4% gradient within each row
   - Odd rows (A,C,E,...): L→R processing, negative correlation
   - Even rows (B,D,F,...): R→L processing, positive correlation
   - Validated: 16/16 rows show correct pattern

3. **Plate-level drift** (row A→P)
   - 0.5% reagent depletion + thermal drift
   - Compounds with settling to produce ~8% total A→P drift

4. **Uncoupled roughness** (viability independence)
   - 25% of CV breaks perfect correlation
   - Within-row cells vs viability: r = 0.76 (realistic imperfection)

5. **Cell line-specific modifiers**
   - Attachment efficiency: 70% (neurons) to 95% (cancer cells)
   - Shear sensitivity: 0.7× (robust) to 2.0× (fragile)
   - Mechanical robustness: 0.5× (fragile) to 1.3× (hardy)

6. **Coating quality variation** (neurons only)
   - 8% plate-specific 2D spatial gradient
   - Only applied to cell lines with `coating_required: true`
   - Creates third independent spatial structure

7. **Cell suspension settling** (time-dependent)
   - 4% amplification of row A→P drift
   - Models cells settling in reservoir during 60-180s dispense
   - Compounds multiplicatively with other effects

---

## Validation Results

### Spatial Gradients
- **Corner-to-corner**: 12.1% (A1 → P24)
- **Row A→P drift**: 8.1% (first 4 rows vs last 4 rows)
- **Within-row serpentine**: ±4% (perfect alternating pattern)
- **Total CV**: 4.37% (realistic for liquid handling)

### Cell Line Differences
| Cell Line | Mean Cells | Attachment | Viability | Shear | Coating |
|-----------|------------|------------|-----------|-------|---------|
| HepG2     | 14,066     | 90%        | 0.9378    | 1.0×  | No      |
| iPSC_NGN2 | 11,806     | 70%        | 0.8960    | 2.0×  | Yes     |
| U2OS      | 11,878     | 95%        | 0.9494    | 0.7×  | No      |

### Correlation Structure
- **Overall correlation**: 0.06 (correct! Low because serpentine reverses trends)
- **Within-row correlation**: 0.76 mean (range 0.67-0.86)
- **Pin-to-pin variation**: 2.74% CV

---

## Process Presets

### Default: median_manual_8ch
- **Expected A→P drift**: 5-10%
- **Process**: EL406 8-channel pipette, sequential rows, no remix
- **Settings**: `cell_suspension_settling_cv = 0.04`
- **Philosophy**: "Median day, not best day" - makes spatial QC non-optional

### Alternative: bestday_bulk_agitated
- **Expected A→P drift**: 1-3%
- **Process**: Automated bulk dispenser with agitation (Multidrop, Certus)
- **Settings**: `cell_suspension_settling_cv = 0.015`
- **Use when**: Modeling best-case automated liquid handling

### Alternative: neurons_gentle_coated
- **Expected A→P drift**: 8-12%
- **Process**: iPSC neurons, coated plates, gentle handling
- **Settings**: `cell_suspension_settling_cv = 0.05-0.06`
- **Use when**: Fragile primary cells with coating requirements

---

## Technical Details

### Parameter Values
```yaml
technical_noise:
  pin_cv: 0.03                         # Pin-to-pin variation
  temporal_gradient_cv: 0.04           # Within-row serpentine
  plate_level_drift_cv: 0.005          # Reagent/thermal drift
  roughness_cv: 0.05                   # Mechanical stress
  coating_quality_cv: 0.08             # Coating spatial variation
  cell_suspension_settling_cv: 0.04    # Settling amplification (DEFAULT)
```

### Deterministic Seeding
- Same `(plate_id, well_position, seed)` → same artifacts
- Learnable by agents (no purely random components)
- Independent RNG streams prevent order dependence

### Integration Points
- `src/cell_os/hardware/hardware_artifacts.py`: Core calculation
- `src/cell_os/hardware/biological_virtual.py`: seed_vessel() integration
- `data/cell_thalamus_params.yaml`: Parameter configuration

---

## Why 8% A→P Drift is Realistic

The observed ~8% drift is **not** a simple sum (4% + 0.5% = 4.5%). Effects compound:

### Compounding Math
```
Effective drift = settling(t) × plate_drift × pin_correlation_with_time
```

Where:
- **Settling** is time-dependent (not static 4%)
- **Pin biases** correlate with traversal order (not purely random)
- **Attachment efficiency** amplifies initial concentration differences

### When 8-10% Happens in Real World
- Multi-dispense time is 60-180s (cells settle during process)
- Source mixing is imperfect (no aggressive remix between rows)
- Aspiration height stays fixed (samples different suspension layers)
- 8-channel manifolds have consistent traversal order
- Viscosity/clumping makes settling non-linear

### Spatial QC Validation
This drift level ensures:
- Row effects are detectable (agents must learn to deconfound)
- Spatial artifacts aren't trivial (2% would be too polite)
- QC matters (can't ignore plate position)

---

## Test Coverage

### Validated
✅ Serpentine pattern (16/16 rows correct)
✅ Pin biases (2.74% CV)
✅ Cell line differences (attachment, shear, robustness)
✅ Correlation structure (0.76 within-row)
✅ Coating effects (neurons only)
✅ Settling amplification (8% A→P drift)
✅ Deterministic reproduction (same seed → same result)

### Test Scripts
- `scripts/test_cellline_hardware_artifacts.py`: 3×3 panel comparison
- `scripts/test_seeding_hardware_artifacts.py`: Spatial validation

---

## Next Steps

**Seeding artifacts are COMPLETE and production-ready.**

Future work (NOT in scope for Phase 0):
- Feeding artifacts validation
- Cell Painting artifacts validation
- 96-well plate testing
- Certus differentiation (complex plate maps)
- Instrument calibration drift over time
