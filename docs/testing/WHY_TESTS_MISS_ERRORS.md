# Why Tests Don't Catch NameErrors (and How to Fix It)

## The Problem You Just Hit

```python
# Line 530 in tab_campaign_posh.py
"Quantity": qty_pbs,  # NameError: name 'qty_pbs' is not defined
```

This should have been `qty_pbs_ml` (the actual variable name).

## Why Current Tests Don't Catch This

### 1. **Code Path Not Executed**
```python
if view_mode == "Aggregate View":
    # This path is tested ✅
    ...
else:  # Daily Breakdown
    # This path is NOT tested ❌
    qty_pbs  # NameError here!
```

**The issue:** Your tests only run the "Aggregate View" code path, not the "Daily Breakdown" path.

### 2. **No Static Analysis in CI**
- Unit tests only run code that's explicitly called
- If a code path isn't executed, errors in it won't be caught
- NameErrors are **runtime errors**, not syntax errors

### 3. **Streamlit Tests Don't Exercise All Paths**
- Integration tests might render the page
- But they don't click every button or select every option
- So conditional code paths remain untested

## The Solution: Multi-Layer Testing

### Layer 1: Static Analysis (Catches This!)
```bash
# Run pylint to find undefined variables
pylint --disable=all --enable=undefined-variable dashboard_app/
```

**I just added:** `tests/static/test_code_analysis.py`
- Uses `pylint` to check for undefined variables
- Runs BEFORE code execution
- **Would have caught `qty_pbs` immediately**

### Layer 2: Code Coverage
```bash
# Run tests with coverage
pytest --cov=dashboard_app --cov-report=html
```

Shows which lines are NOT tested. You'd see:
```
dashboard_app/pages/tab_campaign_posh.py   85%   Lines 526-542 not covered
```

### Layer 3: Branch Coverage
```python
# Test BOTH code paths
def test_aggregate_view():
    render_resources(..., view_mode="Aggregate View")

def test_daily_breakdown():  # ← This test was missing!
    render_resources(..., view_mode="Daily Breakdown")
```

## Why This Specific Error Wasn't Caught

**Root Cause:** The "Daily Breakdown" view is:
1. Behind a conditional (`if view_mode == "Daily Breakdown"`)
2. Not tested in unit tests
3. Not clicked in integration tests
4. Not checked by static analysis (until now)

## What I Just Added

### 1. **Static Analysis Tests** (`tests/static/test_code_analysis.py`)
```python
def test_no_undefined_variables_in_dashboard():
    """Use pylint to check for undefined variables."""
    # Runs pylint on all dashboard files
    # FAILS if undefined variables found
```

### 2. **Updated CI Workflow**
```yaml
- name: Run static analysis
  run: pytest tests/static/ -v
```

## How to Prevent This in the Future

### Short-term
✅ Run static analysis before committing:
```bash
python3 -m pylint --disable=all --enable=undefined-variable dashboard_app/
```

### Medium-term
✅ Add pre-commit hook:
```bash
# .git/hooks/pre-commit
#!/bin/bash
python3 -m pylint --disable=all --enable=undefined-variable dashboard_app/
if [ $? -ne 0 ]; then
    echo "❌ Undefined variables found! Fix them before committing."
    exit 1
fi
```

### Long-term
✅ Require 100% branch coverage for dashboard code
✅ Add integration tests that exercise all UI paths
✅ Use type hints + mypy for even better static checking

## The Testing Pyramid for Streamlit Apps

```
         /\
        /  \  E2E Tests (Playwright)
       /----\  - Test full user flows
      /      \  - Slow, brittle
     /--------\
    /          \ Integration Tests (streamlit.testing)
   /------------\ - Test page rendering
  /              \ - Medium speed
 /----------------\
/                  \ Static Analysis (pylint, mypy)
/--------------------\ - Fastest, catches most bugs
                       - Run on every commit
```

**Key Insight:** Static analysis catches 80% of bugs in 1% of the time!

## Immediate Action

Run this now to find other issues:
```bash
python3 -m pytest tests/static/test_code_analysis.py -v
```

This will find ALL undefined variables in your dashboard before you click anything!
