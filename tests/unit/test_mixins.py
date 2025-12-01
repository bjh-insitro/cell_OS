import unittest
from unittest.mock import MagicMock, patch
from src.cell_os.unit_ops.parametric import ParametricOps
from src.cell_os.unit_ops.base import VesselLibrary, UnitOp

class TestParametricOpsMixins(unittest.TestCase):
    def setUp(self):
        # Mock dependencies
        self.mock_vessels = MagicMock(spec=VesselLibrary)
        self.mock_inv = MagicMock()
        
        # Mock inventory get_price
        self.mock_inv.get_price.return_value = 1.0
        
        # Mock vessel object
        self.mock_vessel = MagicMock()
        self.mock_vessel.name = "TestVessel"
        self.mock_vessel.working_volume_ml = 10.0
        self.mock_vessel.coating_volume_ml = 2.0
        self.mock_vessels.get.return_value = self.mock_vessel
        
        # Instantiate ParametricOps
        self.ops = ParametricOps(self.mock_vessels, self.mock_inv)

    def test_culture_ops_thaw(self):
        """Test op_thaw from CultureOpsMixin."""
        op = self.ops.op_thaw("flask_t75", cell_line="U2OS")
        self.assertIsInstance(op, UnitOp)
        self.assertTrue(op.uo_id.startswith("Thaw_"))
        # Check if sub-steps are generated
        self.assertTrue(len(op.sub_steps) > 0)

    def test_culture_ops_passage(self):
        """Test op_passage from CultureOpsMixin."""
        op = self.ops.op_passage("flask_t75", ratio=3)
        self.assertIsInstance(op, UnitOp)
        self.assertTrue(op.uo_id.startswith("Passage_"))
        # Check cost calculation (should be > 0)
        self.assertTrue(op.material_cost_usd > 0)

    def test_cloning_ops_transduce(self):
        """Test op_transduce from CloningOpsMixin."""
        op = self.ops.op_transduce("flask_t75", virus_vol_ul=50.0, method="spinoculation")
        self.assertIsInstance(op, UnitOp)
        self.assertIn("spinoculation", op.uo_id)
        # Check if centrifuge step is added for spinoculation
        centrifuge_steps = [s for s in op.sub_steps if "Centrifuge" in s.name or "Centrifuge" in s.uo_id]
        self.assertTrue(len(centrifuge_steps) > 0)

    def test_cloning_ops_transfect(self):
        """Test op_transfect from CloningOpsMixin."""
        op = self.ops.op_transfect("flask_t75", method="pei")
        self.assertIsInstance(op, UnitOp)
        self.assertIn("Transfect", op.uo_id)

    def test_analysis_ops_mycoplasma(self):
        """Test op_mycoplasma_test from AnalysisOpsMixin."""
        op = self.ops.op_mycoplasma_test("sample_1", method="pcr")
        self.assertIsInstance(op, UnitOp)
        self.assertIn("MycoTest", op.uo_id)
        self.assertIn("pcr", op.uo_id)

    def test_analysis_ops_karyotype(self):
        """Test op_karyotype from AnalysisOpsMixin."""
        op = self.ops.op_karyotype("sample_1", method="g_banding")
        self.assertIsInstance(op, UnitOp)
        self.assertIn("Karyotype", op.uo_id)

if __name__ == '__main__':
    unittest.main()
