"""
Tripwire Test Harness

Provides stable API abstraction for tripwire tests to survive refactors.

This is the ONLY module that knows about changing signatures.
Tripwire tests import only from here.
"""

from typing import Tuple, Dict, Any, Optional
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.epistemic_agent.world import ExperimentalWorld
from cell_os.epistemic_agent.schemas import Proposal, WellSpec
from cell_os.core.observation import RawWellResult


def make_vm(seed: int = 0, **kwargs) -> BiologicalVirtualMachine:
    """
    Create BiologicalVirtualMachine with stable defaults.

    Hides changing constructor signatures.
    """
    return BiologicalVirtualMachine(seed=seed, **kwargs)


def seed_vm_vessel(
    vm: BiologicalVirtualMachine,
    vessel_id: str,
    cell_line: str = 'A549',
    initial_count: float = 500000,
    vessel_type: str = '96-well',
    **kwargs
) -> None:
    """
    Seed a vessel with stable defaults.

    Abstracts over seed_vessel signature changes.
    """
    vm.seed_vessel(
        vessel_id=vessel_id,
        cell_line=cell_line,
        initial_count=initial_count,
        vessel_type=vessel_type,
        **kwargs
    )


def make_world(seed: int = 0, budget_wells: int = 100, **kwargs) -> ExperimentalWorld:
    """
    Create ExperimentalWorld with stable defaults.

    Hides changing constructor signatures.
    """
    return ExperimentalWorld(
        budget_wells=budget_wells,
        seed=seed,
        **kwargs
    )


def run_world(
    world: ExperimentalWorld,
    wells: list,
    design_id: str = 'test',
    hypothesis: str = 'tripwire test'
) -> Tuple[RawWellResult, ...]:
    """
    Run experiment through world interface.

    Converts simple well specs to Proposal if needed.

    Args:
        world: ExperimentalWorld instance
        wells: List of dicts with well spec (cell_line, compound, dose_uM, assay, duration_h)
        design_id: Design identifier
        hypothesis: Experiment hypothesis

    Returns:
        Tuple of RawWellResult
    """
    # Convert simple dicts to WellSpec
    well_specs = []
    for w in wells:
        well_spec = WellSpec(
            cell_line=w.get('cell_line', 'A549'),
            compound=w.get('compound', 'DMSO'),
            dose_uM=w.get('dose_uM', 0.0),
            time_h=w.get('time_h', w.get('duration_h', 72.0)),  # Accept both
            assay=w.get('assay', 'cell_painting'),
            position_tag=w.get('position_tag', 'center')
        )
        well_specs.append(well_spec)

    # Create proposal
    proposal = Proposal(
        design_id=design_id,
        hypothesis=hypothesis,
        wells=well_specs,
        budget_limit=world.budget_remaining
    )

    return world.run_experiment(proposal)


def get_vessel_state(vm: BiologicalVirtualMachine, vessel_id: str):
    """Get vessel state from VM."""
    # VM stores vessels differently depending on version
    if hasattr(vm, 'vessel_states'):
        return vm.vessel_states.get(vessel_id)
    elif hasattr(vm, 'vessels'):
        return vm.vessels.get(vessel_id)
    elif hasattr(vm, '_vessels'):
        return vm._vessels.get(vessel_id)
    else:
        raise AttributeError("Cannot find vessels storage in VM")


def get_injection_manager_state(vm: BiologicalVirtualMachine, vessel_id: str):
    """Get injection manager state for vessel."""
    # injection_mgr vs injection_manager
    mgr = getattr(vm, 'injection_mgr', None) or getattr(vm, 'injection_manager', None)
    if mgr is None:
        raise AttributeError("Cannot find injection manager in VM")
    return mgr.get_state(vessel_id)
