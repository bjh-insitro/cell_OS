"""
Cell Registry module.
Stores metadata for cell lines and assays.
"""

from __future__ import annotations
from typing import Optional
import pandas as pd
from dataclasses import dataclass, field

@dataclass
class CellRegistry:
    """
    Registry for static biological knowledge: cell lines and assays.
    """
    cell_lines: pd.DataFrame = field(default_factory=pd.DataFrame)
    assays: pd.DataFrame = field(default_factory=pd.DataFrame)

    def get_cell_line(self, cell_line: str) -> Optional[pd.Series]:
        """
        Return metadata for a single cell line as a row, if present.

        Expects `cell_lines` to have a column named "cell_line" or "id".
        Uses "cell_line" if present, otherwise falls back to "id".
        """
        if self.cell_lines.empty:
            return None

        key_col = None
        if "cell_line" in self.cell_lines.columns:
            key_col = "cell_line"
        elif "id" in self.cell_lines.columns:
            key_col = "id"

        if key_col is None:
            return None

        subset = self.cell_lines[self.cell_lines[key_col] == cell_line]
        if subset.empty:
            return None

        return subset.iloc[0]
