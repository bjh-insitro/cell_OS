# Assumptions and Boundaries

**Purpose**: Distinguish confessed parameters (tunable design choices) from enforced invariants (hard constraints).

This document makes explicit what is "plausible fiction for epistemic purposes" vs. "structural requirement for system integrity."

**Related files**:
- `src/cell_os/hardware/assays/assay_params.py` - Centralized parameter definitions
- `tests/unit/test_assay_params_bounds.py` - Parameter validation tests
- `tests/unit/test_subpopulation_invariants.py` - Population structure tests
- `tests/integration/test_artifact_sensitivity.py` - Robustness tests
- `tests/integration/test_no_oracle_property.py` - Oracle prevention tests

---

## Confessed Parameters (AssayParams)

These parameters shape what the agent observes but are NOT claimed to be biologically accurate. They serve **epistemic goals**: preventing oracles, creating plausible measurement artifacts, forcing robust inference.

### Location
`src/cell_os/hardware/assays/assay_params.py::AssayParams`

Default instance: `DEFAULT_ASSAY_PARAMS`

### Parameters

#### 1. CP_DEAD_SIGNAL_FLOOR (default: 0.3)
**Purpose**: Prevents Cell Painting from being a perfect viability oracle.

**Formula**:
```python
signal_intensity = CP_DEAD_SIGNAL_FLOOR + (1 - CP_DEAD_SIGNAL_FLOOR) * viability
```

**Rationale**: Dead cells retain some fluorescence (membrane fragments, debris). If floor == 0.0, signal would perfectly track viability (oracle).

**Effect of changing**:
- Lower → Better viability inference, approaches oracle
- Higher → More ambiguity, harder to distinguish live/dead

**Bounds**: (0, 1) exclusive
- 0 = perfect viability oracle (forbidden)
- 1 = no signal (measurement becomes useless)

---

#### 2. LDH_DEATH_AMPLIFICATION_CAP (default: 10.0)
**Purpose**: Prevents LDH signal explosion near 100% death.

**Formula**:
```python
death_amplification = death_fraction / (1 - death_fraction)
death_amplification = min(death_amplification, LDH_DEATH_AMPLIFICATION_CAP)
```

**Rationale**: Without cap, `death/(1-death)` explodes as death → 1.0, causing numerical instability and perfect death inference (oracle). Real assays saturate.

**Effect of changing**:
- Lower → Earlier saturation, more epistemic uncertainty at high death
- Higher → Wider dynamic range, but numerical instability risk

**Bounds**: (1, 100)
- < 1 = no capping (defeats purpose)
- > 100 = unrealistic, approaches perfect oracle

---

#### 3. ATP_SIGNAL_FLOOR (default: 0.3)
**Purpose**: Basal ATP from glycolysis, prevents mito dysfunction oracle.

**Formula**:
```python
atp_signal = max(ATP_SIGNAL_FLOOR, 1 - coeff * mito_dysfunction)
```

**Rationale**: Cells produce ~30% ATP via glycolysis even with complete mitochondrial failure. If floor == 0.0, ATP signal would perfectly infer mito dysfunction (oracle).

**Effect of changing**:
- Lower → Better mito dysfunction inference, approaches oracle
- Higher → More ambiguity, harder to detect dysfunction

**Bounds**: (0, 1) exclusive
- 0 = perfect mito dysfunction oracle (forbidden)
- 1 = saturated signal (no measurement)

---

#### 4. SEGMENTATION_C_BASE (default: 0.8)
**Purpose**: Models segmentation yield loss from debris/dead cells.

**Formula**:
```python
segmentation_yield = 1.0 - SEGMENTATION_C_BASE * debris_load
```

**Rationale**: Dead cells and debris reduce segmentation success. At 100% debris, lose ~80% of segmentable cells.

**Effect of changing**:
- Lower → Less debris effect, better segmentation at high death
- Higher → More debris effect, worse segmentation at high death

**Bounds**: [0, 2]
- 0 = no debris effect
- 2 = 200% loss at full debris (max plausible with amplification)

---

## Enforced Invariants

These are **hard constraints** - violations indicate bugs or broken system integrity.

### 1. Subpopulation Structure (`test_subpopulation_invariants.py`)

**Invariants**:
- Fractions sum to 1.0 ± 1e-6 (conservation of mass)
- All fractions in [0, 1] (probability bounds)
- IC50 shifts monotonically ordered: `sensitive <= typical <= resistant`
- Count matches structure (currently 3: sensitive/typical/resistant)

**Rationale**: These define the heterogeneity model's mathematical structure. Violations break dose-response calculations.

**NOT confessed**: The specific 25/50/25 split IS confessed (non-biological), but the structural requirement that fractions sum to 1 is **enforced**.

---

### 2. Parameter Validation (`test_assay_params_bounds.py`)

**Invariants**:
- Signal floors in (0, 1) - must prevent oracles but allow measurement
- Amplification caps > 1 - must actually cap
- Coefficients in reasonable ranges - prevent nonsense values

**Rationale**: These bounds prevent both oracles (floors == 0) and broken measurements (floors == 1).

---

### 3. Artifact Robustness (`test_artifact_sensitivity.py`)

**Invariants**:
- Evaporation doesn't crash system (volume loss tracked correctly)
- Compound treatment doesn't cause covenant violations
- Combined artifacts (evaporation + carryover + measurement) don't deadlock

**Rationale**: System must tolerate realistic artifact variation. These tests ensure parameter changes don't break epistemic loop.

---

### 4. No-Oracle Property (`test_no_oracle_property.py`)

**Invariants**:
- Signal floors are configured > 0 (prevents perfect inference)
- ATP signals remain positive and finite
- Measurements show variation across viability levels (not identical)

**Rationale**: If measurements were perfect oracles, epistemic debt system becomes meaningless. Floors force inference under uncertainty.

---

## Calibration Strategies

If validating against real data, prioritize in this order:

1. **Enforce invariants first** (these are non-negotiable)
2. **Tune confessed parameters** to match observed noise/ambiguity
3. **Document deviations** from defaults in RunContext or per-experiment metadata

**Example**: If real Cell Painting has 15% dead signal floor (not 30%), update `CP_DEAD_SIGNAL_FLOOR = 0.15` but keep bounds validation (> 0, < 1).

---

## What This PR Does NOT Cover

**Aspiration effects** (PR #2):
- Aspiration-induced stress
- Volume loss → concentration amplification
- These are **biological effects**, not measurement parameters

This PR focuses on **measurement layer parameters** only, keeping scope minimal and diffs clean.
