"""Quick test of DriftModel before full integration."""
import numpy as np
from src.cell_os.hardware.drift_model import DriftModel


def test_drift_model_basic():
    """Test DriftModel initialization and basic functionality."""
    drift = DriftModel(seed=42)

    # Test gain at different times
    times = [0, 24, 48, 72]

    print("\nImaging gains:")
    gains_imaging = []
    for t in times:
        gain = drift.get_gain(float(t), 'imaging')
        gains_imaging.append(gain)
        print(f"  t={t:2d}h: {gain:.6f}")

    print("\nReader gains:")
    gains_reader = []
    for t in times:
        gain = drift.get_gain(float(t), 'reader')
        gains_reader.append(gain)
        print(f"  t={t:2d}h: {gain:.6f}")

    # Test bounds
    assert all(0.85 <= g <= 1.15 for g in gains_imaging), "Imaging gains out of bounds"
    assert all(0.85 <= g <= 1.15 for g in gains_reader), "Reader gains out of bounds"

    # Test gains vary over time
    assert len(set(gains_imaging)) > 1, "Imaging gains don't vary"
    assert len(set(gains_reader)) > 1, "Reader gains don't vary"

    # Test determinism
    gain_0_repeat = drift.get_gain(0.0, 'imaging')
    assert gain_0_repeat == gains_imaging[0], "Drift is not deterministic"

    print("\n✓ All basic tests passed")


def test_drift_correlation():
    """Test correlation between imaging and reader drift."""
    drift = DriftModel(seed=42)

    t_grid = np.linspace(0.0, 72.0, 1000)
    gains_imaging = [drift.get_gain(t, 'imaging') for t in t_grid]
    gains_reader = [drift.get_gain(t, 'reader') for t in t_grid]

    corr = np.corrcoef(gains_imaging, gains_reader)[0, 1]
    print(f"\nPearson correlation: {corr:.4f}")
    print(f"Target range: [0.20, 0.50]")

    assert 0.05 < corr < 0.80, f"Correlation {corr:.4f} out of sanity bounds"
    print("✓ Correlation sanity check passed")


if __name__ == '__main__':
    test_drift_model_basic()
    test_drift_correlation()
