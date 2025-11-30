"""
POSH Campaign Manager Tab.

Focuses on simulating the end-to-end POSH campaign, starting with MCB generation.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from cell_os.simulation.mcb_wrapper import simulate_mcb_generation, VendorVialSpec

def render_posh_campaign_manager(df, pricing):
    """Render the POSH Campaign Manager tab."""
    st.header("🧬 POSH Campaign Simulation")
    st.markdown("""
    Simulate the full multi-cell-line POSH campaign.
    **Phase 1: Master Cell Bank (MCB) Generation**
    """)
    
    # --- Sidebar Controls ---
    with st.sidebar:
        st.subheader("Campaign Settings")
        cell_line = st.selectbox("Cell Line", ["U2OS", "HepG2", "A549"])
        
        st.subheader("Vendor Vial Specs")
        initial_cells = st.number_input("Initial Cells", value=1.0e6, format="%.1e")
        vendor_lot = st.text_input("Vendor Lot", value="LOT-2025-X")
        
        st.subheader("Banking Targets")
        target_vials = st.number_input("Target MCB Vials", value=30, min_value=10, max_value=100)
        
        run_sim = st.button("▶️ Simulate MCB Generation", type="primary")

    # --- Main Content ---
    
    # Initialize session state for results if not present
    if "mcb_results" not in st.session_state:
        st.session_state.mcb_results = {}
        
    if run_sim:
        with st.spinner(f"Simulating MCB generation for {cell_line}..."):
            spec = VendorVialSpec(
                cell_line=cell_line,
                initial_cells=initial_cells,
                lot_number=vendor_lot,
                vial_id=f"VENDOR-{cell_line}-001"
            )
            
            result = simulate_mcb_generation(spec, target_vials=target_vials)
            st.session_state.mcb_results[cell_line] = result
            st.success(f"Simulation complete for {cell_line}!")
            
    # Display Results
    if st.session_state.mcb_results:
        # Tabbed view for different cell lines if multiple run
        cell_lines_run = list(st.session_state.mcb_results.keys())
        tabs = st.tabs(cell_lines_run)
        
        for i, c_line in enumerate(cell_lines_run):
            with tabs[i]:
                result = st.session_state.mcb_results[c_line]
                _render_mcb_result(result)
    else:
        st.info("Configure settings in the sidebar and click 'Simulate MCB Generation' to start.")

def _render_mcb_result(result):
    """Render metrics and plots for a single MCB result."""
    
    # 1. KPI Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Vials Banked", len(result.vials))
    with col2:
        avg_viability = pd.Series([v.viability for v in result.vials]).mean()
        st.metric("Avg Viability", f"{avg_viability*100:.1f}%")
    with col3:
        days = result.summary.get("days_to_complete", 0)
        st.metric("Duration", f"{days} days")
    with col4:
        status = "✅ Success" if result.success else "❌ Failed"
        st.metric("Status", status)
        
    st.divider()
    
    # 2. Plots
    col_plot1, col_plot2 = st.columns(2)
    
    with col_plot1:
        st.subheader("Growth Curve")
        if not result.daily_metrics.empty:
            fig = px.line(result.daily_metrics, x="day", y="total_cells", 
                         title=f"{result.cell_line} Expansion", markers=True)
            st.plotly_chart(fig, use_container_width=True)
            
    with col_plot2:
        st.subheader("Viability Trend")
        if not result.daily_metrics.empty:
            fig = px.line(result.daily_metrics, x="day", y="avg_viability", 
                         title=f"{result.cell_line} Viability", markers=True,
                         range_y=[0.8, 1.0])
            st.plotly_chart(fig, use_container_width=True)
            
    # 3. Vial Table
    st.subheader("Generated MCB Vials")
    if result.vials:
        vial_data = [{
            "Vial ID": v.vial_id,
            "Passage": v.passage_number,
            "Cells": f"{v.cells_per_vial:.1e}",
            "Viability": f"{v.viability:.2%}",
            "Source": v.source_vendor_vial_id,
            "Location": v.location
        } for v in result.vials]
        st.dataframe(pd.DataFrame(vial_data), use_container_width=True)
    else:
        st.warning("No vials generated.")
        
    # 4. Logs
    with st.expander("Simulation Logs"):
        for log in result.logs:
            st.text(log)
