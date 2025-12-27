"""
Generate full 384-well bead plate data for plate map visualization.

This is a one-time data generation script, not a test.
Run with: pytest tests/integration/generate_bead_plate_data.py -xvs
"""

import json
from pathlib import Path
import numpy as np

from src.cell_os.plate_executor_v2 import parse_plate_design_v2, execute_well
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.run_context import RunContext


def test_generate_full_bead_plate_output():
    """
    Generate full 384-well bead plate observations and save to JSONL.

    Output: results/cal_beads_dyes_seed42/observations.jsonl
    """
    json_path = Path("validation_frontend/public/plate_designs/CAL_384_MICROSCOPE_BEADS_DYES_v1.json")

    if not json_path.exists():
        print(f"ERROR: Plate design not found: {json_path}")
        return

    # Parse plate
    print(f"Parsing bead plate: {json_path.name}")
    parsed_wells, metadata = parse_plate_design_v2(json_path)
    print(f"✓ Parsed {len(parsed_wells)} wells")
    print(f"  Materials: {metadata.get('materials_used', [])}")

    # Shared execution parameters
    seed = 42
    run_context = RunContext.sample(seed=seed)
    plate_id = "CAL_384_MICROSCOPE_BEADS_DYES_v1"
    vessel_type = "384-well"

    # Create VM
    print(f"\nCreating VM with seed={seed}...")
    vm = BiologicalVirtualMachine(seed=seed, run_context=run_context, use_database=False)
    vm._load_cell_thalamus_params()
    print(f"✓ VM created")

    # Execute all wells
    print(f"\nExecuting {len(parsed_wells)} wells...")
    results = []
    for i, pw in enumerate(parsed_wells):
        if (i + 1) % 96 == 0 or i == 0:
            print(f"  Progress: {i + 1}/{len(parsed_wells)} wells ({100*(i+1)//len(parsed_wells)}%)")

        result = execute_well(pw, vm, seed, run_context, plate_id, vessel_type)
        results.append(result)

    print(f"✓ Execution complete: {len(results)} wells")

    # Create output directory
    output_dir = Path("results/cal_beads_dyes_seed42")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save as JSONL (one JSON record per line)
    output_file = output_dir / "observations.jsonl"
    print(f"\nSaving to: {output_file}")
    with open(output_file, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + '\n')

    print(f"✓ JSONL saved ({len(results)} records)")

    # Also save summary stats
    summary_file = output_dir / "summary.json"
    summary = {
        "plate_id": plate_id,
        "seed": seed,
        "n_wells": len(results),
        "materials_used": metadata.get('materials_used', []),
        "schema_version": metadata.get('schema_version'),
        "channels": ["er", "mito", "nucleus", "actin", "rna"]
    }
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"✓ Summary saved: {summary_file}")
    print(f"\n✅ Data generation complete!")
    print(f"   Output: {output_file}")
    print(f"   Wells: {len(results)}")


if __name__ == "__main__":
    # Can also run directly
    test_generate_full_bead_plate_output()
