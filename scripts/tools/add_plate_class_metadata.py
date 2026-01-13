#!/usr/bin/env python3
"""
Add plate_class metadata to V3 and V4 plate designs.

Implements Phase 1 of PLATE_CLASS_SPECIFICATION.md.
"""

import json
from pathlib import Path

def add_screening_metadata(plate_design):
    """Add SCREENING plate class metadata to V3."""
    plate_design['plate_class'] = 'SCREENING'
    plate_design['plate_class_metadata'] = {
        'purpose': 'Stress-test spatial model under realistic screening conditions',
        'design_objectives': [
            'maximize_spatial_decorrelation',
            'stress_test_spatial_corrections',
            'validate_hit_robustness',
            'break_row_column_confounds'
        ],
        'valid_metrics': [
            'spatial_variance',
            'boring_wells_spatial_test',
            'row_column_decorrelation',
            'z_factor_under_stress',
            'mixed_tile_cv',
            'hit_robustness'
        ],
        'invalid_metrics': [
            'island_cv',
            'absolute_cv_as_biological_noise',
            'technical_replicate_floor'
        ],
        'interpretation_notes': [
            'High mixed tile CV (60-80%) is EXPECTED due to neighbor diversity',
            'Spatial variance should be LOW (indicates successful decorrelation)',
            'Z-factors represent realistic screening conditions, not ideal lab conditions',
            'Do NOT use absolute CV to estimate biological noise - use calibration plates instead'
        ],
        'design_features': {
            'cell_line_pattern': 'single_well_alternating_checkerboard',
            'spatial_mixing': True,
            'homogeneous_islands': False,
            'anchor_placement': 'scattered',
            'gradients_allowed': True,
            'probes_allowed': True
        }
    }
    return plate_design


def add_calibration_metadata(plate_design):
    """Add CALIBRATION plate class metadata to V4."""
    plate_design['plate_class'] = 'CALIBRATION'
    plate_design['plate_class_metadata'] = {
        'purpose': 'Measure technical noise floor and biological variability under controlled conditions',
        'design_objectives': [
            'minimize_cv',
            'isolate_technical_variance',
            'measure_perturbation_effects',
            'establish_baseline_stability'
        ],
        'valid_metrics': [
            'island_cv',
            'vehicle_technical_floor',
            'anchor_island_stability',
            'perturbation_variance_inflation',
            'inter_island_consistency'
        ],
        'invalid_metrics': [
            'global_spatial_variance',
            'row_column_decorrelation',
            'mixed_region_cv',
            'boring_wells_spatial_test'
        ],
        'interpretation_notes': [
            'High spatial variance is EXPECTED due to homogeneous island clustering',
            'Island CV (2-20%) measures technical + biological noise under controlled conditions',
            'Vehicle islands establish baseline; anchor islands measure perturbation effects',
            'Do NOT use spatial variance as quality metric - use island CV instead'
        ],
        'design_features': {
            'cell_line_pattern': 'homogeneous_islands',
            'spatial_mixing': False,
            'homogeneous_islands': True,
            'island_count': 8,
            'island_size': '3x3',
            'anchor_placement': 'island_based',
            'forced_nominal_conditions': True,
            'exclusion_rules_active': True
        }
    }
    return plate_design


def main():
    print("="*80)
    print("ADDING PLATE CLASS METADATA")
    print("="*80)
    print()
    print("Implementing Phase 1 of PLATE_CLASS_SPECIFICATION.md")
    print()

    # Update V3 (Screening)
    v3_path = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v3.json")
    print(f"Updating {v3_path.name} → SCREENING plate class")

    with open(v3_path, 'r') as f:
        v3 = json.load(f)

    v3 = add_screening_metadata(v3)

    with open(v3_path, 'w') as f:
        json.dump(v3, f, indent=2)

    print("  ✓ Added plate_class: SCREENING")
    print("  ✓ Added plate_class_metadata")
    print("  ✓ Documented valid metrics: spatial_variance, z_factor, mixed_tile_cv")
    print("  ✓ Documented invalid metrics: island_cv, technical_floor")
    print()

    # Update V4 (Calibration)
    v4_path = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v4.json")
    print(f"Updating {v4_path.name} → CALIBRATION plate class")

    with open(v4_path, 'r') as f:
        v4 = json.load(f)

    v4 = add_calibration_metadata(v4)

    with open(v4_path, 'w') as f:
        json.dump(v4, f, indent=2)

    print("  ✓ Added plate_class: CALIBRATION")
    print("  ✓ Added plate_class_metadata")
    print("  ✓ Documented valid metrics: island_cv, technical_floor, perturbation_effect")
    print("  ✓ Documented invalid metrics: spatial_variance, row_column_decorrelation")
    print()

    # Update V5 (Hybrid - optional)
    v5_path = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v5.json")
    if v5_path.exists():
        print(f"Updating {v5_path.name} → HYBRID plate class (exploratory)")

        with open(v5_path, 'r') as f:
            v5 = json.load(f)

        v5['plate_class'] = 'HYBRID'
        v5['plate_class_metadata'] = {
            'purpose': 'Exploratory design combining calibration islands with screening checkerboard',
            'design_objectives': [
                'measure_island_cv',
                'maintain_spatial_decorrelation',
                'test_hybrid_feasibility'
            ],
            'valid_metrics': [
                'island_cv',
                'boring_wells_spatial_variance'
            ],
            'invalid_metrics': [],
            'interpretation_notes': [
                'Hybrid plates compromise on both calibration and screening objectives',
                'Use specialized plates (V3 or V4) for production work',
                'V5 is exploratory - testing if single-well alternation + islands avoids V4 spatial artifacts'
            ],
            'design_features': {
                'cell_line_pattern': 'v3_checkerboard_with_islands',
                'spatial_mixing': True,
                'homogeneous_islands': True,
                'island_count': 8,
                'island_size': '3x3',
                'base_pattern': 'single_well_alternating'
            }
        }

        with open(v5_path, 'w') as f:
            json.dump(v5, f, indent=2)

        print("  ✓ Added plate_class: HYBRID")
        print("  ✓ Marked as exploratory (not production)")
        print()

    print("="*80)
    print("PLATE CLASS METADATA ADDED")
    print("="*80)
    print()
    print("Updated files:")
    print(f"  - {v3_path}")
    print(f"  - {v4_path}")
    if v5_path.exists():
        print(f"  - {v5_path}")
    print()
    print("Next steps:")
    print("  1. Create validation script (validate_plate_class.py)")
    print("  2. Update QC comparison scripts to check plate class")
    print("  3. Update frontend to display plate class metadata")
    print()
    print("Analysis scripts should now check plate_class before computing metrics:")
    print("  - V3 (SCREENING): spatial_variance, z_factor, mixed_tile_cv")
    print("  - V4 (CALIBRATION): island_cv, technical_floor, perturbation_effect")


if __name__ == "__main__":
    main()
