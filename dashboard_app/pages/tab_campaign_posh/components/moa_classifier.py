import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from cell_os.simulation.posh_screen_wrapper import MOA_ALIGNMENT_THRESHOLD

def classify_and_render_moa(s_result, df_umap):
    """Classify hits by Mechanism of Action and render MoA plots."""
    st.markdown("---")
    st.markdown("#### 🧬 Mechanism of Action (MoA) Classification")
    
    if not s_result.hit_list.empty and not s_result.embeddings.empty:
        # Calculate stress vector in embedding space
        hit_genes = s_result.hit_list["Gene"].tolist()
        
        # Get control genes (non-hits)
        control_genes = s_result.volcano_data[~s_result.volcano_data["Gene"].isin(hit_genes)]["Gene"].tolist()
        
        # Get embeddings for controls and calculate mean (baseline)
        control_embeds = s_result.embeddings[s_result.embeddings["Gene"].isin(control_genes)]
        embed_cols = [c for c in control_embeds.columns if c.startswith("DIM_")]
        baseline_embed = control_embeds[embed_cols].mean().values
        
        # Calculate mean of all genes (stressed state)
        all_embed_mean = s_result.embeddings[embed_cols].mean().values
        
        # Stress vector: direction from baseline to stressed
        stress_vector = all_embed_mean - baseline_embed
        stress_vector_norm = stress_vector / (np.linalg.norm(stress_vector) + 1e-10)
        
        # For each hit, calculate its direction relative to stress vector
        hit_embeds = s_result.embeddings[s_result.embeddings["Gene"].isin(hit_genes)]
        
        moa_data = []
        for _, row in hit_embeds.iterrows():
            gene = row["Gene"]
            gene_embed = row[embed_cols].values
            
            # Vector from baseline to this gene
            gene_vector = gene_embed - baseline_embed
            gene_vector_norm = gene_vector / (np.linalg.norm(gene_vector) + 1e-10)
            
            # Dot product: measures alignment with stress vector
            # +1 = same direction (enhancer), -1 = opposite (suppressor), 0 = orthogonal
            alignment = np.dot(gene_vector_norm, stress_vector_norm)
            
            # Magnitude: how far from baseline
            magnitude = np.linalg.norm(gene_vector)
            
            # Classify using constant
            if alignment > MOA_ALIGNMENT_THRESHOLD:
                moa = "Enhancer"
                color = "#FF4B4B"
            elif alignment < -MOA_ALIGNMENT_THRESHOLD:
                moa = "Suppressor"
                color = "#00CC66"
            else:
                moa = "Orthogonal"
                color = "#FFA500"
            
            moa_data.append({
                "Gene": gene,
                "MoA": moa,
                "Alignment": alignment,
                "Magnitude": magnitude,
                "Color": color
            })
        
        df_moa = pd.DataFrame(moa_data)
        
        # Merge with UMAP for visualization
        df_umap_moa = pd.merge(df_umap[df_umap["Phenotype"] == "Hit"], df_moa, on="Gene")
        
        # MoA-colored UMAP
        fig_moa = px.scatter(
            df_umap_moa,
            x="UMAP_1",
            y="UMAP_2",
            color="MoA",
            hover_data=["Gene", "Alignment", "Magnitude"],
            title="Mechanism of Action Classification",
            color_discrete_map={"Enhancer": "#FF4B4B", "Suppressor": "#00CC66", "Orthogonal": "#FFA500"},
            opacity=0.8,
            size="Magnitude",
            size_max=15
        )
        st.plotly_chart(fig_moa, use_container_width=True, key="moa_plot")
        
        # Summary table
        col_moa1, col_moa2, col_moa3 = st.columns(3)
        
        with col_moa1:
            enhancers = df_moa[df_moa["MoA"] == "Enhancer"]
            st.metric("Enhancers", len(enhancers), help="Hits that amplify the stress phenotype")
            if not enhancers.empty:
                st.dataframe(enhancers.sort_values("Magnitude", ascending=False).head(5)[["Gene", "Magnitude"]], use_container_width=True, hide_index=True)
                
        with col_moa2:
            suppressors = df_moa[df_moa["MoA"] == "Suppressor"]
            st.metric("Suppressors", len(suppressors), help="Hits that reverse the stress phenotype")
            if not suppressors.empty:
                st.dataframe(suppressors.sort_values("Magnitude", ascending=False).head(5)[["Gene", "Magnitude"]], use_container_width=True, hide_index=True)
                
        with col_moa3:
            orthogonal = df_moa[df_moa["MoA"] == "Orthogonal"]
            st.metric("Orthogonal", len(orthogonal), help="Hits that cause a different phenotype")
            if not orthogonal.empty:
                st.dataframe(orthogonal.sort_values("Magnitude", ascending=False).head(5)[["Gene", "Magnitude"]], use_container_width=True, hide_index=True)
                
        st.info(f"💡 **How it works:** We calculate a 'Stress Vector' from Control to Treated state in the 128-d embedding space. Hits aligned with this vector (> {MOA_ALIGNMENT_THRESHOLD}) are Enhancers. Hits opposed (< -{MOA_ALIGNMENT_THRESHOLD}) are Suppressors.")
    else:
        st.info("No hits identified to classify.")
