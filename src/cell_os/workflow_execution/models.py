"""
Data models for workflow execution.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum


class ExecutionStatus(str, Enum):
    """Status of a workflow execution."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    """Status of an individual step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExecutionStep:
    """Represents a single step in a workflow execution."""
    step_id: str
    step_index: int
    name: str
    operation_type: str
    parameters: Dict[str, Any]
    status: StepStatus = StepStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'step_id': self.step_id,
            'step_index': self.step_index,
            'name': self.name,
            'operation_type': self.operation_type,
            'parameters': self.parameters,
            'status': self.status.value if isinstance(self.status, StepStatus) else self.status,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'error_message': self.error_message,
            'result': self.result
        }


@dataclass
class WorkflowExecution:
    """Represents a complete workflow execution."""
    execution_id: str
    workflow_name: str
    cell_line: str
    vessel_id: str
    operation_type: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    steps: List[ExecutionStep] = field(default_factory=list)
    current_step_index: int = 0
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'execution_id': self.execution_id,
            'workflow_name': self.workflow_name,
            'cell_line': self.cell_line,
            'vessel_id': self.vessel_id,
            'operation_type': self.operation_type,
            'status': self.status.value if isinstance(self.status, ExecutionStatus) else self.status,
            'steps': [step.to_dict() for step in self.steps],
            'current_step_index': self.current_step_index,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'metadata': self.metadata
        }
