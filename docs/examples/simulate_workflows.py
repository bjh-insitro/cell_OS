"""
Example: End-to-End Workflow Simulation

Demonstrates how to simulate complete experimental workflows and collect synthetic data.
"""

import pandas as pd
from pathlib import Path
from cell_os.simulation.executor import SimulationExecutor
from cell_os.unit_ops.base import UnitOp

# Ensure output directory exists
Path("results").mkdir(exist_ok=True)


def example_1_simple_passage_workflow():
    """
    Example 1: Simple passage workflow with data collection.
    """
    print("\n" + "="*60)
    print("Example 1: Simple Passage Workflow")
    print("="*60)
    
    # Initialize simulation executor
    executor = SimulationExecutor(
        db_path="data/sim_executions.db",
        collect_data=True,
        simulation_speed=0.0  # Instant execution
    )
    
    # Define workflow
    workflow = [
        UnitOp(
            operation="seed",
            parameters={
                "vessel_id": "T75_1",
                "cell_line": "HEK293T",
                "initial_count": 5e5,
                "capacity": 1e7
            }
        ),
        UnitOp(
            operation="incubate",
            parameters={"minutes": 72 * 60, "temperature_c": 37.0}  # 3 days
        ),
        UnitOp(
            operation="passage",
            parameters={
                "source_vessel": "T75_1",
                "target_vessel": "T75_2",
                "split_ratio": 4.0
            }
        ),
        UnitOp(
            operation="viability_assay",
            parameters={"vessel_id": "T75_2"}
        )
    ]
    
    # Execute workflow
    execution = executor.create_execution(workflow, name="Simple Passage")
    result = executor.execute(execution.execution_id)
    
    print(f"\nExecution Status: {result.status}")
    print(f"Steps Completed: {len([s for s in result.steps if s.status == 'completed'])}/{len(result.steps)}")
    
    # Show collected data
    print(f"\nCollected {len(executor.collected_data)} data points:")
    for record in executor.collected_data:
        print(f"  - {record['operation']}: {record.get('vessel_id', 'N/A')}")
        
    # Export data
    executor.export_data("results/simple_passage_data.json")
    print("\n✓ Data exported to results/simple_passage_data.json")
    
    # Show final vessel states
    states = executor.get_vessel_states()
    print(f"\nFinal Vessel States:")
    for vessel_id, state in states.items():
        print(f"  {vessel_id}:")
        print(f"    Cell Count: {state['cell_count']:.2e}")
        print(f"    Viability: {state['viability']:.2%}")
        print(f"    Passage: P{state['passage_number']}")


def example_2_dose_response_experiment():
    """
    Example 2: Dose-response experiment with multiple wells.
    """
    print("\n" + "="*60)
    print("Example 2: Dose-Response Experiment")
    print("="*60)
    
    executor = SimulationExecutor(collect_data=True, simulation_speed=0.0)
    
    # Define doses to test
    doses = [0.001, 0.01, 0.1, 1.0, 10.0]
    compound = "staurosporine"
    
    workflow = []
    
    # Seed all wells
    for i, dose in enumerate(doses):
        well_id = f"well_A{i+1}"
        workflow.extend([
            UnitOp(
                operation="seed",
                parameters={
                    "vessel_id": well_id,
                    "cell_line": "HEK293T",
                    "initial_count": 1e5,
                    "capacity": 5e5
                }
            )
        ])
    
    # Treat with different doses
    for i, dose in enumerate(doses):
        well_id = f"well_A{i+1}"
        workflow.append(
            UnitOp(
                operation="treat",
                parameters={
                    "vessel_id": well_id,
                    "compound": compound,
                    "dose_uM": dose
                }
            )
        )
    
    # Incubate
    workflow.append(
        UnitOp(
            operation="incubate",
            parameters={"minutes": 24 * 60, "temperature_c": 37.0}
        )
    )
    
    # Measure viability
    for i, dose in enumerate(doses):
        well_id = f"well_A{i+1}"
        workflow.append(
            UnitOp(
                operation="viability_assay",
                parameters={"vessel_id": well_id}
            )
        )
    
    # Execute
    execution = executor.create_execution(workflow, name="Dose-Response")
    result = executor.execute(execution.execution_id)
    
    print(f"\nExecution Status: {result.status}")
    
    # Extract dose-response data
    viability_data = [r for r in executor.collected_data if r['operation'] == 'viability_assay']
    treatment_data = [r for r in executor.collected_data if r['operation'] == 'treat']
    
    # Combine data
    dose_response = []
    for treat, viab in zip(treatment_data, viability_data):
        dose_response.append({
            "dose_uM": treat["dose_uM"],
            "viability": viab["viability"],
            "cell_count": viab["cell_count"]
        })
    
    df = pd.DataFrame(dose_response)
    print("\nDose-Response Results:")
    print(df.to_string(index=False))
    
    # Export
    df.to_csv("results/dose_response_data.csv", index=False)
    print("\n✓ Data exported to results/dose_response_data.csv")


def example_3_multi_passage_tracking():
    """
    Example 3: Track cells over multiple passages.
    """
    print("\n" + "="*60)
    print("Example 3: Multi-Passage Tracking")
    print("="*60)
    
    executor = SimulationExecutor(collect_data=True, simulation_speed=0.0)
    
    n_passages = 5
    workflow = []
    
    # Initial seed
    workflow.append(
        UnitOp(
            operation="seed",
            parameters={
                "vessel_id": "T75_P0",
                "cell_line": "HEK293T",
                "initial_count": 5e5,
                "capacity": 1e7
            }
        )
    )
    
    # Passage loop
    for p in range(n_passages):
        source = f"T75_P{p}"
        target = f"T75_P{p+1}"
        
        workflow.extend([
            UnitOp(
                operation="incubate",
                parameters={"minutes": 72 * 60, "temperature_c": 37.0}  # 3 days
            ),
            UnitOp(
                operation="viability_assay",
                parameters={"vessel_id": source}
            ),
            UnitOp(
                operation="passage",
                parameters={
                    "source_vessel": source,
                    "target_vessel": target,
                    "split_ratio": 4.0
                }
            )
        ])
    
    # Execute
    execution = executor.create_execution(workflow, name="Multi-Passage")
    result = executor.execute(execution.execution_id)
    
    print(f"\nExecution Status: {result.status}")
    
    # Extract passage data
    passage_data = [r for r in executor.collected_data if r['operation'] == 'passage']
    viability_data = [r for r in executor.collected_data if r['operation'] == 'viability_assay']
    
    tracking = []
    for i, (passage, viab) in enumerate(zip(passage_data, viability_data)):
        tracking.append({
            "passage_number": i,
            "cells_transferred": passage["cells_transferred"],
            "viability": passage["viability"],
            "pre_passage_viability": viab["viability"]
        })
    
    df = pd.DataFrame(tracking)
    print("\nPassage Tracking:")
    print(df.to_string(index=False))
    
    # Export
    df.to_csv("results/passage_tracking_data.csv", index=False)
    print("\n✓ Data exported to results/passage_tracking_data.csv")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Workflow Simulation Examples")
    print("="*60)
    
    # Run examples
    example_1_simple_passage_workflow()
    example_2_dose_response_experiment()
    example_3_multi_passage_tracking()
    
    print("\n" + "="*60)
    print("All examples completed successfully!")
    print("="*60)
    print("\nGenerated files:")
    print("  - results/simple_passage_data.json")
    print("  - results/dose_response_data.csv")
    print("  - results/passage_tracking_data.csv")
    print("\n")
