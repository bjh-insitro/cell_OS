# Epistemic Actions Implementation Summary

**Version:** v1.0 (Option A - Calibration Uncertainty Proxy)
**Date:** 2025-12-23
**Status:** Complete and Tested

## Overview

Implemented a closed-loop epistemic action system that generalizes the mitigation architecture from "QC flag → mitigate" to "uncertainty state → decide". The system chooses between REPLICATE vs EXPAND actions based on calibration uncertainty, spending budget with epistemic reward computation.

## Design Decisions

### Option A: Calibration Uncertainty Proxy (CHOSEN)

**Rationale:** This is the only uncertainty in the codebase that is currently *real*, *tracked*, and *updateable* without inventing machinery.

**Uncertainty metric:** `BeliefState.calibration_entropy_bits`
- Aggregates: noise (0-2 bits), assays (0-3 bits), edges (0-1 bit), exploration (0-2 bits), patterns (0-2 bits)
- Typical range: 0-10 bits
- Measures uncertainty about MEASUREMENT QUALITY (the ruler), NOT biological parameters

**Decision thresholds:**
- Uncertainty > 4.0 bits → REPLICATE (tighten ruler confidence)
- Uncertainty ≤ 4.0 bits → EXPAND (advance exploration)
- Max consecutive replications: 2 (prevents budget death spiral)

**Action semantics:**
- REPLICATE: Calls `make_replicate_proposal(previous_proposal)` → 2× wells for tighter CI
- EXPAND: Calls `propose_next_experiment(capabilities, previous_observation)` → normal policy path

**Epistemic reward:**
```
reward = (uncertainty_before - uncertainty_after) / (cost_wells / 96.0)
```
Units: bits per plate-equivalent

## Implementation

### Files Created

#### 1. `src/cell_os/epistemic_agent/epistemic_actions.py`
Core module with:
- `EpistemicAction` enum (REPLICATE, EXPAND, NONE)
- `EpistemicContext` dataclass (tracks pending actions)
- `compute_epistemic_reward()` function

#### 2. `tests/integration/test_epistemic_actions.py`
Test suite with:
- `test_epistemic_determinism`: Same seed → same actions/rewards
- `test_epistemic_budget_conservation`: Wells consumed match expectations (REPLICATE = 2× wells)
- `test_epistemic_action_switching`: Mock estimator → verify decision logic
- `test_epistemic_confounding_adversary`: Optional benchmark (skipped)

### Files Modified

#### 3. `src/cell_os/epistemic_agent/beliefs/state.py`
Added:
```python
def estimate_calibration_uncertainty(self) -> float:
    """Return current calibration uncertainty (bits).

    This measures uncertainty about MEASUREMENT QUALITY:
    - Noise (CI width on pooled sigma)
    - Edge effects (detection confidence)
    - Assay gates (LDH, Cell Painting, scRNA)
    - Dose-response patterns (curvature, time dependence)
    - Exploration coverage (untested compounds)

    This does NOT measure biological parameter uncertainty (IC50, mechanism).
    """
    return self.calibration_entropy_bits
```

#### 4. `src/cell_os/epistemic_agent/agent/policy_rules.py`
Added to `__init__`:
```python
self.consecutive_epistemic_replications = 0  # Track consecutive REPLICATE actions
```

Added methods:
- `choose_epistemic_action()`: Decision logic with threshold and replication cap
- `create_epistemic_proposal()`: Creates REPLICATE or EXPAND proposals

#### 5. `src/cell_os/epistemic_agent/loop.py`
Added to `__init__`:
```python
self.epistemic_file = self.log_dir / f"{self.run_id}_epistemic.jsonl"
self._pending_epistemic_action = None
```

Added to `run()`:
- Epistemic action check in cycle loop (after mitigation, before science)
- Uncertainty snapshots (`uncertainty_pre` BEFORE belief update, `uncertainty_post` AFTER)
- Epistemic action scheduling (after observation, creates pending action)

Added methods:
- `_execute_epistemic_cycle()`: Executes epistemic action at cycle k+1
- `_write_epistemic_event()`: Logs to epistemic.jsonl

## Integer Cycle Semantics

Epistemic actions follow identical semantics to mitigation:
- Consumes a full integer cycle (not a subcycle)
- If cycle k has high uncertainty, epistemic action executes at cycle k+1
- Science resumes at cycle k+2
- No floats, no cycle reuse, strict monotonic progression

## Critical Implementation Details

### Timing Fix (User Correction)
Snapshot uncertainty at correct moments:
- `uncertainty_pre`: BEFORE `agent.update_from_observation()` (line ~420)
- `uncertainty_post`: AFTER `agent.update_from_observation()` (line ~427)
- Decision uses `uncertainty_post` (post-update measurement)

### EXPAND Determinism (User Correction)
EXPAND must pass real `previous_observation` to maintain determinism:
```python
return self.propose_next_experiment(capabilities, previous_observation=previous_observation_dict)
```

### Replication Cap (User Correction)
GUARDRAIL prevents infinite loops:
```python
if self.consecutive_epistemic_replications >= max_consecutive_replications:
    self.consecutive_epistemic_replications = 0  # Reset counter
    return (EpistemicAction.EXPAND, "Max consecutive replications (2) reached, forcing expansion...")
```

### Test Strategy (User Correction)
Mock estimator only, NOT belief dynamics:
```python
with patch.object(
    loop.agent.beliefs,
    'estimate_calibration_uncertainty',
    side_effect=mock_uncertainty
):
    loop.run()
```

## Test Results

All three required tests pass:

```
tests/integration/test_epistemic_actions.py::test_epistemic_determinism PASSED
tests/integration/test_epistemic_actions.py::test_epistemic_budget_conservation PASSED
tests/integration/test_epistemic_actions.py::test_epistemic_action_switching PASSED
```

### Test Insights

1. **Determinism**: Identical seeds produce identical epistemic actions and rewards
2. **Budget Conservation**:
   - REPLICATE costs 2× previous proposal wells (by design, for tighter CI)
   - Total budget: `initial = spent + remaining` (verified)
3. **Action Switching**:
   - High uncertainty (>4.0 bits) → REPLICATE chosen
   - Low uncertainty (≤4.0 bits) → EXPAND chosen
   - Consecutive cap (2) enforced → forced EXPAND after 2 REPLICATEs

## Logging

Epistemic actions are logged to `{run_id}_epistemic.jsonl`:

```json
{
  "cycle": 2,
  "cycle_type": "epistemic_action",
  "flagged_cycle": 1,
  "seed": 42,
  "action": "replicate",
  "action_cost_wells": 192,
  "action_cost_plates": 2.0,
  "budget_plates_remaining": 0.0,
  "reward": 0.0,
  "metrics": {
    "uncertainty_before": 6.5,
    "uncertainty_after": 6.5,
    "delta_uncertainty": 0.0,
    "consecutive_replications": 1
  },
  "rationale": "High calibration uncertainty (6.50 bits > 4.0 threshold), replicate to tighten ruler confidence (consecutive: 1/2)"
}
```

## Future Work

### Phase 2: Real Biological Uncertainty (Not Implemented)

Option B (dose coverage proxy) or real mechanism posteriors would measure uncertainty about IC50, dose-response parameters, mechanism identity. This requires:
- IC50 fitting machinery
- Bayesian posterior distributions
- Information gain from dose ladder exploration

**Current status:** Not implemented. System only tracks calibration uncertainty (Option A).

## Key Takeaways

1. **Philosophy**: "Measure the ruler before measuring biology" - prioritize calibration uncertainty reduction
2. **Honest uncertainty**: Uses only real, tracked uncertainty (`calibration_entropy_bits`), not invented metrics
3. **Deterministic behavior**: Same seed → same actions → same rewards (reproducibility)
4. **Budget discipline**: REPLICATE doubles wells (2× replicates), EXPAND uses normal policy cost
5. **Guardrails**: Replication cap (2) prevents budget death spiral if uncertainty doesn't drop

## References

- **Mitigation pattern**: `src/cell_os/epistemic_agent/mitigation.py`
- **Accountability system**: `src/cell_os/epistemic_agent/accountability.py`
- **BeliefState**: `src/cell_os/epistemic_agent/beliefs/state.py`
- **Policy**: `src/cell_os/epistemic_agent/agent/policy_rules.py`
- **Loop orchestration**: `src/cell_os/epistemic_agent/loop.py`
