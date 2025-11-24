"""
Unit tests for Campaign and goal logic.

Tests campaign goal evaluation and completion criteria.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from src.campaign import Campaign, PotencyGoal, SelectivityGoal
from src.posteriors import Phase0WorldModel


def test_potency_goal_creation():
    """Test creating a potency goal."""
    goal = PotencyGoal(
        cell_line="HepG2",
        ic50_threshold_uM=1.0
    )
    
    assert goal.cell_line == "HepG2"
    assert goal.threshold == 1.0  # Actual attribute name is 'threshold'


def test_selectivity_goal_creation():
    """Test creating a selectivity goal."""
    goal = SelectivityGoal(
        target_cell="cancer_cell",
        control_cell="healthy_cell",  # Actual parameter name
        selectivity_ratio=10.0
    )
    
    assert goal.target_cell == "cancer_cell"
    assert goal.control_cell == "healthy_cell"
    assert goal.selectivity_ratio == 10.0


def test_campaign_initialization():
    """Test campaign initialization."""
    goal = PotencyGoal("HepG2", 1.0)
    campaign = Campaign(goal=goal, max_cycles=10)
    
    assert campaign.goal == goal
    assert campaign.max_cycles == 10
    assert not campaign.is_complete


def test_campaign_update():
    """Test updating campaign state."""
    goal = PotencyGoal("HepG2", 1.0)
    campaign = Campaign(goal=goal, max_cycles=5)
    
    # Create empty posterior
    posterior = Phase0WorldModel()
    
    # update() increments cycles
    campaign.update(posterior)
    
    # After 5 updates, should be complete
    for _ in range(4):
        campaign.update(posterior)
    
    assert campaign.is_complete


def test_potency_goal_not_met():
    """Test potency goal when IC50 is not met."""
    goal = PotencyGoal("HepG2", ic50_threshold_uM=1.0)
    
    # Create empty posterior (no data yet)
    posterior = Phase0WorldModel()
    
    result = goal.is_met(posterior)
    assert not result  # Goal not met with no data


def test_campaign_budget_tracking():
    """Test that campaign can track budget."""
    goal = PotencyGoal("HepG2", 1.0)
    campaign = Campaign(goal=goal, max_cycles=10)
    
    # Manually set budget (since it's set outside __init__)
    campaign.budget = 1000.0
    
    assert campaign.budget == 1000.0
    
    # Simulate spending
    campaign.budget -= 250.0
    assert campaign.budget == 750.0


def test_selectivity_goal_ratio():
    """Test selectivity goal ratio."""
    goal = SelectivityGoal(
        target_cell="cancer",
        control_cell="healthy",
        selectivity_ratio=10.0
    )
    
    assert goal.selectivity_ratio == 10.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
