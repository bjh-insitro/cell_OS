"""Tab 2: Morphology Manifold - PCA/UMAP visualization"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import sys
from pathlib import Path

src_path = Path(__file__).parent.parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from cell_os.database.cell_thalamus_db import CellThalamusDB


def render_tab_2():
    """Render the Morphology Manifold tab."""

    st.header("Morphology Manifold Exploration")
    st.markdown("Interactive PCA visualization of 5-channel Cell Painting features")

    with st.expander("ℹ️ Understanding the Morphology Manifold", expanded=False):
        st.markdown("""
        **What is this showing?**
        - Each point = one well with 5 morphology measurements (ER, Mito, Nucleus, Actin, RNA)
        - PCA reduces 5 dimensions → 2 or 3 dimensions for visualization
        - Points close together = similar morphology
        - Points far apart = different morphology

        **What to look for:**
        - **Stress axis clustering**: Do compounds from the same stress axis (e.g., oxidative) cluster together?
        - **Dose-response gradients**: Do higher doses move along consistent directions?
        - **Cell line separation**: Do different cell lines occupy distinct regions?
        - **Outliers**: Are there any wells with unusual morphology?

        **Good manifold properties:**
        - Biological factors dominate the structure
        - Stress axes are separable
        - Technical replicates cluster tightly
        """)

    # Get design ID
    design_id = get_design_id()

    if not design_id:
        st.info("Run a simulation in Tab 1 first, or enter a Design ID below")
        design_id = st.text_input("Design ID")
        if not design_id:
            return

    db_path = st.session_state.get('db_path', 'data/cell_thalamus.db')
    db = CellThalamusDB(db_path=db_path)

    # Load data
    results = db.get_results(design_id)

    if not results:
        st.error(f"No results found for Design ID: {design_id}")
        return

    df = pd.DataFrame(results)

    st.success(f"Loaded {len(df)} wells from design {design_id}")

    # Filters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        include_sentinels = st.checkbox("Include Sentinels", value=False)

    with col2:
        selected_cell_lines = st.multiselect(
            "Cell Lines",
            options=df['cell_line'].unique().tolist(),
            default=df['cell_line'].unique().tolist()
        )

    with col3:
        selected_compounds = st.multiselect(
            "Compounds",
            options=df['compound'].unique().tolist(),
            default=df['compound'].unique().tolist()[:5]  # First 5 by default
        )

    with col4:
        color_by = st.selectbox(
            "Color By",
            options=['compound', 'cell_line', 'dose_uM', 'timepoint_h', 'stress_axis']
        )

    # Filter data
    if not include_sentinels:
        df = df[df['is_sentinel'] == False]

    df = df[df['cell_line'].isin(selected_cell_lines)]
    df = df[df['compound'].isin(selected_compounds)]

    if len(df) == 0:
        st.warning("No data matches the selected filters")
        return

    # Add stress axis for coloring
    compound_to_axis = {
        'tBHQ': 'oxidative',
        'hydrogen_peroxide': 'oxidative',
        'tunicamycin': 'er_stress',
        'thapsigargin': 'er_stress',
        'etoposide': 'dna_damage',
        'cccp': 'mitochondrial',
        'oligomycin_a': 'mitochondrial',
        'two_deoxy_d_glucose': 'mitochondrial',
        'mg132': 'proteasome',
        'nocodazole': 'microtubule',
        'DMSO': 'control'
    }
    df['stress_axis'] = df['compound'].map(compound_to_axis)

    # Run PCA
    morphology_features = ['morph_er', 'morph_mito', 'morph_nucleus', 'morph_actin', 'morph_rna']
    X = df[morphology_features].values

    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # PCA
    pca = PCA(n_components=3)
    X_pca = pca.fit_transform(X_scaled)

    df['PC1'] = X_pca[:, 0]
    df['PC2'] = X_pca[:, 1]
    df['PC3'] = X_pca[:, 2]

    # Explained variance
    explained_var = pca.explained_variance_ratio_

    # Display explained variance
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("PC1 Variance", f"{explained_var[0]*100:.1f}%")
    with col_b:
        st.metric("PC2 Variance", f"{explained_var[1]*100:.1f}%")
    with col_c:
        st.metric("PC3 Variance", f"{explained_var[2]*100:.1f}%")

    # 2D or 3D toggle
    plot_mode = st.radio("Visualization", options=["2D (PC1 vs PC2)", "3D (PC1, PC2, PC3)"], horizontal=True)

    # Create plot
    if plot_mode == "2D (PC1 vs PC2)":
        fig = px.scatter(
            df,
            x='PC1',
            y='PC2',
            color=color_by,
            hover_data=['well_id', 'compound', 'dose_uM', 'cell_line', 'timepoint_h'],
            title=f"Morphology Manifold (Colored by {color_by})",
            labels={'PC1': f'PC1 ({explained_var[0]*100:.1f}%)', 'PC2': f'PC2 ({explained_var[1]*100:.1f}%)'}
        )
        fig.update_traces(marker=dict(size=6, opacity=0.7))

    else:  # 3D
        fig = px.scatter_3d(
            df,
            x='PC1',
            y='PC2',
            z='PC3',
            color=color_by,
            hover_data=['well_id', 'compound', 'dose_uM', 'cell_line', 'timepoint_h'],
            title=f"Morphology Manifold 3D (Colored by {color_by})",
            labels={
                'PC1': f'PC1 ({explained_var[0]*100:.1f}%)',
                'PC2': f'PC2 ({explained_var[1]*100:.1f}%)',
                'PC3': f'PC3 ({explained_var[2]*100:.1f}%)'
            }
        )
        fig.update_traces(marker=dict(size=4, opacity=0.6))

    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True)

    # Component loadings
    with st.expander("📊 PCA Component Loadings"):
        loadings_df = pd.DataFrame(
            pca.components_.T,
            columns=['PC1', 'PC2', 'PC3'],
            index=['ER', 'Mito', 'Nucleus', 'Actin', 'RNA']
        )
        st.dataframe(loadings_df.style.background_gradient(cmap='RdBu', axis=None))


def get_design_id():
    """Get design ID from session state."""
    return st.session_state.get('latest_design_id')
