"""
Helper utilities shared across workflow builders.
"""
from __future__ import annotations

from typing import Tuple

DEFAULT_COATING = "vitronectin"
DEFAULT_DISSOCIATION = "trypsin"
STEM_CELL_ALIASES = {"ipsc", "hesc"}


def infer_vessel_type(vessel_id: str) -> str:
    """Infer standardized vessel type (e.g., 'T75') from a vessel identifier."""
    parts = vessel_id.split("_")
    if len(parts) > 1 and parts[0] == "flask":
        return parts[1].upper()
    return parts[-1].upper()


def resolve_coating(cell_line: str) -> Tuple[bool, str]:
    """
    Determine if coating is required and which agent to use.

    Returns (needs_coating, coating_agent).
    """
    profile = _get_cell_line_profile(cell_line)
    if profile and getattr(profile, "coating_required", False):
        agent = getattr(profile, "coating", None) or getattr(profile, "coating_reagent", None)
        return True, agent or DEFAULT_COATING

    if cell_line.lower() in STEM_CELL_ALIASES:
        return True, DEFAULT_COATING

    return False, DEFAULT_COATING


def resolve_dissociation_method(cell_line: str) -> str:
    """
    Determine preferred dissociation method for a cell line.
    Falls back to heuristics if no profile is available.
    """
    profile = _get_cell_line_profile(cell_line)
    if profile and getattr(profile, "dissociation_method", None):
        return profile.dissociation_method

    if cell_line.lower() in STEM_CELL_ALIASES:
        return "accutase"

    return DEFAULT_DISSOCIATION


def _get_cell_line_profile(cell_line: str):
    """Safely retrieve cell line profile without raising on import errors."""
    try:
        from cell_os.cell_line_database import get_cell_line_profile

        return get_cell_line_profile(cell_line)
    except Exception:
        return None
