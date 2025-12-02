"""
Enhanced Analytics Dashboard Tab

Provides insights into workflow executions, success rates, resource usage, and costs.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from cell_os.workflow_executor import WorkflowExecutor, ExecutionStatus, StepStatus

def render_analytics(df, pricing):
    """Render the Analytics tab."""
    st.header("📈 Enhanced Analytics")
    st.markdown("""
    Analyze execution performance, success rates, and operational metrics.
    """)
    
    executor = WorkflowExecutor()
    executions = executor.list_executions()
    
    if not executions:
        st.info("No execution data available yet. Run some protocols to generate analytics.")
        return

    # Convert to DataFrame for analysis
    data = []
    for ex in executions:
        duration = 0
        if ex.started_at and ex.completed_at:
            duration = (ex.completed_at - ex.started_at).total_seconds()
            
        data.append({
            "id": ex.execution_id,
            "name": ex.workflow_name,
            "cell_line": ex.cell_line,
            "operation": ex.operation_type,
            "status": ex.status.value,
            "created_at": ex.created_at,
            "duration_seconds": duration,
            "steps_count": len(ex.steps),
            "date": ex.created_at.date()
        })
    
    df_exec = pd.DataFrame(data)
    
    # --- Key Metrics ---
    st.subheader("Key Performance Indicators")
    col1, col2, col3, col4 = st.columns(4)
    
    total_runs = len(df_exec)
    success_rate = (len(df_exec[df_exec['status'] == 'completed']) / total_runs) * 100
    avg_duration = df_exec[df_exec['status'] == 'completed']['duration_seconds'].mean()
    failed_runs = len(df_exec[df_exec['status'] == 'failed'])
    
    col1.metric("Total Executions", total_runs)
    col2.metric("Success Rate", f"{success_rate:.1f}%")
    col3.metric("Avg Duration", f"{avg_duration:.1f}s")
    col4.metric("Failed Runs", failed_runs, delta=-failed_runs, delta_color="inverse")
    
    st.divider()
    
    # --- Charts ---
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("Execution Status Distribution")
        status_counts = df_exec['status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        
        fig_status = px.pie(
            status_counts, 
            values='Count', 
            names='Status',
            color='Status',
            color_discrete_map={
                'completed': '#28a745',
                'failed': '#dc3545',
                'running': '#ffc107',
                'pending': '#6c757d'
            },
            hole=0.4
        )
        st.plotly_chart(
            fig_status,
        use_container_width=True,
            key="analytics_status_distribution"
        )
        
    with col_chart2:
        st.subheader("Executions Over Time")
        daily_counts = df_exec.groupby('date').size().reset_index(name='Count')
        fig_timeline = px.bar(daily_counts, x='date', y='Count', title="Daily Execution Volume")
        st.plotly_chart(
            fig_timeline,
        use_container_width=True,
            key="analytics_execution_timeline"
        )
        
    # --- Detailed Analysis ---
    st.subheader("Protocol Performance")
    
    # Group by operation type
    op_stats = df_exec.groupby('operation').agg({
        'id': 'count',
        'duration_seconds': 'mean',
        'status': lambda x: (x == 'completed').mean() * 100
    }).reset_index()
    
    op_stats.columns = ['Operation', 'Count', 'Avg Duration (s)', 'Success Rate (%)']
    op_stats['Avg Duration (s)'] = op_stats['Avg Duration (s)'].round(1)
    op_stats['Success Rate (%)'] = op_stats['Success Rate (%)'].round(1)
    
    st.dataframe(
        op_stats, 
        width="stretch",
        column_config={
            "Success Rate (%)": st.column_config.ProgressColumn(
                "Success Rate",
                format="%.1f%%",
                min_value=0,
                max_value=100,
            )
        }
    )
    
    # --- Cell Line Usage ---
    st.subheader("Cell Line Activity")
    cell_counts = df_exec['cell_line'].value_counts().reset_index()
    cell_counts.columns = ['Cell Line', 'Executions']
    
    fig_cells = px.bar(
        cell_counts, 
        x='Cell Line', 
        y='Executions',
        color='Executions',
        color_continuous_scale='Viridis'
    )
    st.plotly_chart(
        fig_cells,
        width="stretch",
        key="analytics_cell_line_activity"
    )
