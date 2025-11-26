"""
Tests for Resource Accounting.
"""

import pytest
import pandas as pd
from cell_os.lab_world_model.resource_accounting import ResourceAccounting
from cell_os.lab_world_model.resource_costs import ResourceCosts

@pytest.fixture
def mock_pricing():
    return pd.DataFrame([
        {"resource_id": "res_a", "unit_price_usd": 10.0},
        {"resource_id": "res_b", "unit_price_usd": 0.5},
        {"resource_id": "res_c", "unit_price_usd": 100.0},
    ])

@pytest.fixture
def accounting(mock_pricing):
    costs = ResourceCosts(pricing=mock_pricing)
    return ResourceAccounting(resource_costs=costs)

def test_calculate_cost(accounting):
    assert accounting.calculate_cost("res_a", 5) == 50.0
    assert accounting.calculate_cost("res_b", 10) == 5.0
    assert accounting.calculate_cost("unknown", 10) == 0.0

def test_aggregate_costs(accounting):
    log = [
        {"resource_id": "res_a", "quantity": 2},  # 20.0
        {"resource_id": "res_b", "quantity": 4},  # 2.0
        {"resource_id": "res_a", "quantity": 1},  # 10.0
        {"resource_id": "res_c", "quantity": 0.1}, # 10.0
        {"resource_id": "unknown", "quantity": 100}, # 0.0
    ]
    
    result = accounting.aggregate_costs(log)
    
    assert result["total_cost_usd"] == 42.0
    assert result["breakdown"]["res_a"] == 30.0
    assert result["breakdown"]["res_b"] == 2.0
    assert result["breakdown"]["res_c"] == 10.0
