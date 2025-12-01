"""
Workflow execution package.

This package provides a modular workflow execution system with:
- Models: Data structures for executions and steps
- Repository: Persistence layer using repository pattern
- Queue: Execution queue management
- Executor: Core execution logic

Example usage:
    from cell_os.workflow_execution import WorkflowExecutor
    
    executor = WorkflowExecutor()
    execution = executor.create_execution_from_protocol(...)
    result = executor.execute(execution.execution_id)
"""
from .models import (
    ExecutionStatus,
    StepStatus,
    ExecutionStep,
    WorkflowExecution
)
from .repository import ExecutionRepository
from .queue import ExecutionQueue
from .executor import WorkflowRunner, WorkflowExecutor

__all__ = [
    'ExecutionStatus',
    'StepStatus',
    'ExecutionStep',
    'WorkflowExecution',
    'ExecutionRepository',
    'ExecutionQueue',
    'WorkflowRunner',
    'WorkflowExecutor',
]
