# dashboard_app/pages/tab_3_economics.py
import streamlit as st
import pandas as pd
from pathlib import Path

def render_economics(df, pricing):
    """Renders the content for the Economics dashboard tab."""
    st.header("Financials")
    
    if not df.empty and "cost_usd" in df.columns:
        # Cumulative Spend
        df["cumulative_cost"] = df["cost_usd"].cumsum()
        st.line_chart(df.reset_index(), x="index", y="cumulative_cost")
    
    st.header("Inventory Levels")
    
    inventory = pricing.get("inventory")
    if inventory:
        records = []
        for resource_id, resource in inventory.resources.items():
            records.append({
                "Resource": resource_id,
                "Name": resource.name,
                "Stock": resource.stock_level,
                "Unit": resource.logical_unit,
                "Unit Price (USD)": resource.unit_price_usd,
                "Total Value (USD)": resource.unit_price_usd * resource.stock_level,
            })
        inventory_df = pd.DataFrame(records)
        if inventory_df.empty:
            st.info("No catalog resources found. Seed the inventory database to see live stock levels.")
        else:
            st.dataframe(
                inventory_df.sort_values("Total Value (USD)", ascending=False),
                use_container_width=True,
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Save Inventory Snapshot", use_container_width=True):
                    snapshot_path = Path("results/inventory_snapshot.csv")
                    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                    inventory_df.to_csv(snapshot_path, index=False)
                    st.success(f"Inventory snapshot saved to {snapshot_path}")
            with col2:
                st.download_button(
                    "Download CSV",
                    inventory_df.to_csv(index=False),
                    file_name="inventory_snapshot.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
    else:
        st.warning("Inventory database unavailable. Run `make bootstrap-data` to seed resources.")
