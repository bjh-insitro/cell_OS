# System-Level Closure: EpisodeSummary + Health Debt

**Status**: Implemented
**Date**: 2025-12-23
**Goal**: Close the loop at the system level to prevent "locally smart but globally useless" behavior

## What Was Built

### 1. Episode-Level Governance (`episode_summary.py`)

A structured accounting system that answers: **"What is the unit of progress?"**

**Data structures:**
- `BudgetSpending`: What we spent (wells, plates, calibration vs exploration, edge wells)
- `EpistemicLearning`: What we learned (gain, variance reduction, gates earned/lost)
- `HealthSacrifices`: What we sacrificed (health debt, mitigation actions, contract violations)
- `MitigationEvent`: Single mitigation action with trigger and outcome
- `InstrumentHealthTimeSeries`: Instrument health evolution over episode
- `EpisodeSummary`: Complete episode accounting with aggregate metrics

**Key metrics:**
- `efficiency_bits_per_plate`: Information gained per resource spent
- `health_balance`: Debt repaid - debt accumulated
- `exploration_ratio`: Science wells / total wells

**Output:**
- Written to `{run_id}_episode_summary.json` at episode end
- Human-readable summary in console logs

### 2. Health Debt Tracking (`beliefs/state.py`)

A state variable that tracks instrument quality degradation and forces the agent to pay it down.

**Fields added to BeliefState:**
- `health_debt`: Accumulated quality debt (unitless, ~0-10 range)
- `health_debt_history`: Per-cycle tracking for time series

**Methods:**
- `accumulate_health_debt(morans_i, nuclei_cv, segmentation_quality)`: Accumulates debt from QC violations
  - Moran's I excess (> 0.15): `+10 * (morans_i - 0.15)`
  - Nuclei CV excess (> 0.20): `+5 * (nuclei_cv - 0.20)`
  - Segmentation deficit (< 0.80): `+3 * (0.80 - segmentation_quality)`
- `decay_health_debt(decay_rate, reason)`: Decays debt after high-quality runs or mitigation
  - Default 20% decay per clean cycle
  - Higher decay for mitigation actions
- `get_health_debt_pressure()`: Returns policy guidance
  - "low" (< 2.0): safe to explore
  - "medium" (2.0-5.0): prefer calibration
  - "high" (> 5.0): urgent mitigation needed

### 3. Loop Integration (`loop.py`)

**Initialization:**
- Episode summary initialized at start of `run()`
- Tracks initial calibration entropy and noise CI width for delta calculations

**Finalization:**
- `_finalize_episode_summary()` method aggregates:
  - Spending from history (classify by action type, calibration vs exploration)
  - Learning from beliefs (entropy reduction, gates earned/lost, variance reduction)
  - Sacrifices from health debt history and mitigation/epistemic files
  - Instrument health time series from QC flags
- Computes aggregate metrics (efficiency, health balance, exploration ratio)
- Writes JSON summary to disk
- Prints human-readable summary to console

### 4. Integration Tests (`tests/integration/test_episode_summary.py`)

**Coverage:**
- `test_episode_summary_generation`: Verifies summary is created and has valid sections
- `test_episode_summary_tracks_mitigation`: Verifies mitigation timeline is captured
- `test_episode_summary_tracks_gates`: Verifies gates earned/lost tracking
- `test_health_debt_accumulation_and_decay`: Tests debt accumulation/repayment logic
- `test_episode_summary_budget_breakdown`: Verifies budget accounting sums correctly
- `test_episode_summary_with_abort`: Tests graceful handling of aborted runs

## What This Prevents

1. **Local optimality trap**: "Reward went up" is no longer sufficient. System must show what it learned and at what cost.

2. **Budget waste**: Explicit tracking of calibration vs exploration spending surfaces inefficient allocation.

3. **Quality drift**: Health debt accumulation forces the agent to address instrument degradation, not just ignore it.

4. **Unmeasured sacrifice**: Mitigation timeline shows when and why the system had to stop science to fix problems.

## What's Still Missing

### Short-term (next PR):
1. **Calibration as first-class action**: Make calibration an explicit action in the action space, not just a template choice.
   - Allows agent to explicitly choose "calibrate now vs press forward" based on expected information value
   - Policy can reference health debt pressure to prioritize calibration when debt is high

### Medium-term:
2. **Per-cycle epistemic gain tracking**: Currently using entropy delta as proxy. Should sum realized gain from epistemic controller claims.

3. **Structured QC metrics in observations**: Currently parsing QC metrics from text flags. Should be structured data for cleaner tracking.

4. **Contract violation tracking**: Placeholder (always 0). Should aggregate from contract reports.

5. **Edge well precision**: Currently estimating ~20% edge wells. Should track actual plate layout.

### Long-term:
6. **Model confidence metric**: Placeholder for future mechanism posterior confidence tracking.

7. **Prediction error on held-out conditions**: Gold standard unit of progress metric.

## Files Modified

- `src/cell_os/epistemic_agent/episode_summary.py` (new)
- `src/cell_os/epistemic_agent/beliefs/state.py` (added health_debt fields and methods)
- `src/cell_os/epistemic_agent/loop.py` (integrated episode summary generation)
- `tests/integration/test_episode_summary.py` (new)

## Usage Example

```python
from cell_os.epistemic_agent.loop import EpistemicLoop

# Run episode
loop = EpistemicLoop(budget=384, max_cycles=10, seed=42)
loop.run()

# Access episode summary
summary = loop.episode_summary

print(f"Efficiency: {summary.efficiency_bits_per_plate:.3f} bits/plate")
print(f"Health balance: {summary.health_balance:+.2f}")
print(f"Gates earned: {summary.learning.gates_earned}")
print(f"Mitigation actions: {len(summary.mitigation_timeline)}")

# Summary JSON written to: results/epistemic_agent/{run_id}_episode_summary.json
```

## Next Steps

See "What's Still Missing" section above. Priority: **calibration as first-class action**.

---

The uncomfortable question has been answered: **The unit of progress is epistemic gain per resource spent, with health debt held constant or decreasing.**

If efficiency drops, exploration ratio is too low, or health balance is negative, the system is failing at the system level, even if local reward is increasing.
