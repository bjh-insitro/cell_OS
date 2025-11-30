"""
Campaign Manager

Manages high-level experimental campaigns, generating schedules of jobs
and submitting them to the Job Queue.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import sqlite3
import json
from pathlib import Path

from cell_os.job_queue import JobQueue, JobPriority


@dataclass
class Campaign:
    """Represents a high-level campaign (collection of related jobs)."""
    campaign_id: str
    name: str
    description: str
    status: str = "active"  # active, completed, cancelled
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CampaignJob:
    """A job within a campaign."""
    campaign_job_id: str
    campaign_id: str
    protocol_name: str
    cell_line: str
    vessel_id: str
    operation_type: str
    scheduled_time: datetime
    status: str = "pending"  # pending, submitted, completed, failed
    job_id: Optional[str] = None  # Link to JobQueue job_id


class CampaignDatabase:
    """SQLite database for campaigns."""
    
    def __init__(self, db_path: str = "data/campaigns.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                campaign_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaign_jobs (
                campaign_job_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                protocol_name TEXT NOT NULL,
                cell_line TEXT NOT NULL,
                vessel_id TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                status TEXT NOT NULL,
                job_id TEXT,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
            )
        """)
        
        conn.commit()
        conn.close()
        
    def save_campaign(self, campaign: Campaign):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO campaigns (campaign_id, name, description, status, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            campaign.campaign_id,
            campaign.name,
            campaign.description,
            campaign.status,
            campaign.created_at.isoformat(),
            json.dumps(campaign.metadata)
        ))
        conn.commit()
        conn.close()
        
    def save_campaign_job(self, job: CampaignJob):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO campaign_jobs 
            (campaign_job_id, campaign_id, protocol_name, cell_line, vessel_id, operation_type, scheduled_time, status, job_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job.campaign_job_id,
            job.campaign_id,
            job.protocol_name,
            job.cell_line,
            job.vessel_id,
            job.operation_type,
            job.scheduled_time.isoformat(),
            job.status,
            job.job_id
        ))
        conn.commit()
        conn.close()
        
    def list_campaigns(self) -> List[Campaign]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM campaigns ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        campaigns = []
        for r in rows:
            metadata = {}
            if r[5] and isinstance(r[5], str) and r[5].strip():
                try:
                    metadata = json.loads(r[5])
                except json.JSONDecodeError:
                    print(f"Warning: Failed to parse metadata for campaign {r[0]}: {r[5]}")
            
            created_at = datetime.now()
            if r[4]:
                if isinstance(r[4], str):
                    try:
                        created_at = datetime.fromisoformat(r[4])
                    except ValueError:
                        pass
                elif isinstance(r[4], datetime):
                    created_at = r[4]

            campaigns.append(Campaign(
                campaign_id=r[0],
                name=r[1],
                description=r[2],
                status=r[3],
                created_at=created_at,
                metadata=metadata
            ))
        
        return campaigns
        
    def get_campaign_jobs(self, campaign_id: str) -> List[CampaignJob]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM campaign_jobs WHERE campaign_id = ? ORDER BY scheduled_time ASC", (campaign_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [CampaignJob(
            campaign_job_id=r[0],
            campaign_id=r[1],
            protocol_name=r[2],
            cell_line=r[3],
            vessel_id=r[4],
            operation_type=r[5],
            scheduled_time=datetime.fromisoformat(r[6]) if isinstance(r[6], str) else r[6],
            status=r[7],
            job_id=r[8]
        ) for r in rows]


from cell_os.workflow_executor import WorkflowExecutor
from cell_os.protocol_resolver import ProtocolResolver

class CampaignManager:
    """
    Orchestrates campaign creation and execution.
    """
    
    def __init__(self, job_queue: JobQueue, executor: WorkflowExecutor, resolver: ProtocolResolver, db_path: str = "data/campaigns.db"):
        self.job_queue = job_queue
        self.executor = executor
        self.resolver = resolver
        self.db = CampaignDatabase(db_path)
        
    def create_campaign(self, name: str, description: str = "") -> Campaign:
        """Create a new campaign."""
        campaign = Campaign(
            campaign_id=str(uuid.uuid4()),
            name=name,
            description=description
        )
        self.db.save_campaign(campaign)
        return campaign
        
    def add_job_to_campaign(self, campaign_id: str, protocol_name: str, cell_line: str, 
                           vessel_id: str, operation_type: str, scheduled_time: datetime) -> CampaignJob:
        """Add a planned job to a campaign."""
        job = CampaignJob(
            campaign_job_id=str(uuid.uuid4()),
            campaign_id=campaign_id,
            protocol_name=protocol_name,
            cell_line=cell_line,
            vessel_id=vessel_id,
            operation_type=operation_type,
            scheduled_time=scheduled_time
        )
        self.db.save_campaign_job(job)
        return job
        
    def generate_maintenance_schedule(self, campaign_id: str, cell_line: str, vessel_id: str, 
                                    start_date: datetime, duration_days: int, 
                                    passage_interval_days: int = 3, feed_interval_days: int = 1):
        """
        Generate a schedule of Feed and Passage operations.
        
        Logic:
        - Feed every `feed_interval_days`
        - Passage every `passage_interval_days` (replaces Feed on that day)
        """
        current_date = start_date
        end_date = start_date + timedelta(days=duration_days)
        
        day_count = 0
        
        while current_date < end_date:
            day_count += 1
            current_date += timedelta(days=1)
            
            # Determine operation
            if day_count % passage_interval_days == 0:
                op_type = "passage"
            elif day_count % feed_interval_days == 0:
                op_type = "feed"
            else:
                continue
                
            # Schedule at 9 AM
            run_time = datetime.combine(current_date.date(), datetime.min.time()) + timedelta(hours=9)
            
            self.add_job_to_campaign(
                campaign_id=campaign_id,
                protocol_name=f"{op_type.title()} {cell_line} (Day {day_count})",
                cell_line=cell_line,
                vessel_id=vessel_id,
                operation_type=op_type,
                scheduled_time=run_time
            )
            
    def submit_campaign(self, campaign_id: str):
        """
        Submit all pending jobs in a campaign to the JobQueue.
        """
        jobs = self.db.get_campaign_jobs(campaign_id)
        
        for job in jobs:
            if job.status != "pending":
                continue
                
            try:
                # 1. Resolve Protocol
                if job.operation_type == "passage":
                    parts = job.vessel_id.split('_')
                    vessel_type = parts[1].upper() if len(parts) > 1 else parts[-1].upper()
                    unit_ops = self.resolver.resolve_passage_protocol(job.cell_line, vessel_type)
                elif job.operation_type == "thaw":
                    # Need access to ops, which resolver has
                    thaw_op = self.resolver.ops.op_thaw(job.vessel_id, cell_line=job.cell_line)
                    unit_ops = [thaw_op]
                elif job.operation_type == "feed":
                    feed_op = self.resolver.ops.op_feed(job.vessel_id, cell_line=job.cell_line)
                    unit_ops = [feed_op]
                else:
                    print(f"Unknown operation: {job.operation_type}")
                    continue

                # 2. Create Execution
                execution = self.executor.create_execution_from_protocol(
                    protocol_name=job.protocol_name,
                    cell_line=job.cell_line,
                    vessel_id=job.vessel_id,
                    operation_type=job.operation_type,
                    unit_ops=unit_ops,
                    metadata={"campaign_id": campaign_id, "campaign_job_id": job.campaign_job_id}
                )
                
                # 3. Submit to Queue
                queue_job = self.job_queue.submit_job(
                    execution_id=execution.execution_id,
                    priority=JobPriority.NORMAL,
                    scheduled_time=job.scheduled_time
                )
                
                # 4. Update Campaign Job
                job.status = "submitted"
                job.job_id = queue_job.job_id
                self.db.save_campaign_job(job)
                
            except Exception as e:
                print(f"Failed to submit job {job.campaign_job_id}: {e}")
                job.status = "failed" # Mark as failed submission
                self.db.save_campaign_job(job)
        
        # Update campaign status
        campaign_list = [c for c in self.db.list_campaigns() if c.campaign_id == campaign_id]
        if campaign_list:
            campaign = campaign_list[0]
            campaign.status = "active" # Or running
            self.db.save_campaign(campaign)

