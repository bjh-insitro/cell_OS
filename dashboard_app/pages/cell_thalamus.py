"""
Cell Thalamus Dashboard - Interactive exploration of Phase 0 variance validation

6 tabs:
1. Run Simulation - Execute Phase 0 campaigns
2. Morphology Manifold - PCA/UMAP visualization
3. Dose-Response Explorer - Compound response curves
4. Variance Analysis - Mixed model results
5. Sentinel Monitor - SPC control charts
6. Plate Viewer - Spatial heatmaps
"""

import streamlit as st
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from cell_thalamus.tab_1_run_simulation import render_tab_1
from cell_thalamus.tab_2_morphology_manifold import render_tab_2
from cell_thalamus.tab_3_dose_response import render_tab_3
from cell_thalamus.tab_4_variance_analysis import render_tab_4
from cell_thalamus.tab_5_sentinel_monitor import render_tab_5
from cell_thalamus.tab_6_plate_viewer import render_tab_6

st.set_page_config(
    page_title="Cell Thalamus v1",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Header
st.title("🧬 Cell Thalamus v1 - Variance-Aware Measurement Validation")
st.markdown("""
**Goal**: Prove that stress biology rails are real, variance is honest, and morphology manifolds are learnable.

Cell Thalamus validates the measurement layer *before* scaling to the Printed Tensor.
""")

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "▶️ Run Simulation",
    "🎨 Morphology Manifold",
    "📈 Dose-Response",
    "📊 Variance Analysis",
    "🎯 Sentinel Monitor",
    "🗺️ Plate Viewer"
])

with tab1:
    render_tab_1()

with tab2:
    render_tab_2()

with tab3:
    render_tab_3()

with tab4:
    render_tab_4()

with tab5:
    render_tab_5()

with tab6:
    render_tab_6()
