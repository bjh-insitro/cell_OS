# Slow and Hanging Tests Report

## Summary
Fixed import errors and cache conflicts. Systematically tested each test directory to identify slow/hanging tests.

## Test Directory Performance

### Fast Directories (< 5s)
- `tests/agent2/` - 10 tests in 0.57s ✅
- `tests/dashboard/` - 19 tests in 1.99s ✅
- `tests/epistemic/` - 19 tests in 0.73s ✅
- `tests/phase0/` - 9 tests in 0.02s ✅

### Moderate Speed (5-20s)
- `tests/simulation/` - 10 tests in 11.36s ⚠️

### Slow Directories (> 30s)
- `tests/static/` - 4 tests (3 passed, 1 skipped) in 56.35s ⚠️ **SLOW**
  - Average ~18s per test

### Large Test Suites With Issues
- `tests/unit/` - 509 tests - **HANGS at ~56%** ❌
  - Produces output then stops progressing
  - Likely has a hanging test around test #285-290
- `tests/integration/` - 256 tests - **HANGS at ~85%** ❌
  - Hangs on test_virtualwell_realism_probes.py
- `tests/phase6a/` - 296 tests across 77 files (many issues, needs systematic testing)

## Confirmed Hanging Tests

### Unit Tests
1. **`tests/unit/` directory contains hanging test(s)** - HANGS at ~56% ❌
   - Approximately at test #285-290 out of 509
   - Needs individual file testing to identify specific culprit
   - 509 tests across multiple files

### Integration Tests
1. **`tests/integration/test_virtualwell_realism_probes.py`** - HANGS ❌
   - Produces no output after 45+ seconds
   - Causes integration test suite to hang at ~85% completion

### Phase6a Tests
1. **`tests/phase6a/test_lognormal_integration.py`** - HANGS ❌
   - Confirmed to hang for 5+ minutes
   - Must be excluded from test runs

### Root Tests Directory
1. **`tests/test_simulation_realism.py`** - HANGS ❌
   - Hangs on first test (test_dmso_control_cv) after 30+ seconds
   - 6 tests total in file

## Tests Requiring Further Investigation

### Phase6a Directory (77 test files, 296 tests total)
- Many files untested due to time constraints
- Known to contain multiple slow/hanging tests based on previous runs
- Requires systematic file-by-file testing

## Recommendations

1. **Immediate Exclusions**: Add these to pytest configuration
   ```
   --ignore=tests/phase6a/test_lognormal_integration.py
   --ignore=tests/integration/test_virtualwell_realism_probes.py
   --ignore=tests/test_simulation_realism.py
   --ignore=tests/unit/  # Contains hanging test around test #285-290
   --ignore=tests/integration/  # Contains hanging test at ~85%
   ```

2. **Install pytest-timeout plugin** for per-test timeouts:
   ```bash
   pip install pytest-timeout
   pytest --timeout=30
   ```

3. **Systematic Testing**: Test each file individually in unit/ and phase6a/ to identify specific problematic tests

4. **Optimize Slow Tests**: Investigate why static tests take ~18s each

## Test Run Strategy

### ✅ Fast Tests Only (70 passed, 1 skipped in 72 seconds):
```bash
pytest tests/agent2 tests/dashboard tests/epistemic tests/phase0 tests/simulation tests/static -v
```

### For investigating hanging tests:
Test individual files from:
- `tests/unit/` - Identify which file hangs at ~56%
- `tests/integration/` - Identify which files hang (besides test_virtualwell_realism_probes.py)
- `tests/phase6a/` - Use identify_slow_tests.sh to test all 77 files

### Not recommended (will hang):
```bash
# DO NOT RUN - will hang:
pytest  # Runs all tests including hanging ones
pytest tests/unit/  # Hangs at 56%
pytest tests/integration/  # Hangs at 85%
```
