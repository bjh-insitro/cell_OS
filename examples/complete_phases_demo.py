"""
Complete Simulation Demo: Phases 1-3

Demonstrates all simulation capabilities:
- Phase 1: Biological state tracking
- Phase 2: Workflow integration
- Phase 3: Data-driven parameters from YAML
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
import numpy as np

def demo_phase_1():
    """Phase 1: Basic biological simulation."""
    print("\n" + "="*70)
    print("PHASE 1: Biological State Tracking")
    print("="*70)
    
    vm = BiologicalVirtualMachine(simulation_speed=0.0)
    
    # Seed and grow
    vm.seed_vessel("T75_1", "HEK293T", initial_count=5e5)
    vm.incubate(48 * 3600, 37.0)
    
    state = vm.get_vessel_state("T75_1")
    print(f"\n✓ Cell growth simulation:")
    print(f"  Initial: 5.0e5 cells")
    print(f"  After 48h: {state['cell_count']:.2e} cells")
    print(f"  Viability: {state['viability']:.2%}")
    print(f"  Confluence: {state['confluence']:.2%}")

def demo_phase_2():
    """Phase 2: Workflow integration."""
    print("\n" + "="*70)
    print("PHASE 2: Workflow Integration")
    print("="*70)
    
    from cell_os.workflow_executor import WorkflowExecutor
    
    # Use BiologicalVirtualMachine as hardware
    hardware = BiologicalVirtualMachine(simulation_speed=0.0)
    executor = WorkflowExecutor(hardware=hardware)
    
    print("\n✓ BiologicalVirtualMachine integrated with WorkflowExecutor")
    print(f"  Hardware type: {type(hardware).__name__}")
    print(f"  Executor ready: {executor is not None}")
    print(f"  Simulation speed: instant (0.0)")

def demo_phase_3():
    """Phase 3: Data-driven parameters."""
    print("\n" + "="*70)
    print("PHASE 3: Data-Driven Parameters")
    print("="*70)
    
    # Import here to avoid module issues
    sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
    from manage_simulation_params import SimulationParameterManager
    
    manager = SimulationParameterManager()
    
    print("\n✓ YAML Parameter Database:")
    print(f"  Cell lines: {len(manager.params['cell_lines'])}")
    print(f"  Compounds: {len(manager.params['compound_sensitivity'])}")
    
    # Show some parameters
    print("\n  Sample Cell Line (HEK293T):")
    hek_params = manager.params['cell_lines']['HEK293T']
    print(f"    Doubling time: {hek_params['doubling_time_h']}h")
    print(f"    Max confluence: {hek_params['max_confluence']}")
    print(f"    Passage stress: {hek_params['passage_stress']}")
    
    print("\n  Sample Compound (staurosporine):")
    stauro = manager.params['compound_sensitivity']['staurosporine']
    print(f"    HEK293T IC50: {stauro['HEK293T']} μM")
    print(f"    HeLa IC50: {stauro['HeLa']} μM")
    print(f"    Hill slope: {stauro['hill_slope']}")

def demo_complete_workflow():
    """Complete end-to-end demonstration."""
    print("\n" + "="*70)
    print("COMPLETE WORKFLOW: All Phases Together")
    print("="*70)
    
    # Initialize with YAML parameters
    vm = BiologicalVirtualMachine(simulation_speed=0.0)
    
    print("\n1. Testing multiple cell lines (from YAML):")
    print("-" * 70)
    
    cell_lines = ["HEK293T", "HeLa", "Jurkat"]
    for cell_line in cell_lines:
        vm.seed_vessel(f"well_{cell_line}", cell_line, initial_count=1e5)
        vm.incubate(24 * 3600, 37.0)
        
        state = vm.get_vessel_state(f"well_{cell_line}")
        print(f"  {cell_line:10} | Count: {state['cell_count']:.2e} | Viability: {state['viability']:.2%}")
    
    print("\n2. Testing dose-response with YAML IC50 values:")
    print("-" * 70)
    
    # Test staurosporine on different cell lines
    doses = [0.01, 0.1, 1.0]
    compound = "staurosporine"
    
    for cell_line in ["HEK293T", "HeLa"]:
        print(f"\n  {cell_line} + {compound}:")
        for dose in doses:
            vessel_id = f"dose_{cell_line}_{dose}"
            vm.seed_vessel(vessel_id, cell_line, initial_count=1e5)
            result = vm.treat_with_compound(vessel_id, compound, dose_uM=dose)
            print(f"    {dose:6.2f} μM -> {result['viability_effect']:.2%} viability (IC50: {result['ic50']} μM)")
    
    print("\n3. Comparing passage stress across cell lines:")
    print("-" * 70)
    
    for cell_line in cell_lines:
        vessel_id = f"passage_{cell_line}"
        vm.seed_vessel(vessel_id, cell_line, initial_count=4e6)
        
        result = vm.passage_cells(vessel_id, f"{vessel_id}_P1", split_ratio=4.0)
        print(f"  {cell_line:10} | Viability after passage: {result['target_viability']:.2%}")

def demo_parameter_management():
    """Demonstrate parameter management tool."""
    print("\n" + "="*70)
    print("PARAMETER MANAGEMENT")
    print("="*70)
    
    sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
    from manage_simulation_params import SimulationParameterManager
    
    manager = SimulationParameterManager()
    
    print("\n✓ Current database:")
    manager.list_cell_lines()
    manager.list_compounds()
    
    print("\n✓ Easy to extend:")
    print("  manager.add_cell_line('A549', doubling_time_h=22.0)")
    print("  manager.add_compound('etoposide', ic50_values={'HEK293T': 2.5})")

def main():
    print("\n" + "="*70)
    print("CELL_OS SIMULATION SYSTEM - COMPLETE DEMONSTRATION")
    print("Phases 1, 2 & 3")
    print("="*70)
    
    # Set random seed for reproducibility
    np.random.seed(42)
    
    # Run all demos
    demo_phase_1()
    demo_phase_2()
    demo_phase_3()
    demo_complete_workflow()
    demo_parameter_management()
    
    print("\n" + "="*70)
    print("✓ ALL DEMONSTRATIONS COMPLETE")
    print("="*70)
    print("\nKey Achievements:")
    print("  ✅ Phase 1: Biological state tracking with realistic growth/passage/treatment")
    print("  ✅ Phase 2: Seamless integration with WorkflowExecutor")
    print("  ✅ Phase 3: Data-driven parameters from YAML (5 cell lines, 6 compounds)")
    print("\nReady for:")
    print("  • Synthetic data generation at scale")
    print("  • ML model training")
    print("  • Algorithm benchmarking")
    print("  • Experimental design validation")
    print()

if __name__ == "__main__":
    main()
