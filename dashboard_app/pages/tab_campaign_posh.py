"""
POSH Campaign Manager Tab.

Focuses on simulating the end-to-end POSH campaign, starting with MCB generation.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from cell_os.simulation.mcb_wrapper import simulate_mcb_generation, VendorVialSpec

import plotly.graph_objects as go
import graphviz

def _render_lineage(result):
    """Render a lineage tree using Graphviz."""
    st.subheader("Sample Lineage")
    
    if not result.vials:
        st.info("No lineage to display.")
        return

    # Create Digraph
    dot = graphviz.Digraph(comment='Sample Lineage')
    dot.attr(rankdir='LR') # Left to Right layout
    
    # Input Node
    # For MCB, source is Vendor Vial. For WCB, source is MCB Vial.
    source_id = result.vials[0].source_vendor_vial_id if hasattr(result.vials[0], 'source_vendor_vial_id') else result.vials[0].source_mcb_vial_id
    input_label = f"Input\n{source_id}"
    dot.node('Input', input_label, shape='box', style='filled', fillcolor='#e1f5fe')
    
    # Process Node
    process_label = "Expansion\n& Banking"
    dot.node('Process', process_label, shape='ellipse', style='filled', fillcolor='#fff9c4')
    
    # Edge Input -> Process
    dot.edge('Input', 'Process')
    
    # Output Nodes (Vials)
    # To avoid clutter, if > 10 vials, summarize
    num_vials = len(result.vials)
    if num_vials > 10:
        # Show first 3, last 3, and a summary node
        display_vials = result.vials[:3] + result.vials[-3:]
        
        for v in display_vials:
            label = f"{v.vial_id}\n(P{v.passage_number})"
            dot.node(v.vial_id, label, shape='note', style='filled', fillcolor='#e8f5e9')
            dot.edge('Process', v.vial_id)
            
        # Summary node
        summary_label = f"... {num_vials - 6} more vials ..."
        dot.node('Summary', summary_label, shape='plaintext')
        dot.edge('Process', 'Summary', style='dashed')
        
    else:
        for v in result.vials:
            label = f"{v.vial_id}\n(P{v.passage_number})"
            dot.node(v.vial_id, label, shape='note', style='filled', fillcolor='#e8f5e9')
            dot.edge('Process', v.vial_id)
            
    st.graphviz_chart(dot)

def _render_resources(result):
    """Render resource usage and cost analysis."""
    st.subheader("Resource & Cost Analysis 💰")
    
    # 1. Calculate Costs
    # Assumptions
    COST_MEDIA_L = 500.0
    COST_STAFF_HR = 100.0
    COST_BSC_HR = 50.0
    COST_VIAL = 5.0
    
    # Extract totals
    total_media = result.summary.get("total_media_l", 0.0)
    
    # Sum daily hours if available, otherwise estimate
    if not result.daily_metrics.empty:
        total_staff = result.daily_metrics["staff_hours"].sum() if "staff_hours" in result.daily_metrics.columns else 0.0
        total_bsc = result.daily_metrics["bsc_hours"].sum() if "bsc_hours" in result.daily_metrics.columns else 0.0
    else:
        total_staff = 0.0
        total_bsc = 0.0
        
    num_vials = len(result.vials)
    
    # Calculate Totals
    cost_media = total_media * COST_MEDIA_L
    cost_staff = total_staff * COST_STAFF_HR
    cost_bsc = total_bsc * COST_BSC_HR
    cost_vials = num_vials * COST_VIAL
    
    total_cost = cost_media + cost_staff + cost_bsc + cost_vials
    cost_per_vial = total_cost / num_vials if num_vials > 0 else 0.0
    
    # 2. Display KPI Metrics
    r_col1, r_col2, r_col3 = st.columns(3)
    with r_col1:
        st.metric("Total Campaign Cost", f"${total_cost:,.2f}")
    with r_col2:
        st.metric("Cost Per Vial", f"${cost_per_vial:,.2f}")
    with r_col3:
        st.metric("Media Consumed", f"{total_media:.1f} L")
        
    st.divider()
    
    # 3. Visualizations
    c_col1, c_col2 = st.columns(2)
    
    with c_col1:
        st.markdown("**Cost Breakdown**")
        labels = ['Media', 'Staff Labor', 'BSC Usage', 'Vials']
        values = [cost_media, cost_staff, cost_bsc, cost_vials]
        
        fig_pie = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4)])
        fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with c_col2:
        st.markdown("**Daily Labor Load**")
        if not result.daily_metrics.empty and "staff_hours" in result.daily_metrics.columns:
            fig_bar = go.Figure(data=[
                go.Bar(name='Staff Hours', x=result.daily_metrics['day'], y=result.daily_metrics['staff_hours']),
                go.Bar(name='BSC Hours', x=result.daily_metrics['day'], y=result.daily_metrics['bsc_hours'])
            ])
            fig_bar.update_layout(barmode='group', height=300, margin=dict(t=0, b=0, l=0, r=0),
                                 legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Daily labor data not available.")

    st.divider()
    
    # 4. Consumables Bill of Materials
    st.subheader("Consumables Bill of Materials 📦")
    
    import math
    
    # Calculate quantities
    qty_media_bottles = math.ceil(total_media / 0.5) # 500mL bottles
    qty_vials = num_vials + result.summary.get("waste_vials", 0)
    qty_flasks = max(1, int(num_vials / 5)) # Estimate: 1 T75 per 5 vials
    qty_pbs = 1 # Fixed estimate
    qty_trypsin = 1 # Fixed estimate
    
    # Estimate Pipettes & Tips based on usage
    # Feed = 15mL, Thaw = 50mL. Approx ops from total media.
    # 1 Feed = 1 Pipette (10mL) + 1 Tip (1000uL)
    # 1 Passage = 2 Pipettes + 4 Tips
    # Rough proxy: 
    estimated_feeds = int((total_media * 1000) / 15)
    estimated_passages = max(1, int(num_vials / 10))
    
    qty_pipettes_10ml = estimated_feeds + (estimated_passages * 2) + 2 # +2 for start/end
    qty_tips_1000ul = estimated_feeds + (estimated_passages * 4)
    
    # Unit Costs
    cost_media_bottle = 250.0 # $500/L -> $250/500mL
    cost_vial_unit = 5.0
    cost_flask_unit = 10.0
    cost_pbs_unit = 25.0
    cost_trypsin_unit = 45.0
    cost_pipette_unit = 0.50
    cost_tip_unit = 0.10
    
    consumables_data = [
        {"Item": "mTeSR Plus Kit (500mL)", "Quantity": qty_media_bottles, "Unit Cost": f"${cost_media_bottle:.2f}", "Total Cost": f"${qty_media_bottles * cost_media_bottle:.2f}"},
        {"Item": "Cryovials (1.8mL)", "Quantity": qty_vials, "Unit Cost": f"${cost_vial_unit:.2f}", "Total Cost": f"${qty_vials * cost_vial_unit:.2f}"},
        {"Item": "T75 Flasks", "Quantity": qty_flasks, "Unit Cost": f"${cost_flask_unit:.2f}", "Total Cost": f"${qty_flasks * cost_flask_unit:.2f}"},
        {"Item": "Serological Pipettes (10mL)", "Quantity": qty_pipettes_10ml, "Unit Cost": f"${cost_pipette_unit:.2f}", "Total Cost": f"${qty_pipettes_10ml * cost_pipette_unit:.2f}"},
        {"Item": "Pipette Tips (1000uL)", "Quantity": qty_tips_1000ul, "Unit Cost": f"${cost_tip_unit:.2f}", "Total Cost": f"${qty_tips_1000ul * cost_tip_unit:.2f}"},
        {"Item": "PBS (500mL)", "Quantity": qty_pbs, "Unit Cost": f"${cost_pbs_unit:.2f}", "Total Cost": f"${qty_pbs * cost_pbs_unit:.2f}"},
        {"Item": "Trypsin-EDTA (100mL)", "Quantity": qty_trypsin, "Unit Cost": f"${cost_trypsin_unit:.2f}", "Total Cost": f"${qty_trypsin * cost_trypsin_unit:.2f}"}
    ]
    
    st.dataframe(pd.DataFrame(consumables_data), use_container_width=True)

def render_posh_campaign_manager(df, pricing):
    """Render the POSH Campaign Manager tab."""
    st.header("🧬 POSH Campaign Simulation")
    st.markdown("""
    Simulate the full multi-cell-line POSH campaign.
    **Phase 1: Master Cell Bank (MCB) Generation**
    """)
    
    # --- Configuration Controls ---
    with st.expander("Campaign Configuration", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("Campaign Settings")
            cell_line = st.selectbox("Cell Line", ["U2OS", "HepG2", "A549"], key="posh_sim_cell_line")
            
        with col2:
            st.subheader("Vendor Vial Specs")
            initial_cells = st.number_input("Initial Cells", value=1.0e6, format="%.1e")
            vendor_lot = st.text_input("Vendor Lot", value="LOT-2025-X")
            
        with col3:
            st.subheader("Banking Targets")
            target_vials = st.number_input("Target MCB Vials", value=10, min_value=10, max_value=100)
            
        st.divider()
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

import plotly.graph_objects as go

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
        days = result.summary.get("duration_days", 0)
        st.metric("Duration", f"{days} days")
    with col4:
        status = "✅ Success" if result.success else "❌ Failed"
        st.metric("Status", status)
        
    st.divider()
    
    # Create Tabs for different views
    tab_bio, tab_res = st.tabs(["🧬 Biology & Quality", "💰 Resources & Cost"])
    
    with tab_bio:
        # 2. Plots
        st.subheader("Growth Curve")
        if not result.daily_metrics.empty:
            fig = px.line(result.daily_metrics, x="day", y="total_cells", 
                         title=f"{result.cell_line} Expansion", markers=True)
            st.plotly_chart(fig, use_container_width=True)
            
        # 3. Lineage
        _render_lineage(result)
                
        # 4. Vial Table
        st.subheader("Generated MCB Vials")
        if result.vials:
            vial_data = [{
                "Vial ID": v.vial_id,
                "Passage": v.passage_number,
                "Cells": f"{v.cells_per_vial:.1e}",
                "Viability": f"{v.viability:.2%}",
                "Source Vendor": v.source_vendor_vial_id,
                "Location": v.location
            } for v in result.vials]
            st.dataframe(pd.DataFrame(vial_data), use_container_width=True)
        else:
            st.warning("No vials generated.")
            
    with tab_res:
        _render_resources(result)
        
    # 5. Logs (outside tabs)
    with st.expander("Simulation Logs"):
        for log in result.logs:
            st.text(log)
    st.markdown("""
    **Phase 2: Working Cell Bank (WCB) Generation**
    Select a generated MCB vial to expand into a Working Cell Bank.
    """)
    
    if not st.session_state.mcb_results:
        st.info("⚠️ Please complete Phase 1 (MCB Generation) above to proceed to Phase 2.")
    else:
        # Initialize session state for WCB results and consumed vials
        if "wcb_results" not in st.session_state:
            st.session_state.wcb_results = {}
        if "consumed_mcb_vials" not in st.session_state:
            st.session_state.consumed_mcb_vials = set()
            
        with st.expander("WCB Configuration", expanded=True):
            wcb_col1, wcb_col2, wcb_col3 = st.columns(3)
            
            # Get available MCB vials from results (excluding consumed ones)
            available_mcb_vials = []
            mcb_vial_map = {}
            
            for res in st.session_state.mcb_results.values():
                if res.success and res.vials:
                    for v in res.vials:
                        if v.vial_id not in st.session_state.consumed_mcb_vials:
                            label = f"{v.vial_id} ({v.cell_line}, P{v.passage_number})"
                            available_mcb_vials.append(label)
                            mcb_vial_map[label] = v
            
            with wcb_col1:
                if available_mcb_vials:
                    selected_mcb_label = st.selectbox("Source MCB Vial", available_mcb_vials)
                else:
                    st.warning("No available MCB vials. Run Phase 1 to generate more.")
                    selected_mcb_label = None
                
            with wcb_col2:
                target_wcb_vials = st.number_input("Target WCB Vials", value=10, min_value=10, max_value=500)
                
            with wcb_col3:
                st.write("") # Spacer
                st.write("")
                run_wcb_sim = st.button("▶️ Simulate WCB Generation", type="primary", disabled=not selected_mcb_label)
                
        if run_wcb_sim and selected_mcb_label:
            source_vial = mcb_vial_map[selected_mcb_label]
            with st.spinner(f"Simulating WCB generation from {source_vial.vial_id}..."):
                from cell_os.simulation.wcb_wrapper import simulate_wcb_generation, MCBVialSpec
                
                # Create spec from selected MCB vial
                spec = MCBVialSpec(
                    cell_line=source_vial.cell_line,
                    vial_id=source_vial.vial_id,
                    passage_number=source_vial.passage_number,
                    cells_per_vial=source_vial.cells_per_vial,
                    viability=source_vial.viability
                )
                
                result = simulate_wcb_generation(spec, target_vials=target_wcb_vials)
                st.session_state.wcb_results[source_vial.vial_id] = result
                
                # Mark vial as consumed
                st.session_state.consumed_mcb_vials.add(source_vial.vial_id)
                
                st.success(f"WCB Simulation complete for {source_vial.vial_id}!")
                st.rerun() # Rerun to update the dropdown list

        # Display WCB Results
        if st.session_state.wcb_results:
            st.subheader("WCB Results")
            wcb_keys = list(st.session_state.wcb_results.keys())
            wcb_tabs = st.tabs(wcb_keys)
            
            for i, key in enumerate(wcb_keys):
                with wcb_tabs[i]:
                    result = st.session_state.wcb_results[key]
                    _render_wcb_result(result)

def _render_wcb_result(result):
    """Render metrics and plots for a single WCB result."""
    # Reuse similar logic to MCB but adapted for WCB context
    
    # 1. KPI Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("WCB Vials Banked", len(result.vials))
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
    
    # Create Tabs
    tab_bio, tab_res = st.tabs(["🧬 Biology & Quality", "💰 Resources & Cost"])
    
    with tab_bio:
        # 2. Plots
        st.subheader("Expansion")
        if not result.daily_metrics.empty:
            fig = px.line(result.daily_metrics, x="day", y="total_cells", 
                         title=f"{result.cell_line} WCB Expansion", markers=True)
            st.plotly_chart(fig, use_container_width=True)
            
        # 3. Lineage
        _render_lineage(result)
                
        # 4. Vial Table
        st.subheader("Generated WCB Vials")
        if result.vials:
            vial_data = [{
                "Vial ID": v.vial_id,
                "Passage": v.passage_number,
                "Cells": f"{v.cells_per_vial:.1e}",
                "Viability": f"{v.viability:.2%}",
                "Source MCB": v.source_mcb_vial_id,
                "Location": v.location
            } for v in result.vials]
            st.dataframe(pd.DataFrame(vial_data), use_container_width=True)
        else:
            st.warning("No WCB vials generated.")
            
    with tab_res:
        _render_resources(result)
