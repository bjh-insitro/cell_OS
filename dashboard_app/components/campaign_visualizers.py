"""
Reusable visualization components for campaign management.
Extracted from tab_campaign_posh.py to improve maintainability.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import graphviz
from typing import Dict, Any, Optional

# --- Helper Classes ---

class PricingInventory:
    """Simple wrapper to mimic the Inventory interface for pricing lookups."""
    def __init__(self, pricing_data):
        self.pricing = pricing_data

    def get_price(self, item_id: str) -> float:
        """Get the unit price for an item."""
        if not self.pricing or 'items' not in self.pricing:
            return 0.0
        
        item = self.pricing['items'].get(item_id)
        if item:
            return item.get('unit_price_usd', 0.0)
        return 0.0


# --- Helper Functions ---

def get_item_cost(pricing: Dict, item_id: str, default_cost: float = 0.0) -> float:
    """Helper to safely get item cost from pricing dict."""
    if not pricing or "items" not in pricing:
        return default_cost
    item = pricing["items"].get(item_id)
    if item:
        return item.get("unit_price_usd", default_cost)
    return default_cost


def get_item_pack_price(pricing: Dict, item_id: str, default_cost: float = 0.0) -> float:
    """Get item pack price from pricing dict."""
    if not pricing or "items" not in pricing:
        return default_cost
    item = pricing["items"].get(item_id)
    if item:
        # If pack_price_usd is missing, fallback to unit_price
        return item.get("pack_price_usd", item.get("unit_price_usd", default_cost))
    return default_cost


def get_item_name(pricing: Dict, item_id: str, default_name: str) -> str:
    """Helper to safely get item name from pricing dict."""
    if not pricing or "items" not in pricing:
        return default_name
    item = pricing["items"].get(item_id)
    if item:
        return item.get("name", default_name)
    return default_name


# --- Renderers ---

def render_unit_ops_table(workflow):
    """Render the table of parameterized unit operations."""
    st.markdown("#### 📋 Protocol Steps")
    
    # Get all ops from workflow (handles both Workflow and legacy structures)
    if hasattr(workflow, 'all_ops'):
        ops = workflow.all_ops
    elif hasattr(workflow, 'steps'):
        ops = workflow.steps
    else:
        st.warning("Workflow structure not recognized")
        return
    
    steps_data = []
    for i, op in enumerate(ops):
        # Handle different UnitOp structures
        if hasattr(op, 'parameters'):
            params_str = ", ".join([f"{k}={v}" for k, v in op.parameters.items()])
        else:
            params_str = ""
        
        op_type = getattr(op, 'op_type', getattr(op, 'uo_id', 'Unknown'))
        duration = getattr(op, 'duration_min', getattr(op, 'time_score', 0))
        cost = getattr(op, 'cost_usd', getattr(op, 'material_cost_usd', 0) + getattr(op, 'instrument_cost_usd', 0))
        
        steps_data.append({
            "Step": i + 1,
            "Operation": op_type,
            "Parameters": params_str,
            "Duration (min)": duration,
            "Cost ($)": f"${cost:.2f}"
        })
    
    st.dataframe(
        pd.DataFrame(steps_data),
        width="stretch",
        hide_index=True
    )


def render_lineage(result):
    """Render a lineage tree using Graphviz."""
    if not result.lineage_data:
        st.info("No lineage data available.")
        return

    st.markdown("#### 🌳 Cell Lineage")
    
    # Create Graphviz digraph
    dot = graphviz.Digraph(comment='Cell Lineage')
    dot.attr(rankdir='LR')
    dot.attr('node', shape='box', style='rounded,filled', fillcolor='lightblue')
    
    # Add nodes and edges
    for node in result.lineage_data.get("nodes", []):
        label = f"{node['id']}\n{node.get('type', 'Unknown')}"
        if "cells" in node:
            label += f"\n{node['cells']:.1e} cells"
            
        # Color code by type
        fillcolor = 'lightblue'
        if node.get('type') == 'Vial':
            fillcolor = '#ffcccc'  # Reddish for vials
        elif node.get('type') == 'Flask':
            fillcolor = '#ccffcc'  # Greenish for flasks
        elif node.get('type') == 'Bioreactor':
            fillcolor = '#ccccff'  # Blueish for bioreactors
            
        dot.node(node['id'], label, fillcolor=fillcolor)
        
    def edge_color(label: str) -> str:
        label_lower = label.lower()
        if "freeze" in label_lower or "bank" in label_lower:
            return "#f28e2b"
        if "passage" in label_lower or "expand" in label_lower:
            return "#59a14f"
        if "seed" in label_lower:
            return "#4e79a7"
        return "#9c755f"

    timeline = []
    for idx, edge in enumerate(result.lineage_data.get("edges", []), start=1):
        label = edge.get("op", "")
        color = edge_color(label)
        dot.edge(edge['source'], edge['target'], label=label, color=color, fontcolor=color)
        timeline.append({"Step": idx, "Source": edge["source"], "Target": edge["target"], "Operation": label})
        
    st.graphviz_chart(dot)

    # Export options
    try:
        svg_bytes = dot.pipe(format="svg")
        png_bytes = dot.pipe(format="png")
        col_svg, col_png = st.columns(2)
        with col_svg:
            st.download_button(
                "Download Lineage (SVG)",
                data=svg_bytes,
                file_name="lineage.svg",
                mime="image/svg+xml",
            )
        with col_png:
            st.download_button(
                "Download Lineage (PNG)",
                data=png_bytes,
                file_name="lineage.png",
                mime="image/png",
            )
    except graphviz.backend.ExecutableNotFound:
        st.warning("Graphviz binaries not found; export buttons disabled.")

    if timeline:
        st.markdown("#### 📅 Lineage Timeline")
        timeline_df = pd.DataFrame(timeline)
        st.dataframe(timeline_df, width="stretch", hide_index=True)


def render_resources(result, pricing, workflow_type="MCB"):
    """Render resource usage and BOM."""
    st.markdown(f"#### 📦 Bill of Materials ({workflow_type})")
    
    # 1. Aggregate resources
    resources = {}
    total_cost = 0.0
    
    # Add workflow resources
    for op in result.workflow.all_ops:
        if hasattr(op, 'items') and op.items:
            for item in op.items:
                item_id = item.resource_id
                qty = item.quantity
                if item_id not in resources:
                    resources[item_id] = 0.0
                resources[item_id] += qty
            
    # Add fixed resources if any (from result metadata)
    if hasattr(result, "resources") and result.resources:
        for item_id, qty in result.resources.items():
            if item_id not in resources:
                resources[item_id] = 0.0
            resources[item_id] += qty

    # 2. Create DataFrame
    bom_data = []
    for item_id, qty in resources.items():
        unit_cost = get_item_cost(pricing, item_id)
        line_cost = unit_cost * qty
        total_cost += line_cost
        
        name = get_item_name(pricing, item_id, item_id)
        
        bom_data.append({
            "Item ID": item_id,
            "Name": name,
            "Quantity": qty,
            "Unit Cost": f"${unit_cost:.2f}",
            "Total Cost": f"${line_cost:.2f}",
            "_cost_val": line_cost  # For sorting
        })
        
    if not bom_data:
        st.info("Detailed itemized bill of materials not available for this workflow.")
        st.markdown("**Cost Summary**")
        
        # Show aggregate costs from operations
        total_material = sum(op.material_cost_usd for op in result.workflow.all_ops)
        total_instrument = sum(op.instrument_cost_usd for op in result.workflow.all_ops)
        total = total_material + total_instrument
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Cost", f"${total:.2f}")
        with col2:
            st.metric("Materials", f"${total_material:.2f}")
        with col3:
            st.metric("Instruments", f"${total_instrument:.2f}")
        
        # Show operations table
        st.markdown("**Operations**")
        ops_data = []
        for op in result.workflow.all_ops:
            ops_data.append({
                "Operation": op.name,
                "Category": op.category,
                "Material Cost": f"${op.material_cost_usd:.2f}",
                "Instrument Cost": f"${op.instrument_cost_usd:.2f}",
                "Total": f"${op.material_cost_usd + op.instrument_cost_usd:.2f}"
            })
        
        if ops_data:
            st.dataframe(pd.DataFrame(ops_data), width="stretch")
        return

    df_bom = pd.DataFrame(bom_data).sort_values("_cost_val", ascending=False)
    df_display = df_bom.drop(columns=["_cost_val"])
    
    # 3. Display metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Material Cost", f"${total_cost:.2f}")
    with col2:
        st.metric("Unique Items", len(bom_data))
    with col3:
        # Find most expensive item
        if not df_bom.empty:
            top_item = df_bom.iloc[0]
            st.metric("Top Cost Driver", top_item["Name"])
            
    # 4. Display table
    st.dataframe(df_display, width="stretch", hide_index=True)
    
    # 5. Cost breakdown chart
    if total_cost > 0:
        fig = px.pie(
            df_bom, 
            values="_cost_val", 
            names="Name", 
            title=f"Cost Breakdown ({workflow_type})"
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        normalized_type = workflow_type.lower()
        st.plotly_chart(
            fig,
            width="stretch",
            key=f"campaign_cost_breakdown_{normalized_type}"
        )


def render_titration_resources(result, pricing):
    """Render resources for titration using the workflow."""
    render_resources(result, pricing, workflow_type="Titration")
