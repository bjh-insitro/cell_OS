import streamlit as st
import pandas as pd
import json
import altair as alt
from pathlib import Path
from datetime import datetime
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.database.repositories.campaign import CampaignRepository

st.set_page_config(
    page_title="Autonomous Campaigns",
    page_icon="🤖",
    layout="wide"
)

# Initialize database
@st.cache_resource
def get_db():
    return CampaignRepository()

def load_campaign_list():
    """Load list of available campaigns from database."""
    db = get_db()
    campaign_ids = db.get_all_campaigns()
    
    campaigns = []
    for cid in campaign_ids:
        campaign = db.get_campaign(cid)
        stats = db.get_campaign_stats(cid)
        campaigns.append({
            "campaign_id": cid,
            "campaign": campaign,
            "stats": stats
        })
    
    return campaigns

def load_campaign_data(campaign_id):
    """Load all data for a campaign."""
    db = get_db()
    iterations = db.get_iterations(campaign_id)
    
    # Aggregate all results
    all_results = []
    for iteration in iterations:
        if iteration.results:
            for res in iteration.results:
                # Add iteration number
                res["iteration"] = iteration.iteration_number
                all_results.append(res)
    
    return iterations, all_results

def render_campaign_selector(campaigns):
    """Render campaign selection dropdown."""
    if not campaigns:
        st.warning("No campaigns found in database. Run `python scripts/demos/run_loop_v2.py` to create one.")
        return None
    
    # Create label map
    options = {c["campaign_id"]: f"{c['campaign_id']} ({c['stats']['status']})" for c in campaigns}
    
    selected_id = st.selectbox(
        "Select Campaign", 
        options.keys(), 
        format_func=lambda x: options[x]
    )
    
    return next(c for c in campaigns if c["campaign_id"] == selected_id)

def render_campaign_summary(campaign_data):
    """Render top-level campaign summary."""
    st.header("Campaign Summary")
    
    campaign = campaign_data["campaign"]
    stats = campaign_data["stats"]
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Iterations",
            stats["iterations"]
        )
    
    with col2:
        st.metric(
            "Total Experiments",
            stats["experiments"]
        )
    
    with col3:
        if "duration_seconds" in stats:
            duration = stats["duration_seconds"]
            st.metric(
                "Duration",
                f"{duration:.1f}s",
                f"{duration/60:.1f} min"
            )
        else:
            st.metric("Duration", "N/A")
    
    with col4:
        st.metric(
            "Status",
            stats["status"].upper()
        )

def render_best_result(all_results):
    """Render best result found."""
    st.subheader("Best Result Found")
    
    if not all_results:
        st.info("No results available.")
        return
    
    # Find best result (highest measurement)
    best = max(all_results, key=lambda x: x.get("measurement", 0))
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        **Cell Line**: {best.get('cell_line', 'N/A')}  
        **Compound**: {best.get('compound', 'N/A')}  
        **Dose**: {best.get('dose', 0):.4f} µM  
        """)
    
    with col2:
        st.markdown(f"""
        **Measurement**: {best.get('measurement', 0):.4f}  
        **Viability**: {best.get('viability', 'N/A')}  
        **Iteration**: {best.get('iteration', 'N/A')}  
        """)

def render_optimization_trajectory(all_results):
    """Render optimization trajectory over iterations."""
    st.subheader("Optimization Trajectory")
    
    if not all_results:
        st.info("No data available.")
        return
        
    df = pd.DataFrame(all_results)
    
    # Ensure iteration column exists
    if "iteration" not in df.columns:
        # Fallback to extracting from proposal_id if needed
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
    
    st.altair_chart(chart, width="stretch")

def render_dose_response_surface(all_results):
    """Render dose-response surface."""
    st.subheader("Dose-Response Landscape")
    
    if not all_results:
        st.info("No data available.")
        return
        
    df = pd.DataFrame(all_results)
    
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
    
    st.altair_chart(chart, width="stretch")

def render_exploration_vs_exploitation(iterations):
    """Render exploration vs exploitation over time."""
    st.subheader("Exploration vs. Exploitation")
    
    if not iterations:
        st.info("No iteration data available.")
        return
    
    # Extract iteration-level stats
    iter_stats = []
    for iteration in iterations:
        if not iteration.results:
            continue
            
        measurements = [r["measurement"] for r in iteration.results]
        doses = [r["dose"] for r in iteration.results]
        
        if not measurements:
            continue
            
        iter_stats.append({
            "iteration": iteration.iteration_number,
            "mean_measurement": sum(measurements) / len(measurements),
            "std_measurement": pd.Series(measurements).std() if len(measurements) > 1 else 0,
            "dose_diversity": pd.Series(doses).std() if len(doses) > 1 else 0,
            "experiments": len(iteration.results)
        })
    
    if not iter_stats:
        st.info("Insufficient data for stats.")
        return
        
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
        st.altair_chart(chart1, width="stretch")
    
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
        st.altair_chart(chart2, width="stretch")

def render_compound_comparison(all_results):
    """Compare performance across compounds."""
    st.subheader("Compound Comparison")
    
    if not all_results:
        st.info("No data available.")
        return
        
    df = pd.DataFrame(all_results)
    
    # Box plot by compound
    chart = alt.Chart(df).mark_boxplot().encode(
        x=alt.X("compound:N", title="Compound"),
        y=alt.Y("measurement:Q", title="Measurement"),
        color="compound:N"
    ).properties(
        height=300
    )
    
    st.altair_chart(chart, width="stretch")

def render_cell_line_comparison(all_results):
    """Compare performance across cell lines."""
    st.subheader("Cell Line Comparison")
    
    if not all_results:
        st.info("No data available.")
        return
        
    df = pd.DataFrame(all_results)
    
    # Box plot by cell line
    chart = alt.Chart(df).mark_boxplot().encode(
        x=alt.X("cell_line:N", title="Cell Line"),
        y=alt.Y("measurement:Q", title="Measurement"),
        color="cell_line:N"
    ).properties(
        height=300
    )
    
    st.altair_chart(chart, width="stretch")

def render_raw_data(all_results, campaign_id):
    """Render raw experimental data."""
    st.subheader("Raw Experimental Data")
    
    if not all_results:
        st.info("No data available.")
        return
        
    df = pd.DataFrame(all_results)
    
    # Select relevant columns
    cols = ["iteration", "proposal_id", "cell_line", "compound", "dose", "measurement", "viability", "status"]
    display_cols = [c for c in cols if c in df.columns]
    df_display = df[display_cols]
    
    st.dataframe(df_display, width="stretch")
    
    # Download button
    csv = df_display.to_csv(index=False)
    st.download_button(
        label="Download CSV",
        data=csv,
        file_name=f"{campaign_id}_results.csv",
        mime="text/csv"
    )

def main():
    st.title("Autonomous Campaigns 🤖")
    st.markdown("""
    Monitor and analyze autonomous optimization campaigns powered by the AI scientist.
    **Now powered by CampaignDatabase 🚀**
    """)
    
    # Load campaigns
    campaigns = load_campaign_list()
    
    if not campaigns:
        st.info("No campaigns found in database. Run an autonomous campaign to see results here.")
        st.code("python scripts/demos/run_loop_v2.py --max-iterations 10 --batch-size 8")
        return
    
    # Select campaign
    selected = render_campaign_selector(campaigns)
    if not selected:
        return
    
    campaign_id = selected["campaign_id"]
    
    # Load detailed data
    iterations, all_results = load_campaign_data(campaign_id)
    
    # Render summary
    render_campaign_summary(selected)
    
    # Render best result
    render_best_result(all_results)
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs([
        "Optimization Trajectory",
        "Dose-Response",
        "Comparisons",
        "Raw Data"
    ])
    
    with tab1:
        render_optimization_trajectory(all_results)
        render_exploration_vs_exploitation(iterations)
    
    with tab2:
        render_dose_response_surface(all_results)
    
    with tab3:
        render_compound_comparison(all_results)
        render_cell_line_comparison(all_results)
    
    with tab4:
        render_raw_data(all_results, campaign_id)
    
    # Configuration details
    with st.expander("Campaign Configuration"):
        if selected["campaign"].config:
            st.json(selected["campaign"].config)
        else:
            st.info("No configuration available.")

if __name__ == "__main__":
    main()
