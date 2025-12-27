# Bead and Dye Simulator Extension Design

**Date:** 2025-12-26
**Status:** Design → Implementation
**Goal:** Extend BiologicalVirtualMachine to support non-biological calibration materials (beads, dyes, buffer) for detector calibration

---

## 1. Problem Statement

Current simulator assumes all wells contain cells with biology (viability, compounds, growth). The bead plate (`CAL_384_MICROSCOPE_BEADS_DYES_v1.json`) requires:

- **DARK wells**: buffer only (camera baseline, read noise)
- **FLATFIELD_DYE_LOW/HIGH**: uniform fluorescent dye solutions (no biology, known intensity)
- **MULTICOLOR_BEADS**: sparse/dense bead distributions (known intensities, spatial patterns)
- **FOCUS_BEADS**: bright beads for autofocus mapping

These materials have:
- **No biology**: no viability, no growth, no compound effects
- **Known optical properties**: fixed intensities per channel
- **Spatial structure**: uniform (dyes) vs sparse/dense (beads)
- **Deterministic behavior**: no biology variance, only detector noise

---

## 2. Design Principles

1. **Minimal disruption**: Don't break existing VesselState or Cell Painting pipeline
2. **Material type dispatch**: Branch on material type early, route to appropriate simulator
3. **Reuse detector stack**: Beads/dyes go through SAME detector (floor, saturation, quantization)
4. **No biology coupling**: Material measurements don't touch VesselState biology fields
5. **Backwards compatibility**: Existing tests/code work unchanged

---

## 3. Architecture

### 3.1 New Material Types

Create `MaterialState` dataclass (parallel to `VesselState`):

```python
@dataclass
class MaterialState:
    """Non-biological calibration material (beads, dyes, buffer)."""
    material_id: str          # e.g., "well_A1_FLATFIELD_DYE_LOW"
    material_type: str        # "buffer_only", "fluorescent_dye_solution", "fluorescent_beads"
    well_position: str        # "A1", etc.

    # Optical properties (per-channel intensities in arbitrary units)
    # These are the "true signal" before detector stack
    base_intensities: Dict[str, float]  # {er: 100.0, mito: 100.0, ...}

    # Spatial structure (for beads)
    spatial_pattern: Optional[str] = None  # "uniform", "sparse", "dense", None
    bead_count: Optional[int] = None       # Number of beads (for sparse/dense)

    # Metadata
    seed: int = 0                          # Deterministic RNG seed for this material
```

### 3.2 Material Intensity Specifications

Hardcoded nominal intensities (can be overridden in plate design):

```python
MATERIAL_NOMINAL_INTENSITIES = {
    'DARK': {
        'er': 0.0, 'mito': 0.0, 'nucleus': 0.0, 'actin': 0.0, 'rna': 0.0
    },
    'FLATFIELD_DYE_LOW': {
        # Low end of detector range (~10% of typical cell signal)
        'er': 50.0, 'mito': 50.0, 'nucleus': 60.0, 'actin': 45.0, 'rna': 55.0
    },
    'FLATFIELD_DYE_HIGH': {
        # High end (~2× typical cell signal, test saturation)
        'er': 400.0, 'mito': 500.0, 'nucleus': 600.0, 'actin': 450.0, 'rna': 550.0
    },
    'MULTICOLOR_BEADS_SPARSE': {
        # Bright spots (per-bead intensity, not per-well average)
        'er': 200.0, 'mito': 250.0, 'nucleus': 300.0, 'actin': 220.0, 'rna': 270.0
    },
    'MULTICOLOR_BEADS_DENSE': {
        # Same per-bead, more beads → higher well average
        'er': 200.0, 'mito': 250.0, 'nucleus': 300.0, 'actin': 220.0, 'rna': 270.0
    },
    'FOCUS_BEADS': {
        # Very bright for autofocus
        'er': 300.0, 'mito': 350.0, 'nucleus': 400.0, 'actin': 320.0, 'rna': 370.0
    }
}

# Bead counts per well (for averaging)
BEAD_COUNTS = {
    'sparse': 10,   # ~10 beads per well
    'dense': 100,   # ~100 beads per well
    'medium': 30    # ~30 beads per well
}
```

### 3.3 Material Measurement Flow

New method: `BiologicalVirtualMachine.measure_material(material_id, **kwargs)`

```python
def measure_material(self, material_id: str, **kwargs) -> Dict[str, Any]:
    """
    Measure non-biological calibration material (beads, dyes, buffer).

    Args:
        material_id: Material identifier
        **kwargs: measurement parameters (plate_id, exposure_multiplier, etc.)

    Returns:
        Dict with morphology and detector_metadata (same structure as Cell Painting)
    """
    material = self.material_states[material_id]  # Lookup MaterialState

    # Dispatch to material-specific simulator
    if material.material_type == "buffer_only":
        return self._measure_buffer(material, **kwargs)
    elif material.material_type == "fluorescent_dye_solution":
        return self._measure_dye_solution(material, **kwargs)
    elif material.material_type == "fluorescent_beads":
        return self._measure_beads(material, **kwargs)
    else:
        raise ValueError(f"Unknown material type: {material.material_type}")
```

### 3.4 Detector Stack Reuse

All material measurements go through detector stack (same code as Cell Painting):

```python
def _apply_detector_stack(self, signal: Dict[str, float], **kwargs) -> tuple[Dict[str, float], Dict[str, Any]]:
    """
    Apply detector stack to signal (viability-scaled biology OR material intensities).

    Pipeline:
    1. Exposure multiplier (agent-controlled)
    2. Additive floor (detector read noise)
    3. Saturation (dynamic range limits)
    4. Quantization (ADC digitization)

    Returns:
        (measured_signal, detector_metadata)
    """
    # Extract from Cell Painting pipeline (steps 3, 8, 9, 10)
    # This is the SAME code path for cells and materials
```

### 3.5 Material Simulators

#### 3.5.1 Buffer (DARK wells)
```python
def _measure_buffer(self, material: MaterialState, **kwargs) -> Dict[str, Any]:
    """
    Measure buffer-only well (camera baseline).

    Signal: 0.0 (true black) + detector artifacts only
    """
    # Start with zero signal
    signal = {ch: 0.0 for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']}

    # Apply detector stack (floor + saturation + quantization)
    signal, detector_metadata = self._apply_detector_stack(signal, **kwargs)

    return {
        'morphology': signal,
        'material_type': 'buffer_only',
        'detector_metadata': detector_metadata,
        'well_position': material.well_position,
        **kwargs  # Echo exposure_multiplier, etc.
    }
```

#### 3.5.2 Dye Solution (FLATFIELD)
```python
def _measure_dye_solution(self, material: MaterialState, **kwargs) -> Dict[str, Any]:
    """
    Measure uniform fluorescent dye solution.

    Signal: Known base intensities + minimal variance (no biology, just mixing noise)
    """
    signal = material.base_intensities.copy()

    # Add minimal shot noise (Poisson-like, ~3% CV for dye mixing)
    for ch in signal:
        signal[ch] *= self.rng_assay.normal(1.0, 0.03)
        signal[ch] = max(0.0, signal[ch])

    # Apply detector stack
    signal, detector_metadata = self._apply_detector_stack(signal, **kwargs)

    return {
        'morphology': signal,
        'material_type': 'fluorescent_dye_solution',
        'detector_metadata': detector_metadata,
        'well_position': material.well_position,
        **kwargs
    }
```

#### 3.5.3 Beads (MULTICOLOR_BEADS)
```python
def _measure_beads(self, material: MaterialState, **kwargs) -> Dict[str, Any]:
    """
    Measure fluorescent beads (sparse or dense).

    Signal: Per-bead intensities averaged over bead count + spatial variance
    """
    signal = material.base_intensities.copy()
    bead_count = material.bead_count or BEAD_COUNTS.get(material.spatial_pattern, 10)

    # Beads have per-bead variance + averaging over N beads
    # Variance scales as 1/sqrt(N) for averaging noise
    per_bead_cv = 0.10  # 10% per-bead variance (manufacturing + focus)
    averaging_cv = per_bead_cv / np.sqrt(bead_count)

    for ch in signal:
        signal[ch] *= self.rng_assay.normal(1.0, averaging_cv)
        signal[ch] = max(0.0, signal[ch])

    # Apply detector stack
    signal, detector_metadata = self._apply_detector_stack(signal, **kwargs)

    return {
        'morphology': signal,
        'material_type': 'fluorescent_beads',
        'spatial_pattern': material.spatial_pattern,
        'bead_count': bead_count,
        'detector_metadata': detector_metadata,
        'well_position': material.well_position,
        **kwargs
    }
```

---

## 4. Integration with Plate Executor

Extend `plate_executor_v2.py` to handle material wells:

```python
def execute_well(pw: ParsedWell, ...) -> Dict[str, Any]:
    """Execute well (cells OR materials)."""

    # Check if this is a material well
    if pw.treatment in MATERIAL_TYPES:
        # Create MaterialState
        material = MaterialState(
            material_id=f"material_{pw.well_id}",
            material_type=MATERIAL_TYPE_MAP[pw.treatment],
            well_position=pw.well_id,
            base_intensities=MATERIAL_NOMINAL_INTENSITIES[pw.treatment],
            spatial_pattern=MATERIAL_SPATIAL_PATTERNS.get(pw.treatment),
            bead_count=None,  # Use defaults
            seed=stable_hash_seed(base_seed, pw.well_id, "material")
        )

        # Measure material (no VM needed)
        return vm.measure_material(material.material_id, **measurement_ctx.to_kwargs())

    # Else: normal cell well (existing logic)
    # ...
```

---

## 5. Validation Strategy

### 5.1 Contract Tests (Fast)

Create `tests/contracts/test_material_measurement.py`:

```python
def test_dark_wells_measure_floor_only():
    """DARK wells should measure only detector floor (no signal)."""
    # Test that buffer gives ~0 + floor noise

def test_flatfield_dye_low_no_biology_variance():
    """Dye solutions have low variance (no biology)."""
    # Measure same dye 100× → CV should be ~3% (not ~15% like cells)

def test_flatfield_dye_high_tests_saturation():
    """High dye intensity should trigger saturation at high exposure."""
    # Measure at exposure=5.0 → should saturate

def test_beads_sparse_vs_dense_averaging():
    """Dense beads have lower variance than sparse (averaging)."""
    # CV_sparse / CV_dense ≈ sqrt(N_dense / N_sparse)

def test_material_reuses_detector_stack():
    """Materials go through same detector as cells."""
    # Verify detector_metadata structure identical
```

### 5.2 Bead Plate Execution (Integration)

Run full bead plate design:
```bash
python -m cell_os.plate_executor_v2 \
    --design validation_frontend/public/plate_designs/CAL_384_MICROSCOPE_BEADS_DYES_v1.json \
    --output results/bead_plate/
```

Verify:
- DARK wells: morphology near 0.0 (within floor noise)
- FLATFIELD_DYE_LOW: uniform across plate (CV < 5%)
- FLATFIELD_DYE_HIGH: some saturation at high exposure
- BEADS_SPARSE: higher variance than BEADS_DENSE

---

## 6. Implementation Plan

**Phase 1: Core Material Support** (this PR)
- [ ] Create `MaterialState` dataclass
- [ ] Add `MATERIAL_NOMINAL_INTENSITIES` constants
- [ ] Implement `_measure_buffer()`, `_measure_dye_solution()`, `_measure_beads()`
- [ ] Extract `_apply_detector_stack()` from Cell Painting
- [ ] Add `measure_material()` dispatch method
- [ ] Write contract tests (5 tests, <5 seconds)

**Phase 2: Plate Executor Integration** (next PR)
- [ ] Extend `ParsedWell` to handle material types
- [ ] Add material dispatch in `execute_well()`
- [ ] Parse bead plate JSON schema
- [ ] Execute bead plate end-to-end
- [ ] Validate output structure

**Phase 3: Calibration Implementation** (future PR)
- [ ] Implement calibration module (estimate floor, saturation, quantization)
- [ ] Generate exposure recommendations
- [ ] Write calibration report generator

---

## 7. Open Questions

**Q1:** Should materials have run_context batch effects?
**A1:** YES - detector artifacts (gain drift, channel biases) apply to materials too. Materials measure the DETECTOR, not just biology.

**Q2:** Should materials have spatial gradients (illumination non-uniformity)?
**A2:** YES for dyes (flat-field is the whole point). NO for beads initially (beads are sparse, averaging washes out gradients).

**Q3:** Should exposure_multiplier work for materials?
**A3:** YES - exposure is instrument setting, applies to all measurements.

**Q4:** How to handle bead plate schema (`microscope_calibration_plate_v1`)?
**A4:** Convert to v2 format in `_load_and_validate_design()` (same approach as v1→v2 cell plates).

---

## 8. Success Criteria

✅ DARK wells measure ~0 ± floor noise
✅ FLATFIELD_DYE_LOW has <5% CV across plate (uniform)
✅ FLATFIELD_DYE_HIGH saturates at high exposure
✅ BEADS_DENSE has lower variance than BEADS_SPARSE
✅ Detector metadata identical structure for cells and materials
✅ Contract tests run in <5 seconds
✅ No disruption to existing Cell Painting tests
