"""
Cell Line Database - SQLite Backend

This module provides cell-type-specific defaults by reading from the SQLite database.
Maintains the legacy API for backward compatibility.

Migration Note: This now reads from data/cell_lines.db instead of data/cell_lines.yaml
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from cell_os.database.repositories.cell_line import CellLineRepository

@dataclass
class CellLineProfile:
    """Profile for a specific cell line with optimal method defaults."""
    name: str
    cell_type: str  # e.g., "immortalized", "primary", "iPSC", "differentiated"
    
    # Dissociation
    dissociation_method: str  # "accutase", "tryple", "trypsin", "versene", "scraping"
    dissociation_notes: str
    
    # Transfection
    transfection_method: str  # "pei", "lipofectamine", "fugene", "calcium_phosphate", "nucleofection"
    transfection_efficiency: str  # "low", "medium", "high"
    transfection_notes: str
    
    # Transduction
    transduction_method: str  # "passive", "spinoculation"
    transduction_notes: str
    
    # Freezing
    freezing_media: str  # "cryostor", "fbs_dmso", "bambanker", "mfresr"
    freezing_notes: str
    
    # Culture conditions
    coating: str  # e.g., "laminin_521", "matrigel", "plo", "none"
    media: str  # Primary media type
    
    # Cost profile
    cost_tier: str  # "budget", "standard", "premium"
    
    # Fields with defaults (must come after non-default fields)
    coating_required: bool = False
    vial_type: str = "cryovial_1_8ml"  # Default vial type
    freezing_volume_ml: float = 1.0  # Default freezing volume
    cells_per_vial: int = 1000000  # Default cells per vial


# Global database instance
_DB_INSTANCE = None

def _get_db() -> CellLineRepository:
    """Get or create database instance."""
    global _DB_INSTANCE
    if _DB_INSTANCE is None:
        _DB_INSTANCE = CellLineRepository("data/cell_lines.db")
    return _DB_INSTANCE

def get_cell_line_profile(cell_line: str) -> Optional[CellLineProfile]:
    """
    Get the profile for a specific cell line from SQLite database.
    
    Args:
        cell_line: Cell line identifier (case-insensitive)
        
    Returns:
        CellLineProfile if found, None otherwise
    """
    db = _get_db()
    
    # Try exact match first
    cell_line_obj = db.get_cell_line(cell_line)
    
    # Try case-insensitive match
    if not cell_line_obj:
        all_lines = db.get_all_cell_lines()
        cell_line_map = {k.upper(): k for k in all_lines}
        key = cell_line_map.get(cell_line.upper())
        if key:
            cell_line_obj = db.get_cell_line(key)
    
    if not cell_line_obj:
        return None
    
    # Get characteristics and convert to dict
    char_list = db.get_characteristics(cell_line_obj.cell_line_id)
    chars = {c.characteristic: c.value for c in char_list}
    
    return CellLineProfile(
        name=cell_line_obj.display_name,
        cell_type=cell_line_obj.cell_type,
        dissociation_method=chars.get("dissociation_method", ""),
        dissociation_notes=chars.get("dissociation_notes", ""),
        transfection_method=chars.get("transfection_method", ""),
        transfection_efficiency=chars.get("transfection_efficiency", ""),
        transfection_notes=chars.get("transfection_notes", ""),
        transduction_method=chars.get("transduction_method", ""),
        transduction_notes=chars.get("transduction_notes", ""),
        freezing_media=chars.get("freezing_media", ""),
        freezing_notes=chars.get("freezing_notes", ""),
        vial_type=chars.get("vial_type", "cryovial_1_8ml"),
        freezing_volume_ml=float(chars.get("freezing_volume_ml", 1.0)),
        cells_per_vial=int(chars.get("cells_per_vial", 1000000)),
        coating=cell_line_obj.coating_reagent or "none",
        media=chars.get("media", cell_line_obj.growth_media),
        cost_tier=cell_line_obj.cost_tier,
        coating_required=cell_line_obj.coating_required
    )

def get_optimal_methods(cell_line: str) -> Dict[str, str]:
    """
    Get optimal methods for a cell line as a dictionary.
    
    Args:
        cell_line: Cell line identifier
        
    Returns:
        Dictionary with optimal method selections
    """
    profile = get_cell_line_profile(cell_line)
    if profile is None:
        raise ValueError(f"Unknown cell line: {cell_line}")
    
    return {
        "dissociation_method": profile.dissociation_method,
        "transfection_method": profile.transfection_method,
        "transduction_method": profile.transduction_method,
        "freezing_media": profile.freezing_media,
        "coating": profile.coating,
        "media": profile.media,
    }

def list_cell_lines() -> List[str]:
    """Get list of all supported cell lines."""
    db = _get_db()
    return db.get_all_cell_lines()

def get_cell_lines_by_type(cell_type: str) -> List[str]:
    """
    Get all cell lines of a specific type.
    
    Args:
        cell_type: "immortalized", "primary", "iPSC", "hESC", or "differentiated"
        
    Returns:
        List of cell line identifiers
    """
    db = _get_db()
    cell_lines = db.find_cell_lines(cell_type=cell_type)
    return [cl.cell_line_id for cl in cell_lines]

def get_cell_lines_by_cost_tier(cost_tier: str) -> List[str]:
    """
    Get all cell lines in a specific cost tier.
    
    Args:
        cost_tier: "budget", "standard", or "premium"
        
    Returns:
        List of cell line identifiers
    """
    db = _get_db()
    cell_lines = db.find_cell_lines(cost_tier=cost_tier)
    return [cl.cell_line_id for cl in cell_lines]

# Populate CELL_LINE_DATABASE for backward compatibility
def _populate_legacy_db() -> Dict[str, CellLineProfile]:
    db_dict = {}
    for cell_line_id in list_cell_lines():
        profile = get_cell_line_profile(cell_line_id)
        if profile:
            db_dict[cell_line_id] = profile
    return db_dict

CELL_LINE_DATABASE = _populate_legacy_db()
