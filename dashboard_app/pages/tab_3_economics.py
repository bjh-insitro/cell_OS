# dashboard_app/pages/tab_3_economics.py
import io
from pathlib import Path

import pandas as pd
import streamlit as st

def render_economics(df, pricing):
    """Renders the content for the Economics dashboard tab."""
    st.header("Financials")
    
    if not df.empty and "cost_usd" in df.columns:
        # Cumulative Spend
        df["cumulative_cost"] = df["cost_usd"].cumsum()
        cost_chart_data = df.reset_index()
        st.line_chart(cost_chart_data, x="index", y="cumulative_cost")

        cost_export = cost_chart_data[["index", "cost_usd", "cumulative_cost"]].rename(columns={"index": "step"})
        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine="xlsxwriter") as writer:
            cost_export.to_excel(writer, index=False, sheet_name="financials")
        st.download_button(
            "Download Cost Breakdown (Excel)",
            data=excel_buf.getvalue(),
            file_name="cost_breakdown.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    
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
                width="stretch",
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Save Inventory Snapshot", width="stretch"):
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
                    width="stretch",
                )
    else:
        st.warning("Inventory database unavailable. Run `make bootstrap-data` to seed resources.")
