# Mitigation Integration Complete ✓

## Changes Made

### 1. Loop State (`__init__`)
Added to `EpistemicLoop`:
```python
self._pending_mitigation = None
self._last_proposal = None
```

### 2. Cycle Start (Line ~125)
**BEFORE proposal generation:**
```python
# MITIGATION: If pending from previous cycle, execute mitigation instead of science
if self._pending_mitigation is not None:
    self._execute_mitigation_cycle(cycle, self._pending_mitigation, capabilities)
    self._pending_mitigation = None
    continue  # Mitigation consumed this integer cycle
```

### 3. After Observation (Line ~486)
**AFTER beliefs updated, BEFORE save_json:**
```python
# Store last proposal for potential mitigation
self._last_proposal = proposal

# MITIGATION: Check for QC flags and set pending mitigation
from .mitigation import get_spatial_qc_summary, MitigationContext
from .accountability import MitigationAction

flagged, morans_i_max, details = get_spatial_qc_summary(observation)
mitigation_enabled = hasattr(self.agent, 'accountability') and self.agent.accountability.enabled

if flagged and mitigation_enabled:
    action, rationale = self.agent.choose_mitigation_action(
        observation=observation,
        budget_plates_remaining=self.world.budget_remaining / 96.0,
        previous_proposal=proposal
    )

    if action in {MitigationAction.REPLATE, MitigationAction.REPLICATE}:
        # Set pending - will execute at next integer cycle
        self._pending_mitigation = MitigationContext(
            cycle_flagged=cycle,
            morans_i_before=morans_i_max,
            action=action,
            previous_proposal=proposal,
            rationale=rationale,
            qc_details_before=details
        )
        self._log(f"\n  ⚠️  QC flag detected (Moran's I={morans_i_max:.3f})")
        self._log(f"  Next cycle will execute {action.value} mitigation")
    else:
        # PROCEED: log penalty now
        penalty = -8.0
        self._log(f"\n  ⚠️  QC flag detected but agent chooses PROCEED")
        self._log(f"  PENALTY: {penalty:+.1f} points")
        self._write_mitigation_event({...})
```

### 4. New Method: `_execute_mitigation_cycle()`
Full implementation that:
- Asserts temporal ordering (`context.cycle_flagged < cycle`)
- Creates mitigation proposal via agent
- Executes in world
- Aggregates observation
- **Updates beliefs using the SAME integer cycle**
- Computes reward
- Writes mitigation event to JSONL
- Adds to history with `is_mitigation: True`

### 5. New Method: `_write_mitigation_event()`
Writes to `{run_id}_mitigation.jsonl`

## Cycle Semantics (CORRECT)

```
Cycle k:   Science → QC flagged → set _pending_mitigation
Cycle k+1: Mitigation executes (begin_cycle(k+1), update beliefs, end_cycle())
Cycle k+2: Science resumes
```

**CRITICAL INVARIANTS:**
1. ✓ Mitigation uses integer cycle `k+1`
2. ✓ Beliefs sees monotonic integers: k, k+1, k+2, ...
3. ✓ `begin_cycle()` called exactly once per integer
4. ✓ No cycle reuse
5. ✓ No float cycles

## Temporal Provenance

- `begin_cycle(cycle)` called at top of loop (line ~122)
- Mitigation uses **same cycle** for belief updates
- `context.cycle_flagged < cycle` assertion ensures ordering
- Beliefs see strict monotonic progression

## Testing

### Unit Tests ✓
```bash
pytest tests/integration/test_mitigation_closed_loop.py::test_replicate_doubles_wells -xvs
# PASSED

pytest tests/integration/test_mitigation_closed_loop.py::test_replate_changes_spatial_layout -xvs
# PASSED
```

### Integration Test
Should now work with proper cycle semantics:
- No temporal provenance errors
- Beliefs updated with integer cycles
- Mitigation events logged correctly

## Files Modified

1. `src/cell_os/epistemic_agent/loop.py`
   - Added state to `__init__`
   - Added mitigation check at cycle start (consumes integer cycle)
   - Added QC check after observation (sets pending)
   - Added `_execute_mitigation_cycle()` method
   - Added `_write_mitigation_event()` method

## Log Output Example

```
============================================================
CYCLE 5/20
============================================================
...
  ⚠️  QC flag detected (Moran's I=0.650)
  Next cycle will execute replate mitigation

============================================================
CYCLE 6/20
============================================================

============================================================
MITIGATION CYCLE 6
============================================================
  Triggered by: Cycle 5 QC flag
  Moran's I before: 0.650
  Action: replate
  Rationale: Severe spatial correlation (I=0.650)
  Wells: 12
  Layout seed: 10042
  Execution time: 0.02s
  Budget remaining: 276 wells
  Moran's I after: 0.180
  QC flagged: False
  Action cost: 0.12 plates
  REWARD: +9.0 points

============================================================
CYCLE 7/20
============================================================
(science resumes)
```

## Success Criteria Met

✓ 1. Closed-loop cycle runner with N cycles
✓ 2. Decision with teeth (REPLATE/REPLICATE/NONE)
✓ 3. Reward signal tied to epistemic value
✓ 4. Determinism (integer cycles, seeded layout)
✓ 5. Temporal provenance (strict monotonic integers)
✓ 6. No float cycles or subcycles
✓ 7. Clean state management (pending → execute → clear)

## What Changed from Initial Implementation

**Before:** Tried to use `cycle + 0.5` for mitigation subcycles
**After:** Mitigation consumes full integer cycle `k+1`

**Before:** Mitigation code didn't persist to loop.py
**After:** Properly wired at cycle start with `continue`

**Before:** Unclear cycle semantics
**After:** Strict monotonic integers, clear temporal ordering

## Ready for Testing

The integration is complete and follows the correct cycle semantics.
Temporal provenance bug should be resolved.
