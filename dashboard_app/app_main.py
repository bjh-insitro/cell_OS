"""
Streamlit entry point for the Cell OS Campaign Dashboard.

Runs the Imaging Dose Loop simulation and visualizes the results.
To run: streamlit run dashboard_app/app_main.py
"""
import streamlit as st
import pandas as pd
import plotly.express as px

# Import the simulator function from your new module
from imaging_loop_simulator import run_simulation, SIM_CONFIG


# --- STREAMLIT PAGE SETUP ---
st.set_page_config(
    page_title="Cell OS Autonomous Campaign Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🔬 Autonomous Campaign Simulation Dashboard")
st.markdown("Visualizing the Bayesian Optimization process for dose selection.")

# --- SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.header("Simulation Settings")
    
    # Allow user to change the number of cycles
    current_cycles = SIM_CONFIG['simulation']['cycles']
    num_cycles = st.slider(
        "Number of Cycles to Run",
        min_value=1,
        max_value=15,
        value=current_cycles,
        step=1
    )
    
    # Button to run the simulation
    if st.button("Run Simulation", key="run_sim_button"):
        st.session_state['run_needed'] = True
        
    st.info("The simulation is run on demand using the `imaging_loop_simulator`.")


# --- DATA LOADING AND CACHING ---
# Cache the simulation run to prevent re-running it every time Streamlit refreshes
@st.cache_data(show_spinner=True)
def load_and_run_data(cycles):
    """Runs the simulation and caches the resulting DataFrame."""
    # Temporarily update the config for the run
    run_config = SIM_CONFIG.copy()
    run_config['simulation']['cycles'] = cycles
    
    df = run_simulation(config=run_config)
    return df

# Initialize session state for the first run
if 'run_needed' not in st.session_state:
    st.session_state['run_needed'] = True


# --- MAIN DASHBOARD CONTENT ---
if st.session_state['run_needed']:
    # Run the simulation and get the history
    history_df = load_and_run_data(num_cycles)
    st.session_state['run_needed'] = False

    st.subheader("Experiment Proposals History")
    
    # 1. Proposal Table (Data Inspection)
    st.dataframe(history_df, use_container_width=True)

    # 2. Score Trend Chart
    st.subheader("Optimization Score Trend")
    fig_score = px.line(
        history_df, 
        x="cycle", 
        y="score", 
        title="Optimization Score by Cycle (Expected Improvement)",
        markers=True
    )
    st.plotly_chart(fig_score, use_container_width=True)
    
    # 3. Dose Selection Chart
    st.subheader("Selected Dose Over Time")
    fig_dose = px.scatter(
        history_df,
        x="cycle",
        y="dose_uM",
        log_y=True,  # Doses are often log-scaled
        title="Dose (µM) Proposed in Each Cycle",
        size='score', # Use score to size the points
        hover_data=['viability_value', 'stress_value']
    )
    st.plotly_chart(fig_dose, use_container_width=True)

    # Display World Model Insights (optional, but good for diagnostics)
    st.markdown("---")
    st.header("Simulation Parameters")
    st.json(SIM_CONFIG) # Show the base configuration for reference