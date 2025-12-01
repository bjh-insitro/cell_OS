"""
Autonomous Executor - Bridge between AI Scientist and Execution Infrastructure

This module connects the autonomous optimization loop (scripts/demos/run_loop.py) with
the production-ready execution infrastructure (WorkflowExecutor + JobQueue).

Key Features:
- Converts AI proposals into executable workflows
- Submits experiments through JobQueue for scheduling
- Tracks execution progress and collects results
- Provides crash recovery for autonomous campaigns
- Unifies manual and autonomous experiment execution
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
import json

from cell_os.workflow_executor import WorkflowExecutor, ExecutionStatus
from cell_os.job_queue import JobQueue, JobPriority, JobStatus
from cell_os.hardware.base import HardwareInterface
from cell_os.hardware.virtual import VirtualMachine


@dataclass
class ExperimentProposal:
    """
    Represents an experiment proposed by the AI scientist.
    
    This is the interface between the acquisition function and the executor.
    """
    proposal_id: str
    cell_line: str
    compound: str
    dose: float
    assay_type: str  # e.g., "viability", "reporter", "imaging"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_workflow_params(self) -> Dict[str, Any]:
        """Convert proposal to workflow parameters."""
        return {
            "cell_line": self.cell_line,
            "compound": self.compound,
            "dose": self.dose,
            "assay_type": self.assay_type,
            "proposal_id": self.proposal_id,
            **self.metadata
        }


@dataclass
class ExperimentResult:
    """
    Results from an executed experiment.
    
    This is returned to the AI scientist for model updating.
    """
    proposal_id: str
    execution_id: str
    cell_line: str
    compound: str
    dose: float
    assay_type: str
    measurement: float
    viability: Optional[float] = None
    status: str = "completed"
    error_message: Optional[str] = None
    execution_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for model training."""
        return {
            "proposal_id": self.proposal_id,
            "execution_id": self.execution_id,
            "cell_line": self.cell_line,
            "compound": self.compound,
            "dose": self.dose,
            "assay_type": self.assay_type,
            "measurement": self.measurement,
            "viability": self.viability,
            "status": self.status,
            "error_message": self.error_message,
            "execution_time": self.execution_time,
            **self.metadata
        }


class AutonomousExecutor:
    """
    Executes experiments proposed by the AI scientist using the production infrastructure.
    
    This class bridges the gap between:
    - AI scientist (acquisition functions, Gaussian processes)
    - Production execution (WorkflowExecutor, JobQueue)
    
    Usage:
        executor = AutonomousExecutor(hardware=hardware)
        
        # AI proposes experiments
        proposals = acquisition_function.propose(n=8)
        
        # Execute through production infrastructure
        results = executor.execute_batch(proposals, wait=True)
        
        # Update AI model
        learner.update(results)
    """
    
    def __init__(
        self,
        hardware: Optional[HardwareInterface] = None,
        workflow_executor: Optional[WorkflowExecutor] = None,
        job_queue: Optional[JobQueue] = None,
        db_path: str = "data/autonomous_experiments.db"
    ):
        """
        Initialize the autonomous executor.
        
        Args:
            hardware: Hardware interface (defaults to VirtualMachine)
            workflow_executor: Workflow executor (created if not provided)
            job_queue: Job queue (created if not provided)
            db_path: Database path for tracking autonomous experiments
        """
        self.hardware = hardware or VirtualMachine()
        self.workflow_executor = workflow_executor or WorkflowExecutor(
            hardware=self.hardware,
            db_path=db_path.replace("autonomous_experiments", "executions")
        )
        self.job_queue = job_queue or JobQueue(
            executor=self.workflow_executor,
            db_path=db_path.replace("autonomous_experiments", "job_queue")
        )
        
        # Start job queue worker
        self.job_queue.start_worker()
        
        # Track proposal -> execution mapping
        self.proposal_map: Dict[str, str] = {}  # proposal_id -> execution_id
        
        # Register workflow generator
        self._register_workflow_generators()
    
    def _register_workflow_generators(self):
        """Register functions to convert proposals into workflows."""
        self.workflow_generators: Dict[str, Callable] = {
            "viability": self._generate_viability_workflow,
            "reporter": self._generate_reporter_workflow,
            "imaging": self._generate_imaging_workflow,
        }
        
        # Register custom handlers for autonomous operations
        self.workflow_executor.register_handler("seed", self._handle_seed)
        self.workflow_executor.register_handler("assay", self._handle_assay)
        self.workflow_executor.register_handler("imaging", self._handle_imaging_assay)
    
    def _generate_viability_workflow(self, proposal: ExperimentProposal) -> List[Dict[str, Any]]:
        """Generate workflow steps for viability assay."""
        vessel_id = f"plate_{proposal.proposal_id}"
        
        steps = [
            {
                "name": "seed_cells",
                "operation_type": "seed",
                "parameters": {
                    "vessel_id": vessel_id,
                    "cell_line": proposal.cell_line,
                    "cell_count": 10000,
                    "volume_ul": 100
                }
            },
            {
                "name": "incubate_attachment",
                "operation_type": "incubate",
                "parameters": {
                    "vessel_id": vessel_id,
                    "duration_seconds": 4 * 3600,  # 4 hours
                    "temperature": 37.0
                }
            },
            {
                "name": "add_compound",
                "operation_type": "dispense",
                "parameters": {
                    "vessel_id": vessel_id,
                    "reagent": proposal.compound,
                    "volume_ul": 10,
                    "concentration_um": proposal.dose
                }
            },
            {
                "name": "incubate_treatment",
                "operation_type": "incubate",
                "parameters": {
                    "vessel_id": vessel_id,
                    "duration_seconds": 24 * 3600,  # 24 hours
                    "temperature": 37.0
                }
            },
            {
                "name": "measure_viability",
                "operation_type": "assay",
                "parameters": {
                    "vessel_id": vessel_id,
                    "assay_type": "viability",
                    "readout": "luminescence"
                }
            }
        ]
        
        return steps
    
    def _generate_reporter_workflow(self, proposal: ExperimentProposal) -> List[Dict[str, Any]]:
        """Generate workflow steps for reporter assay."""
        vessel_id = f"plate_{proposal.proposal_id}"
        
        steps = [
            {
                "name": "seed_cells",
                "operation_type": "seed",
                "parameters": {
                    "vessel_id": vessel_id,
                    "cell_line": proposal.cell_line,
                    "cell_count": 10000,
                    "volume_ul": 100
                }
            },
            {
                "name": "incubate_attachment",
                "operation_type": "incubate",
                "parameters": {
                    "vessel_id": vessel_id,
                    "duration_seconds": 4 * 3600,
                    "temperature": 37.0
                }
            },
            {
                "name": "add_compound",
                "operation_type": "dispense",
                "parameters": {
                    "vessel_id": vessel_id,
                    "reagent": proposal.compound,
                    "volume_ul": 10,
                    "concentration_um": proposal.dose
                }
            },
            {
                "name": "incubate_treatment",
                "operation_type": "incubate",
                "parameters": {
                    "vessel_id": vessel_id,
                    "duration_seconds": 24 * 3600,
                    "temperature": 37.0
                }
            },
            {
                "name": "measure_reporter",
                "operation_type": "assay",
                "parameters": {
                    "vessel_id": vessel_id,
                    "assay_type": "reporter",
                    "readout": "fluorescence"
                }
            }
        ]
        
        return steps
    
    def _generate_imaging_workflow(self, proposal: ExperimentProposal) -> List[Dict[str, Any]]:
        """Generate workflow steps for imaging assay."""
        vessel_id = f"plate_{proposal.proposal_id}"
        
        steps = [
            {
                "name": "seed_cells",
                "operation_type": "seed",
                "parameters": {
                    "vessel_id": vessel_id,
                    "cell_line": proposal.cell_line,
                    "cell_count": 5000,
                    "volume_ul": 100
                }
            },
            {
                "name": "incubate_attachment",
                "operation_type": "incubate",
                "parameters": {
                    "vessel_id": vessel_id,
                    "duration_seconds": 4 * 3600,
                    "temperature": 37.0
                }
            },
            {
                "name": "add_compound",
                "operation_type": "dispense",
                "parameters": {
                    "vessel_id": vessel_id,
                    "reagent": proposal.compound,
                    "volume_ul": 10,
                    "concentration_um": proposal.dose
                }
            },
            {
                "name": "incubate_treatment",
                "operation_type": "incubate",
                "parameters": {
                    "vessel_id": vessel_id,
                    "duration_seconds": 48 * 3600,  # 48 hours for imaging
                    "temperature": 37.0
                }
            },
            {
                "name": "acquire_images",
                "operation_type": "imaging",
                "parameters": {
                    "vessel_id": vessel_id,
                    "channels": ["DAPI", "GFP", "RFP"],
                    "sites_per_well": 9
                }
            }
        ]
        
        return steps
    
    def create_workflow(self, proposal: ExperimentProposal) -> str:
        """
        Create a workflow from an experiment proposal.
        
        Args:
            proposal: Experiment proposal from AI scientist
            
        Returns:
            execution_id: ID of the created workflow execution
        """
        import uuid
        from cell_os.workflow_executor import WorkflowExecution, ExecutionStep, StepStatus
        from datetime import datetime
        
        # Generate workflow steps based on assay type
        generator = self.workflow_generators.get(proposal.assay_type)
        if not generator:
            raise ValueError(f"Unknown assay type: {proposal.assay_type}")
        
        step_dicts = generator(proposal)
        
        # Create execution ID
        execution_id = str(uuid.uuid4())
        
        # Create execution object
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_name=f"autonomous_{proposal.assay_type}",
            cell_line=proposal.cell_line,
            vessel_id=f"plate_{proposal.proposal_id}",
            operation_type=proposal.assay_type,
            metadata={
                "proposal_id": proposal.proposal_id,
                "compound": proposal.compound,
                "dose": proposal.dose,
                "autonomous": True
            }
        )
        
        # Convert step dictionaries to ExecutionStep objects
        for idx, step_dict in enumerate(step_dicts):
            step = ExecutionStep(
                step_id=str(uuid.uuid4()),
                step_index=idx,
                name=step_dict["name"],
                operation_type=step_dict["operation_type"],
                parameters=step_dict["parameters"],
                status=StepStatus.PENDING
            )
            execution.steps.append(step)
        
        # Save to database
        self.workflow_executor.db.save_execution(execution)
        
        # Track mapping
        self.proposal_map[proposal.proposal_id] = execution_id
        
        return execution_id
    
    def submit_proposal(
        self,
        proposal: ExperimentProposal,
        priority: JobPriority = JobPriority.NORMAL
    ) -> str:
        """
        Submit a single experiment proposal for execution.
        
        Args:
            proposal: Experiment proposal
            priority: Job priority
            
        Returns:
            job_id: ID of the submitted job
        """
        # Create workflow
        execution_id = self.create_workflow(proposal)
        
        # Submit to job queue
        job = self.job_queue.submit_job(
            execution_id=execution_id,
            priority=priority,
            metadata={
                "proposal_id": proposal.proposal_id,
                "autonomous": True
            }
        )
        
        return job.job_id
    
    def execute_batch(
        self,
        proposals: List[ExperimentProposal],
        priority: JobPriority = JobPriority.NORMAL,
        wait: bool = True,
        timeout: float = 300.0
    ) -> List[ExperimentResult]:
        """
        Execute a batch of experiment proposals.
        
        Args:
            proposals: List of experiment proposals
            priority: Job priority for all experiments
            wait: If True, wait for all experiments to complete
            timeout: Maximum time to wait (seconds)
            
        Returns:
            List of experiment results
        """
        # Submit all proposals
        job_ids = []
        for proposal in proposals:
            job_id = self.submit_proposal(proposal, priority=priority)
            job_ids.append(job_id)
        
        if not wait:
            return []
        
        # Wait for completion
        start_time = time.time()
        results = []
        
        while time.time() - start_time < timeout:
            all_complete = True
            
            for i, (proposal, job_id) in enumerate(zip(proposals, job_ids)):
                # Check job status
                job = self.job_queue.get_job_status(job_id)
                
                if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                    # Already processed
                    if i < len(results):
                        continue
                    
                    # Get execution result
                    execution_id = self.proposal_map[proposal.proposal_id]
                    execution = self.workflow_executor.get_execution_status(execution_id)
                    
                    # Extract result
                    result = self._extract_result(proposal, execution)
                    results.append(result)
                else:
                    all_complete = False
            
            if all_complete and len(results) == len(proposals):
                break
            
            time.sleep(0.5)
        
        return results
    
    def _extract_result(
        self,
        proposal: ExperimentProposal,
        execution: Any
    ) -> ExperimentResult:
        """Extract experiment result from execution."""
        # Find the measurement step
        measurement = None
        viability = None
        
        for step in execution.steps:
            if step.operation_type in ["assay", "imaging"]:
                if step.result:
                    measurement = step.result.get("measurement", 0.0)
                    viability = step.result.get("viability", 1.0)
                break
        
        # Create result
        result = ExperimentResult(
            proposal_id=proposal.proposal_id,
            execution_id=execution.execution_id,
            cell_line=proposal.cell_line,
            compound=proposal.compound,
            dose=proposal.dose,
            assay_type=proposal.assay_type,
            measurement=measurement or 0.0,
            viability=viability,
            status="completed" if execution.status == ExecutionStatus.COMPLETED else "failed",
            error_message=execution.error_message,
            execution_time=(execution.completed_at - execution.started_at).total_seconds() if execution.completed_at else None,
            metadata=execution.metadata
        )
        
        return result
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about the job queue."""
        return self.job_queue.get_queue_stats()
    
    def _handle_seed(self, step) -> Dict[str, Any]:
        """Handle cell seeding operation."""
        vessel_id = step.parameters.get("vessel_id")
        cell_line = step.parameters.get("cell_line")
        cell_count = step.parameters.get("cell_count", 10000)
        volume_ul = step.parameters.get("volume_ul", 100)
        
        # Use hardware to seed cells
        result = self.hardware.seed_vessel(
            vessel_id=vessel_id,
            cell_line=cell_line,
            initial_count=cell_count
        )
        
        return {
            "vessel_id": vessel_id,
            "cell_line": cell_line,
            "seeded_count": cell_count,
            "volume_ul": volume_ul,
            "status": "success"
        }
    
    def _handle_assay(self, step) -> Dict[str, Any]:
        """Handle assay measurement operation."""
        vessel_id = step.parameters.get("vessel_id")
        assay_type = step.parameters.get("assay_type")
        readout = step.parameters.get("readout", "luminescence")
        
        # Simulate assay measurement
        # In real implementation, this would interface with plate reader
        import random
        
        # Get simulated measurement based on assay type
        if assay_type == "viability":
            measurement = random.uniform(0.5, 1.0)  # Viability fraction
            viability = measurement
        elif assay_type == "reporter":
            measurement = random.uniform(100, 10000)  # RFU
            viability = random.uniform(0.8, 1.0)
        else:
            measurement = random.uniform(0, 1)
            viability = 1.0
        
        return {
            "vessel_id": vessel_id,
            "assay_type": assay_type,
            "readout": readout,
            "measurement": measurement,
            "viability": viability,
            "status": "success"
        }
    
    def _handle_imaging_assay(self, step) -> Dict[str, Any]:
        """Handle imaging acquisition operation."""
        vessel_id = step.parameters.get("vessel_id")
        channels = step.parameters.get("channels", ["DAPI"])
        sites_per_well = step.parameters.get("sites_per_well", 9)
        
        # Simulate imaging
        import random
        
        # Generate mock image metrics
        measurement = random.uniform(0.3, 0.9)  # Phenotype score
        
        return {
            "vessel_id": vessel_id,
            "channels": channels,
            "sites_per_well": sites_per_well,
            "total_images": len(channels) * sites_per_well,
            "measurement": measurement,
            "viability": random.uniform(0.8, 1.0),
            "status": "success"
        }
    
    def shutdown(self):
        """Shutdown the executor and clean up resources."""
        self.job_queue.stop_worker()
