"""
Workflow Index module.
Stores metadata about available workflows.
"""

from __future__ import annotations
from typing import Optional
import pandas as pd
from dataclasses import dataclass, field

@dataclass
class WorkflowIndex:
    """
    Registry for workflow definitions.
    """
    workflows: pd.DataFrame = field(default_factory=pd.DataFrame)

    def get_workflow_row(self, workflow_id: str) -> Optional[pd.Series]:
        """
        Return the row in `workflows` corresponding to the given workflow id.

        Expects a column named "workflow_id" or "id".
        """
        if self.workflows.empty:
            return None

        key_col = None
        if "workflow_id" in self.workflows.columns:
            key_col = "workflow_id"
        elif "id" in self.workflows.columns:
            key_col = "id"

        if key_col is None:
            return None

        subset = self.workflows[self.workflows[key_col] == workflow_id]
        if subset.empty:
            return None

        return subset.iloc[0]

    def get_workflow_cost(self, workflow_id: str) -> Optional[float]:
        """
        Return an estimated cost for a workflow if available.

        This method assumes that `workflows` has either:
          - a column "estimated_cost_usd", or
          - a column "cost_usd"

        If neither is present or the row is missing, returns None.
        """
        row = self.get_workflow_row(workflow_id)
        if row is None:
            return None

        for col in ("estimated_cost_usd", "cost_usd"):
            if col in row.index and pd.notna(row[col]):
                try:
                    return float(row[col])
                except (TypeError, ValueError):
                    return None

        return None
