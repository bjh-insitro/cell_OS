# Epistemic Agent System Exploration

**Date**: 2024-12-19
**Scope**: Deep dive into `src/cell_os/epistemic_agent/` architecture and design bridge

---

## Executive Summary

The **epistemic_agent** system is a **provenance-first AI research agent** that enforces auditable, reproducible experimentation through a **design bridge** between agent proposals and execution.

**Core Philosophy**: "Refusal without a receipt is just a crash with posture."

**Key Achievement**: Every agent decision produces a persistent, replayable design artifact with validation teeth.

---

## Architecture Overview

### Module Structure (1728 lines total)

```
src/cell_os/epistemic_agent/
├── design_bridge.py (420 lines)      # Core: Proposal → Design → Validate → Persist
├── world_with_bridge.py (268 lines)  # Execution layer with bridge enforcement
├── loop.py (418 lines)               # Agent loop coordination
├── world.py (343 lines)              # Base world model
├── exceptions.py (152 lines)         # Covenant violations (structured, not string-parsed)
├── schemas.py (109 lines)            # Proposal, WellSpec data structures
├── beliefs/ (ledger, state)          # Belief tracking with provenance
├── acquisition/ (chooser)            # Experiment selection
└── agent/ (policy_rules)             # Decision logic
```

### The Seven Covenants (Referenced)

From `exceptions.py` and `REFUSAL_AND_RETRY_THEOLOGY.md`:

1. **C1-C4**: (Not directly in bridge, likely in agent logic)
2. **C5**: Agent Must Refuse What It Cannot Guarantee
3. **C6**: Every Decision Must Have a Receipt
4. **C7**: We Optimize for Causal Discoverability, Not Throughput

---

## Design Bridge: The Core Innovation

### Flow

```
Agent Proposal
    ↓
proposal_to_design_json()        # Convert to design artifact
    ↓
validate_design()                # Check lab constraints
    ↓ [PASS]              ↓ [FAIL]
persist_design()     persist_rejected_design()
    ↓                         ↓
Execute              Quarantine + Reason File
```

### Key Functions

#### 1. `proposal_to_design_json(proposal, cycle, run_id, well_positions) → design`

Converts agent's `Proposal` (intent) to design JSON (executable artifact).

**Input**: `Proposal` with `WellSpec` list
```python
Proposal(
    design_id="test_design_001",
    hypothesis="DMSO control vs compound X",
    wells=[WellSpec(cell_line="A549", compound="DMSO", dose_uM=0.0, time_h=24), ...]
)
```

**Output**: Design JSON matching `data/designs/*.json` schema
```json
{
  "design_id": "test_design_001",
  "design_type": "autonomous_epistemic",
  "description": "DMSO control vs compound X",
  "metadata": {...},
  "wells": [
    {
      "cell_line": "A549",
      "compound": "DMSO",
      "dose_uM": 0.0,
      "timepoint_h": 24,
      "well_pos": "C05",
      "plate_id": "Agent_...",
      ...
    }
  ]
}
```

#### 2. `validate_design(design, strict=True) → None | raises InvalidDesignError`

Validates design against lab constraints.

**Current status**: PLACEHOLDER validation
- Checks: required fields, well format (A01-H12), non-negative doses, positive timepoints, no duplicates
- **NOT checking**: compound library, dose ranges, plate capacity, multi-day constraints

**Important**: All errors set `validator_mode="placeholder"` to prevent false sense of safety.

**Violation codes** (structured, not string-parsed):
- `missing_required_field`
- `invalid_wells_structure`
- `empty_design`
- `missing_well_field`
- `invalid_well_position`
- `negative_dose`
- `invalid_timepoint`
- `duplicate_well_positions`

#### 3. `persist_design(design, output_dir, run_id, cycle) → filepath`

Writes validated design to disk for provenance and replay.

**Filename format**: `{run_id}_cycle_{cycle:03d}_{design_id[:8]}.json`

**Example**: `test_run_001_cycle_001_test_des.json`

#### 4. `persist_rejected_design(design, output_dir, run_id, cycle, violation_code, violation_message, ...) → (design_path, reason_path)`

Quarantines invalid designs with structured reason files.

**Output**:
- `rejected/{run_id}_cycle_{cycle:03d}_{design_id[:8]}_REJECTED.json` - Invalid design
- `rejected/{run_id}_cycle_{cycle:03d}_{design_id[:8]}_REJECTED.reason.json` - Rejection reason

**Reason file format**:
```json
{
  "violation_code": "duplicate_well_positions",
  "violation_message": "Duplicate well positions: ['C05']",
  "validator_mode": "placeholder",
  "design_hash": "a1b2c3d4e5f67890",
  "caught_at": {
    "cycle": 1,
    "run_id": "test_run_001",
    "timestamp": "2024-12-19T...",
    "git_sha": null
  },
  "design_path": "/path/to/rejected/..."
}
```

#### 5. `compute_design_hash(design) → str`

Computes deterministic 16-char hex hash for replay verification.

**Hashes ONLY execution-relevant fields**:
- design_id
- wells: cell_line, compound, dose_uM, timepoint_h, well_pos, plate_id, day, operator, is_sentinel

**Excludes** (no hash pollution):
- metadata.created_at
- metadata.comments
- paths
- timestamps

**Purpose**: Replay verification - same design hash → same execution

---

## Test Suite: "Teeth" Not Coverage

`tests/unit/test_epistemic_bridge_teeth.py` (603 lines)

These are **ENFORCEMENT tests**, not coverage tests. If they break, epistemic guarantees are broken.

### Tooth #1: Replay Determinism

**Test**: `test_design_hash_is_stable_across_reloads`

**Proof**: Design artifact is sufficient for reproduction
```python
design_v1 → persist → reload → design_v2
assert compute_design_hash(design_v1) == compute_design_hash(design_v2)
```

**If this fails**: Your "receipt" is decorative, not functional.

### Tooth #2: No-Bypass

**Test**: `test_invalid_design_raises_before_execution`

**Proof**: Invalid designs are REJECTED before execution (Covenant 5)
```python
design["wells"][0]["well_pos"] = "Z99"  # Invalid
with pytest.raises(InvalidDesignError):
    validate_design(design)
```

**Enforcement**: Structured exception with:
- `violation_code` (machine-readable)
- `covenant_id = "C5"`
- `validator_mode = "placeholder"`

### Tooth #3: Rejected Design Persistence

**Test**: `test_rejected_design_is_persisted_with_reason`

**Proof**: Refusal produces audit trail
```python
invalid_design → persist_rejected_design → (rejected.json, reason.json)
assert rejected_path.exists()
assert reason_path.exists()
```

**If this fails**: "Refusal without a receipt is just a crash with posture."

### Test Results

```
✓ test_design_hash_is_stable_across_reloads PASSED
✓ test_hash_changes_when_execution_relevant_field_changes PASSED
✓ test_hash_unchanged_when_metadata_changes PASSED
✓ test_invalid_design_raises_before_execution PASSED
✓ test_invalid_design_produces_rejection_with_provenance PASSED
✓ test_design_to_well_assignments_is_only_execution_path PASSED
✓ test_rejected_design_is_persisted_with_reason PASSED
✓ test_rejected_design_hash_is_computed PASSED
✓ test_persistence_failure_sets_audit_degraded PASSED
✓ test_validation_errors_indicate_placeholder_status PASSED
```

**All 10 enforcement tests passing** ✓

---

## Exception Hierarchy

### `EpistemicInvariantError` (Base)

When you see this: something violated the epistemic charter.
**Do not catch and continue. Fix the violation.**

### `InvalidDesignError` (Covenant 5)

Raised when agent proposes design violating lab constraints.

**Structured fields** (no parsing needed):
- `violation_code`: Machine-readable
- `design_id`: Proposal ID
- `rejected_path`: Path to quarantined design
- `reason_path`: Path to reason file
- `validator_mode`: "placeholder" | "full"
- `audit_degraded`: True if refusal artifacts failed to write
- `audit_error`: Error message if audit_degraded=True

### `DecisionReceiptInvariantError` (Covenant 6)

Raised when `choose_next()` returns without decision receipt.

**Required receipt fields**:
- template, forced, trigger, regime, gate_state (always)
- enforcement_layer (if forced or abort)
- attempted_template, calibration_plan (if abort)

### `BeliefLedgerInvariantError` (Covenant 7)

Raised when beliefs mutate without evidence events.

**Violation**: Direct mutation (`beliefs.field = value`) loses provenance.
**Correct**: Call `_set()` to emit evidence events.

### `RefusalPersistenceError`

Raised when refusal artifacts fail to write.

**Critical distinction**:
- Refusal is STILL enforced (agent still refuses)
- But audit trail is DEGRADED (receipt write failed)
- Caller must surface this degradation explicitly

---

## Relationship to Phase 5/6A Work

### Current Gap

**Phase 5/6A**: BiologicalVirtualMachine with epistemic control (weak signatures, temporal tradeoffs)

**Epistemic Agent**: Design validation and provenance enforcement

**Missing Connection**: The epistemic_agent system doesn't currently integrate with:
- Phase 5 masked compounds (potency/toxicity scalars)
- Phase 5 epistemic policies (smart probe-commit strategies)
- Phase 6A beam search (action sequence planning)

### Potential Integration Points

1. **Beam search → Design bridge**
   - Beam search currently produces raw `Policy` objects
   - Could wrap in `Proposal` → `design_bridge` → validated artifact
   - Enforcement: Invalid beam policies rejected before execution

2. **Phase 5 classifier → Design validation**
   - Add validator rule: "If predicted axis with confidence < 0.15, refuse execution"
   - Structured violation: `violation_code="low_confidence_classification"`

3. **Audit trail for search iterations**
   - Persist rejected beam candidates with reason="death_budget_exceeded"
   - Enable debugging: "Why didn't beam search try X?"

---

## Key Insights

### 1. **Placeholder Status is Explicit**

All validation errors set `validator_mode="placeholder"` until full validation active.

**This prevents false sense of safety.**

From code comment:
> IMPORTANT: This is currently PLACEHOLDER validation that only checks
> structural requirements. Full validation (compound library, dose ranges,
> plate capacity, multi-day constraints) is NOT ACTIVE.

### 2. **Refusal is Righteous AND Auditable**

Not enough to refuse invalid designs - must persist WHY.

**Rejected design artifacts**:
- Invalid design JSON (for diff tracking)
- Reason file with structured violation
- Design hash (for comparing retry attempts)
- Git SHA (for reproducibility)

### 3. **Hash Excludes Metadata Pollution**

Design hash only includes execution-relevant fields.

**Changes that DON'T affect hash** (correct):
- Timestamps
- Paths
- Comments

**Changes that DO affect hash** (correct):
- Dose, compound, timepoint
- Well positions
- Cell line

### 4. **Exceptions are Structured, Not String-Parsed**

All epistemic errors have structured fields:
- `violation_code` (machine-readable)
- `covenant_id` (which covenant violated)
- `details` (dict with context)

**No string parsing needed** for programmatic handling.

---

## TODO Items Found in Code

From `design_bridge.py`:
```python
# TODO: Import actual validation logic from src/cell_os/simulation/design_validation.py
```

This is the main gap: placeholder validation needs to become full validation.

---

## Recommendations

### 1. **Keep Enforcement Tests Passing**

These 10 tests are the teeth. If they break, the guarantees are broken.

### 2. **Upgrade Validator from Placeholder to Full**

Import `src/cell_os/simulation/design_validation.py` logic:
- Compound library checks
- Dose range validation
- Plate capacity limits
- Multi-day constraints

Set `validator_mode="full"` once active.

### 3. **Integrate with Phase 6A Beam Search**

Wrap beam search policies in design bridge:
- Beam candidate → Proposal → Design JSON → Validate
- Invalid candidates: persist rejection with reason
- Enables audit: "Why was this schedule rejected?"

### 4. **Add Epistemic Validators**

Phase 5-specific rules:
- Refuse if classifier confidence < threshold
- Refuse if death trajectory exceeds budget mid-search
- Refuse if intervention count > 2

---

## Conclusion

The epistemic_agent system is a **well-designed provenance enforcement layer** that:
- ✅ Ensures every execution has a persistent design artifact
- ✅ Validates designs before execution (Covenant 5)
- ✅ Produces audit trail for refusals
- ✅ Enables deterministic replay
- ✅ All enforcement tests passing

**Status**: Production-ready foundation for provenance enforcement.

**Gap**: Placeholder validation needs upgrade to full validation.

**Opportunity**: Integrate with Phase 6A beam search for auditable policy planning.
