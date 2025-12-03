import streamlit as st
import plotly.express as px
from dashboard_app.pages.tab_campaign_posh.components.digital_cell_viewer import render_digital_cell_viewer

def render_channel_intensities(s_result):
    """Render the Channel Intensities tab content."""
    st.markdown("### Cell Painting Channel Intensities")
    st.markdown("Raw fluorescence intensity values (AFU) from the 5-channel Cell Painting panel. These represent what the microscope actually sees before segmentation.")
    
    # Summary metrics
    cols = st.columns(5)
    channels = ["Hoechst", "ConA", "Phalloidin", "WGA", "MitoProbe"]
    targets = ["Nucleus", "ER", "Actin", "Golgi", "Mito"]
    
    for i, (chan, target) in enumerate(zip(channels, targets)):
        with cols[i]:
            if chan in s_result.channel_intensities.columns:
                mean_val = s_result.channel_intensities[chan].mean()
                st.metric(f"{chan} ({target})", f"{mean_val:.0f}")
            
    # Correlation plot
    st.markdown("### Channel Correlations")
    
    col_x, col_y = st.columns(2)
    with col_x:
        x_axis = st.selectbox("X Axis Channel", channels, index=4, key="chan_x") # MitoProbe default
    with col_y:
        y_axis = st.selectbox("Y Axis Channel", channels, index=0, key="chan_y") # Hoechst default
        
    fig_corr = px.scatter(
        s_result.channel_intensities,
        x=x_axis,
        y=y_axis,
        hover_data=["Gene"],
        title=f"Channel Correlation: {x_axis} vs {y_axis}",
        opacity=0.6,
        color_discrete_sequence=["#5F9EA0"]
    )
    st.plotly_chart(fig_corr, use_container_width=True, key="chan_corr_plot")
    
    # Distributions
    st.markdown("### Intensity Distributions")
    
    # Melt for plotting
    df_melt = s_result.channel_intensities.melt(id_vars=["Gene"], value_vars=channels)
    
    # Colors for channels
    colors = ["#4169E1", "#32CD32", "#FF4500", "#FFD700", "#8B0000"]
    
    fig_dist = px.histogram(
        df_melt,
        x="value",
        color="variable",
        barmode="overlay",
        title="Fluorescence Intensity Distributions",
        labels={"value": "Intensity (AFU)", "variable": "Channel"},
        opacity=0.6,
        color_discrete_map=dict(zip(channels, colors))
    )
    st.plotly_chart(fig_dist, use_container_width=True, key="chan_dist_plot")
    
    st.info("💡 **Interpretation:** Shifts in intensity distributions indicate global cellular responses. For example, reduced MitoProbe intensity indicates mitochondrial depolarization (loss of membrane potential).")
    
    # Render Digital Cell Viewer Component
    render_digital_cell_viewer(s_result)
