"""
Interactive Phenotype Explorer

An educational tool for exploring how simulation parameters affect POSH screen results.
Users can adjust parameters in real-time and see how they impact hit calling, 
data quality, and phenotypic clustering.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from cell_os.simulation.posh_screen_wrapper import (
    simulate_posh_screen,
    CELL_PAINTING_FEATURES,
    HIT_RATE,
    P_VALUE_THRESHOLD,
    LOG2FC_THRESHOLD
)


def render_phenotype_explorer():
    """Render the Interactive Phenotype Explorer page."""
    
    st.title("🔬 Interactive Phenotype Explorer")
    st.markdown("""
    **Explore how simulation parameters affect POSH screen results in real-time.**
    
    Adjust the parameters below and watch how they impact:
    - Hit detection sensitivity
    - Data quality and noise
    - Phenotypic clustering
    - Statistical power
    
    This tool helps you understand experimental design trade-offs!
    """)
    
    # Sidebar: Simulation Parameters
    with st.sidebar:
        st.header("⚙️ Simulation Parameters")
        
        st.subheader("Biological Parameters")
        cell_line = st.selectbox(
            "Cell Line",
            ["U2OS", "A549", "HepG2", "iPSC"],
            help="Different cell lines have different baseline morphologies"
        )
        
        treatment = st.selectbox(
            "Treatment",
            ["tBHP", "Staurosporine", "Tunicamycin"],
            help="Different treatments cause different phenotypic changes"
        )
        
        dose = st.slider(
            "Dose (µM)",
            min_value=1.0,
            max_value=100.0,
            value=10.0,
            step=5.0,
            help="Higher doses = stronger phenotypes"
        )
        
        feature = st.selectbox(
            "Phenotypic Feature",
            list(CELL_PAINTING_FEATURES.keys()),
            format_func=lambda x: CELL_PAINTING_FEATURES[x]["name"],
            help="Which morphological feature to analyze"
        )
        
        st.divider()
        
        st.subheader("Experimental Design")
        library_size = st.slider(
            "Library Size (genes)",
            min_value=100,
            max_value=5000,
            value=1000,
            step=100,
            help="Larger libraries = more statistical power but more expensive"
        )
        
        # Advanced parameters in expander
        with st.expander("🔧 Advanced Parameters"):
            st.markdown("**Note**: These parameters are for educational exploration only.")
            st.markdown("*In the real simulation, these are fixed internally.*")
            
            custom_hit_rate = st.slider(
                "Hit Rate (%)",
                min_value=1.0,
                max_value=20.0,
                value=HIT_RATE * 100,
                step=1.0,
                help="Percentage of library that are true hits"
            ) / 100
            
            effect_size_multiplier = st.slider(
                "Effect Size Multiplier",
                min_value=0.5,
                max_value=3.0,
                value=1.0,
                step=0.1,
                help="Amplify or reduce the magnitude of hit effects"
            )
            
            noise_level = st.slider(
                "Biological Noise Level",
                min_value=0.5,
                max_value=2.0,
                value=1.0,
                step=0.1,
                help="Increase or decrease measurement variability"
            )
            
            p_threshold = st.slider(
                "P-value Threshold",
                min_value=0.001,
                max_value=0.1,
                value=P_VALUE_THRESHOLD,
                step=0.005,
                format="%.3f",
                help="Significance threshold for hit calling"
            )
            
            fc_threshold = st.slider(
                "Log2 Fold-Change Threshold",
                min_value=0.5,
                max_value=2.0,
                value=LOG2FC_THRESHOLD,
                step=0.1,
                help="Minimum effect size for hit calling"
            )
        
        st.divider()
        
        random_seed = st.number_input(
            "Random Seed",
            min_value=1,
            max_value=9999,
            value=42,
            help="Change seed for different random realizations"
        )
        
        run_button = st.button("🚀 Run Simulation", type="primary", use_container_width=True)
    
    # Main content area
    if "explorer_result" not in st.session_state:
        st.info("👈 Adjust parameters in the sidebar and click **Run Simulation** to begin!")
        
        # Show example visualization
        st.markdown("### What You'll See:")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**📊 Volcano Plot**")
            st.markdown("- Visualize hit distribution")
            st.markdown("- See effect sizes vs significance")
        with col2:
            st.markdown("**🗺️ UMAP Clustering**")
            st.markdown("- Explore phenotypic landscape")
            st.markdown("- Identify hit clusters")
        
        st.markdown("**📈 Statistical Diagnostics**")
        st.markdown("- Power analysis")
        st.markdown("- False discovery rate estimates")
        st.markdown("- Data quality metrics")
        
        return
    
    if run_button:
        with st.spinner(f"Running simulation with {library_size} genes..."):
            # Run simulation
            result = simulate_posh_screen(
                cell_line=cell_line,
                treatment=treatment,
                dose_uM=dose,
                library_size=library_size,
                feature=feature,
                random_seed=random_seed
            )
            
            # Store in session state
            st.session_state.explorer_result = result
            st.session_state.explorer_params = {
                "cell_line": cell_line,
                "treatment": treatment,
                "dose": dose,
                "library_size": library_size,
                "feature": feature,
                "custom_hit_rate": custom_hit_rate,
                "effect_size_multiplier": effect_size_multiplier,
                "noise_level": noise_level,
                "p_threshold": p_threshold,
                "fc_threshold": fc_threshold,
                "random_seed": random_seed
            }
            st.rerun()
    
    # Display results
    if "explorer_result" in st.session_state:
        result = st.session_state.explorer_result
        params = st.session_state.explorer_params
        
        if not result.success:
            st.error(f"❌ Simulation failed: {result.error_message}")
            return
        
        # Header with key metrics
        st.success(f"✅ Simulation Complete!")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Hits Identified", len(result.hit_list))
        with col2:
            hit_rate_observed = len(result.hit_list) / params["library_size"] * 100
            st.metric("Hit Rate", f"{hit_rate_observed:.1f}%")
        with col3:
            if len(result.hit_list) > 0:
                avg_fc = abs(result.hit_list["Log2FoldChange"]).mean()
                st.metric("Avg |Log2FC|", f"{avg_fc:.2f}")
            else:
                st.metric("Avg |Log2FC|", "N/A")
        with col4:
            if len(result.hit_list) > 0:
                avg_p = result.hit_list["P_Value"].mean()
                st.metric("Avg P-value", f"{avg_p:.2e}")
            else:
                st.metric("Avg P-value", "N/A")
        
        st.divider()
        
        # Tabs for different views
        tab_volcano, tab_umap, tab_stats, tab_data = st.tabs([
            "🌋 Volcano Plot",
            "🗺️ UMAP Clustering",
            "📊 Statistical Diagnostics",
            "📋 Raw Data"
        ])
        
        with tab_volcano:
            render_volcano_tab(result, params)
        
        with tab_umap:
            render_umap_tab(result, params)
        
        with tab_stats:
            render_stats_tab(result, params)
        
        with tab_data:
            render_data_tab(result, params)


def render_volcano_tab(result, params):
    """Render the volcano plot tab."""
    st.markdown("### Volcano Plot: Effect Size vs Significance")
    
    feature_info = CELL_PAINTING_FEATURES[result.selected_feature]
    
    # Create volcano plot
    fig = px.scatter(
        result.volcano_data,
        x="Log2FoldChange",
        y="NegLog10P",
        color="Category",
        hover_data=["Gene"],
        title=f"{params['cell_line']} + {params['treatment']} ({params['dose']}µM) - {feature_info['name']}",
        color_discrete_map={
            "Non-targeting": "lightgrey",
            "Enhancer": "#FF5722",
            "Suppressor": "#2196F3"
        },
        opacity=0.7,
        labels={
            "Log2FoldChange": f"{feature_info['name']} Effect ({feature_info['unit']})",
            "NegLog10P": "-log10(P-value)"
        },
        height=600
    )
    
    # Add threshold lines
    fig.add_hline(
        y=-np.log10(params.get("p_threshold", P_VALUE_THRESHOLD)),
        line_dash="dash",
        line_color="grey",
        annotation_text=f"p={params.get('p_threshold', P_VALUE_THRESHOLD)}"
    )
    fig.add_vline(
        x=params.get("fc_threshold", LOG2FC_THRESHOLD),
        line_dash="dash",
        line_color="grey"
    )
    fig.add_vline(
        x=-params.get("fc_threshold", LOG2FC_THRESHOLD),
        line_dash="dash",
        line_color="grey"
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Interpretation
    st.info(f"""
    **Interpretation:**
    - 🔴 **Enhancers** ({len(result.hit_list[result.hit_list['Log2FoldChange'] > 0])}): Increase {feature_info['name'].lower()}
    - 🔵 **Suppressors** ({len(result.hit_list[result.hit_list['Log2FoldChange'] < 0])}): Decrease {feature_info['name'].lower()}
    - ⚪ **Non-hits** ({len(result.volcano_data) - len(result.hit_list)}): No significant effect
    
    **Thresholds**: P < {params.get('p_threshold', P_VALUE_THRESHOLD)}, |Log2FC| > {params.get('fc_threshold', LOG2FC_THRESHOLD)}
    """)


def render_umap_tab(result, params):
    """Render the UMAP clustering tab."""
    st.markdown("### UMAP: Phenotypic Landscape")
    
    # Merge projection with volcano data
    df_umap = pd.merge(
        result.projection_2d,
        result.volcano_data[["Gene", "Log2FoldChange", "P_Value", "Category"]],
        on="Gene"
    )
    
    # Create UMAP plot colored by hit status
    fig = px.scatter(
        df_umap,
        x="UMAP_1",
        y="UMAP_2",
        color="Category",
        hover_data=["Gene", "Log2FoldChange", "P_Value"],
        title="Phenotypic Clustering (UMAP Projection)",
        color_discrete_map={
            "Non-targeting": "lightgray",
            "Enhancer": "#FF5722",
            "Suppressor": "#2196F3"
        },
        opacity=0.7,
        height=600
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.info("""
    **What is UMAP?**
    - UMAP (Uniform Manifold Approximation and Projection) reduces 128-dimensional embeddings to 2D
    - Points close together have similar phenotypes
    - Hits often form distinct clusters away from controls
    - This visualization helps identify phenotypic subgroups
    """)
    
    # Show cluster statistics
    if len(result.hit_list) > 0:
        st.markdown("#### Cluster Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Hit Spatial Distribution**")
            hit_genes = result.hit_list["Gene"].tolist()
            df_hits = df_umap[df_umap["Gene"].isin(hit_genes)]
            
            st.metric("Hit Cluster Spread (std)", f"{df_hits['UMAP_1'].std():.2f}")
            st.metric("Control Cluster Spread (std)", f"{df_umap[~df_umap['Gene'].isin(hit_genes)]['UMAP_1'].std():.2f}")
        
        with col2:
            st.markdown("**Separation Quality**")
            # Calculate distance between hit and control centroids
            hit_centroid = df_hits[["UMAP_1", "UMAP_2"]].mean()
            control_centroid = df_umap[~df_umap["Gene"].isin(hit_genes)][["UMAP_1", "UMAP_2"]].mean()
            separation = np.sqrt((hit_centroid["UMAP_1"] - control_centroid["UMAP_1"])**2 + 
                                (hit_centroid["UMAP_2"] - control_centroid["UMAP_2"])**2)
            st.metric("Centroid Separation", f"{separation:.2f}")


def render_stats_tab(result, params):
    """Render statistical diagnostics tab."""
    st.markdown("### Statistical Diagnostics")
    
    # Power analysis
    st.markdown("#### Statistical Power")
    col1, col2 = st.columns(2)
    
    with col1:
        # Estimate power based on observed hits
        expected_hits = params["library_size"] * params.get("custom_hit_rate", HIT_RATE)
        observed_hits = len(result.hit_list)
        power_estimate = min(1.0, observed_hits / max(1, expected_hits))
        
        st.metric(
            "Estimated Power",
            f"{power_estimate*100:.1f}%",
            help="Proportion of true hits successfully detected"
        )
        
        st.metric(
            "Expected Hits",
            f"{expected_hits:.0f}",
            help=f"Based on {params.get('custom_hit_rate', HIT_RATE)*100:.0f}% hit rate"
        )
    
    with col2:
        st.metric("Observed Hits", observed_hits)
        
        if observed_hits > 0:
            # Estimate FDR (simplified)
            fdr_estimate = max(0, 1 - power_estimate)
            st.metric(
                "Est. False Discovery Rate",
                f"{fdr_estimate*100:.1f}%",
                help="Estimated proportion of hits that are false positives"
            )
    
    st.divider()
    
    # Distribution analysis
    st.markdown("#### Data Quality Metrics")
    
    feature_info = CELL_PAINTING_FEATURES[result.selected_feature]
    feature_map = {
        "mitochondrial_fragmentation": "Mitochondrial_Fragmentation",
        "nuclear_size": "Nucleus_Area",
        "er_stress_score": "ER_Stress_Score",
        "cell_count": "Cell_Area"
    }
    col_name = feature_map.get(result.selected_feature, "Mitochondrial_Fragmentation")
    
    if col_name in result.raw_measurements.columns:
        values = result.raw_measurements[col_name]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Mean", f"{values.mean():.2f}")
        with col2:
            st.metric("Std Dev", f"{values.std():.2f}")
        with col3:
            cv = (values.std() / values.mean()) * 100
            st.metric("CV (%)", f"{cv:.1f}")
        
        # Distribution plot
        fig = px.histogram(
            result.raw_measurements,
            x=col_name,
            nbins=50,
            title=f"Distribution of {feature_info['name']}",
            labels={col_name: feature_info['name']}
        )
        st.plotly_chart(fig, use_container_width=True)


def render_data_tab(result, params):
    """Render raw data tab."""
    st.markdown("### Raw Data Tables")
    
    tab_hits, tab_volcano, tab_raw = st.tabs(["Hit List", "Volcano Data", "Raw Measurements"])
    
    with tab_hits:
        st.markdown(f"**{len(result.hit_list)} hits identified**")
        st.dataframe(result.hit_list, use_container_width=True)
        
        # Download button
        csv = result.hit_list.to_csv(index=False)
        st.download_button(
            "⬇️ Download Hit List (CSV)",
            csv,
            f"hits_{params['cell_line']}_{params['treatment']}.csv",
            "text/csv"
        )
    
    with tab_volcano:
        st.markdown(f"**{len(result.volcano_data)} genes analyzed**")
        st.dataframe(result.volcano_data, use_container_width=True)
    
    with tab_raw:
        st.markdown(f"**Raw measurements for {len(result.raw_measurements)} genes**")
        st.dataframe(result.raw_measurements.head(100), use_container_width=True)
        st.caption("Showing first 100 rows")
