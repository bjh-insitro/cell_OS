# dashboard_app/pages/tab_2_science.py
import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
# Import necessary components from utils
from dashboard_app.utils import DoseResponseGP

def render_science_explorer(df, pricing):
    """Renders the content for the Dose-Response Explorer tab."""
    st.header("Dose-Response Explorer")
    
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            cell_line = st.selectbox("Cell Line", df["cell_line"].unique())
        with col2:
            compound = st.selectbox("Compound", df["compound"].unique())
            
        # Filter Data
        mask = (df["cell_line"] == cell_line) & (df["compound"] == compound)
        df_slice = df[mask].copy()
        
        if not df_slice.empty:
            # Plot Data
            chart = alt.Chart(df_slice).mark_circle(size=60).encode(
                x=alt.X("dose_uM", scale=alt.Scale(type="log")),
                y=alt.Y("viability", type="quantitative"),
                color="cycle:O",
                tooltip=[
                    alt.Tooltip("dose_uM", type="quantitative"),
                    alt.Tooltip("viability", type="quantitative"),
                    alt.Tooltip("cycle", type="ordinal")
                ]
            ).interactive()
            
            # Fit GP (On the fly!)
            try:
                # Filter out zero doses for log scale
                df_fit = df_slice[df_slice["dose_uM"] > 0].copy()
                if len(df_fit) > 0:
                    gp = DoseResponseGP.from_dataframe(
                        df_fit, cell_line, compound, time_h=24, viability_col="viability"
                    )
                    grid = gp.predict_on_grid(num_points=100)
                    
                    df_grid = pd.DataFrame(grid)
                    
                    line = alt.Chart(df_grid).mark_line(color='red').encode(
                        x=alt.X("dose_uM", scale=alt.Scale(type="log")),
                        y=alt.Y("mean", type="quantitative")
                    )
                    
                    # Pre-calc bounds
                    df_grid["upper"] = df_grid["mean"] + df_grid["std"]
                    df_grid["lower"] = df_grid["mean"] - df_grid["std"]
                    
                    band = alt.Chart(df_grid).mark_area(opacity=0.2, color='red').encode(
                        x=alt.X("dose_uM", scale=alt.Scale(type="log")),
                        y=alt.Y("lower", type="quantitative"),
                        y2=alt.Y2("upper")
                    )
                    
                    st.altair_chart(chart + line + band, width="stretch")
                else:
                    st.altair_chart(chart, width="stretch")
                    st.warning("Not enough positive dose data to fit GP.")
                    
            except Exception as e:
                st.error(f"GP Fit Failed: {e}")
                st.altair_chart(chart, width="stretch")
        else:
            st.info("No data for this selection.")
    else:
        st.info("No experimental data yet.")
