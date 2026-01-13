# Agent 3: Calibration Tracking Integration Example

This document shows how to integrate ECE calibration tracking into your epistemic agent workflow.

## Quick Start

```python
from cell_os.epistemic_agent.diagnostics import (
    record_classification,
    emit_calibration_diagnostic,
    check_and_emit_alert,
)
from cell_os.hardware.mechanism_posterior_v2 import Mechanism
from pathlib import Path

# After each mechanism classification
posterior = {
    Mechanism.ER_STRESS: 0.72,
    Mechanism.MITOCHONDRIAL: 0.18,
    Mechanism.MICROTUBULE: 0.10,
}
predicted = Mechanism.ER_STRESS
true_mechanism = Mechanism.ER_STRESS  # From simulator

# Record event (non-blocking, safe)
record_classification(
    predicted=predicted,
    true_mechanism=true_mechanism,
    posterior=posterior
)

# Periodically (e.g., every N cycles), emit diagnostics
diagnostics_file = Path("diagnostics.jsonl")
emit_calibration_diagnostic(diagnostics_file)
check_and_emit_alert(diagnostics_file)
```

## JSONL Output Examples

### Calibration Diagnostic
```json
{
  "event": "mechanism_calibration",
  "ece": 0.12,
  "n_samples": 64,
  "n_bins": 10,
  "mean_confidence": 0.75,
  "accuracy": 0.68,
  "unstable": false,
  "timestamp": "2025-12-21T16:00:00"
}
```

### Calibration Alert (if ECE > 0.15)
```json
{
  "event": "mechanism_calibration_alert",
  "ece": 0.22,
  "threshold": 0.15,
  "n_samples": 50,
  "is_stable": true,
  "message": "Mechanism posteriors appear miscalibrated",
  "timestamp": "2025-12-21T16:05:00"
}
```

## Integration Points

### Where to Call `record_classification()`

Call this **after every mechanism classification**, wherever you have:
1. A predicted mechanism (argmax of posterior)
2. Ground truth mechanism (from simulator)
3. Full posterior distribution

Example locations:
- After `MechanismPosterior` is computed
- In confidence calibration pipeline (if available)
- In evaluation/testing code

### Where to Call `emit_calibration_diagnostic()`

Call this periodically to log calibration metrics:
- Every N cycles (e.g., N=10)
- At end of each run
- When saving checkpoints

### Where to Call `check_and_emit_alert()`

Call this alongside `emit_calibration_diagnostic()` to check for miscalibration.
Alert is only emitted if:
- ECE > 0.15 (threshold)
- n_samples >= 30 (stable)

## Non-Blocking Guarantee

All functions are non-blocking:
- Errors are logged, not raised
- Missing data is handled gracefully
- No exceptions propagate to caller

This is **pure instrumentation** - your pipeline continues even if logging fails.

## Global Tracker

The system uses a global singleton tracker for simplicity:

```python
from cell_os.epistemic_agent.diagnostics import (
    get_global_tracker,
    reset_global_tracker,
)

# Get current tracker
tracker = get_global_tracker()
stats = tracker.get_statistics()
print(f"ECE: {stats['ece']:.3f}, n={stats['n_samples']}")

# Reset between runs
reset_global_tracker()
```

## Interpreting ECE

- **ECE < 0.10**: Well-calibrated (confidence matches accuracy)
- **ECE 0.10-0.15**: Moderately miscalibrated (acceptable)
- **ECE > 0.15**: Poorly calibrated (alert threshold)
- **ECE > 0.25**: Catastrophically miscalibrated (overconfident or underconfident)

## Example: Overconfidence

```
Diagnostic:
{
  "ece": 0.35,
  "mean_confidence": 0.95,
  "accuracy": 0.60
}
```

**Interpretation**: Agent says "95% sure" but is only right 60% of the time.
Gap = |0.95 - 0.60| = 0.35 (HIGH - overconfident)

## Example: Underconfidence

```
Diagnostic:
{
  "ece": 0.35,
  "mean_confidence": 0.55,
  "accuracy": 0.90
}
```

**Interpretation**: Agent says "55% sure" but is actually right 90% of the time.
Gap = |0.55 - 0.90| = 0.35 (HIGH - underconfident)

## Philosophy

This is **detection, not correction**:
- ✅ Measures calibration
- ✅ Logs metrics
- ✅ Emits alerts
- ❌ Does NOT fix miscalibration
- ❌ Does NOT change policies
- ❌ Does NOT block execution

If you see high ECE, investigate:
1. Is the posterior inference correct?
2. Are nuisance factors properly modeled?
3. Is the confidence calibration layer working?

But don't automatically "fix" it - understand it first.
