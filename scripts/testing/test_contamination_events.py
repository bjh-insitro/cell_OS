#!/usr/bin/env python3
"""
Minimal test: Run one regime with 10× contamination rate and verify events are generated.

Expected: ~16-17 events over 32 vessels × 168h with 10× rate.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cell_os.calibration.identifiability_runner_2d1 import run_regime, design_vessel_ids, design_sampling_times

def main():
    print("=" * 80)
    print("CONTAMINATION EVENT TEST: Regime B (10× rate)")
    print("=" * 80)
    print("Config: 32 vessels × 168h")
    print("Expected: ~16-17 contamination events")
    print()

    # Regime B config (10× enriched rate)
    contamination_config = {
        'enabled': True,
        'baseline_rate_per_vessel_day': 0.005,
        'rate_multiplier': 10.0,
        'type_probs': {'bacterial': 0.5, 'fungal': 0.2, 'mycoplasma': 0.3},
    }

    vessel_ids = design_vessel_ids(32, 'B_enriched')
    sampling_times = design_sampling_times(168.0, 6.0)

    result = run_regime(
        regime_label='B_enriched',
        contamination_config=contamination_config,
        vessel_ids=vessel_ids,
        sampling_times=sampling_times,
        cell_line='HEK293',
        initial_count=5000,
        run_seed=2000,
    )

    n_events = len(result['ground_truth'])
    print()
    print("=" * 80)
    print(f"RESULT: {n_events} contamination events detected")
    print("=" * 80)

    if n_events < 5:
        print("❌ FAIL: Too few events (expected ~16-17)")
        print()
        print("Event details:")
        for evt in result['ground_truth']:
            print(f"  {evt['vessel_id']}: {evt['contamination_type']} at {evt['contamination_onset_h']:.1f}h")
        sys.exit(1)
    elif n_events > 30:
        print("❌ FAIL: Too many events (expected ~16-17)")
        sys.exit(1)
    else:
        print(f"✅ PASS: Event count in expected range [5, 30]")
        print()
        print("Event breakdown:")
        types = {}
        for evt in result['ground_truth']:
            ctype = evt['contamination_type']
            types[ctype] = types.get(ctype, 0) + 1
            print(f"  {evt['vessel_id']}: {ctype} at {evt['contamination_onset_h']:.1f}h")
        print()
        print("By type:")
        for ctype, count in sorted(types.items()):
            print(f"  {ctype}: {count}")
        sys.exit(0)

if __name__ == "__main__":
    main()
