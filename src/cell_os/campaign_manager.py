"""
Campaign Manager

Manages high-level experimental campaigns, generating schedules of jobs
and submitting them to the Job Queue.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from cell_os.job_queue import JobQueue, JobPriority
from cell_os.workflow_execution import WorkflowExecutor
from cell_os.protocol_resolver import ProtocolResolver
from cell_os.database.repositories.campaign import CampaignRepository, Campaign, CampaignJob


class CampaignManager:
    """
    Orchestrates campaign creation and execution.
    """
    
    def __init__(self, job_queue: JobQueue, executor: WorkflowExecutor, resolver: ProtocolResolver, db_path: str = "data/campaigns.db"):
        self.job_queue = job_queue
        self.executor = executor
        self.resolver = resolver
        self.db = CampaignRepository(db_path)
        
    def create_campaign(self, name: str, description: str = "") -> Campaign:
        """Create a new campaign."""
        campaign = Campaign(
            campaign_id=str(uuid.uuid4()),
            campaign_type="manual",
            name=name,
            description=description,
            status="active",
            created_at=datetime.now().isoformat()
        )
        self.db.create_campaign(campaign)
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
        self.db.add_campaign_job(job)
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
                self.db.add_campaign_job(job)
                
            except Exception as e:
                print(f"Failed to submit job {job.campaign_job_id}: {e}")
                job.status = "failed" # Mark as failed submission
                self.db.add_campaign_job(job)
        
        # Update campaign status
        campaign = self.db.get_campaign(campaign_id)
        if campaign:
            self.db.update_campaign_status(campaign_id, "active")
