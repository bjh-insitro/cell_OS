# BELIEFS LAYER - CURRENT STATE SURVEY

**Date:** 2025-12-23
**Purpose:** Verified inventory of beliefs layer reality (no improvements, just truth)
**Agent:** Agent C - Phase 0

---

## I. MODULE STRUCTURE (VERIFIED)

### Core Modules
- `beliefs/state.py` - 1336 lines - BeliefState class and mutation logic
- `beliefs/ledger.py` - ~250 lines - Event dataclasses and append functions
- `beliefs/updates/` - 887 total lines across 5 modules:
  - `base.py` - 41 lines - Abstract updater interface
  - `noise.py` - 315 lines - Noise gate updater
  - `response.py` - 142 lines - Response belief updater
  - `edge.py` - 138 lines - Edge effect updater
  - `assay_gates.py` - 224 lines - Assay-specific gate updater

**Anchor:** `find beliefs/ -name "*.py" | wc -l` → 9 files (excluding __pycache__)

---

## II. BELIEF MUTATION POINTS (VERIFIED)

### Public Mutation Methods (Called from loop.py)

1. **`begin_cycle(cycle: int)`** - state.py:201
   - Sets `self._cycle = cycle`
   - Resets `self._events = []`
   - **Called from:** loop.py:118

2. **`end_cycle() -> List[EvidenceEvent]`** - state.py:206
   - Returns accumulated `self._events`
   - **Called from:** loop.py:386

3. **`update(observation, cycle: int)`** - state.py:800
   - **Main belief update method**
   - Delegates to 4 updaters: noise, edge, response, assay_gates
   - Returns (events, diagnostics)
   - **Called from:** policy_rules.py:380 (via agent.update_from_observation)

4. **`update_from_instrument_shape(shape_summary, cycle: int)`** - state.py:877
   - Sets `self.instrument_shape`, `instrument_shape_learned`, `calibration_plate_run`
   - **Called from:** loop.py:370

5. **`record_refusal(refusal_reason, debt_bits, debt_threshold)`** - state.py:217-231
   - Sets `epistemic_insolvent = True`
   - Increments `consecutive_refusals`
   - **Called from:** loop.py:238

6. **`record_action_executed(was_calibration: bool)`** - state.py:249-283
   - Resets `consecutive_refusals` if conditions met
   - Clears `epistemic_insolvent` if solvency restored
   - **Called from:** loop.py:449

7. **`update_debt_level(current_debt: float)`** - state.py:285-300
   - Sets `epistemic_debt_bits`
   - Clears insolvency if debt below threshold
   - **Called from:** loop.py:446

### Internal Mutation Methods

- `_emit_gate_event()` - state.py:533-555
- `_emit_gate_loss()` - state.py:557-588
- `_emit_gate_shadow()` - state.py:590-620
- `assert_no_undocumented_mutation()` - state.py:660-680 (validation, not mutation)

### Updater Mutation Methods

Each updater in `beliefs/updates/` has an `update()` method that mutates BeliefState fields:
- **NoiseBeliefUpdater** - noise.py:44
- **EdgeBeliefUpdater** - edge.py:25
- **ResponseBeliefUpdater** - response.py:23
- **AssayGateUpdater** - assay_gates.py:42

**Reality:** Updaters directly mutate BeliefState fields via `self.state.field = value`. No _set() wrapper exists (despite Covenant 7 intent).

---

## III. LEDGER WRITE SITES (VERIFIED)

### Evidence Events (evidence.jsonl)
**Write site:** loop.py:453
**Function:** `append_events_jsonl(self.evidence_file, events)`
**Source:** `events = self.agent.beliefs.end_cycle()` (loop.py:386)

### Decision Events (decisions.jsonl)
**Write sites:**
- loop.py:129 - After propose (normal path)
- loop.py:139 - After propose (ABORT exception path)
- loop.py:156 - Fallback abort Decision creation

**Function:** `append_decisions_jsonl(self.decisions_file, [self.agent.last_decision])`
**Source:** `self.agent.last_decision` (set by policy_rules.py, not beliefs layer)

### Refusal Events (refusals.jsonl)
**Write site:** loop.py:235
**Function:** `append_refusals_jsonl(self.refusals_file, [refusal_event])`
**Created:** loop.py:225-234 (inline RefusalEvent construction in loop.py, not beliefs layer)

### Diagnostics (diagnostics.jsonl)
**Write sites:**
1. loop.py:92 - Contamination warning (plain dict to append_noise_diagnostics_jsonl)
2. loop.py:196-197 - Debt diagnostic (direct JSON write with `open()`)
3. loop.py:455 - Noise diagnostics (typed append_noise_diagnostics_jsonl)

**Reality:** Mixed schemas, mixed write methods (typed append vs direct write)

---

## IV. EVENT SCHEMAS (CURRENT STATE)

### EvidenceEvent - ledger.py:40-67
```python
@dataclass(frozen=True)
class EvidenceEvent:
    cycle: int
    belief: str
    prev: Any
    new: Any
    evidence: Dict[str, Any]
    supporting_conditions: List[str]
    note: Optional[str] = None
    evidence_time_h: Optional[float] = None
    claim_time_h: Optional[float] = None
```
**Serialization:** `to_dict()` → `asdict()` (no event_type or schema_version injection)
**Temporal enforcement:** ledger.py:117-130 raises TemporalProvenanceError if evidence_time_h is None for non-gate, non-exempt beliefs

### DecisionEvent - ledger.py:136-151
```python
@dataclass(frozen=True)
class DecisionEvent:
    cycle: int
    candidates: List[Dict[str, Any]]
    selected: str
    selected_score: float
    selected_candidate: Dict[str, Any]
    reason: str
```
**Serialization:** `to_dict()` → `asdict()` (no envelope)
**Note:** This is OLD schema. loop.py actually uses core/decision.py::Decision, not this DecisionEvent!

### RefusalEvent - ledger.py:162-201
```python
@dataclass(frozen=True)
class RefusalEvent:
    cycle: int
    timestamp: str  # NAIVE (no timezone) - loop.py:227 uses datetime.now().isoformat()
    refusal_reason: str
    proposed_template: str
    proposed_hypothesis: str
    proposed_wells: int
    debt_bits: float
    base_cost_wells: int
    inflated_cost_wells: float
    budget_remaining: int
    debt_threshold: float
    blocked_by_cost: bool
    blocked_by_threshold: bool
    design_id: Optional[str] = None
```
**Serialization:** `to_dict()` → `asdict()` (no envelope)
**Timestamp:** NAIVE datetime (no UTC)

### NoiseDiagnosticEvent - ledger.py:212-237
```python
@dataclass(frozen=True)
class NoiseDiagnosticEvent:
    cycle: int
    condition_key: str
    n_wells: int
    std_cycle: float
    mean_cycle: float
    pooled_df: int
    pooled_sigma: float
    ci_low: Optional[float]
    ci_high: Optional[float]
    rel_width: Optional[float]
    drift_metric: Optional[float]
    noise_sigma_stable: bool
    enter_threshold: float
    exit_threshold: float
    df_min: int
    drift_threshold: float
```
**Serialization:** `to_dict()` → `asdict()` (no envelope)

### Reality Check: No Schema Versioning
**Verified:** `rg -n "schema|version" beliefs/ledger.py` → NO MATCHES
**Consequence:** No `event_type` or `schema_version` fields in any serialized event

---

## V. TEMPORAL PROVENANCE (CURRENT ENFORCEMENT)

### Enforced Invariants

1. **Evidence time requirement** - ledger.py:117-130
   - For non-gate beliefs: `evidence_time_h` must not be None
   - Exemptions: gate events (gate_event:*, gate_loss:*, gate_shadow:*), epistemic_insolvent
   - Enforcement: Raises TemporalProvenanceError at write time

2. **Temporal admissibility** - ledger.py:47
   - Documented rule: `evidence_time_h >= claim_time_h`
   - **Reality:** NOT ENFORCED (only documented in docstring)

### Existing Tests (VERIFIED)
- tests/unit/test_temporal_causality_e2e.py
- tests/unit/test_temporal_causality_enforcement.py
- tests/unit/test_observation_provenance.py
- tests/unit/test_decision_provenance.py
- tests/phase6a/test_temporal_coherence.py
- tests/phase6a/test_temporal_provenance_enforcement.py
- tests/phase6a/test_temporal_retroactive_inference_blocks.py
- tests/phase6a/test_temporal_scrna_integration.py

---

## VI. RNG USAGE IN BELIEFS (VERIFIED)

### Direct RNG Usage: NONE
**Command:** `rg -n "random|np\.random|Random" beliefs/state.py` → NO MATCHES
**Conclusion:** BeliefState does NOT use random number generation

### Datetime Usage: LOCAL TIME (NAIVE)
**Locations:**
- state.py:550 - `datetime.now().isoformat(timespec="seconds")` in gate event evidence
- state.py:583 - `datetime.now().isoformat(timespec="seconds")` in gate loss evidence
- state.py:615 - `datetime.now().isoformat(timespec="seconds")` in gate shadow evidence

**Import:** `from datetime import datetime` (inline imports, lines 520, 572, 603)
**Reality:** NAIVE timestamps (no timezone), used only in evidence dict payloads, not in top-level timestamp fields

---

## VII. FILESYSTEM WRITES IN BELIEFS (VERIFIED)

### Direct Writes: NONE
**Verified:** Beliefs layer does NOT directly write to files
**Write delegation:** All JSONL writes happen in loop.py via ledger.py append functions

### Belief Output Flow:
1. BeliefState accumulates events in `self._events` (in-memory list)
2. `end_cycle()` returns events to loop.py
3. loop.py calls `append_events_jsonl()` to write

---

## VIII. UGLY REALITIES (NO SUGAR-COATING)

### 1. Mixed Diagnostics Schema
- Contamination event: plain dict passed to typed function (duck typing)
- Debt diagnostic: direct JSON write bypassing typed functions
- Noise diagnostics: typed NoiseDiagnosticEvent
- **No uniform envelope** (event_type, schema_version, timestamp)

### 2. Naive Timestamps
- RefusalEvent.timestamp: loop.py:227 uses `datetime.now().isoformat()` without timezone
- Evidence dict "emitted_at": state.py:550, :583, :615 - same issue
- **No UTC enforcement**

### 3. Schema Evolution Risk
- No schema_version field anywhere
- No event_type field in serialized JSON (only internal to evidence dict payloads)
- Downstream parsers must rely on filename or guesswork

### 4. DecisionEvent Not Used
- ledger.py:136 defines DecisionEvent but loop.py uses core/decision.py::Decision instead
- **Dead code in ledger.py**

### 5. Updater Direct Mutation
- Despite Covenant 7 ("no undocumented mutation"), updaters directly mutate fields
- assert_no_undocumented_mutation exists but only catches mutations OUTSIDE update() path
- **No _set() wrapper actually enforced**

### 6. Type Mismatch at loop.py:92
- append_noise_diagnostics_jsonl expects List[NoiseDiagnosticEvent]
- loop.py:92 passes `[contamination_event]` where contamination_event is plain dict
- **Works via duck typing, would fail static type check**

---

## IX. BELIEF DETERMINISM (CURRENT STATE)

### Deterministic Inputs
- update() receives Observation (deterministic if simulator is)
- No RNG usage in beliefs layer
- **Expected:** Given same Observation, beliefs should be deterministic

### Non-Deterministic Elements
- Timestamps: `datetime.now()` used in evidence dict "emitted_at" fields (state.py:550, :583, :615)
- **Impact:** Evidence dict payloads contain wallclock time, but NOT used in belief logic (only for logging)

### Determinism Status
- **Belief state updates:** DETERMINISTIC (no RNG, pure functions)
- **Evidence events:** SEMI-DETERMINISTIC (same updates, different timestamps in evidence dict)
- **No existing test:** No test verifies belief determinism given same inputs

---

## X. PROVENANCE INVARIANTS (WHAT'S ENFORCED TODAY)

### Enforced at Write Time
1. Evidence events have evidence_time_h (ledger.py:121) - raises TemporalProvenanceError
2. JSON serialization succeeds (implicit - would crash if unserializable)

### NOT Enforced
1. Causal ordering: evidence_time_h >= claim_time_h (documented at ledger.py:47, not checked)
2. Decision causality: "at least one Decision per cycle" (no check)
3. Execution → Evidence link: "if experiment ran, Evidence exists" (no check)
4. Refusal → RefusalEvent link: "if refused, RefusalEvent written" (happens in practice but not enforced)
5. Supporting conditions non-empty (allowed to be empty list)

### Mutation Tracking
- assert_no_undocumented_mutation (state.py:660) enforces Covenant 7
- **Reality:** Only catches mutations OUTSIDE update() cycle, not within updaters
- **Gap:** Updaters can mutate fields directly without evidence events (by design)

---

## XI. DEPENDENCIES (BELIEFS → OTHER MODULES)

### Imports (from beliefs/state.py)
- `from .ledger import EvidenceEvent, cond_key`
- `from ..exceptions import BeliefLedgerInvariantError, ExecutionIntegrityState, IntegrityViolation`
- `from datetime import datetime` (inline, not top-level)
- Standard library: `typing`, `dataclasses`, `math`, `numpy`

### Called By
- loop.py (7 call sites for belief methods)
- policy_rules.py (calls beliefs.update via agent.update_from_observation)

### Calls
- Updaters (noise, edge, response, assay_gates) via delegation in update()
- No RNG
- No file I/O
- No external APIs

---

## XII. NEXT STEPS (PHASE 1+)

Based on this survey, Phase 1-5 will address:

1. **Schema standardization:** Add event_type and schema_version to all events
2. **Diagnostics hardening:** Centralize mixed writes via diagnostic_writer.py
3. **Timestamp normalization:** Use UTC everywhere
4. **Provenance tests:** Lock existing good behavior, catch regressions
5. **Determinism tests:** Verify belief updates are deterministic
6. **Documentation:** STATE_MAP.md, MEASUREMENT_PURITY.md, ASSUMPTIONS_LEDGER.md

---

**END OF PHASE 0 SURVEY**
