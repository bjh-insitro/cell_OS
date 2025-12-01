"""
Home/Landing page for the cell_OS dashboard.

Provides quick-start guidance, recent activity highlights, and shortcuts to
the most common tabs so new users have immediate context.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import pandas as pd
import streamlit as st


def _count_unique(df: pd.DataFrame, column: str) -> int:
    """Return number of unique entries for a column if it exists."""
    if column in df.columns:
        return int(df[column].nunique())
    return 0


def _find_timestamp_column(df: pd.DataFrame) -> str | None:
    """Return a best-guess timestamp column for recent activity."""
    for column in ["updated_at", "completed_at", "timestamp", "created_at"]:
        if column in df.columns:
            return column
    return None


def _format_currency(value: float) -> str:
    """Format currency with fallbacks."""
    if value >= 1_000_000:
        return f"${value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value/1_000:.1f}K"
    return f"${value:,.0f}"


def render_home(df: pd.DataFrame, pricing: Dict[str, Any]):
    """Render the dashboard landing page."""
    st.header("👋 Welcome to cell_OS Mission Control")
    st.write(
        "This hub gives you a snapshot of current activity, quick-start tips, "
        "and shortcuts to the most important tools in the platform."
    )

    # Metrics ---------------------------------------------------------------
    total_campaigns = _count_unique(df, "experiment_id")
    active_campaigns = int(df[df.get("status", pd.Series(dtype=str)).str.lower().eq("running")].shape[0]) if "status" in df else 0
    total_cost = float(df["cost_usd"].sum()) if "cost_usd" in df.columns else 0.0

    col1, col2, col3 = st.columns(3)
    col1.metric("Tracked Campaigns", total_campaigns or "—")
    col2.metric("Active Runs", active_campaigns or "—")
    col3.metric("Cumulative Spend", _format_currency(total_cost) if total_cost else "—")

    st.divider()

    # Quick Start -----------------------------------------------------------
    st.subheader("Quick Start")
    st.markdown(
        """
1. **Run a campaign**: `cell-os-run --config config/campaign_example.yaml`
2. **Sync databases**: `make bootstrap-data`
3. **Open the dashboard**: `streamlit run dashboard_app/app.py`
4. **Review results** via the tabs below.
        """
    )

    # Recent Activity ------------------------------------------------------
    st.subheader("Recent Activity")
    if df.empty:
        st.info("No experiment history found yet. Run a campaign to populate this feed.")
    else:
        ts_col = _find_timestamp_column(df)
        recent_df = df.copy()
        if ts_col:
            recent_df = recent_df.sort_values(ts_col, ascending=False)
        preview_cols = [col for col in ["experiment_id", "cell_line", "status", ts_col] if col and col in recent_df.columns]
        st.dataframe(
            recent_df[preview_cols].head(5) if preview_cols else recent_df.head(5),
            use_container_width=True,
        )

    st.divider()

    # Shortcut cards -------------------------------------------------------
    st.subheader("Jump Back In")
    shortcuts = [
        ("🚀 Mission Control", "System overview & alerts", "🚀 Mission Control"),
        ("🔬 Science", "Dose-response curves & assays", "🔬 Science"),
        ("💰 Economics", "Costs, inventory, and BOMs", "💰 Economics"),
        ("🧬 POSH Campaign Sim", "Plan and simulate POSH campaigns", "🧬 POSH Campaign Sim"),
    ]
    cols = st.columns(len(shortcuts))
    for col, (title, description, tab_name) in zip(cols, shortcuts):
        with col:
            st.markdown(f"**{title}**")
            st.caption(description)
            if st.button("Open", key=f"shortcut_{tab_name}", use_container_width=True):
                st.session_state.pending_nav = tab_name
                st.experimental_rerun()

    st.divider()

    # Helpful links --------------------------------------------------------
    st.subheader("Helpful Links")
    st.markdown(
        """
- 📘 [User Guide](docs/guides/USER_GUIDE.md)
- 🧪 [Tests & Lint](README.md#-testing)
- 📂 [Example Configs](config/)
        """
    )
