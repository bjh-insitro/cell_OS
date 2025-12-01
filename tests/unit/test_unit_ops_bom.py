
import unittest
from unittest.mock import MagicMock
from cell_os.unit_ops.base import UnitOp
from cell_os.inventory import BOMItem
from cell_os.unit_ops.operations.cell_culture import CellCultureOps
from cell_os.unit_ops.operations.harvest_freeze import HarvestFreezeOps
from cell_os.unit_ops.operations.vessel_ops import VesselOps
from cell_os.unit_ops.operations.transfection import TransfectionOps
from cell_os.unit_ops.imaging import ImagingOps
from cell_os.unit_ops.operations.qc_ops import QCOps
from cell_os.unit_ops.liquid_handling import LiquidHandlingOps

class MockInventory:
    def get_price(self, item_id):
        prices = {
            "pipette_10ml": 0.5,
            "pipette_2ml": 0.3,
            "pipette_200ul": 0.1,
            "tip_200ul_lr": 0.05,
            "tube_15ml_conical": 0.4,
            "tube_50ml_conical": 0.6,
            "flask_t75": 5.0,
            "plate_96well_u": 3.0,
            "dmem_10fbs": 0.02, # per mL
            "dpbs": 0.01, # per mL
            "trypsin_edta": 0.05, # per mL
            "dmso_media": 0.1, # per mL
            "cryovial": 1.0,
            "matrigel": 2.0, # per mL
            "vitronectin": 10.0, # per mg? let's say per mL working
            "lentivirus": 10.0, # per uL
            "plasmid_dna": 2.0, # per ug
            "pei": 1.0, # per mL
            "opti_mem": 0.05, # per mL
            "mitotracker": 1.0, # per mL
            "paraformaldehyde": 0.1, # per mL
            "triton_x100": 0.05, # per mL
            "cell_painting_cocktail": 5.0, # per mL
            "pbs": 0.01, # per mL
            "mycoplasma_pcr_kit": 20.0,
            "pcr_plate_96": 2.0,
            "tryptic_soy_broth": 0.01, # per mL
            "culture_bottle": 2.0,
            "agar_plate": 1.0,
            "colcemid": 1.0, # per mL
            "g_banding_kit": 50.0,
            "incubator_usage": 0.5, # per hour
            "centrifuge_usage": 1.0, # per run
            "biosafety_cabinet_usage": 5.0, # per hour
            "water_bath_usage": 0.2, # per run
            "microscope_usage": 10.0, # per hour
            "high_content_imager_usage": 50.0, # per hour
            "liquid_handler_usage": 10.0, # per run
            "pcr_machine_usage": 5.0, # per run
            "plate_reader_usage": 5.0, # per run
        }
        return prices.get(item_id, 0.0)

class TestUnitOpsBOM(unittest.TestCase):
    def setUp(self):
        self.vessel_lib = MagicMock()
        self.vessel_lib.get.return_value.name = "TestVessel"
        self.vessel_lib.get.return_value.working_volume_ml = 10.0
        self.inv = MockInventory()
        self.lh = LiquidHandlingOps(self.vessel_lib, self.inv)
        
        # Initialize ops with mock dependencies
        self.cc_ops = CellCultureOps(self.vessel_lib, self.inv, self.lh)
        self.hf_ops = HarvestFreezeOps(self.vessel_lib, self.inv, self.lh)
        self.v_ops = VesselOps(self.vessel_lib, self.inv, self.lh)
        self.tf_ops = TransfectionOps(self.vessel_lib, self.inv, self.lh)
        self.img_ops = ImagingOps(self.vessel_lib, self.inv) # ImagingOps handles lh internally or doesn't use it same way?
        self.qc_ops = QCOps(self.vessel_lib, self.inv, self.lh)
        self.lh_ops = LiquidHandlingOps(self.vessel_lib, self.inv)

    def test_thaw_bom(self):
        op = self.cc_ops.thaw("flask_t75", "HeLa")
        self.assertTrue(len(op.items) > 0)
        resource_ids = [item.resource_id for item in op.items]
        self.assertIn("flask_T75", resource_ids)  # Note: capital T75 in implementation
        self.assertIn("dmem_high_glucose", resource_ids)  # Default media
        self.assertIn("pipette_10ml", resource_ids)
        self.assertIn("water_bath_usage", resource_ids)
        self.assertGreater(op.material_cost_usd, 0)

    def test_passage_bom(self):
        op = self.cc_ops.passage("flask_t75", ratio=2)  # Use 'ratio' not 'split_ratio'
        self.assertTrue(len(op.items) > 0)
        resource_ids = [item.resource_id for item in op.items]
        self.assertIn("flask_T75", resource_ids)  # New vessels
        # Default dissociation method is "accutase" (line 246 in cell_culture.py)
        self.assertIn("accutase", resource_ids)
        self.assertIn("pbs", resource_ids)
        self.assertIn("pipette_10ml", resource_ids)
        self.assertGreater(op.material_cost_usd, 0)

    def test_harvest_bom(self):
        op = self.hf_ops.harvest("flask_t75")
        self.assertTrue(len(op.items) > 0)
        resource_ids = [item.resource_id for item in op.items]
        self.assertIn("trypsin", resource_ids)  # Default dissociation method
        self.assertIn("tube_15ml_conical", resource_ids)
        # centrifuge_usage only added if lh has op_centrifuge method
        # Since our mock LiquidHandlingOps doesn't have it, we won't assert it
        self.assertGreater(op.material_cost_usd, 0)

    def test_freeze_bom(self):
        op = self.hf_ops.freeze(num_vials=5)  # freeze() signature: num_vials is first positional arg
        self.assertTrue(len(op.items) > 0)
        resource_ids = [item.resource_id for item in op.items]
        self.assertIn("micronic_tube", resource_ids)
        self.assertIn("cryostor_cs10", resource_ids)  # Default freezing media
        self.assertIn("controlled_rate_freezer_usage", resource_ids)
        self.assertEqual(sum(item.quantity for item in op.items if item.resource_id == "micronic_tube"), 5)

    def test_coat_bom(self):
        op = self.v_ops.coat("plate_6well", agents=["matrigel"])
        self.assertTrue(len(op.items) > 0)
        resource_ids = [item.resource_id for item in op.items]
        self.assertIn("matrigel", resource_ids)
        self.assertIn("pipette_10ml", resource_ids)
        self.assertIn("incubator_usage", resource_ids)

    def test_transfect_bom(self):
        op = self.tf_ops.transfect("plate_6well", method="pei")
        self.assertTrue(len(op.items) > 0)
        resource_ids = [item.resource_id for item in op.items]
        self.assertIn("pei", resource_ids)
        self.assertIn("plasmid_dna", resource_ids)
        self.assertIn("opti_mem", resource_ids)
        self.assertIn("pipette_200ul", resource_ids)

    def test_imaging_bom(self):
        op = self.img_ops.op_cell_painting("plate_96well")
        self.assertTrue(len(op.items) > 0)
        resource_ids = [item.resource_id for item in op.items]
        self.assertIn("mitotracker", resource_ids)
        self.assertIn("paraformaldehyde", resource_ids)
        self.assertIn("cell_painting_cocktail", resource_ids)
        self.assertIn("liquid_handler_usage", resource_ids)

    def test_qc_mycoplasma_bom(self):
        op = self.qc_ops.mycoplasma_test("sample_1", method="pcr")
        self.assertTrue(len(op.items) > 0)
        resource_ids = [item.resource_id for item in op.items]
        self.assertIn("mycoplasma_pcr_kit", resource_ids)
        self.assertIn("pcr_plate_96", resource_ids)
        self.assertIn("pcr_machine_usage", resource_ids)

    def test_liquid_handling_dispense_bom(self):
        op = self.lh_ops.op_dispense("plate_96well", 0.1, "media")
        self.assertTrue(len(op.items) > 0)
        resource_ids = [item.resource_id for item in op.items]
        self.assertIn("media", resource_ids)
        self.assertIn("tip_200ul_lr", resource_ids) # Should be small tip for 0.1mL

if __name__ == '__main__':
    unittest.main()
