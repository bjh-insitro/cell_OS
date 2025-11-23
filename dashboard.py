import streamlit as st
import pandas as pd
import numpy as np
import yaml
import os
import altair as alt
from src.modeling import DoseResponseGP, DoseResponseGPConfig

st.set_page_config(page_title="cell_OS Dashboard", layout="wide")

st.title("🧬 cell_OS Mission Control")

# -------------------------------------------------------------------
# Sidebar: Configuration & Status
# -------------------------------------------------------------------
st.sidebar.header("Status")
if st.sidebar.button("Refresh Data"):
    st.rerun()

# Load Data
@st.cache_data
def load_data():
    history_path = "results/experiment_history.csv"
    if os.path.exists(history_path):
        df = pd.read_csv(history_path)
    else:
        df = pd.DataFrame()
        
    pricing_path = "data/raw/pricing.yaml"
    with open(pricing_path, 'r') as f:
        pricing = yaml.safe_load(f)
        
    return df, pricing

df, pricing = load_data()

# -------------------------------------------------------------------
# Tabs
# -------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["🚀 Mission Control", "🔬 Science", "💰 Economics"])

# -------------------------------------------------------------------
# Tab 1: Mission Control
# -------------------------------------------------------------------
with tab1:
    col1, col2, col3 = st.columns(3)
    
    # Calculate Metrics
    if not df.empty:
        total_spent = df["cost_usd"].sum() if "cost_usd" in df.columns else 0.0
        current_cycle = df["cycle"].max() if "cycle" in df.columns else 0
        n_experiments = len(df)
    else:
        total_spent = 0.0
        current_cycle = 0
        n_experiments = 0
        
    # Budget (Hardcoded initial for now, or read from log?)
    initial_budget = 5000.0
    remaining_budget = initial_budget - total_spent
    
    col1.metric("Budget Remaining", f"${remaining_budget:,.2f}", delta=f"-${total_spent:,.2f}")
    col2.metric("Current Cycle", f"{current_cycle}")
    col3.metric("Total Experiments", f"{n_experiments}")
    
    st.divider()
    
    st.subheader("Recent Activity")
    if not df.empty:
        st.dataframe(df.tail(10), use_container_width=True)
        
    st.subheader("Mission Log")
    log_path = "results/mission_log.md"
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            log_content = f.read()
        st.markdown(log_content)
    else:
        st.info("No mission log found.")

# -------------------------------------------------------------------
# Tab 2: Science
# -------------------------------------------------------------------
with tab2:
    st.header("Dose-Response Explorer")
    
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            cell_line = st.selectbox("Cell Line", df["cell_line"].unique())
        with col2:
            compound = st.selectbox("Compound", df["compound"].unique())
            
        # Filter Data
        mask = (df["cell_line"] == cell_line) & (df["compound"] == compound)
        df_slice = df[mask].copy()
        
        if not df_slice.empty:
            # Plot Data
            chart = alt.Chart(df_slice).mark_circle(size=60).encode(
                x=alt.X("dose_uM", scale=alt.Scale(type="log")),
                y="viability",
                color="cycle:O",
                tooltip=["dose_uM", "viability", "cycle"]
            ).interactive()
            
            # Fit GP (On the fly!)
            try:
                # Filter out zero doses for log scale
                df_fit = df_slice[df_slice["dose_uM"] > 0].copy()
                if len(df_fit) > 0:
                    gp = DoseResponseGP.from_dataframe(
                        df_fit, cell_line, compound, time_h=24, viability_col="viability"
                    )
                    grid = gp.predict_on_grid(num_points=100)
                    
                    df_grid = pd.DataFrame(grid)
                    
                    line = alt.Chart(df_grid).mark_line(color='red').encode(
                        x=alt.X("dose_uM", scale=alt.Scale(type="log")),
                        y="mean"
                    )
                    
                    band = alt.Chart(df_grid).mark_area(opacity=0.3, color='red').encode(
                        x=alt.X("dose_uM", scale=alt.Scale(type="log")),
                        y="mean",
                        y2="mean + std" # Altair calculation? No, need to pre-calc
                    )
                    # Pre-calc bounds
                    df_grid["upper"] = df_grid["mean"] + df_grid["std"]
                    df_grid["lower"] = df_grid["mean"] - df_grid["std"]
                    
                    band = alt.Chart(df_grid).mark_area(opacity=0.2, color='red').encode(
                        x=alt.X("dose_uM", scale=alt.Scale(type="log")),
                        y="lower",
                        y2="upper"
                    )
                    
                    st.altair_chart(chart + line + band, use_container_width=True)
                else:
                    st.altair_chart(chart, use_container_width=True)
                    st.warning("Not enough positive dose data to fit GP.")
                    
            except Exception as e:
                st.error(f"GP Fit Failed: {e}")
                st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No data for this selection.")
    else:
        st.info("No experimental data yet.")

# -------------------------------------------------------------------
# Tab 3: Economics
# -------------------------------------------------------------------
with tab3:
    st.header("Financials")
    
    if not df.empty and "cost_usd" in df.columns:
        # Cumulative Spend
        df["cumulative_cost"] = df["cost_usd"].cumsum()
        st.line_chart(df.reset_index(), x="index", y="cumulative_cost")
    
    st.header("Inventory Levels")
    # We don't have a live inventory file that updates yet (inventory.py is in-memory).
    # But we can show the catalog prices.
    
    items = []
    for item_id, data in pricing.get("items", {}).items():
        items.append({
            "Name": data.get("name"),
            "Price": data.get("unit_price_usd"),
            "Unit": data.get("logical_unit")
        })
    
    st.dataframe(pd.DataFrame(items), use_container_width=True)
    st.info("Live inventory tracking requires persisting the Inventory state to a file (TODO).")
