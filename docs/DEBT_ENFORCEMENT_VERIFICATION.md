# Epistemic Debt Enforcement - Verification and Completion

## Phase 0: Debt Path Trace

### Where Debt is Computed

**Debt State Storage:**
- Class: `EpistemicDebtLedger` in `src/cell_os/epistemic_agent/debt.py:145`
- Field: `total_debt: float` (line 162)
- Claims list: `claims: List[EpistemicClaim]` (line 163)
- Repayments list: `repayments: List[RepaymentEvent]` (line 164)

**Claim Recording:**
- Function: `EpistemicDebtLedger.claim()` in `epistemic_agent/debt.py:167-196`
- Creates `EpistemicClaim` with `claimed_gain_bits`
- Called via `EpistemicController.claim_action()` in `epistemic_agent/control.py:162-195`
- Integration: `EpistemicIntegration.claim_design()` in `controller_integration.py:114-177`

**Gain Realization:**
- Function: `EpistemicDebtLedger.realize()` in `epistemic_agent/debt.py:205-234`
- Computes penalty: `claim.overclaim_penalty` (max(0, claimed - realized))
- Updates: `self.total_debt += penalty` (line 221)
- Called via `EpistemicController.resolve_action()` in `epistemic_agent/control.py:237-293`

**Debt Repayment:**
- Function: `EpistemicDebtLedger.apply_repayment()` in `epistemic_agent/debt.py:244-299`
- Evidence-based: requires `repayment_reason` and `evidence` dict
- Reduces debt: `self.total_debt = max(0.0, self.total_debt - actual_repayment)`

### Where Debt is Consulted

**Enforcement Point:**
- Function: `EpistemicController.should_refuse_action()` in `epistemic_agent/control.py:499-595`
- Hard threshold: `debt > 2.0 bits` blocks non-calibration actions (line 551)
- Cost inflation: applied via `get_inflated_cost()` (lines 537-540)
- Budget reserve: non-calibration must leave ≥12 wells (MIN_CALIBRATION_COST_WELLS)
- Deadlock detection: checks if calibration is affordable when debt high (lines 556-564)

**Loop Integration:**
- File: `src/cell_os/epistemic_agent/loop.py:169-241`
- Calls `should_refuse_action()` BEFORE execution (line 169)
- On refusal:
  - Logs refusal (lines 178-200)
  - Writes `RefusalEvent` to `refusals.jsonl` (lines 202-213)
  - Marks agent as insolvent: `beliefs.record_refusal()` (lines 216-220)
  - Aborts on deadlock (lines 224-235)
  - Continues to next cycle (line 241)

**Agent Response:**
- Function: `TemplateChooser._check_epistemic_insolvency()` in `acquisition/chooser.py:629-690`
- Checks: `beliefs.epistemic_insolvent` (line 637)
- On insolvency: forces `baseline_replicates` template (lines 668-690)
- Bankruptcy after 3 consecutive refusals (lines 642-665)

### Where Debt is Updated During Calibration

**Belief State Integration:**
- Function: `BeliefState.record_refusal()` in `beliefs/state.py:210-246`
- Sets: `epistemic_insolvent = True` (line 228)
- Increments: `consecutive_refusals` (line 230)
- Stores: `last_refusal_reason`, `epistemic_debt_bits` (lines 221-232)

**Repayment on Calibration:**
- Function: `BeliefState.record_gate_earned()` in `beliefs/state.py:247-280`
- Triggers when noise gate earned
- Grants 0.25-1.0 bits repayment depending on noise reduction
- Clears insolvency if debt < 2.0 (lines 297-299)

## Current Enforcement Status

### ✅ ALREADY IMPLEMENTED

1. **Hard Refusal on Debt Threshold**
   - Debt ≥ 2.0 bits → refusal for non-calibration
   - Implemented in `epistemic_agent/control.py:551`
   - Enforced in `loop.py:169-241`

2. **Calibration Always Accessible**
   - Calibration templates exempt from hard threshold
   - Capped inflation (1.5×) for calibration
   - Implemented in `epistemic_agent/control.py:532, 539`

3. **Budget Reserve Enforcement**
   - Non-calibration must leave ≥12 wells for recovery
   - Prevents epistemic bankruptcy
   - Implemented in `epistemic_agent/control.py:545`

4. **Deadlock Detection**
   - Detects when debt requires calibration but calibration unaffordable
   - Terminal abort on deadlock
   - Implemented in `epistemic_agent/control.py:553-564` and `loop.py:224-235`

5. **Agent Learns from Refusals**
   - `beliefs.record_refusal()` sets `epistemic_insolvent = True`
   - Chooser checks `epistemic_insolvent` and forces calibration
   - Implemented in `beliefs/state.py:210-246` and `chooser.py:637-690`

6. **Refusal Logging**
   - `RefusalEvent` written to `refusals.jsonl`
   - Includes debt, cost, budget, and refusal reason
   - Implemented in `loop.py:202-213`

### ⚠️ GAPS IDENTIFIED

1. **Per-Cycle Debt Diagnostics Missing**
   - No structured debt_status diagnostic event
   - Need: `epistemic_debt_status` event with debt_bits, threshold, action_allowed, inflation_factor

2. **Test Coverage Incomplete**
   - Existing tests: `tests/integration/test_epistemic_debt_enforcement_with_teeth.py`
   - Missing: E2E test showing debt accumulation → refusal → recovery cycle
   - Missing: Test verifying repayment actually reduces debt

3. **Repayment Integration Unclear**
   - Repayment logic exists but integration with belief updates may be incomplete
   - Need to verify repayment is called when gate earned

## Conclusion

**The enforcement infrastructure is ALREADY COMPLETE.** The hard refusal model (Model 1) is fully implemented with:
- Hard threshold at 2.0 bits
- Calibration always accessible
- Deadlock prevention
- Agent recovery mechanism

**What's missing is:**
1. Structured diagnostic logging (per-cycle debt status)
2. Comprehensive E2E tests
3. Clear documentation of the enforcement model

This is not a "make it work" task—it's a "verify it works and add observability" task.
