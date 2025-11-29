import streamlit as st
import pandas as pd
import json
import altair as alt
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="Autonomous Campaigns",
    page_icon="🤖",
    layout="wide"
)

# Constants
CAMPAIGNS_DIR = Path("results/autonomous_campaigns")

def load_campaign_list():
    """Load list of available campaigns."""
    if not CAMPAIGNS_DIR.exists():
        return []
    
    campaigns = []
    for campaign_dir in CAMPAIGNS_DIR.iterdir():
        if campaign_dir.is_dir():
            report_path = campaign_dir / "campaign_report.json"
            if report_path.exists():
                with open(report_path) as f:
                    report = json.load(f)
                    campaigns.append({
                        "campaign_id": report["campaign_id"],
                        "path": campaign_dir,
                        "report": report
                    })
    
    return sorted(campaigns, key=lambda x: x["campaign_id"], reverse=True)

def load_campaign_checkpoints(campaign_path):
    """Load all checkpoints for a campaign."""
    checkpoints = []
    for checkpoint_file in sorted(campaign_path.glob("checkpoint_iter_*.json")):
        with open(checkpoint_file) as f:
            checkpoints.append(json.load(f))
    return checkpoints

def render_campaign_selector(campaigns):
    """Render campaign selection dropdown."""
    if not campaigns:
        st.warning("No campaigns found. Run `python scripts/run_loop_v2.py` to create one.")
        return None
    
    campaign_ids = [c["campaign_id"] for c in campaigns]
    selected_id = st.selectbox("Select Campaign", campaign_ids)
    
    return next(c for c in campaigns if c["campaign_id"] == selected_id)

def render_campaign_summary(report):
    """Render top-level campaign summary."""
    st.header("Campaign Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Iterations",
            report["results"]["total_iterations"]
        )
    
    with col2:
        st.metric(
            "Total Experiments",
            report["results"]["total_experiments"]
        )
    
    with col3:
        duration = report["results"]["duration_seconds"]
        st.metric(
            "Duration",
            f"{duration:.1f}s",
            f"{duration/60:.1f} min"
        )
    
    with col4:
        throughput = report["results"]["throughput"]
        st.metric(
            "Throughput",
            f"{throughput:.2f} exp/s"
        )

def render_best_result(report):
    """Render best result found."""
    st.subheader("Best Result Found")
    
    best = report.get("best_result")
    if not best:
        st.info("No best result available.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        **Cell Line**: {best['cell_line']}  
        **Compound**: {best['compound']}  
        **Dose**: {best['dose']:.4f} µM  
        """)
    
    with col2:
        st.markdown(f"""
        **Measurement**: {best['measurement']:.4f}  
        **Viability**: {best.get('viability', 'N/A')}  
        **Status**: {best['status']}  
        """)

def render_optimization_trajectory(report):
    """Render optimization trajectory over iterations."""
    st.subheader("Optimization Trajectory")
    
    results = report["all_results"]
    df = pd.DataFrame(results)
    
    # Add iteration number based on proposal_id
    df["iteration"] = df["proposal_id"].str.extract(r"prop_(\d+)_").astype(int)
    
    # Create trajectory chart
    base = alt.Chart(df).encode(
        x=alt.X("iteration:Q", title="Iteration"),
        tooltip=["iteration", "cell_line", "compound", "dose", "measurement"]
    )
    
    # Points for all experiments
    points = base.mark_circle(size=60, opacity=0.6).encode(
        y=alt.Y("measurement:Q", title="Measurement"),
        color=alt.Color("cell_line:N", title="Cell Line")
    )
    
    # Line for best-so-far
    df_sorted = df.sort_values("iteration")
    df_sorted["best_so_far"] = df_sorted["measurement"].cummax()
    
    best_line = alt.Chart(df_sorted).mark_line(
        color="red",
        strokeWidth=2,
        strokeDash=[5, 5]
    ).encode(
        x="iteration:Q",
        y="best_so_far:Q"
    )
    
    chart = (points + best_line).properties(
        height=400,
        title="Measurement vs. Iteration (Red dashed line = Best so far)"
    ).interactive()
    
    st.altair_chart(chart, use_container_width=True)

def render_dose_response_surface(report):
    """Render dose-response surface."""
    st.subheader("Dose-Response Landscape")
    
    results = report["all_results"]
    df = pd.DataFrame(results)
    
    # Create heatmap-style scatter
    chart = alt.Chart(df).mark_circle(size=100).encode(
        x=alt.X("dose:Q", scale=alt.Scale(type="log"), title="Dose (µM, log scale)"),
        y=alt.Y("compound:N", title="Compound"),
        color=alt.Color("measurement:Q", scale=alt.Scale(scheme="viridis"), title="Measurement"),
        size=alt.Size("measurement:Q", legend=None),
        tooltip=["compound", "dose", "measurement", "cell_line"]
    ).properties(
        height=300
    ).interactive()
    
    st.altair_chart(chart, use_container_width=True)

def render_exploration_vs_exploitation(checkpoints):
    """Render exploration vs exploitation over time."""
    st.subheader("Exploration vs. Exploitation")
    
    # Extract iteration-level stats
    iter_stats = []
    for checkpoint in checkpoints:
        results = checkpoint["results"]
        measurements = [r["measurement"] for r in results]
        doses = [r["dose"] for r in results]
        
        iter_stats.append({
            "iteration": checkpoint["iteration"],
            "mean_measurement": sum(measurements) / len(measurements),
            "std_measurement": pd.Series(measurements).std(),
            "dose_diversity": pd.Series(doses).std(),
            "experiments": len(results)
        })
    
    df = pd.DataFrame(iter_stats)
    
    # Create dual-axis chart
    col1, col2 = st.columns(2)
    
    with col1:
        # Mean measurement (exploitation)
        chart1 = alt.Chart(df).mark_line(point=True).encode(
            x=alt.X("iteration:Q", title="Iteration"),
            y=alt.Y("mean_measurement:Q", title="Mean Measurement"),
            tooltip=["iteration", "mean_measurement"]
        ).properties(
            title="Mean Measurement (Exploitation)",
            height=250
        )
        st.altair_chart(chart1, use_container_width=True)
    
    with col2:
        # Std measurement (exploration)
        chart2 = alt.Chart(df).mark_line(point=True, color="orange").encode(
            x=alt.X("iteration:Q", title="Iteration"),
            y=alt.Y("std_measurement:Q", title="Std Measurement"),
            tooltip=["iteration", "std_measurement"]
        ).properties(
            title="Std Measurement (Exploration)",
            height=250
        )
        st.altair_chart(chart2, use_container_width=True)

def render_compound_comparison(report):
    """Compare performance across compounds."""
    st.subheader("Compound Comparison")
    
    results = report["all_results"]
    df = pd.DataFrame(results)
    
    # Box plot by compound
    chart = alt.Chart(df).mark_boxplot().encode(
        x=alt.X("compound:N", title="Compound"),
        y=alt.Y("measurement:Q", title="Measurement"),
        color="compound:N"
    ).properties(
        height=300
    )
    
    st.altair_chart(chart, use_container_width=True)

def render_cell_line_comparison(report):
    """Compare performance across cell lines."""
    st.subheader("Cell Line Comparison")
    
    results = report["all_results"]
    df = pd.DataFrame(results)
    
    # Box plot by cell line
    chart = alt.Chart(df).mark_boxplot().encode(
        x=alt.X("cell_line:N", title="Cell Line"),
        y=alt.Y("measurement:Q", title="Measurement"),
        color="cell_line:N"
    ).properties(
        height=300
    )
    
    st.altair_chart(chart, use_container_width=True)

def render_raw_data(report):
    """Render raw experimental data."""
    st.subheader("Raw Experimental Data")
    
    results = report["all_results"]
    df = pd.DataFrame(results)
    
    # Select relevant columns
    display_cols = ["proposal_id", "cell_line", "compound", "dose", "measurement", "viability", "status"]
    df_display = df[display_cols]
    
    st.dataframe(df_display, use_container_width=True)
    
    # Download button
    csv = df_display.to_csv(index=False)
    st.download_button(
        label="Download CSV",
        data=csv,
        file_name=f"{report['campaign_id']}_results.csv",
        mime="text/csv"
    )

def main():
    st.title("Autonomous Campaigns 🤖")
    st.markdown("""
    Monitor and analyze autonomous optimization campaigns powered by the AI scientist.
    """)
    
    # Load campaigns
    campaigns = load_campaign_list()
    
    if not campaigns:
        st.info("No campaigns found. Run an autonomous campaign to see results here.")
        st.code("python scripts/run_loop_v2.py --max-iterations 10 --batch-size 8")
        return
    
    # Select campaign
    selected = render_campaign_selector(campaigns)
    if not selected:
        return
    
    report = selected["report"]
    
    # Render summary
    render_campaign_summary(report)
    
    # Render best result
    render_best_result(report)
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs([
        "Optimization Trajectory",
        "Dose-Response",
        "Comparisons",
        "Raw Data"
    ])
    
    with tab1:
        render_optimization_trajectory(report)
        
        # Load checkpoints for exploration analysis
        checkpoints = load_campaign_checkpoints(selected["path"])
        if checkpoints:
            render_exploration_vs_exploitation(checkpoints)
    
    with tab2:
        render_dose_response_surface(report)
    
    with tab3:
        render_compound_comparison(report)
        render_cell_line_comparison(report)
    
    with tab4:
        render_raw_data(report)
    
    # Configuration details
    with st.expander("Campaign Configuration"):
        st.json(report["config"])

if __name__ == "__main__":
    main()
