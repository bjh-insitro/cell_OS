# CAL_384 Plate Executor - Parser Complete

**Status**: Parser + WellSpec generation complete. Full execution requires integration work.

---

## What Was Built

### 1. Plate Design Parser (~200 LOC)

**File**: `src/cell_os/plate_executor.py`

**Function**: `parse_plate_design_v2(json_path) → List[ParsedWell]`

Parses `CAL_384_RULES_WORLD_v2.json` with full resolution precedence logic:

```
Resolution Order (first match wins):
1. background_controls.wells_no_cells (8 wells)
2. contrastive_tiles[].assignment (8 tiles × 4 wells = 32 wells)
3. biological_anchors.wells (31 wells: Nocodazole + Thapsigargin)
4. non_biological_provocations:
   - stain_scale_probes (32 wells)
   - fixation_timing_probes (16 wells)
   - imaging_focus_probes (16 wells)
5. cell_density_gradient by column (LOW: cols 1-8, NOMINAL: 9-16, HIGH: 17-24)
6. global_defaults.default_assignment (all remaining wells)
```

**Derived fields**:
- `cell_line`: From `row_to_cell_line` map (interleaved HepG2/A549)
- `cell_density`: From column-based gradient (unless overridden)
- `stain_scale`: 1.0 unless in STAIN_LOW (0.9) or STAIN_HIGH (1.1) wells
- `fixation_timing_offset_min`: 0 unless in EARLY_FIX (-15) or LATE_FIX (+15) wells
- `imaging_focus_offset_um`: 0 unless in FOCUS_MINUS (-2) or FOCUS_PLUS (+2) wells

**Output**: 384 `ParsedWell` objects with complete metadata

---

### 2. WellSpec Converter

**Function**: `parsed_wells_to_wellspecs(parsed_wells) → List[WellSpec]`

Converts `ParsedWell` → `WellSpec` for simulation:

```python
WellSpec(
    cell_line="HepG2",
    compound="Nocodazole",
    dose_uM=0.3,
    time_h=48.0,
    position_tag="A9",  # Includes density markers if applicable
    assay=AssayType.CELL_PAINTING
)
```

**Special handling**:
- DMSO/VEHICLE wells → `compound="DMSO"`
- NO_CELLS wells → `compound="NO_CELLS"` (background controls)
- Position tags encode density: `"A1_dens_low"`, `"A24_dens_high"`, etc.

---

### 3. Demo Script

**File**: `scripts/run_cal_384_v2.py`

Demonstrates parsing and summarizes plate structure:

```bash
python3 scripts/run_cal_384_v2.py
```

**Output**:
- 384 wells parsed
- Treatment distribution (81.5% VEHICLE, 4.2% anchors, etc.)
- Cell density gradient (32.3% LOW, 33.3% NOMINAL, 32.3% HIGH)
- Non-biological provocations (32 stain probes, 16 timing, 16 focus)
- Example wells with full metadata

---

## Plate Design Structure

### CAL_384_RULES_WORLD_v2 Composition

| Category | Wells | Purpose |
|----------|-------|---------|
| **VEHICLE** | 313 (81.5%) | Baseline measurements |
| **ANCHOR_MORPH** (Nocodazole 0.3µM) | 16 + 4 tile = 20 | Strong morphology reference |
| **ANCHOR_DEATH** (Thapsigargin 0.05µM) | 15 + 4 tile = 19 | Stress + LDH reference |
| **VEHICLE_TILE** | 16 | Local repeatability check (2×2 tiles in corners) |
| **NO_CELLS** | 8 | Background controls |
| **Density probes** | 8 (4 LOW, 4 HIGH tiles) | Stress density-driven confounds |

### Non-Biological Provocations

| Probe Type | Wells | Values | Purpose |
|------------|-------|--------|---------|
| **Stain scale** | 32 | 0.9× (col 6), 1.1× (col 19) | Test normalization assumptions |
| **Fixation timing** | 16 | -15 min (early), +15 min (late) | Test timing sensitivity |
| **Focus offset** | 16 | -2µm (col 1), +2µm (col 24) | Test focus robustness |

### Interleaved Cell Lines (breaks spatial confounds)

```
Row A: HepG2    Row I: HepG2
Row B: A549     Row J: A549
Row C: HepG2    Row K: HepG2
Row D: A549     Row L: A549
Row E: HepG2    Row M: HepG2
Row F: A549     Row N: A549
Row G: HepG2    Row O: HepG2
Row H: A549     Row P: A549
```

### Density Gradient (by column)

```
Columns 1-8:   LOW density (0.7× nominal)
Columns 9-16:  NOMINAL density (1.0×)
Columns 17-24: HIGH density (1.3×)
```

---

## What's NOT Yet Built

### Full Execution Pipeline

**Current state**: Parser generates `List[WellSpec]` ✅

**Missing**: Batch execution through `BiologicalVirtualMachine`

**Why it's not trivial**:
1. **Independent wells**: Each well is a separate physical vessel
2. **State management**: BiologicalVirtualMachine needs vessel lifecycle per well
3. **Compound library**: Need IC50 values for Nocodazole, Thapsigargin
4. **Batch processing**: 384 wells × 48h simulation = significant compute

### Option A: Use ExperimentalWorld

**Approach**: Convert `List[WellSpec]` → `Proposal` → `ExperimentalWorld.run_experiment()`

**Pros**:
- Reuses existing epistemic agent infrastructure
- Already handles BiologicalVirtualMachine lifecycle
- Built-in observation aggregation

**Cons**:
- ExperimentalWorld expects agent-driven proposals (hypothesis, reasoning)
- Calibration plate is NOT hypothesis-driven (it's measurement characterization)

### Option B: Direct BiologicalVirtualMachine Batch Execution

**Approach**: Custom batch executor that:
1. Creates one VM per well (or reuses VM with vessel reset)
2. Seeds vessel with appropriate cell line + density
3. Applies treatment (compound + dose)
4. Advances time to 48h
5. Executes Cell Painting assay
6. Collects results

**Pros**:
- Direct control over execution
- No epistemic agent overhead
- Cleaner for calibration plates

**Cons**:
- Need to implement vessel lifecycle
- Need compound library integration
- No reuse of existing infrastructure

---

## Recommendation

**For calibration plates**, use **Option B** (direct batch execution):

1. **Add compound library** with IC50 values for anchors:
   ```python
   CALIBRATION_COMPOUNDS = {
       "Nocodazole": {"IC50_HepG2": 0.5, "IC50_A549": 0.6, "mechanism": "MICROTUBULE"},
       "Thapsigargin": {"IC50_HepG2": 0.08, "IC50_A549": 0.10, "mechanism": "ER_STRESS"}
   }
   ```

2. **Implement batch executor** (~150 LOC):
   ```python
   def execute_calibration_plate(wellspecs: List[WellSpec], seed: int) -> PlateResults:
       vm = BiologicalVirtualMachine(seed=seed)
       results = []

       for ws in wellspecs:
           # Create vessel
           vessel_id = f"well_{ws.position_tag}"
           density_scale = parse_density_from_position(ws.position_tag)
           vm.seed_vessel(vessel_id, ws.cell_line, initial_count=1e6 * density_scale)

           # Apply treatment
           if ws.compound != "DMSO":
               vm.add_treatment(vessel_id, ws.compound, ws.dose_uM)

           # Advance time
           vm.advance_time(ws.time_h)

           # Measure
           result = vm.cell_painting_assay(vessel_id)
           results.append(result)

       return PlateResults(wellspecs, results)
   ```

3. **LOC estimate**: ~150 lines for batch executor + compound library

---

## What You Can Do Now

**Immediately** (parser is complete):
```bash
python3 scripts/run_cal_384_v2.py
```

This shows:
- ✅ 384 wells parsed correctly
- ✅ Interleaved cell lines (HepG2/A549)
- ✅ Density gradient (LOW/NOMINAL/HIGH)
- ✅ Biological anchors (Nocodazole, Thapsigargin)
- ✅ Non-biological provocations (stain, timing, focus)
- ✅ Background controls (NO_CELLS)
- ✅ WellSpec objects ready for simulation

**Next** (requires batch executor):
- Simulate all 384 wells
- Generate Cell Painting morphology data
- Analyze calibration results:
  - Spatial correction models
  - Noise floor per feature family
  - Sensitivity to stain/timing/focus
  - Anchor orthogonality check

---

## Files Created

**Implementation**:
- `src/cell_os/plate_executor.py` (~200 LOC)

**Scripts**:
- `scripts/run_cal_384_v2.py` (~120 LOC)

**Documentation**:
- `docs/CAL_384_PLATE_EXECUTOR_COMPLETE.md` (this file)

**Test**:
- `test_cal_384_v2_execution.py` (diagnostic script)

---

## Summary

**Parser complete** ✅
- JSON → ParsedWell → WellSpec conversion working
- All resolution precedence rules implemented
- Density gradient, provocations, anchors, tiles all handled

**Full execution** ⏸️
- Requires batch executor (~150 LOC)
- Requires compound library for anchors
- Straightforward to implement when needed

**LOC**: ~320 lines (parser + script + docs)

**Next step**: Implement batch executor if you want to run full 384-well simulation.
