"""
Integration test for Agent Persistence.
Verifies that the AutonomousTitrationAgent can save state and resume after interruption.
"""
import os
import pytest
import os
import sys
import pytest
import shutil

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from core.experiment_db import ExperimentDB
from cell_os.titration_loop import AutonomousTitrationAgent
from cell_os.posh.lv_moi import ScreenConfig
from cell_os.budget_manager import BudgetConfig

DB_PATH = "data/experiments.db"

def _get_db_connection():
    """Helper to get a connection for test verification."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@pytest.fixture
def clean_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    yield
    # Cleanup after test
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_agent_persistence(clean_db):
    # Setup
    config = ScreenConfig(max_titration_rounds=2)
    prices = BudgetConfig() # Mock prices
    
    # 1. Run Agent for Cell Line A (First Run)
    agent1 = AutonomousTitrationAgent(config, prices, experiment_id="TEST_EXP_001")
    
    targets_1 = [
        {"name": "CellLine_A", "true_params": {"titer": 10000, "alpha": 0.9}},
        {"name": "CellLine_B", "true_params": {"titer": 20000, "alpha": 0.8}}
    ]
    
    # Run only for CellLine_A then stop (simulate crash/stop by only passing list of 1)
    # Actually, let's just run the full thing but check intermediate state if possible.
    # Or better: Run for A, check DB. Then Run for B, check DB.
    
    print("\n--- RUN 1: CellLine_A ---")
    agent1.run_campaign([targets_1[0]])
    
    # Verify DB has state
    conn = _get_db_connection()
    cursor = conn.cursor()
    
    # Check Experiment
    cursor.execute("SELECT * FROM experiments WHERE experiment_id='TEST_EXP_001'")
    assert cursor.fetchone() is not None
    
    # Check Agent State
    cursor.execute("SELECT state_json FROM agent_state WHERE agent_id='TitrationAgent_v1'")
    state_row = cursor.fetchone()
    assert state_row is not None
    assert "CellLine_A" in state_row['state_json']
    
    # Check Results Logged
    cursor.execute("SELECT count(*) FROM titration_results WHERE cell_line='CellLine_A'")
    count_a = cursor.fetchone()[0]
    assert count_a > 0
    
    conn.close()
    
    # 2. Run Agent again (Resume)
    print("\n--- RUN 2: Resume (Should skip A, run B) ---")
    agent2 = AutonomousTitrationAgent(config, prices, experiment_id="TEST_EXP_001")
    
    # Pass both A and B. A should be skipped.
    reports = agent2.run_campaign(targets_1)
    
    # We expect reports only for B (since A is skipped, it returns no report for it? 
    # Wait, the current logic returns reports for *run* lines. 
    # If skipped, it doesn't add to 'reports' list in the loop.
    
    assert len(reports) == 1
    assert reports[0].cell_line == "CellLine_B"
    
    # Verify DB again
    conn = _get_db_connection()
    cursor = conn.cursor()
    
    # Check Agent State has both
    cursor.execute("SELECT state_json FROM agent_state WHERE agent_id='TitrationAgent_v1'")
    state_row = cursor.fetchone()
    assert "CellLine_A" in state_row['state_json']
    assert "CellLine_B" in state_row['state_json']
    
    conn.close()
