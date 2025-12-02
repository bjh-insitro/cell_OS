"""
cell_OS Dashboard Application

Main entry point for the Streamlit dashboard. This orchestrates the navigation
and rendering of all dashboard pages through a centralized page registry.
"""

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st
import traceback

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

from dashboard_app.utils import load_data, get_inventory_handles
from dashboard_app.config import create_page_registry, PageCategory

LOG_PATH = Path("logs/dashboard_errors.log")


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
    st.sidebar.title("Navigation")
    search_term = st.sidebar.text_input("Filter tabs", placeholder="Type to search…")
    category_options = ["All"] + [cat.value for cat in PageCategory]
    selected_category = st.sidebar.selectbox("Category", category_options)
    
    all_pages = page_registry.get_all_pages()
    filtered_pages = []
    for page in all_pages:
        if selected_category != "All" and page.category.value != selected_category:
            continue
        if search_term:
            tokens = [page.title, page.description or "", page.category.value, page.key]
            if not any(search_term.lower() in token.lower() for token in tokens if token):
                continue
        filtered_pages.append(page)
    
    if not filtered_pages:
        filtered_pages = all_pages
    
    page_titles = [f"{p.emoji} {p.title}" for p in filtered_pages]
    
    # Default to POSH Campaign Sim for landing
    default_target = "🧬 POSH Campaign Sim"
    if default_target in page_titles:
        default_index = page_titles.index(default_target)
    else:
        default_index = 0

    pending = st.session_state.pop("pending_nav", None)
    if pending and pending in page_titles:
        default_index = page_titles.index(pending)
    
    selected_page = st.sidebar.selectbox(
        "Select Page",
        page_titles,
        index=min(default_index, len(page_titles) - 1),
        label_visibility="collapsed"
    )
    
    st.sidebar.divider()
    
    # Status
    st.sidebar.header("Status")
    
    # Refresh button
    if st.sidebar.button("Refresh Data", use_container_width=True):
        st.rerun()
    
    st.sidebar.subheader("Recent Tabs")
    recent_tabs = st.session_state.setdefault("recent_tabs", [])
    for entry in recent_tabs[:5]:
        st.sidebar.caption(entry)
    
    return selected_page


def log_dashboard_error(page_config, exception, stack_trace: str) -> str:
    """Persist dashboard errors and provide a GitHub issue link."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().isoformat()
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {page_config.title}\n{stack_trace}\n{'-'*60}\n")
    title = quote_plus(f"Dashboard error on {page_config.title}")
    body = quote_plus(
        f"### Context\n- Page: {page_config.title}\n- Timestamp: {timestamp}\n\n```\n{stack_trace}\n```"
    )
    return f"https://github.com/brighart/cell_OS/issues/new?title={title}&body={body}"


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
        stack = traceback.format_exc()
        issue_url = log_dashboard_error(page_config, e, stack)
        st.error(f"Error rendering page: {page_config.title}")
        st.caption(f"Details recorded in {LOG_PATH}")
        st.markdown(f"[Report Issue]({issue_url})")
        st.code(stack, language="python")
        
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
    
    st.info("Inventory data unavailable; run a campaign or seed the database to view live levels.")


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
    df, pricing_data = load_data()
    pricing = {
        "items": dict(pricing_data.get("items", {})),
        "stock_levels": dict(pricing_data.get("stock_levels", {})),
    }
    inventory, inventory_manager = get_inventory_handles()
    pricing["inventory"] = inventory
    pricing["inventory_manager"] = inventory_manager
    pricing["stock_levels"] = {rid: res.stock_level for rid, res in inventory.resources.items()}
    
    # Render sidebar and get selected page
    selected_page = render_sidebar(page_registry)
    
    recent = st.session_state.setdefault("recent_tabs", [])
    if selected_page in recent:
        recent.remove(selected_page)
    recent.insert(0, selected_page)
    st.session_state["recent_tabs"] = recent[:5]

    # Render the selected page
    render_page(selected_page, page_registry, df, pricing)


if __name__ == "__main__":
    main()
