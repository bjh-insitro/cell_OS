import streamlit as st
import pandas as pd
import numpy as np
import yaml
import os
import altair as alt
from cell_os.modeling import DoseResponseGP, DoseResponseGPConfig

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
        try:
            # Try to read with error handling for malformed CSV
            df = pd.read_csv(history_path, on_bad_lines='skip')
        except Exception as e:
            st.warning(f"Could not load experiment history: {e}")
            df = pd.DataFrame()
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
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "🚀 Mission Control", 
    "🔬 Science", 
    "💰 Economics", 
    "🕸️ Workflow Visualizer", 
    "🧭 POSH Decision Assistant",
    "🧪 POSH Screen Designer",
    "📊 Campaign Reports",
    "🧮 Budget Calculator"
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
from cell_os.workflow_renderer import render_workflow_graph
from cell_os.workflow_renderer_plotly import render_workflow_plotly
from cell_os.unit_ops import ParametricOps, VesselLibrary
from cell_os.inventory import Inventory
from cell_os.workflows import WorkflowBuilder, Workflow

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
from cell_os.posh_decision_engine import (
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
from cell_os.posh_scenario import POSHScenario
from cell_os.posh_screen_design import run_posh_screen_design
from cell_os.posh_lv_moi import (
    fit_lv_transduction_model,
    LVTitrationResult,
    ScreenSimulator,
    ScreenConfig
)
from cell_os.posh_viz import (
    plot_library_composition,
    plot_titration_curve,
    plot_titer_posterior,
    plot_risk_assessment,
    plot_cost_breakdown
)
from cell_os.lab_world_model import LabWorldModel

with tab6:
    st.header("🧪 POSH Screen Designer")
    st.markdown("Design a complete POSH screen using the autonomous library design and LV modeling agents.")
    
    # Scenario Selection
    st.subheader("1. Select or Create Scenario")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        scenario_mode = st.radio(
            "Scenario Source",
            ["Load from YAML", "Create Custom"],
            horizontal=True
        )
    
    scenario = None
    
    if scenario_mode == "Load from YAML":
        # List available scenarios
        import glob
        scenario_files = glob.glob("data/scenarios/*.yaml")
        
        if scenario_files:
            selected_file = st.selectbox(
                "Select Scenario",
                scenario_files,
                format_func=lambda x: x.split("/")[-1]
            )
            
            if st.button("Load Scenario"):
                try:
                    scenario = POSHScenario.from_yaml(selected_file)
                    st.success(f"Loaded scenario: {scenario.name}")
                except Exception as e:
                    st.error(f"Failed to load scenario: {e}")
        else:
            st.warning("No scenario files found in data/scenarios/")
    
    else:  # Create Custom
        with st.form("custom_scenario"):
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Scenario Name", value="Custom_Screen")
                genes = st.number_input("Number of Genes", min_value=10, max_value=25000, value=1000)
                guides_per_gene = st.number_input("Guides per Gene", min_value=1, max_value=10, value=4)
                cell_lines_input = st.text_input("Cell Lines (comma-separated)", value="U2OS,A549,HepG2")
            
            with col2:
                moi_target = st.number_input("Target MOI", min_value=0.1, max_value=2.0, value=0.3, step=0.1)
                coverage = st.number_input("Coverage (cells/gene/bank)", min_value=100, max_value=5000, value=1000)
                budget = st.number_input("Budget (USD)", min_value=1000, max_value=1000000, value=50000, step=1000)
            
            if st.form_submit_button("Create Scenario"):
                cell_lines = [cl.strip() for cl in cell_lines_input.split(",")]
                scenario = POSHScenario(
                    name=name,
                    cell_lines=cell_lines,
                    genes=genes,
                    guides_per_gene=guides_per_gene,
                    coverage_cells_per_gene_per_bank=coverage,
                    banks_per_line=1,
                    moi_target=moi_target,
                    moi_tolerance=0.05,
                    viability_min=0.7,
                    segmentation_min=0.8,
                    stress_signal_min=2.0,
                    budget_max=budget
                )
                st.success(f"Created scenario: {scenario.name}")
    
    # Design Screen
    if scenario is not None:
        st.divider()
        st.subheader("2. Design Library")
        
        if st.button("Run Library Design", type="primary"):
            with st.spinner("Designing library..."):
                try:
                    world = LabWorldModel.empty()
                    result = run_posh_screen_design(world, scenario)
                    
                    st.session_state['posh_result'] = result
                    st.success("Library design complete!")
                except Exception as e:
                    st.error(f"Design failed: {e}")
                    import traceback
                    st.code(traceback.format_exc())
    
    # Display Results
    if 'posh_result' in st.session_state:
        result = st.session_state['posh_result']
        
        st.divider()
        st.subheader("📊 Design Results")
        
        # Key Metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Genes", f"{result.library.num_genes:,}")
        col2.metric("Total Guides", f"{len(result.library.df):,}")
        col3.metric("Guides/Gene", result.library.guides_per_gene_actual)
        col4.metric("Cell Lines", len(result.scenario.cell_lines))
        
        # Library Composition
        st.subheader("Library Composition")
        try:
            chart = plot_library_composition(result.library)
            st.altair_chart(chart, use_container_width=True)
        except Exception as e:
            st.error(f"Visualization error: {e}")
        
        # LV Design
        if result.lv_design:
            st.divider()
            st.subheader("🧬 LV Titration Design")
            
            for cell_line, plan in result.lv_design.titration_plans.items():
                with st.expander(f"📋 {cell_line} Titration Plan"):
                    col1, col2 = st.columns(2)
                    col1.metric("Plate Format", plan.plate_format)
                    col1.metric("Cells per Well", f"{plan.cells_per_well:,}")
                    col2.metric("Replicates", plan.replicates_per_condition)
                    col2.metric("Volumes to Test", len(plan.lv_volumes_ul))
                    
                    st.write("**Volumes (µL):**", ", ".join([f"{v:.1f}" for v in plan.lv_volumes_ul]))
        
        # Simulate Titration Data (Demo)
        st.divider()
        st.subheader("🔬 Simulate Titration \u0026 Model Fitting")
        
        selected_line = st.selectbox("Select Cell Line", result.scenario.cell_lines)
        
        if st.button("Simulate Titration Data"):
            with st.spinner("Simulating titration..."):
                try:
                    # Simulate data
                    plan = result.lv_design.titration_plans[selected_line]
                    true_titer = 50000  # TU/µL
                    
                    rows = []
                    for vol in plan.lv_volumes_ul:
                        moi = (vol * true_titer) / plan.cells_per_well
                        bfp = 0.98 * (1 - np.exp(-moi)) + np.random.normal(0, 0.01)
                        bfp = max(0.001, min(0.999, bfp))
                        rows.append({'volume_ul': vol, 'fraction_bfp': bfp})
                    
                    titration_data = pd.DataFrame(rows)
                    titration_result = LVTitrationResult(cell_line=selected_line, data=titration_data)
                    
                    # Fit model
                    model = fit_lv_transduction_model(
                        result.scenario,
                        result.lv_design.batch,
                        titration_result,
                        n_cells_override=plan.cells_per_well
                    )
                    
                    st.session_state[f'model_{selected_line}'] = model
                    st.session_state[f'data_{selected_line}'] = titration_data
                    
                    st.success(f"Model fitted! Inferred titer: {model.titer_tu_ul:,.0f} TU/µL")
                except Exception as e:
                    st.error(f"Simulation failed: {e}")
                    import traceback
                    st.code(traceback.format_exc())
        
        # Display Model Results
        if f'model_{selected_line}' in st.session_state:
            model = st.session_state[f'model_{selected_line}']
            data = st.session_state[f'data_{selected_line}']
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Inferred Titer", f"{model.titer_tu_ul:,.0f} TU/µL")
            col2.metric("Max Infectivity", f"{model.max_infectivity:.1%}")
            col3.metric("R²", f"{model.r_squared:.3f}")
            
            # Titration Curve
            st.subheader("Titration Curve")
            try:
                chart = plot_titration_curve(model, data, target_moi=result.scenario.moi_target)
                st.altair_chart(chart, use_container_width=True)
            except Exception as e:
                st.error(f"Visualization error: {e}")
            
            # Titer Posterior
            if model.posterior:
                st.subheader("Titer Posterior Distribution")
                try:
                    chart = plot_titer_posterior(model)
                    if chart:
                        st.altair_chart(chart, use_container_width=True)
                        
                        ci_low, ci_high = model.posterior.ci_95
                        st.info(f"95% Credible Interval: [{ci_low:,.0f}, {ci_high:,.0f}] TU/µL")
                except Exception as e:
                    st.error(f"Visualization error: {e}")
            
            # Risk Assessment
            st.divider()
            st.subheader("⚠️ Scale-Up Risk Assessment")
            
            with st.form("risk_config"):
                col1, col2 = st.columns(2)
                
                with col1:
                    target_bfp = st.slider("Target BFP%", 0.1, 0.5, 0.3, 0.05)
                    tolerance_low = st.slider("Tolerance Lower", 0.1, 0.5, 0.25, 0.05)
                
                with col2:
                    tolerance_high = st.slider("Tolerance Upper", 0.1, 0.5, 0.35, 0.05)
                    n_sims = st.number_input("Simulations", 1000, 10000, 5000, 1000)
                
                if st.form_submit_button("Run Risk Assessment"):
                    try:
                        config = ScreenConfig(
                            num_guides=len(result.library.df),
                            coverage_target=result.scenario.coverage_cells_per_gene_per_bank,
                            target_bfp=target_bfp,
                            bfp_tolerance=(tolerance_low, tolerance_high)
                        )
                        
                        simulator = ScreenSimulator(model, config)
                        
                        st.session_state['simulator'] = simulator
                        st.session_state['n_sims'] = n_sims
                        
                        pos = simulator.get_probability_of_success()
                        st.success(f"Probability of Success: {pos:.1%}")
                    except Exception as e:
                        st.error(f"Risk assessment failed: {e}")
            
            if 'simulator' in st.session_state:
                simulator = st.session_state['simulator']
                n_sims = st.session_state.get('n_sims', 5000)
                
                try:
                    chart = plot_risk_assessment(simulator, n_sims=n_sims)
                    st.altair_chart(chart, use_container_width=True)
                except Exception as e:
                    st.error(f"Visualization error: {e}")
        
        # Cost Breakdown (Placeholder)
        
        col1.metric("Reagents", f"${total_reagent_cost:,.2f}")
        col2.metric("Virus", f"${total_virus_cost:,.2f}")
        col3.metric("Flow Cytometry", f"${flow_cost:,.2f}")
        col4.metric("**TOTAL**", f"${total_cost:,.2f}", delta=None)
        
        st.divider()
        st.subheader("📊 Cost Breakdown")
        
        # Pie chart of costs
        cost_df = pd.DataFrame({
            "Category": ["Reagents", "Virus", "Flow Cytometry"],
            "Cost": [total_reagent_cost, total_virus_cost, flow_cost]
        })
        
        chart = alt.Chart(cost_df).mark_arc().encode(
            theta="Cost:Q",
            color=alt.Color("Category:N", scale=alt.Scale(scheme='category10')),
            tooltip=["Category", alt.Tooltip("Cost:Q", format="$,.2f")]
        )
        
        st.altair_chart(chart, use_container_width=True)
        
        # Export budget config
        st.divider()
        st.subheader("💾 Save Configuration")
        
        budget_config_yaml = f"""# Budget Configuration
max_titration_budget_usd: {total_cost:.2f}
reagent_cost_per_well: {reagent_cost}
virus_price: {virus_price}
mins_per_sample_flow: 3.0
flow_rate_per_hour: 120.0
"""
        
        st.code(budget_config_yaml, language="yaml")
        
        if st.download_button(
            label="Download Budget Config",
            data=budget_config_yaml,
            file_name="budget_config.yaml",
            mime="text/yaml"
        ):
            st.success("Config downloaded!")
