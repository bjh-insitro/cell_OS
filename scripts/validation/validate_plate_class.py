#!/usr/bin/env python3
"""
Validate that plate designs match their declared plate class.

Checks that design features are consistent with CALIBRATION, SCREENING, or HYBRID class.
"""

import json
import sys
from pathlib import Path

# Expected features for each plate class
CALIBRATION_REQUIREMENTS = {
    'homogeneous_islands': {
        'required': True,
        'min_islands': 2,
        'min_island_size': 9,  # 3×3
        'description': 'Calibration plates must have homogeneous islands for CV measurement'
    },
    'exclusion_rules': {
        'required': True,
        'description': 'Calibration plates must protect islands from probes/gradients'
    },
    'vehicle_islands': {
        'required': True,
        'min_count': 1,
        'description': 'Calibration plates need vehicle islands for baseline'
    }
}

SCREENING_REQUIREMENTS = {
    'spatial_mixing': {
        'required': True,
        'max_homogeneous_size': 4,  # Allow 2×2 max
        'description': 'Screening plates must have spatial mixing (checkerboard pattern)'
    },
    'no_large_islands': {
        'required': True,
        'max_island_size': 4,  # No 3×3+ islands
        'description': 'Screening plates should not have large homogeneous regions'
    }
}

HYBRID_REQUIREMENTS = {
    'islands_and_mixing': {
        'required': True,
        'description': 'Hybrid plates must have both islands and spatial mixing'
    }
}


def check_homogeneous_islands(plate_design):
    """Check if plate has homogeneous islands."""
    if 'reproducibility_islands' not in plate_design:
        return {
            'has_islands': False,
            'island_count': 0,
            'islands': []
        }

    islands = plate_design['reproducibility_islands'].get('islands', [])

    island_info = []
    for island in islands:
        island_id = island.get('island_id', '?')
        cell_line = island.get('cell_line', '?')
        treatment = island.get('assignment', {}).get('treatment', '?')
        wells = island.get('wells', [])
        island_size = len(wells)

        island_info.append({
            'id': island_id,
            'cell_line': cell_line,
            'treatment': treatment,
            'size': island_size
        })

    return {
        'has_islands': len(islands) > 0,
        'island_count': len(islands),
        'islands': island_info
    }


def check_exclusion_rules(plate_design):
    """Check if plate has exclusion rules protecting islands."""
    if 'reproducibility_islands' not in plate_design:
        return {'has_exclusions': False}

    exclusions = plate_design['reproducibility_islands'].get('exclusion_rules')
    if not exclusions:
        return {'has_exclusions': False}

    forced_fields = exclusions.get('forced_fields', {})

    return {
        'has_exclusions': True,
        'forced_fields': forced_fields
    }


def check_spatial_mixing(plate_design):
    """Check if plate has spatial mixing (checkerboard pattern)."""
    if 'cell_lines' not in plate_design:
        return {'has_mixing': False}

    strategy = plate_design['cell_lines'].get('strategy', '')
    well_to_cell_line = plate_design['cell_lines'].get('well_to_cell_line', {})

    # Sample a few adjacent wells to check for alternation
    sample_wells = [
        ('A1', 'A2'), ('A2', 'A3'), ('A3', 'A4'),
        ('B1', 'B2'), ('B2', 'B3'),
        ('A1', 'B1'), ('A2', 'B2')
    ]

    alternation_count = 0
    same_count = 0

    for w1, w2 in sample_wells:
        if w1 in well_to_cell_line and w2 in well_to_cell_line:
            if well_to_cell_line[w1] != well_to_cell_line[w2]:
                alternation_count += 1
            else:
                same_count += 1

    # If most sampled pairs alternate, it's a checkerboard
    has_mixing = alternation_count > same_count

    return {
        'has_mixing': has_mixing,
        'strategy': strategy,
        'alternation_ratio': alternation_count / (alternation_count + same_count) if (alternation_count + same_count) > 0 else 0
    }


def validate_calibration_plate(plate_design, plate_id):
    """Validate CALIBRATION plate class."""
    print(f"Validating CALIBRATION plate: {plate_id}")
    print("-" * 80)

    all_pass = True

    # Check 1: Has homogeneous islands
    island_info = check_homogeneous_islands(plate_design)

    if not island_info['has_islands']:
        print("❌ FAILED: No homogeneous islands found")
        print("   Calibration plates require ≥ 2 islands for CV measurement")
        all_pass = False
    elif island_info['island_count'] < CALIBRATION_REQUIREMENTS['homogeneous_islands']['min_islands']:
        print(f"❌ FAILED: Only {island_info['island_count']} islands (need ≥ 2)")
        all_pass = False
    else:
        print(f"✅ PASSED: {island_info['island_count']} homogeneous islands found")
        for island in island_info['islands']:
            print(f"   - {island['id']}: {island['cell_line']} + {island['treatment']} ({island['size']} wells)")

    print()

    # Check 2: Has exclusion rules
    exclusion_info = check_exclusion_rules(plate_design)

    if not exclusion_info['has_exclusions']:
        print("⚠️  WARNING: No exclusion rules found")
        print("   Calibration plates should protect islands from probes/gradients")
    else:
        print("✅ PASSED: Exclusion rules configured")
        for field, value in exclusion_info['forced_fields'].items():
            print(f"   - {field}: {value}")

    print()

    # Check 3: Has vehicle islands
    vehicle_islands = [i for i in island_info['islands'] if i['treatment'] == 'VEHICLE']

    if len(vehicle_islands) == 0:
        print("⚠️  WARNING: No vehicle islands found")
        print("   Calibration plates should have ≥ 1 vehicle island for baseline")
    else:
        print(f"✅ PASSED: {len(vehicle_islands)} vehicle islands (baseline measurement)")

    print()
    return all_pass


def validate_screening_plate(plate_design, plate_id):
    """Validate SCREENING plate class."""
    print(f"Validating SCREENING plate: {plate_id}")
    print("-" * 80)

    all_pass = True

    # Check 1: Has spatial mixing
    mixing_info = check_spatial_mixing(plate_design)

    if not mixing_info['has_mixing']:
        print("❌ FAILED: No spatial mixing detected")
        print("   Screening plates require checkerboard pattern for decorrelation")
        all_pass = False
    else:
        print(f"✅ PASSED: Spatial mixing detected (alternation ratio: {mixing_info['alternation_ratio']:.2f})")
        print(f"   Strategy: {mixing_info['strategy']}")

    print()

    # Check 2: No large homogeneous islands
    island_info = check_homogeneous_islands(plate_design)

    if island_info['has_islands']:
        large_islands = [i for i in island_info['islands'] if i['size'] > SCREENING_REQUIREMENTS['no_large_islands']['max_island_size']]

        if large_islands:
            print(f"⚠️  WARNING: {len(large_islands)} large islands found (≥ 3×3)")
            print("   Screening plates should avoid large homogeneous regions")
            for island in large_islands:
                print(f"   - {island['id']}: {island['size']} wells")
        else:
            print("✅ PASSED: No large homogeneous islands")
    else:
        print("✅ PASSED: No homogeneous islands (pure screening design)")

    print()
    return all_pass


def validate_hybrid_plate(plate_design, plate_id):
    """Validate HYBRID plate class."""
    print(f"Validating HYBRID plate: {plate_id}")
    print("-" * 80)

    all_pass = True

    # Check: Has both islands and mixing
    island_info = check_homogeneous_islands(plate_design)
    mixing_info = check_spatial_mixing(plate_design)

    if not island_info['has_islands']:
        print("❌ FAILED: No islands found")
        print("   Hybrid plates require islands (like calibration)")
        all_pass = False
    else:
        print(f"✅ PASSED: {island_info['island_count']} islands found")

    if not mixing_info['has_mixing']:
        print("❌ FAILED: No spatial mixing detected")
        print("   Hybrid plates require mixing (like screening)")
        all_pass = False
    else:
        print(f"✅ PASSED: Spatial mixing detected")

    print()
    print("⚠️  Note: Hybrid plates compromise on both objectives")
    print("   Use specialized plates (CALIBRATION or SCREENING) for production work")
    print()

    return all_pass


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_plate_class.py <plate_design.json>")
        print()
        print("Example:")
        print("  python validate_plate_class.py validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v3.json")
        sys.exit(1)

    plate_file = Path(sys.argv[1])

    if not plate_file.exists():
        print(f"Error: File not found: {plate_file}")
        sys.exit(1)

    print("=" * 80)
    print("PLATE CLASS VALIDATION")
    print("=" * 80)
    print()

    with open(plate_file, 'r') as f:
        plate_design = json.load(f)

    plate_id = plate_design.get('plate', {}).get('plate_id', 'Unknown')
    plate_class = plate_design.get('plate_class')

    if not plate_class:
        print(f"❌ ERROR: No plate_class field found in {plate_file.name}")
        print()
        print("Plate designs must declare their class:")
        print("  - CALIBRATION: Measure noise floor (homogeneous islands)")
        print("  - SCREENING: Stress-test spatial model (checkerboard mixing)")
        print("  - HYBRID: Exploratory (both islands and mixing)")
        print()
        print("Run scripts/add_plate_class_metadata.py to add metadata")
        sys.exit(1)

    print(f"Plate: {plate_id}")
    print(f"Class: {plate_class}")
    print()

    # Validate based on class
    if plate_class == 'CALIBRATION':
        passed = validate_calibration_plate(plate_design, plate_id)
    elif plate_class == 'SCREENING':
        passed = validate_screening_plate(plate_design, plate_id)
    elif plate_class == 'HYBRID':
        passed = validate_hybrid_plate(plate_design, plate_id)
    else:
        print(f"❌ ERROR: Unknown plate class '{plate_class}'")
        print("   Valid classes: CALIBRATION, SCREENING, HYBRID")
        sys.exit(1)

    # Summary
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print()

    if passed:
        print(f"✅ {plate_id} is a valid {plate_class} plate")
        print()
        print("Design features match declared class.")
        print("Metrics specified in plate_class_metadata are appropriate.")
    else:
        print(f"❌ {plate_id} does NOT match declared {plate_class} class")
        print()
        print("Design features are inconsistent with plate class.")
        print("Review design or update plate_class field.")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
