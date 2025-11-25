"""
posh_screen_designer.py

Experimental planning calculator for POSH screens.
Determines cell counts, plate numbers, transduction scale, and banking requirements.
"""

from dataclasses import dataclass
from typing import Optional, Dict
import math

@dataclass
class LibrarySpec:
    """gRNA library specification."""
    name: str
    num_genes: int
    grnas_per_gene: int = 4
    viral_titer_tu_ml: float = 1e7  # Transducing units per mL
    viral_volume_ml: float = 1.0
    
    @property
    def total_grnas(self) -> int:
        return self.num_genes * self.grnas_per_gene

@dataclass
class CellTypeParams:
    """Cell type-specific parameters for POSH."""
    name: str
    barcode_efficiency: float  # Fraction of cells with valid barcodes (0.0-1.0)
    cells_per_well_6well: int  # Maximum cells per well in 6-well plate
    doubling_time_hours: float = 24.0
    
@dataclass
class ScreenDesign:
    """Complete POSH screen experimental design."""
    library: LibrarySpec
    cell_type: CellTypeParams
    target_cells_per_grna: int = 750  # Target 500-1000
    moi: float = 0.3
    representation: int = 250  # Coverage multiplier for transduction
    plate_format: str = "6-well"
    
    def __post_init__(self):
        """Calculate all derived parameters."""
        self._calculate()
    
    def _calculate(self):
        """Perform all calculations."""
        # Key parameters
        cells_per_well_at_80pct = self.cell_type.cells_per_well_6well  # e.g., 500K for A549
        wells_per_plate = 6
        
        # 1. Target cell counts at FIXATION (end of experiment)
        # We want 500-1000 valid barcoded cells per gRNA
        self.total_target_cells = self.library.total_grnas * self.target_cells_per_grna
        
        # 2. Adjust for barcode efficiency
        # If we want 750 valid barcoded cells/gRNA and efficiency is 60%,
        # we need 750/0.60 = 1,250 total cells/gRNA
        self.cells_needed_for_barcoding = int(self.total_target_cells / self.cell_type.barcode_efficiency)
        
        # 3. Screening plates needed (at 80% confluence, fixation time)
        cells_per_plate_at_fixation = cells_per_well_at_80pct * wells_per_plate
        self.screening_plates = math.ceil(self.cells_needed_for_barcoding / cells_per_plate_at_fixation)
        
        # 4. Seeding density for screening
        # Seed at ~30% confluence, grow to 80% over ~3-4 days
        # For A549: 500K at 80% means seed ~200K per well
        seeding_fraction = 0.4  # Seed at 40% of final density
        cells_per_well_seeding = int(cells_per_well_at_80pct * seeding_fraction)
        self.screening_seeding_cells = cells_per_well_seeding * wells_per_plate * self.screening_plates
        
        # 5. Transduction scale
        # Need enough cells to achieve representation at target MOI
        # This is INDEPENDENT of screening scale - it's about library coverage
        self.transduction_cells_needed = self.library.total_grnas * self.representation
        
        # 6. Viral particles needed
        # MOI = (viral particles) / (cells)
        self.viral_particles_needed = self.moi * self.transduction_cells_needed
        
        # 7. Viral volume needed
        self.viral_volume_ml = self.viral_particles_needed / self.library.viral_titer_tu_ml
        
        # 8. Transduction plates (for spinoculation)
        # Seed at lower density for transduction (~50K/well for 6-well)
        cells_per_well_transduction = 50000  # Lower density for transduction
        cells_per_plate_transduction = cells_per_well_transduction * wells_per_plate
        self.transduction_plates = math.ceil(self.transduction_cells_needed / cells_per_plate_transduction)
        
        # 9. Selection and expansion
        # After selection, need to expand to screening scale
        # Assume 50% survival after puromycin selection
        self.post_selection_cells = int(self.transduction_cells_needed * 0.5)
        
        # 10. Banking strategy
        # Bank enough cells for 4 independent screens
        # Each screen needs: screening_seeding_cells
        # Add 20% buffer for thaw losses and passage
        cells_per_screen = int(self.screening_seeding_cells * 1.2)
        total_cells_for_banking = cells_per_screen * 4  # 4 screens
        
        # 11. Expansion needed for banking
        # Need to grow from post-selection cells to banking target
        self.expansion_fold_for_banking = total_cells_for_banking / max(self.post_selection_cells, 1)
        
        # 12. Cryopreservation
        # Bank at 5M cells/vial (Micronic tubes), need vials for 4 screens
        cells_per_vial = 5e6  # Micronic tubes can hold 5-10M cells
        vials_per_screen = math.ceil(cells_per_screen / cells_per_vial)
        self.cryo_vials_needed = vials_per_screen * 4  # 4 screens total
        self.vials_per_screen = vials_per_screen
        self.cells_per_vial = cells_per_vial
        
        # 13. Thaw and recovery workflow
        # Thaw vials → Flask → Expand → Passage into 6-wells
        # Assume 70% recovery after thaw
        self.thaw_recovery_rate = 0.7
        self.cells_after_thaw = int(cells_per_screen * self.thaw_recovery_rate)
        
        # 14. Cost estimates (rough)
        self.estimated_cost_usd = self._estimate_cost()
    
    def _estimate_cost(self) -> float:
        """Rough cost estimate."""
        # Zombie POSH per plate
        cost_per_plate = 850.0
        
        # Transduction costs
        media_cost = self.transduction_plates * 50  # Media for transduction
        selection_cost = self.transduction_plates * 30  # Puromycin
        
        # Screening costs
        screening_cost = self.screening_plates * cost_per_plate
        
        # Cryopreservation
        cryo_cost = self.cryo_vials_needed * 5  # $5 per vial
        
        return media_cost + selection_cost + screening_cost + cryo_cost
    
    def get_summary(self) -> Dict[str, any]:
        """Get summary of design parameters."""
        return {
            "Library": {
                "Name": self.library.name,
                "Genes": self.library.num_genes,
                "gRNAs": self.library.total_grnas,
                "Viral Titer": f"{self.library.viral_titer_tu_ml:.2e} TU/mL"
            },
            "Cell Type": {
                "Name": self.cell_type.name,
                "Barcode Efficiency": f"{self.cell_type.barcode_efficiency * 100:.0f}%",
                "Cells/Well (6-well)": f"{self.cell_type.cells_per_well_6well:,}"
            },
            "Transduction": {
                "Target Cells": f"{self.transduction_cells_needed:,}",
                "MOI": self.moi,
                "Representation": self.representation,
                "Viral Volume Needed": f"{self.viral_volume_ml:.1f} mL",
                "Transduction Plates": self.transduction_plates
            },
            "Screening": {
                "Target Cells (Raw)": f"{self.total_target_cells:,}",
                "Cells Needed (Adjusted for Barcode Efficiency)": f"{self.cells_needed_for_barcoding:,}",
                "Screening Plates": self.screening_plates,
                "Cells/gRNA (Target)": self.target_cells_per_grna
            },
            "Post-Selection": {
                "Expected Cells": f"{self.post_selection_cells:,}",
                "Cryo Vials": self.cryo_vials_needed
            },
            "Cost": {
                "Estimated Total": f"${self.estimated_cost_usd:,.0f}"
            }
        }
    
    def get_protocol_summary(self) -> str:
        """Get human-readable protocol summary."""
        seeding_per_well = int(self.screening_seeding_cells / (self.screening_plates * 6))
        fixation_per_well = self.cell_type.cells_per_well_6well
        
        summary = f"""
# POSH Screen Design Summary

## Library: {self.library.name}
- {self.library.num_genes} genes × {self.library.grnas_per_gene} gRNAs/gene = {self.library.total_grnas} total gRNAs
- Viral titer: {self.library.viral_titer_tu_ml:.2e} TU/mL

## Cell Type: {self.cell_type.name}
- Barcode efficiency: {self.cell_type.barcode_efficiency * 100:.0f}%
- Capacity at 80% confluence: {fixation_per_well:,} cells/well (6-well)

## Experimental Design

### 1. Transduction (Day 0)
- **Cells needed**: {self.transduction_cells_needed:,} cells
- **MOI**: {self.moi}
- **Representation**: {self.representation}× coverage
- **Viral volume**: {self.viral_volume_ml:.1f} mL
- **Plates**: {self.transduction_plates} × 6-well plates
- **Seeding density**: ~50,000 cells/well (low density for transduction)

### 2. Selection (Days 2-7)
- Add puromycin at Day 2
- Maintain selection for 5-7 days
- Expected survival: ~50% ({self.post_selection_cells:,} cells)

### 3. Expansion & Banking (Days 7-14)
- Expand from {self.post_selection_cells:,} to {int(self.screening_seeding_cells * 1.2 * 4):,} cells
- **Expansion needed**: {self.expansion_fold_for_banking:.1f}× fold
- **Banking strategy**: Prepare for 4 independent screens
- **Freeze**: {self.cryo_vials_needed} total vials ({self.vials_per_screen} vials per screen × 4 screens)
- **Format**: {int(self.cells_per_vial/1e6)}M cells/vial (Micronic tubes)

### 4. Thaw & Recovery (Per Screen)
- Thaw {self.vials_per_screen} vial(s) into T75 flask
- Expected recovery: ~70% ({self.cells_after_thaw:,} cells)
- Expand in flask for 3-4 days
- Passage into 6-well plates when ready

### 5. Screening Setup (Day 0 of Screen)
- Seed into **{self.screening_plates} × 6-well plates**
- **Seeding density**: {seeding_per_well:,} cells/well (~40% confluence)
- Grow for 3-4 days to reach 80% confluence

### 6. Fixation & POSH (Day 3-4 of Screen)
- Fix at 80% confluence: {fixation_per_well:,} cells/well
- **Total cells at fixation**: {self.cells_needed_for_barcoding:,} cells
- **Expected valid barcodes**: {self.total_target_cells:,} cells ({self.target_cells_per_grna} cells/gRNA)
- Proceed with Zombie POSH protocol

## Cost Estimate
**Total**: ${self.estimated_cost_usd:,.0f}

## Critical Parameters
- ✓ Achieving {self.target_cells_per_grna} valid barcoded cells/gRNA (target: 500-1000)
- ✓ Barcode efficiency: {self.cell_type.barcode_efficiency * 100:.0f}% (measured via pilot)
- ✓ MOI: {self.moi} (optimized for single integration)
- ✓ Fixation at 80% confluence: {fixation_per_well:,} cells/well
"""
        return summary


# Predefined cell type parameters
CELL_TYPE_PARAMS = {
    "A549": CellTypeParams(
        name="A549 (Lung Carcinoma)",
        barcode_efficiency=0.60,  # 55-65% range, use middle
        cells_per_well_6well=500000,  # ~500K cells per well
        doubling_time_hours=22.0
    ),
    "HeLa": CellTypeParams(
        name="HeLa (Cervical Cancer)",
        barcode_efficiency=0.50,  # Estimate, needs pilot
        cells_per_well_6well=600000,
        doubling_time_hours=24.0
    ),
    "K562": CellTypeParams(
        name="K562 (Myeloid Leukemia)",
        barcode_efficiency=0.45,  # Suspension cells, lower efficiency
        cells_per_well_6well=1000000,  # Suspension, higher density
        doubling_time_hours=20.0
    )
}


def create_screen_design(
    library_name: str,
    num_genes: int,
    cell_type: str = "A549",
    viral_titer: float = 1e7,
    target_cells_per_grna: int = 750,
    moi: float = 0.3
) -> ScreenDesign:
    """
    Convenience function to create a screen design.
    
    Args:
        library_name: Name of the library
        num_genes: Number of genes in library
        cell_type: Cell type to use (A549, HeLa, K562)
        viral_titer: Viral titer in TU/mL
        target_cells_per_grna: Target cells per gRNA (500-1000 recommended)
        moi: Multiplicity of infection
    """
    library = LibrarySpec(
        name=library_name,
        num_genes=num_genes,
        viral_titer_tu_ml=viral_titer
    )
    
    cell_params = CELL_TYPE_PARAMS.get(cell_type)
    if not cell_params:
        raise ValueError(f"Unknown cell type: {cell_type}. Available: {list(CELL_TYPE_PARAMS.keys())}")
    
    return ScreenDesign(
        library=library,
        cell_type=cell_params,
        target_cells_per_grna=target_cells_per_grna,
        moi=moi
    )
