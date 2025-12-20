# InjectionManager Covenant (Authoritative Concentration Spine)

**Date**: 2025-12-20
**Status**: ACTIVE COVENANT
**Scope**: All vessel concentrations (compounds + nutrients), evaporation drift, and event-driven operations.

## 0. Purpose

InjectionManager is the *only* authority for well-level concentrations.
Everything else is interpretation, reporting, or scheduling.

If you are about to write concentration state anywhere else, stop. That is how shadow-state starts. Shadow-state is the beginning of lies.

---

## 1. Non-negotiable invariants

### I1. Single writable truth
- The only writable concentration state lives in **InjectionManager**.
- No other object (Vessel, BiologicalVirtual, assays, schedulers) may own "real" concentrations.

### I2. Read-only consumers
- BiologicalVirtual and assays may **read** concentrations.
- They may not mutate concentrations directly.
- Any change to concentrations must occur through **validated events**.

### I3. Event-driven only
- All changes to concentrations happen via `InjectionManager.apply_event(...)` (or equivalent).
- Events are schema validated. Invalid payloads hard fail.

### I4. Deterministic step semantics
- Concentration updates from physics (evaporation) occur in exactly one place: `InjectionManager.step(dt)`.
- Evaporation must not be applied anywhere else.

### I5. Replayability and receipts
- InjectionManager maintains an ordered event log.
- The log is sufficient to replay concentrations deterministically (given initial conditions and dt schedule).
- Receipts are canonical for debugging and audits.

### I6. No resurrection
- After a washout event, compound concentration must not increase unless a later TREAT event occurs.
- Evaporation cannot "bring back" compound that has been removed.

---

## 2. What lives where

### InjectionManager owns
- Canonical well-level concentrations for:
  - compounds (per-compound)
  - nutrients (per-nutrient or coarse nutrient pool)
- Evaporation model and drift application
- Schema validation for all events
- Event application (treat, feed, washout, optional mix/dilute if modeled)
- Event log + receipts + replay utilities

### BiologicalVirtual owns
- Biology state (stress, growth, death, phenotype)
- Hazard models and attrition logic
- Nutrient depletion models (as biology), but **reads nutrient concentration from InjectionManager**
- Anything that claims to be biology, not plumbing

### Scheduler (Injection B) owns
- When events occur
- How conflicting events are ordered
- Never the physics, never the truth

### Assays own
- Readouts, embeddings, noise models, transforms
- Never concentration truth

---

## 3. Allowed event types and strict schemas

InjectionManager accepts only explicit event types with strict payloads.
No "optional" fields that blur semantics.

### Event: SEED_VESSEL
**Purpose**: initialize well state and default concentrations
**Payload**: `initial_nutrients_mM` (dict with glucose, glutamine)

**Schema**:
```python
{
    "event_type": "SEED_VESSEL",
    "time_h": float,
    "vessel_id": str,
    "payload": {
        "initial_nutrients_mM": {
            "glucose": float,
            "glutamine": float
        }
    }
}
```

**Rules**:
- Must not include compound fields
- Establishes baseline nutrients and empty compounds

### Event: TREAT_COMPOUND
**Purpose**: set compound concentration in target wells
**Payload**: `compound` (str), `dose_uM` (float)

**Schema**:
```python
{
    "event_type": "TREAT_COMPOUND",
    "time_h": float,
    "vessel_id": str,
    "payload": {
        "compound": str,
        "dose_uM": float
    }
}
```

**Rules**:
- Must not include nutrient fields
- Sets final concentration (overwrites if compound already present)

### Event: FEED_VESSEL
**Purpose**: change nutrient concentrations in target wells
**Payload**: `nutrients_mM` (dict with glucose, glutamine)

**Schema**:
```python
{
    "event_type": "FEED_VESSEL",
    "time_h": float,
    "vessel_id": str,
    "payload": {
        "nutrients_mM": {
            "glucose": float,
            "glutamine": float
        }
    }
}
```

**Rules**:
- Must not include compound fields
- Resets nutrients (does NOT dilute compounds in v1)
- If volume is modeled in future: FEED may dilute compound, but that must be explicit and centralized in InjectionManager

### Event: WASHOUT_COMPOUND
**Purpose**: remove compound(s) from target wells
**Payload**: `compound` (str or None for all compounds)

**Schema**:
```python
{
    "event_type": "WASHOUT_COMPOUND",
    "time_h": float,
    "vessel_id": str,
    "payload": {
        "compound": str | None  # None = remove all compounds
    }
}
```

**Rules**:
- Sets compound concentration to 0.0 (hard clamp in v1)
- Does NOT mutate nutrients
- Future extensions may add `residual_fraction` policy

---

## 4. Hook points and contracts (8 hooks)

These are the only legal integration points. Anything else is a bug.

### 4.1 seed_vessel
**File**: `biological_virtual.py:1465`
**Must**:
- Initialize InjectionManager state via SEED_VESSEL event
- Establish baseline nutrients and empty compounds
- Mirror InjectionManager → VesselState fields

**Must not**:
- Set `vessel.compounds` or nutrients as truth

**Enforcement**: Test B1 (48h Story), Test B3 (Event Log)

### 4.2 treat_with_compound
**File**: `biological_virtual.py:1822`
**Must**:
- Convert intent into validated TREAT_COMPOUND event
- Apply via `InjectionManager.add_event()`
- Mirror InjectionManager → VesselState.compounds

**Must not**:
- Write concentrations anywhere else

**Enforcement**: Test 1 (Schema), Test B1 (48h Story)

### 4.3 feed_vessel
**File**: `biological_virtual.py:1515`
**Must**:
- Convert intent into validated FEED_VESSEL event
- Apply via `InjectionManager.add_event()`
- Mirror InjectionManager → VesselState nutrients

**Must not**:
- Mutate compound concentrations

**Enforcement**: Test 1 (Schema), Test B1 (48h Story feed semantics)

### 4.4 washout_compound
**File**: `biological_virtual.py:1582`
**Must**:
- Convert intent into validated WASHOUT_COMPOUND event
- Apply via `InjectionManager.add_event()`
- Mirror InjectionManager → VesselState.compounds

**Must not**:
- Implement washout logic in BiologicalVirtual

**Enforcement**: Test B1 (48h Story washout semantics)

### 4.5 _step_vessel
**File**: `biological_virtual.py:1085`
**Must**:
- Call `InjectionManager.step(dt_h, now_h)` exactly once per timestep
- Mirror InjectionManager → VesselState fields after step
- Ensure ordering: evaporation → growth → death proposals → commit death

**Must not**:
- Apply evaporation/drift anywhere else

**Enforcement**: Test 2 (Evaporation Drift), Test B1 (48h Story step wiring)

### 4.6 _apply_compound_attrition
**File**: `biological_virtual.py:1212`
**Must**:
- Read compound concentrations from `InjectionManager.get_all_compounds_uM()`
- Use authoritative concentrations for hazard computation

**Must not**:
- Read from `vessel.compounds` as truth (it's a mirror)

**Enforcement**: Test 2 (Evaporation Drift), Test B2 (Spine Tampering)

### 4.7 _update_nutrient_depletion
**File**: `biological_virtual.py:738`
**Must**:
- Read nutrient concentrations from `InjectionManager.get_nutrient_conc_mM()`
- Write depleted nutrients back via `InjectionManager.set_nutrients_mM()` (internal sync hook)

**Must not**:
- Treat `vessel.media_glucose_mM` as truth

**Enforcement**: Test B1 (48h Story), Test B2 (Spine Tampering)

### 4.8 cell_painting_assay
**File**: `biological_virtual.py:2250`
**Must**:
- Be read-only with respect to concentrations
- Read concentrations via `InjectionManager.get_all_compounds_uM()`

**Must not**:
- Mutate concentrations or apply "convenient corrections"

**Enforcement**: Test B1 (48h Story assay non-mutating)

---

## 5. Resolution policy (ordering inside a timestep)

This is the canonical rule for deterministic behavior.

For each timestep boundary (`advance_time(hours)` call):

1. **Apply scheduled events** (from scheduler or direct calls) in deterministic order:
   - WASHOUT (removes compounds)
   - FEED (resets nutrients)
   - TREAT (sets compounds)

2. **Apply physics once**: `InjectionManager.step(dt_h, now_h)`
   - Evaporation concentrates both compounds and nutrients
   - Edge wells evaporate 3× faster than interior
   - Volume multiplier capped at min_volume_mult (default 0.70)

3. **Apply biology**: Growth → Death proposals → Commit death → Confluence
   - Growth uses current cell counts
   - Death proposals read concentrations from InjectionManager
   - Nutrient depletion reads/syncs with InjectionManager

4. **Produce receipts**: Event log is updated during event application

### Event ordering rule (current implementation)
Events are applied in the order received (FIFO).
If multiple events occur at the same `time_h`, order is call-order dependent.

**Future (Injection B)**: Scheduler will enforce explicit priority/sequence ordering.

### Timestep ordering invariant
```
_step_vessel(hours):
    0. InjectionManager.step(dt_h=hours, now_h=simulated_time)  # Evaporation
    1. _update_vessel_growth(hours)                              # Growth
    2. _propose_hazards()                                        # Death proposals (reads InjectionManager)
    3. _commit_step_death(hours)                                 # Apply combined survival
    4. _manage_confluence()                                      # Cap growth
    5. _update_death_mode()                                      # Label death cause
```

**Enforcement**: Test B1 (48h Story) verifies this ordering produces expected concentrations

---

## 6. Common failure modes (and what to do instead)

### F1. Shadow state (duplicate concentration fields)
**Symptom**: `vessel.compounds` diverges from InjectionManager
**Fix**: Delete or deprecate the shadow field; enforce reads from InjectionManager only
**Guard**: Test B2 (Spine Tampering Ignored)

### F2. Double evaporation
**Symptom**: Drift is too strong, edge effects exaggerated, concentrations explode
**Fix**: Evaporation belongs only in `InjectionManager.step`
**Guard**: Test 2 (Evaporation Drift), Test B1 (48h Story)

### F3. Assay mutation
**Symptom**: Assay changes concentrations "to simulate dye" or "cleanup"
**Fix**: Assays must be pure readouts; any chemical addition must be an explicit event type
**Guard**: Test B1 (48h Story "assay is non-mutating")

### F4. Implicit dilution
**Symptom**: FEED changes compound concentrations silently
**Fix**: If volume is modeled, dilution must be explicit and centralized in InjectionManager. If not modeled (current v1), FEED must not change compounds.
**Guard**: Test B1 (48h Story feed semantics invariant)

### F5. Undocumented washout semantics
**Symptom**: Different call sites assume different "residual" behavior
**Fix**: Washout policy must be explicit in the event payload (current: hard clamp to 0.0)
**Guard**: Test B1 (48h Story washout semantics)

### F6. Hook unwiring during refactor
**Symptom**: After refactor, biology stops reading InjectionManager (reads stale mirrors instead)
**Fix**: All 8 hooks must maintain their contracts (see Section 4)
**Guard**: Test B1 (48h Story), Test B2 (Spine Tampering)

---

## 7. Tests that enforce this covenant

These tests are not "nice to have." They are the locks on the door.

### Test 1: Schema Validation
**File**: `tests/phase6a/test_injection_manager_schema.py`
**Enforces**: I3 (Event-driven only), Section 3 (Strict schemas)
**Catches**: Mismatched payloads, missing fields, schema violations

### Test 2: Evaporation Drift Affects Attrition
**File**: `tests/phase6a/test_evap_drift_affects_attrition.py`
**Enforces**: I1 (Single truth), 4.6 (Biology reads spine)
**Catches**: Biology reading legacy fields, evaporation being decorative

### Test B1: 48-Hour Story (Spine Stays The Spine)
**File**: `tests/phase6a/test_48h_story_spine_invariants.py`
**Enforces**: All 8 hooks (Section 4), Section 5 (Ordering)
**Catches**: Hook unwiring, step ordering bugs, assay mutation, feed/washout semantics violations

### Test B2: Spine Tampering Is Ignored
**File**: `tests/phase6a/test_spine_tampering_ignored.py`
**Enforces**: I1 (Single truth), I2 (Read-only consumers)
**Catches**: Shadow state introduction, biology reading corrupted mirrors

### Test B3: Event Log Receipts
**File**: `tests/phase6a/test_event_log_receipts.py`
**Enforces**: I5 (Replayability), Section 3 (Event schemas)
**Catches**: Event log corruption, non-replayable state, missing receipts

---

If any of these fail, you are not "slightly broken."
You are lying about what happened in the wells.

---

## 8. Current implementation notes

### Evaporation rates
- Interior wells: `base_evap_rate_per_h = 0.0005` (0.05% volume per hour)
- Edge wells: `edge_evap_rate_per_h = 0.0020` (0.2% volume per hour, 4× interior)
- Volume cap: `min_volume_mult = 0.70` (max 30% volume loss)

### Nutrient concentration
- Evaporation concentrates nutrients identically to compounds (physically honest)
- Nutrient depletion (biology) reads from InjectionManager, syncs back via internal hook

### Washout semantics (v1)
- Hard clamp to 0.0 (no residual fraction)
- Future: may add `residual_fraction` policy parameter

### Feed semantics (v1)
- Resets nutrients to specified values
- Does NOT dilute compounds (no volume modeling yet)
- Future (Injection B): explicit volume tracking will enable dilution

### Mirror pattern
- VesselState fields (`compounds`, `media_glucose_mM`, etc.) are **read-only mirrors**
- Updated immediately after InjectionManager mutations
- Exist only for back-compatibility and introspection
- Biology MUST NOT read mirrors as truth (reads InjectionManager directly)

---

## 9. Amendments

This covenant may evolve, but only with:
- Updated enforcement tests that pass
- Explicit notes in integration reports
- Clear statement of what invariant changed and why
- Git commit message that references this covenant

**Amendment process**:
1. Propose change (with rationale)
2. Update covenant doc
3. Update/add enforcement tests
4. Verify all tests pass
5. Document in `INJECTION_A_INTEGRATION_COMPLETE.md` or successor

---

## 10. Final word

InjectionManager is not a "module," it's a constitution.

The spine stays the spine. Biology reads it, never mutates it directly. Event-driven mutations only. Strict schema validation. Complete forensics. Protected by 5 enforcement tests.

If you find yourself wanting to "just quickly set a concentration," you are about to violate the covenant. Stop. Write an event. Validate the schema. Apply through InjectionManager. That's the price of truth.

**Design principle**: If a change would make a test easier to write but a lie easier to tell, reject the change.

**Last Updated**: 2025-12-20
