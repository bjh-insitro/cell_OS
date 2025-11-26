"""Tests for Campaign budget management."""

import pytest
from cell_os.campaign import Campaign, CampaignGoal
from cell_os.posteriors import Phase0WorldModel


class MockGoal:
    """Mock goal for testing."""
    def is_met(self, world_model):
        return False


class TestCampaignBudget:
    """Tests for Campaign budget tracking."""
    
    def test_campaign_init_with_budget(self):
        """Test campaign initialization with budget."""
        goal = MockGoal()
        campaign = Campaign(goal, max_cycles=5, budget_total_usd=1000.0)
        
        assert campaign.budget_total_usd == 1000.0
        assert campaign.budget_spent_usd == 0.0
        assert campaign.budget_remaining_usd == 1000.0
    
    def test_campaign_init_unlimited_budget(self):
        """Test campaign with unlimited budget (default)."""
        goal = MockGoal()
        campaign = Campaign(goal, max_cycles=5)
        
        assert campaign.budget_total_usd == float('inf')
        assert campaign.budget_remaining_usd == float('inf')
    
    def test_spend_within_budget(self):
        """Test spending within budget."""
        goal = MockGoal()
        campaign = Campaign(goal, budget_total_usd=1000.0)
        
        campaign.spend(100.0)
        assert campaign.budget_spent_usd == 100.0
        assert campaign.budget_remaining_usd == 900.0
        
        campaign.spend(200.0)
        assert campaign.budget_spent_usd == 300.0
        assert campaign.budget_remaining_usd == 700.0
    
    def test_spend_exceeds_budget_raises(self):
        """Test that spending beyond budget raises error."""
        goal = MockGoal()
        campaign = Campaign(goal, budget_total_usd=100.0)
        
        with pytest.raises(ValueError, match="Insufficient budget"):
            campaign.spend(150.0)
        
        # Budget should be unchanged
        assert campaign.budget_spent_usd == 0.0
    
    def test_spend_exact_budget(self):
        """Test spending exactly the budget."""
        goal = MockGoal()
        campaign = Campaign(goal, budget_total_usd=100.0)
        
        campaign.spend(100.0)
        assert campaign.budget_remaining_usd == 0.0
        
        # Should not be able to spend more
        with pytest.raises(ValueError):
            campaign.spend(0.01)
    
    def test_low_budget_warning(self):
        """Test that low budget triggers warning."""
        goal = MockGoal()
        campaign = Campaign(goal, budget_total_usd=1000.0)
        
        # Spend 91% of budget
        campaign.spend(910.0)
        
        # Next spend should trigger warning (< 10% remaining)
        with pytest.warns(UserWarning, match="Low budget warning"):
            campaign.spend(1.0)
    
    def test_unlimited_budget_never_runs_out(self):
        """Test that unlimited budget never raises errors."""
        goal = MockGoal()
        campaign = Campaign(goal)  # Unlimited budget
        
        # Should be able to spend arbitrarily large amounts
        campaign.spend(1e10)
        campaign.spend(1e10)
        
        assert campaign.budget_remaining_usd == float('inf')


if __name__ == "__main__":
    pytest.main([__file__, "-vv"])
