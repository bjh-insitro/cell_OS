# dashboard_app/utils.py

import streamlit as st
import pandas as pd
import numpy as np
import yaml
import os
import altair as alt
from datetime import datetime

# --- CORE EXTERNAL IMPORTS ---
# Imports from the cell_os package (These must be successfully installed via pip install -e .)
from cell_os.modeling import DoseResponseGP, DoseResponseGPConfig

# FIX: Separating imports that were previously bundled but lived in different files
from cell_os.workflow_renderer import render_workflow_graph
from cell_os.workflow_renderer_plotly import render_workflow_plotly # <-- CORRECTED SOURCE FILE
# --- END FIX ---

from cell_os.unit_ops import ParametricOps, VesselLibrary
from cell_os.inventory import Inventory
from cell_os.workflows import WorkflowBuilder, Workflow

# Imports needed by other tabs
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
from cell_os.dino_analysis import load_dino_embeddings_from_csv # Used in Tab 9

# --- SHARED FUNCTIONS ---

@st.cache_data
def load_data():
    """Loads experiment history and pricing data, caching the results."""
    history_path = "results/experiment_history.csv"
    if os.path.exists(history_path):
        try:
            df = pd.read_csv(history_path, on_bad_lines='skip')
        except Exception as e:
            st.warning(f"Could not load experiment history: {e}")
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()
        
    pricing_path = "data/raw/pricing.yaml"
    if os.path.exists(pricing_path):
        try:
            with open(pricing_path, 'r') as f:
                pricing = yaml.safe_load(f)
        except Exception as e:
            st.warning(f"Could not load pricing data: {e}")
            pricing = {}
    else:
        pricing = {}
        
    return df, pricing

@st.cache_resource
def init_automation_resources(vessel_path="data/raw/vessels.yaml", pricing_path="data/raw/pricing.yaml"):
    """Initializes and caches the core automation engine resources."""
    try:
        vessel_lib = VesselLibrary(vessel_path)
        inv = Inventory(pricing_path)
        ops = ParametricOps(vessel_lib, inv)
        builder = WorkflowBuilder(ops)
        return vessel_lib, inv, ops, builder
    except Exception as e:
        # st.error(f"Failed to initialize core automation resources: {e}")
        return None, None, None, None