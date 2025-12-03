import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse
import matplotlib.patheffects as path_effects
import numpy as np
from cell_os.simulation.posh_screen_wrapper import CHANNEL_MAX_VALUES

def render_digital_cell_viewer(s_result):
    """Render the Digital Cell Viewer component."""
    st.markdown("---")
    st.markdown("### 🔬 Digital Cell Viewer")
    st.markdown("Visualize what a representative cell looks like based on the simulated channel intensities.")
    
    col_sel, col_view = st.columns([1, 2])
    
    with col_sel:
        # Select a gene to view
        # Default to a hit if available
        default_gene = s_result.hit_list.iloc[0]["Gene"] if not s_result.hit_list.empty else s_result.channel_intensities.iloc[0]["Gene"]
        selected_gene = st.selectbox("Select Gene to Visualize", s_result.channel_intensities["Gene"].unique(), index=list(s_result.channel_intensities["Gene"]).index(default_gene))
        
        # Get data for this gene
        gene_data = s_result.channel_intensities[s_result.channel_intensities["Gene"] == selected_gene].iloc[0]
        
        st.markdown("**Channel Values:**")
        st.code(f"""
Hoechst (Nuc): {gene_data['Hoechst']:.0f}
ConA (ER):     {gene_data['ConA']:.0f}
Phalloidin:    {gene_data['Phalloidin']:.0f}
WGA (Golgi):   {gene_data['WGA']:.0f}
MitoProbe:     {gene_data['MitoProbe']:.0f}
        """)
        
        # Normalize for display using constants
        norm_vals = {
            "Hoechst": min(1.0, gene_data['Hoechst'] / CHANNEL_MAX_VALUES["Hoechst"]),
            "ConA": min(1.0, gene_data['ConA'] / CHANNEL_MAX_VALUES["ConA"]),
            "Phalloidin": min(1.0, gene_data['Phalloidin'] / CHANNEL_MAX_VALUES["Phalloidin"]),
            "WGA": min(1.0, gene_data['WGA'] / CHANNEL_MAX_VALUES["WGA"]),
            "MitoProbe": min(1.0, gene_data['MitoProbe'] / CHANNEL_MAX_VALUES["MitoProbe"]),
        }
        
    with col_view:
        # Draw synthetic cell using matplotlib
        fig, ax = plt.subplots(figsize=(6, 6), facecolor='black')
        ax.set_facecolor('black')
        ax.set_xlim(-10, 10)
        ax.set_ylim(-10, 10)
        ax.axis('off')
        
        # 1. Actin (Phalloidin) - Red/Orange - Cell Body Outline
        # Irregular shape simulated by multiple ellipses
        alpha_act = norm_vals["Phalloidin"] * 0.6
        cell_body = Ellipse((0, 0), 16, 14, angle=15, color='#FF4500', alpha=alpha_act)
        ax.add_patch(cell_body)
        
        # 2. ER (ConA) - Green - Perinuclear cloud
        alpha_er = norm_vals["ConA"] * 0.5
        er_cloud = Ellipse((0.5, 0.5), 12, 10, angle=-10, color='#32CD32', alpha=alpha_er)
        ax.add_patch(er_cloud)
        
        # 3. Mitochondria (MitoProbe) - Deep Red/Cyan - Scattered points
        # We draw random points to simulate mito network
        alpha_mito = norm_vals["MitoProbe"]
        num_mito = int(50 * alpha_mito) + 10
        mx = np.random.normal(0, 4, num_mito)
        my = np.random.normal(0, 4, num_mito)
        ax.scatter(mx, my, c='#00FFFF', s=15, alpha=alpha_mito*0.8, edgecolors='none')
        
        # 4. Golgi (WGA) - Yellow - Near nucleus
        alpha_wga = norm_vals["WGA"] * 0.7
        golgi = Ellipse((2, 2), 3, 2, angle=45, color='#FFD700', alpha=alpha_wga)
        ax.add_patch(golgi)
        
        # 5. Nucleus (Hoechst) - Blue - Center
        alpha_nuc = norm_vals["Hoechst"]
        # Size also depends on intensity (condensation)
        # In our sim, higher intensity = smaller area (condensation)
        # So we invert the size relationship slightly for visual effect
        nuc_size = 6.0 * (1.0 - (alpha_nuc - 0.5) * 0.5) 
        nucleus = Circle((0, 0), nuc_size/2, color='#4169E1', alpha=0.9)
        # Add glow
        nucleus.set_path_effects([path_effects.withStroke(linewidth=3, foreground='#4169E1', alpha=0.3)])
        ax.add_patch(nucleus)
        
        st.pyplot(fig)
        st.caption(f"Synthetic Composite Image: {selected_gene}")
