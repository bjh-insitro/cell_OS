import streamlit as st
from dashboard_app.utils import download_button

def render_hit_list(s_result, screen_cell_line):
    """Render the Hit List tab content."""
    st.dataframe(s_result.hit_list, use_container_width=True)
    download_button(
        s_result.hit_list,
        "⬇️ Download Hits (CSV)",
        f"{screen_cell_line}_hits.csv"
    )
