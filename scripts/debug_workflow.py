import sys
import os
import json

# Add project root to path to enable module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import necessary components (assuming they are correctly defined in your package)
from dashboard_app.utils import init_automation_resources

def print_workflow_steps(workflow_name="Master Cell Bank (MCB) Production"):
    """
    Initializes the automation resources and prints the steps of a chosen workflow.
    """
    print(f"\n--- DEBUGGING WORKFLOW: {workflow_name} ---")
    
    # Initialize resources (This relies on the cached success of your dashboard initialization)
    vessel_lib, inv, ops, builder = init_automation_resources()
    
    if builder is None:
        print("ERROR: Could not initialize WorkflowBuilder. Check data/raw/vessels.yaml.")
        return

    # 1. Select the Workflow Builder Function
    if workflow_name == "Master Cell Bank (MCB) Production":
        workflow_func = builder.build_master_cell_bank
    elif workflow_name == "POSH Screening Campaign":
        workflow_func = builder.build_zombie_posh
    else:
        print(f"Error: Workflow '{workflow_name}' not recognized.")
        return

    # 2. Build the Workflow Object
    try:
        workflow = workflow_func()
    except Exception as e:
        print(f"ERROR: Workflow construction failed: {e}")
        return

    # 3. Print Granular Steps (Tier 3 UOs)
    
    # We only care about the single process block inside the MCB workflow
    for i, process in enumerate(workflow.processes):
        print(f"\n### PROCESS {i+1}: {process.name} ###")
        
        # Iterate through the top-level operations (UO) that make up this process
        for op in process.ops:
            print(f"\n[UO] {op.name} (Cost: ${op.material_cost_usd:.2f})")
            
            # If the operation is a composite (like op_thaw or op_passage), print its sub_steps
            if hasattr(op, 'sub_steps') and op.sub_steps:
                print("--- Sub-Steps (Granular Execution) ---")
                for step in op.sub_steps:
                    # Print granular step details, including material if identifiable
                    material_id = "N/A"
                    if hasattr(step, 'kwargs') and 'media' in step.kwargs:
                         material_id = step.kwargs['media']
                    elif hasattr(step, 'kwargs') and 'reagent' in step.kwargs:
                         material_id = step.kwargs['reagent']
                    
                    print(f"  -> {step.name: <30} | Cost: ${step.material_cost_usd:.4f} | Material: {material_id}")
                print("--------------------------------------")


if __name__ == "__main__":
    # Run the debug script for the MCB Process Block
    print_workflow_steps("Master Cell Bank (MCB) Production")