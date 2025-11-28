"""
Workflow Execution Engine

Executes protocols step-by-step, tracks progress, handles errors,
and persists execution state to the database.
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
import sqlite3
import sqlite3
import json
from cell_os.hardware.base import HardwareInterface
from cell_os.hardware.virtual import VirtualMachine


class ExecutionStatus(Enum):
    """Status of a workflow execution."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
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
            "step_id": self.step_id,
            "step_index": self.step_index,
            "name": self.name,
            "operation_type": self.operation_type,
            "parameters": self.parameters,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "error_message": self.error_message,
            "result": self.result
        }


@dataclass
class WorkflowExecution:
    """Represents a complete workflow execution."""
    execution_id: str
    workflow_name: str
    cell_line: str
    vessel_id: str
    operation_type: str  # "thaw", "passage", "feed"
    status: ExecutionStatus = ExecutionStatus.PENDING
    steps: List[ExecutionStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "execution_id": self.execution_id,
            "workflow_name": self.workflow_name,
            "cell_line": self.cell_line,
            "vessel_id": self.vessel_id,
            "operation_type": self.operation_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "steps": [step.to_dict() for step in self.steps]
        }


class ExecutionDatabase:
    """SQLite database for storing workflow executions."""
    
    def __init__(self, db_path: str = "data/executions.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
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
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                error_message TEXT,
                metadata TEXT
            )
        """)
        
        # Steps table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_steps (
                step_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                name TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                parameters TEXT NOT NULL,
                status TEXT NOT NULL,
                start_time TEXT,
                end_time TEXT,
                error_message TEXT,
                result TEXT,
                FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
            )
        """)
        
        # Create indices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_exec_status ON executions(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_exec_created ON executions(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_step_exec ON execution_steps(execution_id)")
        
        conn.commit()
        conn.close()
    
    def save_execution(self, execution: WorkflowExecution):
        """Save or update an execution."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Save execution
        cursor.execute("""
            INSERT OR REPLACE INTO executions 
            (execution_id, workflow_name, cell_line, vessel_id, operation_type, 
             status, created_at, started_at, completed_at, error_message, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            execution.execution_id,
            execution.workflow_name,
            execution.cell_line,
            execution.vessel_id,
            execution.operation_type,
            execution.status.value,
            execution.created_at.isoformat(),
            execution.started_at.isoformat() if execution.started_at else None,
            execution.completed_at.isoformat() if execution.completed_at else None,
            execution.error_message,
            json.dumps(execution.metadata)
        ))
        
        # Save steps
        for step in execution.steps:
            cursor.execute("""
                INSERT OR REPLACE INTO execution_steps
                (step_id, execution_id, step_index, name, operation_type, parameters,
                 status, start_time, end_time, error_message, result)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                step.step_id,
                execution.execution_id,
                step.step_index,
                step.name,
                step.operation_type,
                json.dumps(step.parameters),
                step.status.value,
                step.start_time.isoformat() if step.start_time else None,
                step.end_time.isoformat() if step.end_time else None,
                step.error_message,
                json.dumps(step.result) if step.result else None
            ))
        
        conn.commit()
        conn.close()
    
    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Retrieve an execution by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get execution
        cursor.execute("SELECT * FROM executions WHERE execution_id = ?", (execution_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        # Get steps
        cursor.execute(
            "SELECT * FROM execution_steps WHERE execution_id = ? ORDER BY step_index",
            (execution_id,)
        )
        step_rows = cursor.fetchall()
        
        conn.close()
        
        # Reconstruct execution
        execution = WorkflowExecution(
            execution_id=row[0],
            workflow_name=row[1],
            cell_line=row[2],
            vessel_id=row[3],
            operation_type=row[4],
            status=ExecutionStatus(row[5]),
            created_at=datetime.fromisoformat(row[6]),
            started_at=datetime.fromisoformat(row[7]) if row[7] else None,
            completed_at=datetime.fromisoformat(row[8]) if row[8] else None,
            error_message=row[9],
            metadata=json.loads(row[10]) if row[10] else {}
        )
        
        # Reconstruct steps
        for step_row in step_rows:
            step = ExecutionStep(
                step_id=step_row[0],
                step_index=step_row[2],
                name=step_row[3],
                operation_type=step_row[4],
                parameters=json.loads(step_row[5]),
                status=StepStatus(step_row[6]),
                start_time=datetime.fromisoformat(step_row[7]) if step_row[7] else None,
                end_time=datetime.fromisoformat(step_row[8]) if step_row[8] else None,
                error_message=step_row[9],
                result=json.loads(step_row[10]) if step_row[10] else None
            )
            execution.steps.append(step)
        
        return execution
    
    def list_executions(self, status: Optional[ExecutionStatus] = None, limit: int = 100) -> List[WorkflowExecution]:
        """List executions, optionally filtered by status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if status:
            cursor.execute(
                "SELECT execution_id FROM executions WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status.value, limit)
            )
        else:
            cursor.execute(
                "SELECT execution_id FROM executions ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
        
        execution_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return [self.get_execution(eid) for eid in execution_ids if self.get_execution(eid)]


class WorkflowExecutor:
    """
    Executes workflows step-by-step with progress tracking and error handling.
    """
    
    def __init__(self, db_path: str = "data/executions.db", inventory_manager=None, hardware: Optional[HardwareInterface] = None):
        self.db = ExecutionDatabase(db_path)
        self.inventory_manager = inventory_manager
        self.hardware = hardware or VirtualMachine()
        self.step_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()
        
        # Ensure hardware is connected
        try:
            self.hardware.connect()
        except Exception as e:
            print(f"Warning: Could not connect to hardware: {e}")
    
    def _register_default_handlers(self):
        """Register default step handlers."""
        self.step_handlers["dispense"] = self._handle_dispense
        self.step_handlers["aspirate"] = self._handle_aspirate
        self.step_handlers["incubate"] = self._handle_incubate
        self.step_handlers["centrifuge"] = self._handle_centrifuge
        self.step_handlers["count"] = self._handle_count
        self.step_handlers["mix"] = self._handle_mix
    
    def _handle_dispense(self, step: ExecutionStep) -> Dict[str, Any]:
        """Handle dispense operation."""
        vol_ml = step.parameters.get("volume_ml", 0.0)
        vol_ul = vol_ml * 1000.0
        loc = step.parameters.get("location", "unknown")
        return self.hardware.dispense(vol_ul, loc)
    
    def _handle_aspirate(self, step: ExecutionStep) -> Dict[str, Any]:
        """Handle aspirate operation."""
        vol_ml = step.parameters.get("volume_ml", 0.0)
        vol_ul = vol_ml * 1000.0
        loc = step.parameters.get("location", "unknown")
        return self.hardware.aspirate(vol_ul, loc)
    
    def _handle_mix(self, step: ExecutionStep) -> Dict[str, Any]:
        """Handle mix operation."""
        vol_ml = step.parameters.get("volume_ml", 0.0)
        vol_ul = vol_ml * 1000.0
        reps = step.parameters.get("repetitions", 3)
        loc = step.parameters.get("location", "unknown")
        return self.hardware.mix(vol_ul, reps, loc)
    
    def _handle_incubate(self, step: ExecutionStep) -> Dict[str, Any]:
        """Handle incubation operation."""
        minutes = step.parameters.get("minutes", 0)
        seconds = minutes * 60.0
        temp = step.parameters.get("temperature_c", 37.0)
        return self.hardware.incubate(seconds, temp)
    
    def _handle_centrifuge(self, step: ExecutionStep) -> Dict[str, Any]:
        """Handle centrifuge operation."""
        minutes = step.parameters.get("minutes", 0)
        seconds = minutes * 60.0
        g = step.parameters.get("g_force", 300.0)
        return self.hardware.centrifuge(seconds, g)
    
    def _handle_count(self, step: ExecutionStep) -> Dict[str, Any]:
        """Handle cell counting operation."""
        loc = step.parameters.get("location", "sample")
        return self.hardware.count_cells(loc)
    
    def register_handler(self, operation_type: str, handler: Callable):
        """Register a custom step handler."""
        self.step_handlers[operation_type] = handler
    
    def create_execution_from_protocol(
        self,
        protocol_name: str,
        cell_line: str,
        vessel_id: str,
        operation_type: str,
        unit_ops: List[Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> WorkflowExecution:
        """
        Create an execution from a list of UnitOps.
        
        Args:
            protocol_name: Name of the protocol
            cell_line: Cell line being processed
            vessel_id: Vessel identifier
            operation_type: Type of operation (thaw, passage, feed)
            unit_ops: List of UnitOp objects
            metadata: Additional metadata
            
        Returns:
            WorkflowExecution ready to be executed
        """
        execution_id = str(uuid.uuid4())
        
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_name=protocol_name,
            cell_line=cell_line,
            vessel_id=vessel_id,
            operation_type=operation_type,
            metadata=metadata or {}
        )
        
        # Convert UnitOps to ExecutionSteps
        for idx, uo in enumerate(unit_ops):
            # Handle composite ops with sub_steps
            if hasattr(uo, 'sub_steps') and uo.sub_steps:
                for sub_idx, sub_uo in enumerate(uo.sub_steps):
                    step = self._unitop_to_step(sub_uo, f"{idx}.{sub_idx}")
                    execution.steps.append(step)
            else:
                step = self._unitop_to_step(uo, str(idx))
                execution.steps.append(step)
        
        # Save to database
        self.db.save_execution(execution)
        
        return execution
    
    def _unitop_to_step(self, unit_op: Any, index: str) -> ExecutionStep:
        """Convert a UnitOp to an ExecutionStep."""
        # Extract operation type from UnitOp ID
        uo_id = getattr(unit_op, 'uo_id', 'unknown')
        
        # Try to extract operation type from uo_id
        # Format is usually "operation_###" or just "operation"
        if '_' in uo_id:
            op_type = uo_id.split('_')[0].lower()
        else:
            op_type = uo_id.lower()
        
        # Extract parameters from name
        parameters = {
            "name": unit_op.name if hasattr(unit_op, 'name') else "Unknown",
            "instrument": getattr(unit_op, 'instrument', None),
            "material_cost": getattr(unit_op, 'material_cost_usd', 0.0),
            "instrument_cost": getattr(unit_op, 'instrument_cost_usd', 0.0),
            "required_resources": []
        }
        
        # Extract required resources from BOM items
        if hasattr(unit_op, 'items') and unit_op.items:
            for item in unit_op.items:
                parameters["required_resources"].append({
                    "resource_id": item.resource_id,
                    "quantity": item.quantity
                })
        
        return ExecutionStep(
            step_id=str(uuid.uuid4()),
            step_index=int(index.split('.')[0]) if '.' not in index else int(index.split('.')[1]),
            name=unit_op.name if hasattr(unit_op, 'name') else f"Step {index}",
            operation_type=op_type,
            parameters=parameters
        )
    
    def execute(self, execution_id: str, dry_run: bool = False) -> WorkflowExecution:
        """
        Execute a workflow.
        
        Args:
            execution_id: ID of the execution to run
            dry_run: If True, simulate without actually executing
            
        Returns:
            Updated WorkflowExecution
        """
        execution = self.db.get_execution(execution_id)
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")
        
        # Update status
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.now()
        self.db.save_execution(execution)
        
        try:
            # Execute each step
            for step in execution.steps:
                step.status = StepStatus.RUNNING
                step.start_time = datetime.now()
                self.db.save_execution(execution)
                
                try:
                    # Get handler for this operation type
                    handler = self.step_handlers.get(step.operation_type, self._handle_generic)
                    
                    if not dry_run:
                        result = handler(step)
                        step.result = result
                        
                        # Deduct resources if inventory manager is available
                        if self.inventory_manager:
                            self._deduct_resources(step, execution_id)
                    else:
                        step.result = {"dry_run": True}
                    
                    step.status = StepStatus.COMPLETED
                    step.end_time = datetime.now()
                    
                except Exception as e:
                    step.status = StepStatus.FAILED
                    step.error_message = str(e)
                    step.end_time = datetime.now()
                    raise
                
                finally:
                    self.db.save_execution(execution)
            
            # Mark execution as completed
            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = datetime.now()
            
        except Exception as e:
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.now()
        
        finally:
            self.db.save_execution(execution)
        
        return execution
    
    def _deduct_resources(self, step: ExecutionStep, execution_id: str):
        """Deduct resources required for the step."""
        required = step.parameters.get("required_resources", [])
        for item in required:
            try:
                self.inventory_manager.consume_stock(
                    resource_id=item["resource_id"],
                    quantity=item["quantity"],
                    transaction_meta={"execution_id": execution_id, "step_id": step.step_id}
                )
            except Exception as e:
                # Log warning but don't fail execution? Or fail?
                # For now, let's log it in the step result
                if step.result:
                    step.result["inventory_warning"] = str(e)
                else:
                    step.result = {"inventory_warning": str(e)}

    def _handle_generic(self, step: ExecutionStep) -> Dict[str, Any]:
        """Generic handler for unknown operation types."""
        return {"status": "success", "message": f"Executed {step.operation_type}"}
    
    def get_execution_status(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get current status of an execution."""
        return self.db.get_execution(execution_id)
    
    def list_executions(self, status: Optional[ExecutionStatus] = None) -> List[WorkflowExecution]:
        """List all executions, optionally filtered by status."""
        return self.db.list_executions(status)
