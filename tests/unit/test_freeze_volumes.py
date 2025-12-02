import pytest

from cell_os.unit_ops import ParametricOps, VesselLibrary
from cell_os.inventory import Inventory


def test_freeze_uses_standard_vial_volume():
    vessel_lib = VesselLibrary("data/raw/vessels.yaml")
    inventory = Inventory()
    ops = ParametricOps(vessel_lib, inventory)

    num_vials = 4
    unit_op = ops.op_freeze(num_vials=num_vials, freezing_media="cryostor_cs10", cell_line="iPSC")

    resuspend_step = next(step for step in unit_op.sub_steps if "Resuspend in" in step.name)
    assert f"{num_vials * 0.35:.2f}mL" in resuspend_step.name

    aspirate_steps = [step for step in unit_op.sub_steps if step.name.startswith("Aspirate 0.35mL for vial")]
    assert len(aspirate_steps) == num_vials
