# dashboard_app/pages/tab_1_mission_control.py

import streamlit as st
import pandas as pd
import os
# Only import the specific required components from utils
from dashboard_app.utils import ExperimentDB

def render_mission_control(df, pricing):
    """Renders the content for the Mission Control dashboard tab."""
    col1, col2, col3 = st.columns(3)
    
    # Connect to database
    try:
        db = ExperimentDB()
        
        # Query experiment statistics
        db.cursor.execute("""
            SELECT 
                COUNT(DISTINCT experiment_id) as n_experiments,
                SUM(cost_usd) as total_cost
            FROM titration_results
        """)
        row = db.cursor.fetchone()
        
        if row and row[0]:  # Has data
            n_experiments = row[0]
            total_cost = row[1] if row[1] else 0.0
            
            # Get most recent experiment
            db.cursor.execute("""
                SELECT experiment_id, MAX(timestamp) as last_update
                FROM titration_results
                GROUP BY experiment_id
                ORDER BY last_update DESC
                LIMIT 1
            """)
            recent_row = db.cursor.fetchone()
            current_experiment = recent_row[0] if recent_row else "None"
            
        else:  # No data yet
            n_experiments = 0
            total_cost = 0.0
            current_experiment = "No experiments yet"
        
        # Budget (from config or default)
        initial_budget = 5000.0
        remaining_budget = initial_budget - total_cost
        
        col1.metric("Budget Remaining", f"${remaining_budget:,.2f}", delta=f"-${total_cost:,.2f}")
        col2.metric("Active Experiment", current_experiment)
        col3.metric("Total Experiments", f"{n_experiments}")
        
        st.divider()
        
        # Recent Activity from Database
        st.subheader("Recent Titration Results")
        
        db.cursor.execute("""
            SELECT 
                experiment_id,
                cell_line,
                round_number,
                volume_ul,
                fraction_bfp,
                cost_usd,
                timestamp
            FROM titration_results
            ORDER BY timestamp DESC
            LIMIT 20
        """)
        
        results = db.cursor.fetchall()
        
        if results:
            df_recent = pd.DataFrame(results, columns=[
                'Experiment', 'Cell Line', 'Round', 'Volume (µL)', 
                'BFP%', 'Cost ($)', 'Timestamp'
            ])
            df_recent['BFP%'] = (df_recent['BFP%'] * 100).round(1)
            st.dataframe(df_recent, width="stretch")
        else:
            st.info("No experiments run yet. Launch a campaign to see results!")
            st.code("cell-os-run --config config/campaign_example.yaml")
        
        db.close()
        
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        st.warning("Falling back to file-based data...")
        
        # Fallback to CSV if DB fails
        if os.path.exists("results/experiment_history.csv"):
            df_fallback = pd.read_csv("results/experiment_history.csv", on_bad_lines='skip')
            st.dataframe(df_fallback.tail(10), width="stretch")
    
    st.subheader("Mission Log")
    log_path = "results/mission_log.md"
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            log_content = f.read()
        st.markdown(log_content)
    else:
        st.info("No mission log found.")
