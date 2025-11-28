"""
Cell Line Database - Shim to data/cell_lines.yaml

This module provides cell-type-specific defaults by reading from the central
configuration file (data/cell_lines.yaml). It maintains the legacy API
for backward compatibility.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import yaml
from pathlib import Path

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
    
    # New field for explicit coating requirement
    coating_required: bool = False


_YAML_CACHE = None

def _load_yaml():
    global _YAML_CACHE
    if _YAML_CACHE is None:
        try:
            # Assume running from root
            path = Path("data/cell_lines.yaml")
            if not path.exists():
                 # Try relative path if running from tests?
                 # For now assume root.
                 return {}
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
            _YAML_CACHE = data.get('cell_lines', {})
        except Exception as e:
            print(f"Error loading cell_lines.yaml: {e}")
            _YAML_CACHE = {}
    return _YAML_CACHE

def get_cell_line_profile(cell_line: str) -> Optional[CellLineProfile]:
    """
    Get the profile for a specific cell line.
    
    Args:
        cell_line: Cell line identifier (case-insensitive)
        
    Returns:
        CellLineProfile if found, None otherwise
    """
    data = _load_yaml()
    # Case insensitive lookup
    cell_line_map = {k.upper(): k for k in data.keys()}
    key = cell_line_map.get(cell_line.upper())
    
    if not key:
        return None
    
    cfg = data[key]
    if "profile" not in cfg:
        return None
    
    p = cfg["profile"]
    return CellLineProfile(
        name=cfg.get("display_name", key),
        cell_type=p.get("cell_type", "unknown"),
        dissociation_method=p.get("dissociation_method", ""),
        dissociation_notes=p.get("dissociation_notes", ""),
        transfection_method=p.get("transfection_method", ""),
        transfection_efficiency=p.get("transfection_efficiency", ""),
        transfection_notes=p.get("transfection_notes", ""),
        transduction_method=p.get("transduction_method", ""),
        transduction_notes=p.get("transduction_notes", ""),
        freezing_media=p.get("freezing_media", ""),
        freezing_notes=p.get("freezing_notes", ""),
        coating=p.get("coating_reagent", "none"),
        media=p.get("media", ""),
        cost_tier=p.get("cost_tier", "standard"),
        coating_required=p.get("coating_required", False)
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
    data = _load_yaml()
    return list(data.keys())

def get_cell_lines_by_type(cell_type: str) -> List[str]:
    """
    Get all cell lines of a specific type.
    
    Args:
        cell_type: "immortalized", "primary", "iPSC", "hESC", or "differentiated"
        
    Returns:
        List of cell line identifiers
    """
    data = _load_yaml()
    results = []
    for key, cfg in data.items():
        if "profile" in cfg and cfg["profile"].get("cell_type") == cell_type:
            results.append(key)
    return results

def get_cell_lines_by_cost_tier(cost_tier: str) -> List[str]:
    """
    Get all cell lines in a specific cost tier.
    
    Args:
        cost_tier: "budget", "standard", or "premium"
        
    Returns:
        List of cell line identifiers
    """
    data = _load_yaml()
    results = []
    for key, cfg in data.items():
        if "profile" in cfg and cfg["profile"].get("cost_tier") == cost_tier:
            results.append(key)
    return results

# Populate CELL_LINE_DATABASE for backward compatibility
def _populate_legacy_db() -> Dict[str, CellLineProfile]:
    db = {}
    data = _load_yaml()
    for key in data:
        profile = get_cell_line_profile(key)
        if profile:
            db[key] = profile
    return db

CELL_LINE_DATABASE = _populate_legacy_db()
