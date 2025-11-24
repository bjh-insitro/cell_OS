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
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🚀 Mission Control", 
    "🔬 Science", 
    "💰 Economics", 
    "🕸️ Workflow Visualizer", 
    "🧭 POSH Decision Assistant",
    "🧪 POSH Screen Designer"
])

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

# -------------------------------------------------------------------
# Tab 5: POSH Decision Assistant
# -------------------------------------------------------------------
from src.posh_decision_engine import (
    POSHDecisionEngine, 
    UserRequirements, 
    POSHProtocol, 
    AutomationLevel
)

with tab5:
    st.header("🧭 POSH Decision Assistant")
    st.markdown("Answer a few questions to get a personalized POSH configuration recommendation.")
    
    engine = POSHDecisionEngine()
    
    # User Input Form
    with st.form("posh_requirements"):
        st.subheader("Experimental Requirements")
        
        col1, col2 = st.columns(2)
        
        with col1:
            num_plates = st.number_input(
                "Number of Plates",
                min_value=1,
                max_value=500,
                value=10,
                help="How many plates do you plan to run?"
            )
            
            budget_usd = st.number_input(
                "Budget (USD)",
                min_value=100,
                max_value=1000000,
                value=10000,
                step=1000,
                help="Total budget for this experiment"
            )
            
            timeline_weeks = st.number_input(
                "Timeline (weeks)",
                min_value=1,
                max_value=52,
                value=4,
                help="How many weeks until you need results?"
            )
        
        with col2:
            has_automation = st.checkbox(
                "Access to Automation Equipment",
                value=False,
                help="Do you have liquid handlers or automated systems?"
            )
            
            needs_multimodal = st.checkbox(
                "Need Multimodal Imaging",
                value=False,
                help="Require HCR FISH + IBEX immunofluorescence?"
            )
            
            tissue_samples = st.checkbox(
                "Working with Tissue Samples",
                value=False,
                help="Are you processing tissue sections (vs cultured cells)?"
            )
        
        submitted = st.form_submit_button("Get Recommendation", type="primary")
    
    if submitted:
        # Create requirements
        req = UserRequirements(
            num_plates=num_plates,
            budget_usd=budget_usd,
            timeline_weeks=timeline_weeks,
            has_automation=has_automation,
            needs_multimodal=needs_multimodal,
            tissue_samples=tissue_samples
        )
        
        # Get recommendation
        rec = engine.recommend(req)
        
        st.divider()
        st.subheader("📋 Recommended Configuration")
        
        # Display recommendation in columns
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Protocol", rec.protocol.value.title())
        with col2:
            st.metric("Multimodal", "Enabled" if rec.multimodal else "Disabled")
        with col3:
            st.metric("Automation", rec.automation.value.replace("_", " ").title())
        
        st.divider()
        
        # Cost and Time Estimates
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                "Estimated Total Cost",
                f"${rec.estimated_cost_usd:,.0f}",
                delta=f"${rec.estimated_cost_usd - budget_usd:,.0f}" if rec.estimated_cost_usd > budget_usd else None,
                delta_color="inverse"
            )
        
        with col2:
            st.metric(
                "Estimated Timeline",
                f"{rec.estimated_time_weeks:.1f} weeks",
                delta=f"{rec.estimated_time_weeks - timeline_weeks:.1f} weeks" if rec.estimated_time_weeks > timeline_weeks else None,
                delta_color="inverse"
            )
        
        # Justification
        st.subheader("💡 Justification")
        st.markdown(rec.justification)
        
        # Warnings
        if rec.warnings:
            st.subheader("⚠️ Warnings")
            for warning in rec.warnings:
                st.warning(warning)
        
        # Alternatives
        if rec.alternatives:
            st.subheader("🔄 Consider These Alternatives")
            for alt in rec.alternatives:
                st.info(f"• {alt}")
        
        # Comparison Table
        st.divider()
        st.subheader("📊 Configuration Comparison")
        
        configs = engine.compare_configurations(req)
        
        comparison_data = []
        for config_name, config_rec in configs.items():
            comparison_data.append({
                "Configuration": config_name.title(),
                "Protocol": config_rec.protocol.value.title(),
                "Multimodal": "Yes" if config_rec.multimodal else "No",
                "Automation": config_rec.automation.value.replace("_", " ").title(),
                "Cost (USD)": f"${config_rec.estimated_cost_usd:,.0f}",
                "Time (weeks)": f"{config_rec.estimated_time_weeks:.1f}"
            })
        
        df_comparison = pd.DataFrame(comparison_data)
        st.dataframe(df_comparison, use_container_width=True, hide_index=True)

# -------------------------------------------------------------------
# Tab 6: POSH Screen Designer
# -------------------------------------------------------------------
from src.posh_screen_designer import create_screen_design, CELL_TYPE_PARAMS

with tab6:
    st.header("🧪 POSH Screen Designer")
    st.markdown("Calculate experimental parameters for your POSH screen based on library size and cell type.")
    
    with st.form("screen_design_form"):
        st.subheader("Library Specification")
        
        col1, col2 = st.columns(2)
        
        with col1:
            library_name = st.text_input("Library Name", value="My_Library")
            num_genes = st.number_input(
                "Number of Genes",
                min_value=10,
                max_value=25000,
                value=1000,
                help="Total number of genes in your library"
            )
            grnas_per_gene = st.number_input(
                "gRNAs per Gene",
                min_value=1,
                max_value=10,
                value=4,
                help="Typical: 4 for knockout, 3-5 for CRISPRi"
            )
        
        with col2:
            viral_titer = st.number_input(
                "Viral Titer (TU/mL)",
                min_value=1e5,
                max_value=1e9,
                value=1e7,
                format="%.2e",
                help="Functional titer of your viral stock"
            )
            
            cell_type = st.selectbox(
                "Cell Type",
                options=list(CELL_TYPE_PARAMS.keys()),
                help="Select your cell type (barcode efficiency varies)"
            )
            
            target_cells = st.slider(
                "Target Cells per gRNA",
                min_value=250,
                max_value=2000,
                value=750,
                step=50,
                help="Recommended: 500-1000 cells per gRNA"
            )
        
        calculate = st.form_submit_button("Calculate Design", type="primary")
    
    if calculate:
        # Create design
        design = create_screen_design(
            library_name=library_name,
            num_genes=num_genes,
            cell_type=cell_type,
            viral_titer=viral_titer,
            target_cells_per_grna=target_cells,
            moi=0.3  # Fixed at 0.3 as per user spec
        )
        
        # Override grnas_per_gene if user changed it
        design.library.grnas_per_gene = grnas_per_gene
        design._calculate()  # Recalculate with new value
        
        st.divider()
        st.subheader("📊 Experimental Design")
        
        # Key Metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total gRNAs", f"{design.library.total_grnas:,}")
        col2.metric("Transduction Cells", f"{design.transduction_cells_needed:,}")
        col3.metric("Screening Plates", design.screening_plates)
        col4.metric("Estimated Cost", f"${design.estimated_cost_usd:,.0f}")
        
        st.divider()
        
        # Detailed Breakdown
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🧬 Transduction")
            st.metric("Cells Needed", f"{design.transduction_cells_needed:,}")
            st.metric("MOI", design.moi)
            st.metric("Representation", f"{design.representation}×")
            st.metric("Viral Volume", f"{design.viral_volume_ml:.2f} mL")
            st.metric("Transduction Plates (6-well)", design.transduction_plates)
        
        with col2:
            st.subheader("🔬 Screening")
            st.metric("Target Cells (Raw)", f"{design.total_target_cells:,}")
            st.metric("Barcode Efficiency", f"{design.cell_type.barcode_efficiency * 100:.0f}%")
            st.metric("Cells Needed (Adjusted)", f"{design.cells_needed_for_barcoding:,}")
            st.metric("Screening Plates (6-well)", design.screening_plates)
            st.metric("Cells per gRNA", design.target_cells_per_grna)
        
        st.divider()
        
        # Post-Selection
        st.subheader("🧊 Post-Selection & Banking")
        col1, col2 = st.columns(2)
        col1.metric("Expected Cells (50% survival)", f"{design.post_selection_cells:,}")
        col2.metric("Cryo Vials (1M cells/vial)", design.cryo_vials_needed)
        
        # Protocol Summary
        st.divider()
        st.subheader("📋 Protocol Summary")
        with st.expander("View Full Protocol", expanded=False):
            st.markdown(design.get_protocol_summary())
        
        # Export button
        if st.button("📄 Export Protocol to Markdown"):
            protocol_text = design.get_protocol_summary()
            st.download_button(
                label="Download Protocol",
                data=protocol_text,
                file_name=f"{library_name}_POSH_protocol.md",
                mime="text/markdown"
            )

