"""
ExperimentalWorld with design bridge integration.

This is a drop-in replacement for world.py that adds:
1. Proposal → DesignJSON conversion
2. Design validation
3. Design persistence (for replay)
4. Execution from validated design

Replace ExperimentalWorld.run_experiment() with this version to enforce
the design artifact pipeline.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
import standalone_cell_thalamus as sim

from .schemas import Proposal, Observation
from .design_bridge import (
    proposal_to_design_json,
    validate_design,
    persist_design,
    persist_rejected_design,
    compute_design_hash,
    RefusalPersistenceError,
)
from .exceptions import InvalidDesignError


def run_experiment_with_bridge(
    self,  # ExperimentalWorld instance
    proposal: Proposal,
    cycle: int,
    run_id: str,
    design_output_dir: Optional[Path] = None,
    validate: bool = True
) -> Observation:
    """Execute proposed experiment through design artifact pipeline.

    This replaces the original run_experiment() method to enforce:
    1. Proposal → DesignJSON conversion
    2. Design validation (hard fail if invalid)
    3. Design persistence (for replay and provenance)
    4. Execution from validated design artifact

    Args:
        proposal: Agent's experiment proposal
        cycle: Current cycle number (for design metadata)
        run_id: Run identifier (for provenance)
        design_output_dir: Directory for design artifacts (default: results/designs/)
        validate: If True, validate design before execution (default: True)

    Returns:
        Observation with summary statistics

    Raises:
        ValueError: If proposal exceeds budget or has invalid parameters
        InvalidDesignError: If design violates lab constraints (Covenant 5)
    """
    # Validate budget
    wells_requested = len(proposal.wells)
    if wells_requested > self.budget_remaining:
        raise ValueError(
            f"Insufficient budget: requested {wells_requested}, "
            f"remaining {self.budget_remaining}"
        )

    # Allocate well positions for design JSON generation
    # Note: This still uses proposal → assignments temporarily for position allocation
    # but the EXECUTION path uses design_json as canonical source (see Step 4)
    _, well_positions = self._convert_proposal_to_assignments_with_positions(
        proposal
    )

    # === NEW: Design artifact pipeline ===

    # Step 1: Convert Proposal → DesignJSON
    design_json = proposal_to_design_json(
        proposal=proposal,
        cycle=cycle,
        run_id=run_id,
        well_positions=well_positions,
        metadata={
            "budget_remaining_before": self.budget_remaining,
            "budget_remaining_after": self.budget_remaining - wells_requested,
        }
    )

    # Step 2: Validate design (hard fail if invalid)
    if validate:
        try:
            validate_design(design_json, strict=True)
        except InvalidDesignError as e:
            # This is Covenant 5: agent must refuse what it cannot guarantee
            # CRITICAL: Persist rejected design BEFORE raising
            # (Receipt first, then die)
            if design_output_dir is None:
                design_output_dir = Path("results/designs") / run_id

            # Try to persist refusal artifacts
            # If persistence fails, we still refuse but mark audit as degraded
            try:
                rejected_path, reason_path = persist_rejected_design(
                    design=design_json,
                    output_dir=design_output_dir,
                    run_id=run_id,
                    cycle=cycle,
                    violation_code=e.violation_code,
                    violation_message=e.message,
                    validator_mode=e.validator_mode or "unknown",
                )
                audit_degraded = False
                audit_error = None
            except RefusalPersistenceError as persist_ex:
                # Persistence failed, but refusal is still enforced
                rejected_path = None
                reason_path = None
                audit_degraded = True
                audit_error = str(persist_ex)

            # Now raise with full provenance (structured, no string parsing)
            raise InvalidDesignError(
                message=f"Agent proposed invalid design (cycle {cycle}): {e.message}",
                violation_code=e.violation_code,
                design_id=e.design_id,
                rejected_path=str(rejected_path) if rejected_path else None,
                reason_path=str(reason_path) if reason_path else None,
                validator_mode=e.validator_mode,
                cycle=cycle,
                details=e.details,
                audit_degraded=audit_degraded,
                audit_error=audit_error,
            ) from e

    # Step 3: Persist design for provenance
    if design_output_dir is None:
        design_output_dir = Path("results/designs") / run_id
    design_path = persist_design(design_json, design_output_dir, run_id, cycle)

    # Compute hash for replay verification
    design_hash = compute_design_hash(design_json)

    # Log design provenance
    print(f"  Design artifact: {design_path.name} (hash={design_hash})")

    # === END: Design artifact pipeline ===

    # Step 4: Execute from design (design_json is now canonical source)
    # Convert design_json → WellAssignments to enforce that design is ground truth
    well_assignments_from_design = _design_to_well_assignments(design_json)
    results = self._simulate_wells(well_assignments_from_design, proposal.design_id)

    # Aggregate results into summary statistics
    observation = self._aggregate_results(
        results,
        proposal.design_id,
        wells_requested
    )

    # Attach design provenance to observation
    observation.qc_flags.append(f"design_hash:{design_hash}")
    observation.qc_flags.append(f"design_path:{design_path}")

    # Update budget
    self.budget_remaining -= wells_requested
    self.history.append(observation)

    return observation


def _design_to_well_assignments(design_json: Dict[str, Any]) -> List[Any]:
    """Convert design JSON to WellAssignments for simulator execution.

    This is the ONLY function that should convert design → execution format.
    By making this the sole path, we enforce that design_json is canonical.

    Args:
        design_json: Validated, persisted design artifact

    Returns:
        List of WellAssignment objects for simulator
    """
    assignments = []
    for well in design_json["wells"]:
        assignment = sim.WellAssignment(
            well_id=well["well_pos"],
            cell_line=well["cell_line"],
            compound=well["compound"],
            dose_uM=well["dose_uM"],
            timepoint_h=well["timepoint_h"],
            plate_id=well["plate_id"],
            day=well["day"],
            operator=well["operator"],
            is_sentinel=well["is_sentinel"]
        )
        assignments.append(assignment)
    return assignments


def _convert_proposal_to_assignments_with_positions(
    self,  # ExperimentalWorld instance
    proposal: Proposal
) -> tuple[List[Any], List[str]]:
    """Convert WellSpec to WellAssignment, returning both assignments and positions.

    This is the same as _convert_proposal_to_assignments but also returns
    the well positions for design JSON generation.

    Returns:
        (assignments, positions): List of WellAssignment and list of well_pos strings
    """
    assignments = []
    positions = []

    # Allocate wells based on position_tag
    edge_iter = iter(self.EDGE_WELLS)
    center_iter = iter(self.CENTER_WELLS)
    any_wells = self.CENTER_WELLS + self.EDGE_WELLS
    any_iter = iter(any_wells)

    for i, spec in enumerate(proposal.wells):
        # Select well position based on position_tag
        if spec.position_tag == 'edge':
            well_id = next(edge_iter, f"E{i+1:02d}")
        elif spec.position_tag == 'center':
            well_id = next(center_iter, f"C{i+1:02d}")
        else:  # 'any'
            well_id = next(any_iter, f"A{i+1:02d}")

        # Create WellAssignment (simulator's format)
        assignment = sim.WellAssignment(
            well_id=well_id,
            cell_line=spec.cell_line,
            compound=spec.compound,
            dose_uM=spec.dose_uM,
            timepoint_h=spec.time_h,
            plate_id=f"Plate_{proposal.design_id[:8]}",
            day=1,
            operator="Agent",
            is_sentinel=False
        )
        assignments.append(assignment)
        positions.append(well_id)

    return assignments, positions


# Integration instructions:
#
# In src/cell_os/epistemic_agent/world.py, replace run_experiment() with:
#
#   from .world_with_bridge import run_experiment_with_bridge
#
#   class ExperimentalWorld:
#       def run_experiment(self, proposal, cycle, run_id, **kwargs):
#           return run_experiment_with_bridge(
#               self, proposal, cycle, run_id, **kwargs
#           )
#
# In src/cell_os/epistemic_agent/loop.py, update observation call:
#
#   observation = self.world.run_experiment(
#       proposal,
#       cycle=cycle,
#       run_id=self.run_id  # Pass run_id for provenance
#   )
