#!/usr/bin/env python3
"""
Apply calibration to biological plate JSON.

Simpler version of apply_calibration.py that works with plate JSON format.
"""

import argparse
import json
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cell_os.calibration.profile import CalibrationProfile


def apply_calibration_to_plate(plate_path: str, calibration_path: str, output_path: str):
    """Apply calibration corrections to all wells in a plate."""

    # Load plate data
    with open(plate_path, 'r') as f:
        plate_data = json.load(f)

    # Load calibration profile
    profile = CalibrationProfile(calibration_path)

    print(f"Loaded calibration profile")
    print(f"  Schema: {profile.schema_version}")
    print(f"Applying to {len(plate_data['parsed_wells'])} wells...")

    # Apply calibration to raw_results (where morphology actually lives)
    calibrated_results = []
    for well in plate_data.get('raw_results', []):
        well_id = well['well_id']
        morph_raw = well.get('morphology', {})

        if not morph_raw:
            # No morphology, skip
            well_cal = well.copy()
            well_cal['morphology_corrected'] = {}
            well_cal['calibration_applied'] = False
            calibrated_results.append(well_cal)
            continue

        # Apply vignette correction
        morph_corrected = profile.correct_morphology(morph_raw, well_id)

        # Create calibrated well record (preserve original morphology)
        well_cal = well.copy()
        well_cal['morphology_corrected'] = morph_corrected
        well_cal['calibration_applied'] = True

        calibrated_results.append(well_cal)

    # Create output with calibrated results
    output_data = plate_data.copy()
    output_data['raw_results'] = calibrated_results
    output_data['calibration_applied'] = True

    # Write output
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"Wrote calibrated plate to: {output_path}")
    print(f"  Raw morphology preserved in 'morphology'")
    print(f"  Corrected morphology in 'morphology_corrected'")


def main():
    parser = argparse.ArgumentParser(description="Apply calibration to biological plate")
    parser.add_argument('--plate', required=True, help='Input plate JSON')
    parser.add_argument('--calibration', required=True, help='Calibration report JSON')
    parser.add_argument('--output', required=True, help='Output calibrated plate JSON')

    args = parser.parse_args()

    apply_calibration_to_plate(args.plate, args.calibration, args.output)


if __name__ == '__main__':
    main()
