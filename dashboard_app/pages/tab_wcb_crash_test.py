import streamlit as st
import pandas as pd
import json
import base64
import altair as alt
from pathlib import Path
import io
from PIL import Image

st.set_page_config(
    page_title="WCB Crash Test Analysis",
    page_icon="🧬",
    layout="wide"
)

# Constants
ASSETS_DIR = Path("dashboard_assets_wcb")

def load_assets():
    """Load all dashboard assets from the output directory."""
    assets = {}
    
    # Check if directory exists
    if not ASSETS_DIR.exists():
        st.error(f"Assets directory not found: {ASSETS_DIR}")
        return None

    # Load Summary JSON
    try:
        with open(ASSETS_DIR / "wcb_summary.json", "r") as f:
            assets["summary"] = json.load(f)
    except FileNotFoundError:
        st.warning("wcb_summary.json not found.")
        
    # Load Run Results CSV
    try:
        assets["run_results"] = pd.read_csv(ASSETS_DIR / "wcb_run_results.csv")
    except FileNotFoundError:
        st.warning("wcb_run_results.csv not found.")
        
    # Load Daily Metrics CSV
    try:
        assets["daily_metrics"] = pd.read_csv(ASSETS_DIR / "wcb_daily_metrics.csv")
    except FileNotFoundError:
        st.warning("wcb_daily_metrics.csv not found.")
        
    return assets

def render_metrics(summary):
    """Render top-level metrics."""
    st.header("Simulation Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Success Rate", 
            f"{summary.get('success_rate', 0):.1%}",
            f"{summary.get('successful_runs', 0)}/{summary.get('total_runs', 0)} runs"
        )
        
    with col2:
        st.metric(
            "Median Vials",
            f"{summary.get('vials_p50', 0):.0f}",
            f"Target: 10"
        )
        
    with col3:
        st.metric(
            "Median Duration",
            f"{summary.get('duration_p50', 0):.1f} days",
            f"Max Passage: P{summary.get('max_passage_p95', 0):.0f}"
        )
        
    with col4:
        failures = summary.get('failed_runs', 0)
        contamination = summary.get('contaminated_runs', 0)
        st.metric(
            "Failures",
            f"{failures}",
            f"{contamination} contaminated"
        )

def render_vial_distribution(df):
    """Render interactive vial distribution chart."""
    st.subheader("Production Yield Distribution")
    
    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X("final_vials:Q", bin=alt.Bin(maxbins=15), title="Final Vials Generated"),
        y=alt.Y("count()", title="Number of Runs"),
        color=alt.Color("had_contamination:N", title="Contaminated", scale={"domain": [False, True], "range": ["#4c78a8", "#e45756"]}),
        tooltip=["count()", "final_vials", "had_contamination"]
    ).properties(
        height=300
    ).interactive()
    
    st.altair_chart(chart, use_container_width=True)

def render_growth_curves(daily_df, run_results_df):
    """Render growth curves."""
    st.subheader("Cell Growth Trajectories")
    
    # Join with run results to get failure status
    merged = daily_df.merge(run_results_df[["run_id", "terminal_failure", "had_contamination"]], on="run_id", how="left")
    
    # Filter for performance (limit to 100 runs if too many)
    run_ids = merged["run_id"].unique()
    if len(run_ids) > 100:
        selected_ids = run_ids[:100]
        merged = merged[merged["run_id"].isin(selected_ids)]
        st.caption(f"Showing first 100 runs for performance.")
    
    chart = alt.Chart(merged).mark_line(opacity=0.5).encode(
        x=alt.X("day:Q", title="Day"),
        y=alt.Y("total_cells:Q", scale=alt.Scale(type="log"), title="Total Cells (Log Scale)"),
        color=alt.Color("terminal_failure:N", title="Failed Run"),
        detail="run_id",
        tooltip=["run_id", "day", "total_cells", "flask_count"]
    ).properties(
        height=400
    ).interactive()
    
    st.altair_chart(chart, use_container_width=True)

def render_failure_analysis(df):
    """Render failure analysis."""
    st.subheader("Failure Analysis")
    
    failed_df = df[df["terminal_failure"] == True]
    
    if failed_df.empty:
        st.success("No failures detected in this dataset.")
        return
        
    st.dataframe(
        failed_df[["run_id", "failed_reason", "duration_days", "waste_cells"]],
        use_container_width=True
    )
    
    # Failure reason breakdown
    reason_counts = failed_df["failed_reason"].value_counts().reset_index()
    reason_counts.columns = ["Reason", "Count"]
    
    chart = alt.Chart(reason_counts).mark_bar().encode(
        x=alt.X("Count:Q"),
        y=alt.Y("Reason:N", sort="-x"),
        color=alt.value("#e45756")
    ).properties(
        title="Failure Reasons",
        height=200
    )
    
    st.altair_chart(chart, use_container_width=True)

def main():
    st.title("WCB Crash Test Analysis 🧬")
    st.markdown("Analysis of Monte Carlo simulations for Working Cell Bank production (1->10 vials).")
    
    assets = load_assets()
    if not assets:
        st.info("Run the WCB simulation first to generate assets.")
        return
        
    if "summary" in assets:
        render_metrics(assets["summary"])
        
    tab1, tab2, tab3, tab4 = st.tabs(["Production", "Growth Dynamics", "Failures", "Raw Data"])
    
    with tab1:
        if "run_results" in assets:
            render_vial_distribution(assets["run_results"])
            
    with tab2:
        if "daily_metrics" in assets and "run_results" in assets:
            render_growth_curves(assets["daily_metrics"], assets["run_results"])
            
    with tab3:
        if "run_results" in assets:
            render_failure_analysis(assets["run_results"])
            
    with tab4:
        st.subheader("Run Results")
        if "run_results" in assets:
            st.dataframe(assets["run_results"])
            
        st.subheader("Daily Metrics")
        if "daily_metrics" in assets:
            st.dataframe(assets["daily_metrics"])

if __name__ == "__main__":
    main()
