"""
Inventory Management Dashboard Tab

Allows users to view stock levels, manage lots, and track usage history.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from dashboard_app.utils import init_automation_resources

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
        
    # Create tabs
    tab_stock, tab_restock, tab_history = st.tabs([
        "📊 Stock Levels",
        "➕ Restock",
        "📜 Transaction History"
    ])
    
    with tab_stock:
        render_stock_levels(inv_manager)
        
    with tab_restock:
        render_restock_form(inv_manager)
        
    with tab_history:
        render_transaction_history(inv_manager)

def render_stock_levels(inv_manager):
    """Render current stock levels."""
    st.subheader("Current Stock Levels")
    
    # Get all resources
    resources = []
    for res_id, res in inv_manager.inventory.resources.items():
        resources.append({
            "ID": res_id,
            "Name": res.name,
            "Category": res.category,
            "Stock Level": res.stock_level,
            "Unit": res.logical_unit,
            "Vendor": res.vendor,
            "Catalog #": res.catalog_number
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
        use_container_width=True,
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
            st.dataframe(df_lots, use_container_width=True)
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
    
    st.dataframe(df_trans, use_container_width=True)
