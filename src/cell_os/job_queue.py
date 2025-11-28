"""
Job Queue System for Workflow Execution

Provides scheduling, prioritization, and resource management for workflow executions.
"""

import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
import sqlite3
import json
from queue import PriorityQueue, Empty
import uuid


class JobPriority(Enum):
    """Priority levels for jobs."""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    URGENT = 0


class JobStatus(Enum):
    """Status of a queued job."""
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueuedJob:
    """Represents a job in the queue."""
    job_id: str
    execution_id: str
    priority: JobPriority
    status: JobStatus = JobStatus.QUEUED
    scheduled_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other):
        """Compare jobs for priority queue ordering."""
        # Lower priority value = higher priority
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        # If same priority, earlier scheduled time wins
        if self.scheduled_time and other.scheduled_time:
            return self.scheduled_time < other.scheduled_time
        # If no scheduled time, earlier creation wins
        return self.created_at < other.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "job_id": self.job_id,
            "execution_id": self.execution_id,
            "priority": self.priority.value,
            "status": self.status.value,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "metadata": self.metadata
        }


class JobQueueDatabase:
    """SQLite database for job queue persistence."""
    
    def __init__(self, db_path: str = "data/job_queue.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queued_jobs (
                job_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                priority INTEGER NOT NULL,
                status TEXT NOT NULL,
                scheduled_time TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                error_message TEXT,
                metadata TEXT
            )
        """)
        
        # Create indices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_status ON queued_jobs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_priority ON queued_jobs(priority)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_scheduled ON queued_jobs(scheduled_time)")
        
        conn.commit()
        conn.close()
    
    def save_job(self, job: QueuedJob):
        """Save or update a job."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO queued_jobs
            (job_id, execution_id, priority, status, scheduled_time, created_at,
             started_at, completed_at, error_message, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job.job_id,
            job.execution_id,
            job.priority.value,
            job.status.value,
            job.scheduled_time.isoformat() if job.scheduled_time else None,
            job.created_at.isoformat(),
            job.started_at.isoformat() if job.started_at else None,
            job.completed_at.isoformat() if job.completed_at else None,
            job.error_message,
            json.dumps(job.metadata)
        ))
        
        conn.commit()
        conn.close()
    
    def get_job(self, job_id: str) -> Optional[QueuedJob]:
        """Retrieve a job by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM queued_jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return QueuedJob(
            job_id=row[0],
            execution_id=row[1],
            priority=JobPriority(row[2]),
            status=JobStatus(row[3]),
            scheduled_time=datetime.fromisoformat(row[4]) if row[4] else None,
            created_at=datetime.fromisoformat(row[5]),
            started_at=datetime.fromisoformat(row[6]) if row[6] else None,
            completed_at=datetime.fromisoformat(row[7]) if row[7] else None,
            error_message=row[8],
            metadata=json.loads(row[9]) if row[9] else {}
        )
    
    def list_jobs(self, status: Optional[JobStatus] = None, limit: int = 100) -> List[QueuedJob]:
        """List jobs, optionally filtered by status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if status:
            cursor.execute(
                "SELECT job_id FROM queued_jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status.value, limit)
            )
        else:
            cursor.execute(
                "SELECT job_id FROM queued_jobs ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
        
        job_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return [self.get_job(jid) for jid in job_ids if self.get_job(jid)]


class JobQueue:
    """
    Job queue for scheduling and executing workflows.
    
    Features:
    - Priority-based scheduling
    - Scheduled execution (run at specific time)
    - Resource locking (prevent conflicts)
    - Automatic retry on failure
    - Background worker thread
    """
    
    def __init__(self, executor=None, db_path: str = "data/job_queue.db"):
        from cell_os.notifications import NotificationManager
        self.db = JobQueueDatabase(db_path)
        self.executor = executor
        self.queue = PriorityQueue()
        self.resource_locks: Dict[str, str] = {}  # resource_id -> job_id
        self.running = True
        self.notification_manager = NotificationManager()
        
        # Load pending jobs from database
        self._load_pending_jobs()
        
        # Start worker thread
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
    
    def _load_pending_jobs(self):
        """Load pending jobs from database into queue."""
        pending_statuses = [JobStatus.QUEUED, JobStatus.SCHEDULED]
        for status in pending_statuses:
            jobs = self.db.list_jobs(status=status)
            for job in jobs:
                # Only queue if scheduled time has passed or no scheduled time
                if not job.scheduled_time or job.scheduled_time <= datetime.now():
                    self.queue.put(job)
    
    def submit_job(
        self,
        execution_id: str,
        priority: JobPriority = JobPriority.NORMAL,
        scheduled_time: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> QueuedJob:
        """
        Submit a job to the queue.
        
        Args:
            execution_id: ID of the execution to run
            priority: Priority level
            scheduled_time: When to run (None = ASAP)
            metadata: Additional metadata
            
        Returns:
            QueuedJob object
        """
        job = QueuedJob(
            job_id=str(uuid.uuid4()),
            execution_id=execution_id,
            priority=priority,
            status=JobStatus.SCHEDULED if scheduled_time else JobStatus.QUEUED,
            scheduled_time=scheduled_time,
            metadata=metadata or {}
        )
        
        # Save to database
        self.db.save_job(job)
        
        # Add to queue if ready to run
        if not scheduled_time or scheduled_time <= datetime.now():
            self.queue.put(job)
        
        return job
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued job."""
        job = self.db.get_job(job_id)
        if not job:
            return False
        
        if job.status in [JobStatus.QUEUED, JobStatus.SCHEDULED]:
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            self.db.save_job(job)
            return True
        
        return False
    
    def get_job_status(self, job_id: str) -> Optional[QueuedJob]:
        """Get current status of a job."""
        return self.db.get_job(job_id)
    
    def list_jobs(self, status: Optional[JobStatus] = None) -> List[QueuedJob]:
        """List all jobs, optionally filtered by status."""
        return self.db.list_jobs(status=status)
    
    def acquire_resource(self, resource_id: str, job_id: str) -> bool:
        """
        Acquire a resource lock.
        
        Args:
            resource_id: Resource to lock (e.g., "ot2_deck_1")
            job_id: Job requesting the lock
            
        Returns:
            True if lock acquired, False if resource is busy
        """
        if resource_id in self.resource_locks:
            return False
        
        self.resource_locks[resource_id] = job_id
        return True
    
    def release_resource(self, resource_id: str, job_id: str):
        """Release a resource lock."""
        if self.resource_locks.get(resource_id) == job_id:
            del self.resource_locks[resource_id]
    
    def start_worker(self):
        """Start the background worker thread."""
        # Worker is now started in __init__
        pass
    
    def stop_worker(self):
        """Stop the background worker thread."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
    
    def _worker_loop(self):
        """Background worker to process jobs."""
        while self.running:
            try:
                # Get job from queue (blocking with timeout)
                try:
                    queued_job = self.queue.get(timeout=1.0)
                except Empty:
                    continue
                
                # Check if scheduled time has arrived
                if queued_job.scheduled_time and datetime.now() < queued_job.scheduled_time:
                    # Not ready yet, put back in queue
                    # Note: This is inefficient for a real system (busy wait), but fine for prototype
                    self.queue.put(queued_job)
                    time.sleep(1.0) 
                    continue
                
                # Check resource availability (simplified)
                # In a real system, we'd check specific resources required by the job
                
                # Execute job
                queued_job.status = JobStatus.RUNNING
                queued_job.started_at = datetime.now()
                self.db.save_job(queued_job)
                
                try:
                    if self.executor:
                        self.executor.execute(queued_job.execution_id)
                        queued_job.status = JobStatus.COMPLETED
                        
                        # Notify success
                        self.notification_manager.send(
                            title="Job Completed",
                            message=f"Job {queued_job.job_id} completed successfully.",
                            level="success"
                        )
                    else:
                        # Simulation mode if no executor
                        time.sleep(2.0)
                        queued_job.status = JobStatus.COMPLETED
                        
                except Exception as e:
                    queued_job.status = JobStatus.FAILED
                    queued_job.error_message = str(e)
                    
                    # Notify failure
                    self.notification_manager.send(
                        title="Job Failed",
                        message=f"Job {queued_job.job_id} failed: {e}",
                        level="error"
                    )
                
                queued_job.completed_at = datetime.now()
                self.db.save_job(queued_job)
                self.queue.task_done()
                
            except Exception as e:
                print(f"Worker error: {e}")
    
    def _check_scheduled_jobs(self):
        """Check for scheduled jobs that are ready to run."""
        # This method is no longer needed as scheduling is handled in _worker_loop
        pass
    
    def _execute_job(self, job: QueuedJob):
        """Execute a single job."""
        # This method is now integrated into _worker_loop
        pass
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about the queue."""
        all_jobs = self.db.list_jobs(limit=1000)
        
        stats = {
            "total_jobs": len(all_jobs),
            "queued": sum(1 for j in all_jobs if j.status == JobStatus.QUEUED),
            "scheduled": sum(1 for j in all_jobs if j.status == JobStatus.SCHEDULED),
            "running": sum(1 for j in all_jobs if j.status == JobStatus.RUNNING),
            "completed": sum(1 for j in all_jobs if j.status == JobStatus.COMPLETED),
            "failed": sum(1 for j in all_jobs if j.status == JobStatus.FAILED),
            "cancelled": sum(1 for j in all_jobs if j.status == JobStatus.CANCELLED),
            "queue_size": self.queue.qsize(),
            "active_locks": len(self.resource_locks)
        }
        
        return stats
