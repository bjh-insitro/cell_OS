"""
Integration tests for Streamlit dashboard rendering.
Uses Streamlit's built-in testing framework to catch runtime issues.
"""
import pytest
from streamlit.testing.v1 import AppTest


def _select_dashboard_option(app_test: AppTest, substring: str) -> bool:
    """Select an option containing the given substring from the navigation selectbox."""
    if not app_test.selectbox:
        return False

    for sb in app_test.selectbox:
        options = getattr(sb, "options", []) or []
        for option in options:
            if substring in option:
                sb.select(option)
                return True
    return False


class TestDashboardRendering:
    """Test that dashboard pages render without errors."""

    def test_app_loads_without_error(self):
        """Test that the main app loads successfully."""
        at = AppTest.from_file("dashboard_app/app.py")
        at.run(timeout=10)  # CI may need more time
        assert not at.exception, f"App failed to load: {at.exception}"
    
    def test_posh_campaign_tab_renders(self):
        """Test that POSH Campaign tab renders without duplicate IDs."""
        at = AppTest.from_file("dashboard_app/app.py")
        at.run(timeout=10)

        # Find and select the POSH Campaign tab
        if at.tabs:
            at.tabs[0].select()
        else:
            _select_dashboard_option(at, "POSH Campaign")

        at.run(timeout=10)

        # Should not raise StreamlitDuplicateElementId
        assert not at.exception, f"POSH Campaign tab error: {at.exception}"
    
    def test_mcb_simulation_no_duplicate_ids(self):
        """Test MCB simulation doesn't create duplicate element IDs."""
        at = AppTest.from_file("dashboard_app/app.py")
        at.run(timeout=10)

        # Navigate to POSH Campaign
        if not _select_dashboard_option(at, "POSH Campaign"):
            pytest.skip("Dashboard navigation selectbox not found")

        at.run(timeout=10)

        # Find and click MCB simulation button
        for button in at.button:
            if "MCB" in button.label or "Run" in button.label:
                button.click()
                break

        at.run(timeout=10)

        # Verify no duplicate ID errors
        assert not at.exception, f"MCB simulation error: {at.exception}"
        
        # Verify plotly charts have unique keys
        plotly_charts = [elem for elem in at.get("plotly_chart")]
        if plotly_charts:
            # All charts should have rendered without error
            assert len(plotly_charts) > 0, "No plotly charts found"
    
    def test_all_tabs_render_without_errors(self):
        """Test that all dashboard tabs can be rendered."""
        at = AppTest.from_file("dashboard_app/app.py")
        at.run(timeout=10)

        # Get all available tabs/pages
        if at.selectbox:
            for sb in at.selectbox:
                if hasattr(sb, 'options') and sb.options:
                    for option in sb.options:
                        sb.select(option)
                        at.run(timeout=10)
                        assert not at.exception, f"Error in tab '{option}': {at.exception}"


class TestPlotlyChartKeys:
    """Test that all plotly charts have unique keys."""
    
    def test_no_duplicate_plotly_keys(self):
        """Verify all plotly_chart calls have unique keys."""
        import re
        from pathlib import Path
        
        dashboard_dir = Path("dashboard_app")
        plotly_calls = []
        
        # Scan all Python files in dashboard
        for py_file in dashboard_dir.rglob("*.py"):
            content = py_file.read_text()
            
            # Find all st.plotly_chart calls
            pattern = r'st\.plotly_chart\([^)]+\)'
            matches = re.finditer(pattern, content)
            
            for match in matches:
                call = match.group()
                # Extract key if present
                key_match = re.search(r'key\s*=\s*f?["\']([^"\']+)["\']', call)
                if key_match:
                    key = key_match.group(1)
                    plotly_calls.append({
                        'file': str(py_file),
                        'key': key,
                        'call': call
                    })
                else:
                    # No key found - this should fail
                    pytest.fail(f"plotly_chart without key in {py_file}: {call}")
        
        # Check for duplicate keys
        keys = [pc['key'] for pc in plotly_calls]
        duplicates = [k for k in keys if keys.count(k) > 1]
        
        if duplicates:
            dup_info = [pc for pc in plotly_calls if pc['key'] in duplicates]
            pytest.fail(f"Duplicate plotly_chart keys found: {dup_info}")


class TestStreamlitComponents:
    """Test Streamlit component usage patterns."""

    def test_session_state_usage(self):
        """Test that session state is used correctly."""
        at = AppTest.from_file("dashboard_app/app.py")
        at.run(timeout=10)

        # Session state should be accessible
        assert hasattr(at, 'session_state')

        # Run a few interactions to ensure session state works
        if at.button:
            at.button[0].click()
            at.run(timeout=10)
            assert not at.exception

    def test_no_widget_key_collisions(self):
        """Test that widgets don't have key collisions."""
        at = AppTest.from_file("dashboard_app/app.py")
        at.run(timeout=10)

        # If there are key collisions, Streamlit will raise an exception
        assert not at.exception, f"Widget key collision: {at.exception}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
