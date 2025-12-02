# MCB Crash Test - Integration Test Summary

## Overview

The MCB crash test has been successfully refactored into a reusable library with comprehensive integration tests. All tests pass and the example script maintains identical behavior.

---

## Test Coverage

### Behavior Tests (`test_mcb_crash_test.py`)

#### 1. `test_u2os_mcb_pilot_scale_behaves_sanely`
**What it guarantees**:
- 50 simulation runs complete successfully
- Success rate between 70-100%
- Median vials exactly 30 (target)
- P5 and P95 vials within [0, 30] range
- Duration between 2-7 days (reasonable for 10x expansion)
- Waste metrics are non-negative
- Failures array is properly structured

**Soft bounds** (intentionally flexible):
- Success rate: 70-100% (allows for contamination variability)
- Duration: 2-7 days (biological variability in growth rates)

#### 2. `test_u2os_mcb_without_failures`
**What it guarantees**:
- With failures disabled, 100% success rate
- All runs hit exactly 30 vials
- No contamination events
- Deterministic behavior when failures are off

#### 3. `test_mcb_crash_test_deterministic`
**What it guarantees**:
- Same random seed produces identical results
- Regression testing is stable
- No hidden non-determinism in simulation

#### 4. `test_mcb_crash_test_dataframes`
**What it guarantees**:
- Result DataFrames have all expected columns
- Run results include: run_id, duration_days, final_vials, waste metrics, contamination flags
- Daily metrics include: day, total_cells, flask_count, confluence, viability

---

### Asset Generation Tests (`test_mcb_crash_assets.py`)

#### 1. `test_mcb_crash_generates_dashboard_assets`
**What it guarantees**:
- All 5 required files are generated:
  - mcb_summary.json
  - mcb_run_results.csv
  - mcb_daily_metrics.csv
  - dashboard_manifest.json
  - plots_manifest.json
- Files are created in specified output directory

#### 2. `test_mcb_summary_json_structure`
**What it guarantees**:
- Summary JSON contains all 16 required fields:
  - total_runs, successful_runs, success_rate
  - contaminated_runs, failed_runs
  - vials_p5, vials_p50, vials_p95
  - waste_p50, waste_total, waste_cells_p50
  - waste_vials_eq_p50, waste_fraction_p50
  - duration_p50, failures, violations

#### 3. `test_dashboard_manifest_structure`
**What it guarantees**:
- Manifest has title, description, components
- Components include metric, plot, and table types
- Structure is compatible with Streamlit dashboard

#### 4. `test_plots_manifest_structure`
**What it guarantees**:
- All 3 plots are generated:
  - dist_vials (vial distribution)
  - growth_curves (cell growth trajectories)
  - dist_waste (waste fraction distribution)
- Plots are base64-encoded PNGs (>100 chars each)

#### 5. `test_csv_files_not_empty`
**What it guarantees**:
- CSV files contain header + data rows
- Run results CSV has exactly N+1 lines (header + N runs)
- Daily metrics CSV is not empty

---

## Intentionally Soft Bounds

### Success Rate (70-100%)
**Why flexible**: Contamination is stochastic. With a 1% per-day contamination rate and 4-day median duration, we expect ~4% failure rate, but variance is high with small sample sizes.

**When to tighten**: If we calibrate contamination rates to real data, we could narrow to ±2% of expected rate.

### Duration (2-7 days)
**Why flexible**: Biological variability in:
- Thaw recovery (initial cell count varies)
- Growth rate (doubling time has noise)
- Passage timing (confluence threshold)

**When to tighten**: If we reduce biological noise parameters, we could narrow to 3-5 days.

### Vials P5/P95 (0-30)
**Why flexible**: 
- P5 can be 0 if contamination occurs early
- P95 is capped at 30 (target limit)
- Allows for failure scenarios

**When to tighten**: With failures disabled, we could assert P5=P95=30.

---

## What the Tests Catch

### Regression Protection ✅
- Changes to `BiologicalVirtualMachine` growth model
- Changes to `FailureModeSimulator` contamination logic
- Changes to `ParametricOps` unit operations
- Changes to passage/feed/freeze logic
- Changes to waste calculation

### API Contract ✅
- `MCBTestConfig` parameters respected
- `MCBTestResult` structure maintained
- Dashboard asset format compatibility
- CSV column names and structure

### Edge Cases ✅
- Empty daily metrics (all runs fail immediately)
- Zero contamination (failures disabled)
- Deterministic behavior (fixed seed)

---

## What the Tests Don't Catch

### Biological Realism ❌
Tests don't validate that:
- Doubling time matches real U2OS cells
- Contamination rates match real lab data
- Waste fraction is realistic

**Recommendation**: Add calibration tests against real MCB production data when available.

### Performance Regression ❌
Tests don't enforce runtime limits.

**Recommendation**: Add `@pytest.mark.timeout(30)` to catch performance regressions.

### Visual Quality ❌
Tests check that plots exist and are non-empty, but don't validate visual appearance.

**Recommendation**: Add image comparison tests if plot aesthetics become critical.

---

## Follow-Up Improvements

### Priority 1: Calibration Tests
When real MCB production data becomes available:
```python
def test_contamination_rate_matches_historical_data():
    # Run 1000 simulations
    # Assert contamination rate within ±1% of historical
    pass

def test_duration_matches_historical_data():
    # Assert median duration within ±0.5 days of historical
    pass
```

### Priority 2: Performance Tests
```python
@pytest.mark.timeout(30)
def test_mcb_crash_test_completes_in_reasonable_time():
    # 100 simulations should complete in <30s
    pass
```

### Priority 3: Parameterized Tests
```python
@pytest.mark.parametrize("cell_line,expected_duration", [
    ("U2OS", 4.0),
    ("HEK293T", 3.0),
    ("iPSC", 5.0),
])
def test_mcb_crash_test_cell_line_specific(cell_line, expected_duration):
    # Test different cell lines
    pass
```

### Priority 4: Failure Mode Coverage
```python
def test_all_contamination_types_can_occur():
    # Run many simulations
    # Assert all 4 contamination types appear in failures
    pass
```

---

## CI/CD Integration

### Recommended pytest.ini configuration:
```ini
[pytest]
markers =
    integration: Integration tests (slower, run on PR)
    slow: Very slow tests (run nightly)
    
testpaths = tests/integration tests/unit
```

### Recommended GitHub Actions workflow:
```yaml
- name: Run integration tests
  run: pytest tests/integration/ -v --tb=short
  
- name: Check test coverage
  run: pytest tests/integration/test_mcb_crash*.py --cov=cell_os.mcb_crash
```

---

## Summary

**Test Count**: 9 new integration tests  
**Total Coverage**: 166 integration tests pass  
**Behavior Guaranteed**: Sane results, deterministic execution, complete asset generation  
**Regression Protection**: World model, unit ops, failure logic changes caught  
**API Stability**: Config/result contracts enforced  

**Next Steps**: Add calibration tests when real data available, add performance timeouts, expand to other cell lines.
