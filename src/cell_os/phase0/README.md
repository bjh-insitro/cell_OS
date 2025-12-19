# Phase 0: Infrastructure Validation

Phase 0 is **not exploratory work**. It is a set of **executable, numerical gates** that MUST pass before any biological conclusions can be drawn.

If Phase 0 doesn't end with hard criteria, it never ends. It just "feels done" until it ruins Phase 1.

## Exit Criteria

### 1. Sentinel Stability
**Gate:** Plate-to-plate drift CV < threshold

**What it detects:**
- Inconsistent plate preparation
- Unstable measurement system
- Environmental control failures

**Implementation:**
```python
from cell_os.phase0 import assert_sentinel_drift_below, RunSummary, SentinelObs

sentinels = [
    SentinelObs(plate_id="P1", well_pos="A01", metric_name="LDH", value=100.0),
    SentinelObs(plate_id="P1", well_pos="A02", metric_name="LDH", value=101.0),
    # ... more sentinel observations across multiple plates
]

run = RunSummary(
    sentinels=sentinels,
    edge_effects=[],
    positive_controls=[],
    measurement_replicates={},
)

# This will raise Phase0GateFailure if drift is too high
assert_sentinel_drift_below(threshold_cv=0.02, run=run)  # 2% CV threshold
```

### 2. Measurement Precision
**Gate:** Within-condition replicate CV < threshold

**What it detects:**
- High technical noise
- Pipetting inconsistencies
- Instrument variability

**Implementation:**
```python
from cell_os.phase0 import assert_measurement_cv_below

run = RunSummary(
    sentinels=[],
    edge_effects=[],
    positive_controls=[],
    measurement_replicates={
        "LDH": [100.0, 101.0, 99.5, 100.5, 100.2],  # Technical replicates
        "CP_PC1": [50.2, 51.0, 49.8, 50.5],
    },
)

assert_measurement_cv_below(threshold_cv=0.03, run=run)  # 3% CV threshold
```

### 3. Plate Edge Effects
**Gate:** Edge-center difference < threshold OR edge effect is reproducible

**What it detects:**
- Temperature gradients
- Evaporation
- Media diffusion artifacts

**Implementation:**
```python
from cell_os.phase0 import assert_plate_edge_effect_detectable_or_absent, EdgeObs

edge_effects = [
    EdgeObs(plate_id="P1", well_pos="A01", metric_name="LDH", region="edge", value=100.5),
    EdgeObs(plate_id="P1", well_pos="D05", metric_name="LDH", region="center", value=100.0),
    # ... more edge and center observations
]

run = RunSummary(
    sentinels=[],
    edge_effects=edge_effects,
    positive_controls=[],
    measurement_replicates={},
)

# Fail if abs(mean_edge - mean_center) > 2.0 for any plate+metric
assert_plate_edge_effect_detectable_or_absent(
    run=run,
    max_abs_edge_center_delta=2.0
)
```

### 4. Positive Control Validation
**Gate:** Known control effect > threshold

**What it detects:**
- Assay failure (control doesn't work)
- Dead/unhealthy cells
- Corrupted reagents

**Implementation:**
```python
from cell_os.phase0 import assert_effect_recovery_for_known_controls, PositiveControlObs

positive_controls = [
    PositiveControlObs(
        metric_name="LDH",
        control_name="CCCP_mid",
        baseline_name="vehicle",
        control_value=140.0,
        baseline_value=100.0,
    ),
]

run = RunSummary(
    sentinels=[],
    edge_effects=[],
    positive_controls=positive_controls,
    measurement_replicates={},
)

# Fail if abs(control - baseline) < 20.0 for any control
assert_effect_recovery_for_known_controls(run=run, min_abs_effect=20.0)
```

## Running All Gates at Once

```python
from cell_os.phase0 import assert_phase0_exit

# Populate run summary with all required data
run = RunSummary(
    sentinels=sentinel_observations,
    edge_effects=edge_observations,
    positive_controls=control_observations,
    measurement_replicates=replicate_data,
)

# Run all four gates with calibrated thresholds
assert_phase0_exit(
    run=run,
    sentinel_drift_cv=0.02,        # 2% plate-to-plate drift
    measurement_cv=0.03,            # 3% within-condition noise
    max_edge_center_delta=2.0,      # Edge effect threshold
    min_positive_effect=20.0,       # Positive control effect size
)
```

If any gate fails, `Phase0GateFailure` is raised with structured details:
- `criterion`: which gate failed
- `measured`: actual measured value
- `threshold`: configured threshold
- `message`: human-readable failure description
- `details`: structured diagnostic data

## Calibrating Thresholds

**These are placeholder values. You MUST calibrate them against your actual system.**

### Step 1: Measure your baseline noise
Run 3+ plates with identical conditions (vehicle only, no perturbations). Compute:
- Sentinel plate-to-plate CV
- Within-plate replicate CV
- Edge-center delta
- Positive control effect size

### Step 2: Set thresholds at 2-3× baseline noise
- If your sentinel drift is naturally 0.7%, set threshold at 0.02 (2%)
- If your replicate CV is 1.5%, set threshold at 0.03-0.05 (3-5%)
- If your edge effect is naturally 0.5 units, set threshold at 1.0-2.0

### Step 3: Fail loudly when gates don't pass
Do NOT ship Phase 1 code until Phase 0 gates pass consistently across multiple runs.

## Wiring into the Agent Loop

Wherever you finalize a Phase 0 run, add:

```python
# After collecting all observations for the run
from cell_os.phase0 import assert_phase0_exit, Phase0GateFailure

try:
    assert_phase0_exit(
        run=run_summary,
        sentinel_drift_cv=config.phase0.sentinel_drift_cv,
        measurement_cv=config.phase0.measurement_cv,
        max_edge_center_delta=config.phase0.max_edge_delta,
        min_positive_effect=config.phase0.min_control_effect,
    )
    print("✓ Phase 0 exit criteria PASSED")
except Phase0GateFailure as e:
    print(f"✗ Phase 0 exit criterion FAILED: {e.criterion}")
    print(f"  Measured: {e.measured:.4f}")
    print(f"  Threshold: {e.threshold:.4f}")
    print(f"  Details: {e.details}")
    raise
```

## Design Philosophy

1. **Boring is good.** These are simple CV and mean comparisons. No ML, no fancy stats.
2. **Fail loudly.** If a gate fails, the entire run fails. No warnings, no soft failures.
3. **Structured errors.** All failures include structured diagnostic data for debugging.
4. **Single choke point.** All Phase 0 runs must pass through `assert_phase0_exit()`.

## What This Prevents

- **Silent drift:** Plate prep degrades over time but you don't notice until Phase 1 fails
- **False positives:** High noise makes random wells look like hits
- **Wasted cycles:** Agent explores biology on a broken measurement system
- **Haunted data:** "It worked once" but you can't reproduce it

## Current Status

**⚠️  THRESHOLDS ARE PLACEHOLDERS ⚠️**

You MUST calibrate these against your actual noise model:
- `sentinel_drift_cv = 0.02` (2%)
- `measurement_cv = 0.03` (3%)
- `max_edge_center_delta = 2.0` (absolute units)
- `min_positive_effect = 20.0` (absolute units)

Until calibration is complete, Phase 0 is not done.
