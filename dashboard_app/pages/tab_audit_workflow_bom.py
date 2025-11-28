# dashboard_app/pages/tab_audit_workflow_bom.py

import streamlit as st
import pandas as pd
import re
from dashboard_app.utils import (
    init_automation_resources, 
    Workflow 
)

def extract_consumable_from_step(step):
    """
    Enhanced consumable extraction logic.
    Parses step names and attributes to identify specific consumables.
    """
    material_id = "N/A"
    
    # Check if there's a material cost
    if not (hasattr(step, 'material_cost_usd') and step.material_cost_usd > 0):
        return material_id
    
    step_name = step.name.lower() if hasattr(step, 'name') else ""
    
    # Pattern matching for common consumables
    consumable_patterns = {
        r'tube.*50.*ml': 'tube_50ml_conical',
        r'tube.*15.*ml': 'tube_15ml_conical',
        r'pipette.*25.*ml': 'pipette_25ml',
        r'pipette.*10.*ml': 'pipette_10ml',
        r'pipette.*5.*ml': 'pipette_5ml',
        r'pipette.*2.*ml': 'pipette_2ml',
        r'tip.*1000.*ul|tip.*1.*ml': 'tip_1000ul_lr',
        r'tip.*200.*ul': 'tip_200ul_lr',
        r'mtesr|media': 'mtesr_plus_kit',
        r'laminin': 'laminin_521',
        r'dpbs|pbs': 'dpbs',
        r'accutase': 'accutase',
        r'trypsin': 'trypsin_edta',
        r'flask.*t75': 'flask_t75',
        r'flask.*t175': 'flask_t175',
        r'plate.*96': 'plate_96well_tc',
        r'vial|cryovial': 'cryovial_1_8ml',
    }
    
    for pattern, consumable_id in consumable_patterns.items():
        if re.search(pattern, step_name):
            material_id = consumable_id
            break
    
    # If still N/A, use generic categorization
    if material_id == "N/A":
        if 'dispense' in step_name or 'aliquot' in step_name:
            material_id = "Reagent/Media (unspecified)"
        elif 'vessel' in step_name or 'flask' in step_name or 'plate' in step_name:
            material_id = "Vessel/Labware"
        else:
            material_id = "Consumable (unspecified)"
    
    return material_id


def render_workflow_bom_audit(df, pricing):
    st.header("🔍 Workflow Bill of Materials (BOM) Audit")
    st.markdown(
        "Select a **Campaign Workflow** (Tier 1), **Process Block** (Tier 2), or **Parametric Unit Operation** (Tier 3) to audit."
    )

    # 1. Initialize Resources 
    vessel_lib, inv, ops, builder = init_automation_resources()
    
    if builder is None:
        return 

    # 2. Define Workflows by Category (Process Blocks vs. Campaigns vs. Unit Ops)
    process_blocks = { # Tier 2
        "Master Cell Bank (MCB) Production": lambda: builder.build_master_cell_bank(),
        "Viral Titer (LV) Measurement": lambda: builder.build_viral_titer(), 
    }
    
    campaign_workflows = { # Tier 1
        "POSH Screening Campaign": lambda: builder.build_zombie_posh(),
    }
    
    # Tier 3: Individual Parametric Unit Operations
    parametric_operations = {
        "op_thaw (Thaw Cells into Flask)": lambda: ops.op_thaw("flask_t75", cell_line="U2OS"),
        "op_passage (Cell Passage/Expansion)": lambda: ops.op_passage("flask_t75", ratio=3, dissociation_method="accutase"),
        "op_feed (Feed Cells with Media)": lambda: ops.op_feed("flask_t75", media="mtesr_plus_kit", supplements=["puromycin"]),
        "op_transduce (Lentiviral Transduction)": lambda: ops.op_transduce("flask_t75", virus_vol_ul=10.0, method="spinoculation"),
        "op_coat (Coat Vessel with ECM)": lambda: ops.op_coat("flask_t75", agents=["laminin_521"]),
        "op_transfect (Transfect Cells)": lambda: ops.op_transfect("flask_t175", method="pei"),
        "op_harvest (Harvest Cells)": lambda: ops.op_harvest("flask_t75", dissociation_method="accutase"),
        "op_freeze (Freeze Cell Vials)": lambda: ops.op_freeze(num_vials=10, freezing_media="cryostor"),
    }
    
    # --- UI Selection Logic (Updated Labels) ---
    st.subheader("1. Choose Workflow Level")
    # Use Radio to select the main tier
    category = st.radio(
        "Workflow Level", 
        ["Parametric Unit Operation", "Process Block", "Campaign Workflow"], 
        index=0, 
        horizontal=True, 
        key="audit_category_radio"
    )

    if category == "Process Block":
        selected_workflows = process_blocks
        selection_key = "audit_process_block_select"
        label = "2. Select Process Block"
    elif category == "Campaign Workflow":
        selected_workflows = campaign_workflows
        selection_key = "audit_campaign_select"
        label = "2. Select Campaign Workflow"
    else:  # Parametric Unit Operation
        selected_workflows = parametric_operations
        selection_key = "audit_unit_op_select"
        label = "2. Select Parametric Unit Operation"

    selected_option_name = st.selectbox(
        label, 
        list(selected_workflows.keys()),
        key=selection_key
    )
    
    # Add view mode selection (only for workflows, not individual ops)
    if category in ["Process Block", "Campaign Workflow"]:
        view_mode = st.radio(
            "3. Select View Mode",
            ["Detailed (All Sub-Steps)", "Grouped by Parametric Operation"],
            index=0,
            horizontal=True,
            key="view_mode_radio"
        )
    else:
        view_mode = "Detailed (All Sub-Steps)"  # Default for individual ops
    
    # 3. Determine function and proceed
    obj_func = selected_workflows[selected_option_name]
    
    if st.button("Generate Step-by-Step BOM Audit", type="primary"):
        st.subheader(f"Audit Results for: {selected_option_name}")
        
        try:
            # Generate Object
            result_obj = obj_func()
            
            # Import UnitOp for type checking
            from cell_os.unit_ops import UnitOp
            
            # Handle individual UnitOp (Parametric Operation)
            if isinstance(result_obj, UnitOp):
                st.info(f"🔧 Auditing Parametric Unit Operation: **{result_obj.name}**")
                
                # Get sub-steps
                if hasattr(result_obj, 'sub_steps') and result_obj.sub_steps:
                    sub_steps = result_obj.sub_steps
                else:
                    sub_steps = [result_obj]
                
                # Build table data
                all_steps = []
                for idx, step in enumerate(sub_steps, 1):
                    material_id = extract_consumable_from_step(step)
                    all_steps.append({
                        "Step #": idx,
                        "Sub-Step": step.name,
                        "Consumable_ID": material_id,
                        "Material Cost ($)": f"${step.material_cost_usd:.4f}",
                        "Instrument Cost ($)": f"${step.instrument_cost_usd:.4f}",
                        "Total Cost ($)": f"${step.material_cost_usd + step.instrument_cost_usd:.4f}",
                        "Automation": step.automation_fit,
                        "Time (min)": step.time_score
                    })
                
                df_audit = pd.DataFrame(all_steps)
                st.dataframe(df_audit, use_container_width=True)
                
                # Summary statistics
                st.subheader("📊 Operation Summary")
                col1, col2, col3, col4 = st.columns(4)
                
                total_material = df_audit['Material Cost ($)'].apply(lambda x: float(x.replace('$', ''))).sum()
                total_instrument = df_audit['Instrument Cost ($)'].apply(lambda x: float(x.replace('$', ''))).sum()
                total_cost = total_material + total_instrument
                
                col1.metric("Total Material Cost", f"${total_material:.4f}")
                col2.metric("Total Instrument Cost", f"${total_instrument:.4f}")
                col3.metric("Total Operation Cost", f"${total_cost:.4f}")
                col4.metric("Number of Sub-Steps", len(sub_steps))
                
                # Show operation metadata
                with st.expander("📋 Operation Metadata"):
                    st.write(f"**Operation ID:** `{result_obj.uo_id}`")
                    st.write(f"**Layer:** {result_obj.layer}")
                    st.write(f"**Category:** {result_obj.category}")
                    st.write(f"**Instrument:** {result_obj.instrument}")
                    st.write(f"**Automation Fit:** {result_obj.automation_fit}/10")
                    st.write(f"**Failure Risk:** {result_obj.failure_risk}/10")
                    st.write(f"**Staff Attention:** {result_obj.staff_attention}/10")
                
            # Handle Workflow objects
            elif isinstance(result_obj, Workflow):
                
                if view_mode == "Detailed (All Sub-Steps)":
                    # DETAILED VIEW: Show all sub-steps
                    all_steps = []
                    
                    for process in result_obj.processes:
                        for op in process.ops:
                            
                            if hasattr(op, 'sub_steps') and op.sub_steps:
                                granular_steps = op.sub_steps
                            else:
                                granular_steps = [op]
                                
                            for step in granular_steps:
                                material_id = extract_consumable_from_step(step)

                                all_steps.append({
                                    "Process": process.name,
                                    "Parametric UnitOp": op.name,
                                    "Sub-Step": step.name,
                                    "Consumable_ID": material_id,
                                    "Material Cost ($)": f"${step.material_cost_usd:.4f}",
                                    "Instrument Cost ($)": f"${step.instrument_cost_usd:.4f}",
                                    "Total Cost ($)": f"${step.material_cost_usd + step.instrument_cost_usd:.4f}",
                                    "Automation": step.automation_fit,
                                    "Time (min)": step.time_score
                                })

                    df_audit = pd.DataFrame(all_steps)
                    st.dataframe(df_audit, use_container_width=True)
                    
                    # Summary statistics
                    st.subheader("📊 Cost Summary")
                    col1, col2, col3 = st.columns(3)
                    
                    total_material = df_audit['Material Cost ($)'].apply(lambda x: float(x.replace('$', ''))).sum()
                    total_instrument = df_audit['Instrument Cost ($)'].apply(lambda x: float(x.replace('$', ''))).sum()
                    total_cost = total_material + total_instrument
                    
                    col1.metric("Total Material Cost", f"${total_material:.2f}")
                    col2.metric("Total Instrument Cost", f"${total_instrument:.2f}")
                    col3.metric("Total Workflow Cost", f"${total_cost:.2f}")
                    
                else:
                    # GROUPED VIEW: Group by parametric operation
                    st.info("📦 Showing parametric operations with expandable sub-step details")
                    
                    for process in result_obj.processes:
                        st.markdown(f"### Process: {process.name}")
                        
                        for op in process.ops:
                            # Calculate totals for this operation
                            if hasattr(op, 'sub_steps') and op.sub_steps:
                                sub_steps = op.sub_steps
                                total_mat = sum(s.material_cost_usd for s in sub_steps)
                                total_inst = sum(s.instrument_cost_usd for s in sub_steps)
                            else:
                                sub_steps = [op]
                                total_mat = op.material_cost_usd
                                total_inst = op.instrument_cost_usd
                            
                            total_op_cost = total_mat + total_inst
                            
                            # Create expander for each parametric operation
                            with st.expander(
                                f"**{op.name}** | 💰 ${total_op_cost:.2f} | ⏱️ {op.time_score} min | 🔧 {len(sub_steps)} sub-steps",
                                expanded=False
                            ):
                                # Show sub-steps in a table
                                sub_step_data = []
                                for step in sub_steps:
                                    material_id = extract_consumable_from_step(step)
                                    sub_step_data.append({
                                        "Step": step.name,
                                        "Consumable": material_id,
                                        "Material $": f"${step.material_cost_usd:.4f}",
                                        "Instrument $": f"${step.instrument_cost_usd:.4f}",
                                        "Total $": f"${step.material_cost_usd + step.instrument_cost_usd:.4f}",
                                    })
                                
                                df_sub = pd.DataFrame(sub_step_data)
                                st.dataframe(df_sub, use_container_width=True)
                                
                                # Show operation summary
                                st.caption(f"**Operation Summary:** Material: ${total_mat:.4f} | Instrument: ${total_inst:.4f} | Total: ${total_op_cost:.4f}")
                
                st.caption(
                    "💡 **Note:** Cost values are derived from the Unit Cost ($/mL or $/unit) stored in the SQLite Inventory Database."
                )
            else:
                st.warning(f"Unexpected object type: {type(result_obj)}. Expected Workflow or UnitOp.")
        
        except Exception as e:
            st.error(f"❌ WORKFLOW GENERATION ERROR: The selected workflow crashed during execution. Details: {e}")
            import traceback
            with st.expander("Show Error Details"):
                st.code(traceback.format_exc())


    st.caption("⚙️ To run this audit, ensure you have successfully run `python scripts/migrate_pricing.py` to populate the database.")