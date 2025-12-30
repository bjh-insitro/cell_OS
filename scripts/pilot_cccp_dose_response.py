#!/usr/bin/env python3
"""
Pilot: CCCP dose-response characterization (baseline, no ER coupling)

Goal: Find the dose where mito_dysfunction ≈ 0.3-0.5 (mid-slope regime).

This is disposable experimental instrumentation. Do not reuse.
"""

import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.run_context import RunContext


def pilot_cccp_dose_response():
    """
    Sweep CCCP doses and measure mito_dysfunction.

    Baseline only: ER damage = 0 (no coupling yet).
    """
    # Doses to test (µM) - refined range to find mid-slope
    cccp_doses = [0.5, 0.6, 0.7, 0.8, 1.0]

    # Replicates per dose
    n_replicates = 6

    # Time
    exposure_h = 12.0

    results = {}

    for dose_uM in cccp_doses:
        mito_dysfunction_values = []

        for replicate in range(n_replicates):
            vm = BiologicalVirtualMachine()
            vm.run_context = RunContext.sample(seed=100 + replicate)
            vm.rng_assay = np.random.default_rng(1000 + replicate)
            vm.rng_biology = np.random.default_rng(2000 + replicate)
            vm._load_cell_thalamus_params()

            vessel_id = "P1_A01"
            vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)
            vessel = vm.vessel_states[vessel_id]

            # Baseline: ER damage = 0
            vessel.er_damage = 0.0
            vessel.er_stress = 0.0

            # Expose to CCCP
            vm.treat_with_compound(vessel_id, compound='CCCP', dose_uM=dose_uM)
            vm.advance_time(exposure_h)

            # Measure mito dysfunction
            mito_dysfunction_values.append(vessel.mito_dysfunction)

        # Compute stats
        median = float(np.median(mito_dysfunction_values))
        q25 = float(np.percentile(mito_dysfunction_values, 25))
        q75 = float(np.percentile(mito_dysfunction_values, 75))

        results[dose_uM] = {
            'median': median,
            'iqr': (q25, q75),
            'values': mito_dysfunction_values,
        }

    return results


def print_results(results):
    """Print dose-response table."""
    print("\n" + "="*60)
    print("CCCP Dose-Response Pilot (baseline, no ER coupling)")
    print("="*60)
    print(f"{'Dose (µM)':<12} {'Median':<12} {'IQR':<20} {'Regime':<15}")
    print("-"*60)

    for dose_uM in sorted(results.keys()):
        r = results[dose_uM]
        median = r['median']
        q25, q75 = r['iqr']

        # Classify regime
        if median < 0.2:
            regime = "Floor"
        elif median > 0.7:
            regime = "Ceiling"
        elif 0.3 <= median <= 0.5:
            regime = "MID-SLOPE ★"
        else:
            regime = "Transition"

        print(f"{dose_uM:<12.1f} {median:<12.3f} [{q25:.3f}, {q75:.3f}]   {regime:<15}")

    print("-"*60)

    # Recommendation
    midslope_candidates = [
        dose for dose, r in results.items()
        if 0.3 <= r['median'] <= 0.5
    ]

    if midslope_candidates:
        print(f"\n✓ Recommended mid-slope dose: {midslope_candidates[0]:.1f} µM")
        print(f"  (median mito_dysfunction ≈ {results[midslope_candidates[0]]['median']:.3f})")
    else:
        print("\n⚠ No dose in mid-slope regime (0.3-0.5).")
        print("  Consider testing intermediate doses.")

    print("="*60 + "\n")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, '/Users/bjh/cell_OS')

    print("Running CCCP dose-response pilot...")
    print("(This will take ~30-60 seconds)")

    results = pilot_cccp_dose_response()
    print_results(results)

    # Write recommendation to TEST_DESIGN.md
    midslope_candidates = [
        dose for dose, r in results.items()
        if 0.3 <= r['median'] <= 0.5
    ]

    if midslope_candidates:
        dose = midslope_candidates[0]
        median = results[dose]['median']

        recommendation = f"""
## Pilot Results (Baseline CCCP Dose-Response)

Tested: {sorted(results.keys())} µM CCCP × 12h (N=6 per dose)

**Mid-slope dose identified:**
- **CCCP {dose:.1f} µM** → median mito_dysfunction = {median:.3f}
- IQR: [{results[dose]['iqr'][0]:.3f}, {results[dose]['iqr'][1]:.3f}]

This dose will be used for the monotonicity test.

**Full results:**
"""
        for d in sorted(results.keys()):
            r = results[d]
            recommendation += f"- {d:.1f} µM: median={r['median']:.3f}, IQR=[{r['iqr'][0]:.3f}, {r['iqr'][1]:.3f}]\n"

        print("\nWriting recommendation to TEST_DESIGN_er_mito_coupling.md...")
        with open('/Users/bjh/cell_OS/tests/phase6a/TEST_DESIGN_er_mito_coupling.md', 'a') as f:
            f.write(recommendation)
        print("✓ Done")
