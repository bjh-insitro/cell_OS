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
        st.plotly_chart(fig_pie, width="stretch", key=f"cost_breakdown_{workflow_type}{key_suffix}")
        
    with c_col2:
        st.markdown("**Daily Labor Load**")
        if not result.daily_metrics.empty and "staff_hours" in result.daily_metrics.columns:
            fig_bar = go.Figure(data=[
                go.Bar(name='Staff Hours', x=result.daily_metrics['day'], y=result.daily_metrics['staff_hours']),
                go.Bar(name='BSC Hours', x=result.daily_metrics['day'], y=result.daily_metrics['bsc_hours'])
            ])
            fig_bar.update_layout(barmode='group', height=300, margin=dict(t=0, b=0, l=0, r=0),
                                 legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_bar, width="stretch", key=f"labor_load_{workflow_type}{key_suffix}")
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
        st.dataframe(df_daily, width="stretch")
        
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
        
        st.plotly_chart(fig_daily, width="stretch", key="daily_cost_breakdown")
        
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
        st.dataframe(df_detailed, width="stretch")
        
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
            
            st.dataframe(pivot.style.format("${:.2f}"), width="stretch")
        
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
                
                st.plotly_chart(fig, width="stretch", key="titration_results")
                
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
                    
                    st.dataframe(pd.DataFrame(workflow_steps), width="stretch")
                    
                    # Total cost
                    total_mat = sum(op.material_cost_usd for process in lb_result.workflow.processes for op in process.ops)
                    total_inst = sum(op.instrument_cost_usd for process in lb_result.workflow.processes for op in process.ops)
                    total_cost = total_mat + total_inst
                    
                    st.metric("Total Workflow Cost", f"${total_cost:,.2f}", 
                             help=f"Materials: ${total_mat:,.2f} | Instruments: ${total_inst:,.2f}")
            else:
                st.error(f"❌ Library Banking Failed: {lb_result.error_message}")
            
            
    # Display Results



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
            st.plotly_chart(fig, width="stretch", key=f"mcb_growth_{result.cell_line}")
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
            st.dataframe(pd.DataFrame(vial_data), width="stretch")
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
                st.dataframe(pd.DataFrame(qc_data), width="stretch")
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
            st.plotly_chart(fig, width="stretch", key=f"wcb_expansion_{unique_key}")
            
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
            st.dataframe(pd.DataFrame(vial_data), width="stretch")
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
                st.dataframe(pd.DataFrame(qc_data), width="stretch")
                st.metric("Total QC Cost", f"${total_qc_cost:.2f}")
