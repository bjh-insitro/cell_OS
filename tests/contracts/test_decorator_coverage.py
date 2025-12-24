"""
Test: All assay measure() methods must be decorated with @enforce_measurement_contract.

This prevents accidental bypass when new assays are added.
"""

import pytest
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.assays.cell_painting import CellPaintingAssay
from src.cell_os.hardware.assays.viability import LDHViabilityAssay
from src.cell_os.hardware.assays.scrna_seq import ScRNASeqAssay


def test_all_assay_measure_methods_are_decorated():
    """
    Every assay's measure() method must have the contract decorator.

    This prevents silent cheating when new assays are added.
    """
    # Create VM to get assay instances
    vm = BiologicalVirtualMachine()

    assays_to_check = [
        (vm._cell_painting_assay, "CellPaintingAssay"),
        (vm._ldh_viability_assay, "LDHViabilityAssay"),
        (vm._scrna_seq_assay, "ScRNASeqAssay"),
    ]

    for assay_instance, assay_name in assays_to_check:
        # Check that measure() method exists
        assert hasattr(assay_instance, 'measure'), (
            f"{assay_name} must have a measure() method"
        )

        measure_method = getattr(assay_instance, 'measure')

        # For bound methods, we need to access __func__ to get the actual function
        if hasattr(measure_method, '__func__'):
            func = measure_method.__func__
        else:
            func = measure_method

        # Check that the function is decorated by inspecting its closure
        # The enforce_measurement_contract decorator creates a wrapper with a closure
        # containing the contract and other variables
        if hasattr(func, '__closure__') and func.__closure__:
            # Decorated function should have closure variables (contract, vessel_arg_index, etc.)
            closure_vars = [
                cell.cell_contents for cell in func.__closure__
                if hasattr(cell, 'cell_contents')
            ]

            # Look for MeasurementContract in closure
            from src.cell_os.contracts.causal_contract import MeasurementContract
            has_contract = any(isinstance(var, MeasurementContract) for var in closure_vars)

            assert has_contract, (
                f"{assay_name}.measure() must be decorated with @enforce_measurement_contract.\n"
                f"Found closure vars: {[type(v).__name__ for v in closure_vars]}\n"
                f"Add the decorator to {assay_name}.measure() in the assay file."
            )
        else:
            pytest.fail(
                f"{assay_name}.measure() does not appear to be decorated.\n"
                f"The method has no closure, which means @enforce_measurement_contract is missing.\n"
                f"Add the decorator to {assay_name}.measure() in the assay file."
            )


def test_vm_assay_entrypoints_exist():
    """
    VM must expose all assay entrypoints.

    This is a sanity check that assays are properly wired.
    """
    vm = BiologicalVirtualMachine()

    # Check VM methods exist
    assert hasattr(vm, 'cell_painting_assay'), "VM must have cell_painting_assay() method"
    assert hasattr(vm, 'atp_viability_assay'), "VM must have atp_viability_assay() method"
    assert hasattr(vm, 'scrna_seq_assay'), "VM must have scrna_seq_assay() method"

    # Check assay instances exist
    assert hasattr(vm, '_cell_painting_assay'), "VM must have _cell_painting_assay instance"
    assert hasattr(vm, '_ldh_viability_assay'), "VM must have _ldh_viability_assay instance"
    assert hasattr(vm, '_scrna_seq_assay'), "VM must have _scrna_seq_assay instance"


def test_assay_classes_are_correct_types():
    """
    Assay instances must be of the correct type.

    Prevents accidental mock or stub classes in production.
    """
    vm = BiologicalVirtualMachine()

    assert isinstance(vm._cell_painting_assay, CellPaintingAssay), (
        "vm._cell_painting_assay must be a CellPaintingAssay instance"
    )
    assert isinstance(vm._ldh_viability_assay, LDHViabilityAssay), (
        "vm._ldh_viability_assay must be a LDHViabilityAssay instance"
    )
    assert isinstance(vm._scrna_seq_assay, ScRNASeqAssay), (
        "vm._scrna_seq_assay must be a ScRNASeqAssay instance"
    )
