"""
Tests for Campaign Manager
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from cell_os.campaign_manager import CampaignManager
from cell_os.database.repositories.campaign import CampaignRepository, Campaign
from cell_os.job_queue import JobQueue
from cell_os.workflow_execution import WorkflowExecutor
from cell_os.protocol_resolver import ProtocolResolver

class MockJobQueue:
    def submit_job(self, execution_id, priority, scheduled_time):
        class MockJob:
            job_id = "job-123"
        return MockJob()

class MockExecutor:
    def create_execution_from_protocol(self, **kwargs):
        class MockExecution:
            execution_id = "exec-123"
        return MockExecution()

class MockResolver:
    def __init__(self):
        self.ops = MockOps()
        
    def resolve_passage_protocol(self, cell_line, vessel_type):
        return []

class MockOps:
    def op_thaw(self, *args, **kwargs):
        return "thaw_op"
    def op_feed(self, *args, **kwargs):
        return "feed_op"

class TestCampaignDatabase:
    def setup_method(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db = CampaignRepository(self.temp_db.name)
        
    def teardown_method(self):
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
            
    def test_save_and_retrieve_campaign(self):
        campaign = Campaign(
            campaign_id="camp-1",
            campaign_type="manual",
            name="Test Campaign",
            description="Test Desc"
        )
        self.db.create_campaign(campaign)
        
        retrieved = self.db.find_campaigns()
        assert len(retrieved) == 1
        assert retrieved[0].name == "Test Campaign"

class TestCampaignManager:
    def setup_method(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        
        self.queue = MockJobQueue()
        self.executor = MockExecutor()
        self.resolver = MockResolver()
        
        self.manager = CampaignManager(
            job_queue=self.queue,
            executor=self.executor,
            resolver=self.resolver,
            db_path=self.temp_db.name
        )
        
    def teardown_method(self):
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
            
    def test_create_campaign(self):
        campaign = self.manager.create_campaign("Test Campaign")
        assert campaign.name == "Test Campaign"
        assert campaign.status == "active"
        
    def test_generate_schedule(self):
        campaign = self.manager.create_campaign("Schedule Test")
        start_date = datetime.now()
        
        self.manager.generate_maintenance_schedule(
            campaign.campaign_id,
            "HEK293T",
            "flask_T75",
            start_date,
            duration_days=5,
            passage_interval_days=3,
            feed_interval_days=1
        )
        
        jobs = self.manager.db.get_campaign_jobs(campaign.campaign_id)
        # Day 1: Feed
        # Day 2: Feed
        # Day 3: Passage
        # Day 4: Feed
        # Day 5: Feed
        assert len(jobs) == 5
        assert jobs[2].operation_type == "passage"
        assert jobs[0].operation_type == "feed"
        
    def test_submit_campaign(self):
        campaign = self.manager.create_campaign("Submit Test")
        self.manager.add_job_to_campaign(
            campaign.campaign_id,
            "Test Protocol",
            "HEK293T",
            "flask_T75",
            "feed",
            datetime.now()
        )
        
        self.manager.submit_campaign(campaign.campaign_id)
        
        jobs = self.manager.db.get_campaign_jobs(campaign.campaign_id)
        assert jobs[0].status == "submitted"
        assert jobs[0].job_id == "job-123"
