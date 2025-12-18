"""Tab 3: Dose-Response Explorer"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys
from pathlib import Path

src_path = Path(__file__).parent.parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from cell_os.database.cell_thalamus_db import CellThalamusDB
from cell_os.cell_thalamus.variance_analysis import VarianceAnalyzer


def render_tab_3():
    """Render the Dose-Response Explorer tab."""

    st.header("Dose-Response Curves")
    st.markdown("Explore compound effects on morphology and ATP viability")

    with st.expander("ℹ️ Interpreting Dose-Response Curves", expanded=False):
        st.markdown("""
        **What is this showing?**
        - X-axis: Compound dose (log scale)
        - Y-axis: Response (ATP signal or morphology channel intensity)
        - Blue line: Mean response across replicates
        - Shaded area: Standard error of the mean (SEM)
        - Gray dots: Individual well measurements

        **Key metrics:**
        - **EC50/IC50**: Dose that produces 50% effect (inflection point)
        - **Dynamic range**: Difference between baseline and maximum effect
        - **Hill slope**: Steepness of the curve (cooperativity)

        **What to look for:**
        - **Monotonic response**: Does the curve go consistently up or down?
        - **Saturation**: Does the response plateau at high doses?
        - **Variability**: Are error bars small (good reproducibility)?
        - **ATP vs morphology**: Do they agree or show different patterns?
        """)

    # Get design ID
    design_id = st.session_state.get('latest_design_id')

    if not design_id:
        st.info("Run a simulation in Tab 1 first")
        return

    db_path = st.session_state.get('db_path', 'data/cell_thalamus.db')
    db = CellThalamusDB(db_path=db_path)

    # Load data
    results = db.get_results(design_id)
    if not results:
        st.error(f"No results found")
        return

    df = pd.DataFrame(results)
    df = df[df['is_sentinel'] == False]  # Exclude sentinels

    # Selection controls
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        compound = st.selectbox(
            "Compound",
            options=sorted(df['compound'].unique())
        )

    with col2:
        cell_line = st.selectbox(
            "Cell Line",
            options=sorted(df['cell_line'].unique())
        )

    with col3:
        timepoint = st.selectbox(
            "Timepoint",
            options=sorted(df['timepoint_h'].unique()),
            format_func=lambda x: f"{x}h"
        )

    with col4:
        metric = st.selectbox(
            "Metric",
            options=['atp_signal', 'morph_er', 'morph_mito', 'morph_nucleus', 'morph_actin', 'morph_rna'],
            format_func=lambda x: x.replace('morph_', '').replace('_', ' ').title()
        )

    # Filter data
    df_filtered = df[
        (df['compound'] == compound) &
        (df['cell_line'] == cell_line) &
        (df['timepoint_h'] == timepoint)
    ]

    if len(df_filtered) == 0:
        st.warning("No data for this combination")
        return

    # Group by dose and compute statistics
    dose_stats = df_filtered.groupby('dose_uM')[metric].agg(['mean', 'std', 'count']).reset_index()
    dose_stats['sem'] = dose_stats['std'] / np.sqrt(dose_stats['count'])

    # Create dose-response plot
    fig = go.Figure()

    # Add mean line
    fig.add_trace(go.Scatter(
        x=dose_stats['dose_uM'],
        y=dose_stats['mean'],
        mode='lines+markers',
        name='Mean',
        line=dict(color='blue', width=2),
        marker=dict(size=8)
    ))

    # Add error bars
    fig.add_trace(go.Scatter(
        x=dose_stats['dose_uM'],
        y=dose_stats['mean'] + dose_stats['sem'],
        mode='lines',
        name='Mean + SEM',
        line=dict(width=0),
        showlegend=False
    ))

    fig.add_trace(go.Scatter(
        x=dose_stats['dose_uM'],
        y=dose_stats['mean'] - dose_stats['sem'],
        mode='lines',
        name='Mean - SEM',
        line=dict(width=0),
        fillcolor='rgba(0, 100, 255, 0.2)',
        fill='tonexty',
        showlegend=False
    ))

    # Add individual points (semi-transparent)
    fig.add_trace(go.Scatter(
        x=df_filtered['dose_uM'],
        y=df_filtered[metric],
        mode='markers',
        name='Individual Wells',
        marker=dict(size=4, color='gray', opacity=0.3)
    ))

    fig.update_layout(
        title=f"{compound} on {cell_line} at {timepoint}h",
        xaxis_title="Dose (μM)",
        yaxis_title=metric.replace('morph_', '').replace('_', ' ').title(),
        xaxis_type="log",
        height=500,
        hovermode='closest'
    )

    st.plotly_chart(fig, use_container_width=True, key="dose_response_curve_main")

    # Statistics table
    st.subheader("Dose-Response Statistics")
    st.dataframe(
        dose_stats.style.format({
            'dose_uM': '{:.2f}',
            'mean': '{:.1f}',
            'std': '{:.1f}',
            'sem': '{:.1f}',
            'count': '{:.0f}'
        }),
        use_container_width=True
    )

    # Compare multiple metrics
    with st.expander("📊 Compare Multiple Metrics"):
        st.markdown("Compare ATP signal vs morphology channels")

        metrics_to_compare = st.multiselect(
            "Select metrics to compare",
            options=['atp_signal', 'morph_er', 'morph_mito', 'morph_nucleus', 'morph_actin', 'morph_rna'],
            default=['atp_signal', 'morph_er']
        )

        if len(metrics_to_compare) >= 2:
            fig_multi = go.Figure()

            for metric_name in metrics_to_compare:
                dose_stats_multi = df_filtered.groupby('dose_uM')[metric_name].mean().reset_index()

                fig_multi.add_trace(go.Scatter(
                    x=dose_stats_multi['dose_uM'],
                    y=dose_stats_multi[metric_name],
                    mode='lines+markers',
                    name=metric_name.replace('morph_', '').replace('_', ' ').title()
                ))

            fig_multi.update_layout(
                title=f"Multi-Metric Comparison: {compound} on {cell_line}",
                xaxis_title="Dose (μM)",
                yaxis_title="Normalized Signal",
                xaxis_type="log",
                height=400
            )

            st.plotly_chart(fig_multi, use_container_width=True, key=f"dose_response_multi_{compound}_{cell_line}")
