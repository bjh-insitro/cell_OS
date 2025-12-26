"""
Prerequisite verification tests for v4.

These tests verify that prerequisites are applied BEFORE v4 diffs.
If these fail, v4 will "pass locally while lying."
"""

import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_prereq_a_no_sync_after_step():
    """Verify subpop viabilities stay independent after step.

    This catches if _sync_subpopulation_viabilities still exists and is called.
    """

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.9)
    vessel = vm.vessel_states["v"]

    # Manually set different viabilities
    names = sorted(vessel.subpopulations.keys())
    vessel.subpopulations[names[0]]['viability'] = 0.5
    vessel.subpopulations[names[1]]['viability'] = 0.7
    vessel.subpopulations[names[2]]['viability'] = 0.9

    # Step without treatment (just time passage)
    vm._step_vessel(vessel, 1.0)

    # Assert they stayed different
    v_after = [vessel.subpopulations[n]['viability'] for n in names]
    unique = len(set(np.round(v_after, 6)))

    assert unique >= 2, \
        f"Subpops re-synced during step: {v_after}. " \
        f"_sync_subpopulation_viabilities still being called?"

    print(f"✓ Prereq A: No sync after step (viabilities: {[f'{v:.2f}' for v in v_after]})")


def test_prereq_b_per_subpop_hazards_exist():
    """Verify per-subpop hazard computation and caching works.

    This catches if attrition is still computed at vessel level only.
    """

    vm = BiologicalVirtualMachine(seed=42)
    # Low viability to allow attrition (viability gate requires < 0.5)
    vm.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.3)
    vessel = vm.vessel_states["v"]

    # Treat with lethal dose
    vm.treat_with_compound("v", "tunicamycin", 5.0)

    # Step to 15h (past commitment delays, triggers hazard computation)
    # Note: Commitment delays are ~5-6h, so need to step past them for nonzero hazards
    vm.advance_time(15.0)

    # Check per-subpop hazards cached
    names = sorted(vessel.subpopulations.keys())

    for name in names:
        subpop = vessel.subpopulations[name]

        # Assert hazard fields exist
        assert '_total_hazard' in subpop, \
            f"Missing '_total_hazard' for {name}. Prereq B not applied?"
        assert '_hazards' in subpop, \
            f"Missing '_hazards' for {name}. Prereq B not applied?"

    # Extract hazards
    hazards = [vessel.subpopulations[n]['_total_hazard'] for n in names]

    # Assert they differ (sensitive has lower IC50 → higher hazard)
    unique_hazards = len(set(np.round(hazards, 9)))

    assert unique_hazards >= 2, \
        f"All subpop hazards equal: {hazards}. IC50 shifts not applied?"

    # Identify by IC50 shift
    subpops_by_shift = sorted(names, key=lambda n: vessel.subpopulations[n]['ic50_shift'])
    sensitive = subpops_by_shift[0]
    resistant = subpops_by_shift[-1]

    h_sens = vessel.subpopulations[sensitive]['_total_hazard']
    h_res = vessel.subpopulations[resistant]['_total_hazard']

    # Sensitive should have higher hazard at same dose
    assert h_sens > h_res, \
        f"Sensitive hazard ({h_sens:.6f}) not > resistant ({h_res:.6f}). " \
        f"IC50 shift logic inverted?"

    print(f"✓ Prereq B: Per-subpop hazards exist and differ")
    print(f"  Sensitive: {h_sens:.6f}/h, Resistant: {h_res:.6f}/h")


def test_prereq_b_commitment_delays_used():
    """Verify commitment delays from v3 are actually retrieved and used.

    This catches if commitment_delay_h parameter isn't passed to attrition function.
    """

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("v", "A549", initial_count=1e6, initial_viability=0.3)
    vessel = vm.vessel_states["v"]

    # Treat with lethal dose (triggers commitment delay sampling in v3)
    vm.treat_with_compound("v", "tunicamycin", 5.0)

    # Verify commitment delays exist (v3 contract)
    exposure_id = vessel.compound_meta.get('exposure_ids', {}).get('tunicamycin')
    assert exposure_id is not None, "v3 not merged? No exposure_id found"

    names = sorted(vessel.subpopulations.keys())
    delays = []

    for name in names:
        cache_key = ('tunicamycin', exposure_id, name)
        delay = vessel.compound_meta.get('commitment_delays', {}).get(cache_key)
        assert delay is not None, \
            f"v3 not merged? No commitment delay for {name}"
        delays.append(delay)

    # Delays should vary (heterogeneity)
    assert len(set(delays)) >= 2, \
        f"All delays equal: {delays}. v3 sampling broken?"

    print(f"✓ Prereq B: Commitment delays exist (v3 merged)")
    print(f"  Delays: {[f'{d:.1f}h' for d in delays]}")


if __name__ == "__main__":
    print("Running v4 prerequisite verification tests...\n")

    try:
        test_prereq_a_no_sync_after_step()
        print()
        test_prereq_b_per_subpop_hazards_exist()
        print()
        test_prereq_b_commitment_delays_used()
        print("\n✓ All prerequisites verified - Ready for v4 diffs")
    except AssertionError as e:
        print(f"\n✗ Prerequisite verification FAILED: {e}")
        print("\nDo NOT apply v4 diffs until prerequisites are fixed.")
        sys.exit(1)
