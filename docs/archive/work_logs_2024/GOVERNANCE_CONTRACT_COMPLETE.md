# Governance Contract: Complete and Enforced

**Date:** 2025-12-21
**Status:** ✅ Implemented and enforced

## What Was Built

A **pure governance function** that enforces decision discipline at the choke point, making it impossible to create terminal decisions (COMMIT/NO_DETECTION) without passing the contract.

## The Contract

**Location:** `src/cell_os/epistemic_agent/governance/contract.py`

**Function:** `decide_governance(inputs, thresholds) -> decision`

### Rules (in priority order)

1. **Anti-cowardice**: If evidence is strong (≥0.70), you may NOT claim NO_DETECTION
2. **Anti-hubris**: You may COMMIT only if:
   - Top posterior ≥ 0.80 (strong belief)
   - AND nuisance ≤ 0.35 (low confounding)
3. **Default safe**: Otherwise NO_COMMIT (keep exploring)

### Input Validation

- `nuisance_prob` must be in [0, 1]
- `evidence_strength` must be in [0, 1]
- Invalid inputs → NO_COMMIT with `bad_input` reason

## Integration Point (The Choke Point)

**Location:** `src/cell_os/hardware/beam_search.py:_expand_node()`

**Line 826:** `gov_decision = self._apply_governance_contract(node)`

All terminal node creation goes through:
1. **Line 828**: `if gov_decision.action == COMMIT:` → create COMMIT node
2. **Line 885**: `elif gov_decision.action == NO_DETECTION:` → create NO_DETECTION node
3. **Implicit else**: NO_COMMIT → no terminal node (beam continues exploring)

### Key Change

**Before:**
```python
# Ad-hoc logic scattered across 80+ lines
if cal_conf >= threshold and is_concrete_mechanism:
    # create COMMIT node
if cal_conf >= threshold and is_unknown and not concrete_signal_exists:
    # create NO_DETECTION node
```

**After:**
```python
# Single choke point enforcing contract
gov_decision = self._apply_governance_contract(node)
if gov_decision.action == COMMIT:
    commit_node.commit_target = gov_decision.mechanism  # Contract approves mechanism
```

## Tests

### Unit Tests
**Location:** `tests/unit/test_governance_contract.py`

Three scenarios (deterministic, <1 second):
1. Weak posterior + high nuisance → NO_COMMIT
2. Strong posterior + low nuisance → COMMIT
3. Strong evidence forbids NO_DETECTION → NO_COMMIT

### Integration Test
**Location:** `tests/integration/test_governance_enforcement.py`

**Purpose:** Prove the contract cannot be bypassed

**Strategy:** Monkeypatch `decide_governance` to raise RuntimeError, run beam search, assert RuntimeError is raised.

**If this test fails:** Someone bypassed the choke point (contract not called).

## What This Prevents

### Scenario 1: "Confident nonsense"
- **Before:** System could commit with high calibrated confidence but weak posterior
- **After:** Contract blocks COMMIT if posterior < 0.80 OR nuisance > 0.35

### Scenario 2: "Give up too early"
- **Before:** System could claim NO_DETECTION when evidence clearly exists
- **After:** Contract forbids NO_DETECTION if evidence_strength ≥ 0.70

### Scenario 3: "Abstention loophole"
- **Before:** Could COMMIT to "unknown" (essentially abstaining while claiming to commit)
- **After:** Contract only permits COMMIT to concrete mechanisms with evidence

## Evidence Strength Definition

Currently: `evidence_strength = posterior_top_prob`

**Interpretation:** If top mechanism has high probability, signal exists.

**Future:** Could be:
- `1 - P(NO_EFFECT)` if posterior has a null hypothesis bucket
- `1 - nuisance_prob` (crude proxy)
- Calibrated "signal exists" score

## Design Principles

1. **Boring is good**: No clever heuristics, just rules
2. **Pure function**: No side effects, deterministic, testable
3. **Single choke point**: All decisions flow through one place
4. **Fail closed**: Invalid inputs → NO_COMMIT (safe default)
5. **Enforceable**: Integration test catches bypasses

## Files Modified

```
src/cell_os/epistemic_agent/governance/
  ├── contract.py              # Pure governance function (NEW)
  └── __init__.py              # Clean exports (NEW)

src/cell_os/hardware/
  └── beam_search.py           # Integration at choke point (MODIFIED)
      - Lines 18-24: Import governance
      - Lines 677-713: _apply_governance_contract adapter
      - Lines 823-938: Contract enforcement in _expand_node

tests/unit/
  └── test_governance_contract.py       # Unit tests (NEW)

tests/integration/
  └── test_governance_enforcement.py    # Choke point enforcement test (NEW)
```

## How to Use Elsewhere

If other systems need governance (e.g., epistemic agent, policy chooser):

```python
from src.cell_os.epistemic_agent.governance import decide_governance, GovernanceInputs

decision = decide_governance(GovernanceInputs(
    posterior={"MICROTUBULE": 0.85, "ER_STRESS": 0.10, "MITO": 0.05},
    nuisance_prob=0.25,
    evidence_strength=0.88,
))

if decision.action == GovernanceAction.COMMIT:
    # Allowed to commit to decision.mechanism
elif decision.action == GovernanceAction.NO_DETECTION:
    # Allowed to stop (low evidence)
else:
    # Must stay undecided or continue probing
```

## Next Steps (Optional)

1. **Add governance to epistemic agent** if it makes terminal decisions
2. **Tune thresholds** based on empirical false positive/negative rates
3. **Log governance decisions** for forensics (decision.reason already available)
4. **Add posterior entropy** as additional input if needed

## The Only Thing That Matters

**Before this patch:** Governance was emergent, statistical, negotiable.

**After this patch:** Governance is a contract. You pass the test or you don't ship.

This is the difference between "a clever system" and "a system you can defend."
