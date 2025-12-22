# Agent 3: Epistemic Debt Deadlock Analysis

**Date**: 2025-12-21

## Current Behavior Verification

### Issue 1: Calibration IS Inflated by Debt

**Location**: `src/cell_os/epistemic_control.py:508`

```python
def should_refuse_action(...):
    inflated_cost = self.get_inflated_cost(float(base_cost_wells))  # Line 508
    is_calibration = template_name in calibration_templates

    blocked_by_cost = inflated_cost > budget_remaining  # Line 517
```

**Problem**: `get_inflated_cost()` is called BEFORE checking `is_calibration`.

This means:
- Calibration actions are inflated by debt multiplier
- At debt=2.0 bits with sensitivity=0.5, calibration cost is ~2× base
- At debt=4.0 bits, calibration cost is ~3× base
- Recovery becomes progressively harder as debt increases

### Issue 2: Circular Dependency

**Trap cycle**:
1. Agent overclaims → debt increases
2. Debt > 2.0 → non-calibration blocked
3. Agent must calibrate
4. Calibration cost inflated by debt
5. Budget insufficient for inflated calibration
6. Agent stuck forever

### Issue 3: Deadlock is Implicit

**Location**: No explicit deadlock detection exists

Current behavior:
- System emits repeated refusals
- Eventually budget exhausts
- Aborts with `abort_insufficient_assay_gate_budget`
- No classification of "this is deadlock, not budget exhaustion"

### Issue 4: Debt Repayment is Implicit

**Location**: `epistemic_control.py:412-472`

Repayment exists but:
- Not obviously monotonic
- No diagnostic when debt decreases
- No clear audit trail of "debt reduced from X to Y because Z"

---

## Root Cause

**Calibration is both the cure and a victim of debt inflation.**

This creates an unstable equilibrium where high debt makes recovery expensive,
which makes recovery harder, which increases debt further.

The budget reserve (MIN_CALIBRATION_COST_WELLS = 12) helps but doesn't solve it:
- Reserve ensures 12 wells are available
- But if calibration costs 12×2 = 24 wells (inflated), reserve fails

---

## Solution Strategy

### Option: Capped Inflation for Calibration (CHOSEN)

**Rationale**:
- Calibration should be mildly painful (cost matters)
- But not progressively impossible
- Cap at 1.5× base cost (50% penalty max)

**Implementation**:
```python
def get_inflated_cost_for_action(base_cost, is_calibration):
    if is_calibration:
        # Capped inflation for recovery path
        multiplier = min(self.get_cost_multiplier(base_cost), 1.5)
    else:
        # Full inflation for exploration
        multiplier = self.get_cost_multiplier(base_cost)
    return base_cost * multiplier
```

**Why not hard exemption?**
- Debt should still hurt (discipline)
- Cap preserves pain without creating trap

**Why not budget reservation?**
- Already have MIN_CALIBRATION_COST_WELLS
- Reservation doesn't solve inflation problem

---

## Changes Required

1. **Split inflation logic**: calibration vs exploration
2. **Cap calibration inflation**: max 1.5×
3. **Explicit deadlock detection**: check if calibration affordable
4. **Monotonic repayment**: emit diagnostics on debt decrease
5. **Terminal deadlock event**: clean abort, not loop

---

## Test Strategy

1. **Calibration recovery**: Debt → calibrate → debt decreases
2. **Deadlock detection**: High debt + low budget → explicit deadlock
3. **Inflation asymmetry**: Calibration capped, exploration not

---

## Success Criteria

- ✅ Calibration always affordable (with cap)
- ✅ Overconfidence still hurts (cost increases)
- ✅ Deadlock detected explicitly
- ✅ No silent failure modes
- ✅ Agent can recover from any debt level
