import streamlit as st
import pandas as pd

def render_raw_measurements(s_result, treatment, dose):
    """Render the Raw Measurements tab content."""
    st.subheader("🔬 Raw Imaging Measurements")
    st.markdown(f"""Showing raw fluorescence measurements from MitoTracker channel.  
    **Treatment:** {treatment} ({dose}µM)""")
    
    # Display raw data table
    with st.expander("View Raw Data Table", expanded=False):
        st.dataframe(s_result.raw_measurements, use_container_width=True)
    
    # Summary statistics - dynamic based on feature
    st.markdown("### Summary Statistics")
    
    if s_result.selected_feature == "mitochondrial_fragmentation":
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Mean Intensity",
                f"{s_result.raw_measurements['Mito_Mean_Intensity'].mean():.0f}",
                help="Average MitoTracker fluorescence intensity"
            )
        with col2:
            st.metric(
                "Avg Object Count",
                f"{s_result.raw_measurements['Mito_Object_Count'].mean():.1f}",
                help="Average number of mitochondrial objects per cell"
            )
        with col3:
            st.metric(
                "Avg Total Area",
                f"{s_result.raw_measurements['Mito_Total_Area'].mean():.0f}",
                help="Average total mitochondrial area (pixels)"
            )
        with col4:
            # Check for both possible column names for backward compatibility
            frag_col = "Mitochondrial_Fragmentation" if "Mitochondrial_Fragmentation" in s_result.raw_measurements.columns else "Fragmentation_Index"
            if frag_col in s_result.raw_measurements.columns:
                st.metric(
                    "Avg Fragmentation",
                    f"{s_result.raw_measurements[frag_col].mean():.2f}",
                    help="Calculated from: Object Count / (Total Area / 100)"
                )
    
    elif s_result.selected_feature == "nuclear_size":
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Mean Nuc Area", f"{s_result.raw_measurements['Nucleus_Area'].mean():.0f}")
        with col2:
            st.metric("Mean Nuc Intensity", f"{s_result.raw_measurements['Nucleus_Mean_Intensity'].mean():.0f}")
        with col3:
            st.metric("Mean Form Factor", f"{s_result.raw_measurements['Nucleus_Form_Factor'].mean():.2f}")
        with col4:
            if "Nuclear_Condensation" in s_result.raw_measurements.columns:
                st.metric("Avg Condensation", f"{s_result.raw_measurements['Nuclear_Condensation'].mean():.2f}")
    
    else:
        st.info(f"Summary statistics for {s_result.selected_feature} not yet implemented.")
