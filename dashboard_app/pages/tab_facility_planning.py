import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path

st.set_page_config(
    page_title="Facility Planning",
    page_icon="🏭",
    layout="wide"
)

# Constants
ASSETS_DIR = Path("data/dashboard_assets/facility")
CSV_PATH = ASSETS_DIR / "facility_load.csv"

# Hardcoded capacities from the stress test script (ideally these would be in a config file)
INCUBATOR_CAPACITY = 20
BSC_CAPACITY = 2.0

@st.cache_data(show_spinner=False)
def load_data():
    if not CSV_PATH.exists():
        st.error(f"Data file not found: {CSV_PATH}")
        return None
    return pd.read_csv(CSV_PATH)

def render_resource_chart(df, metric_col, capacity, title, color):
    """Render a resource usage chart with capacity line."""
    
    base = alt.Chart(df).encode(x=alt.X("day:Q", title="Day"))

    # Usage Area
    area = base.mark_area(opacity=0.3, color=color).encode(
        y=alt.Y(f"{metric_col}:Q", title=title),
        tooltip=["day", metric_col, "active_campaigns"]
    )
    
    # Usage Line
    line = base.mark_line(color=color).encode(
        y=f"{metric_col}:Q"
    )
    
    # Capacity Rule
    rule = base.mark_rule(color="red", strokeDash=[5, 5]).encode(
        y=alt.datum(capacity)
    )
    
    # Overload Points
    overload = base.mark_circle(color="red", size=60).encode(
        y=f"{metric_col}:Q"
    ).transform_filter(
        alt.datum[metric_col] > capacity
    )

    chart = (area + line + rule + overload).properties(
        height=300,
        title=f"{title} (Capacity: {capacity})"
    ).interactive()
    
    st.altair_chart(chart, width="stretch")

def render_violations(df):
    """Render a table of capacity violations."""
    st.subheader("Capacity Violations")
    
    # Filter for violations
    incubator_violations = df[df["incubator_usage"] > INCUBATOR_CAPACITY].copy()
    bsc_violations = df[df["bsc_hours"] > BSC_CAPACITY].copy()
    
    if incubator_violations.empty and bsc_violations.empty:
        st.success("✅ No capacity violations detected.")
        return

    col1, col2 = st.columns(2)
    
    with col1:
        if not incubator_violations.empty:
            st.error(f"Incubator Overload: {len(incubator_violations)} days")
            st.dataframe(
                incubator_violations[["day", "incubator_usage", "active_campaigns"]].style.format({"incubator_usage": "{:.0f}"}),
                width="stretch"
            )
            
    with col2:
        if not bsc_violations.empty:
            st.error(f"BSC Overload: {len(bsc_violations)} days")
            st.dataframe(
                bsc_violations[["day", "bsc_hours", "active_campaigns"]].style.format({"bsc_hours": "{:.1f}"}),
                width="stretch"
            )

def main():
    st.title("Facility Capacity Planning 🏭")
    st.markdown("""
    Visualize resource utilization across multiple concurrent campaigns.
    Identify bottlenecks in **Incubator Space** and **Biosafety Cabinet (BSC) Time**.
    """)
    
    df = load_data()
    if df is None:
        st.info("Run `examples/facility_stress_test.py` to generate data.")
        return
        
    # Metrics Summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Simulation Duration", f"{df['day'].max()} days")
    with col2:
        peak_inc = df['incubator_usage'].max()
        st.metric("Peak Incubator", f"{peak_inc} flasks", delta=f"{peak_inc - INCUBATOR_CAPACITY}", delta_color="inverse")
    with col3:
        peak_bsc = df['bsc_hours'].max()
        st.metric("Peak BSC Load", f"{peak_bsc:.1f} hours", delta=f"{peak_bsc - BSC_CAPACITY:.1f}", delta_color="inverse")
    with col4:
        st.metric("Max Active Campaigns", f"{df['active_campaigns'].max()}")

    # Charts
    st.subheader("Resource Utilization")
    
    tab1, tab2 = st.tabs(["Incubator Usage", "BSC Usage"])
    
    with tab1:
        render_resource_chart(df, "incubator_usage", INCUBATOR_CAPACITY, "Incubator Usage (Flasks)", "#1f77b4")
        
    with tab2:
        render_resource_chart(df, "bsc_hours", BSC_CAPACITY, "BSC Usage (Hours)", "#ff7f0e")
        
    # Violations
    render_violations(df)
    
    # Raw Data
    with st.expander("View Raw Data"):
        st.dataframe(df)

if __name__ == "__main__":
    main()
