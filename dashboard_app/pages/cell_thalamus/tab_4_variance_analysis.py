"""Tab 4: Variance Analysis - Mixed models and variance partitioning"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path

src_path = Path(__file__).parent.parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from cell_os.database.cell_thalamus_db import CellThalamusDB
from cell_os.cell_thalamus.variance_analysis import VarianceAnalyzer


def render_tab_4():
    """Render the Variance Analysis tab."""

    st.header("Variance Component Analysis")
    st.markdown("Partition variance into biological vs technical sources")

    with st.expander("ℹ️ Understanding Variance Analysis", expanded=False):
        st.markdown("""
        **Why variance matters:**
        Cell Thalamus validates that **biological factors dominate technical noise** before scaling experiments.

        **Variance components explained:**

        **🧬 Biological Variance (GOOD - want this high):**
        - **Cell line**: Different cell types respond differently
        - **Compound**: Different stressors produce different phenotypes
        - **Dose**: Higher doses = stronger effects
        - **Timepoint**: Effects change over time

        **🔧 Technical Variance (BAD - want this low):**
        - **Plate**: Variation between physical plates
        - **Day**: Day-to-day experimental variation
        - **Operator**: Different people handling samples

        **Success criteria:**
        - ✅ **Biological >70%**: Real biology is the dominant signal
        - ✅ **Technical <30%**: Measurement noise is controlled
        - ✅ **Sentinels stable**: Quality control wells are reproducible

        **What this means:**
        If biological variance dominates, the measurements are trustworthy and differences you see are real biology, not experimental artifacts.
        """)

    # Get design ID
    design_id = st.session_state.get('latest_design_id')

    if not design_id:
        st.info("Run a simulation in Tab 1 first")
        return

    db_path = st.session_state.get('db_path', 'data/cell_thalamus.db')
    db = CellThalamusDB(db_path=db_path)

    # Run analysis
    with st.spinner("Running variance analysis..."):
        analyzer = VarianceAnalyzer(db)
        analysis_results = analyzer.analyze_design(design_id)

    if 'error' in analysis_results:
        st.error(analysis_results['error'])
        return

    # Display summary
    summary = analysis_results['summary']

    st.subheader("✅ Success Criteria")

    col1, col2, col3 = st.columns(3)

    with col1:
        bio_frac = summary['biological_fraction_mean']
        bio_pass = summary['criteria']['biological_dominance']['pass']
        st.metric(
            "Biological Variance",
            f"{bio_frac*100:.1f}%",
            delta="Pass" if bio_pass else "Fail",
            delta_color="normal" if bio_pass else "inverse"
        )
        if bio_pass:
            st.success("✓ Biological factors dominate (>70%)")
        else:
            st.error("✗ Biological factors too weak (<70%)")

    with col2:
        tech_frac = summary['technical_fraction_mean']
        tech_pass = summary['criteria']['technical_control']['pass']
        st.metric(
            "Technical Variance",
            f"{tech_frac*100:.1f}%",
            delta="Pass" if tech_pass else "Fail",
            delta_color="normal" if tech_pass else "inverse"
        )
        if tech_pass:
            st.success("✓ Technical noise controlled (<30%)")
        else:
            st.error("✗ Technical noise too high (>30%)")

    with col3:
        sentinel_pass = summary['criteria']['sentinel_stability']['pass']
        st.metric(
            "Sentinels",
            "In Control" if sentinel_pass else "Out of Control",
            delta="Pass" if sentinel_pass else "Fail",
            delta_color="normal" if sentinel_pass else "inverse"
        )
        if sentinel_pass:
            st.success("✓ Sentinels stable")
        else:
            st.warning("✗ Some sentinels out of control")

    if summary['overall_pass']:
        st.success("🎉 **PHASE 0 SUCCESS**: All criteria met! Rails are validated.")
    else:
        st.warning("⚠️ **PHASE 0 INCOMPLETE**: Some criteria not met. Review variance structure.")

    st.markdown("---")

    # Variance components by metric
    st.subheader("Variance Components by Metric")

    variance_components = analysis_results['variance_components']

    # Create stacked bar chart
    metrics = list(variance_components.keys())
    bio_fracs = [variance_components[m]['biological_fraction'] for m in metrics]
    tech_fracs = [variance_components[m]['technical_fraction'] for m in metrics]
    res_fracs = [variance_components[m]['residual_fraction'] for m in metrics]

    fig = go.Figure(data=[
        go.Bar(name='Biological', x=metrics, y=[f*100 for f in bio_fracs], marker_color='green'),
        go.Bar(name='Technical', x=metrics, y=[f*100 for f in tech_fracs], marker_color='orange'),
        go.Bar(name='Residual', x=metrics, y=[f*100 for f in res_fracs], marker_color='gray')
    ])

    fig.update_layout(
        barmode='stack',
        title="Variance Decomposition",
        xaxis_title="Metric",
        yaxis_title="Variance (%)",
        height=400,
        yaxis=dict(range=[0, 100])
    )

    st.plotly_chart(fig, use_container_width=True)

    # Detailed components
    st.subheader("Detailed Variance Components")

    metric_to_analyze = st.selectbox(
        "Select metric for detailed breakdown",
        options=metrics,
        format_func=lambda x: x.replace('morph_', '').replace('_', ' ').title()
    )

    components = variance_components[metric_to_analyze]['components']

    # Bar chart of individual components
    component_names = list(components.keys())
    component_values = [components[c] for c in component_names]

    fig_detail = go.Figure(data=[
        go.Bar(
            x=component_names,
            y=component_values,
            marker_color=['green', 'green', 'green', 'green', 'orange', 'orange', 'orange']
        )
    ])

    fig_detail.update_layout(
        title=f"Individual Components: {metric_to_analyze}",
        xaxis_title="Factor",
        yaxis_title="Variance",
        height=350
    )

    st.plotly_chart(fig_detail, use_container_width=True)

    # Component table
    components_df = pd.DataFrame([
        {'Factor': name, 'Variance': value, 'Type': 'Biological' if name in ['compound', 'dose', 'cell_line', 'timepoint'] else 'Technical'}
        for name, value in components.items()
    ])
    components_df = components_df.sort_values('Variance', ascending=False)

    st.dataframe(
        components_df.style.format({'Variance': '{:.2f}'}).background_gradient(subset=['Variance'], cmap='Greens'),
        use_container_width=True
    )
