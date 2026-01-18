#!/usr/bin/env python3
"""
Phase 0 Go/No-Go Full Simulation Driver

Run: python scripts/run_gonogo_sim.py
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from cell_os.cell_thalamus.gonogo_analysis import (
    build_plate_effects,
    generate_gonogo_report,
    run_all_assertions,
)
from cell_os.cell_thalamus.menadione_phase0_runner import run_menadione_simulation
from cell_os.database.cell_thalamus_db import CellThalamusDB


def parse_plate_id(plate_id: str) -> dict:
    """Extract passage, template from plate_id naming convention."""
    # MEN_Psg1_T24h_P1_Operator_A
    m = re.match(r"MEN_Psg(\d+)_T(\d+)h_P(\d+)_Operator_(\w+)", plate_id)
    if m:
        return {
            "passage": int(m.group(1)),
            "timepoint_h": float(m.group(2)),
            "template": int(m.group(3)),
            "operator": m.group(4),
        }
    return {"passage": 1, "template": 1}


def load_df_wells(db_path: str, design_id: str) -> pd.DataFrame:
    """Load well data and add passage/template columns."""
    db = CellThalamusDB(db_path=db_path)
    rows = db.get_results(design_id)
    db.close()

    df = pd.DataFrame(rows)

    # Parse passage/template from plate_id
    parsed = df["plate_id"].apply(parse_plate_id).apply(pd.Series)
    df["passage"] = parsed["passage"].astype("category")
    df["template"] = parsed["template"].astype("category")

    return df


def run_single_simulation(
    variance_mode: str = "realistic",
    workers: int = 4,
    output_dir: str = "data/gonogo_runs",
) -> dict:
    """
    Run a single simulation and generate go/no-go report.

    Args:
        variance_mode: "deterministic", "conservative", or "realistic"
        workers: parallel workers
        output_dir: where to save artifacts

    Returns:
        Report dict with decision, metrics, paths
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(output_dir) / f"{variance_mode}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    db_path = str(run_dir / "simulation.db")

    print(f"=== Running {variance_mode} simulation ===")
    print(f"Output: {run_dir}")

    # Run simulation
    design_id = run_menadione_simulation(
        mode="full",
        workers=workers,
        db_path=db_path,
        quiet=True,
        variance_mode=variance_mode,
    )

    print(f"Design ID: {design_id}")

    # Load data
    df_wells = load_df_wells(db_path, design_id)
    print(f"Loaded {len(df_wells)} wells")

    # Save raw extract
    df_wells.to_parquet(run_dir / "df_wells.parquet")
    print("Saved df_wells.parquet")

    # Run assertions
    print("\n--- Qualitative Assertions ---")
    assertion_results = run_all_assertions(df_wells)
    for name, passed in assertion_results.items():
        if not name.endswith("_error"):
            status = "PASS" if passed else "FAIL"
            print(f"  {status} {name}")
            if not passed and f"{name}_error" in assertion_results:
                print(f"      {assertion_results[f'{name}_error']}")

    # Generate report
    report = generate_gonogo_report(
        df_wells=df_wells,
        design_id=design_id,
        output_dir=str(run_dir),
    )

    # Add assertion results to report
    report["assertions"] = assertion_results
    report["variance_mode"] = variance_mode
    report["workers"] = workers

    # Print decision
    print(f"\n=== DECISION: {report['decision']} ===")
    if report["operating_point"]:
        op = report["operating_point"]
        print(f"Operating point: {op['dose_uM']} uM @ {op['timepoint_h']}h")

    print("\nCriteria:")
    for crit, passed in report["criteria_results"].items():
        status = "PASS" if passed else "FAIL"
        print(f"  {status} {crit}")

    print("\nMetrics:")
    for k, v in report["metrics"].items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for k2, v2 in v.items():
                if isinstance(v2, float):
                    print(f"    {k2}: {v2:.4f}")
                else:
                    print(f"    {k2}: {v2}")
        else:
            if isinstance(v, float):
                print(f"  {k}: {v:.4f}")
            else:
                print(f"  {k}: {v}")

    return report


def run_stability_matrix(workers: int = 4, output_dir: str = "data/gonogo_runs"):
    """
    Run small matrix to check decision stability.

    Tests:
    - variance_mode: deterministic, realistic
    - Workers: 1, workers (checks parallelism doesn't change results)
    """
    print("\n" + "=" * 60)
    print("STABILITY MATRIX")
    print("=" * 60)

    results = []

    for variance_mode in ["deterministic", "realistic"]:
        for n_workers in [1, workers]:
            print(f"\n>>> {variance_mode} / {n_workers} workers")
            print("-" * 40)
            report = run_single_simulation(
                variance_mode=variance_mode,
                workers=n_workers,
                output_dir=output_dir,
            )
            results.append(
                {
                    "variance_mode": variance_mode,
                    "workers": n_workers,
                    "decision": report["decision"],
                    "operating_point": report.get("operating_point"),
                    "dose_eta_sq": report["metrics"]["eta_squared"]["dose_eta_sq"],
                    "template_eta_sq": report["metrics"]["eta_squared"].get("template_eta_sq", 0),
                    "passage_eta_sq": report["metrics"]["eta_squared"].get("passage_eta_sq", 0),
                    "all_assertions_pass": all(
                        v for k, v in report["assertions"].items() if not k.endswith("_error")
                    ),
                }
            )

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(
        f"{'Mode':<15} {'W':>3} {'Decision':>8} {'Op Point':>12} {'dose_eta':>10} {'tmpl_eta':>10} {'pass_eta':>10} {'Asserts':>8}"
    )
    print("-" * 80)
    for r in results:
        op = r["operating_point"]
        op_str = f"{op['dose_uM']:.0f}uM/{op['timepoint_h']:.0f}h" if op else "N/A"
        asserts = "PASS" if r["all_assertions_pass"] else "FAIL"
        print(
            f"{r['variance_mode']:<15} {r['workers']:>3} {r['decision']:>8} {op_str:>12} {r['dose_eta_sq']:>10.4f} {r['template_eta_sq']:>10.4f} {r['passage_eta_sq']:>10.4f} {asserts:>8}"
        )

    # Check for nondeterminism leak
    print("\n" + "-" * 60)
    det_results = [r for r in results if r["variance_mode"] == "deterministic"]
    if len(det_results) == 2:
        if det_results[0]["operating_point"] != det_results[1]["operating_point"]:
            print("WARNING: Deterministic mode produced different operating points!")
            print("         This indicates a nondeterminism leak in the simulation.")
        else:
            print("OK: Deterministic mode is stable across worker counts.")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 0 Go/No-Go simulation driver")
    parser.add_argument(
        "--mode",
        choices=["single", "matrix"],
        default="single",
        help="Run single simulation or stability matrix",
    )
    parser.add_argument(
        "--variance",
        choices=["deterministic", "conservative", "realistic"],
        default="realistic",
        help="Variance mode for single run",
    )
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--output", default="data/gonogo_runs", help="Output directory")
    args = parser.parse_args()

    if args.mode == "single":
        run_single_simulation(
            variance_mode=args.variance,
            workers=args.workers,
            output_dir=args.output,
        )
    else:
        run_stability_matrix(workers=args.workers, output_dir=args.output)
