import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math
from datetime import datetime
import graphviz

from cell_os.simulation.mcb_wrapper import simulate_mcb_generation, VendorVialSpec
from cell_os.simulation.wcb_wrapper import simulate_wcb_generation, MCBVialSpec
from cell_os.simulation.titration_wrapper import simulate_titration
from cell_os.simulation.library_banking_wrapper import simulate_library_banking
from cell_os.cell_line_database import get_cell_line_profile
from cell_os.workflows import WorkflowBuilder
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.unit_ops.base import VesselLibrary
from cell_os.simulation.utils import MockInventory

# Import reusable components
from dashboard_app.utils import download_button
from dashboard_app.components.campaign_visualizers import (
    render_lineage,
    render_unit_ops_table,
    render_titration_resources,
    get_item_cost,
    get_item_pack_price,
    get_item_name,
    PricingInventory
)


@st.cache_resource(show_spinner=False)
def _cached_mcb_simulation(
    cell_line: str,
    vendor_name: str,
    initial_cells: float,
    lot_number: str,
    vial_id: str,
    target_vials: int,
    cells_per_vial: float,
    random_seed: int,
):
    spec = VendorVialSpec(
        cell_line=cell_line,
        vendor_name=vendor_name,
        initial_cells=initial_cells,
        lot_number=lot_number,
        vial_id=vial_id,
    )
    return simulate_mcb_generation(
        spec,
        target_vials=target_vials,
        cells_per_vial=cells_per_vial,
        random_seed=random_seed,
    )


@st.cache_resource(show_spinner=False)
def _cached_wcb_simulation(
    cell_line: str,
    vial_id: str,
    passage_number: int,
    cells_per_vial: float,
    viability: float,
    target_vials: int,
    random_seed: int,
):
    spec = MCBVialSpec(
        cell_line=cell_line,
        vial_id=vial_id,
        passage_number=passage_number,
        cells_per_vial=cells_per_vial,
        viability=viability,
    )
    return simulate_wcb_generation(
        spec,
        target_vials=target_vials,
        cells_per_vial=cells_per_vial,
        random_seed=random_seed,
    )


@st.cache_data(show_spinner=False)
def _cached_titration_simulation(
    cell_line: str,
    true_titer_tu_ml: float,
    target_transduction_efficiency: float,
    cells_per_well: int,
    replicates: int,
    random_seed: int,
):
    return simulate_titration(
        cell_line=cell_line,
        true_titer_tu_ml=true_titer_tu_ml,
        target_transduction_efficiency=target_transduction_efficiency,
        cells_per_well=cells_per_well,
        replicates=replicates,
        random_seed=random_seed,
    )


@st.cache_data(show_spinner=False)
def _cached_library_banking_simulation(
    cell_line: str,
    library_size: int,
    fitted_titer_tu_ml: float,
    optimal_moi: float,
    representation: int,
    target_cells_per_grna: int,
    num_screens: int,
    random_seed: int,
):
    return simulate_library_banking(
        cell_line=cell_line,
        library_size=library_size,
        fitted_titer_tu_ml=fitted_titer_tu_ml,
        optimal_moi=optimal_moi,
        representation=representation,
        target_cells_per_grna=target_cells_per_grna,
        num_screens=num_screens,
        random_seed=random_seed,
    )


def _render_simulation_resources(result, pricing, workflow_type="MCB", unique_key=None):
    """
    Render resource usage and BOM based on simulation results.
    
    This function contains specific logic for MCB/WCB simulation metrics
    that is distinct from the generic BOM rendering.
    """
    # Create a unique suffix for keys
    key_suffix = f"_{unique_key}" if unique_key else f"_{result.cell_line}"
    
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
    cost_media_bottle = get_item_pack_price(pricing, media_id, 50.0)
    media_name = get_item_name(pricing, media_id, f"{media_id} (500mL)")
    
    cost_dissociation_unit = get_item_cost(pricing, dissociation_id, 45.0)
    dissociation_name = get_item_name(pricing, dissociation_id, f"{dissociation_id} (100mL)")
    
    cost_coating_unit = 0.0
    coating_name = ""
    if coating_id:
        cost_coating_unit = get_item_cost(pricing, coating_id, 350.0)
        coating_name = get_item_name(pricing, coating_id, coating_id)
    
    # Get freezing parameters
    freezing_media_id = "cryostor_cs10"  # Default
    vial_type_id = "micronic_tube"  # Default updated to 0.75mL Micronic
    freezing_volume_ml = 0.35  # Default updated to 0.35mL for all cells
    
    if profile:
        if hasattr(profile, 'freezing_media') and profile.freezing_media:
            freezing_media_id = profile.freezing_media
        if hasattr(profile, 'vial_type') and profile.vial_type:
            vial_type_id = profile.vial_type
        if hasattr(profile, 'freezing_volume_ml') and profile.freezing_volume_ml:
            freezing_volume_ml = profile.freezing_volume_ml
    
    cost_freezing_media = get_item_cost(pricing, freezing_media_id, 150.0)
    freezing_media_name = get_item_name(pricing, freezing_media_id, freezing_media_id)
    
    # Define coating_needed for later use
    coating_needed = (coating_id is not None)

    # Standard items
    cost_vial_unit = get_item_cost(pricing, vial_type_id, 5.0)
    vial_name = get_item_name(pricing, vial_type_id, vial_type_id)
    cost_flask_unit = get_item_cost(pricing, "t75_flask", 4.24)
    cost_pbs_unit = get_item_cost(pricing, "dpbs", 0.0364)
    cost_pipette_unit = get_item_cost(pricing, "pipette_10ml", 1.26)
    cost_tip_unit = get_item_cost(pricing, "pipette_tip_1000ul_filter", 0.143)
    
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
        st.plotly_chart(fig_pie, use_container_width=True, key=f"cost_breakdown_{workflow_type}{key_suffix}")
        
    with c_col2:
        st.markdown("**Daily Labor Load**")
        if not result.daily_metrics.empty and "staff_hours" in result.daily_metrics.columns:
            fig_bar = go.Figure(data=[
                go.Bar(name='Staff Hours', x=result.daily_metrics['day'], y=result.daily_metrics['staff_hours']),
                go.Bar(name='BSC Hours', x=result.daily_metrics['day'], y=result.daily_metrics['bsc_hours'])
            ])
            fig_bar.update_layout(barmode='group', height=300, margin=dict(t=0, b=0, l=0, r=0),
                                 legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_bar, use_container_width=True, key=f"labor_load_{workflow_type}{key_suffix}")
        else:
            st.info("Daily labor data not available.")

    st.divider()
    
    # 5. Consumables Bill of Materials
    st.subheader("Consumables Bill of Materials 📦")
    
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
    media_unit_price = get_item_cost(pricing, media_id, 0.814)  # $/mL
    freezing_media_unit_price = get_item_cost(pricing, freezing_media_id, 4.0)  # $/mL
    pbs_unit_price = get_item_cost(pricing, "dpbs", 0.0364)  # $/mL
    dissociation_unit_price = get_item_cost(pricing, dissociation_id, 0.22)  # $/mL
    vial_unit_price = get_item_cost(pricing, vial_type_id, 0.5)  # $/unit
    flask_unit_price = get_item_cost(pricing, "t75_flask", 4.24)  # $/unit
    pipette_unit_price = get_item_cost(pricing, "serological_pipette_10ml", 1.26)  # $/unit
    tip_unit_price = get_item_cost(pricing, "pipette_tip_1000ul_filter", 0.143)  # $/unit
    coating_unit_price = get_item_cost(pricing, coating_id, 50.0) if coating_id else 0  # $/mL
    
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
    
    # Always show Daily Breakdown (removed view toggle)
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
            # Only if media was consumed (feed/passage) or flasks changed (passage)
            if media_used_ml > 0.1 or new_flasks > 0:
                daily_pipettes = current_flasks
                daily_tips = current_flasks * 2  # 2 tips per operation
            else:
                daily_pipettes = 0
                daily_tips = 0
            
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
            cost_pbs_per_ml = get_item_cost(pricing, "dpbs", 0.04)
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
            
            if media_used_ml > 0.1 or new_flasks > 0:
                daily_pipettes = current_flasks
                daily_tips = current_flasks * 2
            else:
                daily_pipettes = 0
                daily_tips = 0
            
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
        
        # Add final day with harvest/freeze consumables
        final_day = result.summary.get("duration_days", len(result.daily_metrics))
        
        # Calculate harvest/freeze consumables
        chart_data.append({
            "Day": final_day,
            "Media": 0.0,
            "Flasks": 0.0,
            "Pipettes": 0.0,
            "Tips": 0.0,
            "Vials": qty_vials * cost_vial_unit,
            "Freezing Media": cost_freezing_media_total,
            "PBS": cost_pbs_total,
            "Dissociation": cost_dissociation_total
        })
        
        df_chart = pd.DataFrame(chart_data)
        
        # Create stacked bar chart
        fig_daily = go.Figure()
        
        categories = ["Coating", "Media", "Flasks", "Pipettes", "Tips", "Vials", "Freezing Media", "PBS", "Dissociation"]
        
        colors = {
            "Coating": "#795548",
            "Media": "#4CAF50",
            "Flasks": "#2196F3",
            "Pipettes": "#FF9800",
            "Tips": "#9C27B0",
            "Vials": "#F44336",
            "Freezing Media": "#E91E63",
            "PBS": "#00BCD4",
            "Dissociation": "#FFC107"
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
        
        st.plotly_chart(fig_daily, use_container_width=True, key="daily_cost_breakdown")
        
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
            cost_pbs_per_ml = get_item_cost(pricing, "dpbs", 0.04)
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
            if media_used_ml > 0.1 or new_flasks > 0:
                daily_pipettes = current_flasks
                daily_tips = current_flasks * 2
            else:
                daily_pipettes = 0
                daily_tips = 0
            
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
                    "Unit Cost": f"${cost_flask_unit:.2f}/flask",
                    "Total Cost": f"${new_flasks * cost_flask_unit:.2f}"
                })
                
            # Pipettes & Tips
            if daily_pipettes > 0:
                 detailed_items.append({
                    "Day": day,
                    "Item": "Serological Pipettes (10mL)",
                    "Quantity": daily_pipettes,
                    "Unit Cost": f"${cost_pipette_unit:.2f}/pipette",
                    "Total Cost": f"${daily_pipettes * cost_pipette_unit:.2f}"
                })
            if daily_tips > 0:
                 detailed_items.append({
                    "Day": day,
                    "Item": "Pipette Tips (1000uL)",
                    "Quantity": daily_tips,
                    "Unit Cost": f"${cost_tip_unit:.2f}/tip",
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
            "Unit Cost": f"${cost_vial_unit:.2f}/vial",
            "Total Cost": f"${qty_vials * cost_vial_unit:.2f}"
        })
        
        # Freezing Media
        detailed_items.append({
            "Day": final_day,
            "Item": f"{freezing_media_name}",
            "Quantity": f"{qty_freezing_media_ml:.1f} mL",
            "Unit Cost": f"${freezing_media_unit_price:.2f}/mL",
            "Total Cost": f"${cost_freezing_media_total:.2f}"
        })
        
        # PBS
        detailed_items.append({
            "Day": final_day,
            "Item": f"PBS ({qty_pbs_ml:.0f}mL)",
            "Quantity": f"{qty_pbs_ml:.0f} mL",
            "Unit Cost": f"${pbs_unit_price * 500:.2f}/500mL",
            "Total Cost": f"${cost_pbs_total:.2f}"
        })
        
        # Dissociation
        detailed_items.append({
            "Day": final_day,
            "Item": dissociation_name,
            "Quantity": qty_dissociation_ml,
            "Unit Cost": f"${dissociation_unit_price:.3f}/mL",
            "Total Cost": f"${qty_dissociation_ml * cost_dissociation_unit:.2f}"
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
            
            # Add Total column
            pivot["Total"] = pivot.sum(axis=1)
            
            # Sort by Total Cost descending
            pivot = pivot.sort_values("Total", ascending=False)
            
            st.dataframe(pivot.style.format("${:.2f}"), use_container_width=True)
        
    # Store workflow and cell_line in result for later use in tabs
    result._workflow_type = workflow_type
    result._cell_line = cell_line
    result._num_vials = num_vials


def render_posh_campaign_manager(df, pricing):
    """Render the POSH Campaign Manager tab."""
    st.header("🧬 POSH Campaign Simulation")
    st.markdown("""
    Simulate the full multi-cell-line POSH campaign.
    **Phase 1: Master Cell Bank (MCB) Generation**
    """)
    
    # --- Configuration Controls ---
    with st.expander("Campaign Configuration", expanded=True):
        st.subheader("Campaign Settings")
        cell_line = st.selectbox("Cell Line", ["U2OS", "HepG2", "A549", "iPSC"], key="posh_sim_cell_line")
        
        # Hardcoded defaults (UI removed per user request)
        initial_cells = 1.0e6
        vendor_lot = "LOT-2025-X"
        target_vials = 10
            
        st.divider()
        run_sim = st.button("▶️ Simulate MCB Generation", type="primary", key="posh_run_mcb_sim")

    # --- Main Content ---
    
    # Initialize session state for results if not present
    if "posh_mcb_results" not in st.session_state:
        st.session_state.posh_mcb_results = {}
        
    if run_sim:
        with st.spinner(f"Simulating MCB generation for {cell_line}..."):
            seed = st.session_state.get("posh_mcb_seed", 0) + 1
            st.session_state["posh_mcb_seed"] = seed
            result = _cached_mcb_simulation(
                cell_line=cell_line,
                vendor_name="ATCC",
                initial_cells=initial_cells,
                lot_number=vendor_lot,
                vial_id=f"VENDOR-{cell_line}-001",
                target_vials=target_vials,
                cells_per_vial=1e6,
                random_seed=seed,
            )
            st.session_state.posh_mcb_results[cell_line] = result
            
    # Display MCB Results
    # Display MCB Results
    if cell_line in st.session_state.posh_mcb_results:
        result = st.session_state.posh_mcb_results[cell_line]
        
        if result.success:
                st.success(f"✅ MCB Generated: {len(result.vials)} vials of {result.cell_line}")
                _render_mcb_result(result, pricing)
                download_button(
                    pd.DataFrame([v.__dict__ for v in result.vials]),
                    "⬇️ Download MCB Vials (CSV)",
                    f"{cell_line.lower()}_mcb_vials.csv",
                )
        else:
            st.error(f"❌ Simulation Failed: {result.summary.get('failed_reason', 'Unknown')}")

    st.divider()
    st.markdown("""
    **Phase 2: Working Cell Bank (WCB) Generation**
    Select a generated MCB vial to expand into a Working Cell Bank.
    """)

    if not st.session_state.posh_mcb_results:
        st.info("⚠️ Please complete Phase 1 (MCB Generation) above to proceed to Phase 2.")
    else:
        # Initialize session state for WCB results and consumed vials
        if "posh_wcb_results" not in st.session_state:
            st.session_state.posh_wcb_results = {}
        if "posh_consumed_mcb_vials" not in st.session_state:
            st.session_state.posh_consumed_mcb_vials = set()
        
        with st.expander("WCB Configuration", expanded=True):
            wcb_col1, wcb_col2, wcb_col3 = st.columns(3)
        
            # Get available MCB vials from results (excluding consumed ones)
            available_mcb_vials = []
            mcb_vial_map = {}
        
            for res in st.session_state.posh_mcb_results.values():
                if res.success and res.vials:
                    for v in res.vials:
                        if v.vial_id not in st.session_state.posh_consumed_mcb_vials:
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
                seed = st.session_state.get("posh_wcb_seed", 0) + 1
                st.session_state["posh_wcb_seed"] = seed
                result = _cached_wcb_simulation(
                    cell_line=source_vial.cell_line,
                    vial_id=source_vial.vial_id,
                    passage_number=source_vial.passage_number,
                    cells_per_vial=source_vial.cells_per_vial,
                    viability=source_vial.viability,
                    target_vials=target_wcb_vials,
                    random_seed=seed,
                )
                st.session_state.posh_wcb_results[source_vial.vial_id] = result
            
                # Mark vial as consumed
                st.session_state.posh_consumed_mcb_vials.add(source_vial.vial_id)
            
                st.success(f"WCB Simulation complete for {source_vial.vial_id}! (Refresh to see updated vial list)")

        # Display WCB Results
        if st.session_state.posh_wcb_results:
            st.subheader("WCB Results")
            wcb_keys = list(st.session_state.posh_wcb_results.keys())
            wcb_tabs = st.tabs(wcb_keys)
        
            for i, key in enumerate(wcb_keys):
                with wcb_tabs[i]:
                    result = st.session_state.posh_wcb_results[key]
                    _render_wcb_result(result, pricing, unique_key=key) # PASS PRICING AND KEY
                    download_button(
                        pd.DataFrame([v.__dict__ for v in result.vials]),
                        "⬇️ Download WCB Vials (CSV)",
                        f"{key.lower()}_wcb_vials.csv",
                    )

    
        # --- Phase 3: LV MOI Titration ---
        st.markdown("""
        **Phase 3: LV MOI Titration**
        Determine the optimal viral volume to achieve target transduction efficiency.
        """)
    
        from cell_os.simulation.titration_wrapper import simulate_titration
    
        with st.expander("Titration Configuration", expanded=True):
            t_col1, t_col2, t_col3, t_col4 = st.columns(4)
            with t_col1:
                titration_cell_line = st.selectbox("Cell Line", ["U2OS", "HepG2", "A549", "iPSC"], key="titration_cell_line")
            with t_col2:
                est_titer = st.number_input("Estimated Titer (TU/mL)", value=1.0e8, format="%.1e", key="titration_est_titer")
            with t_col3:
                target_eff = st.slider("Target Transduction Efficiency", 0.1, 0.9, 0.30, 0.05, key="titration_target_eff")
            with t_col4:
                st.caption("Experiment Design")
                st.text("Format: 6-well plate")
                st.text("Cells/Well: 100,000")
            
            run_titration = st.button("▶️ Simulate Titration", key="run_titration_btn")
        
        if "titration_results" not in st.session_state:
            st.session_state.titration_results = {}
        
        if run_titration:
            with st.spinner("Simulating titration experiment..."):
                seed = st.session_state.get("titration_seed_counter", 0) + 1
                st.session_state["titration_seed_counter"] = seed
                t_result = _cached_titration_simulation(
                    cell_line=titration_cell_line,
                    true_titer_tu_ml=est_titer,
                    target_transduction_efficiency=target_eff,
                    cells_per_well=100000,
                    replicates=2,
                    random_seed=seed,
                )
                st.session_state.titration_results[titration_cell_line] = t_result
            
        if titration_cell_line in st.session_state.titration_results:
            t_result = st.session_state.titration_results[titration_cell_line]
        
            if t_result.success:
                st.success(f"✅ Titration Complete for {titration_cell_line}")
            
                # Metrics
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric("Fitted Titer (TU/mL)", f"{t_result.fitted_titer_tu_ml:.2e}")
                with m2:
                    st.metric("Optimal Volume", f"{t_result.recommended_vol_ul:.2f} µL", help=f"For {target_eff:.0%} Efficiency")
                with m3:
                    st.metric("Target MOI", f"{t_result.target_moi:.2f}")
                with m4:
                    st.metric("Model Fit (R²)", f"{t_result.r_squared:.3f}")
                
                # Plot
                # Create smooth curve for model
                x_smooth = np.linspace(0, t_result.data['volume_ul'].max() * 1.1, 100)
                # BFP = A * (1 - exp(-MOI)) = A * (1 - exp(-(Vol*Titer)/Cells))
                # Titer in TU/uL = fitted_titer_tu_ml / 1000
                titer_ul = t_result.fitted_titer_tu_ml / 1000.0
                y_smooth = t_result.model.max_infectivity * (1.0 - np.exp(-(x_smooth * titer_ul) / 100000))
                
                fig = go.Figure()
                
                # Data points
                fig.add_trace(go.Scatter(
                    x=t_result.data['volume_ul'],
                    y=t_result.data['fraction_bfp'],
                    mode='markers',
                    name='Observed Data',
                    marker=dict(color='blue', size=10, opacity=0.6)
                ))
                
                # Model curve
                fig.add_trace(go.Scatter(
                    x=x_smooth,
                    y=y_smooth,
                    mode='lines',
                    name='Fitted Poisson Model',
                    line=dict(color='red', width=2)
                ))
                
                # Target point
                fig.add_trace(go.Scatter(
                    x=[t_result.recommended_vol_ul],
                    y=[target_eff],
                    mode='markers',
                    name='Optimal Point',
                    marker=dict(color='green', size=15, symbol='star')
                ))
                
                fig.update_layout(
                    title=f"Titration Curve: {titration_cell_line}",
                    xaxis_title="Viral Volume (µL)",
                    yaxis_title="Transduction Efficiency (Fraction BFP)",
                    yaxis_range=[0, 1.0],
                    height=400,
                    template="plotly_white"
                )
                
                st.plotly_chart(fig, use_container_width=True, key="titration_results")
                
                # Cost Analysis
                st.subheader("Titration Cost Analysis 💰")
                render_titration_resources(t_result, pricing)
                download_button(
                    t_result.data,
                    "⬇️ Download Titration Data (CSV)",
                    f"{titration_cell_line.lower()}_titration.csv",
                )
                
            else:
                st.error(f"❌ Titration Failed: {t_result.error_message}")
        
        # --- Phase 4: Library Transduction & Banking ---
        st.divider()
        st.markdown("""
        **Phase 4: Library Transduction & Banking**
        Create a bank of library-transduced cells for POSH screens.
        """)
        
        from cell_os.simulation.library_banking_wrapper import simulate_library_banking
        
        with st.expander("Library Banking Configuration", expanded=True):
            lb_col1, lb_col2, lb_col3, lb_col4 = st.columns(4)
            with lb_col1:
                lb_cell_line = st.selectbox("Cell Line", ["U2OS", "HepG2", "A549", "iPSC"], key="lb_cell_line")
            with lb_col2:
                library_size = st.number_input("Library Size (# gRNAs)", value=1000, step=100, key="library_size")
            with lb_col3:
                representation = st.number_input("Representation (cells/gRNA)", value=1000, step=100, key="representation")
            with lb_col4:
                target_cells_per_grna = st.number_input("Target cells/gRNA (screen)", value=750, step=50, key="target_cells_per_grna")
            
            # Check if titration results are available
            if lb_cell_line in st.session_state.titration_results:
                t_result = st.session_state.titration_results[lb_cell_line]
                st.success(f"✓ Using titration results: Titer = {t_result.fitted_titer_tu_ml:.2e} TU/mL, MOI = {t_result.target_moi:.2f}")
                fitted_titer = t_result.fitted_titer_tu_ml
                optimal_moi = t_result.target_moi
            else:
                st.warning(f"⚠️ No titration results for {lb_cell_line}. Using default values.")
                fitted_titer = 1.0e8
                optimal_moi = 0.3
            
            run_library_banking = st.button("▶️ Simulate Library Banking", key="run_library_banking_btn")
        
        if "library_banking_results" not in st.session_state:
            st.session_state.library_banking_results = {}
        
        if run_library_banking:
            with st.spinner("Simulating library banking workflow..."):
                seed = st.session_state.get("library_banking_seed_counter", 0) + 1
                st.session_state["library_banking_seed_counter"] = seed
                lb_result = _cached_library_banking_simulation(
                    cell_line=lb_cell_line,
                    library_size=library_size,
                    fitted_titer_tu_ml=fitted_titer,
                    optimal_moi=optimal_moi,
                    representation=representation,
                    target_cells_per_grna=target_cells_per_grna,
                    num_screens=4,
                    random_seed=seed,
                )
                st.session_state.library_banking_results[lb_cell_line] = lb_result
        
        if lb_cell_line in st.session_state.library_banking_results:
            lb_result = st.session_state.library_banking_results[lb_cell_line]
            
            if lb_result.success:
                st.success(f"✅ Library Banking Simulation Complete for {lb_cell_line}")
                
                # Metrics
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric("Transduction Cells", f"{lb_result.transduction_cells_needed:,}")
                with m2:
                    st.metric("Viral Volume", f"{lb_result.viral_volume_ml:.1f} mL")
                with m3:
                    st.metric("Transduction Flasks", f"{lb_result.transduction_flasks}")
                with m4:
                    st.metric("Total Vials Banked", f"{lb_result.cryo_vials_needed}")
                
                # Banking details
                st.subheader("Banking Strategy")
                b1, b2, b3 = st.columns(3)
                with b1:
                    st.metric("Post-Selection Cells", f"{lb_result.post_selection_cells:,}", 
                             help=f"{lb_result.selection_survival_rate*100:.0f}% survival")
                with b2:
                    st.metric("Expansion Needed", f"{lb_result.expansion_fold_needed:.1f}×")
                with b3:
                    st.metric("Vials per Screen", f"{lb_result.vials_per_screen} vials", 
                             help=f"{lb_result.cells_per_vial/1e6:.0f}M cells/vial")
                
                # Workflow display
                st.subheader("Workflow Steps")
                if lb_result.workflow:
                    workflow_steps = []
                    step_num = 1
                    for process in lb_result.workflow.processes:
                        for op in process.ops:
                            workflow_steps.append({
                                "Step": step_num,
                                "Operation": op.name,
                                "Category": op.category,
                                "Material Cost": f"${op.material_cost_usd:.2f}",
                                "Instrument Cost": f"${op.instrument_cost_usd:.2f}"
                            })
                            step_num += 1
                    
                    st.dataframe(pd.DataFrame(workflow_steps), use_container_width=True)
                    
                    # Total cost
                    total_mat = sum(op.material_cost_usd for process in lb_result.workflow.processes for op in process.ops)
                    total_inst = sum(op.instrument_cost_usd for process in lb_result.workflow.processes for op in process.ops)
                    total_cost = total_mat + total_inst
                    
                    st.metric("Total Workflow Cost", f"${total_cost:,.2f}", 
                             help=f"Materials: ${total_mat:,.2f} | Instruments: ${total_inst:,.2f}")
            else:
                st.error(f"❌ Library Banking Failed: {lb_result.error_message}")
            
            
            
            
    # Display Results


    # --- Phase 5: Assay Development (tBHP Dose Finding) ---
    st.divider()
    st.markdown("""
    **Phase 5: Assay Development (tBHP Dose Finding)**
    Determine the optimal tBHP dose for oxidative stress assays.
    """)
    
    from cell_os.tbhp_dose_finder import TBHPDoseFinder, TBHPOptimizationCriteria
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
    
    with st.expander("Assay Development Configuration", expanded=True):
        ad_col1, ad_col2, ad_col3 = st.columns(3)
        
        with ad_col1:
            ad_cell_line = st.selectbox("Cell Line", ["A549", "U2OS", "HepG2", "iPSC"], key="ad_cell_line")
        with ad_col2:
            min_viability = st.slider("Min Viability", 0.0, 1.0, 0.70, 0.05, key="ad_min_viability")
        with ad_col3:
            target_signal = st.number_input("Target Signal (RFU)", value=200.0, key="ad_target_signal")
        
        run_assay_dev = st.button("▶️ Run Dose Finding", key="run_assay_dev_btn")
    
    if "assay_dev_results" not in st.session_state:
        st.session_state.assay_dev_results = {}
    
    if run_assay_dev:
        with st.spinner(f"Finding optimal tBHP dose for {ad_cell_line}..."):
            vm = BiologicalVirtualMachine()
            criteria = TBHPOptimizationCriteria(
                min_viability=min_viability,
                target_cellrox_signal=target_signal,
                min_segmentation_quality=0.80
            )
            finder = TBHPDoseFinder(vm, criteria)
            
            result = finder.run_dose_finding(
                cell_line=ad_cell_line,
                dose_range=(0.0, 500.0),
                n_doses=12
            )
            
            st.session_state.assay_dev_results[ad_cell_line] = result
            
            # Store optimal dose for Phase 6
            if "optimal_dose_results" not in st.session_state:
                st.session_state.optimal_dose_results = {}
            st.session_state.optimal_dose_results[ad_cell_line] = result.optimal_dose_uM
    
    if ad_cell_line in st.session_state.assay_dev_results:
        result = st.session_state.assay_dev_results[ad_cell_line]
        
        if result.status == "success":
            st.success(f"✅ Optimal Dose Found: **{result.optimal_dose_uM:.1f} µM**")
        elif result.status == "suboptimal":
            st.warning(f"⚠️ Suboptimal Dose: **{result.optimal_dose_uM:.1f} µM**")
        else:
            st.error(f"❌ Failed: {result.status}")
        
        # Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Viability", f"{result.viability_at_optimal:.1%}")
        m2.metric("CellROX Signal", f"{result.cellrox_signal_at_optimal:.1f}")
        m3.metric("Segmentation", f"{result.segmentation_quality_at_optimal:.1%}")
        
        # Plot
        import altair as alt
        df_res = result.dose_response_curve
        df_res["Signal (Norm)"] = df_res["cellrox_signal"] / df_res["cellrox_signal"].max()
        
        df_plot = df_res.melt(
            id_vars=["dose_uM"],
            value_vars=["viability", "segmentation_quality", "Signal (Norm)"],
            var_name="Metric",
            value_name="Value"
        )
        
        chart = alt.Chart(df_plot).mark_line(point=True).encode(
            x=alt.X("dose_uM", title="tBHP Dose (µM)"),
            y=alt.Y("Value", title="Normalized Value (0-1)"),
            color=alt.Color("Metric", scale={
                "domain": ["viability", "segmentation_quality", "Signal (Norm)"],
                "range": ["#4CAF50", "#2196F3", "#FF5722"]
            }),
            tooltip=["dose_uM", "Metric", "Value"]
        ).properties(height=300).interactive()
        
        rule = alt.Chart(pd.DataFrame({'x': [result.optimal_dose_uM]})).mark_rule(
            color='black', strokeDash=[5, 5]
        ).encode(x='x')
        
        st.altair_chart(chart + rule, use_container_width=True, key="assay_dev_dose_curve")


    # --- Phase 6: POSH Screen Execution ---
    st.divider()
    st.markdown("""
    **Phase 6: POSH Screen Execution**
    Thaw library bank, treat with compound, and image for phenotypic readout.
    """)
    
    from cell_os.simulation.posh_screen_wrapper import simulate_posh_screen, CELL_PAINTING_FEATURES
    
    with st.expander("Screen Configuration", expanded=True):
        s_col1, s_col2, s_col3, s_col4 = st.columns(4)
        with s_col1:
            screen_cell_line = st.selectbox("Cell Line", ["A549", "U2OS", "HepG2", "iPSC"], key="screen_cell_line")
        with s_col2:
            treatment = st.selectbox("Treatment", ["tBHP", "Staurosporine", "Tunicamycin"], key="screen_treatment")
        with s_col3:
            # Get optimal dose from Assay Development
            if "optimal_dose_results" in st.session_state and screen_cell_line in st.session_state.optimal_dose_results:
                dose = st.session_state.optimal_dose_results[screen_cell_line]
                st.metric("Dose (µM)", f"{dose:.1f}", help=f"Optimal dose from Assay Development for {screen_cell_line}")
            else:
                # Allow manual override during development
                use_default = st.toggle("Use Default Dose (40µM)", value=True, key="use_default_dose",
                                       help="Toggle off to manually enter dose")
                if use_default:
                    dose = 40.0
                    st.metric("Dose (µM)", f"{dose:.1f}", help="Default development dose")
                else:
                    dose = st.number_input("Manual Dose (µM)", value=40.0, step=5.0, key="manual_dose")
                st.info(f"💡 Tip: Run Assay Development to find optimal dose for {screen_cell_line}")
        with s_col4:
            # Check if library banking results exist to pre-fill
            default_lib_size = 1000
            if screen_cell_line in st.session_state.get("library_banking_results", {}):
                res = st.session_state.library_banking_results[screen_cell_line]
                if res.success:
                    default_lib_size = res.library_size
                    st.success(f"✓ Linked to {screen_cell_line} Bank ({default_lib_size} genes)")
            
            screen_lib_size = st.number_input("Library Size", value=default_lib_size, key="screen_lib_size")
        
        # Feature selection row
        st.markdown("**Cell Painting Feature to Analyze:**")
        feature_options = {k: v["name"] for k, v in CELL_PAINTING_FEATURES.items()}
        selected_feature_name = st.selectbox(
            "Morphological Feature",
            options=list(feature_options.values()),
            key="screen_feature",
            help="Select which Cell Painting morphological feature to analyze"
        )
        # Reverse lookup to get feature key
        selected_feature = [k for k, v in feature_options.items() if v == selected_feature_name][0]
            
        run_screen = st.button("▶️ Run POSH Screen", key="run_screen_btn")
        
    if "screen_results" not in st.session_state:
        st.session_state.screen_results = {}
        
    if run_screen:
        with st.spinner(f"Running POSH Screen on {screen_cell_line} with {treatment}..."):
            seed = st.session_state.get("screen_seed_counter", 0) + 1
            st.session_state["screen_seed_counter"] = seed
            
            s_result = simulate_posh_screen(
                cell_line=screen_cell_line,
                treatment=treatment,
                dose_uM=dose,
                library_size=screen_lib_size,
                feature=selected_feature,
                random_seed=seed
            )
            st.session_state.screen_results[screen_cell_line] = s_result
            
    if screen_cell_line in st.session_state.screen_results:
        s_result = st.session_state.screen_results[screen_cell_line]
        
        if s_result.success:
            st.success(f"✅ Screen Complete: {len(s_result.hit_list)} hits identified")
            
            # Tabs for results
            tab_volcano, tab_hits, tab_raw, tab_channels, tab_embed, tab_ops = st.tabs(["Volcano Plot 🌋", "Hit List 🎯", "Raw Measurements 📊", "Channel Intensities 🔬", "Embeddings 🕸️", "Operations ⚙️"])
            
            with tab_embed:
                if hasattr(s_result, "embeddings") and not s_result.embeddings.empty:
                    st.markdown("### Deep Learning Embeddings (128-d)")
                    st.markdown("High-dimensional phenotypic profiles generated by a simulated Deep Learning encoder (e.g., DINO). Each cell is represented as a 128-dimensional vector.")
                    
                    # 1. UMAP Plot
                    st.markdown("#### Phenotypic Landscape (UMAP)")
                    
                    # Merge with volcano data to get phenotype info
                    if not s_result.volcano_data.empty:
                        df_umap = pd.merge(s_result.projection_2d, s_result.volcano_data[["Gene", "Log2FoldChange", "P_Value"]], on="Gene")
                        
                        # Create a "Phenotype" column for coloring
                        df_umap["Phenotype"] = "Control-like"
                        # Identify hits (using same criteria as volcano plot usually does, or just checking hit list)
                        hit_genes = s_result.hit_list["Gene"].tolist() if not s_result.hit_list.empty else []
                        df_umap.loc[df_umap["Gene"].isin(hit_genes), "Phenotype"] = "Hit"
                        
                        # Create numeric size column
                        df_umap["Size"] = 2.0
                        df_umap.loc[df_umap["Phenotype"] == "Hit", "Size"] = 5.0
                        
                        fig_umap = px.scatter(
                            df_umap,
                            x="UMAP_1",
                            y="UMAP_2",
                            color="Phenotype",
                            hover_data=["Gene", "Log2FoldChange"],
                            title="UMAP Projection of Phenotypic Space",
                            color_discrete_map={"Control-like": "lightgray", "Hit": "#FF4B4B"},
                            opacity=0.7,
                            size="Size", 
                            size_max=10,
                            symbol="Phenotype"
                        )
                        st.plotly_chart(fig_umap, use_container_width=True, key="umap_plot")
                        
                        st.info("💡 **Interpretation:** In this 2D projection of the 128-dimensional space, points that cluster together share similar phenotypes. 'Hits' (red) form distinct clusters away from the 'Control-like' population, indicating they have perturbed the cell state in a specific way.")
                        
                        # Mechanism of Action Classification
                        st.markdown("---")
                        st.markdown("#### 🧬 Mechanism of Action (MoA) Classification")
                        
                        if not s_result.hit_list.empty and not s_result.embeddings.empty:
                            # Calculate stress vector in embedding space
                            # Get control genes (non-hits)
                            control_genes = s_result.volcano_data[~s_result.volcano_data["Gene"].isin(hit_genes)]["Gene"].tolist()
                            
                            # Get embeddings for controls and calculate mean (baseline)
                            control_embeds = s_result.embeddings[s_result.embeddings["Gene"].isin(control_genes)]
                            embed_cols = [c for c in control_embeds.columns if c.startswith("DIM_")]
                            baseline_embed = control_embeds[embed_cols].mean().values
                            
                            # Calculate mean of all genes (stressed state)
                            all_embed_mean = s_result.embeddings[embed_cols].mean().values
                            
                            # Stress vector: direction from baseline to stressed
                            stress_vector = all_embed_mean - baseline_embed
                            stress_vector_norm = stress_vector / (np.linalg.norm(stress_vector) + 1e-10)
                            
                            # For each hit, calculate its direction relative to stress vector
                            hit_embeds = s_result.embeddings[s_result.embeddings["Gene"].isin(hit_genes)]
                            
                            moa_data = []
                            for _, row in hit_embeds.iterrows():
                                gene = row["Gene"]
                                gene_embed = row[embed_cols].values
                                
                                # Vector from baseline to this gene
                                gene_vector = gene_embed - baseline_embed
                                gene_vector_norm = gene_vector / (np.linalg.norm(gene_vector) + 1e-10)
                                
                                # Dot product: measures alignment with stress vector
                                # +1 = same direction (enhancer), -1 = opposite (suppressor), 0 = orthogonal
                                alignment = np.dot(gene_vector_norm, stress_vector_norm)
                                
                                # Magnitude: how far from baseline
                                magnitude = np.linalg.norm(gene_vector)
                                
                                # Classify
                                if alignment > 0.3:
                                    moa = "Enhancer"
                                    color = "#FF4B4B"
                                elif alignment < -0.3:
                                    moa = "Suppressor"
                                    color = "#00CC66"
                                else:
                                    moa = "Orthogonal"
                                    color = "#FFA500"
                                
                                moa_data.append({
                                    "Gene": gene,
                                    "MoA": moa,
                                    "Alignment": alignment,
                                    "Magnitude": magnitude,
                                    "Color": color
                                })
                            
                            df_moa = pd.DataFrame(moa_data)
                            
                            # Merge with UMAP for visualization
                            df_umap_moa = pd.merge(df_umap[df_umap["Phenotype"] == "Hit"], df_moa, on="Gene")
                            
                            # MoA-colored UMAP
                            fig_moa = px.scatter(
                                df_umap_moa,
                                x="UMAP_1",
                                y="UMAP_2",
                                color="MoA",
                                hover_data=["Gene", "Alignment", "Magnitude"],
                                title="Mechanism of Action Classification",
                                color_discrete_map={"Enhancer": "#FF4B4B", "Suppressor": "#00CC66", "Orthogonal": "#FFA500"},
                                opacity=0.8,
                                size="Magnitude",
                                size_max=15
                            )
                            st.plotly_chart(fig_moa, use_container_width=True, key="moa_plot")
                            
                            # Summary table
                            col_moa1, col_moa2, col_moa3 = st.columns(3)
                            
                            with col_moa1:
                                st.markdown("**🔴 Enhancers**")
                                st.caption("Amplify stress phenotype")
                                enhancers = df_moa[df_moa["MoA"] == "Enhancer"].sort_values("Alignment", ascending=False).head(5)
                                if not enhancers.empty:
                                    st.dataframe(enhancers[["Gene", "Alignment"]], hide_index=True)
                                else:
                                    st.info("None found")
                            
                            with col_moa2:
                                st.markdown("**🟢 Suppressors**")
                                st.caption("Rescue/protect from stress")
                                suppressors = df_moa[df_moa["MoA"] == "Suppressor"].sort_values("Alignment").head(5)
                                if not suppressors.empty:
                                    st.dataframe(suppressors[["Gene", "Alignment"]], hide_index=True)
                                else:
                                    st.info("None found")
                            
                            with col_moa3:
                                st.markdown("**🟠 Orthogonal**")
                                st.caption("Novel/distinct phenotype")
                                orthogonal = df_moa[df_moa["MoA"] == "Orthogonal"].sort_values("Magnitude", ascending=False).head(5)
                                if not orthogonal.empty:
                                    st.dataframe(orthogonal[["Gene", "Magnitude"]], hide_index=True)
                                else:
                                    st.info("None found")
                            
                            st.info("💡 **How it works:** We calculate a 'stress vector' in the 128-dimensional embedding space (from healthy baseline → stressed state). Each hit is classified based on whether it moves **with** the stress (Enhancer), **against** it (Suppressor), or in a **different direction** (Orthogonal/Novel).")
                    
                    
                    # 2. Embedding Heatmap
                    st.markdown("#### Embedding Fingerprints (Top Hits vs Controls)")
                    
                    if not s_result.hit_list.empty:
                        # Get top 10 hits and 10 random controls
                        top_hits = s_result.hit_list.head(10)["Gene"].tolist()
                        controls = s_result.volcano_data[~s_result.volcano_data["Gene"].isin(top_hits)].sample(min(10, len(s_result.volcano_data)))["Gene"].tolist()
                        
                        selected_genes = top_hits + controls
                        # Filter embeddings
                        df_selected_embed = s_result.embeddings[s_result.embeddings["Gene"].isin(selected_genes)].set_index("Gene")
                        # Reorder to group hits and controls
                        df_selected_embed = df_selected_embed.reindex(selected_genes)
                        
                        # Show heatmap
                        fig_heat = px.imshow(
                            df_selected_embed.iloc[:, :50], # Show first 50 dims for clarity
                            labels=dict(x="Embedding Dimension", y="Gene", color="Value"),
                            title="Embedding Vectors (First 50 Dimensions)",
                            aspect="auto",
                            color_continuous_scale="Viridis"
                        )
                        st.plotly_chart(fig_heat, use_container_width=True, key="embed_heatmap")
                    
                else:
                    st.info("No embedding data available. Run a new simulation to generate embeddings.")
            
            with tab_channels:
                if hasattr(s_result, "channel_intensities") and not s_result.channel_intensities.empty:
                    st.markdown("### Cell Painting Channel Intensities")
                    st.markdown("Raw fluorescence intensity values (AFU) from the 5-channel Cell Painting panel. These represent what the microscope actually sees before segmentation.")
                    
                    # Summary metrics
                    cols = st.columns(5)
                    channels = ["Hoechst", "ConA", "Phalloidin", "WGA", "MitoProbe"]
                    targets = ["Nucleus", "ER", "Actin", "Golgi", "Mito"]
                    colors = ["#4169E1", "#32CD32", "#FF4500", "#FFD700", "#8B0000"]
                    
                    for i, (chan, target) in enumerate(zip(channels, targets)):
                        with cols[i]:
                            if chan in s_result.channel_intensities.columns:
                                mean_val = s_result.channel_intensities[chan].mean()
                                st.metric(f"{chan} ({target})", f"{mean_val:.0f}")
                            
                    # Correlation plot
                    st.markdown("### Channel Correlations")
                    
                    col_x, col_y = st.columns(2)
                    with col_x:
                        x_axis = st.selectbox("X Axis Channel", channels, index=4, key="chan_x") # MitoProbe default
                    with col_y:
                        y_axis = st.selectbox("Y Axis Channel", channels, index=0, key="chan_y") # Hoechst default
                        
                    fig_corr = px.scatter(
                        s_result.channel_intensities,
                        x=x_axis,
                        y=y_axis,
                        hover_data=["Gene"],
                        title=f"Channel Correlation: {x_axis} vs {y_axis}",
                        opacity=0.6,
                        color_discrete_sequence=["#5F9EA0"]
                    )
                    st.plotly_chart(fig_corr, use_container_width=True, key="chan_corr_plot")
                    
                    # Distributions
                    st.markdown("### Intensity Distributions")
                    
                    # Melt for plotting
                    df_melt = s_result.channel_intensities.melt(id_vars=["Gene"], value_vars=channels)
                    
                    fig_dist = px.histogram(
                        df_melt,
                        x="value",
                        color="variable",
                        barmode="overlay",
                        title="Fluorescence Intensity Distributions",
                        labels={"value": "Intensity (AFU)", "variable": "Channel"},
                        opacity=0.6,
                        color_discrete_map=dict(zip(channels, colors))
                    )
                    st.plotly_chart(fig_dist, use_container_width=True, key="chan_dist_plot")
                    
                    st.info("💡 **Interpretation:** Shifts in intensity distributions indicate global cellular responses. For example, reduced MitoProbe intensity indicates mitochondrial depolarization (loss of membrane potential).")
                    
                    # Digital Cell Viewer
                    st.markdown("---")
                    st.markdown("### 🔬 Digital Cell Viewer")
                    st.markdown("Visualize what a representative cell looks like based on the simulated channel intensities.")
                    
                    col_sel, col_view = st.columns([1, 2])
                    
                    with col_sel:
                        # Select a gene to view
                        # Default to a hit if available
                        default_gene = s_result.hit_list.iloc[0]["Gene"] if not s_result.hit_list.empty else s_result.channel_intensities.iloc[0]["Gene"]
                        selected_gene = st.selectbox("Select Gene to Visualize", s_result.channel_intensities["Gene"].unique(), index=list(s_result.channel_intensities["Gene"]).index(default_gene))
                        
                        # Get data for this gene
                        gene_data = s_result.channel_intensities[s_result.channel_intensities["Gene"] == selected_gene].iloc[0]
                        
                        st.markdown("**Channel Values:**")
                        st.code(f"""
Hoechst (Nuc): {gene_data['Hoechst']:.0f}
ConA (ER):     {gene_data['ConA']:.0f}
Phalloidin:    {gene_data['Phalloidin']:.0f}
WGA (Golgi):   {gene_data['WGA']:.0f}
MitoProbe:     {gene_data['MitoProbe']:.0f}
                        """)
                        
                        # Normalize for display (approximate max values based on simulation)
                        norm_vals = {
                            "Hoechst": min(1.0, gene_data['Hoechst'] / 45000),
                            "ConA": min(1.0, gene_data['ConA'] / 25000),
                            "Phalloidin": min(1.0, gene_data['Phalloidin'] / 20000),
                            "WGA": min(1.0, gene_data['WGA'] / 18000),
                            "MitoProbe": min(1.0, gene_data['MitoProbe'] / 50000),
                        }
                        
                    with col_view:
                        # Draw synthetic cell using matplotlib
                        import matplotlib.pyplot as plt
                        from matplotlib.patches import Circle, Ellipse
                        import matplotlib.patheffects as path_effects
                        
                        fig, ax = plt.subplots(figsize=(6, 6), facecolor='black')
                        ax.set_facecolor('black')
                        ax.set_xlim(-10, 10)
                        ax.set_ylim(-10, 10)
                        ax.axis('off')
                        
                        # 1. Actin (Phalloidin) - Red/Orange - Cell Body Outline
                        # Irregular shape simulated by multiple ellipses
                        alpha_act = norm_vals["Phalloidin"] * 0.6
                        cell_body = Ellipse((0, 0), 16, 14, angle=15, color='#FF4500', alpha=alpha_act)
                        ax.add_patch(cell_body)
                        
                        # 2. ER (ConA) - Green - Perinuclear cloud
                        alpha_er = norm_vals["ConA"] * 0.5
                        er_cloud = Ellipse((0.5, 0.5), 12, 10, angle=-10, color='#32CD32', alpha=alpha_er)
                        ax.add_patch(er_cloud)
                        
                        # 3. Mitochondria (MitoProbe) - Deep Red/Cyan - Scattered points
                        # We draw random points to simulate mito network
                        alpha_mito = norm_vals["MitoProbe"]
                        num_mito = int(50 * alpha_mito) + 10
                        mx = np.random.normal(0, 4, num_mito)
                        my = np.random.normal(0, 4, num_mito)
                        ax.scatter(mx, my, c='#00FFFF', s=15, alpha=alpha_mito*0.8, edgecolors='none')
                        
                        # 4. Golgi (WGA) - Yellow - Near nucleus
                        alpha_wga = norm_vals["WGA"] * 0.7
                        golgi = Ellipse((2, 2), 3, 2, angle=45, color='#FFD700', alpha=alpha_wga)
                        ax.add_patch(golgi)
                        
                        # 5. Nucleus (Hoechst) - Blue - Center
                        alpha_nuc = norm_vals["Hoechst"]
                        # Size also depends on intensity (condensation)
                        # In our sim, higher intensity = smaller area (condensation)
                        # So we invert the size relationship slightly for visual effect
                        nuc_size = 6.0 * (1.0 - (alpha_nuc - 0.5) * 0.5) 
                        nucleus = Circle((0, 0), nuc_size/2, color='#4169E1', alpha=0.9)
                        # Add glow
                        nucleus.set_path_effects([path_effects.withStroke(linewidth=3, foreground='#4169E1', alpha=0.3)])
                        ax.add_patch(nucleus)
                        
                        st.pyplot(fig)
                        st.caption(f"Synthetic Composite Image: {selected_gene}")
                        
                else:
                    st.info("No channel intensity data available. Run a new simulation to generate channel data.")
            
            with tab_volcano:
                # Volcano Plot
                feature_info = CELL_PAINTING_FEATURES[s_result.selected_feature]
                fig_vol = px.scatter(
                    s_result.volcano_data,
                    x="Log2FoldChange",
                    y="NegLog10P",
                    color="Category",
                    hover_data=["Gene"],
                    title=f"Cell Painting POSH Screen: {screen_cell_line} + {treatment} ({dose}µM)<br><sub>Feature: {feature_info['name']}</sub>",
                    color_discrete_map={
                        "Non-targeting": "lightgrey",
                        "Enhancer": "#FF5722",
                        "Suppressor": "#2196F3"
                    },
                    opacity=0.7,
                    labels={"Log2FoldChange": f"{feature_info['name']} Effect ({feature_info['unit']})"}
                )
                fig_vol.add_hline(y=-np.log10(0.05), line_dash="dash", line_color="grey", annotation_text="p=0.05")
                
                st.plotly_chart(fig_vol, use_container_width=True, key="volcano_plot")
                
                # Add interpretation
                st.info(f"""**Interpretation:** 
                - 🔴 **Enhancers** (right): Genes that increase {feature_info['name'].lower()} when knocked out
                - 🔵 **Suppressors** (left): Genes that decrease {feature_info['name'].lower()} when knocked out
                - ⚪ **Non-targeting**: Genes with no significant effect on this phenotype
                """)
                
            with tab_hits:
                st.dataframe(s_result.hit_list, use_container_width=True)
                download_button(
                    s_result.hit_list,
                    "⬇️ Download Hits (CSV)",
                    f"{screen_cell_line}_hits.csv"
                )
            
            with tab_raw:
                st.subheader("🔬 Raw Imaging Measurements")
                st.markdown(f"""Showing raw fluorescence measurements from MitoTracker channel.  
                **Treatment:** {treatment} ({dose}µM)""")
                
                # Display raw data table
                with st.expander("View Raw Data Table", expanded=False):
                    st.dataframe(s_result.raw_measurements, use_container_width=True)
                
                # Summary statistics - dynamic based on feature
                st.markdown("### Summary Statistics")
                
                if s_result.selected_feature == "mitochondrial_fragmentation":
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric(
                            "Mean Intensity",
                            f"{s_result.raw_measurements['Mito_Mean_Intensity'].mean():.0f}",
                            help="Average MitoTracker fluorescence intensity"
                        )
                    with col2:
                        st.metric(
                            "Avg Object Count",
                            f"{s_result.raw_measurements['Mito_Object_Count'].mean():.1f}",
                            help="Average number of mitochondrial objects per cell"
                        )
                    with col3:
                        st.metric(
                            "Avg Total Area",
                            f"{s_result.raw_measurements['Mito_Total_Area'].mean():.0f}",
                            help="Average total mitochondrial area (pixels)"
                        )
                    with col4:
                        if "Fragmentation_Index" in s_result.raw_measurements.columns:
                            st.metric(
                                "Avg Fragmentation",
                                f"{s_result.raw_measurements['Fragmentation_Index'].mean():.2f}",
                                help="Calculated from: Object Count / (Total Area / 100)"
                            )
                
                elif s_result.selected_feature == "nuclear_size":
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric(
                            "Mean Area",
                            f"{s_result.raw_measurements['Nucleus_Area'].mean():.1f} µm²",
                            help="Average nuclear area"
                        )
                    with col2:
                        st.metric(
                            "Mean Perimeter",
                            f"{s_result.raw_measurements['Nucleus_Perimeter'].mean():.1f} µm",
                            help="Average nuclear perimeter"
                        )
                    with col3:
                        st.metric(
                            "Mean Intensity",
                            f"{s_result.raw_measurements['Nucleus_Mean_Intensity'].mean():.0f}",
                            help="Average nuclear staining intensity"
                        )
                    with col4:
                        st.metric(
                            "Avg Form Factor",
                            f"{s_result.raw_measurements['Nucleus_Form_Factor'].mean():.2f}",
                            help="Nuclear circularity (1.0 = perfect circle)"
                        )
                
                # Scatter plots showing relationships - dynamic based on feature
                st.markdown("### Raw Measurement Relationships")
                
                if s_result.selected_feature == "mitochondrial_fragmentation":
                    # Fragmentation calculation visualization
                    if "Fragmentation_Index" in s_result.raw_measurements.columns:
                        fig_scatter = px.scatter(
                            s_result.raw_measurements,
                            x="Mito_Total_Area",
                            y="Mito_Object_Count",
                            color="Fragmentation_Index",
                            hover_data=["Gene"],
                            title="Fragmentation Calculation: Object Count vs Total Area",
                            labels={
                                "Mito_Total_Area": "Total Mitochondrial Area (pixels)",
                                "Mito_Object_Count": "Number of Mito Objects",
                                "Fragmentation_Index": "Fragmentation"
                            },
                            color_continuous_scale="RdYlBu_r"
                        )
                        st.plotly_chart(fig_scatter, use_container_width=True, key="raw_scatter_frag")
                        
                        st.info("💡 **How Fragmentation is Calculated:** Higher object count + lower total area = higher fragmentation (red). Healthy tubular networks have fewer objects spread over larger area (blue).")
                    
                    # Intensity vs Fragmentation
                    if "Fragmentation_Index" in s_result.raw_measurements.columns:
                        fig_intensity = px.scatter(
                            s_result.raw_measurements,
                            x="Fragmentation_Index",
                            y="Mito_Mean_Intensity",
                            hover_data=["Gene"],
                            title="Mitochondrial Health: Fragmentation vs Intensity",
                            labels={
                                "Fragmentation_Index": "Fragmentation Index",
                                "Mito_Mean_Intensity": "Mean Intensity (MitoTracker)"
                            },
                            opacity=0.6
                        )
                        st.plotly_chart(fig_intensity, use_container_width=True, key="raw_scatter_intensity")
                        
                        st.info("💡 **Biological Interpretation:** Fragmented mitochondria (high fragmentation) often show reduced membrane potential (low intensity), indicating dysfunction.")
                
                elif s_result.selected_feature == "nuclear_size":
                    # Nuclear size vs shape
                    fig_nuclear = px.scatter(
                        s_result.raw_measurements,
                        x="Nucleus_Area",
                        y="Nucleus_Form_Factor",
                        color="Nucleus_Mean_Intensity",
                        hover_data=["Gene"],
                        title="Nuclear Morphology: Size vs Shape Regularity",
                        labels={
                            "Nucleus_Area": "Nuclear Area (µm²)",
                            "Nucleus_Form_Factor": "Form Factor (Circularity)",
                            "Nucleus_Mean_Intensity": "Intensity"
                        },
                        color_continuous_scale="Viridis"
                    )
                    st.plotly_chart(fig_nuclear, use_container_width=True, key="raw_scatter_nuclear")
                    
                    st.info("💡 **How Nuclear Size is Measured:** Nucleus area is calculated from segmented nuclear masks. Form factor near 1.0 indicates round/regular nuclei.")
                    
                    # Area vs Intensity (condensation proxy)
                    fig_condensation = px.scatter(
                        s_result.raw_measurements,
                        x="Nucleus_Area",
                        y="Nucleus_Mean_Intensity",
                        hover_data=["Gene"],
                        title="Nuclear Condensation: Size vs Intensity",
                        labels={
                            "Nucleus_Area": "Nuclear Area (µm²)",
                            "Nucleus_Mean_Intensity": "Mean Intensity (DNA stain)"
                        },
                        opacity=0.6
                    )
                    st.plotly_chart(fig_condensation, use_container_width=True, key="raw_scatter_condensation")
                    
                    st.info("💡 **Biological Interpretation:** Smaller nuclei with higher intensity often indicate chromatin condensation, a marker of apoptosis or stress.")
                
                elif s_result.selected_feature == "er_stress_score":
                    # ER stress metrics (placeholder - would need ER-specific measurements)
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric(
                            "Mito Texture Variance",
                            f"{s_result.raw_measurements['Mito_Texture_Variance'].mean():.0f}",
                            help="Mitochondrial texture heterogeneity (ER stress proxy)"
                        )
                    with col2:
                        st.metric(
                            "Nuclear Intensity",
                            f"{s_result.raw_measurements['Nucleus_Mean_Intensity'].mean():.0f}",
                            help="Nuclear condensation (stress indicator)"
                        )
                    with col3:
                        st.metric(
                            "Nuclear Form Factor",
                            f"{s_result.raw_measurements['Nucleus_Form_Factor'].mean():.2f}",
                            help="Nuclear shape regularity"
                        )
                    with col4:
                        st.metric(
                            "Mito Intensity",
                            f"{s_result.raw_measurements['Mito_Mean_Intensity'].mean():.0f}",
                            help="Mitochondrial health indicator"
                        )
                    
                    # ER stress visualization - texture vs nuclear changes
                    fig_er_stress = px.scatter(
                        s_result.raw_measurements,
                        x="Mito_Texture_Variance",
                        y="Nucleus_Mean_Intensity",
                        color="Nucleus_Form_Factor",
                        hover_data=["Gene"],
                        title="ER Stress Response: Mitochondrial Texture vs Nuclear Changes",
                        labels={
                            "Mito_Texture_Variance": "Mitochondrial Texture Variance",
                            "Nucleus_Mean_Intensity": "Nuclear Intensity",
                            "Nucleus_Form_Factor": "Form Factor"
                        },
                        color_continuous_scale="Reds"
                    )
                    st.plotly_chart(fig_er_stress, use_container_width=True, key="raw_scatter_er_stress")
                    
                    st.info("💡 **How ER Stress is Measured:** ER stress causes mitochondrial dysfunction (increased texture variance) and nuclear changes (altered intensity and shape). This is a composite readout.")
                    
                    # Secondary plot: Mito health overview
                    fig_mito_health = px.scatter(
                        s_result.raw_measurements,
                        x="Mito_Mean_Intensity",
                        y="Mito_Texture_Variance",
                        hover_data=["Gene"],
                        title="Mitochondrial Health Overview",
                        labels={
                            "Mito_Mean_Intensity": "Mean Intensity (Membrane Potential)",
                            "Mito_Texture_Variance": "Texture Variance (Heterogeneity)"
                        },
                        opacity=0.6
                    )
                    st.plotly_chart(fig_mito_health, use_container_width=True, key="raw_scatter_mito_health")
                    
                    st.info("💡 **Biological Interpretation:** ER stress disrupts protein folding, causing mitochondrial dysfunction (reduced intensity, increased heterogeneity) and nuclear stress responses.")
                
                
                
            with tab_ops:
                if s_result.workflow:
                    ops_data = []
                    total_cost = 0.0
                    for process in s_result.workflow.processes:
                        for op in process.ops:
                            cost = op.material_cost_usd + op.instrument_cost_usd
                            total_cost += cost
                            ops_data.append({
                                "Operation": op.name,
                                "Category": op.category,
                                "Cost": f"${cost:.2f}"
                            })
                    
                    st.dataframe(pd.DataFrame(ops_data), use_container_width=True)
                    st.metric("Total Screen Cost", f"${total_cost:,.2f}")
        else:
            st.error(f"❌ Screen Failed: {s_result.error_message}")



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
    
    # Tabs Layout
    tab_lineage, tab_growth, tab_resources, tab_vials, tab_quality, tab_unit_ops = st.tabs([
        "Lineage 🧬", "Growth Curve 📈", "Resources 💰", "Vials 🧪", "Quality 📉", "Unit Operations 🔬"
    ])
    
    with tab_lineage:
        render_lineage(result)
        
    with tab_growth:
        if not result.daily_metrics.empty:
            fig = px.line(result.daily_metrics, x="day", y="avg_confluence", 
                         title=f"{result.cell_line} Confluence", markers=True)
            fig.update_yaxes(tickformat=".0%")
            st.plotly_chart(fig, use_container_width=True, key=f"mcb_growth_{result.cell_line}")
        else:
            st.info("No growth data available.")
            
    with tab_resources:
        _render_simulation_resources(result, pricing, workflow_type="MCB", unique_key=result.cell_line)
        
    with tab_vials:
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
            
    with tab_quality:
        # 5. Logs
        with st.expander("Simulation Logs"):
            for log in result.logs:
                st.text(log)

        # 6. Release QC
        st.subheader("🛡️ Release Quality Control")
        st.markdown("Run post-banking QC assays to certify the bank for release.")
    
    with tab_unit_ops:
        st.markdown("### 🔬 Parameterized Unit Operations")
        
        # Rebuild workflow to get ops
        vessels = VesselLibrary()
        inventory = PricingInventory(pricing)
        ops = ParametricOps(vessels, inventory)
        builder = WorkflowBuilder(ops)
        
        try:
            workflow_type = getattr(result, '_workflow_type', 'MCB')
            cell_line = result.cell_line
            num_vials = len(result.vials)
            
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
                
            # Render table
            render_unit_ops_table(workflow)
                    
        except Exception as e:
            st.warning(f"Could not render unit ops: {e}")
        
        col_qc1, col_qc2 = st.columns([1, 2])
        with col_qc1:
            if st.button("Run Release QC Panel", key=f"run_qc_mcb_{result.cell_line}"):
                st.session_state[f"mcb_qc_run_{result.cell_line}"] = True
                
        with col_qc2:
            if st.session_state.get(f"mcb_qc_run_{result.cell_line}"):
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


def _render_wcb_result(result, pricing, unique_key):
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
    
    # Tabs Layout
    tab_lineage, tab_growth, tab_resources, tab_vials, tab_quality = st.tabs([
        "Lineage 🧬", "Expansion 📈", "Resources 💰", "Vials 🧪", "Quality 📉"
    ])
    
    with tab_lineage:
        render_lineage(result)
        
    with tab_growth:
        if not result.daily_metrics.empty:
            fig = px.line(result.daily_metrics, x="day", y="total_cells", 
                         title=f"{result.cell_line} WCB Expansion", markers=True)
            st.plotly_chart(fig, use_container_width=True, key=f"wcb_expansion_{unique_key}")
            
    with tab_resources:
        _render_simulation_resources(result, pricing, workflow_type="WCB", unique_key=unique_key)
        
    with tab_vials:
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
            
    with tab_quality:
        # 5. Logs
        with st.expander("Simulation Logs"):
            for log in result.logs:
                st.text(log)

        # 6. Release QC
        st.subheader("🛡️ Release Quality Control")
        st.markdown("Run post-banking QC assays to certify the bank for release.")
        
        col_qc1, col_qc2 = st.columns([1, 2])
        with col_qc1:
            qc_key = f"wcb_qc_run_{unique_key}"
            if st.button("Run Release QC Panel", key=f"btn_qc_{unique_key}"):
                st.session_state[qc_key] = True
                
        with col_qc2:
            if st.session_state.get(f"wcb_qc_run_{unique_key}"):
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
