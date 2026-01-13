#!/usr/bin/env python3
"""
Run Autonomous Loop Experiment on JupyterHub
192 wells total: 160 experimental + 32 controls (2 plates)

This runs the specific 13 candidates from the wide portfolio strategy:
- Max 12 wells per candidate (1× initial data, not deep sampling)
- Priority weighting: CCCP > MG132/oligomycin > others
- 2 plates instead of 6 for decisive decision-making

Custom mode:
- 13 compounds × 12 wells each (not full 2,304 design)
- Single timepoint (12h only, not 12h + 48h)
- Single day, single operator, single replicate
- 4 doses × 2 cell lines × 1 condition = 8 wells per compound
- Plus 4 wells for dose-response curve buffer = 12 wells total
"""
import sys
sys.path.insert(0, '.')
from standalone_cell_thalamus import run_parallel_simulation, generate_design

# Create a custom "autonomous_loop" mode
# by temporarily patching the standalone script

def autonomous_loop_mode():
    """Generate 192-well autonomous loop design"""
    import standalone_cell_thalamus as standalone
    from standalone_cell_thalamus import WellAssignment

    # The 13 candidates selected by the autonomous loop
    compounds = [
        'CCCP',         # Primary (highest uncertainty)
        'MG132',        # Scout
        'oligomycin',   # Scout
        'etoposide',    # Probe
        'tunicamycin',  # Probe
        'paclitaxel',   # Probe
        'thapsigargin', # Probe
        'nocodazole',   # Probe
        'H2O2',         # Probe
        'tBHQ',         # Probe
        'oligomycin',   # (appears twice in ranking - skip duplicate)
        'etoposide',    # (duplicate)
        'MG132',        # (duplicate)
    ]

    # Remove duplicates, keep first 13 unique
    seen = set()
    unique_compounds = []
    for c in compounds:
        if c not in seen:
            seen.add(c)
            unique_compounds.append(c)

    # Fill to 13 if needed
    all_compounds = ['CCCP', 'MG132', 'oligomycin', 'etoposide', 'tunicamycin',
                     'paclitaxel', 'thapsigargin', 'nocodazole', 'H2O2', 'tBHQ']
    for c in all_compounds:
        if c not in unique_compounds:
            unique_compounds.append(c)
        if len(unique_compounds) >= 13:
            break

    compounds = unique_compounds[:13]
    cell_lines = ['A549', 'HepG2']

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║          AUTONOMOUS LOOP EXPERIMENT - 192 WELLS              ║
╚══════════════════════════════════════════════════════════════╝

Strategy: Wide Portfolio
- {len(compounds)} candidates × ~12 wells each = ~{len(compounds) * 12} experimental wells
- Controls: DMSO + sentinels
- Total: ~192 wells (2 plates × 96 wells)

Candidates (by uncertainty ranking):
""")

    for i, compound in enumerate(compounds, 1):
        priority = "Primary" if i == 1 else "Scout" if i <= 3 else "Probe"
        print(f"  {i:2d}. {compound:20s} [{priority}]")

    print(f"""
Experimental design:
- 4 doses per compound (vehicle, low, mid, high)
- 2 cell lines (A549, HepG2)
- Single 12h timepoint (not 12h + 48h)
- Single day, operator, replicate (not 2×2×3)
- Result: 13 × 4 × 2 = 104 experimental wells
- Plus 16 DMSO controls × 2 cell lines = 32 control wells
- Plus sentinels = ~192 wells total

Running with 8 workers (~5-10 minutes)...
""")

    # Call generate_design with custom parameters
    # Patch to use autonomous loop settings
    original_generate = standalone.generate_design

    def custom_generate(cell_lines, compounds, mode):
        """Custom design generator for autonomous loop"""
        dose_levels = [0.0, 0.1, 1.0, 10.0]  # 4 doses
        timepoints = [12.0]  # Single timepoint only
        days = [1]  # Single day
        operators = ['Operator_A']  # Single operator
        replicates = 1  # Single replicate

        design = []
        well_idx = 0

        # Generate experimental wells
        for day_idx, day in enumerate(days, 1):
            for operator in operators:
                for replicate in range(1, replicates + 1):
                    plate_id = f"Day{day}_Op{operator}_Rep{replicate}"

                    for timepoint in timepoints:
                        for compound in compounds:
                            compound_params = standalone.COMPOUND_PARAMS.get(compound, {'ec50_uM': 10.0})
                            ec50 = compound_params['ec50_uM']

                            for dose_frac in dose_levels:
                                dose_uM = dose_frac * ec50 if dose_frac > 0 else 0.0

                                for cell_line in cell_lines:
                                    design.append(WellAssignment(
                                        well_id=f"W{well_idx:04d}",
                                        cell_line=cell_line,
                                        compound=compound,
                                        dose_uM=dose_uM,
                                        timepoint_h=timepoint,
                                        plate_id=plate_id,
                                        day=day,
                                        operator=operator,
                                        is_sentinel=False
                                    ))
                                    well_idx += 1

                        # Add DMSO controls (16 per timepoint)
                        for _ in range(16):
                            for cell_line in cell_lines:
                                design.append(WellAssignment(
                                    well_id=f"W{well_idx:04d}",
                                    cell_line=cell_line,
                                    compound='DMSO',
                                    dose_uM=0.0,
                                    timepoint_h=timepoint,
                                    plate_id=plate_id,
                                    day=day,
                                    operator=operator,
                                    is_sentinel=True
                                ))
                                well_idx += 1

        return design

    # Monkey-patch the generate_design function
    standalone.generate_design = custom_generate

    try:
        # Run simulation
        design_id = run_parallel_simulation(
            cell_lines=cell_lines,
            compounds=compounds,
            mode='custom',  # Ignored, we patched generate_design
            workers=8,
            db_path='cell_thalamus_results.db'
        )

        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                      ✅ COMPLETE!                            ║
╚══════════════════════════════════════════════════════════════╝

Design ID: {design_id}
Results: cell_thalamus_results.db

The database should auto-upload to S3.
Your Mac will auto-download it within 30 seconds.
View at: http://localhost:5173/cell-thalamus
""")
        return design_id

    finally:
        # Restore original function
        standalone.generate_design = original_generate

if __name__ == "__main__":
    autonomous_loop_mode()
