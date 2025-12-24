# Mitigation Implementation Status & Integration Plan

## Current Status

### ✓ Components Implemented

1. **Core Logic** (`src/cell_os/epistemic_agent/mitigation.py`)
   - Reward computation: WORKS ✓
   - QC summary extraction: WORKS ✓
   - Context tracking: WORKS ✓

2. **Agent Decision** (`src/cell_os/epistemic_agent/agent/policy_rules.py`)
   - `choose_mitigation_action()`: WORKS ✓
   - `create_mitigation_proposal()`: WORKS ✓
   - Layout epoch tracking: WORKS ✓

3. **Spatial Variance** (`src/cell_os/epistemic_agent/world.py`)
   - Layout seed support: WORKS ✓
   - Position shuffling: WORKS ✓
   - REPLATE produces different layouts: VERIFIED ✓

4. **Schemas** (`src/cell_os/epistemic_agent/schemas.py`)
   - `layout_seed` field: ADDED ✓

5. **Helpers** (`src/cell_os/epistemic_agent/accountability.py`)
   - `make_replate_proposal()`: WORKS ✓
   - `make_replicate_proposal()`: WORKS ✓

### ⚠️ Loop Integration: INCOMPLETE

**Problem:** Loop orchestration code did not persist due to file modification conflicts.

**Current state:**
- Mitigation check method added but not called from main loop
- Mitigation execution method added but placeholder only
- No cycle-to-cycle state management

## The Temporal Provenance Issue

### Root Cause
Belief system requires **strict monotonic integer cycle ordering**. Any violation causes:
```
Ledger refused to write belief_update with evidence_time_h=None;
temporal provenance would be lost
```

### The Correct Cycle Semantics

```
Cycle 1 (science):  observation → QC flagged → mark mitigation pending
Cycle 2 (mitigation): execute REPLATE/REPLICATE → observation → update beliefs
Cycle 3 (science):  normal science resumes
```

**CRITICAL RULES:**
1. Never reuse a cycle number
2. Never use float cycle numbers (no cycle 1.5)
3. Mitigation consumes a full integer cycle
4. Beliefs always see monotonically increasing integers

### What I Initially Did Wrong

I tried to use "cycle + 0.5" for mitigation subcycles. This violates temporal provenance.

### The Fix

Mitigation must be integrated into the main loop as:

```python
for cycle in range(1, self.max_cycles + 1):
    # Check if mitigation pending from previous cycle
    if hasattr(self, '_pending_mitigation'):
        # THIS CYCLE IS MITIGATION
        self._execute_mitigation_cycle(cycle, capabilities)
        continue  # Skip normal science this cycle

    # Normal science cycle
    proposal = self.agent.propose_next_experiment(...)
    observation = self.world.run_experiment(...)
    self.agent.update_from_observation(observation)  # cycle passed internally

    # Check if QC flagged
    if self._check_mitigation_needed(observation):
        # Mark for next cycle
        self._pending_mitigation = {...}
```

This ensures:
- Mitigation uses integer cycle `k+1`
- Beliefs see cycle sequence: k, k+1, k+2, ...
- No float cycles
- No cycle reuse

## Next Steps to Complete Integration

### Step 1: Fix Loop Orchestration (15 minutes)

Edit `src/cell_os/epistemic_agent/loop.py` main `run()` method:

```python
# At start of for loop (line ~112)
for cycle in range(1, self.max_cycles + 1):
    # NEW: Check for pending mitigation
    if hasattr(self, '_pending_mitigation'):
        executed = self._execute_mitigation_cycle(cycle, capabilities)
        if executed:
            continue  # Mitigation consumed this cycle, skip to next

    # Existing code: normal science cycle
    if self.world.budget_remaining <= 0:
        ...
```

### Step 2: Implement Full Mitigation Execution (30 minutes)

Replace placeholder in `_execute_mitigation_cycle()` with:

```python
def _execute_mitigation_cycle(self, cycle: int, capabilities: dict) -> bool:
    """Execute mitigation using THIS integer cycle number."""

    context = self._pending_mitigation
    prev_proposal = self._get_last_proposal_from_history()

    # Agent decides action
    action, rationale = self.agent.choose_mitigation_action(
        observation=prev_observation,  # from history
        budget_plates_remaining=self.world.budget_remaining / 96.0,
        previous_proposal=prev_proposal
    )

    if action == MitigationAction.NONE:
        # Log penalty, return
        ...
        return True

    # Create mitigation proposal
    proposal = self.agent.create_mitigation_proposal(action, prev_proposal, capabilities)

    # Execute
    raw_results = self.world.run_experiment(proposal)
    observation = aggregate_observation(...)

    # CRITICAL: Update beliefs with THIS integer cycle
    self.agent.beliefs.begin_cycle(cycle)
    self.agent.update_from_observation(observation)
    events = self.agent.beliefs.end_cycle()

    # Compute reward
    flagged_after, I_after, details_after = get_spatial_qc_summary(observation)
    reward = compute_mitigation_reward(
        action, context['morans_i_before'], I_after,
        flagged_before=True, flagged_after=flagged_after,
        cost=len(proposal.wells) / 96.0
    )

    # Log
    self._write_mitigation_event({
        "cycle": cycle,  # INTEGER
        "cycle_type": "mitigation",
        "action": action.value,
        "reward": reward,
        ...
    })

    return True
```

### Step 3: Add Provenance Assertion (5 minutes)

In `src/cell_os/epistemic_agent/beliefs/state.py` or wherever beliefs ingest happens:

```python
def begin_cycle(self, cycle: int):
    """Begin new cycle with strict monotonicity check."""
    assert isinstance(cycle, int), f"Cycle must be int, got {type(cycle)}"
    if hasattr(self, 'last_cycle'):
        assert cycle > self.last_cycle, (
            f"Non-monotonic cycle: {cycle} after {self.last_cycle}"
        )
    self.last_cycle = cycle
    ...
```

### Step 4: Test

```bash
pytest tests/integration/test_mitigation_closed_loop.py::test_replicate_doubles_wells -xvs
# Should pass (already does)

pytest tests/integration/test_mitigation_closed_loop.py::test_replate_changes_spatial_layout -xvs
# Should pass (already does)

# Full loop test will need the loop integration complete first
```

## Why This Will Work

1. **Integer cycles only**: No floats, no subcycles in belief keys
2. **Strict monotonicity**: Mitigation consumes k+1, science resumes at k+2
3. **Clean state**: Pending mitigation stored as attribute, cleared after use
4. **Deterministic**: Layout epoch, seed, and cycle progression all deterministic

## Estimated Time to Complete

- Loop orchestration fix: 15 min
- Full mitigation execution: 30 min
- Provenance assertion: 5 min
- Testing: 10 min

**Total: ~1 hour of focused implementation**

## Current Test Results

✓ Unit tests pass (REPLICATE, REPLATE, rewards)
✗ Integration test blocked by loop orchestration not complete
✗ Provenance bug will be fixed by integer cycle semantics

## Files That Need Editing

1. `src/cell_os/epistemic_agent/loop.py` - main run() method (add mitigation check at loop start)
2. `src/cell_os/epistemic_agent/loop.py` - _execute_mitigation_cycle() (replace placeholder)
3. `src/cell_os/epistemic_agent/beliefs/state.py` - add monotonicity assertion (optional but recommended)

## The Core Insight

**Mitigation is not a "subcycle" - it's a full cycle that consumes an integer index.**

This aligns with the physical reality: you can't run science and mitigation simultaneously.
If cycle 5 triggers mitigation, cycle 6 IS the mitigation, and cycle 7 is the next science.

This is the correct mental model and the correct implementation.
