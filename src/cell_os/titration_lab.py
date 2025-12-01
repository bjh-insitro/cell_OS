"""
Titration lab simulation helpers.

Encapsulates the deterministic lab step generation and cost calculations that
AutonomousTitrationAgent relies on for mock runs.
"""

from __future__ import annotations

from typing import Dict, List, TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from cell_os.budget_manager import BudgetConfig


class MockTitrationLab:
    """Generates synthetic titration data and associated cost estimates."""

    def __init__(self, budget_config: "BudgetConfig"):
        self.prices = budget_config

    def run_step(self, cell_line: str, volumes: List[float], true_params: Dict) -> pd.DataFrame:
        """Produce synthetic BFP fractions for a batch of lentiviral doses."""
        rows = []
        titer = true_params["titer"]
        alpha = true_params["alpha"]

        for volume in volumes:
            moi = (volume * titer) / 100000
            p_bfp = alpha * (1.0 - np.exp(-moi))
            noise = np.random.normal(0, 0.03)
            if cell_line == "HepG2" and volume < 1.0:
                noise += np.random.normal(0, 0.02)
            obs = np.clip(p_bfp + noise, 0.001, 0.999)
            rows.append({"volume_ul": volume, "fraction_bfp": obs})

        return pd.DataFrame(rows)

    def calculate_round_cost(self, df_round: pd.DataFrame) -> float:
        """Estimate reagent + virus cost for a titration round."""
        wells = len(df_round)
        virus_used = df_round["volume_ul"].sum()

        cost_reagents_flow = (
            wells * self.prices.reagent_cost_per_well
            + (wells * self.prices.mins_per_sample_flow) / 60.0 * self.prices.flow_rate_per_hour
        )

        cost_virus = virus_used * self.prices.virus_price
        return cost_reagents_flow + cost_virus
