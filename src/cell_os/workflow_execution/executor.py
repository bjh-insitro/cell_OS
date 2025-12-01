"""
Core workflow execution logic.
"""
import uuid
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from cell_os.hardware.base import HardwareInterface
from cell_os.hardware.virtual import VirtualMachine
from .models import WorkflowExecution, ExecutionStep, ExecutionStatus, StepStatus
from .repository import ExecutionRepository
from .queue import ExecutionQueue


class WorkflowRunner:
    """Runs workflow executions step-by-step using registered handlers."""

    def __init__(
        self,
        repo: ExecutionRepository,
        hardware: Optional[HardwareInterface] = None,
        inventory_manager=None,
    ):
        self.repo = repo
        self.inventory_manager = inventory_manager
        self.hardware = hardware or VirtualMachine()
        self.step_handlers: Dict[str, Callable[[ExecutionStep], Dict[str, Any]]] = {}
        self._register_default_handlers()
        self._connect_hardware()

    def _connect_hardware(self):
        try:
            self.hardware.connect()
        except Exception as exc:
            print(f"Warning: Could not connect to hardware: {exc}")

    def register_handler(self, operation_type: str, handler: Callable[[ExecutionStep], Dict[str, Any]]):
        """Register a custom step handler."""
        self.step_handlers[operation_type] = handler

    def run(self, execution: WorkflowExecution, dry_run: bool = False) -> WorkflowExecution:
        """Execute a workflow step-by-step."""
        if not execution:
            raise ValueError("Execution not found")

        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.now()
        self.repo.save(execution)

        try:
            for step in execution.steps:
                step.status = StepStatus.RUNNING
                step.start_time = datetime.now()
                self.repo.save(execution)

                try:
                    handler = self.step_handlers.get(step.operation_type, self._handle_generic)
                    if dry_run:
                        step.result = {"dry_run": True}
                    else:
                        step.result = handler(step)
                        if self.inventory_manager:
                            self._deduct_resources(step, execution.execution_id)
                    step.status = StepStatus.COMPLETED
                    step.end_time = datetime.now()
                except Exception as exc:
                    step.status = StepStatus.FAILED
                    step.error_message = str(exc)
                    step.end_time = datetime.now()
                    raise
                finally:
                    self.repo.save(execution)

            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = datetime.now()
        except Exception as exc:
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(exc)
            execution.completed_at = datetime.now()
        finally:
            self.repo.save(execution)

        return execution

    def _deduct_resources(self, step: ExecutionStep, execution_id: str):
        """Deduct resources from inventory."""
        required = step.parameters.get("required_resources", [])
        for item in required:
            try:
                self.inventory_manager.consume_stock(
                    resource_id=item["resource_id"],
                    quantity=item["quantity"],
                    transaction_meta={"execution_id": execution_id, "step_id": step.step_id},
                )
            except Exception as exc:
                step.result = step.result or {}
                step.result["inventory_warning"] = str(exc)

    def _register_default_handlers(self):
        """Register default handlers for common operations."""
        self.step_handlers["dispense"] = self._handle_dispense
        self.step_handlers["aspirate"] = self._handle_aspirate
        self.step_handlers["incubate"] = self._handle_incubate
        self.step_handlers["centrifuge"] = self._handle_centrifuge
        self.step_handlers["count"] = self._handle_count
        self.step_handlers["mix"] = self._handle_mix

    def _handle_dispense(self, step: ExecutionStep) -> Dict[str, Any]:
        vol_ml = step.parameters.get("volume_ml", 0.0)
        vol_ul = vol_ml * 1000.0
        loc = step.parameters.get("location", "unknown")
        return self.hardware.dispense(vol_ul, loc)

    def _handle_aspirate(self, step: ExecutionStep) -> Dict[str, Any]:
        vol_ml = step.parameters.get("volume_ml", 0.0)
        vol_ul = vol_ml * 1000.0
        loc = step.parameters.get("location", "unknown")
        return self.hardware.aspirate(vol_ul, loc)

    def _handle_mix(self, step: ExecutionStep) -> Dict[str, Any]:
        vol_ml = step.parameters.get("volume_ml", 0.0)
        vol_ul = vol_ml * 1000.0
        reps = step.parameters.get("repetitions", 3)
        loc = step.parameters.get("location", "unknown")
        return self.hardware.mix(vol_ul, reps, loc)

    def _handle_incubate(self, step: ExecutionStep) -> Dict[str, Any]:
        minutes = step.parameters.get("minutes", 0)
        seconds = minutes * 60.0
        temp = step.parameters.get("temperature_c", 37.0)
        return self.hardware.incubate(seconds, temp)

    def _handle_centrifuge(self, step: ExecutionStep) -> Dict[str, Any]:
        minutes = step.parameters.get("minutes", 0)
        seconds = minutes * 60.0
        g = step.parameters.get("g_force", 300.0)
        return self.hardware.centrifuge(seconds, g)

    def _handle_count(self, step: ExecutionStep) -> Dict[str, Any]:
        loc = step.parameters.get("location", "sample")
        return self.hardware.count_cells(loc)

    def _handle_generic(self, step: ExecutionStep) -> Dict[str, Any]:
        """Generic handler for unknown operation types."""
        return {"status": "success", "message": f"Executed {step.operation_type}"}


class WorkflowExecutor:
    """
    Executes workflows step-by-step with progress tracking and error handling.
    
    This is the main entry point for workflow execution, providing a facade
    over the execution components (repository, queue, runner).
    """
    
    def __init__(
        self,
        db_path: str = "data/executions.db",
        inventory_manager=None,
        hardware: Optional[HardwareInterface] = None,
        repository: Optional[ExecutionRepository] = None,
    ):
        self.repo = repository or ExecutionRepository(db_path)
        self.queue = ExecutionQueue()
        self.runner = WorkflowRunner(
            repo=self.repo,
            hardware=hardware,
            inventory_manager=inventory_manager,
        )
        self.step_handlers = self.runner.step_handlers
        self.hardware = self.runner.hardware
        self.inventory_manager = inventory_manager
        # Backward compatibility
        self.db = self.repo
    
    def register_handler(self, operation_type: str, handler: Callable):
        """Register a custom step handler."""
        self.runner.register_handler(operation_type, handler)

    def enqueue_execution(self, execution_id: str):
        """Add an execution ID to the local queue."""
        self.queue.submit(execution_id)

    def start_worker(self, dry_run: bool = False):
        """Process queued executions synchronously."""
        self.queue.start(lambda exec_id: self.execute(exec_id, dry_run=dry_run))

    def stop_worker(self):
        """Stop queue processing."""
        self.queue.stop()

    def pending_queue(self) -> List[str]:
        """Return queued execution IDs."""
        return self.queue.pending()
    
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
        self.repo.save(execution)
        
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
        
        # Copy explicit parameters if present (e.g. for simulation)
        if hasattr(unit_op, 'parameters') and isinstance(unit_op.parameters, dict):
            parameters.update(unit_op.parameters)
        
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
        Execute a workflow by delegating to the WorkflowRunner.
        """
        execution = self.repo.get(execution_id)
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")
        return self.runner.run(execution, dry_run=dry_run)
    
    def get_execution_status(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get current status of an execution."""
        return self.repo.get(execution_id)
    
    def list_executions(self, status: Optional[ExecutionStatus] = None) -> List[WorkflowExecution]:
        """List all executions, optionally filtered by status."""
        return self.repo.list(status)
