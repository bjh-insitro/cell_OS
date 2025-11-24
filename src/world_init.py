"""
world_init.py

Helpers to build a LabWorldModel populated with basic static knowledge
(cell lines, workflows, pricing) plus an initial Phase 0 campaign.
"""

from __future__ import annotations

from typing import List

import pandas as pd

from src.lab_world_model import LabWorldModel, Campaign
from src.inventory import Inventory


def _default_cell_lines_table() -> pd.DataFrame:
    """
    Minimal static table of cell line metadata for Phase 0 / sandbox use.

    You can expand this later or load it from a CSV or database.
    """
    rows: List[dict] = [
        {
            "cell_line": "U2OS",
            "species": "human",
            "tissue": "bone osteosarcoma",
            "doubling_time_h": 24.0,
            "default_vessel": "plate_96",
            "preferred_dissociation": "trypsin",
        },
        {
            "cell_line": "HepG2",
            "species": "human",
            "tissue": "liver hepatocellular carcinoma",
            "doubling_time_h": 30.0,
            "default_vessel": "plate_96",
            "preferred_dissociation": "trypsin",
        },
        {
            "cell_line": "A549",
            "species": "human",
            "tissue": "lung adenocarcinoma",
            "doubling_time_h": 24.0,
            "default_vessel": "plate_96",
            "preferred_dissociation": "trypsin",
        },
        {
            "cell_line": "293T",
            "species": "human",
            "tissue": "kidney (HEK293T)",
            "doubling_time_h": 20.0,
            "default_vessel": "plate_96",
            "preferred_dissociation": "trypsin",
        },
    ]
    return pd.DataFrame(rows)


def _default_workflows_table() -> pd.DataFrame:
    """
    Minimal workflows catalog.

    Each row describes a workflow id and its rough cost. You can later
    generate this from src.workflows / src.unit_ops instead of hardcoding.
    """
    rows = [
        {
            "workflow_id": "WF_PHASE0_DR_V1",
            "name": "Phase 0 Viability Dose Response",
            "description": "Seed cells, dose compounds, measure viability readout.",
            "estimated_cost_usd": 50.0,  # ballpark per 96-well plate, tune later
        }
    ]
    return pd.DataFrame(rows)


def _pricing_table_from_inventory(pricing_yaml_path: str) -> pd.DataFrame:
    """
    Use Inventory + pricing.yaml to build a flat pricing table.
    """
    inv = Inventory(pricing_yaml_path)
    return inv.to_dataframe()


def build_default_world(pricing_yaml_path: str = "data/raw/pricing.yaml") -> LabWorldModel:
    """
    Construct a LabWorldModel with:
      - basic cell line metadata
      - a minimal workflows catalog
      - pricing from pricing.yaml
      - a single Phase 0 campaign definition
    """
    cell_lines_df = _default_cell_lines_table()
    workflows_df = _default_workflows_table()
    pricing_df = _pricing_table_from_inventory(pricing_yaml_path)

    world = LabWorldModel.from_static_tables(
        cell_lines=cell_lines_df,
        workflows=workflows_df,
        pricing=pricing_df,
        assays=None,  # fill this in later when you have a clean assay table
    )

    # Register a canonical Phase 0 campaign
    phase0_campaign = Campaign(
        id="PHASE0_SANDBOX",
        name="Phase 0 Dose Response Sandbox",
        objective="Learn viability dose-response curves for canonical stressors",
        primary_readout="viability",
        workflows=["WF_PHASE0_DR_V1"],
        metadata={
            "notes": "Initial sandbox campaign used to bootstrap the OS.",
        },
    )

    world.add_campaign(phase0_campaign)

    return world
