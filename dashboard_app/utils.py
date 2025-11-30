# dashboard_app/utils.py

import streamlit as st
import pandas as pd
import numpy as np
import yaml
import os
import altair as alt
import sqlite3 
from datetime import datetime
import traceback # NEW IMPORT for error handling

# --- CORE EXTERNAL IMPORTS ---
from cell_os.modeling import DoseResponseGP, DoseResponseGPConfig
from cell_os.workflow_renderer import render_workflow_graph
from cell_os.workflow_renderer_plotly import render_workflow_plotly 
from cell_os.unit_ops import ParametricOps, VesselLibrary
from cell_os.inventory import Inventory
from cell_os.workflows import WorkflowBuilder, Workflow
from cell_os.posh_decision_engine import (
    POSHDecisionEngine, 
    UserRequirements, 
    POSHProtocol, 
    AutomationLevel
)
from cell_os.posh_scenario import POSHScenario
from cell_os.posh_screen_design import run_posh_screen_design
from cell_os.posh_lv_moi import (
    fit_lv_transduction_model,
    LVTitrationResult,
    ScreenSimulator,
    ScreenConfig
)
from cell_os.posh_viz import (
    plot_library_composition,
    plot_titration_curve,
    plot_titer_posterior,
    plot_risk_assessment,
    plot_cost_breakdown
)
from cell_os.lab_world_model import LabWorldModel
from cell_os.budget_manager import BudgetConfig 
from core.experiment_db import ExperimentDB
from cell_os.dino_analysis import load_dino_embeddings_from_csv 

# --- SHARED FUNCTIONS ---

@st.cache_data(ttl=60)  # Refresh cache every 60 seconds
def load_data():
    """Loads experiment history and pricing data from CSV and the SQLite inventory database."""
    
    # 1. Load Experiment History 
    history_path = "results/experiment_history.csv"
    if os.path.exists(history_path):
        try:
            df = pd.read_csv(history_path, on_bad_lines='skip')
        except Exception as e:
            st.warning(f"Could not load experiment history: {e}")
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()
        
    # 2. Load Pricing Data from SQLite DB
    DB_PATH = "data/cell_os_inventory.db"
    
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            pricing_df = pd.read_sql("SELECT * FROM inventory_items", conn)
            conn.close()
            
            pricing = {
                'items': pricing_df.set_index('item_id').T.to_dict()
            }
            
        except Exception as e:
            st.warning(f"Could not load pricing data from DB: {e}")
            yaml_path = "data/raw/pricing.yaml"
            if os.path.exists(yaml_path):
                 with open(yaml_path, 'r') as f:
                     pricing = yaml.safe_load(f)
            else:
                 pricing = {}
    else:
        st.warning(f"Inventory database not found at {DB_PATH}. Run migration script to create it.")
        pricing = {}
        
    return df, pricing

@st.cache_resource
def init_automation_resources(vessel_path="data/raw/vessels.yaml", pricing_path="data/raw/pricing.yaml"):
    """Initializes and caches the core automation engine resources."""
    try:
        # Check if the vessel file exists before proceeding, as this is a common point of failure
        if not os.path.exists(vessel_path):
             raise FileNotFoundError(f"Vessel Library not found at: {vessel_path}")
             
        vessel_lib = VesselLibrary(vessel_path)
        inv = Inventory(pricing_path) 
        
        # Initialize InventoryManager for persistence
        from cell_os.inventory_manager import InventoryManager
        inv_manager = InventoryManager(inv)
        
        ops = ParametricOps(vessel_lib, inv)
        builder = WorkflowBuilder(ops)
        return vessel_lib, inv, ops, builder, inv_manager
    except Exception as e:
        # Display the specific error on the dashboard
        st.error(f"FATAL RESOURCE ERROR: Could not initialize automation engine. Details: {e}")
        # Display the full Python traceback in a code block for debugging
        st.code(traceback.format_exc())
        return None, None, None, None, None