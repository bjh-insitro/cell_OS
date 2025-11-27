import unittest
import os


class TestWorkflowIntegration(unittest.TestCase):
    """
    Integration tests that actually execute workflow building.
    """

    def test_build_zombie_posh_workflow(self):
        """Test that we can build the Zombie POSH workflow without errors."""
        from cell_os.unit_ops import ParametricOps, VesselLibrary
        from cell_os.inventory import Inventory
        from cell_os.workflows import WorkflowBuilder
        
        vessel_path = "data/raw/vessels.yaml"
        pricing_path = "data/raw/pricing.yaml"
        
        if not os.path.exists(vessel_path) or not os.path.exists(pricing_path):
            self.skipTest("Missing config files")
            
        try:
            vessels = VesselLibrary(vessel_path)
            inv = Inventory(pricing_path)
            ops = ParametricOps(vessels, inv)
            builder = WorkflowBuilder(ops)
            
            # This should not raise any errors
            workflow = builder.build_zombie_posh()
            
            # Verify structure
            self.assertIsNotNone(workflow)
            self.assertEqual(workflow.name, "Zombie POSH Screening")
            self.assertGreater(len(workflow.processes), 0)
            self.assertGreater(len(workflow.all_ops), 0)
            
            # Verify all ops have required fields
            for op in workflow.all_ops:
                self.assertIsNotNone(op.uo_id)
                self.assertIsNotNone(op.name)
                self.assertIsNotNone(op.layer)
                self.assertIsNotNone(op.category)
                # These should be integers
                self.assertIsInstance(op.time_score, int)
                self.assertIsInstance(op.cost_score, int)
                self.assertIsInstance(op.automation_fit, int)
                self.assertIsInstance(op.failure_risk, int)
                self.assertIsInstance(op.staff_attention, int)
                
        except Exception as e:
            self.fail(f"Failed to build Zombie POSH workflow: {e}")

if __name__ == '__main__':
    unittest.main()
