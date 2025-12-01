import csv
from pathlib import Path

import pytest
import yaml

from cell_os.cli import run_campaign as cli_module
from cell_os.posh_lv_moi import TitrationReport


def _write_config(tmp_path: Path, output_dir: Path, overrides=None) -> Path:
    config = {
        "experiment_id": "TEST_EXP",
        "experiment_name": "Unit Test Campaign",
        "cell_lines": [
            {"name": "TestLine", "true_titer": 100000, "true_alpha": 0.9},
        ],
        "screen_config": {
            "max_titration_rounds": 2,
            "num_guides": 100,
            "coverage_target": 50,
            "target_bfp": 0.3,
            "bfp_tolerance": [0.25, 0.35],
            "cell_counting_error": 0.01,
            "pipetting_error": 0.01,
        },
        "budget": {
            "max_titration_budget_usd": 1000.0,
            "reagent_cost_per_well": 1.0,
            "mins_per_sample_flow": 1.0,
            "flow_rate_per_hour": 60.0,
            "virus_price": 0.05,
        },
        "output": {
            "results_dir": str(output_dir),
            "generate_html_report": False,
            "save_csv": True,
        },
    }
    if overrides:
        config.update(overrides)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return config_path


def test_cli_dry_run(tmp_path):
    results_dir = tmp_path / "results"
    cfg_path = _write_config(tmp_path, results_dir)

    code = cli_module.main(["--config", str(cfg_path), "--dry-run"])

    assert code == 0
    assert not results_dir.exists()


def test_cli_live_generates_csv(tmp_path, monkeypatch):
    results_dir = tmp_path / "results_live"
    cfg_path = _write_config(tmp_path, results_dir)

    class DummyAgent:
        def __init__(self, config, prices, experiment_id):
            self.config = config
            self.prices = prices
            self.experiment_id = experiment_id

        def run_campaign(self, cell_lines):
            return [
                TitrationReport(
                    cell_line=line["name"],
                    status="GO",
                    rounds_run=1,
                    final_pos=0.95,
                    final_vol=1.23,
                    history_dfs=[],
                    model=None,
                    final_cost=123.45,
                )
                for line in cell_lines
            ]

    monkeypatch.setattr(cli_module, "AutonomousTitrationAgent", DummyAgent)

    code = cli_module.main(["--config", str(cfg_path)])
    assert code == 0

    csv_path = results_dir / "TEST_EXP_summary.csv"
    assert csv_path.exists()

    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    assert rows[0]["cell_line"] == "TestLine"
    assert rows[0]["status"] == "GO"
    assert float(rows[0]["final_cost_usd"]) == pytest.approx(123.45, rel=1e-6)
