# dashboard_app/pages/tab_audit_workflow_bom.py

import streamlit as st
import pandas as pd
from dashboard_app.utils import (
    init_automation_resources, 
    Workflow 
)

def render_workflow_bom_audit(df, pricing):
    st.header("🔍 Workflow Bill of Materials (BOM) Audit")
    st.markdown(
        "Select a **Campaign Workflow** (Tier 1) or a **Process Block** (Tier 2) to see all consuming Unit Operations (Tier 3)."
    )

    # 1. Initialize Resources 
    vessel_lib, inv, ops, builder = init_automation_resources()
    
    if builder is None:
        return 

    # 2. Define Workflows by Category (Process Blocks vs. Campaigns)
    process_blocks = { # Tier 2
        "Master Cell Bank (MCB) Production": lambda: builder.build_master_cell_bank(),
        "Viral Titer (LV) Measurement": lambda: builder.build_viral_titer(), 
    }
    
    campaign_workflows = { # Tier 1
        "POSH Screening Campaign": lambda: builder.build_zombie_posh(),
    }
    
    # --- UI Selection Logic (Updated Labels) ---
    st.subheader("1. Choose Workflow Level")
    # Use Radio to select the main tier
    category = st.radio("Workflow Level", ["Process Block", "Campaign Workflow"], index=0, horizontal=True, key="audit_category_radio")

    if category == "Process Block":
        selected_workflows = process_blocks
        selection_key = "audit_process_block_select"
    else:
        selected_workflows = campaign_workflows
        selection_key = "audit_campaign_select"

    selected_option_name = st.selectbox(
        "2. Select Specific Workflow", 
        list(selected_workflows.keys()),
        key=selection_key
    )
    
    # 3. Determine function and proceed
    obj_func = selected_workflows[selected_option_name]
    
    if st.button("Generate Step-by-Step BOM Audit", type="primary"):
        st.subheader(f"Audit Results for: {selected_option_name}")
        
        try:
            # Generate Object
            result_obj = obj_func()
            
            if isinstance(result_obj, Workflow):
                # Process Workflow Object
                all_steps = []
                
                # --- Iterate through Processes, Operations, and Sub-Steps (Granular UOs) ---
                for process in result_obj.processes:
                    for op in process.ops:
                        
                        if hasattr(op, 'sub_steps') and op.sub_steps:
                            granular_steps = op.sub_steps
                        else:
                            granular_steps = [op]
                            
                        for step in granular_steps:
                            
                            # Attempt to identify the consumable item
                            material_id = "N/A"
                            if hasattr(step, 'material_cost_usd') and step.material_cost_usd > 0:
                                # Heuristic to pull the material ID
                                if hasattr(step, 'kwargs') and any(arg in step.kwargs for arg in ['material_id', 'reagent', 'media']):
                                    material_id = step.kwargs.get('material_id') or step.kwargs.get('reagent') or step.kwargs.get('media')
                                elif hasattr(step, 'name') and ('dispense' in step.name.lower() or 'add' in step.name.lower()):
                                    material_id = "General Consumables"
                                else:
                                    material_id = "Vessel/Fixed Cost"


                            all_steps.append({
                                "Process": process.name,
                                "UnitOp": op.name,
                                "Step_Name": step.name,
                                "Consumable_ID": material_id,
                                "Material Cost ($)": f"${step.material_cost_usd:.4f}",
                                "Instrument Cost ($)": f"${step.instrument_cost_usd:.4f}",
                                "Total Step Cost ($)": f"${step.material_cost_usd + step.instrument_cost_usd:.4f}",
                                "Automation_Fit": step.automation_fit,
                                "Time (min)": step.time_score
                            })

                df_audit = pd.DataFrame(all_steps)
                
                st.dataframe(df_audit, use_container_width=True)
                
                st.caption(
                    "Note: Cost values are derived from the Unit Cost ($/mL or $/unit) stored in the SQLite Inventory Database."
                )
            else:
                st.warning(f"Workflow '{selected_option_name}' is not a composite workflow (no granular steps found).")
        
        except Exception as e:
            st.error(f"WORKFLOW GENERATION ERROR: The selected workflow crashed during execution. Details: {e}")
            # st.code(traceback.format_exc()) 


    st.caption("To run this audit, ensure you have successfully run `python scripts/migrate_pricing.py` to populate the database.")