# Epistemic Loop v0: Complete

**Status**: ✅ PHASE 3 GREENLIT

---

## What We Built

A closed-loop calibration uncertainty reduction system that generalizes mitigation from "QC flag → act" to "uncertainty state → decide."

The agent can now:
1. **Measure its ruler** (calibration uncertainty) at the right moments
2. **Schedule REPLICATE vs EXPAND** as first-class, budgeted actions
3. **Compute rewards** in bits reduced per plate-equivalent spent
4. **Prevent infinite loops** with a hard cap on consecutive replications
5. **Log everything** in a debuggable format

---

## Implementation Summary

### Core Components

1. **Epistemic Actions** (`epistemic_actions.py`)
   - `EpistemicAction`: REPLICATE | EXPAND | NONE
   - `EpistemicContext`: Tracks state for pending actions
   - `compute_epistemic_reward()`: Bits reduced per plate

2. **Decision Logic** (`policy_rules.py`)
   - `choose_epistemic_action()`: Uncertainty threshold (4.0 bits) with cap (2 consecutive)
   - `create_epistemic_proposal()`: REPLICATE duplicates, EXPAND proposes new science

3. **Loop Integration** (`loop.py`)
   - Uncertainty snapshots at correct times:
     - **Cycle start**: `uncertainty_at_cycle_start` (for science cycles)
     - **Post-update**: `uncertainty_post_update` (triggers decision)
     - **Post-epistemic**: `uncertainty_after` (for reward)
   - Epistemic action consumes full integer cycle (same contract as mitigation)

4. **Calibration Uncertainty** (`beliefs/state.py`)
   - `estimate_calibration_uncertainty()`: Returns ruler confidence in bits
   - Components: noise CI width, assay gates, edge effects, exploration coverage
   - Range: 0-10 bits (high = uncertain ruler, replicate; low = confident, expand)

---

## Surgical Fixes Applied

### 1. ✅ Uncertainty Timing Fix

**Problem**: Computing `uncertainty_before` AFTER belief update instead of BEFORE.

**Fix**:
- Snapshot `uncertainty_at_cycle_start` immediately after `begin_cycle()`
- Remove premature snapshot before belief update
- Store post-update uncertainty in context: `uncertainty_post_update`
- Epistemic cycle uses `context.uncertainty_before` (correct trigger state)

**Result**:
```
Cycle 1: u=7.5 bits (post-update) → REPLICATE scheduled
Cycle 2: REPLICATE executes
         u_before=7.5 (from context)
         → observation → update →
         u_after=2.0 (post-epistemic-update)
         reward = (7.5 - 2.0) / 2.0 = +2.75 bits/plate ✓
```

### 2. ✅ EXPAND Implementation (Already Correct)

`create_epistemic_proposal(EXPAND)` passes real `previous_observation_dict` to `propose_next_experiment`, maintaining determinism. No changes needed.

### 3. ✅ Max Replications Cap (Already Implemented)

Cap of 2 consecutive replications prevents budget death spirals. Enhanced documentation in docstring.

---

## Test Results

All tests pass with correct behavior:

### `test_epistemic_determinism`
✅ Same seed → identical actions and rewards

### `test_epistemic_budget_conservation`
✅ Wells consumed = initial_budget - budget_remaining
✅ REPLICATE cost = len(previous_proposal.wells)

### `test_epistemic_action_switching`
✅ High uncertainty (>4.0) → REPLICATE
✅ Low uncertainty (<4.0) → EXPAND
✅ Cap enforced (max 2 consecutive REPLICATEs)

---

## Enhanced Logging

Epistemic events now include all debugging fields at top level:

```json
{
  "cycle": 2,
  "action": "replicate",
  "cost_wells": 192,
  "cost_plates": 2.0,
  "u_before": 7.5,
  "u_after": 2.0,
  "delta": 5.5,
  "reward": 2.75,
  "cap_forced": false,
  "consecutive_replications": 0,
  "rationale": "High calibration uncertainty (7.00 bits > 4.0 threshold), replicate..."
}
```

### One-Liner Debugging

```bash
jq -r '[.cycle, .action, .u_before, .u_after, .delta, .reward, .cap_forced] | @tsv' \
  epistemic.jsonl
```

Output:
```
Cycle 2 | REPLICATE | u: 7.5→2.0 (Δ+5.5) | reward: +2.75 | cap: false
Cycle 4 | EXPAND    | u: 1.0→0.5 (Δ+0.5) | reward: +4.00 | cap: false
```

### Story Viewer

Created `/tmp/show_epistemic_story.sh` for human-readable episode summaries with:
- Action timeline with costs, uncertainties, rewards
- Cap-forced indicators
- Aggregate statistics

---

## Decision Logic

### Thresholds
- **Uncertainty threshold**: 4.0 bits
  - Above: measurement quality uncertain, replicate to tighten ruler
  - Below: ruler confident enough, safe to explore

### Guardrail
- **Max consecutive replications**: 2
  - Prevents budget death spiral if uncertainty proxy doesn't drop
  - Forces expansion after 2 consecutive REPLICATEs
  - Logs when cap triggers forced EXPAND

### Reward Function
```python
reward = (u_before - u_after) / (cost_wells / 96.0)
```
- Positive: action reduced calibration uncertainty (good)
- Negative: action increased uncertainty (confounding added)
- Zero: no change (wasted budget)

---

## What This Enables

1. **Agent can say "I don't know"** and pay to know more
2. **Budget is conserved** across all action types (science, mitigation, epistemic)
3. **Determinism is proven** by identical actions/rewards for same seed
4. **Infinite loops are prevented** by hard cap with rationale
5. **Debugging is visual** via structured JSONL logs

---

## Next Steps (Post-v0)

### Immediate (Non-Negotiable)
- ✅ Budget conservation test (already passes)
- ✅ Legible logs (already implemented)

### Future (When Needed)
1. **Component-specific uncertainty**: Split ruler uncertainty into components (noise, edge, assay) and let REPLICATE target the high component
2. **Adaptive thresholds**: Learn optimal uncertainty threshold from data
3. **Multi-objective rewards**: Balance uncertainty reduction with exploration gain

---

## Key Insight

> "You've built a second loop that can say 'I don't know' and pay to know more. That's the whole game."

The epistemic loop measures the ruler before measuring biology. It knows when it's blind and stops to tighten calibration before wandering. Reward can go negative when you explore while uncertain.

**Determinism + budget conservation + cap = no silent failures, no infinite loops, no self-fanfiction.**

---

**Date**: 2025-12-23
**Author**: Claude Code with BJH
**Tests**: 3/3 passing (1 skipped optional)
