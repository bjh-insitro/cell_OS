# dashboard_app/pages/tab_5_posh_decisions.py
import streamlit as st
import pandas as pd
from dashboard_app.utils import (
    POSHDecisionEngine, 
    UserRequirements, 
    POSHProtocol, 
    AutomationLevel
)

def render_posh_decisions(df, pricing):
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