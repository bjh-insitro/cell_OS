# dashboard_app/pages/tab_4_workflow.py - Start of render_workflow_visualizer function

import streamlit as st
from dashboard_app.utils import (
    init_automation_resources, 
    render_workflow_graph, 
    render_workflow_plotly, 
    WorkflowBuilder, 
    Workflow
)

def render_workflow_visualizer(df, pricing):
    st.header("Workflow Visualization")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.subheader("Configuration")
        
        # Initialize Resources (using the utility function)
        vessel_lib, inv, ops, builder, inv_manager = init_automation_resources()
        
        if builder is None:
            st.error("Cannot load workflow engine. Check configuration files.")
            return

        # 1. Define Workflows by Category
        process_blocks = { # Tier 2
            "Master Cell Bank (MCB) Production": lambda: builder.build_master_cell_bank(),
            "Viral Titer (LV) Measurement": lambda: builder.build_viral_titer(), 
        }
        
        campaign_workflows = { # Tier 1
            "POSH Screening Campaign": lambda: builder.build_zombie_posh(),
        }
        
        # --- UI Selection Logic (Updated Labels) ---
        st.subheader("1. Choose Workflow Level")
        category = st.radio("Workflow Level", ["Process Block", "Campaign Workflow"], index=0, horizontal=True, key="viz_category_radio")

        if category == "Process Block":
            selected_workflows = process_blocks
            selection_key = "viz_process_block_select"
        else:
            selected_workflows = campaign_workflows
            selection_key = "viz_campaign_select"

        selected_option_name = st.selectbox(
            "2. Select Specific Workflow", 
            list(selected_workflows.keys()),
            key=selection_key
        )
        
        # 3. Visualization Engine Toggle
        viz_engine = st.radio(
            "Visualization",
            ["Interactive (Plotly)", "Static (Graphviz)"],
            index=0,
            horizontal=True
        )
        
        # 4. Detail Level Toggle (only for Graphviz)
        if "Graphviz" in viz_engine:
            detail_level = st.radio(
                "Detail Level",
                ["Process (High-level)", "Unit Operations (Detailed)"],
                index=0,
                horizontal=True
            )
            detail_mode = "process" if "Process" in detail_level else "unitop"
        else:
            detail_mode = "process" # Default for Plotly

        # 5. Render Button
        if st.button("Render Graph"):
            
            try: # <--- WRAPPING THE CORE LOGIC IN TRY BLOCK
                # Generate Object
                obj_func = selected_workflows[selected_option_name]
                result_obj = obj_func()
                
                # Determine what to render
                if isinstance(result_obj, Workflow):
                    # CHOOSE RENDERER: COMPLEX WORKFLOW
                    if "Plotly" in viz_engine:
                        fig = render_workflow_plotly(result_obj, detail_level="process")
                        sanitized_name = selected_option_name.replace(' ', '_')
                        st.plotly_chart(
                            fig,
                            use_container_width=True,
                            key=f"workflow_plot_{sanitized_name}"
                        )
                    else:
                        dot = render_workflow_graph(result_obj, title=selected_option_name, detail_level=detail_mode)
                        st.graphviz_chart(dot)
                    
                    # Calculate Total Costs
                    all_ops = result_obj.all_ops
                    total_mat = sum(op.material_cost_usd for op in all_ops)
                    total_inst = sum(op.instrument_cost_usd for op in all_ops)
                    
                    st.subheader("Workflow Cost Estimate")
                    st.metric("Total Material Cost", f"${total_mat:.2f}")
                    st.metric("Total Instrument Cost", f"${total_inst:.2f}")
                    
                    # Add expandable process details
                    st.subheader("Process Details")
                    for process in result_obj.processes:
                        with st.expander(f"📋 {process.name} ({len(process.ops)} operations)"):
                            for op in process.ops:
                                op_name = getattr(op, 'name', 'Unknown')
                                op_cost = op.material_cost_usd + op.instrument_cost_usd
                                st.write(f"- **{op_name}** (${op_cost:.2f})")
                                if hasattr(op, 'sub_steps') and op.sub_steps:
                                    st.caption(f"  └─ {len(op.sub_steps)} sub-steps")
                    
                else:
                    # HANDLE SIMPLE RECIPE (UNIT OP)
                    root_op = result_obj
                    if root_op.sub_steps:
                        recipe_to_render = root_op.sub_steps
                        st.info(f"Showing {len(recipe_to_render)} granular steps for {root_op.name}")
                    else:
                        recipe_to_render = [root_op]
                        
                    dot = render_workflow_graph(recipe_to_render, title=selected_option_name)
                    st.graphviz_chart(dot)
                    
                    st.subheader("Recipe Cost Estimate")
                    st.metric("Material Cost", f"${root_op.material_cost_usd:.2f}")
                    st.metric("Instrument Cost", f"${root_op.instrument_cost_usd:.2f}")
                
            except Exception as e:
                # CATCH AND DISPLAY THE ERROR, which was previously causing the SyntaxError 
                st.error(f"Error generating workflow: {e}")
