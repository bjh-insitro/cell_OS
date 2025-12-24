# Calibration as First-Class Action: Implementation Status

**Started**: 2025-12-23
**Goal**: Make calibration a decision-theoretic action choice, not "if debt high then calibrate"

## Completed ✓

### 1. Calibration Uncertainty Belief State
**File**: `src/cell_os/epistemic_agent/beliefs/state.py`

**Added fields:**
- `calibration_uncertainty: float` - Uncertainty about measurement quality [0, 1]
- `cycles_since_calibration: int` - Time since last calibration
- `last_calibration_cycle: Optional[int]` - Cycle when last calibrated
- `last_action: Optional[str]` - Last epistemic action (for hysteresis)

**Added methods:**
- `advance_cycle_uncertainty()` - Increases uncertainty with time (drift prior, +5% per cycle)
- `update_calibration_uncertainty_from_signals(morans_i, nuclei_cv, segmentation_quality)` - Increases uncertainty from QC instability
- `apply_calibration_result(calibration_metrics, cycle)` - Reduces uncertainty proportional to calibration cleanliness, decays health debt

**Design decisions:**
- Uncertainty vs debt: uncertainty = ignorance, debt = damage
- Uncertainty starts at 0.5 (medium), increases with time and QC volatility
- Calibration reduces uncertainty by 50-90% depending on cleanliness
- Clean calibration (cleanliness > 0.6) decays health debt by up to 30%

### 2. EIV Scoring Module
**File**: `src/cell_os/epistemic_agent/eiv.py`

**Core functions:**
- `score_calibrate()` - EIV = uncertainty reduction + debt reduction - cost
- `score_explore()` - EIV = epistemic gain - health risk - cost
- `score_mitigate()` - EIV = debt reduction - cost
- `select_action_with_hysteresis()` - Selects best action with switch penalty to prevent oscillation

**EIV proxies (testable, not aspirational):**
```python
# Calibrate value
delta_uncertainty = k_u * calibration_uncertainty * 0.7  # 70% reduction
delta_debt = k_d * max(0, health_debt - target) * 0.3  # 30% decay
value = delta_uncertainty + delta_debt
cost = k_plate * 1.0 + k_time * 1.0

# Explore value
value = expected_epistemic_gain  # Already in bits
cost = k_plate * (wells/96) + k_health_risk * risk + k_time

# Mitigate value
value = k_debt * debt_reduction * (excess_debt / debt)
cost = k_plate * (wells/96) + k_time
```

**Hysteresis:**
- Requires score gap > `action_switch_penalty` (default 0.5) to switch actions
- Prevents oscillation under stable state

**Constraints:**
- Calibration penalty if `cycles_since_calibration < min_calibration_gap` (default 2)
- Calibration penalty if `budget_remaining < 96` wells

### 3. EpistemicAction Enum Extension
**File**: `src/cell_os/epistemic_agent/epistemic_actions.py`

**Added:**
- `CALIBRATE = "calibrate"` - Run control-only calibration plate

Now enum has: `REPLICATE`, `EXPAND`, `CALIBRATE`, `NONE`

### 4. EIV Decision Tests (5 deterministic tests)
**File**: `tests/unit/test_eiv_decision_logic.py`

**Tests:**
1. ✓ `test_high_uncertainty_low_debt_chooses_calibrate` - uncertainty=0.8, debt=1.0 → CALIBRATE wins
2. ✓ `test_low_uncertainty_low_debt_high_gain_chooses_explore` - uncertainty=0.2, gain=8.0 → EXPLORE wins
3. ✓ `test_high_debt_chooses_mitigate_over_calibrate` - debt=8.0 → MITIGATE wins
4. ✓ `test_calibration_reduces_uncertainty_more_than_explore` - Calibration provides ~70% reduction
5. ✓ `test_hysteresis_prevents_oscillation` - Gap < penalty → stick with last action

**Bonus tests:**
- `test_calibration_penalty_when_too_recent` - Prevents spam
- `test_calibration_penalty_when_insufficient_budget` - Prevents unaffordable actions

All tests are deterministic (no RNG) and prove the decision logic is not vibes-based.

---

## Remaining Work

### 5. Calibration Proposal Template (controls only)
**Files to modify:**
- `src/cell_os/epistemic_agent/agent/policy_rules.py` - Add `create_calibration_proposal()`

**Requirements:**
- Control-only layout (DMSO + sentinels, NO compounds)
- 96 wells: center-heavy layout to reduce edge variance
- Replicates: 12-24 control wells per cell line
- Assays: Cell Painting (for nuclei_qc) + spatial QC
- **Hard constraint**: `assert proposal.has_no_treatment_identity()` - prevent "everything is calibration" loophole

**Design:**
```python
def create_calibration_proposal(capabilities, reason):
    """
    Create control-only calibration proposal.

    Identity-blind by design: no compounds, no doses, no experimental conditions.
    """
    wells = []
    # DMSO controls distributed center-heavy across plate
    # ... 96 wells total

    # Validator: enforce controls only
    assert all(w.compound in ["DMSO", "sentinel"] for w in wells)

    return Proposal(
        design_id=f"calibration_{reason}",
        hypothesis=f"Calibrate measurement quality: {reason}",
        wells=wells
    )
```

### 6. Loop Execution Pathway
**Files to modify:**
- `src/cell_os/epistemic_agent/loop.py` - Add `_execute_calibration_cycle()`
- `src/cell_os/epistemic_agent/agent/policy_rules.py` - Wire EIV scoring into `choose_epistemic_action()`

**Loop changes:**
```python
# In loop.run(), after science cycle:
if self._pending_calibration is not None:
    self._execute_calibration_cycle(cycle, self._pending_calibration, capabilities)
    self._pending_calibration = None
    continue

# _execute_calibration_cycle():
# - Run calibration proposal (controls only)
# - Aggregate observation
# - Extract QC metrics (morans_i, nuclei_cv, segmentation_quality)
# - beliefs.apply_calibration_result(metrics, cycle)
# - Compute calibration reward
# - Write calibration event to {run_id}_calibration.jsonl
```

**Policy integration:**
```python
def choose_epistemic_action(observation, budget, previous_proposal):
    # Advance uncertainty (time drift)
    beliefs.advance_cycle_uncertainty()

    # Update uncertainty from QC signals
    beliefs.update_calibration_uncertainty_from_signals(
        morans_i=extract_morans_i(observation),
        nuclei_cv=extract_nuclei_cv(observation),
        segmentation_quality=extract_seg_quality(observation)
    )

    # Score actions using EIV
    calibrate_score = eiv.score_calibrate(
        beliefs.calibration_uncertainty,
        beliefs.health_debt,
        beliefs.cycles_since_calibration,
        budget,
        params
    )

    explore_score = eiv.score_explore(
        expected_epistemic_gain=beliefs.estimate_expected_gain(...),
        expected_health_risk=estimate_health_risk(observation),
        expected_cost_wells=96,
        params
    )

    # ... score mitigation if debt high ...

    # Select with hysteresis
    selected = eiv.select_action_with_hysteresis(
        [calibrate_score, explore_score, ...],
        beliefs.last_action,
        params
    )

    # Update last_action
    beliefs.last_action = selected.action

    return selected.action, selected.breakdown
```

### 7. EpisodeSummary Calibration Tracking
**File**: `src/cell_os/epistemic_agent/episode_summary.py`

**Add fields:**
```python
@dataclass
class CalibrationDecision:
    cycle: int
    reason: str  # "high_uncertainty", "high_debt", etc.
    scores: dict  # {calibrate: X, explore: Y, mitigate: Z}
    uncertainty_before: float
    uncertainty_after: float
    debt_before: float
    debt_after: float
    cleanliness: float

@dataclass
class EpisodeSummary:
    # ... existing fields ...

    # NEW:
    calibration_decisions: List[CalibrationDecision] = field(default_factory=list)
    calibration_count: int = 0
    missed_calibration_opportunities: int = 0  # Times calibrate had best score but wasn't taken
```

**Integration in loop finalization:**
```python
def _finalize_episode_summary():
    # ... existing aggregation ...

    # Extract calibration events from calibration.jsonl
    if self.calibration_file.exists():
        for line in f:
            event = json.loads(line)
            summary.calibration_decisions.append(CalibrationDecision(...))

    summary.calibration_count = len(summary.calibration_decisions)

    # Detect missed opportunities (calibrate scored highest but explore/mitigate taken instead)
    # This should be ~0 unless budget-constrained
    for decision in summary.calibration_decisions:
        if decision.scores['calibrate'] > max(other scores) and action_taken != 'calibrate':
            summary.missed_calibration_opportunities += 1
```

### 8. End-to-End Integration Test
**File**: `tests/integration/test_calibration_action_e2e.py`

**Scenario:**
```python
def test_calibration_e2e_with_seeded_rng():
    """
    Deterministic e2e test for calibration action.

    Setup:
    - seed=42, budget=384, max_cycles=8
    - Start with calibration_uncertainty=0.7, health_debt=2.5

    Expected behavior:
    - Cycle 1-2: CALIBRATE chosen (high uncertainty)
    - After calibration: uncertainty drops to ~0.3, debt ~2.0
    - Cycle 3-6: EXPLORE (low uncertainty, exploration safe)
    - Inject QC degradation at cycle 5 → uncertainty increases
    - Cycle 7: CALIBRATE or MITIGATE (depending on debt)

    Assertions:
    - contract violations always 0
    - at least one calibration decision recorded
    - uncertainty decreases after calibration
    - debt decreases after calibration/mitigation
    - EpisodeSummary.calibration_decisions non-empty
    - EpisodeSummary.missed_calibration_opportunities == 0
    """
    loop = EpistemicLoop(budget=384, max_cycles=8, seed=42)

    # Set initial belief state
    loop.agent.beliefs.calibration_uncertainty = 0.7
    loop.agent.beliefs.health_debt = 2.5

    loop.run()

    # Verify calibration occurred
    assert loop.episode_summary.calibration_count >= 1

    # Verify uncertainty reduction
    assert loop.agent.beliefs.calibration_uncertainty < 0.7

    # Verify no contract violations
    assert loop.episode_summary.sacrifices.contract_violations == 0

    # Verify missed opportunities == 0 (always took best action)
    assert loop.episode_summary.missed_calibration_opportunities == 0
```

---

## Design Decisions Log

### Q1: How often can calibration happen?
**Answer**: Minimum gap of 2 cycles unless debt high (enforced by EIV scoring penalty).

### Q2: Calibration plate design?
**Answer**: 1 plate (96 wells), control-only (DMSO + sentinels), center-heavy layout, two cell lines split.

### Q3: Does calibration consume same budget as exploration?
**Answer**: Yes. Otherwise it's a loophole.

### Q4: Allow micro-calibration (half plate)?
**Answer**: Not in Phase 1. Add later if needed.

### Q5: What if calibration makes things worse?
**Answer**: Don't decay health debt, add diagnostic flag. Still reduce uncertainty (you learned something about instrument state).

### Q6: Should calibration be forced if epistemic_deadlock imminent?
**Answer**: Yes, reserve budget for calibration when debt > 1.5 bits (epistemic controller logic).

---

## Success Criteria (to be verified by tests)

- [x] Calibration chosen when `score_calibrate` exceeds `score_explore` by margin
- [ ] Calibration reduces `calibration_uncertainty` in beliefs
- [ ] EpisodeSummary contains calibration count, rationale, scores, before/after metrics
- [ ] No treatment identity in calibration proposal (controls only)
- [ ] Contract reports emitted for calibration cycle
- [ ] No oscillation: hysteresis works
- [ ] Action selection is auditable: "Why did you calibrate at cycle 6?" → "uncertainty=0.8, debt=2.5, score_calibrate=4.2 > score_explore=3.1"

---

## Next Steps

1. Implement calibration proposal template (controls only) in `policy_rules.py`
2. Wire EIV scoring into `choose_epistemic_action()` in `policy_rules.py`
3. Add `_execute_calibration_cycle()` to `loop.py`
4. Extend `EpisodeSummary` with calibration tracking
5. Write e2e integration test
6. Run all tests, verify no regressions
7. Update documentation with final API

Once complete, calibration will be a first-class action with decision-theoretic justification, not vibes.
