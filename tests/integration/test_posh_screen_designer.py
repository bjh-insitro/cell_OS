"""
Test script for POSH Screen Designer
"""

import sys
import os
sys.path.append(os.getcwd())

from src.posh_screen_designer import create_screen_design

def test_screen_designer():
    print("=" * 80)
    print("TESTING POSH SCREEN DESIGNER")
    print("=" * 80)
    
    # Test Case 1: Small pilot library (100 genes)
    print("\n[Test 1] Small Pilot Library (100 genes, A549)")
    design1 = create_screen_design(
        library_name="Kinase_Pilot",
        num_genes=100,
        cell_type="A549",
        viral_titer=1e7,
        target_cells_per_grna=750,
        moi=0.3
    )
    
    summary1 = design1.get_summary()
    print(f"  Total gRNAs: {design1.library.total_grnas}")
    print(f"  Transduction cells: {design1.transduction_cells_needed:,}")
    print(f"  Viral volume: {design1.viral_volume_ml:.1f} mL")
    print(f"  Transduction plates: {design1.transduction_plates}")
    print(f"  Screening plates: {design1.screening_plates}")
    print(f"  Cryo vials: {design1.cryo_vials_needed}")
    print(f"  Estimated cost: ${design1.estimated_cost_usd:,.0f}")
    
    # Test Case 2: Medium library (1000 genes)
    print("\n[Test 2] Medium Library (1000 genes, A549)")
    design2 = create_screen_design(
        library_name="Druggable_Genome",
        num_genes=1000,
        cell_type="A549",
        viral_titer=1e7,
        target_cells_per_grna=750,
        moi=0.3
    )
    
    print(f"  Total gRNAs: {design2.library.total_grnas}")
    print(f"  Transduction cells: {design2.transduction_cells_needed:,}")
    print(f"  Viral volume: {design2.viral_volume_ml:.1f} mL")
    print(f"  Transduction plates: {design2.transduction_plates}")
    print(f"  Screening plates: {design2.screening_plates}")
    print(f"  Cryo vials: {design2.cryo_vials_needed}")
    print(f"  Estimated cost: ${design2.estimated_cost_usd:,.0f}")
    
    # Test Case 3: Large library (5000 genes)
    print("\n[Test 3] Large Library (5000 genes, A549)")
    design3 = create_screen_design(
        library_name="Genome_Wide",
        num_genes=5000,
        cell_type="A549",
        viral_titer=1e7,
        target_cells_per_grna=750,
        moi=0.3
    )
    
    print(f"  Total gRNAs: {design3.library.total_grnas}")
    print(f"  Transduction cells: {design3.transduction_cells_needed:,}")
    print(f"  Viral volume: {design3.viral_volume_ml:.1f} mL")
    print(f"  Transduction plates: {design3.transduction_plates}")
    print(f"  Screening plates: {design3.screening_plates}")
    print(f"  Cryo vials: {design3.cryo_vials_needed}")
    print(f"  Estimated cost: ${design3.estimated_cost_usd:,.0f}")
    
    # Print full protocol for Test 1
    print("\n" + "=" * 80)
    print("PROTOCOL SUMMARY (Test 1)")
    print("=" * 80)
    print(design1.get_protocol_summary())
    
    print("\n" + "=" * 80)
    print("ALL TESTS PASSED")
    print("=" * 80)

if __name__ == "__main__":
    test_screen_designer()
