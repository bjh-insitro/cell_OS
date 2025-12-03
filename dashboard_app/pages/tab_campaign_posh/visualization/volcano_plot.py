import streamlit as st
import plotly.express as px
import numpy as np
from cell_os.simulation.posh_screen_wrapper import CELL_PAINTING_FEATURES

def render_volcano_plot(s_result, screen_cell_line, treatment, dose):
    """Render the Volcano Plot tab content."""
    feature_info = CELL_PAINTING_FEATURES[s_result.selected_feature]
    
    fig_vol = px.scatter(
        s_result.volcano_data,
        x="Log2FoldChange",
        y="NegLog10P",
        color="Category",
        hover_data=["Gene"],
        title=f"Cell Painting POSH Screen: {screen_cell_line} + {treatment} ({dose}µM)<br><sub>Feature: {feature_info['name']}</sub>",
        color_discrete_map={
            "Non-targeting": "lightgrey",
            "Enhancer": "#FF5722",
            "Suppressor": "#2196F3"
        },
        opacity=0.7,
        labels={"Log2FoldChange": f"{feature_info['name']} Effect ({feature_info['unit']})"}
    )
    fig_vol.add_hline(y=-np.log10(0.05), line_dash="dash", line_color="grey", annotation_text="p=0.05")
    
    st.plotly_chart(fig_vol, use_container_width=True, key="volcano_plot")
    
    # Add interpretation
    st.info(f"""**Interpretation:** 
    - 🔴 **Enhancers** (right): Genes that increase {feature_info['name'].lower()} when knocked out
    - 🔵 **Suppressors** (left): Genes that decrease {feature_info['name'].lower()} when knocked out
    - ⚪ **Non-targeting**: Genes with no significant effect on this phenotype
    """)
