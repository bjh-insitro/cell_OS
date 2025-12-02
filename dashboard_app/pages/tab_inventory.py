"""
Inventory Management Dashboard Tab

Allows users to view stock levels, manage lots, and track usage history.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from dashboard_app.utils import init_automation_resources

LOW_STOCK_PERCENT = 0.2
MIN_LOW_STOCK_ABS = 5.0

def render_inventory_manager(df, pricing):
    """Render the Inventory Manager tab."""
    st.header("📦 Inventory Manager")
    st.markdown("""
    Manage lab inventory, track stock levels, and monitor reagent usage.
    """)
    
    # Initialize resources
    vessel_lib, inv, ops, builder, inv_manager = init_automation_resources()
    
    if inv_manager is None:
        st.error("Cannot load inventory manager.")
        return
    
    summary = _compute_inventory_summary(inv_manager)
    _render_summary_metrics(summary)
    
    # Create tabs
    tab_stock, tab_restock, tab_consume, tab_history = st.tabs([
        "📊 Stock Levels",
        "➕ Restock",
        "➖ Consume",
        "📜 Transaction History"
    ])
    
    with tab_stock:
        render_stock_levels(inv_manager)
        
    with tab_restock:
        render_restock_form(inv_manager)
    
    with tab_consume:
        render_consume_form(inv_manager)
        
    with tab_history:
        render_transaction_history(inv_manager)

def _compute_inventory_summary(inv_manager):
    resources = inv_manager.inventory.resources.values()
    total = len(resources)
    low_stock = []
    for res in resources:
        threshold = max(res.pack_size * LOW_STOCK_PERCENT if res.pack_size else 0, MIN_LOW_STOCK_ABS)
        if res.stock_level <= threshold:
            low_stock.append(res)
    last_tx = inv_manager.get_transactions(limit=1)
    last_timestamp = last_tx[0]["timestamp"] if last_tx else None
    total_value = sum((res.unit_price_usd or 0) * (res.stock_level or 0) for res in resources)
    return {
        "total_resources": total,
        "low_stock_count": len(low_stock),
        "last_sync": last_timestamp,
        "total_value": total_value,
    }

def _render_summary_metrics(summary):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tracked Resources", summary["total_resources"])
    with col2:
        st.metric("Low Stock Alerts", summary["low_stock_count"])
    with col3:
        if summary["last_sync"]:
            st.metric("Last Inventory Update", summary["last_sync"].split("T")[0])
        else:
            st.metric("Last Inventory Update", "No history")
    st.caption(f"Total catalog value (book): ${summary['total_value']:,.0f}")

def render_stock_levels(inv_manager):
    """Render current stock levels."""
    st.subheader("Current Stock Levels")
    
    # Get all resources
    resources = []
    for res_id, res in inv_manager.inventory.resources.items():
        threshold = max(res.pack_size * LOW_STOCK_PERCENT if res.pack_size else 0, MIN_LOW_STOCK_ABS)
        low_flag = res.stock_level <= threshold
        resources.append({
            "ID": res_id,
            "Name": res.name,
            "Category": res.category,
            "Stock Level": res.stock_level,
            "Unit": res.logical_unit,
            "Vendor": res.vendor,
            "Catalog #": res.catalog_number,
            "Status": "⚠️ Low" if low_flag else "✅ OK"
        })
        
    df_res = pd.DataFrame(resources)
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        category_filter = st.multiselect(
            "Filter by Category",
            options=df_res["Category"].unique(),
            default=df_res["Category"].unique()
        )
    
    with col2:
        search_term = st.text_input("Search by Name or ID")
        
    # Apply filters
    filtered_df = df_res[df_res["Category"].isin(category_filter)]
    if search_term:
        filtered_df = filtered_df[
            filtered_df["Name"].str.contains(search_term, case=False) | 
            filtered_df["ID"].str.contains(search_term, case=False)
        ]
        
    # Display table
    st.dataframe(
        filtered_df,
        width="stretch",
        column_config={
            "Stock Level": st.column_config.NumberColumn(
                "Stock Level",
                format="%.2f"
            )
        }
    )
    
    # Lot details
    st.divider()
    st.subheader("Lot Details")
    
    selected_resource = st.selectbox(
        "Select Resource to View Lots",
        options=filtered_df["ID"].tolist(),
        format_func=lambda x: f"{x} - {inv_manager.inventory.resources[x].name}"
    )
    
    if selected_resource:
        lots = inv_manager.get_lots(selected_resource)
        if lots:
            df_lots = pd.DataFrame(lots)
            st.dataframe(df_lots, width="stretch")
        else:
            st.info("No active lots found for this resource.")

def render_restock_form(inv_manager):
    """Render form to add stock."""
    st.subheader("Restock Inventory")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Select resource
        resource_ids = list(inv_manager.inventory.resources.keys())
        selected_id = st.selectbox(
            "Select Resource",
            options=resource_ids,
            format_func=lambda x: f"{x} - {inv_manager.inventory.resources[x].name}"
        )
        
        resource = inv_manager.inventory.resources[selected_id]
        st.info(f"Current Stock: {resource.stock_level} {resource.logical_unit}")
        
    with col2:
        quantity = st.number_input(
            f"Quantity to Add ({resource.logical_unit})",
            min_value=0.0,
            step=1.0
        )
        
        lot_id = st.text_input("Lot ID (Optional)", help="Leave empty to auto-generate")
        expiration = st.date_input("Expiration Date (Optional)", value=None)
        
    if st.button("➕ Add Stock", type="primary"):
        if quantity <= 0:
            st.error("Quantity must be greater than 0")
            return
            
        try:
            exp_datetime = datetime.combine(expiration, datetime.min.time()) if expiration else None
            
            inv_manager.add_stock(
                resource_id=selected_id,
                quantity=quantity,
                lot_id=lot_id if lot_id else None,
                expiration_date=exp_datetime
            )
            
            st.success(f"Successfully added {quantity} {resource.logical_unit} of {resource.name}")
            st.rerun()
            
        except Exception as e:
            st.error(f"Error adding stock: {e}")

def render_consume_form(inv_manager):
    """Render form to consume stock."""
    st.subheader("Consume Inventory")
    
    col1, col2 = st.columns(2)
    
    with col1:
        resource_ids = list(inv_manager.inventory.resources.keys())
        selected_id = st.selectbox(
            "Select Resource",
            options=resource_ids,
            format_func=lambda x: f"{x} - {inv_manager.inventory.resources[x].name}"
        )
        resource = inv_manager.inventory.resources[selected_id]
        st.info(f"Current Stock: {resource.stock_level} {resource.logical_unit}")
    
    with col2:
        quantity = st.number_input(
            f"Quantity to Consume ({resource.logical_unit})",
            min_value=0.0,
            step=1.0
        )
        meta_reason = st.text_input("Reason / Usage Notes", help="e.g., POSH Screen 2025-01")
    
    if st.button("➖ Consume Stock", type="secondary"):
        if quantity <= 0:
            st.error("Quantity must be greater than 0")
            return
        try:
            inv_manager.consume_stock(
                resource_id=selected_id,
                quantity=quantity,
                transaction_meta={"reason": meta_reason} if meta_reason else {}
            )
            st.success(f"Consumed {quantity} {resource.logical_unit} of {resource.name}")
            st.rerun()
        except Exception as e:
            st.error(f"Error consuming stock: {e}")

def render_transaction_history(inv_manager):
    """Render transaction history."""
    st.subheader("Transaction History")
    
    transactions = inv_manager.get_transactions(limit=100)
    
    if not transactions:
        st.info("No transactions found.")
        return
        
    df_trans = pd.DataFrame(transactions)
    
    # Enrich with resource names
    df_trans["Resource Name"] = df_trans["resource_id"].apply(
        lambda x: inv_manager.inventory.resources.get(x).name if x in inv_manager.inventory.resources else x
    )
    
    # Reorder columns
    cols = ["timestamp", "type", "Resource Name", "change", "lot_id", "metadata"]
    df_trans = df_trans[cols]
    
    st.dataframe(df_trans, width="stretch")
