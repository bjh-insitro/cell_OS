import pytest

from cell_os.workflows import WorkflowBuilder, Workflow, Process
from cell_os.unit_ops import ParametricOps, UnitOp
from cell_os.unit_ops.base import VesselLibrary
from cell_os.inventory import Inventory


@pytest.fixture
def workflow_builder() -> WorkflowBuilder:
    """
    Minimal, realistic WorkflowBuilder wired to the real ParametricOps,
    vessel library and pricing inventory.
    """
    vessels = VesselLibrary()
    inv = Inventory("data/raw/pricing.yaml")
    ops = ParametricOps(vessels, inv)
    return WorkflowBuilder(ops)


def test_build_master_cell_bank_basic(workflow_builder: WorkflowBuilder):
    """MCB workflow should be a single process with the 4 expected ops."""
    wf = workflow_builder.build_master_cell_bank(flask_size="flask_t75", cell_line="iPSC")

    assert isinstance(wf, Workflow)
    assert wf.name == "Master Cell Bank (MCB) Production"
    assert len(wf.processes) == 1

    proc = wf.processes[0]
    assert isinstance(proc, Process)
    assert proc.name == "Cell Banking & Expansion"

    # For now we only assert the shape, not exact names
    assert len(proc.ops) == 4
    for op in proc.ops:
        assert isinstance(op, UnitOp)


def test_build_viral_titer_basic(workflow_builder: WorkflowBuilder):
    """Viral titer workflow should be a single process with 3 ops."""
    wf = workflow_builder.build_viral_titer()

    assert isinstance(wf, Workflow)
    assert wf.name == "Viral Titer Measurement"
    assert len(wf.processes) == 1

    proc = wf.processes[0]
    assert isinstance(proc, Process)
    assert len(proc.ops) == 3
    for op in proc.ops:
        assert isinstance(op, UnitOp)


def test_build_zombie_posh_structure(workflow_builder: WorkflowBuilder):
    """
    Zombie POSH should produce a multi-process workflow with non-empty ops.
    We keep assertions loose so refactors do not break this every five minutes.
    """
    wf = workflow_builder.build_zombie_posh()

    assert isinstance(wf, Workflow)
    assert "POSH" in wf.name

    # We expect multiple processes (Library, Cell prep, Screening, Analysis)
    assert len(wf.processes) >= 3

    # Every process should have at least one op
    for proc in wf.processes:
        assert isinstance(proc, Process)
        assert len(proc.ops) > 0
        for op in proc.ops:
            assert isinstance(op, UnitOp)