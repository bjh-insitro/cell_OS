"""
State Manager for cell_OS Agents.

Provides a high-level API for agents to save/load their state and log results.
Now uses the unified ExperimentDB.
"""
from typing import Dict, Any, Optional
import uuid
from core.experiment_db import ExperimentDB

class StateManager:
    def __init__(self, experiment_id: str = None, db_path: str = "data/experiments.db"):
        self.db = ExperimentDB(db_path=db_path)
        if not experiment_id:
            experiment_id = f"EXP_{uuid.uuid4().hex[:8]}"
        
        self.db.save_experiment(experiment_id, "Experiment " + experiment_id)
        self.experiment_id = experiment_id

    def save_state(self, agent_id: str, state: Dict[str, Any]):
        """Persist agent state to DB."""
        self.db.save_agent_state(agent_id, self.experiment_id, state)

    def load_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Load agent state from DB."""
        return self.db.load_agent_state(agent_id)

    def log_result(self, cell_line: str, round_num: int, vol: float, bfp: float, cost: float):
        """Log a specific data point from the experiment."""
        self.db.log_titration_data(self.experiment_id, cell_line, round_num, vol, bfp, cost)
