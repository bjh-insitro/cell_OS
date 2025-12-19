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


class DesignValidationError(Exception):
    """Raised when a design violates lab constraints."""
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
        DesignValidationError: If design violates constraints

    TODO: Import actual validation logic from src/cell_os/simulation/design_validation.py
    For now, implements basic structural validation.
    """
    # Required top-level fields
    required_fields = ["design_id", "design_type", "description", "metadata", "wells"]
    for field in required_fields:
        if field not in design:
            raise DesignValidationError(f"Missing required field: {field}")

    # Validate wells structure
    if not isinstance(design["wells"], list):
        raise DesignValidationError("'wells' must be a list")

    if len(design["wells"]) == 0:
        raise DesignValidationError("Design must contain at least one well")

    # Validate each well
    required_well_fields = [
        "cell_line", "compound", "dose_uM", "timepoint_h",
        "plate_id", "well_pos"
    ]
    for i, well in enumerate(design["wells"]):
        for field in required_well_fields:
            if field not in well:
                raise DesignValidationError(
                    f"Well {i} missing required field: {field}"
                )

        # Validate well position format (A01-H12 for 96-well)
        well_pos = well["well_pos"]
        if not (len(well_pos) == 3 and
                well_pos[0] in "ABCDEFGH" and
                well_pos[1:].isdigit() and
                1 <= int(well_pos[1:]) <= 12):
            if strict:
                raise DesignValidationError(
                    f"Well {i} has invalid well_pos: {well_pos} (expected A01-H12)"
                )

        # Validate dose is non-negative
        if well["dose_uM"] < 0:
            raise DesignValidationError(
                f"Well {i} has negative dose: {well['dose_uM']}"
            )

        # Validate timepoint is positive
        if well["timepoint_h"] <= 0:
            raise DesignValidationError(
                f"Well {i} has non-positive timepoint: {well['timepoint_h']}"
            )

    # Check for well position collisions
    well_positions = [w["well_pos"] for w in design["wells"]]
    duplicates = [pos for pos in set(well_positions) if well_positions.count(pos) > 1]
    if duplicates:
        raise DesignValidationError(
            f"Duplicate well positions: {duplicates}"
        )

    # Passed validation
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


def compute_design_hash(design: Dict[str, Any]) -> str:
    """Compute deterministic hash of design for replay verification.

    Args:
        design: Design JSON dict

    Returns:
        16-character hex hash
    """
    # Sort wells by position to ensure deterministic ordering
    wells_sorted = sorted(design["wells"], key=lambda w: w["well_pos"])

    # Extract only execution-relevant fields (ignore metadata)
    canonical = {
        "design_id": design["design_id"],
        "wells": [
            {
                "cell_line": w["cell_line"],
                "compound": w["compound"],
                "dose_uM": w["dose_uM"],
                "timepoint_h": w["timepoint_h"],
                "well_pos": w["well_pos"],
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
    "compute_design_hash",
    "load_design_from_catalog",
    "DesignValidationError",
]
