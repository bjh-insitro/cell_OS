"""
Complete POSH Screen Workflow Recipe

Integrates screen designer calculations with parametric ops to create
a complete end-to-end workflow from transduction to analysis.
"""

from src.unit_ops import AssayRecipe, ParametricOps
from src.posh_screen_designer import create_screen_design

def get_complete_posh_screen_workflow(
    ops: ParametricOps,
    library_name: str,
    num_genes: int,
    cell_type: str = "A549",
    viral_titer: float = 1e7,
    target_cells_per_grna: int = 750,
    moi: float = 0.3
) -> AssayRecipe:
    """
    Complete POSH screen workflow from transduction to analysis.
    Integrates with screen designer calculations.
    
    This recipe captures all the information from the screen designer:
    - Cell counts at each stage
    - Plate numbers
    - Expansion requirements
    - Banking strategy (4 screens)
    - Thaw-flask-passage workflow
    
    Args:
        ops: ParametricOps instance
        library_name: Name of gRNA library
        num_genes: Number of genes in library
        cell_type: Cell type (A549, HeLa, K562)
        viral_titer: Viral titer in TU/mL
        target_cells_per_grna: Target cells per gRNA (500-1000)
        moi: Multiplicity of infection
        
    Returns:
        AssayRecipe with complete workflow and cost calculations
    """
    
    # Generate screen design with all calculations
    design = create_screen_design(
        library_name=library_name,
        num_genes=num_genes,
        cell_type=cell_type,
        viral_titer=viral_titer,
        target_cells_per_grna=target_cells_per_grna,
        moi=moi
    )
    
    vessel = "plate_6well"
    
    # Calculate number of passages needed for expansion
    # Assume ~3× expansion per passage
    passages_for_banking = int(design.expansion_fold_for_banking / 3)
    
    return AssayRecipe(
        name=f"POSH_Screen_{library_name}_{num_genes}g_{cell_type}",
        layers={
            "genetic_supply_chain": [
                # Upstream assumed complete - have viral stock ready
                # (Could add library design, cloning, virus production here)
            ],
            "cell_prep": [
                # Phase 1: Transduction (Day 0)
                (ops.op_transduce(
                    vessel,
                    method="spinoculation",
                    moi=moi,
                    num_cells=design.transduction_cells_needed
                ), design.transduction_plates),
                
                # Phase 2: Selection (Days 2-7)
                (ops.op_feed(vessel, antibiotic="puromycin"), 5),
                
                # Phase 3: Expansion for banking (Days 7-14)
                # Expand to bank for 4 screens
                (ops.op_passage(vessel, method="trypsin"), passages_for_banking),
                
                # Phase 4: Cryopreservation
                # Bank 4 screens worth of cells in Micronic tubes
                (ops.op_freeze(
                    vessel,
                    media="fbs_dmso",
                    num_vials=design.cryo_vials_needed
                ), 1),
                
                # === PER SCREEN WORKFLOW (repeat 4×) ===
                
                # Phase 5: Thaw and recovery
                (ops.op_thaw(vessel, num_vials=design.vials_per_screen), 1),
                
                # Phase 6: Flask expansion (3-4 days)
                (ops.op_passage(vessel, method="trypsin"), 2),
                
                # Phase 7: Seed screening plates at 40% confluence
                (ops.op_seed(vessel, num_cells=design.screening_seeding_cells), design.screening_plates),
                
                # Phase 8: Grow to 80% confluence (3-4 days)
                (ops.op_feed(vessel), 3),
            ],
            "phenotyping": [
                # Phase 9: Fixation at 80% confluence
                (ops.op_fix_cells(vessel), design.screening_plates),
                
                # Phase 10: Zombie POSH workflow
                (ops.op_decross_linking(vessel, duration_h=4.0), design.screening_plates),
                (ops.op_t7_ivt(vessel, duration_h=4.0), design.screening_plates),
                
                # Phase 11: SBS imaging (13 cycles for full barcode)
                (ops.op_sbs_cycle(vessel, cycle_number=1), design.screening_plates * 13),
            ],
            "compute": [
                # Phase 12: Image analysis
                (ops.op_compute_analysis("illumination_correction", design.screening_plates), 1),
                (ops.op_compute_analysis("cell_segmentation", design.screening_plates), 1),
                (ops.op_compute_analysis("base_calling", design.screening_plates * 13), 1),
                (ops.op_compute_analysis("barcode_stitching", design.screening_plates), 1),
                (ops.op_compute_analysis("feature_extraction", design.screening_plates), 1),
            ]
        }
    )


def get_workflow_metadata(design):
    """
    Extract key metadata from screen design for workflow tracking.
    
    Returns dict with all critical parameters that should be stored
    with the workflow execution.
    """
    return {
        "library": {
            "name": design.library.name,
            "num_genes": design.library.num_genes,
            "num_grnas": design.library.total_grnas,
            "viral_titer_tu_ml": design.library.viral_titer_tu_ml,
        },
        "cell_type": {
            "name": design.cell_type.name,
            "barcode_efficiency": design.cell_type.barcode_efficiency,
            "cells_per_well_6well": design.cell_type.cells_per_well_6well,
        },
        "transduction": {
            "cells_needed": design.transduction_cells_needed,
            "moi": design.moi,
            "representation": design.representation,
            "viral_volume_ml": design.viral_volume_ml,
            "plates": design.transduction_plates,
        },
        "banking": {
            "post_selection_cells": design.post_selection_cells,
            "expansion_fold": design.expansion_fold_for_banking,
            "cryo_vials_total": design.cryo_vials_needed,
            "vials_per_screen": design.vials_per_screen,
            "cells_per_vial": design.cells_per_vial,
            "screens_banked": 4,
        },
        "screening": {
            "plates": design.screening_plates,
            "seeding_cells_total": design.screening_seeding_cells,
            "cells_at_fixation": design.cells_needed_for_barcoding,
            "target_cells_per_grna": design.target_cells_per_grna,
            "expected_valid_barcodes": design.total_target_cells,
        },
        "thaw_recovery": {
            "vials_to_thaw": design.vials_per_screen,
            "recovery_rate": design.thaw_recovery_rate,
            "cells_after_thaw": design.cells_after_thaw,
        },
        "cost": {
            "estimated_total_usd": design.estimated_cost_usd,
        }
    }
