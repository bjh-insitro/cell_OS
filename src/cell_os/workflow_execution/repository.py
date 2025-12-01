"""
Persistence layer for workflow executions using repository pattern.
"""
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from ..database.base import BaseRepository
from .models import WorkflowExecution, ExecutionStep, ExecutionStatus, StepStatus


class ExecutionRepository(BaseRepository):
    """Repository for workflow execution persistence."""
    
    def __init__(self, db_path_or_persistence=None):
        """
        Initialize repository.
        
        Args:
            db_path_or_persistence: Either a string path to database file,
                                   or an ExecutionRepository instance (for backward compatibility)
        """
        # Handle backward compatibility: if passed another ExecutionRepository, use its db_path
        if isinstance(db_path_or_persistence, ExecutionRepository):
            db_path = db_path_or_persistence.db_path
        elif db_path_or_persistence is None:
            db_path = "data/executions.db"
        else:
            db_path = db_path_or_persistence
        
        super().__init__(db_path)
        # In-memory cache for backward compatibility
        self._memory: Dict[str, WorkflowExecution] = {}
    
    def _init_schema(self):
        """Initialize database schema."""
        conn = self._get_raw_connection()
        try:
            cursor = conn.cursor()
            
            # Executions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS executions (
                    execution_id TEXT PRIMARY KEY,
                    workflow_name TEXT NOT NULL,
                    cell_line TEXT NOT NULL,
                    vessel_id TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_step_index INTEGER DEFAULT 0,
                    started_at TEXT,
                    completed_at TEXT,
                    error_message TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Steps table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS execution_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    parameters TEXT NOT NULL,
                    status TEXT NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    error_message TEXT,
                    result TEXT,
                    FOREIGN KEY (execution_id) REFERENCES executions(execution_id),
                    UNIQUE(execution_id, step_index)
                )
            """)
            
            # Create indices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_exec_status ON executions(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_exec_workflow ON executions(workflow_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_step_exec ON execution_steps(execution_id)")
            
            conn.commit()
        finally:
            conn.close()
    
    def save(self, execution: WorkflowExecution):
        """Save or update an execution."""
        # Cache in memory
        self._memory[execution.execution_id] = execution
        
        # Save execution
        exec_data = {
            'execution_id': execution.execution_id,
            'workflow_name': execution.workflow_name,
            'cell_line': execution.cell_line,
            'vessel_id': execution.vessel_id,
            'operation_type': execution.operation_type,
            'status': execution.status.value if isinstance(execution.status, ExecutionStatus) else execution.status,
            'current_step_index': execution.current_step_index,
            'started_at': execution.started_at.isoformat() if execution.started_at else None,
            'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
            'error_message': execution.error_message,
            'metadata': json.dumps(execution.metadata) if execution.metadata else None,
            'updated_at': datetime.now().isoformat()
        }
        
        # Check if exists
        existing = self._fetch_one(
            "SELECT execution_id FROM executions WHERE execution_id = ?",
            (execution.execution_id,)
        )
        
        if existing:
            self._update('executions', exec_data, "execution_id = ?", (execution.execution_id,))
        else:
            self._insert('executions', exec_data)
        
        # Save steps
        for step in execution.steps:
            step_data = {
                'execution_id': execution.execution_id,
                'step_id': step.step_id,
                'step_index': step.step_index,
                'name': step.name,
                'operation_type': step.operation_type,
                'parameters': json.dumps(step.parameters),
                'status': step.status.value if isinstance(step.status, StepStatus) else step.status,
                'start_time': step.start_time.isoformat() if step.start_time else None,
                'end_time': step.end_time.isoformat() if step.end_time else None,
                'error_message': step.error_message,
                'result': json.dumps(step.result) if step.result else None
            }
            
            # Check if step exists
            existing_step = self._fetch_one(
                "SELECT id FROM execution_steps WHERE execution_id = ? AND step_index = ?",
                (execution.execution_id, step.step_index)
            )
            
            if existing_step:
                self._update(
                    'execution_steps',
                    step_data,
                    "execution_id = ? AND step_index = ?",
                    (execution.execution_id, step.step_index)
                )
            else:
                self._insert('execution_steps', step_data)
    
    def get(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Retrieve an execution by ID."""
        # Check cache first
        if execution_id in self._memory:
            return self._memory[execution_id]
        
        row = self._fetch_one(
            "SELECT * FROM executions WHERE execution_id = ?",
            (execution_id,)
        )
        
        if not row:
            return None
        
        # Parse metadata
        metadata = json.loads(row['metadata']) if row.get('metadata') else {}
        
        # Get steps
        step_rows = self._fetch_all(
            "SELECT * FROM execution_steps WHERE execution_id = ? ORDER BY step_index",
            (execution_id,)
        )
        
        steps = []
        for step_row in step_rows:
            step = ExecutionStep(
                step_id=step_row['step_id'],
                step_index=step_row['step_index'],
                name=step_row['name'],
                operation_type=step_row['operation_type'],
                parameters=json.loads(step_row['parameters']),
                status=StepStatus(step_row['status']),
                start_time=datetime.fromisoformat(step_row['start_time']) if step_row.get('start_time') else None,
                end_time=datetime.fromisoformat(step_row['end_time']) if step_row.get('end_time') else None,
                error_message=step_row.get('error_message'),
                result=json.loads(step_row['result']) if step_row.get('result') else None
            )
            steps.append(step)
        
        # Create execution
        execution = WorkflowExecution(
            execution_id=row['execution_id'],
            workflow_name=row['workflow_name'],
            cell_line=row['cell_line'],
            vessel_id=row['vessel_id'],
            operation_type=row['operation_type'],
            status=ExecutionStatus(row['status']),
            steps=steps,
            current_step_index=row['current_step_index'],
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else None,
            started_at=datetime.fromisoformat(row['started_at']) if row.get('started_at') else None,
            completed_at=datetime.fromisoformat(row['completed_at']) if row.get('completed_at') else None,
            error_message=row.get('error_message'),
            metadata=metadata
        )
        
        # Cache before returning
        self._memory[execution.execution_id] = execution
        
        return execution
    
    def list(self, status: Optional[ExecutionStatus] = None, limit: int = 100) -> List[WorkflowExecution]:
        """List executions, optionally filtered by status."""
        if status:
            status_value = status.value if isinstance(status, ExecutionStatus) else status
            rows = self._fetch_all(
                "SELECT * FROM executions WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status_value, limit)
            )
        else:
            rows = self._fetch_all(
                "SELECT * FROM executions ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
        
        executions = []
        for row in rows:
            # For list, we don't load steps to improve performance
            metadata = json.loads(row['metadata']) if row.get('metadata') else {}
            execution = WorkflowExecution(
                execution_id=row['execution_id'],
                workflow_name=row['workflow_name'],
                cell_line=row['cell_line'],
                vessel_id=row['vessel_id'],
                operation_type=row['operation_type'],
                status=ExecutionStatus(row['status']),
                steps=[],  # Empty for list view
                current_step_index=row['current_step_index'],
                created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else None,
                started_at=datetime.fromisoformat(row['started_at']) if row.get('started_at') else None,
                completed_at=datetime.fromisoformat(row['completed_at']) if row.get('completed_at') else None,
                error_message=row.get('error_message'),
                metadata=metadata
            )
            executions.append(execution)
        
        return executions
    
    # Backward compatibility methods (old API)
    def save_execution(self, execution: WorkflowExecution):
        """Backward compatibility: alias for save()."""
        return self.save(execution)
    
    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Backward compatibility: alias for get()."""
        return self.get(execution_id)
    
    def list_executions(self, status: Optional[ExecutionStatus] = None, limit: int = 100) -> List[WorkflowExecution]:
        """Backward compatibility: alias for list()."""
        return self.list(status, limit)
