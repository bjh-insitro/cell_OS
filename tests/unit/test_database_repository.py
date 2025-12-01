"""
Test database repository pattern.
"""
import os
import tempfile
from cell_os.database import CampaignRepository, Campaign, CampaignIteration, Experiment


def test_campaign_repository_create_and_get(tmp_path):
    """Test creating and retrieving a campaign."""
    db_path = str(tmp_path / "test_campaigns.db")
    repo = CampaignRepository(db_path)
    
    campaign = Campaign(
        campaign_id="test_campaign_1",
        campaign_type="autonomous",
        goal="Test goal",
        status="running",
        config={"param1": "value1"}
    )
    
    repo.create_campaign(campaign)
    retrieved = repo.get_campaign("test_campaign_1")
    
    assert retrieved is not None
    assert retrieved.campaign_id == "test_campaign_1"
    assert retrieved.campaign_type == "autonomous"
    assert retrieved.config == {"param1": "value1"}


def test_campaign_repository_update_status(tmp_path):
    """Test updating campaign status."""
    db_path = str(tmp_path / "test_campaigns.db")
    repo = CampaignRepository(db_path)
    
    campaign = Campaign(
        campaign_id="test_campaign_2",
        campaign_type="manual",
        status="running"
    )
    
    repo.create_campaign(campaign)
    repo.update_campaign_status("test_campaign_2", "completed", {"final_score": 0.95})
    
    retrieved = repo.get_campaign("test_campaign_2")
    assert retrieved.status == "completed"
    assert retrieved.results_summary == {"final_score": 0.95}
    assert retrieved.end_date is not None


def test_campaign_iterations(tmp_path):
    """Test adding and retrieving iterations."""
    db_path = str(tmp_path / "test_campaigns.db")
    repo = CampaignRepository(db_path)
    
    campaign = Campaign(
        campaign_id="test_campaign_3",
        campaign_type="autonomous"
    )
    repo.create_campaign(campaign)
    
    # Add iterations
    for i in range(3):
        iteration = CampaignIteration(
            campaign_id="test_campaign_3",
            iteration_number=i,
            proposals=[{"proposal": f"test_{i}"}],
            metrics={"score": i * 0.1}
        )
        repo.add_iteration(iteration)
    
    # Retrieve iterations
    iterations = repo.get_iterations("test_campaign_3")
    assert len(iterations) == 3
    assert iterations[0].iteration_number == 0
    assert iterations[2].metrics == {"score": 0.2}


def test_experiment_linking(tmp_path):
    """Test linking experiments to campaigns."""
    db_path = str(tmp_path / "test_campaigns.db")
    repo = CampaignRepository(db_path)
    
    campaign = Campaign(
        campaign_id="test_campaign_4",
        campaign_type="manual"
    )
    repo.create_campaign(campaign)
    
    # Create experiments
    for i in range(2):
        experiment = Experiment(
            experiment_id=f"exp_{i}",
            campaign_id="test_campaign_4",
            experiment_type="test",
            status="completed"
        )
        repo.create_experiment(experiment)
        repo.link_experiment_to_campaign("test_campaign_4", f"exp_{i}", iteration_number=i)
    
    # Get linked experiments
    exp_ids = repo.get_campaign_experiments("test_campaign_4")
    assert len(exp_ids) == 2
    assert "exp_0" in exp_ids
    assert "exp_1" in exp_ids


def test_find_campaigns(tmp_path):
    """Test finding campaigns by filters."""
    db_path = str(tmp_path / "test_campaigns.db")
    repo = CampaignRepository(db_path)
    
    # Create multiple campaigns
    for i in range(3):
        campaign = Campaign(
            campaign_id=f"campaign_{i}",
            campaign_type="autonomous" if i % 2 == 0 else "manual",
            status="running" if i < 2 else "completed"
        )
        repo.create_campaign(campaign)
    
    # Find autonomous campaigns
    autonomous = repo.find_campaigns(campaign_type="autonomous")
    assert len(autonomous) == 2
    
    # Find completed campaigns
    completed = repo.find_campaigns(status="completed")
    assert len(completed) == 1


def test_campaign_stats(tmp_path):
    """Test getting campaign statistics."""
    db_path = str(tmp_path / "test_campaigns.db")
    repo = CampaignRepository(db_path)
    
    campaign = Campaign(
        campaign_id="test_campaign_5",
        campaign_type="autonomous"
    )
    repo.create_campaign(campaign)
    
    # Add iterations and experiments
    for i in range(2):
        iteration = CampaignIteration(
            campaign_id="test_campaign_5",
            iteration_number=i
        )
        repo.add_iteration(iteration)
        
        experiment = Experiment(
            experiment_id=f"exp_stats_{i}",
            campaign_id="test_campaign_5"
        )
        repo.create_experiment(experiment)
        repo.link_experiment_to_campaign("test_campaign_5", f"exp_stats_{i}")
    
    stats = repo.get_campaign_stats("test_campaign_5")
    assert stats['iteration_count'] == 2
    assert stats['experiment_count'] == 2
