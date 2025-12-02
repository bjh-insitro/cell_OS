# dashboard_app/pages/tab_10_assay_development.py
import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
from dashboard_app.utils import get_inventory_handles
from cell_os.tbhp_dose_finder import TBHPDoseFinder, TBHPOptimizationCriteria
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.cell_line_database import list_cell_lines

def render_assay_development(df, pricing):
    st.header("🧪 Assay Development & Optimization")
    st.markdown("""
    Design and simulate assay optimization experiments. 
    Currently supports **Oxidative Stress (tBHP) Dose Finding** for CellROX assays.
    """)
    
    # Initialize virtual machine
    vm = BiologicalVirtualMachine()
    
    # Tabs for different assay types
    tab_oxidative, tab_viability = st.tabs(["Oxidative Stress (tBHP)", "Viability Assays"])
    
    with tab_oxidative:
        st.subheader("tBHP Dose Finding Simulation")
        st.markdown("""
        Find the optimal concentration of tert-Butyl hydroperoxide (tBHP) to induce 
        measurable oxidative stress (CellROX signal) without excessive toxicity.
        """)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            with st.form("tbhp_config"):
                st.markdown("### Experiment Config")
                
                # Cell Line Selection
                cell_lines = list_cell_lines()
                if not cell_lines:
                    cell_lines = ["iPSC", "HEK293", "U2OS", "HepG2", "A549"]
                
                selected_cell_line = st.selectbox("Cell Line", cell_lines)
                
                # Dose Range
                st.markdown("#### Dose Range (µM)")
                min_dose = st.number_input("Min Dose", value=0.0, step=10.0)
                max_dose = st.number_input("Max Dose", value=500.0, step=50.0)
                n_doses = st.number_input("Number of Points", value=12, min_value=4, max_value=24)
                
                # Optimization Criteria
                st.markdown("#### Success Criteria")
                min_viability = st.slider("Min Viability", 0.0, 1.0, 0.70, 0.05)
                target_signal = st.number_input("Target Signal (RFU)", value=200.0)
                min_seg_quality = st.slider("Min Segmentation Quality", 0.0, 1.0, 0.80, 0.05)
                
                submitted = st.form_submit_button("Run Simulation", type="primary")
        
        with col2:
            if submitted:
                with st.spinner(f"Simulating dose response for {selected_cell_line}..."):
                    # Setup finder
                    criteria = TBHPOptimizationCriteria(
                        min_viability=min_viability,
                        target_cellrox_signal=target_signal,
                        min_segmentation_quality=min_seg_quality
                    )
                    finder = TBHPDoseFinder(vm, criteria)
                    
                    # Run simulation
                    result = finder.run_dose_finding(
                        cell_line=selected_cell_line,
                        dose_range=(min_dose, max_dose),
                        n_doses=n_doses
                    )
                    
                    # Display Result
                    if result.status == "success":
                        st.success(f"✅ Optimal Dose Found: **{result.optimal_dose_uM:.1f} µM**")
                        
                        # Store in session state for other tabs
                        if "optimal_dose_results" not in st.session_state:
                            st.session_state.optimal_dose_results = {}
                        st.session_state.optimal_dose_results[selected_cell_line] = result.optimal_dose_uM
                        
                    elif result.status == "suboptimal":
                        st.warning(f"⚠️ Suboptimal Dose Found: **{result.optimal_dose_uM:.1f} µM** (Signal target not fully met)")
                    else:
                        st.error(f"❌ Optimization Failed: {result.status}")
                        st.info(f"Best compromise: **{result.optimal_dose_uM:.1f} µM**")
                    
                    # Metrics at optimal
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Viability", f"{result.viability_at_optimal:.1%}", 
                             delta=f"{result.viability_at_optimal - min_viability:.1%}", delta_color="normal")
                    m2.metric("CellROX Signal", f"{result.cellrox_signal_at_optimal:.1f}", 
                             delta=f"{result.cellrox_signal_at_optimal - target_signal:.1f}", delta_color="normal")
                    m3.metric("Segmentation", f"{result.segmentation_quality_at_optimal:.1%}", 
                             delta=f"{result.segmentation_quality_at_optimal - min_seg_quality:.1%}", delta_color="normal")
                    
                    # Plot Dose Response
                    st.subheader("Dose Response Curves")
                    
                    df_res = result.dose_response_curve
                    
                    # Melt for plotting
                    df_melt = df_res.melt(id_vars=["dose_uM"], 
                                         value_vars=["viability", "segmentation_quality"],
                                         var_name="Metric", value_name="Value")
                    
                    # Base chart
                    base = alt.Chart(df_res).encode(x=alt.X("dose_uM", title="tBHP Dose (µM)"))
                    
                    # Signal line (left axis)
                    signal_line = base.mark_line(color="#FF5722", point=True).encode(
                        y=alt.Y("cellrox_signal", title="CellROX Signal (RFU)"),
                        tooltip=["dose_uM", "cellrox_signal"]
                    )
                    
                    # Viability/Seg line (right axis)
                    # Altair dual axis is tricky, let's just plot separate or normalized
                    
                    # Normalized plot
                    df_res["Signal (Norm)"] = df_res["cellrox_signal"] / df_res["cellrox_signal"].max()
                    
                    df_plot = df_res.melt(id_vars=["dose_uM"], 
                                         value_vars=["viability", "segmentation_quality", "Signal (Norm)"],
                                         var_name="Metric", value_name="Value")
                    
                    chart = alt.Chart(df_plot).mark_line(point=True).encode(
                        x=alt.X("dose_uM", title="tBHP Dose (µM)"),
                        y=alt.Y("Value", title="Normalized Value (0-1)"),
                        color=alt.Color("Metric", scale={"domain": ["viability", "segmentation_quality", "Signal (Norm)"], 
                                                        "range": ["#4CAF50", "#2196F3", "#FF5722"]}),
                        tooltip=["dose_uM", "Metric", "Value"]
                    ).properties(height=400).interactive()
                    
                    # Add optimal dose rule
                    rule = alt.Chart(pd.DataFrame({'x': [result.optimal_dose_uM]})).mark_rule(color='black', strokeDash=[5, 5]).encode(x='x')
                    
                    st.altair_chart(chart + rule, use_container_width=True)
                    
                    # Data Table
                    with st.expander("View Raw Data"):
                        st.dataframe(df_res)

    with tab_viability:
        st.info("Viability assay simulation coming soon.")
