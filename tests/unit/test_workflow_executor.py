"""
Tests for Workflow Execution Engine
"""

import pytest
import tempfile
import os
from datetime import datetime
from cell_os.workflow_executor import (
    WorkflowExecutor,
    WorkflowExecution,
    ExecutionStep,
    ExecutionStatus,
    StepStatus,
    ExecutionPersistence,
    ExecutionRepository,
)
from cell_os.unit_ops.base import UnitOp


class TestExecutionPersistence:
    """Test the execution persistence layer."""
    
    def setup_method(self):
        """Create a temporary database for each test."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db = ExecutionPersistence(self.temp_db.name)
    
    def teardown_method(self):
        """Clean up temporary database."""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_save_and_retrieve_execution(self):
        """Test saving and retrieving an execution."""
        execution = WorkflowExecution(
            execution_id="test-001",
            workflow_name="Test Thaw",
            cell_line="iPSC",
            vessel_id="flask_t75",
            operation_type="thaw"
        )
        
        step = ExecutionStep(
            step_id="step-001",
            step_index=0,
            name="Dispense Media",
            operation_type="dispense",
            parameters={"volume_ml": 15.0}
        )
        execution.steps.append(step)
        
        # Save
        self.db.save_execution(execution)
        
        # Retrieve
        retrieved = self.db.get_execution("test-001")
        
        assert retrieved is not None
        assert retrieved.execution_id == "test-001"
        assert retrieved.workflow_name == "Test Thaw"
        assert retrieved.cell_line == "iPSC"
        assert len(retrieved.steps) == 1
        assert retrieved.steps[0].name == "Dispense Media"
    
    def test_list_executions_by_status(self):
        """Test listing executions filtered by status."""
        # Create multiple executions
        for i in range(3):
            execution = WorkflowExecution(
                execution_id=f"test-{i:03d}",
                workflow_name=f"Test {i}",
                cell_line="HEK293",
                vessel_id="flask_t75",
                operation_type="feed",
                status=ExecutionStatus.COMPLETED if i % 2 == 0 else ExecutionStatus.RUNNING
            )
            self.db.save_execution(execution)
        
        # List all
        all_execs = self.db.list_executions()
        assert len(all_execs) == 3
        
        # List completed only
        completed = self.db.list_executions(status=ExecutionStatus.COMPLETED)
        assert len(completed) == 2
        
        # List running only
        running = self.db.list_executions(status=ExecutionStatus.RUNNING)
        assert len(running) == 1


class TestExecutionRepository:
    """Test repository caching and listing."""

    def setup_method(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        persistence = ExecutionPersistence(self.temp_db.name)
        self.repo = ExecutionRepository(persistence)

    def teardown_method(self):
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_repository_caches_executions(self):
        execution = WorkflowExecution(
            execution_id="repo-001",
            workflow_name="Repo Test",
            cell_line="U2OS",
            vessel_id="flask_t25",
            operation_type="feed",
        )
        self.repo.save(execution)

        fetched = self.repo.get("repo-001")
        assert fetched is not None
        assert fetched.workflow_name == "Repo Test"

        # delete db file to ensure cache serves subsequent read
        os.unlink(self.temp_db.name)
        cached = self.repo.get("repo-001")
        assert cached is fetched

    def test_repository_list_filters_by_status(self):
        for idx in range(3):
            execution = WorkflowExecution(
                execution_id=f"repo-{idx}",
                workflow_name=f"Workflow {idx}",
                cell_line="Test",
                vessel_id="flask_t175",
                operation_type="thaw",
                status=ExecutionStatus.COMPLETED if idx < 2 else ExecutionStatus.RUNNING,
            )
            self.repo.save(execution)

        completed = self.repo.list(status=ExecutionStatus.COMPLETED)
        assert len(completed) >= 2


class TestWorkflowExecutor:
    """Test the workflow executor."""
    
    def setup_method(self):
        """Create a temporary database and executor for each test."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.executor = WorkflowExecutor(self.temp_db.name)
    
    def teardown_method(self):
        """Clean up temporary database."""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_create_execution_from_unitops(self):
        """Test creating an execution from UnitOps."""
        # Create some mock UnitOps
        unit_ops = [
            UnitOp(
                uo_id="dispense_001",
                name="Dispense 15.0 mL mTeSR",
                instrument="Pipette"
            ),
            UnitOp(
                uo_id="incubate_001",
                name="Incubate 60 minutes",
                instrument="Incubator"
            )
        ]
        
        execution = self.executor.create_execution_from_protocol(
            protocol_name="iPSC Thaw",
            cell_line="iPSC",
            vessel_id="flask_t75",
            operation_type="thaw",
            unit_ops=unit_ops
        )
        
        assert execution is not None
        assert execution.workflow_name == "iPSC Thaw"
        assert execution.cell_line == "iPSC"
        assert len(execution.steps) == 2
        assert execution.status == ExecutionStatus.PENDING
    
    def test_execute_workflow_dry_run(self):
        """Test executing a workflow in dry-run mode."""
        # Create execution
        unit_ops = [
            UnitOp(uo_id="dispense_001", name="Dispense Media"),
            UnitOp(uo_id="aspirate_001", name="Aspirate Media")
        ]
        
        execution = self.executor.create_execution_from_protocol(
            protocol_name="Test Protocol",
            cell_line="HEK293",
            vessel_id="flask_t75",
            operation_type="feed",
            unit_ops=unit_ops
        )
        
        # Execute in dry-run mode
        result = self.executor.execute(execution.execution_id, dry_run=True)
        
        assert result.status == ExecutionStatus.COMPLETED
        assert all(step.status == StepStatus.COMPLETED for step in result.steps)
        assert all(step.result.get("dry_run") for step in result.steps)
    
    def test_execute_workflow_real(self):
        """Test executing a workflow with real handlers."""
        # Create execution
        unit_ops = [
            UnitOp(uo_id="dispense_001", name="Dispense 10 mL Media"),
            UnitOp(uo_id="incubate_001", name="Incubate 5 minutes")
        ]
        
        execution = self.executor.create_execution_from_protocol(
            protocol_name="Feed Protocol",
            cell_line="A549",
            vessel_id="flask_t75",
            operation_type="feed",
            unit_ops=unit_ops
        )
        
        # Execute
        result = self.executor.execute(execution.execution_id, dry_run=False)
        
        assert result.status == ExecutionStatus.COMPLETED
        assert result.started_at is not None
        assert result.completed_at is not None
        assert all(step.status == StepStatus.COMPLETED for step in result.steps)
        assert all(step.start_time is not None for step in result.steps)
        assert all(step.end_time is not None for step in result.steps)
    
    def test_execution_with_composite_unitop(self):
        """Test execution with composite UnitOps that have sub_steps."""
        # Create a composite UnitOp
        sub_steps = [
            UnitOp(uo_id="dispense_001", name="Dispense Coating"),
            UnitOp(uo_id="incubate_001", name="Incubate Coating"),
            UnitOp(uo_id="aspirate_001", name="Aspirate Coating")
        ]
        
        composite_op = UnitOp(
            uo_id="coat_vessel",
            name="Coat Vessel",
            sub_steps=sub_steps
        )
        
        execution = self.executor.create_execution_from_protocol(
            protocol_name="Thaw with Coating",
            cell_line="iPSC",
            vessel_id="flask_t75",
            operation_type="thaw",
            unit_ops=[composite_op]
        )
        
        # Should expand sub_steps
        assert len(execution.steps) == 3
        assert execution.steps[0].name == "Dispense Coating"
        assert execution.steps[1].name == "Incubate Coating"
        assert execution.steps[2].name == "Aspirate Coating"
    
    def test_custom_step_handler(self):
        """Test registering and using a custom step handler."""
        call_count = [0]
        
        def custom_handler(step):
            call_count[0] += 1
            return {"custom": True, "step_name": step.name}
        
        # Register custom handler (note: handler key should match extracted op_type)
        self.executor.register_handler("custom", custom_handler)
        
        # Create execution with custom operation (uo_id will be split to get "custom")
        unit_ops = [UnitOp(uo_id="custom_001", name="Custom Operation")]
        
        execution = self.executor.create_execution_from_protocol(
            protocol_name="Custom Protocol",
            cell_line="Test",
            vessel_id="test_vessel",
            operation_type="test",
            unit_ops=unit_ops
        )
        
        # Execute
        result = self.executor.execute(execution.execution_id)
        
        assert call_count[0] == 1
        assert result.steps[0].result["custom"] is True
    
    def test_execution_error_handling(self):
        """Test that execution errors are properly captured."""
        def failing_handler(step):
            raise ValueError("Simulated failure")
        
        self.executor.register_handler("failing", failing_handler)
        
        unit_ops = [UnitOp(uo_id="failing_001", name="Failing Operation")]
        
        execution = self.executor.create_execution_from_protocol(
            protocol_name="Failing Protocol",
            cell_line="Test",
            vessel_id="test_vessel",
            operation_type="test",
            unit_ops=unit_ops
        )
        
        # Execute
        result = self.executor.execute(execution.execution_id)
        
        assert result.status == ExecutionStatus.FAILED
        assert result.error_message is not None
        assert "Simulated failure" in result.error_message
        assert result.steps[0].status == StepStatus.FAILED
    
    def test_get_execution_status(self):
        """Test retrieving execution status."""
        unit_ops = [UnitOp(uo_id="test_001", name="Test Step")]
        
        execution = self.executor.create_execution_from_protocol(
            protocol_name="Status Test",
            cell_line="Test",
            vessel_id="test_vessel",
            operation_type="test",
            unit_ops=unit_ops
        )
        
        # Before execution
        status = self.executor.get_execution_status(execution.execution_id)
        assert status.status == ExecutionStatus.PENDING
        
        # After execution
        self.executor.execute(execution.execution_id)
        status = self.executor.get_execution_status(execution.execution_id)
        assert status.status == ExecutionStatus.COMPLETED
    
    def test_list_executions(self):
        """Test listing executions."""
        # Create multiple executions
        for i in range(5):
            unit_ops = [UnitOp(uo_id=f"test_{i}", name=f"Step {i}")]
            self.executor.create_execution_from_protocol(
                protocol_name=f"Protocol {i}",
                cell_line="Test",
                vessel_id="test_vessel",
                operation_type="test",
                unit_ops=unit_ops
            )
        
        # List all
        all_execs = self.executor.list_executions()
        assert len(all_execs) == 5
        
        # Execute one
        all_execs[0] = self.executor.execute(all_execs[0].execution_id)
        
        # List completed
        completed = self.executor.list_executions(status=ExecutionStatus.COMPLETED)
        assert len(completed) == 1
        
        # List pending
        pending = self.executor.list_executions(status=ExecutionStatus.PENDING)
        assert len(pending) == 4
