"""
cell_OS Dashboard Application

Main entry point for the Streamlit dashboard. This orchestrates the navigation
and rendering of all dashboard pages through a centralized page registry.
"""

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

from dashboard_app.utils import load_data
from dashboard_app.config import create_page_registry, PageCategory


def setup_page():
    """Configure the Streamlit page settings."""
    st.set_page_config(
        page_title="cell_OS Dashboard",
        page_icon="🧬",
        layout="wide",
        initial_sidebar_state="expanded"
    )


def render_sidebar(page_registry):
    """
    Render the sidebar with navigation and status information.
    
    Args:
        page_registry: The PageRegistry instance with all registered pages
        
    Returns:
        str: The selected page title
    """
    # Navigation
    st.sidebar.title("Navigation")
    
    # Get pages organized by category
    page_titles = page_registry.get_page_titles()
    
    # Find the index of POSH Campaign Sim to set as default
    default_index = 0
    for i, title in enumerate(page_titles):
        if "POSH Campaign Sim" in title:
            default_index = i
            break
    
    # Use selectbox for navigation
    selected_page = st.sidebar.selectbox(
        "Select Page",
        page_titles,
        index=default_index,
        label_visibility="collapsed"
    )
    
    st.sidebar.divider()
    
    # Status
    st.sidebar.header("Status")
    
    # Refresh button
    if st.sidebar.button("Refresh Data", use_container_width=True):
        st.rerun()
    
    return selected_page


def render_page(page_title: str, page_registry, df: pd.DataFrame, pricing: dict):
    """
    Render the selected page.
    
    Args:
        page_title: Full title of the page to render (emoji + title)
        page_registry: The PageRegistry instance
        df: DataFrame with simulation/execution data
        pricing: Pricing/inventory data dictionary
    """
    page_config = page_registry.get_page(page_title)
    
    if page_config is None:
        st.error(f"Page not found: {page_title}")
        st.info("Please select a valid page from the navigation menu.")
        return
    
    # Render the page using its registered render function
    try:
        page_config.render_function(df, pricing)
    except Exception as e:
        st.error(f"Error rendering page: {page_config.title}")
        st.exception(e)
        
        # Provide fallback content for Economics page (legacy compatibility)
        if page_config.key == "economics":
            render_economics_fallback(df, pricing)


def render_economics_fallback(df: pd.DataFrame, pricing: dict):
    """Fallback rendering for Economics page if the main renderer fails."""
    st.header("Financials")
    
    if not df.empty and "cost_usd" in df.columns:
        df["cumulative_cost"] = df["cost_usd"].cumsum()
        st.line_chart(df.reset_index(), x="index", y="cumulative_cost")
    
    st.header("Inventory Levels")
    items = []
    for item_id, data in pricing.get("items", {}).items():
        items.append({
            "Name": data.get("name"),
            "Price": data.get("unit_price_usd"),
            "Unit": data.get("logical_unit")
        })
    
    if items:
        st.dataframe(pd.DataFrame(items), use_container_width=True)
    
    st.info("Live inventory tracking requires persisting the Inventory state to a file (TODO).")


def main():
    """Main application entry point."""
    # Setup page configuration
    setup_page()
    
    # Display main title
    st.title("🧬 cell_OS Mission Control")
    
    # Initialize session state
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = 0
    
    # Create page registry
    page_registry = create_page_registry()
    
    # Load data
    df, pricing = load_data()
    
    # Render sidebar and get selected page
    selected_page = render_sidebar(page_registry)
    
    # Render the selected page
    render_page(selected_page, page_registry, df, pricing)


if __name__ == "__main__":
    main()