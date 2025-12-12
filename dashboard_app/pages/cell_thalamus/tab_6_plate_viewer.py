"""Tab 6: Plate Viewer - Spatial heatmaps for quality control (96-well format)"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys
from pathlib import Path

src_path = Path(__file__).parent.parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from cell_os.database.cell_thalamus_db import CellThalamusDB


def render_tab_6():
    """Render the Plate Viewer tab."""

    st.header("Plate Viewer")
    st.markdown("Spatial heatmaps to identify edge effects and plate patterns")

    with st.expander("ℹ️ Understanding Plate Heatmaps", expanded=False):
        st.markdown("""
        **What is this showing?**
        - Heatmap of a 96-well plate (8 rows × 12 columns)
        - Color intensity = metric value (ATP signal or morphology channel)
        - Each cell = one well

        **Spatial patterns to look for:**

        **🔴 Edge effects** (common artifact):
        - Wells on edges (row A/H, column 1/12) often differ from center
        - Caused by: evaporation, temperature gradients, uneven gas exchange
        - **Good assay**: <10% difference between edge and center
        - **Bad assay**: >10% difference = plate handling issues

        **Common patterns:**
        - **Gradient**: Color changes smoothly across plate (temperature issue)
        - **Striping**: Alternating rows/columns (pipetting error)
        - **Hotspot**: One region differs (bubble, plate defect)
        - **Random**: No pattern (good! Just biological variation)

        **Why this matters:**
        Spatial patterns indicate technical problems. If you see strong plate position effects, the experimental design needs modification (better plate randomization, different plate type, environmental controls).
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
    df = pd.DataFrame(results)

    # Plate selection
    col1, col2 = st.columns(2)

    with col1:
        plate_id = st.selectbox(
            "Select Plate",
            options=sorted(df['plate_id'].unique())
        )

    with col2:
        metric = st.selectbox(
            "Select Metric",
            options=['atp_signal', 'morph_er', 'morph_mito', 'morph_nucleus', 'morph_actin', 'morph_rna'],
            format_func=lambda x: x.replace('morph_', '').replace('_', ' ').title()
        )

    # Filter to selected plate
    df_plate = df[df['plate_id'] == plate_id]

    if len(df_plate) == 0:
        st.warning("No data for this plate")
        return

    # Parse well positions (e.g., "A01" -> row A, col 1)
    def parse_well(well_id):
        """Parse well ID into row and column."""
        row = ord(well_id[0]) - ord('A')  # A=0, B=1, ...
        col = int(well_id[1:]) - 1  # 01=0, 02=1, ...
        return row, col

    df_plate['row'], df_plate['col'] = zip(*df_plate['well_id'].apply(parse_well))

    # Create 96-well plate grid (8 rows × 12 columns)
    plate_grid = np.full((8, 12), np.nan)

    for _, row_data in df_plate.iterrows():
        plate_grid[row_data['row'], row_data['col']] = row_data[metric]

    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=plate_grid,
        x=[f"{i+1:02d}" for i in range(12)],
        y=[chr(65 + i) for i in range(8)],
        colorscale='Viridis',
        hovertemplate='Row: %{y}<br>Col: %{x}<br>Value: %{z:.1f}<extra></extra>',
        colorbar=dict(title=metric.replace('morph_', '').replace('_', ' ').title())
    ))

    fig.update_layout(
        title=f"Plate Heatmap: {plate_id}<br>{metric.replace('morph_', '').replace('_', ' ').title()}",
        xaxis_title="Column",
        yaxis_title="Row",
        height=600,
        yaxis=dict(autorange='reversed')  # A at top
    )

    st.plotly_chart(fig, use_container_width=True)

    # Edge effect analysis
    st.subheader("Edge Effect Analysis")

    # Define edge wells (row A, H or column 1, 12 for 96-well)
    edge_rows = [0, 7]   # A and H for 96-well
    edge_cols = [0, 11]  # 1 and 12

    df_plate['is_edge'] = df_plate.apply(
        lambda row: row['row'] in edge_rows or row['col'] in edge_cols,
        axis=1
    )

    edge_wells = df_plate[df_plate['is_edge']]
    center_wells = df_plate[~df_plate['is_edge']]

    if len(edge_wells) > 0 and len(center_wells) > 0:
        edge_mean = edge_wells[metric].mean()
        center_mean = center_wells[metric].mean()
        edge_effect = ((edge_mean - center_mean) / center_mean) * 100

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.metric("Edge Wells Mean", f"{edge_mean:.1f}")

        with col_b:
            st.metric("Center Wells Mean", f"{center_mean:.1f}")

        with col_c:
            st.metric("Edge Effect", f"{edge_effect:+.1f}%")

        if abs(edge_effect) > 10:
            st.warning(f"⚠️ Significant edge effect detected ({edge_effect:+.1f}%)")
        else:
            st.success(f"✓ Edge effect within acceptable range ({edge_effect:+.1f}%)")

    # Compound distribution on plate
    with st.expander("🧪 Compound Distribution"):
        st.markdown("Distribution of compounds across the plate")

        compound_counts = df_plate['compound'].value_counts()

        fig_compounds = go.Figure(data=[
            go.Bar(x=compound_counts.index, y=compound_counts.values)
        ])

        fig_compounds.update_layout(
            title="Compounds on This Plate",
            xaxis_title="Compound",
            yaxis_title="Number of Wells",
            height=300
        )

        st.plotly_chart(fig_compounds, use_container_width=True)

    # Sentinel positions
    with st.expander("🎯 Sentinel Positions"):
        df_sentinels = df_plate[df_plate['is_sentinel'] == True]

        if len(df_sentinels) > 0:
            st.markdown(f"**{len(df_sentinels)} sentinel wells** on this plate:")

            for _, sent in df_sentinels.iterrows():
                st.write(f"- **{sent['well_id']}**: {sent['compound']} ({sent['dose_uM']} μM)")
        else:
            st.info("No sentinels on this plate")
