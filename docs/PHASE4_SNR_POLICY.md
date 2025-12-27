# Phase 4: SNR Policy - Agent-Facing Guardrails

**Status:** ✅ Complete
**Feature:** Prevents agent from learning morphology shifts in sub-noise regimes
**Requirement:** `floor.observable = true` in calibration profile

---

## Overview

The SNR (Signal-to-Noise Ratio) policy prevents the agent from drawing conclusions about biological effects when measurements are below the minimum detectable signal. This is critical for scientific integrity: without this guardrail, the agent might attribute noise fluctuations to real biological effects.

## Key Components

### 1. CalibrationProfile (`src/cell_os/calibration/profile.py`)

Provides floor characterization:
- `floor_observable()`: Check if floor was characterized during calibration
- `floor_mean(channel)`: Detector bias baseline (AU)
- `floor_sigma(channel)`: Detector noise (AU)
- `is_above_noise_floor(signal, channel, k)`: Check if signal > floor_mean + k*floor_sigma
- `minimum_detectable_signal(channel, k)`: Get threshold for each channel

### 2. SNRPolicy (`src/cell_os/epistemic_agent/snr_policy.py`)

Agent-facing policy enforcer:
- **Strict mode:** Reject conditions with ANY channel below threshold
- **Lenient mode:** Warn but allow agent to decide
- **Disabled mode:** When floor not observable (degrades gracefully)

### 3. Integration in Observation Aggregator

SNR policy is applied during aggregation to filter/annotate low-SNR conditions before the agent sees them.

---

## Usage

### Basic Usage

```python
from src.cell_os.calibration.profile import CalibrationProfile
from src.cell_os.epistemic_agent.snr_policy import SNRPolicy
from src.cell_os.epistemic_agent.observation_aggregator import aggregate_observation

# Load calibration profile
profile = CalibrationProfile("calibration_report.json")

# Create SNR policy (5σ threshold, lenient mode)
snr_policy = SNRPolicy(profile, threshold_sigma=5.0, strict_mode=False)

# Check if enabled (requires floor.observable = true)
print(f"SNR policy enabled: {snr_policy.enabled}")
print(f"Minimum detectable signals: {snr_policy.minimum_detectable_signals()}")

# Apply during aggregation
observation = aggregate_observation(
    proposal=proposal,
    raw_results=raw_results,
    budget_remaining=world.budget_remaining,
    snr_policy=snr_policy  # ← Add SNR policy here
)

# Check SNR metadata
if "snr_policy" in observation.qc_struct:
    summary = observation.qc_struct["snr_policy"]
    print(f"Rejected {summary['n_conditions_rejected']} dim conditions")
    print(f"Accepted {summary['n_conditions_accepted']} bright conditions")
```

### Checking Individual Measurements

```python
# Check if a single measurement is above noise floor
signal = 0.50  # AU
is_above, reason = snr_policy.check_measurement(signal, channel="er")

if not is_above:
    print(f"REJECT: {reason}")
    # e.g., "Signal 0.28 AU is below 5.0σ threshold (floor: 0.25 ± 0.05 AU)"
```

### Filtering Observations

```python
# Filter observation to remove/flag low-SNR conditions
filtered_obs = snr_policy.filter_observation(observation_dict, annotate=True)

# Check individual conditions
for cond in filtered_obs["conditions"]:
    snr_meta = cond.get("snr_policy", {})
    if not snr_meta.get("is_valid"):
        print(f"Dim condition: {cond['compound']} @ {cond['dose_uM']} µM")
        print(f"Warnings: {snr_meta['warnings']}")
```

---

## Configuration

### Threshold Selection

The `threshold_sigma` parameter sets the SNR threshold as a multiple of floor noise:

```python
threshold = floor_mean + threshold_sigma * floor_sigma
```

**Recommended values:**
- `5.0` (default): Conservative, standard 5σ detection limit
- `3.0`: Relaxed, accepts dimmer signals (higher false positive risk)
- `10.0`: Ultra-conservative, only very bright signals accepted

### Strict vs Lenient Mode

**Strict mode** (`strict_mode=True`):
- **Behavior:** Reject conditions with ANY channel below threshold
- **Use case:** When all 5 channels must be reliable (e.g., multi-channel phenotypes)
- **Effect:** Reduces false discoveries, but may miss real effects in dim channels

**Lenient mode** (`strict_mode=False`, default):
- **Behavior:** Annotate warnings but allow agent to decide
- **Use case:** When some channels may be legitimately dim (e.g., ER stress only affects ER channel)
- **Effect:** Agent sees all data with SNR metadata for informed decisions

---

## How It Works

### 1. Calibration Phase (Bead/Dye Plate)

The calibration run characterizes detector floor using DARK wells (no sample):

```yaml
# data/calibration_thalamus_params.yaml
technical_noise:
  dark_bias_lsbs: 20.0                # Detector bias (20 LSB ≈ 0.3 AU)
  additive_floor_sigma_er: 0.045      # Detector noise (3 LSB ≈ 0.045 AU)
  # ... per-channel noise
```

Output: `calibration_report.json` with floor statistics:

```json
{
  "floor": {
    "observable": true,
    "per_channel": {
      "er": {
        "mean": 0.25,  // Detector bias baseline
        "unique_values": [0.24, 0.25, 0.26, 0.27, 0.28, 0.29]  // Range ~0.05 AU
      }
    }
  }
}
```

### 2. Agent Observation (Biological Experiment)

When agent receives measurements, SNR policy checks each condition:

```python
# Condition: DMSO control @ 12h
feature_means = {
    "er": 0.28,      # Below threshold (0.25 + 5*0.01 = 0.30)
    "mito": 0.50,    # Above threshold
    "nucleus": 0.60,
    "actin": 0.55,
    "rna": 0.52
}

# Strict mode: REJECT (one dim channel)
# Lenient mode: WARN (agent decides)
```

### 3. Agent Decision

With SNR metadata, agent can:
- **Reject learning:** "Not enough signal to distinguish from noise"
- **Request more exposure:** "Increase laser power or exposure time"
- **Accept with caution:** "Effect is real but near detection limit"

---

## Contract Tests

See `tests/contracts/test_snr_policy_integration.py` for validation:

1. ✅ Policy enabled when `floor.observable = true`
2. ✅ Policy disabled when `floor.observable = false` (graceful degradation)
3. ✅ Dim signals rejected below threshold
4. ✅ Bright signals accepted above threshold
5. ✅ Minimum detectable signals computed correctly
6. ✅ Strict mode rejects conditions with ANY dim channel
7. ✅ Lenient mode annotates but allows agent to decide
8. ✅ Filter removes dim conditions in strict mode
9. ✅ Filter annotates but keeps conditions in lenient mode

Run tests:
```bash
pytest tests/contracts/test_snr_policy_integration.py -xvs
```

---

## Example: Agent Integration

```python
# In agent loop (loop.py or similar)
from src.cell_os.calibration.profile import CalibrationProfile
from src.cell_os.epistemic_agent.snr_policy import SNRPolicy

# Load calibration profile once at startup
calibration_path = Path("results/calibration/calibration_report.json")
if calibration_path.exists():
    profile = CalibrationProfile(calibration_path)
    snr_policy = SNRPolicy(profile, threshold_sigma=5.0, strict_mode=False)
    print(f"✓ SNR policy loaded (enabled={snr_policy.enabled})")
    print(f"  Minimum detectable signals: {snr_policy.minimum_detectable_signals()}")
else:
    snr_policy = None
    print("⚠ No calibration profile found, SNR policy disabled")

# In agent cycle
for cycle in range(max_cycles):
    # Execute experiment
    raw_results = world.run_experiment(proposal)

    # Aggregate with SNR policy
    observation = aggregate_observation(
        proposal=proposal,
        raw_results=raw_results,
        budget_remaining=world.budget_remaining,
        cycle=cycle,
        snr_policy=snr_policy  # ← Apply SNR guardrail
    )

    # Check SNR summary
    if observation.qc_struct and "snr_policy" in observation.qc_struct:
        snr_summary = observation.qc_struct["snr_policy"]
        if snr_summary["n_conditions_rejected"] > 0:
            print(f"⚠ {snr_summary['n_conditions_rejected']} conditions rejected due to low SNR")

    # Update beliefs (only from valid conditions)
    agent.update_from_observation(observation)
```

---

## Phase 4 Deliverables

✅ **1. CalibrationProfile floor methods** (`src/cell_os/calibration/profile.py`)
- `floor_observable()`, `floor_mean()`, `floor_sigma()`
- `is_above_noise_floor()`, `minimum_detectable_signal()`

✅ **2. SNRPolicy module** (`src/cell_os/epistemic_agent/snr_policy.py`)
- Strict/lenient modes
- Measurement checks, condition filtering, observation filtering
- Graceful degradation when floor not observable

✅ **3. Integration in observation aggregator** (`observation_aggregator.py`)
- `snr_policy` parameter in `aggregate_observation()`
- Automatic filtering/annotation of low-SNR conditions

✅ **4. Contract tests** (`tests/contracts/test_snr_policy_integration.py`)
- 11 tests covering all modes and edge cases

✅ **5. Documentation** (this file)
- Usage examples, configuration, integration guide

---

## Related Work

- **Phase 1-3:** Material hardening, detector characterization, calibration integration
- **Phase 4 Dark Floor Fix:** Made floor observable via detector bias + noise
- **Test tripwires:** `test_dark_floor_observable.py`, `test_floor_regression_tripwire.py`

---

## Future Extensions

1. **Dynamic threshold adjustment:** Adjust `threshold_sigma` based on assay criticality
2. **Channel-specific thresholds:** Different thresholds for different channels
3. **Adaptive exposure:** Automatically increase exposure when SNR too low
4. **Uncertainty propagation:** Use SNR to weight belief updates (Bayesian)

---

**Phase 4 Complete:** ✅ Agent now respects detector physics and refuses to learn from noise.
