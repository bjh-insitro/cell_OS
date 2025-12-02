# dashboard_app/pages/tab_6_posh_designer.py
import streamlit as st
import pandas as pd
import altair as alt
import glob
import numpy as np
import traceback
from dashboard_app.utils import (
    POSHScenario, 
    run_posh_screen_design, 
    fit_lv_transduction_model,
    LVTitrationResult,
    ScreenSimulator,
    ScreenConfig,
    plot_library_composition,
    plot_titration_curve,
    plot_titer_posterior,
    plot_risk_assessment,
    LabWorldModel,
    ExperimentDB,
    datetime
)

def render_posh_designer(df, pricing):
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
                    
                    # Save to database
                    db = ExperimentDB()
                    
                    design_data = {
                        'design_id': result.scenario.name,
                        'project_name': 'POSH_Screen',
                        'library_name': f"{result.scenario.name}_Library",
                        'cell_line': ','.join(result.scenario.cell_lines),
                        'target_moi': result.scenario.moi_target,
                        'gRNA_count': result.library.num_genes
                    }
                    
                    db.insert_design(design_data)
                    db.close()
                    
                    st.success(f"✅ Library design complete and saved to database!")
                    st.info(f"Design ID: {result.scenario.name}")
                    
                except Exception as e:
                    st.error(f"Design failed: {e}")
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
                        st.altair_chart(chart, width="stretch")
                        
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
                    st.altair_chart(chart, width="stretch")
                except Exception as e:
                    st.error(f"Visualization error: {e}")
        
        # Cost Breakdown (Placeholder)
        # Defining dummy values for safety
        total_reagent_cost = 1500.0
        total_virus_cost = 800.0
        flow_cost = 500.0
        total_cost = total_reagent_cost + total_virus_cost + flow_cost
        reagent_cost = 2.5 # Placeholder for config export
        virus_price = 0.15 # Placeholder for config export
        
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
        
        st.altair_chart(chart, width="stretch")
        
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