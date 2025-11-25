"""
Cell Line Database - Optimal Method Defaults

This module provides cell-type-specific defaults for various cell culture operations.
Each cell line has recommended methods for dissociation, transfection, transduction,
and freezing based on published protocols and best practices.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass

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


# Cell Line Database
CELL_LINE_DATABASE: Dict[str, CellLineProfile] = {
    
    # ============================================================================
    # IMMORTALIZED CELL LINES (Hardy, easy to culture)
    # ============================================================================
    
    "HEK293": CellLineProfile(
        name="HEK293 (Human Embryonic Kidney)",
        cell_type="immortalized",
        dissociation_method="trypsin",
        dissociation_notes="Hardy cells, trypsin is sufficient and cost-effective",
        transfection_method="pei",
        transfection_efficiency="high",
        transfection_notes="PEI works excellently for HEK293, very cost-effective",
        transduction_method="spinoculation",
        transduction_notes="Spinoculation improves efficiency and reduces time",
        freezing_media="fbs_dmso",
        freezing_notes="Classic 90% FBS + 10% DMSO works well, very economical",
        coating="none",
        media="dmem_high_glucose",
        cost_tier="budget"
    ),
    
    "HEK293T": CellLineProfile(
        name="HEK293T (with SV40 T antigen)",
        cell_type="immortalized",
        dissociation_method="trypsin",
        dissociation_notes="Same as HEK293, very hardy",
        transfection_method="pei",
        transfection_efficiency="high",
        transfection_notes="Optimized for high transfection efficiency, ideal for LV production",
        transduction_method="spinoculation",
        transduction_notes="Fast and efficient",
        freezing_media="fbs_dmso",
        freezing_notes="Standard freezing protocol",
        coating="none",
        media="dmem_high_glucose",
        cost_tier="budget"
    ),
    
    "HeLa": CellLineProfile(
        name="HeLa (Human Cervical Cancer)",
        cell_type="immortalized",
        dissociation_method="trypsin",
        dissociation_notes="Very hardy, trypsin is fine",
        transfection_method="lipofectamine",
        transfection_efficiency="high",
        transfection_notes="Lipofectamine gives better results than PEI for HeLa",
        transduction_method="passive",
        transduction_notes="High transduction efficiency even without spinoculation",
        freezing_media="fbs_dmso",
        freezing_notes="Standard protocol",
        coating="none",
        media="dmem_high_glucose",
        cost_tier="budget"
    ),
    
    "Jurkat": CellLineProfile(
        name="Jurkat (Human T Lymphocyte)",
        cell_type="immortalized",
        dissociation_method="scraping",
        dissociation_notes="Suspension cells, gentle collection only",
        transfection_method="nucleofection",
        transfection_efficiency="medium",
        transfection_notes="Difficult to transfect, nucleofection is most reliable",
        transduction_method="spinoculation",
        transduction_notes="Spinoculation significantly improves transduction",
        freezing_media="fbs_dmso",
        freezing_notes="Standard protocol for suspension cells",
        coating="none",
        media="rpmi_1640",
        cost_tier="standard"
    ),
    
    "A549": CellLineProfile(
        name="A549 (Human Lung Carcinoma)",
        cell_type="immortalized",
        dissociation_method="trypsin",
        dissociation_notes="Hardy adherent cells, trypsin works well",
        transfection_method="lipofectamine",
        transfection_efficiency="medium",
        transfection_notes="Standard lipofectamine protocol",
        transduction_method="spinoculation",
        transduction_notes="Spinoculation at MOI 0.3 for POSH screens. Barcode efficiency: 55-65%",
        freezing_media="fbs_dmso",
        freezing_notes="Standard protocol",
        coating="none",
        media="f12k",
        cost_tier="budget"
    ),
    
    # ============================================================================
    # PLURIPOTENT STEM CELLS (Sensitive, require gentle handling)
    # ============================================================================
    
    "iPSC": CellLineProfile(
        name="Induced Pluripotent Stem Cells",
        cell_type="iPSC",
        dissociation_method="versene",
        dissociation_notes="Ultra-gentle EDTA-only dissociation preserves pluripotency and reduces differentiation",
        transfection_method="nucleofection",
        transfection_efficiency="medium",
        transfection_notes="Nucleofection is most reliable for iPSCs, though efficiency varies by line",
        transduction_method="spinoculation",
        transduction_notes="Spinoculation improves efficiency without harming cells",
        freezing_media="mfresr",
        freezing_notes="mFreSR optimized for stem cell viability and recovery",
        coating="laminin_521",
        media="mtesr_plus_kit",
        cost_tier="premium"
    ),
    
    "hESC": CellLineProfile(
        name="Human Embryonic Stem Cells",
        cell_type="hESC",
        dissociation_method="versene",
        dissociation_notes="Same as iPSC, very sensitive to enzymatic dissociation",
        transfection_method="nucleofection",
        transfection_efficiency="low",
        transfection_notes="Challenging to transfect, nucleofection is best option",
        transduction_method="spinoculation",
        transduction_notes="Spinoculation recommended",
        freezing_media="mfresr",
        freezing_notes="Optimized for hESC recovery",
        coating="laminin_521",
        media="mtesr_plus_kit",
        cost_tier="premium"
    ),
    
    # ============================================================================
    # PRIMARY CELLS (Sensitive, limited lifespan)
    # ============================================================================
    
    "Primary_Neurons": CellLineProfile(
        name="Primary Neurons",
        cell_type="primary",
        dissociation_method="scraping",
        dissociation_notes="Neurons are extremely sensitive, avoid enzymatic dissociation",
        transfection_method="nucleofection",
        transfection_efficiency="low",
        transfection_notes="Very difficult to transfect, nucleofection before plating is best",
        transduction_method="passive",
        transduction_notes="Gentle passive transduction to avoid stress",
        freezing_media="bambanker",
        freezing_notes="Serum-free, gentle freezing for sensitive neurons",
        coating="plo_laminin",
        media="neurobasal",
        cost_tier="premium"
    ),
    
    "Primary_Astrocytes": CellLineProfile(
        name="Primary Astrocytes",
        cell_type="primary",
        dissociation_method="tryple",
        dissociation_notes="More robust than neurons, TrypLE is gentle enough",
        transfection_method="lipofectamine",
        transfection_efficiency="medium",
        transfection_notes="Lipofectamine works reasonably well",
        transduction_method="spinoculation",
        transduction_notes="Spinoculation improves efficiency",
        freezing_media="bambanker",
        freezing_notes="Serum-free freezing recommended",
        coating="plo",
        media="dmem_high_glucose",
        cost_tier="standard"
    ),
    
    "Primary_Fibroblasts": CellLineProfile(
        name="Primary Fibroblasts",
        cell_type="primary",
        dissociation_method="trypsin",
        dissociation_notes="Hardy primary cells, trypsin is fine",
        transfection_method="lipofectamine",
        transfection_efficiency="medium",
        transfection_notes="Standard lipofectamine protocol",
        transduction_method="passive",
        transduction_notes="Good transduction efficiency",
        freezing_media="fbs_dmso",
        freezing_notes="Standard protocol works well",
        coating="none",
        media="dmem_high_glucose",
        cost_tier="budget"
    ),
    
    # ============================================================================
    # DIFFERENTIATED CELLS (From iPSC/hESC)
    # ============================================================================
    
    "iMicroglia": CellLineProfile(
        name="iPSC-derived Microglia",
        cell_type="differentiated",
        dissociation_method="accutase",
        dissociation_notes="Gentle dissociation preserves surface markers and function",
        transfection_method="nucleofection",
        transfection_efficiency="low",
        transfection_notes="Challenging to transfect post-differentiation",
        transduction_method="spinoculation",
        transduction_notes="Spinoculation recommended for immune cells",
        freezing_media="bambanker",
        freezing_notes="Serum-free, maintains viability",
        coating="plo",
        media="rpmi_1640",
        cost_tier="standard"
    ),
    
    "iNeurons": CellLineProfile(
        name="iPSC-derived Neurons (NGN2, etc.)",
        cell_type="differentiated",
        dissociation_method="accutase",
        dissociation_notes="Gentle dissociation if needed, but avoid passaging mature neurons",
        transfection_method="nucleofection",
        transfection_efficiency="low",
        transfection_notes="Transfect as progenitors before differentiation",
        transduction_method="passive",
        transduction_notes="Gentle passive transduction",
        freezing_media="bambanker",
        freezing_notes="Freeze as progenitors, not mature neurons",
        coating="plo_laminin",
        media="neurobasal",
        cost_tier="premium"
    ),
    
    "Cardiomyocytes": CellLineProfile(
        name="iPSC-derived Cardiomyocytes",
        cell_type="differentiated",
        dissociation_method="tryple",
        dissociation_notes="TrypLE is gentle enough for single-cell dissociation",
        transfection_method="nucleofection",
        transfection_efficiency="low",
        transfection_notes="Transfect before differentiation",
        transduction_method="spinoculation",
        transduction_notes="Spinoculation improves efficiency",
        freezing_media="cryostor",
        freezing_notes="CryoStor (DMSO-free) better for cardiomyocyte recovery",
        coating="matrigel",
        media="rpmi_1640",
        cost_tier="premium"
    ),
}


def get_cell_line_profile(cell_line: str) -> Optional[CellLineProfile]:
    """
    Get the profile for a specific cell line.
    
    Args:
        cell_line: Cell line identifier (case-insensitive)
        
    Returns:
        CellLineProfile if found, None otherwise
    """
    # Case-insensitive lookup
    cell_line_upper = cell_line.upper()
    for key, profile in CELL_LINE_DATABASE.items():
        if key.upper() == cell_line_upper:
            return profile
    return None


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


def list_cell_lines() -> list[str]:
    """Get list of all supported cell lines."""
    return list(CELL_LINE_DATABASE.keys())


def get_cell_lines_by_type(cell_type: str) -> list[str]:
    """
    Get all cell lines of a specific type.
    
    Args:
        cell_type: "immortalized", "primary", "iPSC", "hESC", or "differentiated"
        
    Returns:
        List of cell line identifiers
    """
    return [
        key for key, profile in CELL_LINE_DATABASE.items()
        if profile.cell_type == cell_type
    ]


def get_cell_lines_by_cost_tier(cost_tier: str) -> list[str]:
    """
    Get all cell lines in a specific cost tier.
    
    Args:
        cost_tier: "budget", "standard", or "premium"
        
    Returns:
        List of cell line identifiers
    """
    return [
        key for key, profile in CELL_LINE_DATABASE.items()
        if profile.cost_tier == cost_tier
    ]
