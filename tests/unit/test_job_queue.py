"""
Tests for Job Queue System
"""

import pytest
import tempfile
import os
import time
from datetime import datetime, timedelta
from cell_os.job_queue import (
    JobQueue,
    JobQueueDatabase,
    QueuedJob,
    JobPriority,
    JobStatus
)

class MockExecutor:
    """Mock executor for testing."""
    def __init__(self):
        self.executed_ids = []
    
    def execute(self, execution_id, dry_run=False):
        self.executed_ids.append(execution_id)
        # Return a mock result object
        class MockResult:
            status = "completed" # String matching ExecutionStatus.COMPLETED value if it were an enum, but here we just need to match logic
            error_message = None
        
        # We need to match the enum check in job_queue.py: if result.status == ExecutionStatus.COMPLETED:
        # Since we can't easily import ExecutionStatus inside the test without the module, let's mock the behavior
        # In job_queue.py: from cell_os.workflow_executor import ExecutionStatus
        # So we need to return an object where status equals ExecutionStatus.COMPLETED
        
        from cell_os.workflow_executor import ExecutionStatus
        result = MockResult()
        result.status = ExecutionStatus.COMPLETED
        return result

class TestJobQueueDatabase:
    """Test the job queue database."""
    
    def setup_method(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db = JobQueueDatabase(self.temp_db.name)
    
    def teardown_method(self):
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
            
    def test_save_and_retrieve_job(self):
        job = QueuedJob(
            job_id="job-1",
            execution_id="exec-1",
            priority=JobPriority.HIGH
        )
        self.db.save_job(job)
        
        retrieved = self.db.get_job("job-1")
        assert retrieved is not None
        assert retrieved.job_id == "job-1"
        assert retrieved.priority == JobPriority.HIGH
        assert retrieved.status == JobStatus.QUEUED

    def test_list_jobs(self):
        for i in range(3):
            job = QueuedJob(
                job_id=f"job-{i}",
                execution_id=f"exec-{i}",
                priority=JobPriority.NORMAL,
                status=JobStatus.COMPLETED if i == 0 else JobStatus.QUEUED
            )
            self.db.save_job(job)
            
        all_jobs = self.db.list_jobs()
        assert len(all_jobs) == 3
        
        completed = self.db.list_jobs(status=JobStatus.COMPLETED)
        assert len(completed) == 1
        assert completed[0].job_id == "job-0"

class TestJobQueue:
    """Test the job queue logic."""
    
    def setup_method(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.queue = JobQueue(db_path=self.temp_db.name)
        # Stop worker thread so it doesn't consume jobs while we test queue logic
        self.queue.stop_worker()
    
    def teardown_method(self):
        if hasattr(self, 'queue') and self.queue:
            self.queue.stop_worker()
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_submit_job(self):
        job = self.queue.submit_job("exec-1", priority=JobPriority.HIGH)
        assert job.status == JobStatus.QUEUED
        assert job.priority == JobPriority.HIGH
        
        # Verify it's in the internal queue
        assert not self.queue.queue.empty()
        queued_item = self.queue.queue.get()
        assert queued_item.job_id == job.job_id

    def test_priority_ordering(self):
        # Submit low priority first
        self.queue.submit_job("exec-low", priority=JobPriority.LOW)
        # Submit high priority second
        self.queue.submit_job("exec-high", priority=JobPriority.HIGH)
        
        # High priority should come out first
        first = self.queue.queue.get()
        second = self.queue.queue.get()
        
        assert first.execution_id == "exec-high"
        assert second.execution_id == "exec-low"

    def test_scheduled_job(self):
        future_time = datetime.now() + timedelta(hours=1)
        job = self.queue.submit_job("exec-future", scheduled_time=future_time)
        
        assert job.status == JobStatus.SCHEDULED
        # Should NOT be in the immediate queue
        assert self.queue.queue.empty()
        
        # Check DB
        saved_job = self.queue.get_job_status(job.job_id)
        assert saved_job.status == JobStatus.SCHEDULED

    def test_resource_locking(self):
        success = self.queue.acquire_resource("robot-1", "job-1")
        assert success is True
        
        # Try to acquire same resource with different job
        success = self.queue.acquire_resource("robot-1", "job-2")
        assert success is False
        
        # Release and try again
        self.queue.release_resource("robot-1", "job-1")
        success = self.queue.acquire_resource("robot-1", "job-2")
        assert success is True

    def test_cancel_job(self):
        job = self.queue.submit_job("exec-1")
        assert job.status == JobStatus.QUEUED
        
        success = self.queue.cancel_job(job.job_id)
        assert success is True
        
        updated_job = self.queue.get_job_status(job.job_id)
        assert updated_job.status == JobStatus.CANCELLED

    def test_worker_execution(self):
        # Setup mock executor
        mock_executor = MockExecutor()
        
        # Re-initialize queue with executor
        if self.queue:
            self.queue.stop_worker()
        self.queue = JobQueue(db_path=self.temp_db.name, executor=mock_executor)
        
        # Submit job
        self.queue.submit_job("exec-1")
        
        # Wait for worker to process (with timeout)
        import time
        start = time.time()
        while time.time() - start < 2.0:
            if "exec-1" in mock_executor.executed_ids:
                break
            time.sleep(0.1)
            
        assert "exec-1" in mock_executor.executed_ids
        
        # Verify status update
        jobs = self.queue.list_jobs()
        assert jobs[0].status == JobStatus.COMPLETED
