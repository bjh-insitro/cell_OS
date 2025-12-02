"""
Campaign Manager Dashboard Tab

Design and schedule high-throughput experimental campaigns.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from dashboard_app.utils import init_automation_resources
from cell_os.campaign_manager import CampaignManager
from cell_os.job_queue import JobQueue
from cell_os.workflow_executor import WorkflowExecutor
from cell_os.protocol_resolver import ProtocolResolver

def render_campaign_manager(df, pricing):
    """Render the Campaign Manager tab."""
    st.header("🗓️ Campaign Manager")
    st.markdown("""
    Design and schedule high-throughput experimental campaigns.
    """)
    
    # Initialize resources
    vessel_lib, inv, ops, builder, inv_manager = init_automation_resources()
    
    if ops is None:
        st.error("Cannot load automation resources.")
        return
        
    # Initialize system components
    try:
        executor = WorkflowExecutor(inventory_manager=inv_manager)
        queue = JobQueue(executor=executor)
        
        # Ensure resolver is linked
        if not hasattr(ops, 'resolver') or ops.resolver is None:
            resolver = ProtocolResolver()
            resolver.ops = ops
            ops.resolver = resolver
        else:
            resolver = ops.resolver
            
        campaign_manager = CampaignManager(queue, executor, resolver)
        
    except Exception as e:
        st.error(f"Cannot initialize campaign manager: {e}")
        return
        
    # Tabs
    tab_create, tab_active = st.tabs(["✨ Design Campaign", "📋 Active Campaigns"])
    
    with tab_create:
        render_create_campaign(campaign_manager, vessel_lib)
        
    with tab_active:
        render_active_campaigns(campaign_manager)

def render_create_campaign(manager, vessel_lib):
    """Render campaign creation wizard."""
    st.subheader("Design New Campaign")
    
    with st.form("campaign_form"):
        name = st.text_input("Campaign Name", placeholder="e.g., HEK293T Maintenance - Nov 2025")
        description = st.text_area("Description")
        
        st.divider()
        st.write("### Schedule Parameters")
        
        col1, col2 = st.columns(2)
        with col1:
            from cell_os.cell_line_database import list_cell_lines
            cell_lines = list_cell_lines()
            cell_line = st.selectbox("Cell Line", options=cell_lines, key="camp_mgr_cell_line")
            
            vessels = list(vessel_lib.vessels.keys())
            vessel_id = st.selectbox("Vessel", options=vessels, key="camp_mgr_vessel")
            
        with col2:
            start_date = st.date_input("Start Date", value=datetime.now())
            duration = st.number_input("Duration (Days)", min_value=1, value=14)
            
        col3, col4 = st.columns(2)
        with col3:
            passage_interval = st.number_input("Passage Interval (Days)", min_value=1, value=3)
        with col4:
            feed_interval = st.number_input("Feed Interval (Days)", min_value=1, value=1)
            
        submitted = st.form_submit_button("Generate Schedule")
        
    if submitted:
        if not name:
            st.error("Please enter a campaign name.")
            return
            
        # Create campaign
        campaign = manager.create_campaign(name, description)
        
        # Generate schedule
        start_dt = datetime.combine(start_date, datetime.min.time())
        manager.generate_maintenance_schedule(
            campaign.campaign_id,
            cell_line,
            vessel_id,
            start_dt,
            duration,
            passage_interval,
            feed_interval
        )
        
        st.success(f"Campaign '{name}' created!")
        st.session_state["selected_campaign_id"] = campaign.campaign_id
        st.rerun()

    # If a campaign was just created or selected, show preview
    if "selected_campaign_id" in st.session_state:
        campaign_id = st.session_state["selected_campaign_id"]
        jobs = manager.db.get_campaign_jobs(campaign_id)
        
        if jobs:
            st.divider()
            st.subheader("Schedule Preview")
            
            # Convert to DataFrame
            data = []
            for job in jobs:
                data.append({
                    "Date": job.scheduled_time.strftime("%Y-%m-%d"),
                    "Time": job.scheduled_time.strftime("%H:%M"),
                    "Operation": job.operation_type.title(),
                    "Protocol": job.protocol_name,
                    "Status": job.status
                })
            
            st.dataframe(pd.DataFrame(data), width="stretch")
            
            if st.button("🚀 Submit Campaign to Queue", type="primary"):
                with st.spinner("Submitting jobs..."):
                    manager.submit_campaign(campaign_id)
                st.success("All jobs submitted to queue!")
                del st.session_state["selected_campaign_id"]
                st.rerun()

def render_active_campaigns(manager):
    """Render active campaigns."""
    campaigns = manager.db.list_campaigns()
    
    if not campaigns:
        st.info("No campaigns found.")
        return
        
    for campaign in campaigns:
        with st.expander(f"📅 {campaign.name} ({campaign.status})"):
            st.write(f"**Created:** {campaign.created_at.strftime('%Y-%m-%d')}")
            st.write(f"**Description:** {campaign.description}")
            
            jobs = manager.db.get_campaign_jobs(campaign.campaign_id)
            if jobs:
                # Progress
                total = len(jobs)
                submitted = sum(1 for j in jobs if j.status == "submitted")
                completed = sum(1 for j in jobs if j.status == "completed") # Note: status update logic needed
                
                st.progress(submitted / total)
                st.caption(f"{submitted}/{total} jobs submitted")
                
                # Job list
                data = []
                for job in jobs:
                    data.append({
                        "Scheduled": job.scheduled_time.strftime("%Y-%m-%d %H:%M"),
                        "Operation": job.operation_type,
                        "Status": job.status,
                        "Job ID": job.job_id[:8] + "..." if job.job_id else "—"
                    })
                st.dataframe(pd.DataFrame(data), width="stretch")
