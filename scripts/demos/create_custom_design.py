#!/usr/bin/env python3
"""
Example script for creating custom Cell Thalamus designs.

Usage:
    python scripts/create_custom_design.py
"""

from design_catalog import DesignGenerator

# Initialize generator
generator = DesignGenerator()

# Example 1: Create a neuron/microglia design with 4 cell lines
print("=" * 80)
print("EXAMPLE 1: All 4 cell lines (A549, HepG2, neurons, microglia)")
print("=" * 80)

design_4cell = generator.create_design(
    design_id='phase0_4cell_neurons_microglia_v1',
    description='Phase 0 with all 4 cell lines: A549, HepG2, iPSC_NGN2 (neurons), iPSC_Microglia',

    # Cell lines and compounds
    cell_lines=['A549', 'HepG2', 'iPSC_NGN2', 'iPSC_Microglia'],
    compounds=['tBHQ', 'CCCP', 'tunicamycin', 'nocodazole'],  # Focused compound panel

    # Dose configuration
    dose_multipliers=[0, 0.1, 1.0, 10.0],  # Vehicle, low, mid, high
    replicates_per_dose=2,  # 2 reps to fit more cell lines

    # Batch structure
    days=[1],
    operators=['Operator_A'],
    timepoints_h=[12.0, 48.0],

    # Sentinels
    sentinel_config={
        'DMSO': {'dose_uM': 0.0, 'n_per_cell': 3},
        'tBHQ': {'dose_uM': 10.0, 'n_per_cell': 2},
    },

    # Plate layout
    plate_format=96,
    checkerboard=False,  # Separate plates per cell line
    exclude_corners=False,
    exclude_edges=False,
)

# Example 2: High-throughput 384-well screening
print("\n" + "=" * 80)
print("EXAMPLE 2: High-throughput 384-well screening")
print("=" * 80)

design_384 = generator.create_design(
    design_id='phase0_384well_highthroughput_v1',
    description='High-throughput Phase 0 using 384-well format with all 10 compounds',

    # Cell lines and compounds
    cell_lines=['A549', 'HepG2'],
    compounds=['tBHQ', 'H2O2', 'tunicamycin', 'thapsigargin', 'CCCP',
              'oligomycin', 'etoposide', 'MG132', 'nocodazole', 'paclitaxel'],

    # Dose configuration - more granular for 384-well
    dose_multipliers=[0, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0],  # 8-point dose response
    replicates_per_dose=2,

    # Batch structure
    days=[1],
    operators=['Operator_A'],
    timepoints_h=[48.0],  # Single endpoint

    # Sentinels
    sentinel_config={
        'DMSO': {'dose_uM': 0.0, 'n_per_cell': 8},  # More controls for QC
        'tBHQ': {'dose_uM': 10.0, 'n_per_cell': 4},
        'tunicamycin': {'dose_uM': 2.0, 'n_per_cell': 4},
    },

    # Plate layout
    plate_format=384,
    checkerboard=True,  # Mix cell lines on same plate
    exclude_corners=True,  # Common QC practice
    exclude_edges=False,
)

# Example 3: Minimal pilot design (96-well, few compounds)
print("\n" + "=" * 80)
print("EXAMPLE 3: Minimal pilot design for quick validation")
print("=" * 80)

design_pilot = generator.create_design(
    design_id='phase0_pilot_minimal_v1',
    description='Minimal pilot design for quick proof-of-concept',

    # Cell lines and compounds
    cell_lines=['A549'],
    compounds=['tBHQ', 'CCCP', 'tunicamycin'],  # Just 3 compounds

    # Dose configuration
    dose_multipliers=[0, 0.1, 1.0, 10.0],
    replicates_per_dose=3,

    # Batch structure
    days=[1],
    operators=['Operator_A'],
    timepoints_h=[12.0],  # Single timepoint

    # Sentinels
    sentinel_config={
        'DMSO': {'dose_uM': 0.0, 'n_per_cell': 4},
    },

    # Plate layout
    plate_format=96,
    checkerboard=False,
    exclude_corners=False,
    exclude_edges=False,
)

print("\n" + "=" * 80)
print("✓ All designs created successfully!")
print("=" * 80)
print("\nTo run simulations:")
print("  1. Upload designs to JupyterHub: scp data/designs/*.json jupyterhub.insitro.com:/mnt/shared/brig/cell_OS/data/designs/")
print("  2. SSH to JupyterHub: ssh jupyterhub.insitro.com")
print("  3. cd /mnt/shared/brig/cell_OS")
print("  4. Run simulation:")
print("     python3 standalone_cell_thalamus.py --design-json data/designs/phase0_4cell_neurons_microglia_v1.json --seed 0")
print("  5. Sync results: ./scripts/sync_aws_db.sh")
print("  6. View in dashboard!")
