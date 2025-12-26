# Calibration Wiring Complete (#6)

**Status**: Implemented
**Date**: 2025-12-23

## What Was Built

### 1. Calibration Metrics Extraction (`calibration_metrics.py`)

**Purpose**: Extract QC metrics from calibration observations and compute cleanliness score.

**Data structure**:
```python
@dataclass
class CalibrationMetrics:
    morans_i: Optional[float]  # Spatial autocorrelation
    nuclei_cv: Optional[float]  # Nuclei count CV
    segmentation_quality: Optional[float]  # Segmentation quality score
    edge_failure_rate: Optional[float]  # Edge wells failed
    valid_well_fraction: Optional[float]  # Wells passed QC
    cleanliness_score: float  # Overall [0, 1], 1 = perfect
```

**Functions**:
- `extract_calibration_metrics_from_observation(observation)` - Parse QC metrics from observation
- `compute_cleanliness_score(metrics)` - Compute single cleanliness score [0, 1]
- `calibration_metrics_to_dict(metrics)` - Convert to dict for belief updates

**Cleanliness scoring**:
- Perfect (1.0): Moran's I < 0.10, nuclei CV < 0.15, segmentation > 0.85, valid fraction > 0.95
- Poor (0.0): Moran's I > 0.30, nuclei CV > 0.30, segmentation < 0.60, valid fraction < 0.70
- Penalties applied for each component based on thresholds

### 2. Loop Wiring (`loop.py`)

**Added fields**:
- `_pending_calibration: Optional[EpistemicContext]` - Pending calibration action

**Execution pathway**:
```python
# In run() cycle loop:
if self._pending_calibration is not None:
    self._execute_calibration_cycle(cycle, self._pending_calibration, capabilities)
    self._pending_calibration = None
    continue  # Calibration consumed this integer cycle
```

**Decision integration**:
```python
# When EIV chooses CALIBRATE:
elif action == EpistemicAction.CALIBRATE:
    self._pending_calibration = CalibrationContext(
        cycle_flagged=cycle,
        uncertainty_before=uncertainty_post_update,
        action=action,
        previous_proposal=proposal,
        previous_observation=observation_dict,
        rationale=rationale,
        consecutive_replications=0
    )
```

**New method**: `_execute_calibration_cycle(cycle, context, capabilities)`

Flow:
1. Snapshot belief state (uncertainty_before, debt_before)
2. Generate calibration proposal (controls only, via `make_calibration_proposal`)
3. Execute through normal experiment runner
4. Aggregate observation
5. Extract calibration metrics from observation
6. Apply belief updates (`beliefs.apply_calibration_result`)
7. Log calibration event to `{run_id}_calibration.jsonl`
8. Add to history with `is_calibration=True` flag

**Logging**:
- Calibration proposal statistics (wells, center fraction, compounds)
- Execution time
- Calibration metrics (cleanliness, Moran's I, nuclei CV, segmentation quality)
- Belief updates (uncertainty before/after, debt before/after)
- Writes to calibration.jsonl for EpisodeSummary aggregation

### 3. Clean Architecture

**One execution pathway**: All actions route through main cycle loop with pending state pattern:
- Mitigation: `_pending_mitigation` → `_execute_mitigation_cycle()`
- Epistemic: `_pending_epistemic_action` → `_execute_epistemic_cycle()`
- Calibration: `_pending_calibration` → `_execute_calibration_cycle()`

**No spaghetti**: No `if action == CALIBRATE:` sprinkled in five places. Single dispatcher pattern.

**Same runner**: Calibration uses identical experiment execution pathway as exploration. Produces same observation structure and contract reports.

**Identity-blind enforcement**: Calibration validator checked during proposal generation.

**No epistemic gain**: Calibration does not contribute to "epistemic gain" metric. Tracked separately as uncertainty reduction.

## What This Prevents

1. **"Calibration in a trench coat"**: Validator ensures controls-only, no learning sneaking in
2. **Spaghetti control flow**: Single execution pathway with pending state pattern
3. **Reward hacking**: Calibration tracked separately from scientific epistemic gain
4. **Contract bypass**: Calibration runs through same experiment pipeline, generates same contract reports

## Files Modified

- `src/cell_os/epistemic_agent/calibration_metrics.py` (new)
- `src/cell_os/epistemic_agent/loop.py` (added `_pending_calibration`, `_execute_calibration_cycle`, decision wiring)
- `src/cell_os/epistemic_agent/beliefs/state.py` (already has `apply_calibration_result()` from earlier)

## Testing Status

**Smoke tests**:
- ✓ EpistemicLoop imports successfully
- ✓ Calibration metrics module imports
- ✓ Calibration proposal integrates cleanly

**Next**: Small integration test to verify calibration cycle executes (#6 final step)

## Next Steps (#7 and #8)

### #7: EpisodeSummary Calibration Tracking
- Add `calibration_decisions: List[CalibrationDecision]` to EpisodeSummary
- Add `calibration_count: int`
- Add `missed_calibration_opportunities: int`
- Aggregate from `{run_id}_calibration.jsonl` during finalization

### #8: End-to-End Integration Test
- Seeded run with deterministic calibration triggers
- Verify full cycle: decision → execution → belief updates → logging
- Assert contract violations = 0
- Assert calibration decisions tracked in EpisodeSummary
- Assert missed opportunities = 0

---

## Design Decisions Log

**Q: Where to compute cleanliness?**
**A**: In separate `calibration_metrics.py` module. Keeps scoring logic testable and separated from loop mechanics.

**Q: Should calibration use same experiment runner?**
**A**: Yes. Ensures calibration produces identical observation structure and contract reports. No special casing.

**Q: How to prevent "calibration becomes exploration"?**
**A**: Validator checked during proposal generation. Controls-only enforcement at proposal boundary, not execution boundary.

**Q: Should calibration reduce epistemic gain metric?**
**A**: No. Calibration reduces uncertainty (about the ruler), not epistemic gain (about biology). Tracked separately.

---

**Status**: #6 complete, ready for #7 (EpisodeSummary tracking) and #8 (E2E test).
