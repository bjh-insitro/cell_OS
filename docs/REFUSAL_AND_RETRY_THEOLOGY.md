# Refusal and Retry Theology

**Status**: v1.0 (Hard No-Retry Policy)
**Covenant**: 5 (Agent Must Refuse What It Cannot Guarantee)

## The Problem

When the agent proposes a design that violates lab constraints (invalid well positions, negative doses, duplicate wells, etc.), the system must:

1. **Refuse execution** before running the experiment
2. **Persist the refusal** as an auditable artifact (not just a crash)
3. **Decide whether to retry** with a degraded proposal or abort

The dangerous path is "try random stuff until it passes" — this turns validation into an adversarial game where the agent learns to cheat by battering the validator.

## Hard Rule: No Automatic Retries on Validation Failures

**Current policy**: When design validation fails, the agent **aborts immediately** with a refusal receipt.

### Why No Retries?

1. **Validation failure indicates a deeper problem**
   If the agent proposes an invalid design, it means:
   - The agent's internal model of lab constraints is wrong
   - The proposal generation logic has a bug
   - The agent is trying something outside the design schema

   Retrying with degradation papers over the root cause.

2. **No safe degradation axis exists yet**
   What does "degrade" mean for a multi-dimensional design?
   - Reduce number of wells? (loses statistical power)
   - Snap doses to a ladder? (changes the hypothesis)
   - Remove unsupported compounds? (abandons the experiment)
   - Simplify to calibration-only? (throws away learning)

   All of these *change the scientific intent*, not just the execution format.

3. **Retries can turn into adversarial optimization**
   If the agent learns "validator will reject X, so I'll try Y," it's no longer proposing what it believes is best — it's gaming the validator.

4. **Refusal is a signal**
   When the agent proposes something invalid, that's valuable information:
   - The chooser's candidate scoring is miscalibrated
   - The proposal templates need tighter constraints
   - The agent needs better priors about lab capabilities

   Hiding this signal with automatic retries makes the system harder to debug.

## Refusal Receipt Mechanism

When `InvalidDesignError` is raised, the system:

1. **Persists the rejected design** to quarantine:
   ```
   results/designs/<run_id>/rejected/
     └── <run_id>_cycle_<n>_<design_id>_REJECTED.json
     └── <run_id>_cycle_<n>_<design_id>_REJECTED.reason.json
   ```

2. **Writes a refusal receipt** to `decisions.jsonl`:
   ```json
   {
     "cycle": 5,
     "selected": "abort_invalid_design",
     "selected_candidate": {
       "template": "abort_invalid_design",
       "forced": true,
       "trigger": "design_validation_failed",
       "regime": "aborted",
       "enforcement_layer": "design_bridge",
       "attempted_template": "original_design_id",
       "invalid_design_path": "results/designs/run_001/rejected/...",
       "constraint_violation": "duplicate_well_positions",
       "validator_mode": "placeholder",
       "retry_policy": "no_retry_on_validation_failure"
     },
     "reason": "Design validation failed: duplicate_well_positions (placeholder validator)"
   }
   ```

3. **Aborts the run** with `abort_reason` set to violation details

This ensures:
- Refusal is **auditable** (design + reason persisted)
- Refusal has a **receipt** (decision event logged before abort)
- Refusal is **replayable** (rejected design can be re-validated)

## Future: Safe Retry Theology (Not Yet Implemented)

If we later decide retries are necessary, they must follow these rules:

### Rule 1: Max 1 Retry Per Cycle

Only one automatic retry attempt per cycle. If the second attempt fails, abort and demand human intervention.

### Rule 2: Monotonic Degradation Only

Retry must be a **monotonic simplification** along a declared axis:

1. **Dose snapping**: Round invalid doses to nearest valid ladder value
   - Must preserve dose ordering (don't swap control/treatment)
   - Must log `degradation_reason: "dose_snapped"`
   - Must log `diff_against_original_design_hash`

2. **Compound substitution**: Replace unsupported compound with DMSO
   - Only if compound is not the independent variable
   - Must log `degradation_reason: "compound_fallback_to_dmso"`

3. **Well reduction**: Remove invalid wells (preserve valid subset)
   - Only if removing wells doesn't destroy the experiment's statistical power
   - Must log `degradation_reason: "invalid_wells_removed"`

4. **Fallback to calibration**: Shrink to calibration-only template
   - Only if original design was exploratory
   - Must log `degradation_reason: "fallback_to_calibration"`

### Rule 3: Degradation Receipt

Every retry must record:
- `original_design_hash`: Hash of the rejected design
- `degraded_design_hash`: Hash of the retry attempt
- `degradation_reason`: Human-readable explanation
- `degradation_diff`: JSON diff of what changed
- `retry_attempt`: 1 (only one retry allowed)

### Rule 4: No Random Exploration

Retries must NOT:
- Try random parameter combinations
- Guess at valid values
- Approximate by dropping constraints silently

If the system can't safely degrade, it must abort.

## Implementation Checklist

- [x] Add `InvalidDesignError` exception (Covenant 5)
- [x] Add `persist_rejected_design()` to quarantine invalid designs
- [x] Add refusal receipt writing in `loop.py` (before abort)
- [x] Set retry policy to `"no_retry_on_validation_failure"`
- [ ] Add retry mechanism (future: only if safe degradation exists)
- [ ] Add degradation diff tracking (future)
- [ ] Add test for rejected design persistence
- [ ] Add test for refusal receipt completeness

## Validator Mode Field

The `validator_mode` field in rejection reasons indicates which validator caught the error:

- `"placeholder"`: Structural validation only (current)
  - Checks: required fields, well format, duplicates, dose/timepoint bounds
  - Does NOT check: compound library, dose ranges, plate capacity, multi-day constraints

- `"full"`: Complete validation against lab constraints (not yet active)
  - Checks: everything in placeholder + compound library + dose ranges + capacity + safety

When swapping in full validation:
1. Remove `[PLACEHOLDER VALIDATION]` prefix from error messages
2. Update violation code extraction to handle new error types
3. Add tests for full validation failures

## Philosophy: Intent vs Execution Hashes

The current `design_hash` includes execution-relevant fields:
- `cell_line`, `compound`, `dose_uM`, `timepoint_h`, `well_pos`
- `plate_id`, `day`, `operator`, `is_sentinel`

This means:
- Same design on different days → different hash (intentional)
- Same design with different operators → different hash (intentional)

This is correct for **replay determinism** (Covenant 6: same context = same outcome).

**Future consideration**: If we want "same biological intent regardless of operator/day," we'll need two hashes:
- `design_intent_hash`: biology + assay + doses + timepoints + geometry
- `execution_context_hash`: operator + day + instrument settings

Not needed today, but it prevents future philosophical arguments disguised as debugging.

## Summary

**Current state**: Validation failures abort immediately with full provenance (rejected design + reason + refusal receipt).

**Rationale**: No safe automatic retry mechanism exists. Retries risk turning validation into an adversarial game.

**Future**: If retries become necessary, they must be monotonic degradations with full audit trails.

**Enforcement**: This is Covenant 5 in action. The agent refuses what it cannot guarantee.
