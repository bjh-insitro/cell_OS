import streamlit as st
import pandas as pd
import numpy as np
import yaml
import os
import altair as alt
from src.modeling import DoseResponseGP, DoseResponseGPConfig

st.set_page_config(page_title="cell_OS Dashboard", layout="wide")

st.title("🧬 cell_OS Mission Control")

# -------------------------------------------------------------------
# Sidebar: Configuration & Status
# -------------------------------------------------------------------
st.sidebar.header("Status")
if st.sidebar.button("Refresh Data"):
    st.rerun()

# Load Data
@st.cache_data
def load_data():
    history_path = "results/experiment_history.csv"
    if os.path.exists(history_path):
        df = pd.read_csv(history_path)
    else:
        df = pd.DataFrame()
        
    pricing_path = "data/raw/pricing.yaml"
    with open(pricing_path, 'r') as f:
        pricing = yaml.safe_load(f)
        
    return df, pricing

df, pricing = load_data()

# -------------------------------------------------------------------
# Tabs
# -------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["🚀 Mission Control", "🔬 Science", "💰 Economics", "🕸️ Workflow Visualizer"])

# -------------------------------------------------------------------
# Tab 1: Mission Control
# -------------------------------------------------------------------
with tab1:
    col1, col2, col3 = st.columns(3)
    
    # Calculate Metrics
    if not df.empty:
        total_spent = df["cost_usd"].sum() if "cost_usd" in df.columns else 0.0
        current_cycle = df["cycle"].max() if "cycle" in df.columns else 0
        n_experiments = len(df)
    else:
        total_spent = 0.0
        current_cycle = 0
        n_experiments = 0
        
    # Budget (Hardcoded initial for now, or read from log?)
    initial_budget = 5000.0
    remaining_budget = initial_budget - total_spent
    
    col1.metric("Budget Remaining", f"${remaining_budget:,.2f}", delta=f"-${total_spent:,.2f}")
    col2.metric("Current Cycle", f"{current_cycle}")
    col3.metric("Total Experiments", f"{n_experiments}")
    
    st.divider()
    
    st.subheader("Recent Activity")
    if not df.empty:
        st.dataframe(df.tail(10), use_container_width=True)
        
    st.subheader("Mission Log")
    log_path = "results/mission_log.md"
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            log_content = f.read()
        st.markdown(log_content)
    else:
        st.info("No mission log found.")

# -------------------------------------------------------------------
# Tab 2: Science
# -------------------------------------------------------------------
with tab2:
    st.header("Dose-Response Explorer")
    
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            cell_line = st.selectbox("Cell Line", df["cell_line"].unique())
        with col2:
            compound = st.selectbox("Compound", df["compound"].unique())
            
        # Filter Data
        mask = (df["cell_line"] == cell_line) & (df["compound"] == compound)
        df_slice = df[mask].copy()
        
        if not df_slice.empty:
            # Plot Data
            chart = alt.Chart(df_slice).mark_circle(size=60).encode(
                x=alt.X("dose_uM", scale=alt.Scale(type="log")),
                y=alt.Y("viability", type="quantitative"),
                color="cycle:O",
                tooltip=[
                    alt.Tooltip("dose_uM", type="quantitative"),
                    alt.Tooltip("viability", type="quantitative"),
                    alt.Tooltip("cycle", type="ordinal")
                ]
            ).interactive()
            
            # Fit GP (On the fly!)
            try:
                # Filter out zero doses for log scale
                df_fit = df_slice[df_slice["dose_uM"] > 0].copy()
                if len(df_fit) > 0:
                    gp = DoseResponseGP.from_dataframe(
                        df_fit, cell_line, compound, time_h=24, viability_col="viability"
                    )
                    grid = gp.predict_on_grid(num_points=100)
                    
                    df_grid = pd.DataFrame(grid)
                    
                    line = alt.Chart(df_grid).mark_line(color='red').encode(
                        x=alt.X("dose_uM", scale=alt.Scale(type="log")),
                        y=alt.Y("mean", type="quantitative")
                    )
                    
                    # Pre-calc bounds
                    df_grid["upper"] = df_grid["mean"] + df_grid["std"]
                    df_grid["lower"] = df_grid["mean"] - df_grid["std"]
                    
                    band = alt.Chart(df_grid).mark_area(opacity=0.2, color='red').encode(
                        x=alt.X("dose_uM", scale=alt.Scale(type="log")),
                        y=alt.Y("lower", type="quantitative"),
                        y2=alt.Y2("upper")
                    )
                    
                    st.altair_chart(chart + line + band, use_container_width=True)
                else:
                    st.altair_chart(chart, use_container_width=True)
                    st.warning("Not enough positive dose data to fit GP.")
                    
            except Exception as e:
                st.error(f"GP Fit Failed: {e}")
                st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No data for this selection.")
    else:
        st.info("No experimental data yet.")

# -------------------------------------------------------------------
# Tab 3: Economics
# -------------------------------------------------------------------
with tab3:
    st.header("Financials")
    
    if not df.empty and "cost_usd" in df.columns:
        # Cumulative Spend
        df["cumulative_cost"] = df["cost_usd"].cumsum()
        st.line_chart(df.reset_index(), x="index", y="cumulative_cost")
    
    st.header("Inventory Levels")
    # We don't have a live inventory file that updates yet (inventory.py is in-memory).
    # But we can show the catalog prices.
    
    items = []
    for item_id, data in pricing.get("items", {}).items():
        items.append({
            "Name": data.get("name"),
            "Price": data.get("unit_price_usd"),
            "Unit": data.get("logical_unit")
        })
    
    st.dataframe(pd.DataFrame(items), use_container_width=True)
    st.info("Live inventory tracking requires persisting the Inventory state to a file (TODO).")

# -------------------------------------------------------------------
# Tab 4: Workflow Visualizer
# -------------------------------------------------------------------
from src.workflow_renderer import render_workflow_graph
from src.workflow_renderer_plotly import render_workflow_plotly
from src.unit_ops import ParametricOps, VesselLibrary
from src.inventory import Inventory
from src.workflows import WorkflowBuilder, Workflow

with tab4:
    st.header("Workflow Visualization")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.subheader("Configuration")
        
        # Initialize Resources
        try:
            vessel_lib = VesselLibrary("data/raw/vessels.yaml")
            inv = Inventory("data/raw/pricing.yaml")
            ops = ParametricOps(vessel_lib, inv)
            builder = WorkflowBuilder(ops)
            
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
                
        except Exception as e:
            st.error(f"Error initializing workflow engine: {e}")
            st.warning("Ensure 'data/raw/vessels.yaml' and 'data/raw/pricing.yaml' exist.")

