# dashboard_app/pages/tab_4_workflow.py
import streamlit as st
import pandas as pd
# Import necessary components from utils
from dashboard_app.utils import (
    init_automation_resources, 
    render_workflow_graph, 
    render_workflow_plotly, 
    Workflow
)

def render_workflow_visualizer(df, pricing):
    """Renders the content for the Workflow Visualizer tab."""
    st.header("Workflow Visualization")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.subheader("Configuration")
        
        # Initialize Resources (using the utility function)
        vessel_lib, inv, ops, builder = init_automation_resources()
        
        if builder is None:
            st.error("Cannot load workflow engine. Check configuration files.")
            return

        # Define available workflows
        workflow_options = {
            "POSH": lambda: builder.build_zombie_posh(),
        }
        
        all_options = workflow_options
        
        selected_option_name = st.selectbox("Select Workflow / Recipe", list(all_options.keys()))
        
        # Add visualization engine toggle
        viz_engine = st.radio(
            "Visualization",
            ["Interactive (Plotly)", "Static (Graphviz)"],
            index=0,
            horizontal=True
        )
        
        # Add detail level toggle (only for Graphviz)
        if "Graphviz" in viz_engine:
            detail_level = st.radio(
                "Detail Level",
                ["Process (High-level)", "Unit Operations (Detailed)"],
                index=0,
                horizontal=True
            )
            detail_mode = "process" if "Process" in detail_level else "unitop"
        
        if st.button("Render Graph"):
            # Generate Object
            obj_func = all_options[selected_option_name]
            result_obj = obj_func()
            
            # Determine what to render
            if isinstance(result_obj, Workflow):
                # Choose renderer based on selection
                if "Plotly" in viz_engine:
                    # Interactive Plotly visualization
                    fig = render_workflow_plotly(result_obj, detail_level="process")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    # Static Graphviz visualization
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
                # It's a single UnitOp (Recipe)
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