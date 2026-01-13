# Productive NO_COMMIT: Governance-Driven Action Biasing

**Date:** 2025-12-21
**Status:** ✅ Implemented

## What Was Built

A **governance-driven action biasing system** that converts NO_COMMIT from "keep wandering" into "here's what's blocking you, go fix it."

When the governance contract returns NO_COMMIT, the system now:
1. Identifies **machine-readable blockers** (LOW_POSTERIOR_TOP, HIGH_NUISANCE)
2. Computes **action intent bias** that prioritizes blocker-resolving actions
3. **Applies bias multipliers** to heuristic scores during beam search

This makes NO_COMMIT productive: the agent learns to stop arguing with the contract and start feeding it what it needs.

---

## The Three Pieces

### 1. Blocker Enum (Machine-Readable Reasons)

**Location:** `src/cell_os/epistemic_agent/governance/contract.py:16-24`

```python
class Blocker(str, Enum):
    LOW_POSTERIOR_TOP = "LOW_POSTERIOR_TOP"  # Need more mechanism discrimination
    HIGH_NUISANCE = "HIGH_NUISANCE"  # Need to reduce confounding
    BAD_INPUT = "BAD_INPUT"  # Garbage inputs rejected
```

**Added to `GovernanceDecision`:**
```python
blockers: Set[Blocker]  # Empty if COMMIT/NO_DETECTION
```

**Population logic:**
- If `posterior_top < threshold` → add `LOW_POSTERIOR_TOP`
- If `nuisance_prob > threshold` → add `HIGH_NUISANCE`
- Both can fire simultaneously

### 2. Action Intent Taxonomy

**Location:** `src/cell_os/hardware/beam_search.py:29-64`

```python
class ActionIntent(str, Enum):
    DISCRIMINATE = "DISCRIMINATE"  # Separate mechanisms
    REDUCE_NUISANCE = "REDUCE_NUISANCE"  # Washout, feed, wait
    AMPLIFY_SIGNAL = "AMPLIFY_SIGNAL"  # Increase dose
    OBSERVE = "OBSERVE"  # Just measure
```

**Classification function:** `classify_action_intent(action, has_dosed)`

**Heuristics:**
- Washout → REDUCE_NUISANCE (clear confounders)
- Feed → REDUCE_NUISANCE (refresh medium, reduce contact pressure)
- No dose → OBSERVE (just measure)
- High dose after dosing → AMPLIFY_SIGNAL
- First dose / low dose → DISCRIMINATE

This is **not perfect taxonomy**. It's **consistent taxonomy**. Good enough to bias without being brittle.

### 3. Bias Mapping

**Location:** `src/cell_os/hardware/beam_search.py:67-104`

**Function:** `compute_action_bias(blockers, evidence_strength) -> Dict[ActionIntent, float]`

**Returns:** Weight multipliers (1.0 = neutral, >1.0 = boost, <1.0 = downweight)

**Heuristics:**

#### If `HIGH_NUISANCE` blocker:
- REDUCE_NUISANCE: **3.0x** (strong boost)
- OBSERVE: **1.5x** (moderate boost - observe after cleanup)
- AMPLIFY_SIGNAL: **0.3x** (downweight - don't escalate into noise)
- DISCRIMINATE: **0.5x** (downweight - confounded discrimination is misleading)

#### If `LOW_POSTERIOR_TOP` blocker (and nuisance OK):
- DISCRIMINATE: **2.5x** (strong boost)
- OBSERVE: **2.0x** (boost observation)
- AMPLIFY_SIGNAL: **1.5x** (if evidence < 0.5, might need signal boost)

#### If **both blockers**:
- Prioritize nuisance reduction first (confounded discrimination is useless)

---

## Integration Point

**Location:** `src/cell_os/hardware/beam_search.py:852-918`

### Before action generation:
```python
# GOVERNANCE-DRIVEN BIASING
gov_decision_for_bias = self._apply_governance_contract(node)
action_bias = {}
if gov_decision_for_bias.action == NO_COMMIT:
    action_bias = compute_action_bias(
        gov_decision_for_bias.blockers,
        evidence_strength
    )
```

### During heuristic computation:
```python
heuristic = (
    self.w_mechanism * confidence_bonus +
    self.w_viability * viability_bonus -
    self.w_interventions * ops_penalty
)

# APPLY GOVERNANCE BIAS
if action_bias:
    intent = classify_action_intent(action, has_dosed)
    bias_multiplier = action_bias.get(intent, 1.0)
    heuristic *= bias_multiplier
```

---

## What This Changes

### Before
When NO_COMMIT fires, beam search generates all legal actions and scores them purely by:
- Mechanism confidence margin
- Viability
- Intervention cost

**No awareness of why commit failed.**

### After
When NO_COMMIT fires, beam search:
1. **Identifies the blocker** (LOW_POSTERIOR_TOP, HIGH_NUISANCE, or both)
2. **Biases action selection** to prioritize blocker resolution
3. **Multiplies heuristic scores** by intent-specific weights

**Example:** If HIGH_NUISANCE blocks commit, washout/feed actions get 3x boost, while high-dose escalations get 0.3x penalty.

---

## Design Principles

1. **Bias, not dictatorship**: Multipliers affect ranking, not legality. Bad actions get downweighted, not forbidden.
2. **Intent over recipes**: We tag action *intent*, not hand-craft specific action sequences.
3. **Composable heuristics**: Bias multipliers stack with existing beam search scoring.
4. **Fail gracefully**: No blockers → neutral bias (all 1.0x). System works with or without bias.

---

## Test Coverage

### Blocker Detection (`tests/unit/test_governance_contract.py`)
```
✓ LOW_POSTERIOR_TOP blocker detected
✓ HIGH_NUISANCE blocker detected
✓ Both blockers detected
✓ COMMIT has no blockers
✓ NO_DETECTION has no blockers
✓ BAD_INPUT blocker detected
```

### Action Classification
```
✓ no dose = OBSERVE
✓ washout = REDUCE_NUISANCE
✓ feed = REDUCE_NUISANCE
✓ first dose = DISCRIMINATE
✓ high dose after dosing = AMPLIFY_SIGNAL
```

### Bias Computation
```
✓ HIGH_NUISANCE boosts REDUCE_NUISANCE, downweights AMPLIFY_SIGNAL
✓ LOW_POSTERIOR_TOP boosts DISCRIMINATE
✓ Both blockers prioritize REDUCE_NUISANCE over DISCRIMINATE
✓ No blockers = neutral (all 1.0)
```

---

## Acceptance Criteria (How to Verify)

### Criterion 1: High nuisance → favor cleanup actions
**Setup:** Synthetic scenario where nuisance is artificially high (e.g., contact pressure artifact, confounded batch)

**Expected:** Beam search should select REDUCE_NUISANCE actions (washout, feed) **earlier** than baseline.

**Metric:** Track `washout_count + feed_count` in first 3 timesteps. Should increase vs. neutral bias.

### Criterion 2: Split posterior → favor discriminating actions
**Setup:** Two mechanisms with similar posteriors (~0.45 each), low nuisance

**Expected:** Beam search should favor DISCRIMINATE actions (different dose levels, different timings).

**Metric:** Measure posterior margin improvement over time. Should converge faster.

### Criterion 3: Forensics visibility
**Expected:** Run receipts should show:
- `governance_action = "NO_COMMIT"`
- `governance_reason = "no_commit: evidence strong but..."`
- `blockers = {HIGH_NUISANCE}` or `{LOW_POSTERIOR_TOP}` or both

**Verification:** Check `BeamSearchResult.governance_*` fields after run.

---

## What This Enables

### Before: Silent discipline
- Governance blocks bad decisions
- Agent keeps exploring randomly
- No learning from failures

### After: Productive discipline
- Governance blocks bad decisions **and explains why**
- Agent prioritizes actions that resolve blockers
- NO_COMMIT becomes "here's what you need to do"

---

## The Uncomfortable Truth (from the design spec)

> This is where your system stops being "a search algorithm" and starts being "a policy." You are now making design choices about what kinds of information are worth pursuing. There is no neutral version of this.

The contract is the moral code. The biaser is the tactical brain that serves it.

---

## Future Extensions (Not Required Now)

### 1. Targeted Action Generation
Instead of just biasing existing actions, **generate 2-5 specific actions** that directly target blockers:
- HIGH_NUISANCE → explicit "washout + wait 6h + measure" sequence
- LOW_POSTERIOR_TOP → explicit "differential probe" action

**When to add:** If biasing alone doesn't reduce distance-to-commit fast enough.

### 2. Distance-to-Commit Metric
Track over time:
- `posterior_gap = threshold - posterior_top_prob`
- `nuisance_gap = nuisance_prob - threshold`

**Success criterion:** These gaps should **decrease** after NO_COMMIT if biasing is working.

**Failure mode:** Gaps stay constant or increase → biasing isn't helping, need targeted generation.

### 3. Adaptive Bias Strength
Right now bias multipliers are fixed (3.0x, 2.5x, etc.). Could make them:
- **Stronger** if same blocker persists across multiple timesteps
- **Weaker** if blocker is close to threshold (gentle nudge vs. hard push)

### 4. Logging Bias Decisions
Add forensic logging:
```python
if getattr(self, 'debug_action_bias', False):
    logger.info(
        f"Action bias applied at t={node.t_step}: "
        f"blockers={blockers}, intent={intent}, multiplier={bias_multiplier:.2f}"
    )
```

Helps debug "why did it pick that action?"

---

## Files Modified

```
src/cell_os/epistemic_agent/governance/
  ├── contract.py           # Added Blocker enum, populate blockers in decide_governance
  └── __init__.py           # Export Blocker

src/cell_os/hardware/
  └── beam_search.py        # Added ActionIntent, classify_action_intent, compute_action_bias, apply bias
      - Lines 29-104: Action intent taxonomy + bias computation
      - Lines 852-858: Compute bias from governance decision
      - Lines 913-918: Apply bias multiplier to heuristic
```

---

## The Promise

If someone later disables or weakens the biasing logic, the existing tests still pass (governance contract enforcement is separate). But empirical performance will degrade: runs will take longer to escape NO_COMMIT, distance-to-commit won't improve.

This is **self-documenting discipline**. The code explains what it's trying to do.
