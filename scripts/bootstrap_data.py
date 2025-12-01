#!/usr/bin/env python3
"""
Bootstrap local SQLite databases from the canonical YAML fixtures.

Runs both seed scripts so new clones have the latest cell-line protocols
and simulation parameters without manual sqlite3 edits.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_step(args: list[str]) -> None:
    """Execute a subprocess and stream output."""
    print(f"$ {' '.join(args)}")
    result = subprocess.run(args, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed local databases from YAML fixtures.")
    parser.add_argument(
        "--cell-lines-yaml",
        default="data/cell_lines.yaml",
        help="Path to the cell line YAML fixture.",
    )
    parser.add_argument(
        "--cell-lines-db",
        default="data/cell_lines.db",
        help="Cell line SQLite database path.",
    )
    parser.add_argument(
        "--sim-yaml",
        default="data/simulation_parameters.yaml",
        help="Path to the simulation parameter YAML fixture.",
    )
    parser.add_argument(
        "--sim-db",
        default="data/simulation_params.db",
        help="Simulation parameters SQLite database path.",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Do not pass --overwrite to the seed scripts.",
    )
    args = parser.parse_args()

    overwrite_flag: list[str] = [] if args.no_overwrite else ["--overwrite"]

    steps = [
        [
            sys.executable,
            "scripts/seed_cell_line_protocols.py",
            "--yaml",
            args.cell_lines_yaml,
            "--db",
            args.cell_lines_db,
            *overwrite_flag,
        ],
        [
            sys.executable,
            "scripts/seed_simulation_params.py",
            "--yaml",
            args.sim_yaml,
            "--db",
            args.sim_db,
            *overwrite_flag,
        ],
    ]

    for cmd in steps:
        run_step(cmd)

    print("✅ Databases bootstrapped.")


if __name__ == "__main__":
    main()
