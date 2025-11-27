# dashboard_app/app.py (The Final, Corrected Orchestrator)

import streamlit as st
import pandas as pd
import sys
import os 
from datetime import datetime # Needed for the path logic

# ---------------------------------------------------------------------------------
# FIX: Explicitly add package paths to sys.path to resolve absolute imports.
# This bypasses the 'ImportError: attempted relative import' issue.
# ---------------------------------------------------------------------------------
# 1. Get the directory of the current script (e.g., /cell_OS/dashboard_app/)
current_dir = os.path.dirname(os.path.abspath(__file__))
# 2. Get the project root directory (e.g., /cell_OS/)
project_root = os.path.abspath(os.path.join(current_dir, '..'))

# Ensure the project root is on the path (where the 'cell_os' package lives)
if project_root not in sys.path:
    sys.path.append(project_root)

# Ensure the 'dashboard_app' directory is on the path (where 'utils' and 'pages' live)
# This allows Python to resolve the imports using 'from dashboard_app.utils'
if current_dir not in sys.path:
    sys.path.append(current_dir)
# ---------------------------------------------------------------------------------

# --- IMPORT UTILITIES (FIXED: ABSOLUTE IMPORTS) ---
# We must now use the full package name 'dashboard_app' for all internal imports.
from dashboard_app.utils import load_data 

# --- IMPORT PAGE RENDERERS (FIXED: ABSOLUTE IMPORTS) ---
# Tab 1-4 (Original Tabs)
from dashboard_app.pages.tab_1_mission_control import render_mission_control
from dashboard_app.pages.tab_2_science import render_science_explorer
from dashboard_app.pages.tab_3_economics import render_economics 
from dashboard_app.pages.tab_4_workflow import render_workflow_visualizer
# Tab 5 (New Audit Tab)
from dashboard_app.pages.tab_audit_resources import render_resource_audit
# Tab 6-10 (Shifted Tabs)
from dashboard_app.pages.tab_5_posh_decisions import render_posh_decisions
from dashboard_app.pages.tab_6_posh_designer import render_posh_designer
from dashboard_app.pages.tab_7_campaign_reports import render_campaign_reports
from dashboard_app.pages.tab_8_budget_calculator import render_budget_calculator
from dashboard_app.pages.tab_9_phenotype_clustering import render_phenotype_clustering


# --- PAGE SETUP & DATA LOADING ---
st.set_page_config(page_title="cell_OS Dashboard", layout="wide")
st.title("🧬 cell_OS Mission Control")

# Sidebar: Configuration & Status
st.sidebar.header("Status")
if st.sidebar.button("Refresh Data"):
    st.rerun()

df, pricing = load_data()

# -------------------------------------------------------------------
# Tabs Definition (The Orchestration)
# -------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab_audit, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "🚀 Mission Control", 
    "🔬 Science", 
    "💰 Economics", 
    "🕸️ Workflow Visualizer", 
    "🛠️ Resource Audit", 
    "🧭 POSH Decision Assistant", 
    "🧪 POSH Screen Designer", 
    "📊 Campaign Reports", 
    "🧮 Budget Calculator", 
    "🧬 Phenotype Clustering"
])

# -------------------------------------------------------------------
# Tab Content Assignment (Calls the external functions)
# -------------------------------------------------------------------
with tab1:
    render_mission_control(df, pricing)

with tab2:
    render_science_explorer(df, pricing)

with tab3:
    # Fallback/Inline logic for Tab 3 (Economics)
    try:
        render_economics(df, pricing)
    except NameError:
        st.header("Financials")
        if not df.empty and "cost_usd" in df.columns:
            df["cumulative_cost"] = df["cost_usd"].cumsum()
            st.line_chart(df.reset_index(), x="index", y="cumulative_cost")
        st.header("Inventory Levels")
        items = []
        for item_id, data in pricing.get("items", {}).items():
            items.append({"Name": data.get("name"), "Price": data.get("unit_price_usd"), "Unit": data.get("logical_unit")})
        st.dataframe(pd.DataFrame(items), use_container_width=True)
        st.info("Live inventory tracking requires persisting the Inventory state to a file (TODO).")

with tab4:
    render_workflow_visualizer(df, pricing)

with tab_audit:
    render_resource_audit(df, pricing)

with tab5:
    render_posh_decisions(df, pricing)

with tab6:
    render_posh_designer(df, pricing)

with tab7:
    render_campaign_reports(df, pricing)

with tab8:
    render_budget_calculator(df, pricing)

with tab9:
    render_phenotype_clustering(df, pricing)
    
# Now run the app using: streamlit run dashboard_app/app.py