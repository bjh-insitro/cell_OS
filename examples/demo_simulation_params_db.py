"""
Demo script showing the power of the Simulation Parameters Database.

This demonstrates queries that were difficult/impossible with YAML files.
"""

from cell_os.simulation_params_db import SimulationParamsDatabase

def main():
    print("="*60)
    print("🔍 SIMULATION PARAMETERS DATABASE - DEMO")
    print("="*60)
    
    # Initialize database
    db = SimulationParamsDatabase("data/simulation_params.db")
    
    # Query 1: Find all cell lines
    print("\n📋 Query 1: All cell lines")
    print("-" * 40)
    cell_lines = db.get_all_cell_lines()
    for cell_line in sorted(cell_lines):
        params = db.get_cell_line_params(cell_line)
        print(f"  {cell_line:10s} | {params.doubling_time_h:5.1f}h | Confluence: {params.max_confluence:.2f}")
    
    # Query 2: Find fast-growing cell lines
    print("\n⚡ Query 2: Fast-growing cell lines (< 22h doubling time)")
    print("-" * 40)
    for cell_line in cell_lines:
        params = db.get_cell_line_params(cell_line)
        if params.doubling_time_h < 22.0:
            print(f"  ✅ {cell_line}: {params.doubling_time_h}h")
    
    # Query 3: Find cell lines requiring coating
    print("\n🧫 Query 3: Cell lines requiring coating")
    print("-" * 40)
    for cell_line in cell_lines:
        params = db.get_cell_line_params(cell_line)
        if params.coating_required:
            print(f"  ✅ {cell_line}")
    
    # Query 4: Find sensitive compounds for U2OS
    print("\n🎯 Query 4: Compounds with IC50 < 1 µM for U2OS")
    print("-" * 40)
    sensitive = db.find_sensitive_compounds("U2OS", max_ic50=1.0)
    for compound in sensitive:
        print(f"  {compound.compound_name:15s} | IC50: {compound.ic50_um:6.3f} µM | Hill: {compound.hill_slope:.2f}")
    
    # Query 5: Compare compound sensitivity across cell lines
    print("\n📊 Query 5: Staurosporine sensitivity across all cell lines")
    print("-" * 40)
    for cell_line in sorted(cell_lines):
        sensitivity = db.get_compound_sensitivity("staurosporine", cell_line)
        if sensitivity:
            print(f"  {cell_line:10s} | IC50: {sensitivity.ic50_um:6.3f} µM")
    
    # Query 6: Find most potent compound for each cell line
    print("\n💪 Query 6: Most potent compound for each cell line")
    print("-" * 40)
    compounds = db.get_all_compounds()
    for cell_line in sorted(cell_lines):
        min_ic50 = float('inf')
        best_compound = None
        
        for compound in compounds:
            sensitivity = db.get_compound_sensitivity(compound, cell_line)
            if sensitivity and sensitivity.ic50_um < min_ic50:
                min_ic50 = sensitivity.ic50_um
                best_compound = compound
        
        if best_compound:
            print(f"  {cell_line:10s} | {best_compound:15s} | IC50: {min_ic50:6.3f} µM")
    
    # Query 7: Get default parameters
    print("\n⚙️  Query 7: Default parameters")
    print("-" * 40)
    defaults = [
        "doubling_time_h",
        "max_confluence",
        "seeding_efficiency",
        "default_ic50"
    ]
    for param in defaults:
        value = db.get_default_param(param)
        print(f"  {param:20s} = {value}")
    
    print("\n" + "="*60)
    print("✅ Demo complete!")
    print("\n💡 These queries would be difficult/slow with YAML files!")
    print("="*60)

if __name__ == "__main__":
    main()
