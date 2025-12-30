# Calibration as First-Class Action

**Status**: Design spec (not yet implemented)
**Depends on**: System closure (EpisodeSummary + health_debt) ✓ complete

## Problem

Currently, calibration is just a template choice in the design space. The agent cannot explicitly choose "calibrate now vs press forward" as a policy decision informed by:
- Current health debt
- Expected information value
- Budget constraints
- Gate status

This leads to:
1. **Implicit calibration**: Agent calibrates because template selector happens to pick baseline, not because it decided to calibrate
2. **No cost/benefit analysis**: No explicit reasoning about "spend X wells calibrating to reduce uncertainty by Y bits"
3. **Health debt ignored**: Agent doesn't know to prioritize calibration when health_debt is high

## Solution: Calibration Cycle as First-Class Action

Make calibration an explicit action in the epistemic action space, parallel to REPLICATE and EXPAND.

### Design

#### 1. Extend EpistemicAction Enum

```python
class EpistemicAction(Enum):
    REPLICATE = "replicate"  # Reduce uncertainty by replicating previous proposal
    EXPAND = "expand"        # Advance exploration (normal policy)
    CALIBRATE = "calibrate"  # Run calibration plate to establish baseline
    NONE = "none"            # No epistemic action needed
```

#### 2. Decision Logic in `choose_epistemic_action()`

The agent should choose CALIBRATE when:
- **Health debt pressure is high** (`health_debt > 5.0`)
- **Noise gate not stable** and `df_total < 40`
- **Drift detected** (`noise_drift_metric > threshold`)
- **Calibration uncertainty high** (`calibration_entropy_bits > 6.0`)

Priority order:
1. If `health_debt > 5.0` → CALIBRATE (urgent)
2. Else if `calibration_uncertainty > 8.0` and `budget > 1 plate` → CALIBRATE
3. Else if `calibration_uncertainty > 6.0` → REPLICATE (tighten before expanding)
4. Else → EXPAND (safe to explore)

#### 3. Calibration Proposal Template

**What it runs:**
- 96 wells DMSO (or minimal perturbation control)
- Distributed across edge and center positions
- Replicates for pooled variance estimation
- All standard assays (LDH, Cell Painting, or whatever is enabled)

**What it measures:**
- Noise sigma (pooled variance)
- Edge effects (center vs edge comparison)
- Replicate precision
- Channel coupling
- Spatial autocorrelation (QC check)

**Cycle contract:**
- Consumes one full integer cycle (like mitigation/epistemic actions)
- Updates beliefs with new calibration data
- May earn or restore noise gate
- Decays health debt (large decay for explicit calibration)

#### 4. Reward Function

Calibration reward = `(uncertainty_before - uncertainty_after) / cost_plates`

Same formula as epistemic reward, but:
- Cost is typically 1 plate (96 wells)
- Uncertainty reduction is measured via `calibration_entropy_bits`
- Should be positive if calibration tightens noise estimates

#### 5. Integration with Health Debt

When CALIBRATE action executes:
- Check pre-calibration health_debt
- Run calibration plate
- Measure post-calibration metrics (Moran's I, nuclei CV, etc.)
- If QC improves → large health debt decay (e.g., 50%)
- If QC still poor → maintain debt (calibration didn't fix instrument issue)

### Implementation Plan

#### Phase 1: Action Space Extension
1. Add `CALIBRATE` to `EpistemicAction` enum
2. Add calibration decision logic to `choose_epistemic_action()`
3. Implement `create_calibration_proposal()` method in policy

#### Phase 2: Execution Pathway
4. Add `_execute_calibration_cycle()` method to loop (parallel to mitigation/epistemic)
5. Handle pending calibration action in main loop (same pattern as mitigation)
6. Write calibration events to `{run_id}_calibration.jsonl`

#### Phase 3: Belief Updates
7. Add `update_from_calibration()` method to beliefs
8. Implement gate earning/restoration logic
9. Health debt decay with calibration-specific decay rate

#### Phase 4: Integration Test
10. Test calibration triggers when health_debt high
11. Test calibration reduces `calibration_entropy_bits`
12. Test health debt decays after successful calibration
13. Test episode summary tracks calibration actions

### Example Scenario

**Initial state:**
- Cycle 5, health_debt = 6.2 (high)
- calibration_entropy_bits = 7.8
- Last observation: Moran's I = 0.28 (QC flagged)
- Budget: 200 wells remaining

**Agent decision:**
```
Uncertainty: 7.8 bits
Health debt: 6.2 (HIGH pressure)
Decision: CALIBRATE
Rationale: Health debt requires calibration; instrument quality suspect
```

**Calibration execution (Cycle 6):**
- Proposal: 96 wells DMSO, edge+center positions
- Execution: Run plate, aggregate observations
- Post-calibration:
  - Moran's I = 0.12 (clean)
  - Noise sigma: rel_width = 0.22 (improved from 0.35)
  - Health debt decayed: 6.2 → 3.1 (50% decay)
  - calibration_entropy_bits: 7.8 → 5.2 (2.6 bits gained)

**Reward:**
```
reward = (7.8 - 5.2) / 1.0 = 2.6 bits/plate
```

**Cycle 7:**
- Health debt: 3.1 (medium pressure)
- Calibration uncertainty: 5.2 bits
- Decision: EXPAND (safe to continue science)

### Success Criteria

Calibration should be first-class when:
1. ✓ Agent explicitly chooses to calibrate based on health debt and uncertainty
2. ✓ Calibration consumes a full cycle with structured logging
3. ✓ Health debt decays significantly after successful calibration
4. ✓ Calibration reduces `calibration_entropy_bits`
5. ✓ Episode summary tracks calibration actions in mitigation timeline
6. ✓ Policy can be audited: "Why did you calibrate at cycle 6?"
   - Answer: "Health debt = 6.2 > 5.0 threshold, Moran's I = 0.28, urgent calibration needed"

## Files to Modify

- `src/cell_os/epistemic_agent/epistemic_actions.py`: Add CALIBRATE to enum, implement calibration proposal logic
- `src/cell_os/epistemic_agent/agent/policy_rules.py`: Add `choose_calibration_action()`, integrate with health_debt_pressure
- `src/cell_os/epistemic_agent/loop.py`: Add `_execute_calibration_cycle()`, handle pending_calibration
- `src/cell_os/epistemic_agent/beliefs/state.py`: Add `update_from_calibration()`, health debt decay for calibration
- `tests/integration/test_calibration_action.py`: New integration test

## Open Questions

1. **Should calibration always be 1 plate (96 wells)?**
   - Could vary by budget constraints (e.g., 48 wells if low budget)
   - Recommend: Start with fixed 96 wells for consistency

2. **When to restore a lost gate?**
   - If noise_gate lost due to drift, should one calibration restore it?
   - Recommend: Require K-sequential stable observations (same as earning)

3. **What if calibration makes things worse?**
   - If post-calibration QC is worse than pre-calibration
   - Recommend: Don't decay health debt, add diagnostic flag

4. **Should calibration be forced if epistemic_deadlock imminent?**
   - If debt → refuse action → budget too low for calibration
   - Recommend: Yes, reserve budget for calibration when debt > 1.5 bits

---

**Next step**: Implement Phase 1 (Action Space Extension) and Phase 2 (Execution Pathway).
