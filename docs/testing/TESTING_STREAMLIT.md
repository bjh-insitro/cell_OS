# Why Tests Don't Catch Streamlit Issues

## The Problem

You're encountering Streamlit-specific runtime errors (like `StreamlitDuplicateElementId`) that only appear when running the actual dashboard, not during unit testing.

## Root Causes

### 1. **Current Tests Focus on Business Logic, Not UI**
The existing test suite (`tests/unit/`) tests:
- Data models and dataclasses
- Simulation logic
- Workflow builders
- Unit operations

But **NOT**:
- Streamlit rendering
- UI component interactions
- Element ID uniqueness
- Session state management

### 2. **Streamlit Requires a Running App Context**
Streamlit's element ID system only activates when:
- The app is actually running
- Components are rendered in sequence
- Session state is active
- The element registry is tracking IDs

Unit tests run in isolation without this context.

### 3. **No Integration Tests for Dashboard**
The project lacks:
- End-to-end tests that actually run the Streamlit app
- UI integration tests
- Automated browser testing (e.g., Selenium, Playwright)

## Solutions

### Short-term (What I Just Did)
✅ Added unique `key` parameters to all `st.plotly_chart()` calls
✅ Used descriptive keys based on context (e.g., `f"cost_breakdown_{workflow_type}"`)

### Medium-term Recommendations

#### 1. Add Streamlit Integration Tests
```python
# tests/integration/test_dashboard_rendering.py
import pytest
from streamlit.testing.v1 import AppTest

def test_posh_campaign_no_duplicate_ids():
    """Test that POSH campaign page renders without duplicate IDs."""
    at = AppTest.from_file("dashboard_app/app.py")
    at.run()
    
    # Navigate to POSH Campaign tab
    at.selectbox[0].select("POSH Campaign Sim")
    at.run()
    
    # Should not raise StreamlitDuplicateElementId
    assert not at.exception
```

#### 2. Add Pre-commit Checks
```python
# scripts/check_streamlit_keys.py
"""Lint script to ensure all st.plotly_chart calls have unique keys."""
import re
import sys

def check_plotly_keys(filepath):
    with open(filepath) as f:
        content = f.read()
    
    # Find all st.plotly_chart calls
    pattern = r'st\.plotly_chart\([^)]+\)'
    matches = re.findall(pattern, content)
    
    missing_keys = []
    for match in matches:
        if 'key=' not in match:
            missing_keys.append(match)
    
    if missing_keys:
        print(f"❌ Found plotly_chart calls without keys in {filepath}:")
        for m in missing_keys:
            print(f"  - {m}")
        return False
    return True

if __name__ == "__main__":
    files = sys.argv[1:]
    all_pass = all(check_plotly_keys(f) for f in files)
    sys.exit(0 if all_pass else 1)
```

#### 3. Add Browser-based E2E Tests
```python
# tests/e2e/test_dashboard_flows.py
from playwright.sync_api import sync_playwright

def test_mcb_generation_flow():
    """Test complete MCB generation workflow in browser."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("http://localhost:8501")
        
        # Navigate to POSH Campaign
        page.click("text=POSH Campaign Sim")
        
        # Fill in MCB form
        page.fill("input[aria-label='Target Vials']", "30")
        page.click("button:has-text('Run MCB Simulation')")
        
        # Wait for results
        page.wait_for_selector("text=MCB Generated")
        
        # Verify no errors
        assert not page.locator("text=StreamlitDuplicateElementId").is_visible()
        
        browser.close()
```

### Long-term Best Practices

1. **Mandatory Keys Policy**: Require `key` parameter for all stateful Streamlit components
2. **Component Library**: Create reusable dashboard components with built-in key generation
3. **CI/CD Integration**: Run Streamlit tests in GitHub Actions
4. **Visual Regression Testing**: Use tools like Percy or Chromatic to catch UI changes

## Why This Matters

Streamlit issues are **runtime-only** because:
- They depend on the element registry (only exists in running app)
- They're triggered by user interactions
- They involve session state and re-runs
- They require the full Streamlit execution model

**Unit tests can't catch these** because they test isolated functions, not the full app lifecycle.

## Immediate Action Items

- [ ] Add `streamlit.testing.v1` integration tests
- [ ] Create pre-commit hook for key validation
- [ ] Document key naming conventions
- [ ] Add E2E tests for critical workflows
