"""
reporting.py

Generates a human-readable 'Mission Log' explaining the agent's decisions.
"""

import os
import pandas as pd
from src.schema import Phase0WorldModel

class MissionLogger:
    def __init__(self, log_path: str = "results/mission_log.md"):
        self.log_path = log_path
        self._init_log()

    def _init_log(self):
        """Create the log file with a header if it doesn't exist."""
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        if not os.path.exists(self.log_path):
            with open(self.log_path, "w") as f:
                f.write("# Mission Log\n\n")
                f.write("Chronicles of the Autonomous Cell Biology Agent.\n\n")

    def log_cycle(
        self,
        cycle_num: int,
        world_model: Phase0WorldModel,
        selected: pd.DataFrame,
        candidates: pd.DataFrame
    ):
        """
        Append a report for a single cycle.
        """
        with open(self.log_path, "a") as f:
            f.write(f"## Cycle {cycle_num}\n\n")
            
            # 1. Model Status
            n_models = len(world_model.gp_models)
            f.write(f"**Model Status**: Fit {n_models} GP models.\n\n")
            
            # 2. Decision Rationale (The "Why")
            f.write("### Decision Rationale\n")
            f.write("The agent evaluated uncertainty across all conditions:\n\n")
            
            # Group candidates by slice and get max score
            summary = (
                candidates.groupby(["cell_line", "compound"])["priority_score"]
                .max()
                .reset_index()
                .sort_values("priority_score", ascending=False)
            )
            
            f.write("| Cell Line | Compound | Max Uncertainty |\n")
            f.write("|---|---|---|\n")
            for _, row in summary.iterrows():
                f.write(f"| {row['cell_line']} | {row['compound']} | {row['priority_score']:.4f} |\n")
            f.write("\n")
            
            # 3. Investment
            f.write("### Investment Strategy\n")
            investment = selected.groupby(["cell_line", "compound"]).size().reset_index(name="count")
            total = len(selected)
            
            for _, row in investment.iterrows():
                pct = (row['count'] / total) * 100
                f.write(f"- **{row['cell_line']} {row['compound']}**: {row['count']} experiments ({pct:.0f}%)\n")
            
            f.write("\n---\n\n")
            
        print(f"  -> Appended to Mission Log: {self.log_path}")
