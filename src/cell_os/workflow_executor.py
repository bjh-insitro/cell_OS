"""
Workflow Execution Engine

DEPRECATED: This module has been refactored into the workflow_execution package.
This file remains for backward compatibility.

New code should use:
    from cell_os.workflow_execution import WorkflowExecutor

Instead of:
    from cell_os.workflow_executor import WorkflowExecutor
"""

# Import everything from the new package for backward compatibility
from cell_os.workflow_execution import (
    ExecutionStatus,
    StepStatus,
    ExecutionStep,
    WorkflowExecution,
    ExecutionRepository,
    ExecutionQueue,
    WorkflowRunner,
    WorkflowExecutor
)

# For backward compatibility: ExecutionPersistence is now ExecutionRepository
# Old code may use ExecutionPersistence, so we create an alias
ExecutionPersistence = ExecutionRepository

# For backward compatibility with old imports
__all__ = [
    'ExecutionStatus',
    'StepStatus',
    'ExecutionStep',
    'WorkflowExecution',
    'ExecutionPersistence',  # Alias for ExecutionRepository
    'ExecutionRepository',
    'ExecutionQueue',
    'WorkflowRunner',
    'WorkflowExecutor',
]
