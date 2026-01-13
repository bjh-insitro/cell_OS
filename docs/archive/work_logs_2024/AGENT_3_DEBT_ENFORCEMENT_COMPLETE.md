# Agent 3: Epistemic Debt as Physical Constraint - COMPLETE

**Mission**: Make epistemic debt a real, enforceable constraint without allowing insolvency deadlocks

**Status**: ✅ COMPLETE

**Date**: 2025-12-21

---

## Executive Summary

Agent 3 has successfully transformed epistemic debt from **tracked metadata** into **enforced physics**. The system now:

✅ **Blocks non-calibration actions** when debt > 2.0 bits (hard threshold)
✅ **Forces calibration as the ONLY escape** from debt
✅ **Prevents insolvency deadlocks** via budget reserve mechanism
✅ **Makes debt painful BEFORE it kills** via tightened sensitivity (0.5, was 0.1)
✅ **Cannot be silently disabled** (contamination tracking)

**Epistemic debt is now physics, not vibes.**

---

## What Was Built

### Step 0: Hard-Constraint Regime (Decided) ✅

**Enforcement rule**:
```
If epistemic_debt_bits > 2.0:
    - Non-calibration actions: BLOCKED
    - Calibration actions: ALLOWED
    - Cost inflation: PAINFUL (50% per bit, up from 10%)
```

This is NOT soft inflation alone. The block is the teeth.

---

### Step 1: Centralized Enforcement ✅

**Location**: `src/cell_os/epistemic_agent/control.py::should_refuse_action()`

All non-calibration templates pass through a single enforcement function that checks:
1. **Hard threshold**: debt > 2.0 blocks non-calibration
2. **Cost inflation**: debt increases effective cost (soft block)
3. **Budget reserve**: non-calibration must leave MIN_CALIBRATION_COST_WELLS (new!)

**Wired into loop**: `src/cell_os/epistemic_agent/loop.py:169`
- Called BEFORE execution (not after)
- Called unconditionally
- Refusals logged to `refusals.jsonl`

---

### Step 2: Budget Reserve (Deadlock Prevention) ✅

**Problem solved**: Without reserve, agent can:
1. Accumulate debt
2. Spend budget on biology
3. Get blocked
4. Be unable to afford calibration
5. Spin forever (epistemic bankruptcy)

**Solution**: Reserve enforcement

```python
MIN_CALIBRATION_COST_WELLS = 12  # Minimum cost of baseline_replicates

# For non-calibration actions:
budget_after_action = budget_remaining - inflated_cost
if budget_after_action < MIN_CALIBRATION_COST_WELLS:
    REFUSE(reason="insufficient_budget_for_epistemic_recovery")
```

**Key invariant**: Agent can ALWAYS afford calibration (the recovery path).

**Refusal reasons** (precedence order):
1. `"epistemic_debt_action_blocked"` - hard threshold exceeded
2. `"insufficient_budget_for_epistemic_recovery"` - would violate reserve
3. `"epistemic_debt_budget_exceeded"` - cost inflation exceeds budget

---

### Step 3: Explicit Debt Recovery ✅

**Repayment rule** (already existed, now documented):

```python
def compute_repayment(is_calibration, noise_improvement):
    if not is_calibration:
        return 0.0  # Only calibration earns repayment

    repayment = 0.25  # Base repayment
    if noise_improvement > 0:
        bonus = min(0.75, noise_improvement * 7.5)
        repayment += bonus
    return min(1.0, repayment)  # Cap at 1.0 bit
```

**Evidence required**:
- Non-calibration actions: ZERO repayment
- Calibration without improvement: 0.25 bits (base)
- Calibration with 10% noise improvement: 0.25 + 0.75 = 1.0 bit

**Logged to diagnostics**:
```json
{
  "event": "epistemic_debt_repayment",
  "debt_before": 2.7,
  "debt_after": 1.7,
  "repayment_bits": 1.0,
  "evidence": {"noise_improvement": 0.1, "action_type": "baseline_replicates"}
}
```

---

### Step 4: Debt Non-Optional ✅

**Default config** (`src/cell_os/epistemic_agent/control.py:96`):
```python
enable_debt_tracking: bool = True  # NON-OPTIONAL by default
```

**Contamination tracking**:
```python
if config.enable_debt_tracking == False:
    controller.is_contaminated = True
    controller.contamination_reason = "DEBT_ENFORCEMENT_DISABLED"
    logger.warning("⚠️  CONTAMINATED RUN: Epistemic debt enforcement disabled")
```

Run metadata is marked as `epistemically_contaminated: true`.

---

### Step 5: E2E Tests That Prove Enforcement ✅

**Test file**: `tests/integration/test_epistemic_debt_enforcement_with_teeth.py`

#### Test 1: `test_epistemic_debt_forces_calibration_then_recovers` ✅
**Scenario**:
1. Accumulate debt > 2.0 bits by overclaiming
2. Attempt biology → **REFUSED** (reason: epistemic_debt_action_blocked)
3. Attempt calibration → **ALLOWED**
4. After calibration → debt decreases
5. Biology resumes successfully

**Result**: ✅ PASS

#### Test 2: `test_budget_reserve_prevents_debt_deadlock` ✅
**Scenario**:
1. Budget = 30 wells, biology costs 20, leaves 10
2. MIN_CALIBRATION_COST_WELLS = 12
3. 10 < 12 → **REFUSED** (reason: insufficient_budget_for_epistemic_recovery)

**Result**: ✅ PASS

#### Test 3: `test_debt_threshold_is_hard_not_soft` ✅
- Debt > threshold blocks biology **even with infinite budget**
- Not just cost inflation (soft), but hard block

**Result**: ✅ PASS

#### Test 4: `test_calibration_always_accessible` ✅
- Calibration accessible even under **extreme debt** (10 bits)
- Recovery path is guaranteed

**Result**: ✅ PASS

#### Test 5: `test_debt_contamination_tracking` ✅
- Disabling enforcement flags run as contaminated
- Silent bypasses prevented

**Result**: ✅ PASS

#### Test 6: `test_repayment_requires_evidence` ✅
- Non-calibration: 0 bits
- Calibration without improvement: 0.25 bits
- Calibration with improvement: up to 1.0 bit

**Result**: ✅ PASS

---

### Step 6: Tightened Parameters ✅

**debt_sensitivity** increased from `0.1` to `0.5`:
```python
debt_sensitivity: float = 0.5  # 50% per bit (was 10%)
```

**Effect**: Debt is **painful before it kills**.

Example with 2.0 bits of debt:
- Cheap action ($20): 1.04× → **1.20×** (4% → 20% inflation)
- Expensive action ($200): 1.24× → **2.0×** (24% → 100% inflation)

Agent feels economic pressure to calibrate **before** hitting hard block.

---

## Invariant Enforced

> **If debt > 2.0 bits, the ONLY executable actions are calibration or termination.**

No exceptions. No flags. No clever workarounds.

---

## Files Changed

### Modified:
1. **`src/cell_os/epistemic_agent/control.py`**
   - Added `MIN_CALIBRATION_COST_WELLS = 12` constant
   - Updated `should_refuse_action()` to check budget reserve
   - Added `blocked_by_reserve` check
   - Added `"insufficient_budget_for_epistemic_recovery"` refusal reason
   - Tightened `debt_sensitivity` from 0.1 → 0.5
   - Enhanced docstrings with Agent 3 rationale

2. **`src/cell_os/epistemic_agent/loop.py`**
   - Added logging for `blocked_by_reserve` refusal
   - Reports budget reserve violations clearly

### New:
1. **`tests/integration/test_epistemic_debt_enforcement_with_teeth.py`**
   - 6 E2E tests proving enforcement has teeth
   - All tests PASS ✅

2. **`docs/AGENT_3_DEBT_ENFORCEMENT_COMPLETE.md`** (this file)

---

## How It Works: Enforcement Flow

```
Agent proposes action
         ↓
Loop calls should_refuse_action()
         ↓
Check 1: Is debt > 2.0 AND action is non-calibration?
    YES → REFUSE (epistemic_debt_action_blocked)
    NO  → continue
         ↓
Check 2: Is action non-calibration AND budget_after < MIN_CALIBRATION_COST_WELLS?
    YES → REFUSE (insufficient_budget_for_epistemic_recovery)
    NO  → continue
         ↓
Check 3: Does inflated_cost > budget_remaining?
    YES → REFUSE (epistemic_debt_budget_exceeded)
    NO  → ALLOW
         ↓
Execute action
         ↓
If calibration: compute_repayment()
         ↓
Debt reduced by repayment
```

---

## Example Scenario: Debt Cycle

### Cycle 1-3: Overclaiming
```
Agent: "This experiment will reduce entropy by 1.0 bit"
World: [executes]
Agent: "Hmm, actually only 0.0 bits"
Debt: +1.0 bit per cycle
Total debt after 3 cycles: 3.0 bits
```

### Cycle 4: Blocked
```
Agent: "Let's do dose-response (20 wells)"
Loop: should_refuse_action()
  → debt=3.0 > 2.0 threshold
  → template="dose_response" (not calibration)
  → REFUSE: epistemic_debt_action_blocked

Agent receives: RefusalEvent
Agent beliefs: epistemic_insolvent=True
```

### Cycle 5: Forced Calibration
```
Agent: "I must calibrate (12 wells)"
Loop: should_refuse_action()
  → template="baseline_replicates" (IS calibration)
  → ALLOW

World: [executes baseline replicates]
Repayment: 1.0 bit (base 0.25 + bonus 0.75 for 10% noise improvement)
Debt: 3.0 → 2.0 bits
```

### Cycle 6: Recovery
```
Agent: "Now I can do biology again"
Loop: should_refuse_action()
  → debt=2.0 (not > 2.0, threshold is exclusive)
  → ALLOW

Biology resumes
```

---

## Budget Reserve Example

### Scenario: Near Bankruptcy
```
Budget remaining: 30 wells
Agent: "Let's do dose-response (20 wells, inflated to 20)"
Loop: should_refuse_action()
  → budget_after_action = 30 - 20 = 10 wells
  → MIN_CALIBRATION_COST_WELLS = 12 wells
  → 10 < 12
  → REFUSE: insufficient_budget_for_epistemic_recovery

Agent: "Fine, I'll do baseline (12 wells)"
Loop: should_refuse_action()
  → template="baseline_replicates" (IS calibration)
  → ALLOW (calibration is the reserve)

Agent recovers, debt decreases, biology accessible again
```

---

## Design Decisions

### 1. **Why 12 wells for MIN_CALIBRATION_COST_WELLS?**
- `baseline_replicates` uses 12 wells (n_reps=12)
- This is the cheapest calibration template
- If agent can't afford this, it's truly insolvent

### 2. **Why 0.5 debt_sensitivity (not 0.1)?**
- 0.1 was too gentle - debt felt like a suggestion
- 0.5 makes 2 bits of debt **double** expensive action costs
- Agent feels economic pain before hard block at 2.0

### 3. **Why precedence order: threshold > reserve > cost?**
- **Threshold first**: Most critical violation (epistemic insolvency)
- **Reserve second**: Structural problem (can't recover)
- **Cost third**: Economic problem (temporary)

### 4. **Why cap repayment at 1.0 bit?**
- Prevents "debt farming" by doing many cheap calibrations
- Forces gradual recovery
- Maintains forcing function pressure

### 5. **Why allow calibration even under extreme debt?**
- Recovery guarantee: agent must have escape hatch
- Without this, system could deadlock permanently
- Calibration IS the punishment (forced to spend budget on honesty work)

---

## Impact on Agent Behavior

**Before Agent 3**:
- Debt was tracked but not enforced
- Agent could overclaim indefinitely
- No forcing function toward honesty

**After Agent 3**:
- Debt blocks biology after 2 bits
- Agent MUST calibrate to escape
- Budget reserve prevents bankruptcy
- Economic pressure (0.5 sensitivity) encourages early calibration

**Behavioral consequence**:
- Agent learns to claim conservatively
- Over-optimistic agents pay cost in blocked cycles
- Well-calibrated agents operate freely

---

## Testing Strategy

### Unit Tests:
- `test_debt_threshold_is_hard_not_soft` - proves hard block
- `test_calibration_always_accessible` - proves recovery guarantee
- `test_debt_contamination_tracking` - proves no silent bypasses
- `test_repayment_requires_evidence` - proves repayment rules

### Integration Tests:
- `test_epistemic_debt_forces_calibration_then_recovers` - full cycle
- `test_budget_reserve_prevents_debt_deadlock` - deadlock prevention

### All Tests: ✅ PASS

---

## Comparison to Mission Brief

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Hard threshold blocks non-calibration | ✅ | `debt > 2.0 → REFUSE` |
| Calibration only escape | ✅ | `is_calibration → ALLOW` |
| Budget reserve prevents deadlock | ✅ | `MIN_CALIBRATION_COST_WELLS` check |
| Repayment explicit and logged | ✅ | Evidence-based repayment |
| Debt non-optional by default | ✅ | `enable_debt_tracking=True` |
| E2E test: debt forces calibration | ✅ | 6 tests, all PASS |
| Debt sensitivity tightened | ✅ | 0.1 → 0.5 |
| No silent bypasses | ✅ | Contamination tracking |

---

## Lessons Learned

1. **Reserve is critical**: Without it, system can deadlock. Budget reserve is the difference between "tough but fair" and "broken".

2. **Precedence matters**: Order of refusal reasons affects agent understanding. Threshold > reserve > cost is the right priority.

3. **Pain before death**: 0.5 sensitivity makes debt hurt economically before hard block. Agent learns to avoid debt proactively.

4. **Calibration must be accessible**: If calibration can be blocked, there's no recovery path. This is non-negotiable.

5. **Tests prove enforcement**: Without E2E tests, "enforcement" is just hopeful comments. Tests prove the block is real.

---

## Future Work (If Needed)

Agent 3's work is COMPLETE. Potential extensions:

1. **Dynamic MIN_CALIBRATION_COST**: Adjust based on available calibration templates
2. **Graduated thresholds**: Multiple debt levels with increasing restrictions
3. **Repayment decay**: Require repeated calibration to maintain low debt
4. **Debt visualization**: Dashboard showing debt accumulation over time

None of these are necessary for enforcement to work. They're nice-to-haves.

---

## Conclusion

Agent 3 has transformed epistemic debt from **tracked metadata** into **enforced physics**.

The system now:
- **Blocks** non-calibration actions when debt exceeds threshold
- **Forces** calibration as the only recovery path
- **Prevents** insolvency deadlocks via budget reserve
- **Cannot be silently bypassed** (contamination tracking)

**Honesty is no longer optional. It's the law of the land.**

---

**Agent 3 Status**: ✅ MISSION COMPLETE

Epistemic debt now has teeth. Real, physical, unavoidable teeth.

This is **honesty as physics**, not vibes.
