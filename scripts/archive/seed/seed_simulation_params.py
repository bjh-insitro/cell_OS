#!/usr/bin/env python3
"""
Seed simulation_params.db from the legacy YAML fixture.

Usage:
    python scripts/seed_simulation_params.py \
        --yaml data/simulation_parameters.yaml \
        --db data/simulation_params.db \
        [--overwrite]
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

import yaml

from cell_os.database.repositories.simulation_params import (
    SimulationParamsRepository,
    CellLineSimParams,
    CompoundSensitivity,
)


def load_yaml(path: Path) -> Dict[str, Any]:
    """Load the YAML config file."""
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def clear_tables(repo: SimulationParamsRepository) -> None:
    """Remove existing seeded data."""
    repo._execute("DELETE FROM cell_line_params", ())
    repo._execute("DELETE FROM compound_sensitivity", ())
    repo._execute("DELETE FROM default_params", ())


def table_has_column(repo: SimulationParamsRepository, table: str, column: str) -> bool:
    """Return True if the SQLite table contains the specified column."""
    rows = repo._fetch_all(f"PRAGMA table_info({table})")
    return any(row.get("name") == column for row in rows)


def seed_cell_lines(repo: SimulationParamsRepository, configs: Dict[str, Any]) -> None:
    """Insert cell line simulation parameters."""
    for cell_line, params in configs.items():
        payload = CellLineSimParams(
            cell_line_id=cell_line,
            doubling_time_h=float(params.get("doubling_time_h", 24.0)),
            max_confluence=float(params.get("max_confluence", 0.9)),
            max_passage=int(params.get("max_passage", 30)),
            senescence_rate=float(params.get("senescence_rate", 0.01)),
            seeding_efficiency=float(params.get("seeding_efficiency", 0.85)),
            passage_stress=float(params.get("passage_stress", 0.02)),
            cell_count_cv=float(params.get("cell_count_cv", 0.10)),
            viability_cv=float(params.get("viability_cv", 0.02)),
            biological_cv=float(params.get("biological_cv", 0.05)),
            coating_required=bool(params.get("coating_required", False)),
        )
        repo.add_cell_line_params(payload)


def seed_compounds(repo: SimulationParamsRepository, data: Dict[str, Any]) -> None:
    """Insert compound sensitivity rows."""
    for compound, entries in data.items():
        hill_slope = float(entries.get("hill_slope", 1.0))
        for cell_line, value in entries.items():
            if cell_line in {"hill_slope", "description", "cellrox_params", "segmentation_params"}:
                continue
            if not isinstance(value, (int, float)):
                continue
            payload = CompoundSensitivity(
                compound_name=compound,
                cell_line_id=cell_line,
                ic50_um=float(value),
                hill_slope=hill_slope,
                source="yaml_fixture",
            )
            repo.add_compound_sensitivity(payload)


def seed_defaults(repo: SimulationParamsRepository, defaults: Dict[str, Any]) -> None:
    """Insert default parameters."""
    has_updated_at = table_has_column(repo, "default_params", "updated_at")
    for name, value in defaults.items():
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if has_updated_at:
            repo.set_default_param(name, numeric, description="seeded from YAML")
        else:
            repo._execute(
                "INSERT OR REPLACE INTO default_params (param_name, param_value, description) VALUES (?, ?, ?)",
                (name, numeric, "seeded from YAML"),
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed simulation params database from YAML.")
    parser.add_argument("--yaml", default="data/simulation_parameters.yaml", help="Path to YAML config.")
    parser.add_argument("--db", default="data/simulation_params.db", help="Path to SQLite DB.")
    parser.add_argument("--overwrite", action="store_true", help="Clear existing tables before seeding.")
    args = parser.parse_args()

    yaml_path = Path(args.yaml)
    if not yaml_path.exists():
        raise SystemExit(f"YAML file not found: {yaml_path}")

    repo = SimulationParamsRepository(args.db)
    configs = load_yaml(yaml_path)

    if args.overwrite:
        clear_tables(repo)

    seed_cell_lines(repo, configs.get("cell_lines", {}))
    seed_compounds(repo, configs.get("compound_sensitivity", {}))
    seed_defaults(repo, configs.get("defaults", {}))

    summary = {
        "cell_lines": len(configs.get("cell_lines", {})),
        "compounds": len(configs.get("compound_sensitivity", {})),
        "defaults": len(configs.get("defaults", {})),
    }
    print(f"Seeded simulation parameters into {args.db}: {summary}")


if __name__ == "__main__":
    main()
