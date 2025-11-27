# dashboard_app/pages/tab_3_economics.py
import streamlit as st
import pandas as pd

def render_economics(df, pricing):
    """Renders the content for the Economics dashboard tab."""
    st.header("Financials")
    
    if not df.empty and "cost_usd" in df.columns:
        # Cumulative Spend
        df["cumulative_cost"] = df["cost_usd"].cumsum()
        st.line_chart(df.reset_index(), x="index", y="cumulative_cost")
    
    st.header("Inventory Levels")
    
    # Display catalog prices loaded at startup
    items = []
    for item_id, data in pricing.get("items", {}).items():
        items.append({
            "Name": data.get("name"),
            "Price": data.get("unit_price_usd"),
            "Unit": data.get("logical_unit")
        })
    
    st.dataframe(pd.DataFrame(items), use_container_width=True)
    st.info("Live inventory tracking requires persisting the Inventory state to a file (TODO).")