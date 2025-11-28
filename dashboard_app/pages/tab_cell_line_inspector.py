# dashboard_app/pages/tab_cell_line_inspector.py

import streamlit as st
import pandas as pd
from dashboard_app.utils import init_automation_resources
from cell_os.protocol_resolver import ProtocolResolver
from cell_os.cell_line_database import list_cell_lines


def resolve_protocol(cell_line, vessel_id, operation_type, ops, resolver):
    """
    Resolve a protocol for the given cell line, vessel, and operation type.
    
    Returns:
        tuple: (steps_list, error_message)
        - steps_list: List of step dictionaries with keys: index, name, reagent, volume_ml, cost_usd
        - error_message: Error string if resolution failed, None otherwise
    """
    try:
        if operation_type == "passage":
            # Infer vessel type from vessel_id
            parts = vessel_id.split('_')
            if len(parts) > 1 and parts[0] == "flask":
                vessel_type = parts[1].upper()
            else:
                vessel_type = parts[-1].upper()
            
            # Use resolver to get passage protocol
            unit_ops = resolver.resolve_passage_protocol(cell_line, vessel_type)
            
        elif operation_type == "thaw":
            # Use op_thaw with cell_line parameter
            thaw_op = ops.op_thaw(vessel_id, cell_line=cell_line)
            unit_ops = [thaw_op]
            
        elif operation_type == "feed":
            # Use op_feed with cell_line parameter
            feed_op = ops.op_feed(vessel_id, cell_line=cell_line)
            unit_ops = [feed_op]
            
        else:
            return None, f"Unknown operation type: {operation_type}"
        
        # Convert unit ops to step dictionaries
        steps = []
        for idx, uo in enumerate(unit_ops):
            # If this is a composite op with sub_steps, expand them
            if hasattr(uo, 'sub_steps') and uo.sub_steps:
                for sub_idx, sub_step in enumerate(uo.sub_steps):
                    steps.append({
                        'index': f"{idx+1}.{sub_idx+1}",
                        'name': sub_step.name if hasattr(sub_step, 'name') else 'Unnamed Step',
                        'reagent': extract_reagent_from_step(sub_step),
                        'volume_ml': extract_volume_from_step(sub_step),
                        'cost_usd': sub_step.material_cost_usd if hasattr(sub_step, 'material_cost_usd') else 0.0
                    })
            else:
                steps.append({
                    'index': idx + 1,
                    'name': uo.name if hasattr(uo, 'name') else 'Unnamed Step',
                    'reagent': extract_reagent_from_step(uo),
                    'volume_ml': extract_volume_from_step(uo),
                    'cost_usd': uo.material_cost_usd if hasattr(uo, 'material_cost_usd') else 0.0
                })
        
        return steps, None
        
    except Exception as e:
        return None, f"Error resolving protocol: {str(e)}"


def extract_reagent_from_step(step):
    """Extract reagent name from step name or attributes."""
    if not hasattr(step, 'name'):
        return "N/A"
    
    name = step.name.lower()
    
    # Common reagent patterns
    reagents = {
        'mtesr': 'mTeSR Plus',
        'dmem': 'DMEM',
        'dpbs': 'DPBS',
        'accutase': 'Accutase',
        'trypsin': 'Trypsin-EDTA',
        'laminin': 'Laminin-521',
        'vitronectin': 'Vitronectin',
        'versene': 'Versene (EDTA)',
    }
    
    for key, value in reagents.items():
        if key in name:
            return value
    
    return "N/A"


def extract_volume_from_step(step):
    """Extract volume from step name."""
    if not hasattr(step, 'name'):
        return None
    
    import re
    name = step.name
    
    # Look for patterns like "15.0mL" or "15.0 mL"
    match = re.search(r'(\d+\.?\d*)\s*ml', name, re.IGNORECASE)
    if match:
        return float(match.group(1))
    
    return None


def render_cell_line_inspector(df, pricing):
    """Render the Cell Line Inspector tab."""
    st.header("🔬 Cell Line Inspector")
    st.markdown("""
    Inspect the exact protocols that cell_OS will execute for different cell lines and operations.
    All protocols are driven by the YAML configuration in `data/cell_lines.yaml`.
    """)
    
    # Initialize resources
    vessel_lib, inv, ops, builder, inv_manager = init_automation_resources()
    
    if ops is None:
        st.error("Cannot load automation resources. Check configuration files.")
        return
    
    # Initialize ProtocolResolver
    try:
        resolver = ProtocolResolver()
        resolver.ops = ops  # Link ops to resolver
        ops.resolver = resolver  # Link resolver to ops
    except Exception as e:
        st.error(f"Cannot initialize ProtocolResolver: {e}")
        return
    
    st.success("✅ Protocol engine initialized")
    
    # Create three columns for inputs
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Get available cell lines
        try:
            cell_lines = list_cell_lines()
            if not cell_lines:
                cell_lines = ["iPSC", "HEK293", "HEK293T", "HeLa"]
        except:
            cell_lines = ["iPSC", "HEK293", "HEK293T", "HeLa"]
        
        selected_cell_line = st.selectbox(
            "Cell Line",
            options=cell_lines,
            help="Select the cell line to inspect"
        )
    
    with col2:
        # Get available vessels
        vessels = list(vessel_lib.vessels.keys())
        if not vessels:
            vessels = ["flask_t75", "flask_t25", "plate_6well"]
        
        selected_vessel = st.selectbox(
            "Vessel",
            options=vessels,
            help="Select the culture vessel"
        )
    
    with col3:
        operation_types = ["thaw", "passage", "feed"]
        selected_operation = st.selectbox(
            "Operation",
            options=operation_types,
            help="Select the operation to inspect"
        )
    
    # Add a resolve button
    if st.button("🔍 Resolve Protocol", type="primary"):
        with st.spinner("Resolving protocol..."):
            steps, error = resolve_protocol(
                selected_cell_line,
                selected_vessel,
                selected_operation,
                ops,
                resolver
            )
            
            if error:
                st.error(error)
            elif not steps:
                st.warning("No steps generated for this protocol.")
            else:
                # Display protocol steps
                st.subheader(f"Protocol: {selected_operation.title()} {selected_cell_line} in {selected_vessel}")
                
                # Create DataFrame for display
                df_steps = pd.DataFrame(steps)
                
                # Format the display
                display_df = df_steps.copy()
                display_df['cost_usd'] = display_df['cost_usd'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "$0.00")
                display_df['volume_ml'] = display_df['volume_ml'].apply(
                    lambda x: f"{x:.1f} mL" if pd.notna(x) and x is not None else "—"
                )
                
                # Rename columns for display
                display_df.columns = ['#', 'Step Description', 'Reagent', 'Volume', 'Cost']
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                # Calculate and display cost summary
                total_cost = df_steps['cost_usd'].sum()
                
                st.divider()
                
                col_summary1, col_summary2, col_summary3 = st.columns(3)
                
                with col_summary1:
                    st.metric("Total Steps", len(steps))
                
                with col_summary2:
                    st.metric("Estimated Cost", f"${total_cost:.2f}")
                
                with col_summary3:
                    # Count reagent types
                    reagents = df_steps[df_steps['reagent'] != 'N/A']['reagent'].unique()
                    st.metric("Reagents Used", len(reagents))
                
                # Show reagent breakdown
                if len(reagents) > 0:
                    st.subheader("Reagent Summary")
                    reagent_costs = df_steps[df_steps['reagent'] != 'N/A'].groupby('reagent')['cost_usd'].sum()
                    reagent_df = pd.DataFrame({
                        'Reagent': reagent_costs.index,
                        'Total Cost': reagent_costs.values
                    })
                    reagent_df['Total Cost'] = reagent_df['Total Cost'].apply(lambda x: f"${x:.2f}")
                    st.dataframe(reagent_df, use_container_width=True, hide_index=True)
                
                # Store resolved protocol in session state for execution
                st.session_state['last_resolved_protocol'] = {
                    'cell_line': selected_cell_line,
                    'vessel_id': selected_vessel,
                    'operation_type': selected_operation,
                    'steps': steps,
                    'total_cost': total_cost
                }
                
                # Add execution button
                st.divider()
                st.subheader("⚙️ Execute Protocol")
                
                col_exec1, col_exec2 = st.columns([3, 1])
                
                with col_exec1:
                    dry_run = st.checkbox(
                        "Dry Run (simulate without executing)",
                        value=True,
                        help="Enable to simulate execution without running hardware",
                        key="inspector_dry_run"
                    )
                
                with col_exec2:
                    if st.button("🚀 Execute Now", type="secondary", use_container_width=True):
                        # Import executor
                        from cell_os.workflow_executor import WorkflowExecutor, ExecutionStatus, StepStatus
                        
                        try:
                            executor = WorkflowExecutor()
                            
                            # Re-resolve to get UnitOps (not just step dicts)
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
                            
                            # Create execution
                            with st.spinner("Creating execution..."):
                                execution = executor.create_execution_from_protocol(
                                    protocol_name=f"{selected_operation.title()} {selected_cell_line} in {selected_vessel}",
                                    cell_line=selected_cell_line,
                                    vessel_id=selected_vessel,
                                    operation_type=selected_operation,
                                    unit_ops=unit_ops,
                                    metadata={
                                        "created_by": "cell_line_inspector",
                                        "dry_run": dry_run,
                                        "estimated_cost": total_cost
                                    }
                                )
                            
                            # Execute
                            with st.spinner("Executing protocol..."):
                                result = executor.execute(execution.execution_id, dry_run=dry_run)
                            
                            # Show result
                            if result.status == ExecutionStatus.COMPLETED:
                                st.success(f"✅ Execution completed successfully!")
                                
                                col_res1, col_res2, col_res3 = st.columns(3)
                                with col_res1:
                                    st.metric("Execution ID", result.execution_id[:8] + "...")
                                with col_res2:
                                    duration = (result.completed_at - result.started_at).total_seconds()
                                    st.metric("Duration", f"{duration:.1f}s")
                                with col_res3:
                                    completed_steps = sum(1 for s in result.steps if s.status == StepStatus.COMPLETED)
                                    st.metric("Steps Completed", f"{completed_steps}/{len(result.steps)}")
                                
                                st.info(f"💡 View full execution details in the **⚙️ Execution Monitor** tab")
                                
                            elif result.status == ExecutionStatus.FAILED:
                                st.error(f"❌ Execution failed: {result.error_message}")
                                
                                # Show which step failed
                                for step in result.steps:
                                    if step.status == StepStatus.FAILED:
                                        st.error(f"Failed at step {step.step_index}: {step.name}")
                                        if step.error_message:
                                            st.code(step.error_message)
                        
                        except Exception as e:
                            st.error(f"Error during execution: {str(e)}")
                            import traceback
                            st.code(traceback.format_exc())
    
    # Add helpful information
    st.divider()
    st.info("""
    **How to use this inspector:**
    1. Select a cell line, vessel, and operation type
    2. Click "Resolve Protocol" to see the exact steps
    3. Review volumes, reagents, and costs
    
    **Configuration:**
    - All protocols are defined in `data/cell_lines.yaml`
    - To modify a protocol, edit the YAML file and refresh the dashboard
    - The inspector shows exactly what the automation engine will execute
    """)
