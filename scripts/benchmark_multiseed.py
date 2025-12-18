#!/usr/bin/env python3
"""
Multi-seed benchmark for epistemic agent with gate KPI extraction.

v0.4.2: Tracks gate attainment, rel_width tightness, and df efficiency.

Usage:
    python scripts/benchmark_multiseed.py --seeds 10 --budget 384 --cycles 20
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any

# Import reusable KPI extraction
from benchmark_utils import extract_all_kpis


def run_single_seed(seed: int, budget: int, cycles: int, log_dir: Path) -> Dict[str, Any]:
    """Run epistemic agent for a single seed."""
    print(f"\n{'='*60}")
    print(f"Running seed {seed}")
    print(f"{'='*60}")

    cmd = [
        sys.executable,
        "scripts/run_epistemic_agent.py",
        "--seed", str(seed),
        "--budget", str(budget),
        "--cycles", str(cycles),
        "--log-dir", str(log_dir),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    # Find the JSON file for this run (most recent in log_dir)
    json_files = sorted(log_dir.glob("run_*.json"), key=lambda p: p.stat().st_mtime)
    
    if not json_files:
        return {
            "seed": seed,
            "success": False,
            "error": "No JSON output found",
            "exit_code": result.returncode,
        }

    run_json_path = json_files[-1]

    # Extract all KPIs using reusable utils
    kpis = extract_all_kpis(run_json_path)

    return {
        "seed": seed,
        "success": result.returncode == 0,
        "exit_code": result.returncode,
        **kpis,
    }


def print_summary(results: List[Dict[str, Any]]):
    """Print aggregate statistics."""
    print("\n" + "="*60)
    print("AGGREGATE STATISTICS")
    print("="*60)

    n_total = len(results)
    n_success = sum(1 for r in results if r["success"])
    n_gate_earned = sum(1 for r in results if r.get("gate_earned", False))

    print(f"Total runs: {n_total}")
    print(f"Successful: {n_success}/{n_total} ({100*n_success/n_total:.0f}%)")
    print(f"Gate earned: {n_gate_earned}/{n_total} ({100*n_gate_earned/n_total:.0f}%)")

    # Gate statistics (for runs that earned gate)
    gate_runs = [r for r in results if r.get("gate_earned", False)]
    
    if gate_runs:
        print("\n" + "-"*60)
        print("GATE STATISTICS (runs that earned gate)")
        print("-"*60)

        rel_widths = [r["rel_width_final"] for r in gate_runs if r.get("rel_width_final") is not None]
        dfs = [r["df_final"] for r in gate_runs if r.get("df_final") is not None]
        slacks = [r["gate_slack"] for r in gate_runs if r.get("gate_slack") is not None]
        cycles_to_gate = [r["cycles_to_gate"] for r in gate_runs if r.get("cycles_to_gate") is not None]

        if rel_widths:
            print(f"Rel width: mean={sum(rel_widths)/len(rel_widths):.4f}, "
                  f"min={min(rel_widths):.4f}, max={max(rel_widths):.4f}")
        if dfs:
            print(f"DF: mean={sum(dfs)/len(dfs):.0f}, "
                  f"min={min(dfs)}, max={max(dfs)}")
        if slacks:
            print(f"Gate slack: mean={sum(slacks)/len(slacks):.4f}, "
                  f"min={min(slacks):.4f}, max={max(slacks):.4f}")
        if cycles_to_gate:
            print(f"Cycles to gate: mean={sum(cycles_to_gate)/len(cycles_to_gate):.1f}, "
                  f"min={min(cycles_to_gate)}, max={max(cycles_to_gate)}")

    # Integrity warnings
    n_warnings = sum(1 for r in results if r.get("integrity_warnings"))
    if n_warnings > 0:
        print(f"\n⚠️  {n_warnings} runs had integrity warnings")


def main():
    parser = argparse.ArgumentParser(
        description="Multi-seed benchmark for epistemic agent (v0.4.2)"
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=5,
        help="Number of seeds to run (default: 5)",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=384,
        help="Well budget per run (default: 384)",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=20,
        help="Max cycles per run (default: 20)",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="results/epistemic_agent",
        help="Directory for logs (default: results/epistemic_agent)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="benchmark_results.json",
        help="Output JSON file for results (default: benchmark_results.json)",
    )

    args = parser.parse_args()
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Run all seeds
    results = []
    for seed in range(args.seeds):
        result = run_single_seed(seed, args.budget, args.cycles, log_dir)
        results.append(result)

    # Print summary
    print_summary(results)

    # Save results
    output_path = Path(args.output)
    with open(output_path, 'w') as f:
        json.dump({
            "benchmark_config": {
                "n_seeds": args.seeds,
                "budget": args.budget,
                "cycles": args.cycles,
            },
            "results": results,
        }, f, indent=2)

    print(f"\n✓ Results saved to {output_path}")


if __name__ == "__main__":
    main()
