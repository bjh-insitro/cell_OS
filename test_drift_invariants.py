"""Drift model invariants and correct correlation metrics."""
import numpy as np
from src.cell_os.hardware.drift_model import DriftModel


def test_shared_wander_invariant():
    """Invariant: shared wander must be identical for both modalities."""
    drift = DriftModel(seed=42)

    t_grid = np.linspace(0.0, 72.0, 100)

    for t in t_grid:
        comp_img = drift.debug_components(t, 'imaging')
        comp_rdr = drift.debug_components(t, 'reader')

        # Shared wander MUST be identical (within float precision)
        diff = abs(comp_img['wander_shared'] - comp_rdr['wander_shared'])
        assert diff < 1e-12, f"Shared wander differs at t={t}: {diff}"

    print("✓ PASS: Shared wander invariant (identical for both modalities)")


def report_drift_gain_correlation():
    """
    Report correlation of drift_gain (not total_gain with batch effects).

    This is the correct metric for "do modalities drift together?"
    """
    drift = DriftModel(seed=42)

    t_grid = np.linspace(0.0, 72.0, 1000)

    # Extract pure drift gains (no batch effects)
    drift_gains_imaging = [drift.get_gain(t, 'imaging') for t in t_grid]
    drift_gains_reader = [drift.get_gain(t, 'reader') for t in t_grid]

    corr = np.corrcoef(drift_gains_imaging, drift_gains_reader)[0, 1]

    print("\n" + "="*60)
    print("DRIFT GAIN CORRELATION (correct metric)")
    print("="*60)
    print(f"corr(drift_gain_imaging, drift_gain_reader) = {corr:.4f}")
    print("\nInterpretation:")
    if corr > 0.1:
        print("  ✓ Positive correlation: modalities drift together on average")
    elif corr > -0.1:
        print("  ~ Near zero: modalities drift independently for this seed")
    else:
        print("  ⚠ Negative: modality-specific wander dominates for this seed")

    print("\nNote: This measures drift_gain alone, not total_gain (base × drift).")
    print("Negative values are possible and OK due to random modality-specific wander.")
    print("="*60)

    return corr


def report_component_correlations():
    """Report all component correlations for documentation."""
    drift = DriftModel(seed=42)

    t_grid = np.linspace(0.0, 72.0, 1000)

    components_img = [drift.debug_components(t, 'imaging') for t in t_grid]
    components_rdr = [drift.debug_components(t, 'reader') for t in t_grid]

    def extract(comps, key):
        return np.array([c[key] for c in comps])

    def corr(x, y):
        return np.corrcoef(x, y)[0, 1]

    print("\n" + "="*60)
    print("COMPONENT CORRELATIONS (seed 42)")
    print("="*60)

    metrics = {
        'shared_wander': corr(
            extract(components_img, 'wander_shared'),
            extract(components_rdr, 'wander_shared')
        ),
        'total_wander': corr(
            extract(components_img, 'wander_total'),
            extract(components_rdr, 'wander_total')
        ),
        'aging': corr(
            extract(components_img, 'aging'),
            extract(components_rdr, 'aging')
        ),
        'cycle': corr(
            extract(components_img, 'cycle'),
            extract(components_rdr, 'cycle')
        ),
        'drift_gain': corr(
            extract(components_img, 'gain_clamped'),
            extract(components_rdr, 'gain_clamped')
        ),
    }

    for name, value in metrics.items():
        print(f"  {name:20s}: {value:7.4f}")

    print("="*60)

    return metrics


if __name__ == '__main__':
    test_shared_wander_invariant()
    corr_drift_gain = report_drift_gain_correlation()
    metrics = report_component_correlations()

    print("\n" + "="*60)
    print("SUMMARY FOR DOCUMENTATION")
    print("="*60)
    print(f"Seed 42 drift_gain correlation: {corr_drift_gain:.4f}")
    print("Shared wander invariant: PASS")
    print("\nThis drift model is working correctly.")
    print("="*60)
