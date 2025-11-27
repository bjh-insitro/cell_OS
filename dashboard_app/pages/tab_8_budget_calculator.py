# dashboard_app/pages/tab_8_budget_calculator.py
import streamlit as st
from dashboard_app.utils import BudgetConfig # Imported for type hint/context, not strictly needed here

def render_budget_calculator(df, pricing):
    st.header("🧮 Budget Calculator")
    st.markdown("Estimate the cost of your next titration campaign.")
    
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Parameters")
        max_budget = st.number_input("Max Budget ($)", 1000.0, 50000.0, 5000.0, 500.0)
        virus_price = st.number_input("Virus Price ($/µL)", 0.01, 10.0, 0.15, 0.01)
        reagent_cost = st.number_input("Reagent Cost ($/well)", 0.1, 10.0, 2.50, 0.1)
        
    with col2:
        st.subheader("Throughput")
        flow_rate = st.number_input("Flow Rate (samples/hr)", 10, 500, 120)
        mins_per_sample = st.number_input("Prep Time (min/sample)", 0.1, 10.0, 3.0)
        
    st.divider()
    
    # Interactive Estimation
    st.subheader("Estimation")
    n_cell_lines = st.slider("Number of Cell Lines", 1, 10, 3)
    rounds = st.slider("Est. Rounds per Line", 1, 10, 5)
    samples_per_round = st.slider("Samples per Round", 1, 96, 8)
    
    total_samples = n_cell_lines * rounds * samples_per_round
    
    # Calculations
    reagent_total = total_samples * reagent_cost
    
    # Flow cost (assuming $100/hr instrument time + labor)
    flow_hours = total_samples / flow_rate
    flow_cost = flow_hours * 100.0 # Placeholder rate
    
    # Virus cost (assuming avg 5µL per sample)
    virus_vol = total_samples * 5.0
    virus_total = virus_vol * virus_price
    
    grand_total = reagent_total + flow_cost + virus_total
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Samples", total_samples)
    c2.metric("Est. Cost", f"${grand_total:,.2f}")
    c3.metric("Cost/Line", f"${grand_total/n_cell_lines:,.2f}")
    c4.metric("Budget Usage", f"{grand_total/max_budget:.1%}")
    
    if grand_total > max_budget:
        st.error(f"Over Budget by ${grand_total - max_budget:,.2f}!")
    else:
        st.success("Within Budget")
    
    # Export
    if st.button("Generate Config YAML"):
        config_yaml = f"""budget:
  max_titration_budget_usd: {max_budget}
  reagent_cost_per_well: {reagent_cost}
  mins_per_sample_flow: {mins_per_sample}
  flow_rate_per_hour: {flow_rate}
  virus_price: {virus_price}
"""
        st.code(config_yaml, language="yaml")