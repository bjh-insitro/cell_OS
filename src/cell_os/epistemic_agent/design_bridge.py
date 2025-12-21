"""
Design Bridge: Converts agent Proposals to validated, persistent design JSON artifacts.

This ensures:
1. Every execution has a design artifact (Covenant 6: provenance)
2. Designs can be validated against lab constraints
3. Execution is deterministic and replayable
4. Agent decisions create auditable plate maps

The bridge sits between agent proposals and world execution:
  Proposal → DesignJSON → Validate → Persist → Execute
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from .schemas import Proposal, WellSpec
from .exceptions import InvalidDesignError
from ..simulation.design_validation import ExperimentalDesignValidator


class RefusalPersistenceError(RuntimeError):
    """Raised when refusal artifacts fail to write.

    This is distinct from InvalidDesignError because:
    - The refusal is still enforced (agent still refuses)
    - But the audit trail is degraded (receipt write failed)
    - Caller must surface this degradation explicitly
    """
    pass


def proposal_to_design_json(
    proposal: Proposal,
    cycle: int,
    run_id: str,
    well_positions: List[str],
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Convert agent Proposal to design JSON artifact.

    Args:
        proposal: Agent's experiment proposal
        cycle: Current cycle number (for metadata)
        run_id: Run identifier (for provenance)
        well_positions: Actual well positions allocated by world (e.g., ["A01", "A02", ...])
        metadata: Optional additional metadata

    Returns:
        Design JSON dict matching the schema in data/designs/*.json

    Raises:
        ValueError: If proposal and well_positions length mismatch
    """
    if len(proposal.wells) != len(well_positions):
        raise ValueError(
            f"Proposal has {len(proposal.wells)} wells but {len(well_positions)} positions provided"
        )

    # Generate design ID if not already present
    design_id = proposal.design_id

    # Convert WellSpecs to design wells
    design_wells = []
    for wellspec, well_pos in zip(proposal.wells, well_positions):
        design_well = {
            "cell_line": wellspec.cell_line,
            "compound": wellspec.compound,
            "dose_uM": wellspec.dose_uM,
            "dose_type": "vehicle" if wellspec.compound == "DMSO" else "treatment",
            "timepoint_h": wellspec.time_h,
            "day": 1,  # Agent currently single-day (extend later for multi-day campaigns)
            "operator": "EpistemicAgent",  # Mark as autonomous
            "is_sentinel": False,  # Agent doesn't currently use sentinels
            "plate_id": f"Agent_{run_id[:8]}_Cycle{cycle}",
            "well_pos": well_pos,
            # Optional: add assay field if needed for multi-assay designs
            "_assay": wellspec.assay,  # Prefix with _ to mark as agent-specific extension
            "_position_tag": wellspec.position_tag,  # Preserve agent's intent
        }
        design_wells.append(design_well)

    # Build design JSON
    design = {
        "design_id": design_id,
        "design_type": "autonomous_epistemic",  # Distinguish from pre-planned designs
        "description": proposal.hypothesis,  # Agent's hypothesis becomes design description
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "created_by": "epistemic_agent",
            "run_id": run_id,
            "cycle": cycle,
            "budget_limit": proposal.budget_limit,
            "n_wells": len(proposal.wells),
            "design_seed": None,  # Agent doesn't use seeds (execution uses run seed)
            # Agent-specific metadata
            "autonomous": True,
            "hypothesis": proposal.hypothesis,
            **(metadata or {}),
        },
        "wells": design_wells,
    }

    return design


def validate_design(
    design: Dict[str, Any],
    strict: bool = True
) -> None:
    """Validate design JSON against lab constraints.

    Args:
        design: Design JSON dict
        strict: If True, enforce all constraints. If False, warn only.

    Raises:
        InvalidDesignError: If design violates constraints (structured, no parsing needed)

    IMPORTANT: This is currently PLACEHOLDER validation that only checks
    structural requirements (required fields, well format, duplicates).
    Full validation (compound library, dose ranges, plate capacity,
    multi-day constraints) is NOT ACTIVE.

    TODO: Import actual validation logic from src/cell_os/simulation/design_validation.py
    """
    design_id = design.get("design_id", "unknown")
    cycle = design.get("metadata", {}).get("cycle")

    # Required top-level fields
    required_fields = ["design_id", "design_type", "description", "metadata", "wells"]
    for field in required_fields:
        if field not in design:
            raise InvalidDesignError(
                message=f"Missing required field: {field}",
                violation_code="missing_required_field",
                design_id=design_id,
                cycle=cycle,
                validator_mode="placeholder",
                details={"missing_field": field}
            )

    # Validate wells structure
    if not isinstance(design["wells"], list):
        raise InvalidDesignError(
            message="'wells' must be a list",
            violation_code="invalid_wells_structure",
            design_id=design_id,
            cycle=cycle,
            validator_mode="placeholder"
        )

    if len(design["wells"]) == 0:
        raise InvalidDesignError(
            message="Design must contain at least one well",
            violation_code="empty_design",
            design_id=design_id,
            cycle=cycle,
            validator_mode="placeholder"
        )

    # Validate each well
    required_well_fields = [
        "cell_line", "compound", "dose_uM", "timepoint_h",
        "plate_id", "well_pos"
    ]
    for i, well in enumerate(design["wells"]):
        for field in required_well_fields:
            if field not in well:
                raise InvalidDesignError(
                    message=f"Well {i} missing required field: {field}",
                    violation_code="missing_well_field",
                    design_id=design_id,
                    cycle=cycle,
                    validator_mode="placeholder",
                    details={"well_index": i, "missing_field": field}
                )

        # Validate well position format (A01-H12 for 96-well)
        well_pos = well["well_pos"]
        if not (len(well_pos) == 3 and
                well_pos[0] in "ABCDEFGH" and
                well_pos[1:].isdigit() and
                1 <= int(well_pos[1:]) <= 12):
            if strict:
                raise InvalidDesignError(
                    message=f"Well {i} has invalid well_pos: {well_pos} (expected A01-H12)",
                    violation_code="invalid_well_position",
                    design_id=design_id,
                    cycle=cycle,
                    validator_mode="placeholder",
                    details={"well_index": i, "well_pos": well_pos}
                )

        # Validate dose is non-negative
        if well["dose_uM"] < 0:
            raise InvalidDesignError(
                message=f"Well {i} has negative dose: {well['dose_uM']}",
                violation_code="negative_dose",
                design_id=design_id,
                cycle=cycle,
                validator_mode="placeholder",
                details={"well_index": i, "dose_uM": well["dose_uM"]}
            )

        # Validate timepoint is positive
        if well["timepoint_h"] <= 0:
            raise InvalidDesignError(
                message=f"Well {i} has non-positive timepoint: {well['timepoint_h']}",
                violation_code="invalid_timepoint",
                design_id=design_id,
                cycle=cycle,
                validator_mode="placeholder",
                details={"well_index": i, "timepoint_h": well["timepoint_h"]}
            )

    # Check for well position collisions
    well_positions = [w["well_pos"] for w in design["wells"]]
    duplicates = [pos for pos in set(well_positions) if well_positions.count(pos) > 1]
    if duplicates:
        raise InvalidDesignError(
            message=f"Duplicate well positions: {duplicates}",
            violation_code="duplicate_well_positions",
            design_id=design_id,
            cycle=cycle,
            validator_mode="placeholder",
            details={"duplicates": duplicates}
        )

    # Confluence confounding validation (density-matched design enforcement)
    # This ensures comparisons across treatment arms are not confounded by density differences
    validator = ExperimentalDesignValidator()

    # Convert design wells to validator format (timepoint_h → time_h, _assay → assay)
    validator_wells = []
    for w in design["wells"]:
        validator_well = {
            "cell_line": w["cell_line"],
            "compound": w["compound"],
            "dose_uM": w["dose_uM"],
            "time_h": w["timepoint_h"],
            "assay": w.get("_assay", "cell_painting"),  # Default to cell_painting if not specified
        }
        validator_wells.append(validator_well)

    try:
        validator.validate_proposal_for_confluence_confounding(
            wells=validator_wells,
            design_id=design_id,
            threshold=0.15
        )
    except ValueError as e:
        # Validator raises ValueError with structured dict
        if e.args and isinstance(e.args[0], dict):
            error_details = e.args[0]
            raise InvalidDesignError(
                message=error_details["message"],
                violation_code="confluence_confounding",
                design_id=design_id,
                cycle=cycle,
                validator_mode="policy_guard",
                details=error_details
            )
        else:
            # Re-raise if not our structured error
            raise

    # Batch confounding validation (balanced batch assignment enforcement)
    # This ensures treatment assignment is not confounded with technical batches
    from ..simulation.batch_confounding_validator import validate_batch_confounding

    batch_result = validate_batch_confounding(
        design,
        imbalance_threshold=0.7,
        strict=strict
    )

    if batch_result.is_confounded:
        raise InvalidDesignError(
            message=f"Batch confounded: {batch_result.violation_type} (imbalance={batch_result.imbalance_metric:.3f})",
            violation_code="batch_confounding",
            design_id=design_id,
            cycle=cycle,
            validator_mode="policy_guard",
            details={
                "violation_type": batch_result.violation_type,
                "confounded_arms": batch_result.confounded_arms,
                "imbalance_metric": batch_result.imbalance_metric,
                "resolution_strategies": batch_result.resolution_strategies,
                "plate_imbalance": batch_result.details.get("plate_imbalance"),
                "day_imbalance": batch_result.details.get("day_imbalance"),
                "operator_imbalance": batch_result.details.get("operator_imbalance"),
            }
        )

    # Passed all validations
    return None


def persist_design(
    design: Dict[str, Any],
    output_dir: Path,
    run_id: str,
    cycle: int
) -> Path:
    """Write design JSON to disk for provenance and replay.

    Args:
        design: Validated design JSON
        output_dir: Directory for design artifacts
        run_id: Run identifier
        cycle: Cycle number

    Returns:
        Path to written design file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Filename: run_<timestamp>_cycle_<n>_<design_id>.json
    design_id_short = design["design_id"][:8]
    filename = f"{run_id}_cycle_{cycle:03d}_{design_id_short}.json"
    filepath = output_dir / filename

    # Write with indentation for human readability
    with open(filepath, 'w') as f:
        json.dump(design, f, indent=2)

    return filepath


def persist_rejected_design(
    design: Dict[str, Any],
    output_dir: Path,
    run_id: str,
    cycle: int,
    violation_code: str,
    violation_message: str,
    validator_mode: str = "placeholder",
    git_sha: Optional[str] = None
) -> tuple[Path, Path]:
    """Write rejected design to quarantine directory with reason file.

    This ensures refusal is auditable and replayable, not just righteous.

    Args:
        design: Invalid design JSON (before validation failure)
        output_dir: Base directory for design artifacts
        run_id: Run identifier
        cycle: Cycle number
        violation_code: Machine-readable constraint violation code
        violation_message: Human-readable error message
        validator_mode: "placeholder" or "full" (indicates which validator caught it)
        git_sha: Optional git commit hash for reproducibility

    Returns:
        (design_path, reason_path): Paths to rejected design and reason files
    """
    # Quarantine directory
    rejected_dir = Path(output_dir) / "rejected"

    try:
        rejected_dir.mkdir(parents=True, exist_ok=True)

        # Filename with REJECTED suffix
        design_id_short = design.get("design_id", "unknown")[:8]
        base_filename = f"{run_id}_cycle_{cycle:03d}_{design_id_short}_REJECTED"

        # Write invalid design
        design_path = rejected_dir / f"{base_filename}.json"
        with open(design_path, 'w') as f:
            json.dump(design, f, indent=2, sort_keys=True)

        # Compute hash even for rejected design (for diff tracking)
        design_hash = compute_design_hash(design)

        # Write rejection reason (sibling file)
        reason_path = rejected_dir / f"{base_filename}.reason.json"
        reason = {
            "violation_code": violation_code,
            "violation_message": violation_message,
            "validator_mode": validator_mode,
            "design_hash": design_hash,
            "caught_at": {
                "cycle": cycle,
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(),
                "git_sha": git_sha,
            },
            "design_path": str(design_path),
        }
        with open(reason_path, 'w') as f:
            json.dump(reason, f, indent=2, sort_keys=True)

        return design_path, reason_path

    except Exception as ex:
        raise RefusalPersistenceError(
            f"Failed to persist refusal artifacts: {ex}"
        ) from ex


def compute_design_hash(design: Dict[str, Any]) -> str:
    """Compute deterministic hash of design for replay verification.

    Hashes ONLY execution-relevant fields. Changes to metadata, timestamps,
    or paths will NOT affect the hash. Changes to cell line, dose, timepoint,
    plate_id, day, operator, or sentinel status WILL change the hash.

    Args:
        design: Design JSON dict

    Returns:
        16-character hex hash
    """
    # Sort wells by position to ensure deterministic ordering
    wells_sorted = sorted(design["wells"], key=lambda w: w["well_pos"])

    # Extract only execution-relevant fields (ignore metadata, timestamps, paths)
    canonical = {
        "design_id": design["design_id"],
        "wells": [
            {
                "cell_line": w["cell_line"],
                "compound": w["compound"],
                "dose_uM": w["dose_uM"],
                "timepoint_h": w["timepoint_h"],
                "well_pos": w["well_pos"],
                "plate_id": w["plate_id"],
                "day": w["day"],
                "operator": w["operator"],
                "is_sentinel": w["is_sentinel"],
            }
            for w in wells_sorted
        ]
    }

    # Compute SHA256 hash of canonical JSON
    canonical_json = json.dumps(canonical, sort_keys=True)
    hash_bytes = hashlib.sha256(canonical_json.encode('utf-8')).digest()
    return hash_bytes.hex()[:16]


def load_design_from_catalog(
    design_id: str,
    catalog_path: Path = Path("data/designs/catalog.json")
) -> Dict[str, Any]:
    """Load a pre-generated design from the design catalog.

    This allows the agent to select validated designs instead of generating on-the-fly.

    Args:
        design_id: Design ID to load
        catalog_path: Path to design catalog

    Returns:
        Design JSON dict

    Raises:
        FileNotFoundError: If design not found in catalog
    """
    with open(catalog_path) as f:
        catalog = json.load(f)

    # Find design in catalog
    for entry in catalog.get("designs", []):
        if entry.get("design_id") == design_id:
            design_path = Path(entry["path"])
            with open(design_path) as f:
                return json.load(f)

    raise FileNotFoundError(f"Design {design_id} not found in catalog {catalog_path}")


# Export public API
__all__ = [
    "proposal_to_design_json",
    "validate_design",
    "persist_design",
    "persist_rejected_design",
    "compute_design_hash",
    "load_design_from_catalog",
    "RefusalPersistenceError",
]
