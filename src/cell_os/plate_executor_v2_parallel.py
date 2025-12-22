"""
Plate Executor V2 Parallel: Corrected implementation with multiprocessing

Combines all correctness fixes from V2 with parallel execution for speed.
Expected: 384 wells in ~2-3 minutes on 32 CPUs (vs 15 minutes serial).
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from multiprocessing import Pool, cpu_count

from src.cell_os.plate_executor_v2 import (
    parse_plate_design_v2,
    validate_compounds,
    execute_well,
    flatten_result,
    ParsedWell
)
from src.cell_os.hardware.run_context import RunContext


def execute_well_worker(args: tuple) -> Dict[str, Any]:
    """
    Worker function for multiprocessing.

    Args:
        args: (ParsedWell, base_seed, run_context, plate_id)

    Returns:
        Result dictionary
    """
    pw, base_seed, run_context, plate_id = args
    return execute_well(pw, base_seed, run_context, plate_id)


def execute_plate_design_parallel(
    json_path: Path,
    seed: int = 42,
    output_dir: Optional[Path] = None,
    verbose: bool = True,
    workers: Optional[int] = None,
    auto_commit: bool = False
) -> Dict[str, Any]:
    """
    Execute full 384-well plate simulation with parallel processing.

    All correctness fixes from V2:
    - Per-well isolated simulation (fixes time bug)
    - Provocations applied to measurements
    - Realistic background wells
    - Robust compound validation

    Args:
        json_path: Path to JSON plate design
        seed: Random seed for reproducibility
        output_dir: Optional directory to save results
        verbose: Print progress messages
        workers: Number of parallel workers (None = auto-detect)
        auto_commit: If True, git commit and push results after successful execution

    Returns:
        Dictionary with results
    """
    if workers is None:
        workers = max(1, cpu_count() - 1)

    if verbose:
        print(f"{'='*70}")
        print(f"CAL_384 Plate Executor V2 - Parallel Mode")
        print(f"{'='*70}")
        print(f"\nLoading plate design: {json_path.name}")

    # Parse with validation
    parsed_wells, parse_metadata = parse_plate_design_v2(json_path)
    if verbose:
        print(f"✓ Parsed {len(parsed_wells)} wells")

    # Validate compounds
    validate_compounds(parsed_wells)
    if verbose:
        print(f"✓ Validated all compounds")

    # Summary statistics
    cell_lines = set(pw.cell_line for pw in parsed_wells if pw.cell_line != "NONE")
    treatments = set(pw.treatment for pw in parsed_wells)
    compounds = set(pw.reagent for pw in parsed_wells if pw.reagent != "DMSO")

    if verbose:
        print(f"\nPlate summary:")
        print(f"  Cell lines: {', '.join(sorted(cell_lines))}")
        print(f"  Compounds: {', '.join(sorted(compounds))}")
        print(f"  Treatments: {len(treatments)} unique")
        print(f"  Background wells: {len(parse_metadata['background_wells'])}")
        print(f"\nExecution mode: Parallel with {workers} workers")
        print(f"Seed: {seed}")

    # Create shared RunContext for plate-level batch effects
    run_context = RunContext.sample(seed=seed)
    plate_id = json_path.stem

    if verbose:
        print(f"\nExecuting {len(parsed_wells)} wells in parallel...")

    # Prepare arguments for workers
    worker_args = [(pw, seed, run_context, plate_id) for pw in parsed_wells]

    # Execute in parallel
    with Pool(processes=workers) as pool:
        raw_results = pool.map(execute_well_worker, worker_args)

    if verbose:
        print(f"\n✓ Simulation complete: {len(raw_results)} wells")

    # Count successes vs failures
    n_success = sum(1 for r in raw_results if "error" not in r)
    n_failed = len(raw_results) - n_success

    if verbose and n_failed > 0:
        print(f"  ⚠️  {n_failed} wells failed")

    # Generate flattened results
    flat_results = [flatten_result(r) for r in raw_results]

    # Package output
    treatment_counts = {}
    for pw in parsed_wells:
        treatment_counts[pw.treatment] = treatment_counts.get(pw.treatment, 0) + 1

    # Convert sets in parse_metadata to lists for JSON serialization
    serializable_metadata = {}
    for k, v in parse_metadata.items():
        if isinstance(v, set):
            serializable_metadata[k] = list(v)
        elif isinstance(v, dict):
            # Check if dict values are sets
            serializable_metadata[k] = {dk: list(dv) if isinstance(dv, set) else dv for dk, dv in v.items()}
        else:
            serializable_metadata[k] = v

    output = {
        "plate_id": plate_id,
        "seed": seed,
        "n_wells": len(raw_results),
        "n_success": n_success,
        "n_failed": n_failed,
        "parsed_wells": [pw.__dict__ for pw in parsed_wells],
        "raw_results": raw_results,
        "flat_results": flat_results,
        "metadata": {
            "cell_lines": list(cell_lines),
            "treatments": list(treatments),
            "compounds": list(compounds),
            "treatment_counts": treatment_counts,
            **serializable_metadata
        }
    }

    # Save results
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{plate_id}_results_seed{seed}.json"
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)

        if verbose:
            print(f"\n✓ Results saved: {output_file}")

        # Auto-commit and push if requested
        if auto_commit:
            import subprocess
            try:
                if verbose:
                    print(f"\n{'='*70}")
                    print(f"Auto-committing results...")
                    print(f"{'='*70}")

                # Add results file
                subprocess.run(['git', 'add', str(output_file)], check=True, cwd=output_dir.parent.parent)

                # Create commit message
                commit_msg = f"""feat: add calibration plate results - {plate_id} seed{seed}

Executed: {n_wells} wells
Successful: {n_success}
Failed: {n_failed}
Cell lines: {', '.join(output['metadata']['cell_lines'])}
Compounds: {', '.join(output['metadata']['compounds'])}

🤖 Auto-committed by plate_executor_v2_parallel.py"""

                # Commit
                subprocess.run(['git', 'commit', '-m', commit_msg], check=True, cwd=output_dir.parent.parent)

                if verbose:
                    print(f"✓ Results committed")

                # Push
                subprocess.run(['git', 'push'], check=True, cwd=output_dir.parent.parent)

                if verbose:
                    print(f"✓ Results pushed to remote")

            except subprocess.CalledProcessError as e:
                if verbose:
                    print(f"⚠️  Git operation failed: {e}")
                    print(f"   Results saved but not committed. You can commit manually.")

    return output


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='Execute calibration plate with parallel processing')
    parser.add_argument('plate_design', nargs='?',
                        default='validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v2.json',
                        help='Path to plate design JSON file')
    parser.add_argument('--seed', type=int, default=42, help='Random seed (default: 42)')
    parser.add_argument('--workers', type=int, default=None, help='Number of workers (default: auto-detect)')
    parser.add_argument('--auto-commit', action='store_true', help='Auto-commit and push results after completion')
    args = parser.parse_args()

    json_path = Path(args.plate_design)

    if not json_path.exists():
        print(f"✗ Plate design not found: {json_path}")
        sys.exit(1)

    # Run with all correctness fixes + parallel execution
    results = execute_plate_design_parallel(
        json_path=json_path,
        seed=args.seed,
        output_dir=Path("results/calibration_plates"),
        verbose=True,
        workers=args.workers,
        auto_commit=args.auto_commit
    )

    print(f"\n{'='*70}")
    print(f"EXECUTION COMPLETE")
    print(f"{'='*70}")
    print(f"  Wells executed: {results['n_wells']}")
    print(f"  Successful: {results['n_success']}")
    if results['n_failed'] > 0:
        print(f"  Failed: {results['n_failed']}")
