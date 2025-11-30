import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from cell_os.simulation.mcb_wrapper import simulate_mcb_generation, VendorVialSpec
from cell_os.cell_line_database import get_cell_line_profile # NEW IMPORT

import plotly.graph_objects as go
import graphviz

from cell_os.workflows import WorkflowBuilder
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.unit_ops.base import VesselLibrary
from cell_os.mcb_crash import MockInventory

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

def _get_item_pack_price(pricing, item_id, default_cost=0.0):
    """Get item pack price from pricing dict."""
    if not pricing or 'items' not in pricing:
        return default_cost
    
    item = pricing['items'].get(item_id)
    if item:
        return item.get('pack_price_usd', default_cost)
    return default_cost

def _get_item_name(pricing, item_id, default_name):
    """Helper to safely get item name from pricing dict."""
    if not pricing or 'items' not in pricing:
        return default_name
    
    item = pricing['items'].get(item_id)
    if item:
        return item.get('name', default_name)
    return default_name

def _render_resources(result, pricing, workflow_type="MCB"):
    """Render resource usage and BOM."""
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
    cost_media_bottle = _get_item_pack_price(pricing, media_id, 50.0)
    media_name = _get_item_name(pricing, media_id, f"{media_id} (500mL)")
    
    cost_dissociation_unit = _get_item_cost(pricing, dissociation_id, 45.0)
    dissociation_name = _get_item_name(pricing, dissociation_id, f"{dissociation_id} (100mL)")
    
    cost_coating_unit = 0.0
    coating_name = ""
    if coating_id:
        cost_coating_unit = _get_item_cost(pricing, coating_id, 350.0)
        coating_name = _get_item_name(pricing, coating_id, coating_id)
    
    # Get freezing parameters
    freezing_media_id = "cryostor_cs10"  # Default
    vial_type_id = "cryovial_1_8ml"  # Default
    freezing_volume_ml = 1.0  # Default
    
    if profile:
        if hasattr(profile, 'freezing_media') and profile.freezing_media:
            freezing_media_id = profile.freezing_media
        if hasattr(profile, 'vial_type') and profile.vial_type:
            vial_type_id = profile.vial_type
        if hasattr(profile, 'freezing_volume_ml') and profile.freezing_volume_ml:
            freezing_volume_ml = profile.freezing_volume_ml
    
    cost_freezing_media = _get_item_cost(pricing, freezing_media_id, 150.0)
    freezing_media_name = _get_item_name(pricing, freezing_media_id, freezing_media_id)
    
    # Define coating_needed for later use
    coating_needed = (coating_id is not None)

    # Standard items
    cost_vial_unit = _get_item_cost(pricing, vial_type_id, 5.0)
    vial_name = _get_item_name(pricing, vial_type_id, vial_type_id)
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
    
    # Calculate quantities from actual simulation data
    qty_media_bottles = math.ceil(total_media / 0.5) # 500mL bottles
    qty_vials = num_vials + result.summary.get("waste_vials", 0)
    
    # Use actual max flask count from simulation instead of estimate
    if not result.daily_metrics.empty and 'flask_count' in result.daily_metrics.columns:
        qty_flasks = int(result.daily_metrics['flask_count'].max())
    else:
        qty_flasks = max(1, int(num_vials / 5)) # Fallback estimate
    
    
    # Estimate dissociation reagent based on actual passages
    # Each passage uses ~5mL of dissociation reagent per flask
    estimated_passages = max(1, int(result.summary.get("duration_days", 10) / 3)) # Passage every ~3 days
    
    # Calculate actual volumes used
    total_media_ml = total_media * 1000  # Convert L to mL
    qty_freezing_media_ml = qty_vials * freezing_volume_ml
    
    # Estimate PBS usage: ~5mL per passage for washing
    qty_pbs_ml = estimated_passages * qty_flasks * 5.0
    
    # Estimate dissociation reagent: ~5mL per passage per flask
    qty_dissociation_ml = estimated_passages * qty_flasks * 5.0
    
    # Estimate Pipettes & Tips based on usage
    estimated_feeds = int((total_media * 1000) / 15)
    qty_pipettes_10ml = estimated_feeds + (estimated_passages * 2) + 2 
    qty_tips_1000ul = estimated_feeds + (estimated_passages * 4)
    
    # Estimate coating volume if needed
    qty_coating_ml = 0
    if coating_id:
        # Estimate 2mL per flask for coating
        qty_coating_ml = qty_flasks * 2.0
    
    # Get unit prices ($/mL or $/unit) from pricing database
    media_unit_price = _get_item_cost(pricing, media_id, 0.814)  # $/mL
    freezing_media_unit_price = _get_item_cost(pricing, freezing_media_id, 4.0)  # $/mL
    pbs_unit_price = _get_item_cost(pricing, "dpbs", 0.0364)  # $/mL
    dissociation_unit_price = _get_item_cost(pricing, dissociation_id, 0.22)  # $/mL
    vial_unit_price = _get_item_cost(pricing, vial_type_id, 0.5)  # $/unit
    flask_unit_price = _get_item_cost(pricing, "t75_flask", 1.32)  # $/unit
    pipette_unit_price = _get_item_cost(pricing, "serological_pipette_10ml", 0.3)  # $/unit
    tip_unit_price = _get_item_cost(pricing, "pipette_tip_1000ul_filter", 0.143)  # $/unit
    coating_unit_price = _get_item_cost(pricing, coating_id, 50.0) if coating_id else 0  # $/mL
    
    # Calculate total costs
    cost_media_total = total_media_ml * media_unit_price
    cost_freezing_media_total = qty_freezing_media_ml * freezing_media_unit_price
    cost_pbs_total = qty_pbs_ml * pbs_unit_price
    cost_dissociation_total = qty_dissociation_ml * dissociation_unit_price
    cost_vials_total = qty_vials * vial_unit_price
    cost_flasks_total = qty_flasks * flask_unit_price
    cost_pipettes_total = qty_pipettes_10ml * pipette_unit_price
    cost_tips_total = qty_tips_1000ul * tip_unit_price
    cost_coating_total = qty_coating_ml * coating_unit_price if coating_id else 0
    
    if view_mode == "Aggregate View":
        # Build consumables list with actual volumes and costs
        consumables_data = [
            {"Item": f"{media_name} ({total_media_ml:.0f}mL)", "Quantity": f"{total_media_ml:.0f} mL", "Unit Cost": f"${media_unit_price:.3f}/mL", "Total Cost": f"${cost_media_total:.2f}"},
            {"Item": vial_name, "Quantity": qty_vials, "Unit Cost": f"${vial_unit_price:.2f}", "Total Cost": f"${cost_vials_total:.2f}"},
            {"Item": f"{freezing_media_name} ({qty_freezing_media_ml:.1f}mL)", "Quantity": f"{qty_freezing_media_ml:.1f} mL", "Unit Cost": f"${freezing_media_unit_price:.2f}/mL", "Total Cost": f"${cost_freezing_media_total:.2f}"},
            {"Item": "T75 Flasks", "Quantity": qty_flasks, "Unit Cost": f"${flask_unit_price:.2f}", "Total Cost": f"${cost_flasks_total:.2f}"},
            {"Item": "Serological Pipettes (10mL)", "Quantity": qty_pipettes_10ml, "Unit Cost": f"${pipette_unit_price:.2f}", "Total Cost": f"${cost_pipettes_total:.2f}"},
            {"Item": "Pipette Tips (1000uL)", "Quantity": qty_tips_1000ul, "Unit Cost": f"${tip_unit_price:.3f}", "Total Cost": f"${cost_tips_total:.2f}"},
            {"Item": f"PBS ({qty_pbs_ml:.0f}mL)", "Quantity": f"{qty_pbs_ml:.0f} mL", "Unit Cost": f"${pbs_unit_price:.3f}/mL", "Total Cost": f"${cost_pbs_total:.2f}"},
            {"Item": f"{dissociation_name} ({qty_dissociation_ml:.0f}mL)", "Quantity": f"{qty_dissociation_ml:.0f} mL", "Unit Cost": f"${dissociation_unit_price:.3f}/mL", "Total Cost": f"${cost_dissociation_total:.2f}"}
        ]
        
        if coating_id:
            consumables_data.append(
                {"Item": f"{coating_name} ({qty_coating_ml:.0f}mL)", "Quantity": f"{qty_coating_ml:.0f} mL", "Unit Cost": f"${coating_unit_price:.2f}/mL", "Total Cost": f"${cost_coating_total:.2f}"}
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
            
            # Add Day -1 for coating (if needed)
            if coating_needed:
                pbs_vol_ml = 12.25
                cost_pbs_per_ml = _get_item_cost(pricing, "dpbs", 0.04)
                pbs_cost = pbs_vol_ml * cost_pbs_per_ml
                
                chart_data.append({
                    "Day": -1,
                    "Media": 0.0,
                    "Flasks": cost_flask_unit,
                    "Pipettes": 2 * cost_pipette_unit,
                    "Tips": 0.0,
                    "Coating": cost_coating_unit + pbs_cost
                })
            
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
            
            categories = ["Coating", "Media", "Flasks", "Pipettes", "Tips"]
            if "Vials" in df_chart.columns:
                categories.append("Vials")
            
            colors = {
                "Coating": "#795548",
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
            
            # Day -1: Coating (if needed) - done 24hrs before thaw
            if coating_needed:
                # Flask (needed for coating)
                detailed_items.append({
                    "Day": -1,
                    "Item": "T75 Flask",
                    "Quantity": 1,
                    "Unit Cost": f"${cost_flask_unit:.2f}",
                    "Total Cost": f"${cost_flask_unit:.2f}"
                })
                
                # PBS for dilution (12.25 mL for vitronectin)
                pbs_vol_ml = 12.25
                cost_pbs_per_ml = _get_item_cost(pricing, "dpbs", 0.04)
                pbs_cost = pbs_vol_ml * cost_pbs_per_ml
                detailed_items.append({
                    "Day": -1,
                    "Item": "PBS (for coating dilution)",
                    "Quantity": f"{pbs_vol_ml:.2f} mL",
                    "Unit Cost": f"${cost_pbs_per_ml:.4f}/mL",
                    "Total Cost": f"${pbs_cost:.2f}"
                })
                
                # Coating reagent
                detailed_items.append({
                    "Day": -1,
                    "Item": coating_name,
                    "Quantity": 1,
                    "Unit Cost": f"${cost_coating_unit:.2f}",
                    "Total Cost": f"${cost_coating_unit:.2f}"
                })
                
                # Pipettes for coating
                detailed_items.append({
                    "Day": -1,
                    "Item": "Serological Pipettes (10mL)",
                    "Quantity": 2,  # One for PBS, one for coating
                    "Unit Cost": f"${cost_pipette_unit:.2f}",
                    "Total Cost": f"${2 * cost_pipette_unit:.2f}"
                })

            prev_media = 0.0
            prev_flasks = 1 if coating_needed else 0  # Account for coating flask on Day -1
            
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
                "Item": vial_name,
                "Quantity": qty_vials,
                "Unit Cost": f"${cost_vial_unit:.2f}",
                "Total Cost": f"${qty_vials * cost_vial_unit:.2f}"
            })
            
            # Freezing Media
            detailed_items.append({
                "Day": final_day,
                "Item": f"{freezing_media_name}",
                "Quantity": f"{qty_freezing_media_ml:.1f} mL",
                "Unit Cost": f"${cost_freezing_media:.2f}",
                "Total Cost": f"${cost_freezing_media:.2f}"
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
            
            df_detailed = pd.DataFrame(detailed_items)
            df_detailed["Quantity"] = df_detailed["Quantity"].astype(str)
            st.dataframe(df_detailed, use_container_width=True)
            
            # --- NEW: Daily Usage Matrix (Pivot) ---
            st.markdown("### 📊 Daily Usage Matrix ($)")
            
            pivot_data = []
            for item in detailed_items:
                # Parse cost back to float for aggregation
                try:
                    cost_str = item["Total Cost"].replace('$', '').replace(',', '')
                    cost = float(cost_str)
                    pivot_data.append({
                        "Day": f"Day {item['Day']}",
                        "Item": item["Item"],
                        "Cost": cost
                    })
                except (ValueError, AttributeError):
                    continue
            
            if pivot_data:
                df_pivot_source = pd.DataFrame(pivot_data)
                pivot = df_pivot_source.pivot_table(
                    index="Item", 
                    columns="Day", 
                    values="Cost", 
                    aggfunc="sum", 
                    fill_value=0.0
                )
                
                # Sort columns (Day 0, Day 1, ...)
                # Simple string sort works for Day 0-9, but Day 10 comes before Day 2
                # Let's try to sort naturally if possible, or just leave as is
                
                # Add Total column
                pivot["Total"] = pivot.sum(axis=1)
                
                # Sort by Total Cost descending
                pivot = pivot.sort_values("Total", ascending=False)
                
                st.dataframe(pivot.style.format("${:.2f}"), use_container_width=True)
            
            # --- NEW: Parameterized Unit Ops ---
            st.markdown("### 🔬 Parameterized Unit Operations")
            
            # Rebuild workflow to get ops
            # Rebuild workflow to get ops
            vessels = VesselLibrary()
            
            # Use PricingInventory to get real prices from DB
            class PricingInventory:
                def __init__(self, pricing_data):
                    self.pricing = pricing_data
                    
                def get_price(self, item_id: str) -> float:
                    if not self.pricing or 'items' not in self.pricing:
                        return 0.0
                    item = self.pricing['items'].get(item_id)
                    if item:
                        # Prefer unit_price_usd
                        return item.get('unit_price_usd', 0.0)
                    return 0.0
            
            inventory = PricingInventory(pricing)
            ops = ParametricOps(vessels, inventory)
            builder = WorkflowBuilder(ops)
            
            try:
                if workflow_type == "MCB":
                    workflow = builder.build_master_cell_bank(
                        flask_size="flask_T75",
                        cell_line=cell_line,
                        target_vials=num_vials,
                        cells_per_vial=1e6 
                    )
                else:
                    workflow = builder.build_working_cell_bank(
                        flask_size="flask_T75",
                        cell_line=cell_line,
                        target_vials=num_vials,
                        cells_per_vial=1e6
                    )
                    
                # Column headers
                col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                with col1:
                    st.markdown("**Operation**")
                with col2:
                    st.markdown("**Time**")
                with col3:
                    st.markdown("**Cost**")
                with col4:
                    st.markdown("**Labor**")
                with col5:
                    st.markdown("**Category**")
                st.divider()
                
                # Extract ops with expandable sub-steps
                for process in workflow.processes:
                    for idx, op in enumerate(process.ops):
                        # Calculate active labor time (exclude incubation)
                        labor_min = 0.0
                        if op.sub_steps:
                            for step in op.sub_steps:
                                if step.category != "incubation":
                                    labor_min += step.time_score
                        else:
                            # If no sub-steps, assume all is labor unless category is incubation
                            if op.category != "incubation":
                                labor_min = op.time_score
                        
                        # Labor load: staff_attention (1-5 scale) * active time in hours
                        labor_hours = (op.staff_attention * labor_min) / 60.0
                        
                        # Main operation summary
                        col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                        with col1:
                            st.markdown(f"**{idx+1}. {op.name}**")
                        with col2:
                            st.text(f"{op.time_score} min")
                        with col3:
                            st.text(f"${op.material_cost_usd + op.instrument_cost_usd:.2f}")
                        with col4:
                            st.text(f"{labor_hours:.2f}h")
                        with col5:
                            st.text(op.category)
                        
                        # Show sub-steps if they exist
                        if op.sub_steps:
                            with st.expander(f"🔍 View {len(op.sub_steps)} Atomic Steps"):
                                sub_steps_data = []
                                for sub_step in op.sub_steps:
                                    sub_steps_data.append({
                                        "Step": sub_step.name,
                                        "Category": sub_step.category,
                                        "Time (min)": sub_step.time_score,
                                        "Material Cost": f"${sub_step.material_cost_usd:.2f}",
                                        "Instrument Cost": f"${sub_step.instrument_cost_usd:.2f}"
                                    })
                                st.dataframe(pd.DataFrame(sub_steps_data), use_container_width=True)
                        
                        st.divider()
                        
            except Exception as e:
                st.warning(f"Could not render unit ops: {e}")

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
    
    # Create Radio for persistent view state
    view_selection = st.radio(
        "Select View", 
        ["🧬 Biology & Quality", "💰 Resources & Cost"], 
        horizontal=True,
        label_visibility="collapsed",
        key=f"mcb_view_{result.cell_line}"
    )
    
    if view_selection == "🧬 Biology & Quality":
        # 2. Plots
        st.subheader("Growth Curve")
        if not result.daily_metrics.empty:
            fig = px.line(result.daily_metrics, x="day", y="avg_confluence", 
                         title=f"{result.cell_line} Confluence", markers=True)
            fig.update_yaxes(tickformat=".0%")
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
            
    elif view_selection == "💰 Resources & Cost":
        _render_resources(result, pricing, workflow_type="MCB") # PASS PRICING
        
    # 5. Logs (outside tabs)
    with st.expander("Simulation Logs"):
        for log in result.logs:
            st.text(log)

    # 6. Release QC
    st.divider()
    st.subheader("🛡️ Release Quality Control")
    st.markdown("Run post-banking QC assays to certify the bank for release.")
    
    col_qc1, col_qc2 = st.columns([1, 2])
    with col_qc1:
        if st.button("Run Release QC Panel", key="run_qc_wcb"):
            st.session_state.wcb_qc_run = True
            
    with col_qc2:
        if st.session_state.get("wcb_qc_run"):
            # Calculate QC costs
            vessels = VesselLibrary()
            inventory = MockInventory()
            ops = ParametricOps(vessels, inventory)
            builder = WorkflowBuilder(ops)
            qc_workflow = builder.build_bank_release_qc(cell_line=result.cell_line)
            
            qc_data = []
            total_qc_cost = 0.0
            
            for process in qc_workflow.processes:
                for op in process.ops:
                    cost = op.material_cost_usd + op.instrument_cost_usd
                    total_qc_cost += cost
                    qc_data.append({
                        "Assay": op.name,
                        "Type": op.category,
                        "Cost": f"${cost:.2f}"
                    })
            
            st.success("✅ QC Panel Passed")
            st.dataframe(pd.DataFrame(qc_data), use_container_width=True)
            st.metric("Total QC Cost", f"${total_qc_cost:.2f}")
            
    # 6. Release QC
    st.divider()
    st.subheader("🛡️ Release Quality Control")
    st.markdown("Run post-banking QC assays to certify the bank for release.")
    
    col_qc1, col_qc2 = st.columns([1, 2])
    with col_qc1:
        if st.button("Run Release QC Panel", key="run_qc_mcb"):
            st.session_state.mcb_qc_run = True
            
    with col_qc2:
        if st.session_state.get("mcb_qc_run"):
            # Calculate QC costs
            vessels = VesselLibrary()
            inventory = MockInventory()
            ops = ParametricOps(vessels, inventory)
            builder = WorkflowBuilder(ops)
            qc_workflow = builder.build_bank_release_qc(cell_line=result.cell_line)
            
            qc_data = []
            total_qc_cost = 0.0
            
            for process in qc_workflow.processes:
                for op in process.ops:
                    cost = op.material_cost_usd + op.instrument_cost_usd
                    total_qc_cost += cost
                    qc_data.append({
                        "Assay": op.name,
                        "Type": op.category,
                        "Cost": f"${cost:.2f}"
                    })
            
            st.success("✅ QC Panel Passed")
            st.dataframe(pd.DataFrame(qc_data), use_container_width=True)
            st.metric("Total QC Cost", f"${total_qc_cost:.2f}")

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
    
    # Create Radio for persistent view state
    view_selection_wcb = st.radio(
        "Select View", 
        ["🧬 Biology & Quality", "💰 Resources & Cost"], 
        horizontal=True,
        label_visibility="collapsed",
        key=f"wcb_view_{result.cell_line}_{id(result)}"
    )
    
    if view_selection_wcb == "🧬 Biology & Quality":
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
            
    elif view_selection_wcb == "💰 Resources & Cost":
        _render_resources(result, pricing, workflow_type="WCB") # PASS PRICING

    # 5. Logs (outside tabs)
    with st.expander("Simulation Logs"):
        for log in result.logs:
            st.text(log)

    # 6. Release QC
    st.divider()
    st.subheader("🛡️ Release Quality Control")
    st.markdown("Run post-banking QC assays to certify the bank for release.")
    
    col_qc1, col_qc2 = st.columns([1, 2])
    with col_qc1:
        if st.button("Run Release QC Panel", key="run_qc_wcb"):
            st.session_state.wcb_qc_run = True
            
    with col_qc2:
        if st.session_state.get("wcb_qc_run"):
            # Calculate QC costs
            vessels = VesselLibrary()
            inventory = MockInventory()
            ops = ParametricOps(vessels, inventory)
            builder = WorkflowBuilder(ops)
            qc_workflow = builder.build_bank_release_qc(cell_line=result.cell_line)
            
            qc_data = []
            total_qc_cost = 0.0
            
            for process in qc_workflow.processes:
                for op in process.ops:
                    cost = op.material_cost_usd + op.instrument_cost_usd
                    total_qc_cost += cost
                    qc_data.append({
                        "Assay": op.name,
                        "Type": op.category,
                        "Cost": f"${cost:.2f}"
                    })
            
            st.success("✅ QC Panel Passed")
            st.dataframe(pd.DataFrame(qc_data), use_container_width=True)
            st.metric("Total QC Cost", f"${total_qc_cost:.2f}")
