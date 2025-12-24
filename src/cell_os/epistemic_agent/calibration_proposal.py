"""
Calibration proposal template: controls-only, identity-blind, un-cheatable.

This module generates calibration proposals that are:
- Controls only (DMSO + sentinels)
- Identity-blind (no compound/dose information leakage)
- Center-heavy (reduce edge variance)
- Variance-sufficient (minimum 12 wells per cell line)

Design principle: Calibration measures the instrument, not biology.
It cannot sneak in learning by calling exploration "calibration."

The validator is your "calibration in a trench coat" defense.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import random

from .schemas import Proposal, WellSpec


# Allowed control types (identity-blind)
ALLOWED_CONTROLS = {
    "DMSO",  # Vehicle control
    # Sentinels (if you use them, add here)
    # "SENTINEL_MILD", "SENTINEL_STRONG"
}

# Forbidden tokens (identity leak detection)
FORBIDDEN_TOKENS = {
    "staurosporine", "taxol", "etoposide", "doxorubicin", "camptothecin",
    "compound", "dose", "concentration", "uM", "nM", "treatment", "perturb",
    "drug", "inhibitor", "agonist", "antagonist"
}


@dataclass
class CalibrationParams:
    """Parameters for calibration proposal generation."""
    min_controls_per_line: int = 12  # Minimum variance support
    prefer_controls_per_line: int = 24  # Preferred (if budget allows)
    center_fraction_min: float = 0.80  # At least 80% center wells
    default_time_h: float = 12.0  # Default timepoint
    default_assays: List[str] = None  # Default assays

    def __post_init__(self):
        if self.default_assays is None:
            self.default_assays = ["cell_painting"]  # Must include for nuclei_qc


def make_calibration_proposal(
    reason: str,
    cell_lines: List[str],
    budget_remaining: int,
    rng: random.Random,
    params: Optional[CalibrationParams] = None,
    capabilities: Optional[Dict[str, Any]] = None
) -> Proposal:
    """
    Generate control-only calibration proposal.

    This is identity-blind by design: no compounds, no doses, no experimental conditions.
    Only DMSO controls (+ sentinels if configured).

    Args:
        reason: Why calibration is needed ("high_uncertainty", "drift_detected", etc.)
        cell_lines: Cell lines to calibrate (usually 2: A549, HepG2)
        budget_remaining: Remaining budget in wells
        rng: Seeded random number generator for deterministic layouts
        params: Calibration parameters (optional)
        capabilities: World capabilities (optional, for validation)

    Returns:
        Proposal with control-only wells

    Raises:
        ValueError: If budget insufficient for minimum calibration
    """
    if params is None:
        params = CalibrationParams()

    # Determine number of controls per cell line based on budget
    # Target: 96 wells total (1 plate)
    # Split evenly across cell lines
    n_lines = len(cell_lines)
    if n_lines == 0:
        raise ValueError("No cell lines specified for calibration")

    wells_per_line = 96 // n_lines

    # Check budget
    total_wells = wells_per_line * n_lines
    if total_wells > budget_remaining:
        raise ValueError(
            f"Insufficient budget for calibration: need {total_wells} wells, "
            f"have {budget_remaining} remaining"
        )

    # Check minimum variance support
    if wells_per_line < params.min_controls_per_line:
        raise ValueError(
            f"Insufficient wells per cell line for calibration: {wells_per_line} < "
            f"{params.min_controls_per_line} minimum"
        )

    # Generate wells
    wells: List[WellSpec] = []

    for cell_line in cell_lines:
        # Determine center vs edge split (center-heavy)
        # Use ceiling to ensure we meet minimum (e.g., 0.8 * 48 = 38.4 → 39 center)
        import math
        n_center = math.ceil(wells_per_line * params.center_fraction_min)
        n_edge = wells_per_line - n_center

        # Create center control wells
        for _ in range(n_center):
            wells.append(WellSpec(
                cell_line=cell_line,
                compound="DMSO",  # Vehicle control
                dose_uM=0.0,  # No treatment
                time_h=params.default_time_h,
                assay=params.default_assays[0],  # Primary assay (Cell Painting)
                position_tag="center"
            ))

        # Create edge control wells (if any)
        for _ in range(n_edge):
            wells.append(WellSpec(
                cell_line=cell_line,
                compound="DMSO",
                dose_uM=0.0,
                time_h=params.default_time_h,
                assay=params.default_assays[0],
                position_tag="edge"
            ))

    # Shuffle wells for spatial randomization (seeded)
    rng.shuffle(wells)

    # Create proposal
    proposal = Proposal(
        design_id=f"calibration_{reason}",
        hypothesis=f"Calibrate measurement quality: {reason}",
        wells=wells,
        budget_limit=budget_remaining,
        layout_seed=rng.randint(0, 2**31 - 1)  # Seed for plate layout
    )

    # Validate proposal is identity-blind
    assert_calibration_proposal_is_identity_blind(proposal)

    return proposal


def assert_calibration_proposal_is_identity_blind(proposal: Proposal):
    """
    Validate that calibration proposal contains no identity information.

    This is the "calibration in a trench coat" defense: ensures calibration
    cannot sneak in learning by pretending to be controls-only.

    Checks:
    1. All compounds are in ALLOWED_CONTROLS
    2. All doses are 0.0 (no treatment)
    3. No forbidden tokens anywhere in proposal

    Args:
        proposal: Calibration proposal to validate

    Raises:
        ValueError: If proposal violates identity-blind constraints
    """
    # Check 1: All compounds are allowed controls
    for well in proposal.wells:
        if well.compound not in ALLOWED_CONTROLS:
            raise ValueError(
                f"Calibration proposal contains non-control compound: {well.compound}. "
                f"Allowed: {ALLOWED_CONTROLS}"
            )

    # Check 2: All doses are 0.0
    for well in proposal.wells:
        if well.dose_uM != 0.0:
            raise ValueError(
                f"Calibration proposal contains non-zero dose: {well.dose_uM} µM. "
                f"Calibration must be controls-only (dose=0.0)."
            )

    # Check 3: Recursive token scan for identity leaks
    # Convert proposal to dict and scan all string values
    proposal_dict = {
        "design_id": proposal.design_id,
        "hypothesis": proposal.hypothesis,
        "wells": [
            {
                "cell_line": w.cell_line,
                "compound": w.compound,
                "dose_uM": w.dose_uM,
                "time_h": w.time_h,
                "assay": w.assay,
                "position_tag": w.position_tag,
            }
            for w in proposal.wells
        ]
    }

    forbidden_found = []

    def scan_recursive(obj, path=""):
        """Recursively scan object for forbidden tokens."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                # Check key
                if isinstance(k, str) and any(token in k.lower() for token in FORBIDDEN_TOKENS):
                    # Allow "compound" as field name (it's in WellSpec schema)
                    if k != "compound" and k != "dose_uM":
                        forbidden_found.append(f"{path}.{k} (key)")
                scan_recursive(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                scan_recursive(item, f"{path}[{i}]")
        elif isinstance(obj, str):
            # Check string values
            obj_lower = obj.lower()
            for token in FORBIDDEN_TOKENS:
                if token in obj_lower and token not in {"compound", "dose"}:
                    # "DMSO" is allowed, compound names are not
                    if token not in {"dmso", "sentinel"}:
                        forbidden_found.append(f"{path} = '{obj}' (contains '{token}')")

    scan_recursive(proposal_dict)

    if forbidden_found:
        raise ValueError(
            f"Calibration proposal contains forbidden identity tokens:\n" +
            "\n".join(f"  - {item}" for item in forbidden_found[:5]) +
            (f"\n  ... and {len(forbidden_found) - 5} more" if len(forbidden_found) > 5 else "")
        )


def get_calibration_statistics(proposal: Proposal) -> Dict[str, Any]:
    """
    Extract statistics from calibration proposal for validation.

    Returns:
        Dict with keys:
        - total_wells: Total wells in proposal
        - wells_per_line: Wells per cell line
        - center_fraction: Fraction of wells in center positions
        - edge_fraction: Fraction of wells in edge positions
        - cell_lines: List of cell lines
        - compounds: Set of compounds (should be {"DMSO"} only)
    """
    from collections import Counter

    wells = proposal.wells
    n_total = len(wells)

    # Count by position
    position_counts = Counter(w.position_tag for w in wells)
    n_center = position_counts.get("center", 0)
    n_edge = position_counts.get("edge", 0)

    # Count by cell line
    line_counts = Counter(w.cell_line for w in wells)

    # Compounds (should be DMSO only)
    compounds = set(w.compound for w in wells)

    return {
        "total_wells": n_total,
        "wells_per_line": dict(line_counts),
        "center_fraction": n_center / n_total if n_total > 0 else 0.0,
        "edge_fraction": n_edge / n_total if n_total > 0 else 0.0,
        "cell_lines": list(line_counts.keys()),
        "compounds": compounds,
    }
