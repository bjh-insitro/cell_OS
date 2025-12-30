"""Decompose drift components to diagnose correlation structure."""
import numpy as np
from src.cell_os.hardware.drift_model import DriftModel


def analyze_drift_components():
    """Decompose drift into components and compute correlations."""
    drift = DriftModel(seed=42)

    # Dense time grid
    t_grid = np.linspace(0.0, 72.0, 1000)

    # Extract components for both modalities
    components_imaging = [drift.debug_components(t, 'imaging') for t in t_grid]
    components_reader = [drift.debug_components(t, 'reader') for t in t_grid]

    # Extract each component as separate arrays
    def extract(components, key):
        return np.array([c[key] for c in components])

    aging_imaging = extract(components_imaging, 'aging')
    aging_reader = extract(components_reader, 'aging')

    cycle_imaging = extract(components_imaging, 'cycle')
    cycle_reader = extract(components_reader, 'cycle')

    wander_shared_imaging = extract(components_imaging, 'wander_shared')
    wander_shared_reader = extract(components_reader, 'wander_shared')

    wander_total_imaging = extract(components_imaging, 'wander_total')
    wander_total_reader = extract(components_reader, 'wander_total')

    gain_raw_imaging = extract(components_imaging, 'gain_raw')
    gain_raw_reader = extract(components_reader, 'gain_raw')

    gain_clamped_imaging = extract(components_imaging, 'gain_clamped')
    gain_clamped_reader = extract(components_reader, 'gain_clamped')

    # Compute correlations
    print("\n" + "="*60)
    print("COMPONENT CORRELATION ANALYSIS (Seed 42)")
    print("="*60)

    def corr(x, y):
        return np.corrcoef(x, y)[0, 1]

    print("\n1. Shared wander correlation:")
    corr_shared_wander = corr(wander_shared_imaging, wander_shared_reader)
    print(f"   corr(shared_wander_imaging, shared_wander_reader) = {corr_shared_wander:.4f}")
    print(f"   Expected: ~1.00 (should be identical)")
    if abs(corr_shared_wander - 1.0) < 0.01:
        print("   ✓ PASS: Shared wander is truly shared")
    else:
        print("   ✗ FAIL: Shared wander is NOT shared (wiring bug)")

    print("\n2. Total wander correlation:")
    corr_total_wander = corr(wander_total_imaging, wander_total_reader)
    print(f"   corr(total_wander_imaging, total_wander_reader) = {corr_total_wander:.4f}")
    print(f"   Expected: [0.10, 0.70] (alpha mixing working)")
    if 0.05 < corr_total_wander < 0.80:
        print("   ✓ PASS: Alpha mixing creates positive correlation")
    else:
        print("   ✗ FAIL: Alpha mixing not working as expected")

    print("\n3. Cycle correlation:")
    corr_cycle = corr(cycle_imaging, cycle_reader)
    print(f"   corr(cycle_imaging, cycle_reader) = {corr_cycle:.4f}")
    print(f"   Expected: ~0.00 (different periods, independent phases)")
    if abs(corr_cycle) < 0.3:
        print("   ✓ PASS: Cycles are independent")
    else:
        print("   ⚠ WARNING: Cycles are correlated (phases may be linked)")

    print("\n4. Aging correlation:")
    corr_aging = corr(aging_imaging, aging_reader)
    print(f"   corr(aging_imaging, aging_reader) = {corr_aging:.4f}")
    print(f"   Expected: ~1.00 (both monotone decay)")
    if corr_aging > 0.90:
        print("   ✓ PASS: Aging terms are correlated (both decay)")
    else:
        print("   ⚠ WARNING: Aging terms less correlated than expected")

    print("\n5. Final gain correlation:")
    corr_gain_raw = corr(gain_raw_imaging, gain_raw_reader)
    corr_gain_clamped = corr(gain_clamped_imaging, gain_clamped_reader)
    print(f"   corr(gain_raw_imaging, gain_raw_reader) = {corr_gain_raw:.4f}")
    print(f"   corr(gain_clamped_imaging, gain_clamped_reader) = {corr_gain_clamped:.4f}")
    print(f"   Expected: variable, depends on component mix")
    if corr_gain_clamped < -0.5:
        print("   ✗ FAIL: Strongly negative (structural issue)")
    elif corr_gain_clamped < 0:
        print("   ⚠ WARNING: Weakly negative (component interference)")
    else:
        print("   ✓ PASS: Positive correlation")

    # Compute stddevs to see which component dominates
    print("\n" + "="*60)
    print("COMPONENT MAGNITUDE ANALYSIS")
    print("="*60)

    print("\nStandard deviation of each component over time:")
    print(f"  aging_imaging:        {np.std(aging_imaging):.6f}")
    print(f"  aging_reader:         {np.std(aging_reader):.6f}")
    print(f"  cycle_imaging:        {np.std(cycle_imaging):.6f}")
    print(f"  cycle_reader:         {np.std(cycle_reader):.6f}")
    print(f"  wander_total_imaging: {np.std(wander_total_imaging):.6f} (log-space)")
    print(f"  wander_total_reader:  {np.std(wander_total_reader):.6f} (log-space)")

    # Convert wander to multiplicative space for comparison
    wander_mult_imaging = np.exp(wander_total_imaging)
    wander_mult_reader = np.exp(wander_total_reader)
    print(f"\n  wander_mult_imaging:  {np.std(wander_mult_imaging):.6f} (multiplicative)")
    print(f"  wander_mult_reader:   {np.std(wander_mult_reader):.6f} (multiplicative)")

    print(f"\n  gain_raw_imaging:     {np.std(gain_raw_imaging):.6f}")
    print(f"  gain_raw_reader:      {np.std(gain_raw_reader):.6f}")
    print(f"  gain_clamped_imaging: {np.std(gain_clamped_imaging):.6f}")
    print(f"  gain_clamped_reader:  {np.std(gain_clamped_reader):.6f}")

    # Identify dominant component
    print("\n" + "="*60)
    print("DIAGNOSIS")
    print("="*60)

    aging_range_imaging = np.max(aging_imaging) - np.min(aging_imaging)
    cycle_range_imaging = np.max(cycle_imaging) - np.min(cycle_imaging)
    wander_mult_range_imaging = np.max(wander_mult_imaging) - np.min(wander_mult_imaging)

    print(f"\nRange (max - min) for imaging components:")
    print(f"  Aging:  {aging_range_imaging:.6f} ({aging_range_imaging/aging_imaging[0]*100:.2f}% of baseline)")
    print(f"  Cycle:  {cycle_range_imaging:.6f} ({cycle_range_imaging/1.0*100:.2f}% of neutral)")
    print(f"  Wander: {wander_mult_range_imaging:.6f} ({wander_mult_range_imaging/1.0*100:.2f}% of neutral)")

    dominant = max([
        ('aging', aging_range_imaging),
        ('cycle', cycle_range_imaging),
        ('wander', wander_mult_range_imaging)
    ], key=lambda x: x[1])

    print(f"\nDominant component: {dominant[0]} (range={dominant[1]:.6f})")

    if corr_gain_clamped < 0:
        print("\nWhy is final gain correlation negative?")
        if abs(corr_cycle) > 0.3:
            print("  → Cycles may be anti-phase (periods differ, phases random)")
        if corr_aging > 0.9 and corr_total_wander > 0.3:
            print("  → Aging and wander are positive, but cycles dominate and flip sign")
        if dominant[0] == 'cycle':
            print("  → Cycle component dominates, overwhelming positive wander/aging correlation")

    print("\n" + "="*60)
    print("RECOMMENDATION")
    print("="*60)

    if abs(corr_shared_wander - 1.0) > 0.01:
        print("✗ FIX: Shared wander is not shared. Check wiring.")
    elif corr_total_wander < 0.1:
        print("⚠ CONSIDER: Increase ALPHA_SHARED or reduce modality sigma")
    elif dominant[0] == 'cycle' and corr_gain_clamped < 0:
        print("✓ ACCEPT: Negative correlation is due to cycle phase interference")
        print("  This is expected variation, not a bug.")
        print("  Some runs will have positive correlation, some negative.")
    else:
        print("✓ ACCEPT: Drift structure is working as designed")

    print("="*60)


if __name__ == '__main__':
    analyze_drift_components()
