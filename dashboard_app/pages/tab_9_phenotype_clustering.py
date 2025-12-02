# dashboard_app/pages/tab_9_phenotype_clustering.py
import streamlit as st
import pandas as pd
import altair as alt
import tempfile
import traceback
from dashboard_app.utils import load_dino_embeddings_from_csv, ExperimentDB, datetime

def render_phenotype_clustering(df, pricing):
    st.header("🧬 Phenotype Clustering")
    st.markdown("Analyze DINO embeddings to identify morphological hits and visualize phenotypic space.")
    
    # File upload
    st.subheader("1. Load DINO Embeddings")
    
    uploaded_file = st.file_uploader(
        "Upload CSV with DINO embeddings",
        type=['csv'],
        help="CSV should have columns: gene, guide_id, embedding (JSON array)"
    )
    
    if uploaded_file is not None:
        try:
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name
            
            # Load via DINO analyzer
            analyzer = load_dino_embeddings_from_csv(tmp_path)
            
            st.success(f"✅ Loaded {len(analyzer.embeddings)} embeddings ({analyzer.embedding_dim}D)")
            
            # Store in session state
            st.session_state['dino_analyzer'] = analyzer
            
        except Exception as e:
            st.error(f"Failed to load embeddings: {e}")
            st.code(traceback.format_exc())
    
    # Analysis section
    if 'dino_analyzer' in st.session_state:
        analyzer = st.session_state['dino_analyzer']
        
        st.divider()
        st.subheader("2. Hit Calling")
        
        with st.form("hit_calling_params"):
            col1, col2 = st.columns(2)
            
            with col1:
                threshold = st.slider("Z-score Threshold", 0.5, 5.0, 2.0, 0.5)
                min_guides = st.number_input("Min Guides per Gene", 1, 10, 2)
            
            with col2:
                aggregate = st.selectbox("Aggregation Method", ['mean', 'median', 'max'])
            
            if st.form_submit_button("Call Hits", type="primary"):
                with st.spinner("Computing D_M and calling hits..."):
                    try:
                        hits = analyzer.call_hits(threshold=threshold, min_guides=min_guides)
                        st.session_state['hits'] = hits
                        
                        # Save to database
                        
                        # Prompt for experiment ID
                        experiment_id = st.text_input(
                            "Link to Experiment ID (optional)",
                            value="DINO_ANALYSIS_" + datetime.now().strftime("%Y%m%d_%H%M%S"),
                            key="dino_exp_id"
                        )
                        
                        db = ExperimentDB()
                        db.save_dino_results(experiment_id, hits)
                        db.close()
                        
                        n_hits = hits['hit_status'].sum()
                        st.success(f"✅ Found {n_hits} hits out of {len(hits)} genes")
                        st.info(f"Results saved to database with ID: {experiment_id}")
                        
                    except Exception as e:
                        st.error(f"Hit calling failed: {e}")
        
        # Display hits
        if 'hits' in st.session_state:
            hits = st.session_state['hits']
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Genes", len(hits))
            col2.metric("Hits", hits['hit_status'].sum())
            col3.metric("Hit Rate", f"{hits['hit_status'].mean():.1%}")
            
            st.subheader("Hit List")
            st.dataframe(
                hits.style.background_gradient(subset=['d_m', 'z_score'], cmap='Reds'),
                width="stretch"
            )
            
            # Export hits
            csv = hits.to_csv(index=False)
            st.download_button(
                label="📥 Download Hit List (CSV)",
                data=csv,
                file_name="posh_hits.csv",
                mime="text/csv"
            )
        
        # Dimensionality reduction
        st.divider()
        st.subheader("3. Phenotypic Space Visualization")
        
        with st.form("dim_reduction"):
            col1, col2 = st.columns(2)
            
            with col1:
                method = st.selectbox("Method", ['umap', 'tsne'])
            
            with col2:
                n_neighbors = st.slider("Neighbors (UMAP)", 5, 50, 15) if method == 'umap' else 30
            
            if st.form_submit_button("Generate Visualization"):
                with st.spinner(f"Running {method.upper()}..."):
                    try:
                        if method == 'umap':
                            reduced_df = analyzer.reduce_dimensions(method='umap', n_neighbors=n_neighbors)
                        else:
                            reduced_df = analyzer.reduce_dimensions(method='tsne', perplexity=30)
                        
                        st.session_state['reduced_df'] = reduced_df
                        st.success(f"✅ {method.upper()} complete")
                        
                    except Exception as e:
                        st.error(f"Dimensionality reduction failed: {e}")
                        st.info("Install dependencies: pip install umap-learn scikit-learn")
        
        # Plot reduced dimensions
        if 'reduced_df' in st.session_state:
            reduced_df = st.session_state['reduced_df']
            
            # Interactive scatter plot
            color_by = st.selectbox("Color by", ['gene', 'd_m'])
            
            if color_by == 'd_m' and 'd_m' in reduced_df.columns:
                chart = alt.Chart(reduced_df).mark_circle(size=60).encode(
                    x=alt.X('dim1:Q', title='Dimension 1'),
                    y=alt.Y('dim2:Q', title='Dimension 2'),
                    color=alt.Color('d_m:Q', scale=alt.Scale(scheme='viridis'), title='D_M (Morphological Distance)'),
                    tooltip=['gene:N', 'guide_id:N', alt.Tooltip('d_m:Q', format='.3f')]
                ).interactive().properties(
                    width=700,
                    height=500,
                    title='Phenotypic Space (DINO Embeddings)'
                )
            else:
                chart = alt.Chart(reduced_df).mark_circle(size=60).encode(
                    x=alt.X('dim1:Q', title='Dimension 1'),
                    y=alt.Y('dim2:Q', title='Dimension 2'),
                    color='gene:N',
                    tooltip=['gene:N', 'guide_id:N']
                ).interactive().properties(
                    width=700,
                    height=500,
                    title='Phenotype Clustering'
                )
            
            st.altair_chart(chart, width="stretch")
            
            # Export reduced data
            csv = reduced_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Reduced Embeddings (CSV)",
                data=csv,
                file_name="phenotype_clustering.csv",
                mime="text/csv"
            )
    
    else:
        st.info("👆 Upload a CSV file with DINO embeddings to get started.")
        
        st.markdown("""
        ### Expected CSV Format
        
        | gene | guide_id | embedding |
        |------|----------|-----------|
        | TP53 | TP53_g1  | [0.12,-0.34,...] |
        | KRAS | KRAS_g1  | [0.45,0.21,...] |
        
        **Notes:**
        - `embedding` column should contain JSON array or comma-separated values
        - Embedding dimension is auto-detected (typically 384 for DINOv2-S)
        - Include NTC (non-targeting control) genes for D_M calculation
        """)