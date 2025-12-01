"""
Test workflow execution system.
"""
import uuid
from cell_os.workflow_execution import (
    WorkflowExecutor,
    WorkflowExecution,
    ExecutionStep,
    ExecutionStatus,
    StepStatus,
    ExecutionRepository,
    ExecutionQueue
)


def test_execution_repository(tmp_path):
    """Test execution repository CRUD operations."""
    db_path = str(tmp_path / "test_executions.db")
    repo = ExecutionRepository(db_path)
    
    # Create execution
    execution = WorkflowExecution(
        execution_id="test_exec_1",
        workflow_name="Test Workflow",
        cell_line="HEK293T",
        vessel_id="flask_001",
        operation_type="passage"
    )
    
    # Add steps
    step = ExecutionStep(
        step_id="step_1",
        step_index=0,
        name="Aspirate media",
        operation_type="aspirate",
        parameters={"volume_ml": 5.0}
    )
    execution.steps.append(step)
    
    # Save
    repo.save(execution)
    
    # Retrieve
    retrieved = repo.get("test_exec_1")
    assert retrieved is not None
    assert retrieved.workflow_name == "Test Workflow"
    assert len(retrieved.steps) == 1
    assert retrieved.steps[0].name == "Aspirate media"


def test_execution_queue():
    """Test execution queue operations."""
    queue = ExecutionQueue()
    
    # Submit executions
    queue.submit("exec_1")
    queue.submit("exec_2")
    queue.submit("exec_3")
    
    assert queue.size() == 3
    assert not queue.is_empty()
    
    # Check pending
    pending = queue.pending()
    assert len(pending) == 3
    assert "exec_1" in pending


def test_workflow_executor_creation(tmp_path):
    """Test creating a workflow execution."""
    db_path = str(tmp_path / "test_executions.db")
    executor = WorkflowExecutor(db_path=db_path)
    
    # Create a mock UnitOp
    class MockUnitOp:
        def __init__(self, name, uo_id):
            self.name = name
            self.uo_id = uo_id
            self.sub_steps = []
            self.material_cost_usd = 1.0
            self.instrument_cost_usd = 0.5
    
    unit_ops = [
        MockUnitOp("Aspirate 5mL", "aspirate_001"),
        MockUnitOp("Dispense 10mL", "dispense_002"),
    ]
    
    execution = executor.create_execution_from_protocol(
        protocol_name="Test Protocol",
        cell_line="CHO-K1",
        vessel_id="plate_001",
        operation_type="feed",
        unit_ops=unit_ops
    )
    
    assert execution is not None
    assert execution.workflow_name == "Test Protocol"
    assert execution.cell_line == "CHO-K1"
    assert len(execution.steps) == 2
    assert execution.steps[0].operation_type == "aspirate"
    assert execution.steps[1].operation_type == "dispense"


def test_workflow_executor_dry_run(tmp_path):
    """Test dry run execution."""
    db_path = str(tmp_path / "test_executions.db")
    executor = WorkflowExecutor(db_path=db_path)
    
    # Create execution
    execution = WorkflowExecution(
        execution_id=str(uuid.uuid4()),
        workflow_name="Dry Run Test",
        cell_line="HeLa",
        vessel_id="well_A1",
        operation_type="test"
    )
    
    step = ExecutionStep(
        step_id=str(uuid.uuid4()),
        step_index=0,
        name="Test Step",
        operation_type="generic",
        parameters={}
    )
    execution.steps.append(step)
    
    executor.repo.save(execution)
    
    # Execute in dry run mode
    result = executor.execute(execution.execution_id, dry_run=True)
    
    assert result.status == ExecutionStatus.COMPLETED
    assert result.steps[0].status == StepStatus.COMPLETED
    assert result.steps[0].result == {"dry_run": True}


def test_execution_list_by_status(tmp_path):
    """Test listing executions by status."""
    db_path = str(tmp_path / "test_executions.db")
    repo = ExecutionRepository(db_path)
    
    # Create multiple executions with different statuses
    for i, status in enumerate([ExecutionStatus.PENDING, ExecutionStatus.RUNNING, ExecutionStatus.COMPLETED]):
        execution = WorkflowExecution(
            execution_id=f"exec_{i}",
            workflow_name=f"Workflow {i}",
            cell_line="HEK293T",
            vessel_id="flask_001",
            operation_type="passage",
            status=status
        )
        repo.save(execution)
    
    # List completed executions
    completed = repo.list(status=ExecutionStatus.COMPLETED)
    assert len(completed) == 1
    assert completed[0].status == ExecutionStatus.COMPLETED
    
    # List all executions
    all_execs = repo.list()
    assert len(all_execs) == 3


def test_backward_compatibility():
    """Test that old imports still work."""
    # This should not raise an error
    from cell_os.workflow_executor import WorkflowExecutor as OldExecutor
    from cell_os.workflow_execution import WorkflowExecutor as NewExecutor
    
    # They should be the same class
    assert OldExecutor is NewExecutor


def test_execution_step_to_dict():
    """Test ExecutionStep serialization."""
    step = ExecutionStep(
        step_id="step_123",
        step_index=0,
        name="Test Step",
        operation_type="aspirate",
        parameters={"volume_ml": 5.0},
        status=StepStatus.COMPLETED
    )
    
    step_dict = step.to_dict()
    assert step_dict['step_id'] == "step_123"
    assert step_dict['name'] == "Test Step"
    assert step_dict['status'] == "completed"
    assert step_dict['parameters'] == {"volume_ml": 5.0}


def test_workflow_execution_to_dict():
    """Test WorkflowExecution serialization."""
    execution = WorkflowExecution(
        execution_id="exec_456",
        workflow_name="Test Workflow",
        cell_line="CHO",
        vessel_id="plate_001",
        operation_type="passage",
        status=ExecutionStatus.RUNNING
    )
    
    exec_dict = execution.to_dict()
    assert exec_dict['execution_id'] == "exec_456"
    assert exec_dict['workflow_name'] == "Test Workflow"
    assert exec_dict['status'] == "running"
    assert exec_dict['steps'] == []
