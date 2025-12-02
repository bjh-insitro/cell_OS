# dashboard_app/utils.py

import streamlit as st
import pandas as pd
import os
import altair as alt
from datetime import datetime
from typing import Any, Dict, Tuple
import traceback  # NEW IMPORT for error handling

# --- CORE EXTERNAL IMPORTS ---
from cell_os.modeling import DoseResponseGP, DoseResponseGPConfig
from cell_os.rendering import render_workflow_graph, render_workflow_plotly 
from cell_os.unit_ops import ParametricOps, VesselLibrary
from cell_os.inventory import Inventory
from cell_os.inventory_manager import InventoryManager
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
    """Loads experiment history and catalog pricing data from disk + SQLite."""
    
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
        
    # 2. Load catalog data from persistent inventory
    pricing: Dict[str, Any] = {"items": {}}
    inventory, _ = get_inventory_handles()
    for resource_id, resource in inventory.resources.items():
        pricing["items"][resource_id] = {
            "name": resource.name,
            "unit_price_usd": resource.unit_price_usd,
            "logical_unit": resource.logical_unit,
            "category": resource.category,
            "stock_level": resource.stock_level,
        }
    pricing["stock_levels"] = {rid: res.stock_level for rid, res in inventory.resources.items()}
        
    return df, pricing


@st.cache_resource
def get_inventory_handles(db_path: str = "data/inventory.db") -> Tuple[Inventory, InventoryManager]:
    """Return shared Inventory + InventoryManager handles."""
    inventory = Inventory(db_path=db_path)
    manager = InventoryManager(inventory, db_path=db_path)
    return inventory, manager

@st.cache_resource
@st.cache_resource
def init_automation_resources(vessel_path="data/raw/vessels.yaml"):
    """Initializes and caches the core automation engine resources."""
    try:
        # Check if the vessel file exists before proceeding, as this is a common point of failure
        if not os.path.exists(vessel_path):
             raise FileNotFoundError(f"Vessel Library not found at: {vessel_path}")
             
        vessel_lib = VesselLibrary(vessel_path)
        inv = Inventory()  # Loads from database by default 
        
        # Initialize InventoryManager for persistence
        inv_manager = InventoryManager(inv)
        ops = ParametricOps(vessel_lib, inv)
        builder = WorkflowBuilder(ops)
        return vessel_lib, inv, ops, builder, inv_manager
    except Exception as e:
        render_error(e, context="Automation Engine Initialization")
        return None, None, None, None, None

def render_error(error: Exception, context: str = "Error"):
    """Standardized error rendering for the dashboard."""
    st.error(f"❌ {context}: {str(error)}")
    with st.expander("Error Details"):
        st.code(traceback.format_exc())


def download_button(df: pd.DataFrame, label: str, filename: str, file_format: str = "csv"):
    """
    Render a download button for a DataFrame.
    
    Args:
        df: DataFrame to export
        label: Button label
        filename: Output filename
        file_format: One of {"csv", "excel"}
    """
    if df.empty:
        st.info("No data to export.")
        return
    
    if file_format == "excel":
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)
        data = buffer.getvalue()
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        data = df.to_csv(index=False).encode("utf-8")
        mime = "text/csv"
    
    st.download_button(
        label=label,
        data=data,
        file_name=filename,
        mime=mime,
        width="stretch",
    )
