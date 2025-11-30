import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from cell_os.simulation.mcb_wrapper import simulate_mcb_generation, VendorVialSpec
from cell_os.cell_line_database import get_cell_line_profile # NEW IMPORT

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

def _get_item_cost(pricing, item_id, default_cost=0.0):
    """Helper to safely get item cost from pricing dict."""
    if not pricing or 'items' not in pricing:
        return default_cost
    
    item = pricing['items'].get(item_id)
    if item:
        return item.get('unit_price_usd', default_cost)
    return default_cost

def _get_item_name(pricing, item_id, default_name):
    """Helper to safely get item name from pricing dict."""
    if not pricing or 'items' not in pricing:
        return default_name
    
    item = pricing['items'].get(item_id)
    if item:
        return item.get('name', default_name)
    return default_name

def _render_resources(result, pricing):
    """Render resource usage and cost analysis."""
    st.subheader("Resource & Cost Analysis 💰")
    
    # 1. Dynamic Reagent Resolution
    cell_line = result.cell_line
    profile = get_cell_line_profile(cell_line)
    
    # Defaults
    media_id = "dmem_10fbs"
    dissociation_id = "trypsin_edta"
    coating_id = None
    
    if profile:
        if profile.media: media_id = profile.media
        if profile.dissociation_method: 
            # Map method to item ID (simple mapping)
            if profile.dissociation_method == "accutase": dissociation_id = "accutase"
            elif profile.dissociation_method == "versene": dissociation_id = "versene"
            else: dissociation_id = "trypsin_edta"
            
        if profile.coating_required and profile.coating:
            coating_id = profile.coating

    # Look up costs and names
    cost_media_bottle = _get_item_cost(pricing, media_id, 25.0)
    media_name = _get_item_name(pricing, media_id, f"{media_id} (500mL)")
    
    cost_dissociation_unit = _get_item_cost(pricing, dissociation_id, 45.0)
    dissociation_name = _get_item_name(pricing, dissociation_id, f"{dissociation_id} (100mL)")
    
    cost_coating_unit = 0.0
    coating_name = ""
    if coating_id:
        cost_coating_unit = _get_item_cost(pricing, coating_id, 350.0)
        coating_name = _get_item_name(pricing, coating_id, coating_id)
    
    # Define coating_needed for later use
    coating_needed = (coating_id is not None)

    # Standard items
    cost_vial_unit = _get_item_cost(pricing, "cryovial_1_8ml", 5.0)
    cost_flask_unit = _get_item_cost(pricing, "flask_t75", 10.0)
    cost_pbs_unit = _get_item_cost(pricing, "pbs", 25.0)
    cost_pipette_unit = _get_item_cost(pricing, "pipette_10ml", 0.50)
    cost_tip_unit = _get_item_cost(pricing, "tip_1000ul_lr", 0.10)
    
    COST_STAFF_HR = 100.0
    COST_BSC_HR = 50.0

    # 2. Calculate Costs
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
    cost_media = total_media * (cost_media_bottle * 2) # Approx $ per L (bottle is 500ml)
    cost_staff = total_staff * COST_STAFF_HR
    cost_bsc = total_bsc * COST_BSC_HR
    cost_vials = num_vials * cost_vial_unit
    
    total_cost = cost_media + cost_staff + cost_bsc + cost_vials
    cost_per_vial = total_cost / num_vials if num_vials > 0 else 0.0
    
    # 3. Display KPI Metrics
    r_col1, r_col2, r_col3 = st.columns(3)
    with r_col1:
        st.metric("Total Campaign Cost", f"${total_cost:,.2f}")
    with r_col2:
        st.metric("Cost Per Vial", f"${cost_per_vial:,.2f}")
    with r_col3:
        st.metric("Media Consumed", f"{total_media:.1f} L")
        
    st.divider()
    
    # 4. Visualizations
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
    
    # 5. Consumables Bill of Materials
    st.subheader("Consumables Bill of Materials 📦")
    
    import math
    
    # View toggle
    view_mode = st.radio("View Mode", ["Aggregate View", "Daily Breakdown"], horizontal=True, key="bom_view_mode")
    
    # Calculate quantities
    qty_media_bottles = math.ceil(total_media / 0.5) # 500mL bottles
    qty_vials = num_vials + result.summary.get("waste_vials", 0)
    qty_flasks = max(1, int(num_vials / 5)) # Estimate: 1 T75 per 5 vials
    qty_pbs = 1 # Fixed estimate
    qty_dissociation = 1 # Fixed estimate
    
    # Estimate Pipettes & Tips based on usage
    estimated_feeds = int((total_media * 1000) / 15)
    estimated_passages = max(1, int(num_vials / 10))
    
    qty_pipettes_10ml = estimated_feeds + (estimated_passages * 2) + 2 
    qty_tips_1000ul = estimated_feeds + (estimated_passages * 4)
    
    if view_mode == "Aggregate View":
        # Dynamic aggregate view
        consumables_data = [
            {"Item": media_name, "Quantity": qty_media_bottles, "Unit Cost": f"${cost_media_bottle:.2f}", "Total Cost": f"${qty_media_bottles * cost_media_bottle:.2f}"},
            {"Item": "Cryovials (1.8mL)", "Quantity": qty_vials, "Unit Cost": f"${cost_vial_unit:.2f}", "Total Cost": f"${qty_vials * cost_vial_unit:.2f}"},
            {"Item": "T75 Flasks", "Quantity": qty_flasks, "Unit Cost": f"${cost_flask_unit:.2f}", "Total Cost": f"${qty_flasks * cost_flask_unit:.2f}"},
            {"Item": "Serological Pipettes (10mL)", "Quantity": qty_pipettes_10ml, "Unit Cost": f"${cost_pipette_unit:.2f}", "Total Cost": f"${qty_pipettes_10ml * cost_pipette_unit:.2f}"},
            {"Item": "Pipette Tips (1000uL)", "Quantity": qty_tips_1000ul, "Unit Cost": f"${cost_tip_unit:.2f}", "Total Cost": f"${qty_tips_1000ul * cost_tip_unit:.2f}"},
            {"Item": "PBS (500mL)", "Quantity": qty_pbs, "Unit Cost": f"${cost_pbs_unit:.2f}", "Total Cost": f"${qty_pbs * cost_pbs_unit:.2f}"},
            {"Item": dissociation_name, "Quantity": qty_dissociation, "Unit Cost": f"${cost_dissociation_unit:.2f}", "Total Cost": f"${qty_dissociation * cost_dissociation_unit:.2f}"}
        ]
        
        if coating_id:
             # Estimate 1 kit per campaign for simplicity
            consumables_data.append(
                {"Item": coating_name, "Quantity": 1, "Unit Cost": f"${cost_coating_unit:.2f}", "Total Cost": f"${cost_coating_unit:.2f}"}
            )
        
        st.dataframe(pd.DataFrame(consumables_data), use_container_width=True)
        
    else:  # Daily Breakdown
        if not result.daily_metrics.empty:
            daily_breakdown = []
            prev_media = 0.0
            prev_flasks = 0
            
            for idx, row in result.daily_metrics.iterrows():
                day = int(row['day'])
                current_media_ml = row.get('media_consumed', 0.0)
                current_flasks = int(row.get('flask_count', 0))
                
                # Calculate daily deltas
                media_used_ml = current_media_ml - prev_media
                new_flasks = max(0, current_flasks - prev_flasks)
                
                # Estimate daily pipettes and tips based on flask count
                daily_pipettes = current_flasks
                daily_tips = current_flasks * 2  # 2 tips per operation
                
                # Calculate daily costs
                cost_media_day = (media_used_ml / 500.0) * cost_media_bottle  # Convert mL to bottles
                cost_flasks_day = new_flasks * cost_flask_unit
                cost_pipettes_day = daily_pipettes * cost_pipette_unit
                cost_tips_day = daily_tips * cost_tip_unit
                cost_plasticware_day = cost_flasks_day + cost_pipettes_day + cost_tips_day
                
                daily_breakdown.append({
                    "Day": day,
                    "Media (mL)": f"{media_used_ml:.1f}",
                    "New Flasks": new_flasks,
                    "Pipettes": daily_pipettes,
                    "Tips": daily_tips,
                    "Media Cost": f"${cost_media_day:.2f}",
                    "Plasticware Cost": f"${cost_plasticware_day:.2f}",
                    "Daily Total": f"${cost_media_day + cost_plasticware_day:.2f}"
                })
                
                prev_media = current_media_ml
                prev_flasks = current_flasks
            
            # Add final day with vials
            final_day = result.summary.get("duration_days", len(result.daily_metrics))
            cost_vials_final = qty_vials * cost_vial_unit
            daily_breakdown.append({
                "Day": final_day,
                "Media (mL)": "0.0",
                "New Flasks": 0,
                "Pipettes": 0,
                "Tips": 0,
                "Media Cost": "$0.00",
                "Plasticware Cost": f"${cost_vials_final:.2f}",
                "Daily Total": f"${cost_vials_final:.2f}"
            })
            
            df_daily = pd.DataFrame(daily_breakdown)
            st.dataframe(df_daily, use_container_width=True)
            
            # Daily cost visualization
            st.markdown("**Daily Cost Breakdown**")
            
            # Prepare data for stacked bar chart
            chart_data = []
            for idx, row in result.daily_metrics.iterrows():
                day = int(row['day'])
                current_media_ml = row.get('media_consumed', 0.0)
                current_flasks = int(row.get('flask_count', 0))
                
                if idx == 0:
                    media_used_ml = current_media_ml
                    new_flasks = current_flasks
                else:
                    prev_row = result.daily_metrics.iloc[idx - 1]
                    media_used_ml = current_media_ml - prev_row.get('media_consumed', 0.0)
                    new_flasks = max(0, current_flasks - int(prev_row.get('flask_count', 0)))
                
                daily_pipettes = current_flasks
                daily_tips = current_flasks * 2
                
                cost_media_day = (media_used_ml / 500.0) * cost_media_bottle
                cost_flasks_day = new_flasks * cost_flask_unit
                cost_pipettes_day = daily_pipettes * cost_pipette_unit
                cost_tips_day = daily_tips * cost_tip_unit
                
                chart_data.append({
                    "Day": day,
                    "Media": cost_media_day,
                    "Flasks": cost_flasks_day,
                    "Pipettes": cost_pipettes_day,
                    "Tips": cost_tips_day
                })
            
            # Add final day with vials
            final_day = result.summary.get("duration_days", len(result.daily_metrics))
            chart_data.append({
                "Day": final_day,
                "Media": 0.0,
                "Flasks": 0.0,
                "Pipettes": 0.0,
                "Tips": 0.0,
                "Vials": qty_vials * cost_vial_unit
            })
            
            df_chart = pd.DataFrame(chart_data)
            
            # Create stacked bar chart
            fig_daily = go.Figure()
            
            categories = ["Media", "Flasks", "Pipettes", "Tips"]
            if "Vials" in df_chart.columns:
                categories.append("Vials")
            
            colors = {
                "Media": "#4CAF50",
                "Flasks": "#2196F3",
                "Pipettes": "#FF9800",
                "Tips": "#9C27B0",
                "Vials": "#F44336"
            }
            
            for category in categories:
                if category in df_chart.columns:
                    fig_daily.add_trace(go.Bar(
                        name=category,
                        x=df_chart['Day'],
                        y=df_chart[category],
                        marker_color=colors.get(category, "#607D8B")
                    ))
            
            fig_daily.update_layout(
                barmode='stack',
                height=350,
                margin=dict(t=20, b=40, l=40, r=20),
                xaxis_title="Day",
                yaxis_title="Cost (USD)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig_daily, use_container_width=True)
            
            # --- NEW: Detailed Itemization ---
            st.markdown("### 📋 Detailed Itemization")
            detailed_items = []
            
            # Day 0: Coating (if needed)
            if coating_needed:
                 detailed_items.append({
                    "Day": 0,
                    "Item": coating_name,
                    "Quantity": 1,
                    "Unit Cost": f"${cost_coating_unit:.2f}",
                    "Total Cost": f"${cost_coating_unit:.2f}"
                })

            prev_media = 0.0
            prev_flasks = 0
            
            for idx, row in result.daily_metrics.iterrows():
                day = int(row['day'])
                current_media_ml = row.get('media_consumed', 0.0)
                current_flasks = int(row.get('flask_count', 0))
                
                # Calculate deltas
                media_used_ml = current_media_ml - prev_media
                new_flasks = max(0, current_flasks - prev_flasks)
                
                # Daily consumables inference
                daily_pipettes = current_flasks
                daily_tips = current_flasks * 2
                
                # Media
                if media_used_ml > 0:
                     cost = (media_used_ml / 500.0) * cost_media_bottle
                     detailed_items.append({
                        "Day": day,
                        "Item": f"Media ({media_name})",
                        "Quantity": f"{media_used_ml:.1f} mL",
                        "Unit Cost": f"${cost_media_bottle:.2f}/500mL",
                        "Total Cost": f"${cost:.2f}"
                    })
                
                # Flasks
                if new_flasks > 0:
                    detailed_items.append({
                        "Day": day,
                        "Item": "T75 Flasks",
                        "Quantity": new_flasks,
                        "Unit Cost": f"${cost_flask_unit:.2f}",
                        "Total Cost": f"${new_flasks * cost_flask_unit:.2f}"
                    })
                    
                # Pipettes & Tips
                if daily_pipettes > 0:
                     detailed_items.append({
                        "Day": day,
                        "Item": "Serological Pipettes (10mL)",
                        "Quantity": daily_pipettes,
                        "Unit Cost": f"${cost_pipette_unit:.2f}",
                        "Total Cost": f"${daily_pipettes * cost_pipette_unit:.2f}"
                    })
                if daily_tips > 0:
                     detailed_items.append({
                        "Day": day,
                        "Item": "Pipette Tips (1000uL)",
                        "Quantity": daily_tips,
                        "Unit Cost": f"${cost_tip_unit:.2f}",
                        "Total Cost": f"${daily_tips * cost_tip_unit:.2f}"
                    })
                
                prev_media = current_media_ml
                prev_flasks = current_flasks

            # Final Day Items (Harvest)
            final_day = result.summary.get("duration_days", len(result.daily_metrics))
            
            # Vials
            detailed_items.append({
                "Day": final_day,
                "Item": "Cryovials (1.8mL)",
                "Quantity": qty_vials,
                "Unit Cost": f"${cost_vial_unit:.2f}",
                "Total Cost": f"${qty_vials * cost_vial_unit:.2f}"
            })
            
            # PBS
            detailed_items.append({
                "Day": final_day,
                "Item": "PBS (500mL)",
                "Quantity": qty_pbs,
                "Unit Cost": f"${cost_pbs_unit:.2f}",
                "Total Cost": f"${qty_pbs * cost_pbs_unit:.2f}"
            })
            
            # Dissociation
            detailed_items.append({
                "Day": final_day,
                "Item": dissociation_name,
                "Quantity": qty_dissociation,
                "Unit Cost": f"${cost_dissociation_unit:.2f}",
                "Total Cost": f"${qty_dissociation * cost_dissociation_unit:.2f}"
            })
            
            st.dataframe(pd.DataFrame(detailed_items), use_container_width=True)

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
            cell_line = st.selectbox("Cell Line", ["U2OS", "HepG2", "A549", "iPSC"], key="posh_sim_cell_line")
            
        with col2:
            st.subheader("Vendor Vial Specs")
            initial_cells = st.number_input("Initial Cells", value=1.0e6, format="%.1e", key="posh_initial_cells")
            vendor_lot = st.text_input("Vendor Lot", value="LOT-2025-X", key="posh_vendor_lot")
            
        with col3:
            st.subheader("Banking Targets")
            target_vials = st.number_input("Target MCB Vials", value=10, min_value=10, max_value=100, key="posh_target_vials")
            
        st.divider()
        run_sim = st.button("▶️ Simulate MCB Generation", type="primary", key="posh_run_mcb_sim")

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
                _render_mcb_result(result, pricing) # PASS PRICING
    else:
        st.info("Configure settings in the sidebar and click 'Simulate MCB Generation' to start.")

import plotly.graph_objects as go

def _render_mcb_result(result, pricing):
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
        _render_resources(result, pricing) # PASS PRICING
        
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
                    selected_mcb_label = st.selectbox("Source MCB Vial", available_mcb_vials, key="posh_wcb_source_vial")
                else:
                    st.warning("No available MCB vials. Run Phase 1 to generate more.")
                    selected_mcb_label = None
                
            with wcb_col2:
                target_wcb_vials = st.number_input("Target WCB Vials", value=10, min_value=10, max_value=500, key="posh_wcb_target_vials")
                
            with wcb_col3:
                st.write("") # Spacer
                st.write("")
                run_wcb_sim = st.button("▶️ Simulate WCB Generation", type="primary", disabled=not selected_mcb_label, key="posh_run_wcb_sim")
                
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
                
                st.success(f"WCB Simulation complete for {source_vial.vial_id}! (Refresh to see updated vial list)")

        # Display WCB Results
        if st.session_state.wcb_results:
            st.subheader("WCB Results")
            wcb_keys = list(st.session_state.wcb_results.keys())
            wcb_tabs = st.tabs(wcb_keys)
            
            for i, key in enumerate(wcb_keys):
                with wcb_tabs[i]:
                    result = st.session_state.wcb_results[key]
                    _render_wcb_result(result, pricing) # PASS PRICING

def _render_wcb_result(result, pricing):
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
        _render_resources(result, pricing) # PASS PRICING
