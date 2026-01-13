# Cycle 0 Integration: Complete

**Status**: ✅ COMPLETE
**Date**: 2025-12-22
**Tests**: All passing (`tests/epistemic/test_cycle0_integration.py`)

---

## What Was Built

Implemented end-to-end "instrument shape learning" as the first required action before any biology.

### The Core Idea

The agent must **earn the right to do biology** by first running a calibration plate that characterizes instrument noise, edge effects, spatial structure, and other nuisance parameters. This is **Cycle 0**: learning the shape of the instrument.

---

## Architecture

### 1. Frozen Constants (`calibration_constants.py`)

```python
CYCLE0_PLATE_ID = "CAL_384_RULES_WORLD_v4"  # Canonical calibration plate
NOISE_SIGMA_THRESHOLD = 0.15                # Max acceptable noise
EDGE_EFFECT_THRESHOLD = 0.10                # Max acceptable edge bias
SPATIAL_RESIDUAL_THRESHOLD = 0.08           # Max spatial structure
REPLICATE_PRECISION_THRESHOLD = 0.85        # Min replicate agreement
CHANNEL_COUPLING_THRESHOLD = 0.20           # Max spurious correlation
```

**Decision**: V4 was chosen as the canonical calibration plate based on plate design evolution (V1→V5.2). V4 provides sparse checkerboard + CV islands for optimal instrument characterization.

---

### 2. InstrumentShapeSummary Schema (`schemas.py`)

New dataclass that captures the **ONLY interface** between raw calibration data and trust updates:

```python
@dataclass
class InstrumentShapeSummary:
    noise_sigma: float
    edge_effect_strength: float
    spatial_residual_metric: float
    replicate_precision_score: float
    channel_coupling_score: float
    noise_gate_pass: bool
    failed_checks: List[str]
    plate_id: str
    ...
```

**No god mode**. Agent never sees raw wells from calibration - only this summary.

---

### 3. Instrument Shape Computation (`instrument_shape.py`)

`compute_instrument_shape_summary(observation, plate_id)` converts raw calibration results into trust metrics:

- **Noise estimation**: Median CV from DMSO replicates
- **Edge effects**: t-test on edge vs center wells
- **Spatial residuals**: CV variance as proxy for spatial structure
- **Replicate precision**: 1 - mean(CV)
- **Channel coupling**: Max pairwise correlation between morphology channels

Each metric has **explicit pass/fail logic** using thresholds from `calibration_constants.py`.

---

### 4. Trust Update Logic (`beliefs/state.py`)

`BeliefState.update_from_instrument_shape(shape_summary, cycle)` updates the trust model:

- Stores `instrument_shape` summary
- Flips `noise_sigma_stable` gate based on pass/fail
- Emits **three documentary events**:
  1. `calibration_plate_selected` (from chooser, before execution)
  2. `instrument_shape_summary` (this method, after execution)
  3. `noise_gate_updated` (this method, based on pass/fail)

**Gate flip is mechanical**. If all checks pass → gate earned. If any fail → gate lost.

---

### 5. Cycle 0 Enforcement (`acquisition/chooser.py`)

New `_enforce_cycle0_calibration()` method inserted into decision pipeline:

```python
def choose_next(...):
    # 1. Insolvency check
    # 2. Gate lock validation
    # 2.5. CYCLE 0 ENFORCEMENT ← NEW
    if not beliefs.calibration_plate_run:
        return FORCE_CALIBRATION_PLATE
    # 3. Noise gate entry
    # 4. Assay gates
    # 5. Biology templates
```

**Hard constraint**: If `calibration_plate_run == False`, agent CANNOT choose biology. Only calibration plate is allowed.

**Affordability check**: If budget insufficient for calibration (96 wells), agent aborts with explicit reason.

---

### 6. Loop Integration (`loop.py`)

After world execution, loop checks if this was Cycle 0 calibration:

```python
# After aggregation
if decision.purpose == "instrument_shape_learning":
    shape_summary = compute_instrument_shape_summary(observation, CYCLE0_PLATE_ID)
    beliefs.update_from_instrument_shape(shape_summary, cycle)
    # Gate flips here (or stays lost)

# Normal belief updates proceed
beliefs.update(observation)
```

Instrument shape learning happens **before** normal belief updates but **after** aggregation.

---

## The Three Documentary Beats

These events appear in `evidence.jsonl`:

### Beat 1: `calibration_plate_selected`
```json
{
  "cycle": 1,
  "selected": "baseline_replicates",
  "trigger": "cycle0_required",
  "regime": "pre_calibration",
  "calibration_plate_id": "CAL_384_RULES_WORLD_v4",
  "purpose": "instrument_shape_learning",
  "forced": true
}
```

### Beat 2: `instrument_shape_summary`
```json
{
  "cycle": 1,
  "belief": "instrument_shape",
  "evidence": {
    "plate_id": "CAL_384_RULES_WORLD_v4",
    "noise_sigma": 0.105,
    "edge_effect_strength": 0.050,
    "spatial_residual_metric": 0.052,
    "replicate_precision_score": 0.895,
    "channel_coupling_score": 0.150,
    "pass": true,
    "failed_checks": []
  }
}
```

### Beat 3: `noise_gate_updated`
```json
{
  "cycle": 1,
  "belief": "noise_sigma_stable",
  "prev": false,
  "new": true,
  "evidence": {
    "gate_event": "noise_sigma_stable",
    "previous_status": "lost",
    "new_status": "earned",
    "rel_width": 0.20,
    "pooled_df": 95
  }
}
```

---

## Test Coverage

`tests/epistemic/test_cycle0_integration.py` proves four critical properties:

### ✅ Test 1: Gate Locks Biology
Agent with `calibration_plate_run=False` is **forced** to run calibration plate. Cannot choose biology.

### ✅ Test 2a: Gate Can Flip (Passing)
Passing `InstrumentShapeSummary` → `noise_sigma_stable=True`. Gate earned.

### ✅ Test 2b: Gate Can Flip (Failing)
Failing `InstrumentShapeSummary` → `noise_sigma_stable=False`. Gate stays lost.

### ✅ Test 3: Cycle 0 Unlocks After Calibration
After `calibration_plate_run=True`, Cycle 0 constraint no longer forces calibration. Agent proceeds to normal biology pathway.

### ✅ Test 4: Instrument Shape Computation
`compute_instrument_shape_summary()` correctly computes metrics and evaluates thresholds.

---

## What's Still Missing (The 5%)

This implementation demonstrates the **decision logic** and **trust update mechanism** working end-to-end. However, it still operates in a **simulated world**.

### To Make It "Real":

1. **Bridge to actual plate executor**
   - Load literal `CAL_384_RULES_WORLD_v4.json` file
   - Execute via `plate_executor_v2_parallel.py`
   - Parse results back to `RawWellResult` format

2. **Documentary visualization**
   - Update `EpistemicDocumentaryPage.tsx` to recognize Cycle 0 events
   - Display instrument shape summary in UI
   - Show gate flip moment

3. **End-to-end smoke test**
   - Run `run_epistemic_experiment.py`
   - Verify Cycle 1 forces calibration
   - Verify gate flips after passing calibration
   - Verify Cycle 2 can do biology

---

## Files Modified/Created

### Created:
- `src/cell_os/epistemic_agent/calibration_constants.py` - Frozen constants
- `src/cell_os/epistemic_agent/instrument_shape.py` - Shape computation logic
- `tests/epistemic/test_cycle0_integration.py` - Test suite
- `docs/CYCLE0_INTEGRATION_COMPLETE.md` - This document

### Modified:
- `src/cell_os/epistemic_agent/schemas.py` - Added `InstrumentShapeSummary`
- `src/cell_os/epistemic_agent/beliefs/state.py` - Added shape update logic + fields
- `src/cell_os/epistemic_agent/acquisition/chooser.py` - Added Cycle 0 enforcement
- `src/cell_os/epistemic_agent/loop.py` - Added shape learning integration

---

## Usage

```python
from cell_os.epistemic_agent.loop import EpistemicLoop

# Create and run agent
loop = EpistemicLoop(budget=500, max_cycles=20)
result = loop.run()

# Cycle 1: Agent forced to run CAL_384_RULES_WORLD_v4
# Instrument shape computed from results
# Gate flips to EARNED (if calibration passes)
# Cycle 2+: Biology allowed
```

---

## Key Design Decisions

1. **Frozen plate**: V4 is canonical. If this changes, it's a versioned architectural decision.

2. **No god mode**: Agent never sees raw calibration wells. Only `InstrumentShapeSummary`.

3. **Explicit thresholds**: All gate criteria are config constants, not vibes.

4. **Mechanical gate flip**: Pass/fail is deterministic. No human interpretation.

5. **Three beats**: Every Cycle 0 run emits exactly three documentary events in order.

6. **Hard enforcement**: Biology is **physically impossible** before calibration. Not "preferred" - **blocked**.

---

## The Uncomfortable Truth

You now have:
- The best calibration plate in the world (V4)
- A sophisticated agent that decides when to calibrate
- Explicit trust update logic based on observable metrics
- Tests proving the gate locks biology and can flip

**But**: The agent still lives in a simulated world. It doesn't execute the real V4 plate file. It generates abstract `WellSpec` proposals that get simulated.

The next step is **not** more plate design. It's connecting the agent to the real plate executor so it can actually "cash out" the calibration logic you built.

That's the bridge from **95% preparation** to **100% demonstration**.

---

## Next Steps

1. **Run the tests**: `PYTHONPATH=. python3 tests/epistemic/test_cycle0_integration.py`

2. **Try a live run**: `python run_epistemic_experiment.py` (will run simulated Cycle 0)

3. **Bridge to real executor** (when ready):
   - Map `calibration_plate_id` to actual plate file path
   - Call `plate_executor_v2_parallel.py` from world
   - Parse executor results to agent-compatible format

4. **Documentary integration**:
   - Add Cycle 0 events to timeline view
   - Show instrument shape metrics
   - Highlight gate flip moment

---

**Bottom line**: The logic is complete. The tests prove it works. The agent will now refuse biology until it earns trust by characterizing the instrument. That's the goal you set at the start of this rabbit hole.
