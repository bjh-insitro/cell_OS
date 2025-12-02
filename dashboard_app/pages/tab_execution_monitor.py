# dashboard_app/pages/tab_execution_monitor.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from dashboard_app.utils import init_automation_resources
from cell_os.protocol_resolver import ProtocolResolver
from cell_os.workflow_executor import WorkflowExecutor, ExecutionStatus, StepStatus
from cell_os.job_queue import JobQueue, JobPriority, JobStatus


def render_execution_monitor(df, pricing):
    """Render the Execution Monitor tab."""
    st.header("⚙️ Workflow Execution Monitor")
    st.markdown("""
    Monitor and execute protocols in real-time. View execution history, track progress,
    and manage the job queue.
    """)
    
    # Initialize executor and queue
    try:
        # Get inventory manager
        _, _, _, _, inv_manager = init_automation_resources()
        
        executor = WorkflowExecutor(inventory_manager=inv_manager)
        queue = JobQueue(executor=executor)
    except Exception as e:
        st.error(f"Cannot initialize system: {e}")
        return
    
    # Create tabs for different views
    tab_execute, tab_queue, tab_monitor, tab_history = st.tabs([
        "🚀 Execute Protocol",
        "📋 Job Queue",
        "📊 Active Executions",
        "📜 Execution History"
    ])
    
    with tab_execute:
        render_execute_protocol(executor, queue)
    
    with tab_queue:
        render_job_queue(queue)
    
    with tab_monitor:
        render_active_executions(executor)
    
    with tab_history:
        render_execution_history(executor)


def render_execute_protocol(executor, queue):
    """Render the protocol execution interface."""
    st.subheader("Execute a Protocol")
    
    # Initialize resources
    vessel_lib, inv, ops, builder, inv_manager = init_automation_resources()
    
    if ops is None:
        st.error("Cannot load automation resources.")
        return
    
    # Initialize ProtocolResolver
    try:
        resolver = ProtocolResolver()
        resolver.ops = ops
        ops.resolver = resolver
    except Exception as e:
        st.error(f"Cannot initialize ProtocolResolver: {e}")
        return
    
    # Create input form
    col1, col2, col3 = st.columns(3)
    
    with col1:
        from cell_os.cell_line_database import list_cell_lines
        cell_lines = list_cell_lines()
        selected_cell_line = st.selectbox(
            "Cell Line",
            options=cell_lines,
            help="Select the cell line",
            key="exec_mon_cell_line"
        )
    
    with col2:
        vessels = list(vessel_lib.vessels.keys())
        selected_vessel = st.selectbox(
            "Vessel",
            options=vessels,
            help="Select the culture vessel",
            key="exec_mon_vessel"
        )
    
    with col3:
        operation_types = ["thaw", "passage", "feed"]
        selected_operation = st.selectbox(
            "Operation",
            options=operation_types,
            help="Select the operation type",
            key="exec_mon_operation"
        )
    
    # Execution options
    col_opt1, col_opt2 = st.columns(2)
    
    with col_opt1:
        dry_run = st.checkbox(
            "Dry Run (simulate without executing)",
            value=True,
            help="Enable to simulate execution without actually running hardware"
        )
        
    with col_opt2:
        schedule_later = st.checkbox("Schedule for later")
        
    scheduled_time = None
    if schedule_later:
        scheduled_time = st.time_input("Run at time", value=(datetime.now() + timedelta(minutes=5)).time())
        # Combine with today's date for simplicity in this demo
        scheduled_time = datetime.combine(datetime.now().date(), scheduled_time)
        if scheduled_time < datetime.now():
            scheduled_time += timedelta(days=1)
        st.info(f"Scheduled for: {scheduled_time}")

    priority = st.selectbox(
        "Priority",
        options=[p.name for p in JobPriority],
        index=1, # Normal
        format_func=lambda x: x.title()
    )

    # Execute/Queue button
    btn_label = "📅 Add to Queue" if schedule_later else "🚀 Execute Now"
    
    if st.button(btn_label, type="primary"):
        with st.spinner("Creating protocol..."):
            try:
                # Resolve protocol
                if selected_operation == "passage":
                    parts = selected_vessel.split('_')
                    vessel_type = parts[1].upper() if len(parts) > 1 else parts[-1].upper()
                    unit_ops = resolver.resolve_passage_protocol(selected_cell_line, vessel_type)
                elif selected_operation == "thaw":
                    thaw_op = ops.op_thaw(selected_vessel, cell_line=selected_cell_line)
                    unit_ops = [thaw_op]
                elif selected_operation == "feed":
                    feed_op = ops.op_feed(selected_vessel, cell_line=selected_cell_line)
                    unit_ops = [feed_op]
                else:
                    st.error(f"Unknown operation: {selected_operation}")
                    return
                
                # Create execution
                execution = executor.create_execution_from_protocol(
                    protocol_name=f"{selected_operation.title()} {selected_cell_line} in {selected_vessel}",
                    cell_line=selected_cell_line,
                    vessel_id=selected_vessel,
                    operation_type=selected_operation,
                    unit_ops=unit_ops,
                    metadata={
                        "created_by": "dashboard",
                        "dry_run": dry_run
                    }
                )
                
                if schedule_later or True: # Always use queue for consistency in this enhanced version
                    job = queue.submit_job(
                        execution_id=execution.execution_id,
                        priority=JobPriority[priority],
                        scheduled_time=scheduled_time
                    )
                    st.success(f"✅ Job submitted to queue: {job.job_id}")
                    if not schedule_later:
                         # If immediate, trigger worker once to ensure it picks it up (in a real app, worker runs in background)
                         # For demo purposes, we can manually process if it's immediate
                         with st.spinner("Processing queue..."):
                             queue._execute_job(job)
                             st.success("Job executed!")
                             st.rerun()

            except Exception as e:
                st.error(f"Error: {str(e)}")
                import traceback
                st.code(traceback.format_exc())

def render_job_queue(queue):
    """Render the job queue."""
    st.subheader("📋 Job Queue")
    
    # Stats
    stats = queue.get_queue_stats()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Queued", stats["queued"])
    col2.metric("Scheduled", stats["scheduled"])
    col3.metric("Running", stats["running"])
    col4.metric("Completed", stats["completed"])
    
    st.divider()
    
    # List jobs
    jobs = queue.list_jobs()
    if not jobs:
        st.info("Queue is empty")
        return
        
    data = []
    for job in jobs:
        data.append({
            "Job ID": job.job_id[:8] + "...",
            "Execution ID": job.execution_id[:8] + "...",
            "Priority": job.priority.name,
            "Status": job.status.value,
            "Scheduled": job.scheduled_time.strftime("%H:%M:%S") if job.scheduled_time else "ASAP",
            "Created": job.created_at.strftime("%H:%M:%S")
        })
        
    df_jobs = pd.DataFrame(data)
    st.dataframe(df_jobs, width="stretch", hide_index=True)


def render_active_executions(executor):
    """Render active executions monitor."""
    st.subheader("Active Executions")
    
    # Get running executions
    running = executor.list_executions(status=ExecutionStatus.RUNNING)
    
    if not running:
        st.info("No active executions")
        return
    
    for execution in running:
        with st.expander(f"🔄 {execution.workflow_name} ({execution.execution_id[:8]}...)"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Cell Line", execution.cell_line)
            with col2:
                st.metric("Vessel", execution.vessel_id)
            with col3:
                st.metric("Operation", execution.operation_type)
            
            # Progress bar
            completed_steps = sum(1 for s in execution.steps if s.status == StepStatus.COMPLETED)
            total_steps = len(execution.steps)
            progress = completed_steps / total_steps if total_steps > 0 else 0
            
            st.progress(progress)
            st.caption(f"{completed_steps}/{total_steps} steps completed")
            
            # Current step
            current_step = next((s for s in execution.steps if s.status == StepStatus.RUNNING), None)
            if current_step:
                st.info(f"Currently executing: {current_step.name}")


def render_execution_history(executor):
    """Render execution history."""
    st.subheader("Execution History")
    
    # Filter options
    col1, col2 = st.columns([1, 3])
    
    with col1:
        status_filter = st.selectbox(
            "Filter by Status",
            options=["All", "Completed", "Failed", "Pending"],
            index=0
        )
    
    # Get executions
    if status_filter == "All":
        executions = executor.list_executions()
    else:
        status_map = {
            "Completed": ExecutionStatus.COMPLETED,
            "Failed": ExecutionStatus.FAILED,
            "Pending": ExecutionStatus.PENDING
        }
        executions = executor.list_executions(status=status_map[status_filter])
    
    if not executions:
        st.info("No executions found")
        return
    
    # Display as table
    history_data = []
    for execution in executions:
        duration = "—"
        if execution.started_at and execution.completed_at:
            duration = f"{(execution.completed_at - execution.started_at).total_seconds():.1f}s"
        
        history_data.append({
            "ID": execution.execution_id[:8] + "...",
            "Protocol": execution.workflow_name,
            "Cell Line": execution.cell_line,
            "Vessel": execution.vessel_id,
            "Operation": execution.operation_type,
            "Status": execution.status.value,
            "Steps": f"{sum(1 for s in execution.steps if s.status == StepStatus.COMPLETED)}/{len(execution.steps)}",
            "Duration": duration,
            "Created": execution.created_at.strftime("%Y-%m-%d %H:%M")
        })
    
    df_history = pd.DataFrame(history_data)
    
    # Color code by status
    def color_status(val):
        if val == "completed":
            return "background-color: #d4edda"
        elif val == "failed":
            return "background-color: #f8d7da"
        elif val == "running":
            return "background-color: #fff3cd"
        return ""
    
    styled_df = df_history.style.applymap(color_status, subset=["Status"])
    st.dataframe(styled_df, width="stretch", hide_index=True)
    
    # Detailed view
    st.divider()
    st.subheader("Execution Details")
    
    selected_id = st.selectbox(
        "Select execution to view details",
        options=[e.execution_id for e in executions],
        format_func=lambda x: f"{x[:8]}... - {next(e.workflow_name for e in executions if e.execution_id == x)}"
    )
    
    if selected_id:
        execution = executor.get_execution_status(selected_id)
        
        if execution:
            # Metadata
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Status", execution.status.value.upper())
            with col2:
                st.metric("Total Steps", len(execution.steps))
            with col3:
                completed = sum(1 for s in execution.steps if s.status == StepStatus.COMPLETED)
                st.metric("Completed", completed)
            with col4:
                failed = sum(1 for s in execution.steps if s.status == StepStatus.FAILED)
                st.metric("Failed", failed)
            
            # Step details
            st.subheader("Step-by-Step Log")
            for step in execution.steps:
                status_icon = {
                    StepStatus.COMPLETED: "✅",
                    StepStatus.FAILED: "❌",
                    StepStatus.RUNNING: "🔄",
                    StepStatus.PENDING: "⏳",
                    StepStatus.SKIPPED: "⏭️"
                }
                
                icon = status_icon.get(step.status, "❓")
                
                with st.expander(f"{icon} Step {step.step_index}: {step.name}"):
                    col_a, col_b = st.columns(2)
                    
                    with col_a:
                        st.write("**Type:**", step.operation_type)
                        st.write("**Status:**", step.status.value)
                    
                    with col_b:
                        if step.start_time:
                            st.write("**Started:**", step.start_time.strftime("%H:%M:%S"))
                        if step.end_time:
                            st.write("**Ended:**", step.end_time.strftime("%H:%M:%S"))
                    
                    if step.error_message:
                        st.error(f"Error: {step.error_message}")
                    
                    if step.result:
                        st.json(step.result)


