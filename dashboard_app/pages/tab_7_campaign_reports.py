# dashboard_app/pages/tab_7_campaign_reports.py
import streamlit as st
import os

def render_campaign_reports(df, pricing):
    st.header("📊 Campaign Reports")
    
    # Scan for reports
    results_dir = "results/campaigns"
    if os.path.exists(results_dir):
        reports = [f for f in os.listdir(results_dir) if f.endswith("_report.html")]
        reports.sort(reverse=True) # Newest first
        
        if reports:
            selected_report = st.selectbox("Select Report", reports)
            
            if selected_report:
                report_path = os.path.join(results_dir, selected_report)
                
                # Option to open in new tab
                # This uses absolute path, which is OS-specific and may need adjustment
                st.markdown(f"**[Open {selected_report} in new tab](file://{os.path.abspath(report_path)})** (Local only)")
                
                # Read and display (iframe)
                try:
                    with open(report_path, 'r') as f:
                        html_content = f.read()
                    
                    st.components.v1.html(html_content, height=800, scrolling=True)
                except Exception as e:
                    st.error(f"Could not read report file: {e}")
        else:
            st.info("No HTML reports found in results/campaigns/")
    else:
        st.warning(f"Results directory not found: {results_dir}")