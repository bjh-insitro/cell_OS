"""
Library Banking Simulation Wrapper.

Simulates the process of transducing cells with a gRNA library and banking
for multiple POSH screens. Uses titration results to determine optimal conditions.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from cell_os.workflows import Workflow, WorkflowBuilder
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.unit_ops.base import VesselLibrary
from cell_os.simulation.utils import MockInventory


@dataclass
class LibraryBankingResult:
    """Result of library banking simulation."""
    cell_line: str
    library_size: int  # Number of gRNAs
    representation: int  # Cells per gRNA for transduction (e.g., 1000)
    fitted_titer_tu_ml: float  # From titration
    optimal_moi: float  # From titration
    target_cells_per_grna: int  # For final screens (e.g., 750)
    
    # Calculated transduction parameters
    transduction_cells_needed: int
    viral_volume_ml: float
    transduction_flasks: int
    
    # Post-selection
    post_selection_cells: int
    
    # Banking parameters
    cells_per_screen: int
    total_cells_for_banking: int
    expansion_fold_needed: float
    cryo_vials_needed: int
    cells_per_vial: float
    vials_per_screen: int
    
    # Fields with defaults (must be at the end)
    selection_survival_rate: float = 0.5
    workflow: Optional[Workflow] = None
    success: bool = True
    error_message: str = ""


def simulate_library_banking(
    cell_line: str,
    library_size: int,
    fitted_titer_tu_ml: float,
    optimal_moi: float,
    representation: int = 1000,
    target_cells_per_grna: int = 750,
    num_screens: int = 4,
    random_seed: int = 42
) -> LibraryBankingResult:
    """
    Simulate library transduction and banking workflow.
    
    Args:
        cell_line: Cell line name
        library_size: Number of gRNAs in library
        fitted_titer_tu_ml: Viral titer from titration (TU/mL)
        optimal_moi: Optimal MOI from titration
        representation: Coverage for transduction (cells per gRNA)
        target_cells_per_grna: Target cells per gRNA for final screens
        num_screens: Number of screens to bank for (default 4)
        random_seed: Random seed for reproducibility
        
    Returns:
        LibraryBankingResult with all calculations and workflow
    """
    try:
        # 1. Calculate transduction scale
        # Need representation × library_size cells for proper coverage
        transduction_cells_needed = library_size * representation
        
        # 2. Calculate viral volume needed
        # MOI = (viral particles) / (cells)
        # viral particles = MOI × cells
        # volume = viral particles / titer
        viral_particles_needed = optimal_moi * transduction_cells_needed
        viral_volume_ml = viral_particles_needed / fitted_titer_tu_ml
        
        # 3. Calculate transduction flasks
        # Seed at low density for transduction (~2M cells per T75)
        cells_per_flask_transduction = 2000000
        transduction_flasks = int(np.ceil(transduction_cells_needed / cells_per_flask_transduction))
        
        # 4. Post-selection cell count
        # Assume 50% survival after puromycin selection
        selection_survival_rate = 0.5
        post_selection_cells = int(transduction_cells_needed * selection_survival_rate)
        
        # 5. Calculate screening needs
        # Each screen needs enough cells to achieve target_cells_per_grna
        # Assume barcode efficiency of 60% for most cell lines
        barcode_efficiency = 0.60
        cells_needed_per_screen = int((library_size * target_cells_per_grna) / barcode_efficiency)
        
        # Add 20% buffer for thaw losses and passage
        cells_per_screen = int(cells_needed_per_screen * 1.2)
        
        # 6. Banking calculations
        total_cells_for_banking = cells_per_screen * num_screens
        expansion_fold_needed = total_cells_for_banking / max(post_selection_cells, 1)
        
        # 7. Cryopreservation
        # Bank at 5M cells/vial (Micronic tubes)
        cells_per_vial = 5e6
        vials_per_screen = int(np.ceil(cells_per_screen / cells_per_vial))
        cryo_vials_needed = vials_per_screen * num_screens
        
        # 8. Build workflow
        inv = MockInventory()
        vessels = VesselLibrary()
        ops = ParametricOps(vessels, inv)
        builder = WorkflowBuilder(ops)
        
        workflow = builder.build_library_banking_workflow(
            cell_line=cell_line,
            library_size=library_size,
            representation=representation
        )
        
        return LibraryBankingResult(
            cell_line=cell_line,
            library_size=library_size,
            representation=representation,
            fitted_titer_tu_ml=fitted_titer_tu_ml,
            optimal_moi=optimal_moi,
            target_cells_per_grna=target_cells_per_grna,
            transduction_cells_needed=transduction_cells_needed,
            viral_volume_ml=viral_volume_ml,
            transduction_flasks=transduction_flasks,
            post_selection_cells=post_selection_cells,
            selection_survival_rate=selection_survival_rate,
            cells_per_screen=cells_per_screen,
            total_cells_for_banking=total_cells_for_banking,
            expansion_fold_needed=expansion_fold_needed,
            cryo_vials_needed=cryo_vials_needed,
            cells_per_vial=cells_per_vial,
            vials_per_screen=vials_per_screen,
            workflow=workflow,
            success=True
        )
        
    except Exception as e:
        return LibraryBankingResult(
            cell_line=cell_line,
            library_size=library_size,
            representation=representation,
            fitted_titer_tu_ml=fitted_titer_tu_ml,
            optimal_moi=optimal_moi,
            target_cells_per_grna=target_cells_per_grna,
            transduction_cells_needed=0,
            viral_volume_ml=0.0,
            transduction_flasks=0,
            post_selection_cells=0,
            cells_per_screen=0,
            total_cells_for_banking=0,
            expansion_fold_needed=0.0,
            cryo_vials_needed=0,
            cells_per_vial=5e6,
            vials_per_screen=0,
            success=False,
            error_message=str(e)
        )
