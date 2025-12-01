"""
Command-Line Interface for Autonomous Titration Campaigns.

Exposes the same functionality as the legacy `cli/run_campaign.py` script,
but is importable so it can be wired up as a console entry point.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Optional

import yaml

from cell_os.budget_manager import BudgetConfig
from cell_os.html_reporter import generate_html_report
from cell_os.posh_lv_moi import ScreenConfig
from cell_os.titration_loop import AutonomousTitrationAgent


def load_config(config_path: str) -> Dict:
    """Load YAML configuration file."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


def run_campaign_from_config(config: Dict, experiment_id_override: Optional[str] = None):
    """Run a titration campaign based on the provided configuration."""

    # 1. Extract Configuration
    experiment_id = experiment_id_override or config.get("experiment_id", "DEFAULT_EXP")
    cell_lines = config["cell_lines"]
    # Convert cell line config to true_params for agent
    for cl in cell_lines:
        # Populate true_params from legacy fields if present
        titer = cl.get("true_titer")
        alpha = cl.get("true_alpha")
        if titer is not None and alpha is not None:
            cl["true_params"] = {"titer": titer, "alpha": alpha}
        else:
            cl.setdefault("true_params", {})

    # 2. Build ScreenConfig
    sc = config["screen_config"]
    screen_config = ScreenConfig(
        max_titration_rounds=sc.get("max_titration_rounds", 5),
        num_guides=sc.get("num_guides", 1000),
        coverage_target=sc.get("coverage_target", 500),
        target_bfp=sc.get("target_bfp", 0.30),
        bfp_tolerance=tuple(sc.get("bfp_tolerance", [0.25, 0.35])),
        cell_counting_error=sc.get("cell_counting_error", 0.05),
        pipetting_error=sc.get("pipetting_error", 0.05),
    )

    # 3. Build BudgetConfig
    bc = config["budget"]
    budget_config = BudgetConfig(
        max_titration_budget_usd=bc.get("max_titration_budget_usd", 5000.0),
        reagent_cost_per_well=bc.get("reagent_cost_per_well", 2.50),
        mins_per_sample_flow=bc.get("mins_per_sample_flow", 3.0),
        flow_rate_per_hour=bc.get("flow_rate_per_hour", 120.0),
        virus_price=bc.get("virus_price", 0.15),
    )

    # 4. Initialize Agent
    agent = AutonomousTitrationAgent(
        config=screen_config, prices=budget_config, experiment_id=experiment_id
    )

    # 5. Run Campaign
    print(f"\n{'='*70}")
    print(f"Starting Campaign: {config.get('experiment_name', 'Unnamed')}")
    print(f"Experiment ID: {experiment_id}")
    print(f"Cell Lines: {[cl['name'] for cl in cell_lines]}")
    print(f"{'='*70}\n")

    reports = agent.run_campaign(cell_lines)

    # 6. Generate Outputs
    output_settings = config.get("output", {})
    results_dir = Path(output_settings.get("results_dir", "results/campaigns"))
    results_dir.mkdir(parents=True, exist_ok=True)

    if not reports:
        print("⚠️ No new reports generated; skipping HTML and CSV output.")
    else:
        if output_settings.get("generate_html_report", True):
            html_path = results_dir / f"{experiment_id}_report.html"
            print(f"\n📊 Generating HTML Report: {html_path}")
            # Pass screen_config as config, empty log_text for now, and no cost details
            generate_html_report(
                reports, screen_config, log_text="", costs=None, filename=html_path
            )

        if output_settings.get("save_csv", True):
            csv_path = results_dir / f"{experiment_id}_summary.csv"
            print(f"💾 Saving CSV Summary: {csv_path}")
            # TODO: Implement CSV export

    print(f"\n✅ Campaign Complete. Results saved to: {results_dir}")
    return reports


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an autonomous LV titration campaign.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  cell-os-run --config config/campaign_example.yaml
  cell-os-run --config my_config.yaml --experiment-id CUSTOM_001
        """,
    )

    parser.add_argument(
        "--config",
        "-c",
        required=True,
        help="Path to YAML configuration file",
    )

    parser.add_argument(
        "--experiment-id",
        "-e",
        help="Override the experiment ID from config",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load config and validate without running",
    )

    args = parser.parse_args(argv)

    # Load and validate config
    if not os.path.exists(args.config):
        print(f"❌ Error: Config file not found: {args.config}")
        return 1

    config = load_config(args.config)

    if args.dry_run:
        print(f"✅ Config loaded successfully from: {args.config}")
        print(f"   Experiment: {config.get('experiment_name', 'N/A')}")
        print(f"   Cell Lines: {len(config.get('cell_lines', []))}")
        return 0

    # Run campaign
    run_campaign_from_config(config, args.experiment_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())

