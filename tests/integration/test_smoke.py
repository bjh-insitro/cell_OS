import unittest
import os

# Add project root to path

class TestSmoke(unittest.TestCase):
    """
    Smoke tests to ensure critical modules can be imported and basic objects instantiated.
    """

    def test_import_dashboard(self):
        """Test that dashboard.py can be imported (catches missing deps like streamlit, altair)."""
        # We need to mock streamlit because it expects to be run in a specific context
        # or we can just check if imports *inside* dashboard work.
        # Actually, importing dashboard.py runs the script, which is not ideal for a unit test.
        # Better to test the modules it depends on.
        try:
            import streamlit
            import altair
            import graphviz
            import yaml
        except ImportError as e:
            self.fail(f"Failed to import dashboard dependencies: {e}")

    def test_unit_ops_definitions(self):
        """Test that unit_ops.py classes are defined and valid."""
        try:
            from cell_os.unit_ops import UnitOp, VesselLibrary, ParametricOps, AssayRecipe
        except ImportError as e:
            self.fail(f"Failed to import unit_ops classes: {e}")
        except NameError as e:
            self.fail(f"NameError in unit_ops: {e}")

    def test_workflow_renderer(self):
        """Test that workflow_renderer can be imported."""
        try:
            from cell_os.workflow_renderer import render_workflow_graph
        except ImportError as e:
            self.fail(f"Failed to import workflow_renderer: {e}")

    def test_instantiate_parametric_ops(self):
        """Test that we can instantiate ParametricOps (catches logic errors in __init__)."""
        from cell_os.unit_ops import ParametricOps, VesselLibrary
        from cell_os.inventory import Inventory
        
        # We need valid paths for this to work, or we mock them.
        # Using the actual files is a good integration test.
        vessel_path = "data/raw/vessels.yaml"
        pricing_path = "data/raw/pricing.yaml"
        
        if os.path.exists(vessel_path) and os.path.exists(pricing_path):
            try:
                vessels = VesselLibrary(vessel_path)
                inv = Inventory(pricing_path)
                ops = ParametricOps(vessels, inv)
                self.assertIsNotNone(ops)
            except Exception as e:
                self.fail(f"Failed to instantiate ParametricOps: {e}")
        else:
            print("Skipping ParametricOps instantiation test (missing config files)")

if __name__ == '__main__':
    unittest.main()
