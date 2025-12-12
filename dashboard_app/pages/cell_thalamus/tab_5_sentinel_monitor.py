"""Tab 5: Sentinel Monitor - SPC control charts"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path

src_path = Path(__file__).parent.parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from cell_os.database.cell_thalamus_db import CellThalamusDB
from cell_os.cell_thalamus.variance_analysis import VarianceAnalyzer


def render_tab_5():
    """Render the Sentinel Monitor tab."""

    st.header("Sentinel Monitor (SPC)")
    st.markdown("Statistical Process Control for sentinel wells")

    # Get design ID
    design_id = st.session_state.get('latest_design_id')

    if not design_id:
        st.info("Run a simulation in Tab 1 first")
        return

    db_path = st.session_state.get('db_path', 'data/cell_thalamus.db')
    db = CellThalamusDB(db_path=db_path)

    # Get sentinel data
    sentinel_data = db.get_sentinel_data(design_id)

    if not sentinel_data:
        st.warning("No sentinel data found")
        return

    df_sent = pd.DataFrame(sentinel_data)

    # Run SPC analysis
    analyzer = VarianceAnalyzer(db)
    results = db.get_results(design_id)
    df_all = pd.DataFrame(results)

    spc_results = analyzer.sentinel_spc(df_all)

    # Display SPC summary
    st.subheader("Sentinel Status")

    sentinel_compounds = df_sent['compound'].unique()

    cols = st.columns(len(sentinel_compounds))

    for i, compound in enumerate(sentinel_compounds):
        with cols[i]:
            if compound in spc_results:
                spc_data = spc_results[compound]
                in_control = spc_data['in_control']

                st.metric(
                    compound,
                    "✓ In Control" if in_control else "✗ Out of Control",
                    delta=f"{spc_data['n_out_of_control']}/{spc_data['n_points']} OOC"
                )

                if in_control:
                    st.success("All points within 3σ")
                else:
                    st.error(f"{spc_data['n_out_of_control']} points OOC")

    st.markdown("---")

    # Select sentinel to view
    sentinel_compound = st.selectbox(
        "Select sentinel to view control chart",
        options=sorted(sentinel_compounds)
    )

    # Filter to selected sentinel
    df_sentinel = df_sent[df_sent['compound'] == sentinel_compound]

    # Get SPC limits
    spc_data = spc_results[sentinel_compound]
    mean = spc_data['mean']
    ucl = spc_data['ucl']
    lcl = spc_data['lcl']

    # Sort by time (plate/day combination)
    df_sentinel = df_sentinel.sort_values(['day', 'plate_id'])
    df_sentinel['index'] = range(len(df_sentinel))

    # Create control chart
    fig = go.Figure()

    # Add data points
    fig.add_trace(go.Scatter(
        x=df_sentinel['index'],
        y=df_sentinel['atp_signal'],
        mode='markers+lines',
        name='ATP Signal',
        marker=dict(size=8, color='blue'),
        line=dict(color='blue', width=1)
    ))

    # Add mean line
    fig.add_hline(y=mean, line_dash="dash", line_color="green", annotation_text="Mean")

    # Add control limits
    fig.add_hline(y=ucl, line_dash="dash", line_color="red", annotation_text="UCL (+3σ)")
    fig.add_hline(y=lcl, line_dash="dash", line_color="red", annotation_text="LCL (-3σ)")

    # Highlight out-of-control points
    df_ooc = df_sentinel[(df_sentinel['atp_signal'] > ucl) | (df_sentinel['atp_signal'] < lcl)]

    if len(df_ooc) > 0:
        fig.add_trace(go.Scatter(
            x=df_ooc['index'],
            y=df_ooc['atp_signal'],
            mode='markers',
            name='Out of Control',
            marker=dict(size=12, color='red', symbol='x')
        ))

    fig.update_layout(
        title=f"Control Chart: {sentinel_compound}",
        xaxis_title="Measurement Index (sorted by day/plate)",
        yaxis_title="ATP Signal",
        height=500,
        showlegend=True
    )

    st.plotly_chart(fig, use_container_width=True)

    # Statistics
    col_a, col_b, col_c, col_d = st.columns(4)

    with col_a:
        st.metric("Mean", f"{mean:.0f}")

    with col_b:
        st.metric("Std Dev", f"{spc_data['std']:.0f}")

    with col_c:
        st.metric("UCL", f"{ucl:.0f}")

    with col_d:
        st.metric("LCL", f"{lcl:.0f}")

    # Detailed data table
    with st.expander("📋 Sentinel Data Table"):
        display_df = df_sentinel[['well_id', 'plate_id', 'day', 'operator', 'atp_signal', 'cell_line']].copy()
        display_df['in_control'] = (df_sentinel['atp_signal'] >= lcl) & (df_sentinel['atp_signal'] <= ucl)

        st.dataframe(
            display_df.style.format({'atp_signal': '{:.0f}'}).apply(
                lambda row: ['background-color: #ffcccc' if not row['in_control'] else '' for _ in row],
                axis=1
            ),
            use_container_width=True
        )

    # Morphology channels for this sentinel
    with st.expander("🎨 Morphology Channels"):
        st.markdown(f"Morphology features for {sentinel_compound} sentinel")

        morph_channels = ['morph_er', 'morph_mito', 'morph_nucleus', 'morph_actin', 'morph_rna']

        for channel in morph_channels:
            channel_mean = df_sentinel[channel].mean()
            channel_std = df_sentinel[channel].std()
            st.metric(
                channel.replace('morph_', '').upper(),
                f"{channel_mean:.1f}",
                delta=f"±{channel_std:.1f}"
            )
