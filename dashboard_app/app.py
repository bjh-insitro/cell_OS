# dashboard_app/app.py (The Final Orchestrator with Workflow BOM Audit)

import streamlit as st
import pandas as pd
import sys
import os 
from datetime import datetime

# ---------------------------------------------------------------------------------
# FIX: Explicitly add package paths to sys.path to resolve absolute imports.
# This ensures modules are found when running from the project root.
# ---------------------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))

if project_root not in sys.path:
    sys.path.append(project_root)

if current_dir not in sys.path:
    sys.path.append(current_dir)
# ---------------------------------------------------------------------------------

# --- IMPORT UTILITIES (FIXED: ABSOLUTE IMPORTS) ---
from dashboard_app.utils import load_data 

# --- IMPORT PAGE RENDERERS (FIXED: ABSOLUTE IMPORTS) ---
# Tab 1-4 (Original Tabs)
from dashboard_app.pages.tab_1_mission_control import render_mission_control
from dashboard_app.pages.tab_2_science import render_science_explorer
from dashboard_app.pages.tab_3_economics import render_economics 
from dashboard_app.pages.tab_4_workflow import render_workflow_visualizer

# Tab 5 (New Audit Tabs)
from dashboard_app.pages.tab_audit_resources import render_resource_audit
from dashboard_app.pages.tab_audit_workflow_bom import render_workflow_bom_audit # <-- NEW IMPORT
from dashboard_app.pages.tab_cell_line_inspector import render_cell_line_inspector # <-- CELL LINE INSPECTOR
from dashboard_app.pages.tab_execution_monitor import render_execution_monitor # <-- EXECUTION MONITOR
from dashboard_app.pages.tab_analytics import render_analytics # <-- ANALYTICS
from dashboard_app.pages.tab_inventory import render_inventory_manager # <-- INVENTORY MANAGER
from dashboard_app.pages.tab_campaign_manager import render_campaign_manager # <-- CAMPAIGN MANAGER
from dashboard_app.pages.tab_campaign_posh import render_posh_campaign_manager # <-- NEW POSH CAMPAIGN SIM

# Tab 6-10 (Shifted Tabs)
from dashboard_app.pages.tab_5_posh_decisions import render_posh_decisions
from dashboard_app.pages.tab_6_posh_designer import render_posh_designer
from dashboard_app.pages.tab_7_campaign_reports import render_campaign_reports
from dashboard_app.pages.tab_8_budget_calculator import render_budget_calculator
from dashboard_app.pages.tab_9_phenotype_clustering import render_phenotype_clustering


# --- PAGE SETUP & DATA LOADING ---
st.set_page_config(page_title="cell_OS Dashboard", layout="wide")
st.title("🧬 cell_OS Mission Control")

# Initialize session state for active tab
if "active_tab" not in st.session_state:
    st.session_state.active_tab = 0

# Sidebar: Configuration & Status
st.sidebar.header("Status")
if st.sidebar.button("Refresh Data"):
    st.rerun()

df, pricing = load_data()

# -------------------------------------------------------------------
# Sidebar Navigation (Replaces Tabs for Stability)
# -------------------------------------------------------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", [
    "🚀 Mission Control", 
    "🧬 POSH Campaign Sim",
    "🔬 Science", 
    "💰 Economics", 
    "🕸️ Workflow Visualizer", 
    "🛠️ Resource Audit", 
    "🔍 Workflow BOM Audit",
    "🧬 Cell Line Inspector",
    "⚙️ Execution Monitor",
    "📈 Analytics",
    "📦 Inventory",
    "🗓️ Campaign Manager", 
    "🧭 POSH Decision Assistant", 
    "🧪 POSH Screen Designer", 
    "📊 Campaign Reports", 
    "🧮 Budget Calculator", 
    "🧬 Phenotype Clustering"
])

# -------------------------------------------------------------------
# Page Rendering
# -------------------------------------------------------------------

if page == "🚀 Mission Control":
    render_mission_control(df, pricing)

elif page == "🧬 POSH Campaign Sim":
    render_posh_campaign_manager(df, pricing)

elif page == "🔬 Science":
    render_science_explorer(df, pricing)

elif page == "💰 Economics":
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

elif page == "🕸️ Workflow Visualizer":
    render_workflow_visualizer(df, pricing)

elif page == "🛠️ Resource Audit":
    render_resource_audit(df, pricing)

elif page == "🔍 Workflow BOM Audit":
    render_workflow_bom_audit(df, pricing)

elif page == "🧬 Cell Line Inspector":
    render_cell_line_inspector(df, pricing)

elif page == "⚙️ Execution Monitor":
    render_execution_monitor(df, pricing)

elif page == "📈 Analytics":
    render_analytics(df, pricing)

elif page == "📦 Inventory":
    render_inventory_manager(df, pricing)

elif page == "🗓️ Campaign Manager":
    render_campaign_manager(df, pricing)

elif page == "🧭 POSH Decision Assistant":
    render_posh_decisions(df, pricing)

elif page == "🧪 POSH Screen Designer":
    render_posh_designer(df, pricing)

elif page == "📊 Campaign Reports":
    render_campaign_reports(df, pricing)

elif page == "🧮 Budget Calculator":
    render_budget_calculator(df, pricing)

elif page == "🧬 Phenotype Clustering":
    render_phenotype_clustering(df, pricing)