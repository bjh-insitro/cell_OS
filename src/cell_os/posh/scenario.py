from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class POSHScenario:
    """Canonical configuration for a POSH stress screen scenario."""

    name: str
    cell_lines: List[str]
    genes: int
    guides_per_gene: int
    coverage_cells_per_gene_per_bank: int
    banks_per_line: int
    moi_target: float
    moi_tolerance: float
    viability_min: float
    segmentation_min: float
    stress_signal_min: float
    budget_max: float
    
    # Optional fields
    genes_list: Optional[List[str]] = None
    design_rules: Optional[dict] = None
    vendor_format: Optional[str] = None

    @classmethod
    def from_yaml(cls, path: str | Path) -> "POSHScenario":
        """Load a scenario definition from a YAML file."""
        path = Path(path)
        cfg = yaml.safe_load(path.read_text())

        return cls(
            name=cfg["name"],
            cell_lines=cfg["cell_lines"],
            genes=cfg["library"]["genes"],
            guides_per_gene=cfg["library"]["guides_per_gene"],
            coverage_cells_per_gene_per_bank=cfg["coverage"]["cells_per_gene_per_bank"],
            banks_per_line=cfg["coverage"]["banks_per_line"],
            moi_target=cfg["moi"]["target"],
            moi_tolerance=cfg["moi"]["tolerance"],
            viability_min=cfg["stress_window"]["viability_min"],
            segmentation_min=cfg["stress_window"]["segmentation_min"],
            stress_signal_min=cfg["stress_window"]["stress_signal_min"],
            budget_max=cfg["budget"]["max_total_cost_usd"],
            genes_list=cfg.get("genes_list"),
            design_rules=cfg.get("design_rules"),
            vendor_format=cfg.get("vendor_format"),
        )



__all__ = ["POSHScenario"]
