"""
Generate full 384-well bead plate data with DARK floor fix (Phase 4).

This script runs the bead plate calibration with:
- Detector bias enabled (enable_detector_bias=True)
- Calibration-specific technical_noise params (dark_bias_lsbs, floor sigma)
- Outputs to: results/cal_beads_dyes_seed42_darkfix/

Run with: python tests/integration/generate_bead_plate_data_with_dark_fix.py
"""

import json
from pathlib import Path
import numpy as np
import yaml

from src.cell_os.plate_executor_v2 import parse_plate_design_v2, execute_well
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.run_context import RunContext


def generate_bead_plate_with_dark_fix():
    """
    Generate full 384-well bead plate observations with DARK floor fix.

    Output: results/cal_beads_dyes_seed42_darkfix/observations.jsonl
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

    # Create VM with calibration-specific technical_noise params
    print(f"\nCreating VM with seed={seed} and calibration params...")
    vm = BiologicalVirtualMachine(seed=seed, run_context=run_context, use_database=True)

    # Load calibration-specific thalamus params (with DARK floor fix)
    calibration_params_path = Path("data/calibration_thalamus_params.yaml")
    if not calibration_params_path.exists():
        print(f"ERROR: Calibration params not found: {calibration_params_path}")
        print("Expected file: data/calibration_thalamus_params.yaml")
        return

    print(f"  Loading calibration params: {calibration_params_path}")
    with open(calibration_params_path) as f:
        calibration_params = yaml.safe_load(f)

    # Override VM thalamus_params with calibration params
    vm.thalamus_params = calibration_params
    print(f"✓ VM created with calibration params")
    print(f"  dark_bias_lsbs: {calibration_params['technical_noise'].get('dark_bias_lsbs', 'not set')}")
    print(f"  additive_floor_sigma_er: {calibration_params['technical_noise'].get('additive_floor_sigma_er', 0.0)}")
    print(f"  saturation_ceiling_er: {calibration_params['technical_noise'].get('saturation_ceiling_er', 0.0)}")
    print(f"  adc_quant_bits_default: {calibration_params['technical_noise'].get('adc_quant_bits_default', 0)}")

    # Execute all wells
    print(f"\nExecuting {len(parsed_wells)} wells with DARK floor fix...")
    print(f"  (Detector bias enabled for optical materials)")
    results = []
    for i, pw in enumerate(parsed_wells):
        if (i + 1) % 96 == 0 or i == 0:
            print(f"  Progress: {i + 1}/{len(parsed_wells)} wells ({100*(i+1)//len(parsed_wells)}%)")

        result = execute_well(pw, vm, seed, run_context, plate_id, vessel_type)
        results.append(result)

    print(f"✓ Execution complete: {len(results)} wells")

    # Create output directory
    output_dir = Path("results/cal_beads_dyes_seed42_darkfix")
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
        "channels": ["er", "mito", "nucleus", "actin", "rna"],
        "dark_floor_fix_applied": True,
        "calibration_params_file": str(calibration_params_path)
    }
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"✓ Summary saved: {summary_file}")

    # Diagnostic: Show DARK well sample
    print(f"\n📊 DARK Well Diagnostics:")
    dark_wells = [r for r in results if r.get('material_assignment') == 'DARK']
    if dark_wells:
        sample_dark = dark_wells[0]
        print(f"  Sample DARK well ({sample_dark['well_id']}):")
        for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']:
            val = sample_dark['morphology'][ch]
            print(f"    {ch}: {val:.3f} AU")

        # Show DARK variance
        print(f"\n  DARK Variance Check:")
        for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']:
            dark_values = [r['morphology'][ch] for r in dark_wells]
            mean_dark = sum(dark_values) / len(dark_values)
            variance = sum((x - mean_dark) ** 2 for x in dark_values) / len(dark_values)
            std_dark = variance ** 0.5
            unique_values = len(set(dark_values))
            print(f"    {ch}: mean={mean_dark:.3f}, std={std_dark:.3f}, unique={unique_values}")

    print(f"\n✅ Data generation complete with DARK floor fix!")
    print(f"   Output: {output_file}")
    print(f"   Wells: {len(results)}")
    print(f"\nNext steps:")
    print(f"  1. Run DARK contract tests: pytest tests/contracts/test_dark_floor_observable.py -xvs")
    print(f"  2. Run calibration: python -m src.cell_os.calibration.bead_plate_calibration \\")
    print(f"       --obs {output_file} \\")
    print(f"       --out results/cal_beads_dyes_seed42_darkfix/calibration/")


if __name__ == "__main__":
    generate_bead_plate_with_dark_fix()
