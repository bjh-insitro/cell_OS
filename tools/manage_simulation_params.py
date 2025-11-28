"""
Parameter Management Tool

Utility for adding and managing simulation parameters.
"""

import yaml
from pathlib import Path
from typing import Dict, Any


class SimulationParameterManager:
    """Manage simulation parameters in YAML file."""
    
    def __init__(self, params_file: str = "data/simulation_parameters.yaml"):
        self.params_file = Path(params_file)
        self.params = self._load()
        
    def _load(self) -> Dict[str, Any]:
        """Load parameters from YAML."""
        if not self.params_file.exists():
            return {"cell_lines": {}, "compound_sensitivity": {}, "defaults": {}}
            
        with open(self.params_file, 'r') as f:
            return yaml.safe_load(f)
            
    def _save(self):
        """Save parameters to YAML."""
        with open(self.params_file, 'w') as f:
            yaml.dump(self.params, f, default_flow_style=False, sort_keys=False)
            
    def add_cell_line(self, name: str, 
                     doubling_time_h: float = 24.0,
                     max_confluence: float = 0.9,
                     max_passage: int = 30,
                     senescence_rate: float = 0.01,
                     seeding_efficiency: float = 0.85,
                     passage_stress: float = 0.02,
                     cell_count_cv: float = 0.10,
                     viability_cv: float = 0.02,
                     biological_cv: float = 0.05):
        """Add a new cell line to the database."""
        self.params["cell_lines"][name] = {
            "doubling_time_h": doubling_time_h,
            "max_confluence": max_confluence,
            "max_passage": max_passage,
            "senescence_rate": senescence_rate,
            "seeding_efficiency": seeding_efficiency,
            "passage_stress": passage_stress,
            "cell_count_cv": cell_count_cv,
            "viability_cv": viability_cv,
            "biological_cv": biological_cv
        }
        self._save()
        print(f"✓ Added cell line: {name}")
        
    def add_compound(self, name: str, 
                    ic50_values: Dict[str, float],
                    hill_slope: float = 1.0):
        """
        Add a new compound to the database.
        
        Args:
            name: Compound name
            ic50_values: Dict mapping cell line names to IC50 values (μM)
            hill_slope: Hill slope for dose-response curve
        """
        compound_data = ic50_values.copy()
        compound_data["hill_slope"] = hill_slope
        
        self.params["compound_sensitivity"][name] = compound_data
        self._save()
        print(f"✓ Added compound: {name} with {len(ic50_values)} IC50 values")
        
    def list_cell_lines(self):
        """List all cell lines in database."""
        print("\nCell Lines:")
        print("-" * 60)
        for name, params in self.params["cell_lines"].items():
            print(f"{name:15} | Doubling: {params['doubling_time_h']}h | Max passage: {params['max_passage']}")
            
    def list_compounds(self):
        """List all compounds in database."""
        print("\nCompounds:")
        print("-" * 60)
        for name, data in self.params["compound_sensitivity"].items():
            cell_lines = [k for k in data.keys() if k != "hill_slope"]
            print(f"{name:20} | Hill slope: {data.get('hill_slope', 1.0)} | Cell lines: {len(cell_lines)}")
            
    def get_ic50(self, compound: str, cell_line: str) -> float:
        """Get IC50 value for a compound/cell line pair."""
        compound_data = self.params["compound_sensitivity"].get(compound, {})
        return compound_data.get(cell_line, self.params["defaults"].get("default_ic50", 1.0))


def main():
    """Example usage."""
    manager = SimulationParameterManager()
    
    print("="*60)
    print("Simulation Parameter Manager")
    print("="*60)
    
    # List current parameters
    manager.list_cell_lines()
    manager.list_compounds()
    
    # Example: Add a new cell line
    print("\n" + "="*60)
    print("Example: Adding new cell line (A549)")
    print("="*60)
    
    manager.add_cell_line(
        name="A549",
        doubling_time_h=22.0,
        max_confluence=0.88,
        max_passage=25,
        passage_stress=0.022
    )
    
    # Example: Add IC50 values for existing compound
    print("\nExample: Adding IC50 for A549 to existing compounds")
    print("="*60)
    
    # Get existing staurosporine data
    stauro_data = manager.params["compound_sensitivity"].get("staurosporine", {})
    stauro_data["A549"] = 0.15  # Add A549 IC50
    manager.params["compound_sensitivity"]["staurosporine"] = stauro_data
    manager._save()
    print("✓ Added A549 IC50 for staurosporine")
    
    # Example: Add completely new compound
    print("\nExample: Adding new compound (etoposide)")
    print("="*60)
    
    manager.add_compound(
        name="etoposide",
        ic50_values={
            "HEK293T": 2.5,
            "HeLa": 1.8,
            "A549": 3.2
        },
        hill_slope=1.1
    )
    
    # Show updated lists
    print("\n" + "="*60)
    print("Updated Database:")
    print("="*60)
    manager.list_cell_lines()
    manager.list_compounds()
    
    print("\n✓ All examples completed!")


if __name__ == "__main__":
    main()
