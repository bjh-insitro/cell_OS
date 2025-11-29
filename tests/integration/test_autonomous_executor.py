"""
Integration test for AutonomousExecutor

Tests the bridge between AI scientist and production execution infrastructure.
"""

import pytest
import time
from pathlib import Path

from cell_os.autonomous_executor import (
    AutonomousExecutor,
    ExperimentProposal,
    ExperimentResult
)
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.job_queue import JobPriority, JobStatus


@pytest.fixture
def executor():
    """Create an autonomous executor for testing."""
    hardware = BiologicalVirtualMachine(simulation_speed=0.0)
    executor = AutonomousExecutor(
        hardware=hardware,
        db_path="data/test_autonomous.db"
    )
    yield executor
    executor.shutdown()


def test_create_viability_workflow(executor):
    """Test creating a viability workflow from a proposal."""
    proposal = ExperimentProposal(
        proposal_id="test_001",
        cell_line="U2OS",
        compound="staurosporine",
        dose=1.0,
        assay_type="viability"
    )
    
    execution_id = executor.create_workflow(proposal)
    
    assert execution_id is not None
    assert proposal.proposal_id in executor.proposal_map
    assert executor.proposal_map[proposal.proposal_id] == execution_id


def test_submit_single_proposal(executor):
    """Test submitting a single experiment proposal."""
    proposal = ExperimentProposal(
        proposal_id="test_002",
        cell_line="HEK293T",
        compound="tunicamycin",
        dose=0.5,
        assay_type="viability"
    )
    
    job_id = executor.submit_proposal(proposal, priority=JobPriority.HIGH)
    
    assert job_id is not None
    
    # Check job was queued
    job = executor.job_queue.get_job_status(job_id)
    assert job is not None
    assert job.status in [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.COMPLETED]


def test_execute_batch_wait(executor):
    """Test executing a batch of proposals and waiting for results."""
    proposals = [
        ExperimentProposal(
            proposal_id=f"batch_test_{i}",
            cell_line="U2OS",
            compound="staurosporine",
            dose=0.1 * (i + 1),
            assay_type="viability"
        )
        for i in range(3)
    ]
    
    results = executor.execute_batch(
        proposals,
        priority=JobPriority.NORMAL,
        wait=True,
        timeout=60.0
    )
    
    assert len(results) == 3
    
    for result in results:
        assert isinstance(result, ExperimentResult)
        assert result.status == "completed"
        assert result.measurement is not None
        assert result.execution_id is not None


def test_execute_batch_no_wait(executor):
    """Test executing a batch without waiting."""
    proposals = [
        ExperimentProposal(
            proposal_id=f"async_test_{i}",
            cell_line="U2OS",
            compound="staurosporine",
            dose=1.0,
            assay_type="viability"
        )
        for i in range(2)
    ]
    
    results = executor.execute_batch(
        proposals,
        priority=JobPriority.LOW,
        wait=False
    )
    
    # Should return empty list when not waiting
    assert len(results) == 0


def test_different_assay_types(executor):
    """Test creating workflows for different assay types."""
    assay_types = ["viability", "reporter", "imaging"]
    
    for assay_type in assay_types:
        proposal = ExperimentProposal(
            proposal_id=f"assay_{assay_type}",
            cell_line="U2OS",
            compound="test_compound",
            dose=1.0,
            assay_type=assay_type
        )
        
        execution_id = executor.create_workflow(proposal)
        assert execution_id is not None


def test_queue_stats(executor):
    """Test getting queue statistics."""
    # Submit some jobs
    proposals = [
        ExperimentProposal(
            proposal_id=f"stats_test_{i}",
            cell_line="U2OS",
            compound="staurosporine",
            dose=1.0,
            assay_type="viability"
        )
        for i in range(3)
    ]
    
    for proposal in proposals:
        executor.submit_proposal(proposal)
    
    stats = executor.get_queue_stats()
    
    assert "total_jobs" in stats
    assert "queued" in stats or "running" in stats or "completed" in stats


def test_proposal_to_workflow_params(executor):
    """Test converting proposal to workflow parameters."""
    proposal = ExperimentProposal(
        proposal_id="param_test",
        cell_line="U2OS",
        compound="staurosporine",
        dose=1.0,
        assay_type="viability",
        metadata={"custom_field": "value"}
    )
    
    params = proposal.to_workflow_params()
    
    assert params["cell_line"] == "U2OS"
    assert params["compound"] == "staurosporine"
    assert params["dose"] == 1.0
    assert params["assay_type"] == "viability"
    assert params["proposal_id"] == "param_test"
    assert params["custom_field"] == "value"


def test_result_to_dict(executor):
    """Test converting result to dictionary."""
    result = ExperimentResult(
        proposal_id="dict_test",
        execution_id="exec_123",
        cell_line="U2OS",
        compound="staurosporine",
        dose=1.0,
        assay_type="viability",
        measurement=0.75,
        viability=0.95,
        status="completed",
        execution_time=10.5,
        metadata={"custom": "data"}
    )
    
    result_dict = result.to_dict()
    
    assert result_dict["proposal_id"] == "dict_test"
    assert result_dict["execution_id"] == "exec_123"
    assert result_dict["cell_line"] == "U2OS"
    assert result_dict["measurement"] == 0.75
    assert result_dict["viability"] == 0.95
    assert result_dict["custom"] == "data"


def test_multiple_cell_lines(executor):
    """Test executing experiments with different cell lines."""
    cell_lines = ["U2OS", "HEK293T", "A549"]
    
    proposals = [
        ExperimentProposal(
            proposal_id=f"cell_line_{cell_line}",
            cell_line=cell_line,
            compound="staurosporine",
            dose=1.0,
            assay_type="viability"
        )
        for cell_line in cell_lines
    ]
    
    results = executor.execute_batch(proposals, wait=True, timeout=60.0)
    
    assert len(results) == len(cell_lines)
    
    # Check each cell line was used
    result_cell_lines = {r.cell_line for r in results}
    assert result_cell_lines == set(cell_lines)


def test_dose_range(executor):
    """Test executing experiments across a dose range."""
    doses = [0.001, 0.01, 0.1, 1.0, 10.0]
    
    proposals = [
        ExperimentProposal(
            proposal_id=f"dose_{i}",
            cell_line="U2OS",
            compound="staurosporine",
            dose=dose,
            assay_type="viability"
        )
        for i, dose in enumerate(doses)
    ]
    
    results = executor.execute_batch(proposals, wait=True, timeout=60.0)
    
    assert len(results) == len(doses)
    
    # Check doses match
    result_doses = sorted([r.dose for r in results])
    assert result_doses == sorted(doses)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
