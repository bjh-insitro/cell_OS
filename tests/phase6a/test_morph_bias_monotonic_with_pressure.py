"""
Test morphology bias is monotonic and bounded with contact pressure.

Contract:
- Bias is deterministic (no RNG)
- Bias is monotonic (higher p → consistent direction per channel)
- Bias is bounded (coefficients control max shift)
- Specific channel directions:
  - nucleus: decreases with p
  - actin: increases with p
  - er: increases with p
  - mito: decreases with p
  - rna: decreases with p
"""

import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_morph_bias_monotonic():
    """
    Morphology bias should be monotonic with pressure.

    Each channel should shift consistently in one direction as pressure increases.
    """
    vm = BiologicalVirtualMachine()

    # Dummy morphology (all channels at baseline 1.0)
    morph_base = {
        'er': 1.0,
        'mito': 1.0,
        'nucleus': 1.0,
        'actin': 1.0,
        'rna': 1.0,
    }

    # Apply bias at different pressure levels
    morph_p0 = vm._apply_confluence_morphology_bias(morph_base.copy(), p=0.0)
    morph_p50 = vm._apply_confluence_morphology_bias(morph_base.copy(), p=0.5)
    morph_p100 = vm._apply_confluence_morphology_bias(morph_base.copy(), p=1.0)

    print("Channel shifts with pressure:")
    for ch in ['nucleus', 'actin', 'er', 'mito', 'rna']:
        v0 = morph_p0[ch]
        v50 = morph_p50[ch]
        v100 = morph_p100[ch]
        print(f"  {ch:8s}: p=0.0 → {v0:.4f}  |  p=0.5 → {v50:.4f}  |  p=1.0 → {v100:.4f}")

    # Assert monotonicity (direction matches declared coefficients)
    # nucleus: -8% → should decrease
    assert morph_p100['nucleus'] < morph_p50['nucleus'] < morph_p0['nucleus'], \
        "nucleus should decrease with pressure"

    # actin: +10% → should increase
    assert morph_p100['actin'] > morph_p50['actin'] > morph_p0['actin'], \
        "actin should increase with pressure"

    # er: +6% → should increase
    assert morph_p100['er'] > morph_p50['er'] > morph_p0['er'], \
        "er should increase with pressure"

    # mito: -5% → should decrease
    assert morph_p100['mito'] < morph_p50['mito'] < morph_p0['mito'], \
        "mito should decrease with pressure"

    # rna: -4% → should decrease
    assert morph_p100['rna'] < morph_p50['rna'] < morph_p0['rna'], \
        "rna should decrease with pressure"

    print("✓ Morphology bias monotonicity: PASS")


def test_morph_bias_bounded():
    """
    Morphology bias should not exceed declared coefficient bounds.

    At p=1.0, absolute shift should match coefficient magnitude.
    """
    vm = BiologicalVirtualMachine()

    morph_base = {
        'er': 1.0,
        'mito': 1.0,
        'nucleus': 1.0,
        'actin': 1.0,
        'rna': 1.0,
    }

    morph_p100 = vm._apply_confluence_morphology_bias(morph_base.copy(), p=1.0)

    # Declared coefficients (from implementation)
    expected_shifts = {
        'nucleus': -0.08,
        'actin': +0.10,
        'er': +0.06,
        'mito': -0.05,
        'rna': -0.04,
    }

    print("Channel shift bounds at p=1.0:")
    for ch, coeff in expected_shifts.items():
        observed = morph_p100[ch]
        expected = 1.0 * (1.0 + coeff)
        print(f"  {ch:8s}: observed={observed:.4f}, expected={expected:.4f}, diff={abs(observed-expected):.6f}")

        # Should match expected shift within floating-point tolerance
        assert abs(observed - expected) < 1e-6, \
            f"{ch} shift at p=1.0 not bounded: {observed:.4f} vs {expected:.4f}"

    print("✓ Morphology bias bounds: PASS")


def test_morph_bias_deterministic():
    """
    Morphology bias should be deterministic (no RNG).

    Repeated calls with same input should give identical output.
    """
    vm = BiologicalVirtualMachine()

    morph_base = {'er': 1.0, 'mito': 1.0, 'nucleus': 1.0, 'actin': 1.0, 'rna': 1.0}

    # Apply twice
    morph1 = vm._apply_confluence_morphology_bias(morph_base.copy(), p=0.7)
    morph2 = vm._apply_confluence_morphology_bias(morph_base.copy(), p=0.7)

    # Should be identical
    for ch in morph1:
        assert morph1[ch] == morph2[ch], \
            f"Morphology bias not deterministic: {ch} differs"

    print("✓ Morphology bias determinism: PASS")


def test_morph_bias_no_mutation():
    """
    Morphology bias should not mutate input dict.
    """
    vm = BiologicalVirtualMachine()

    morph_base = {'er': 1.0, 'mito': 1.0, 'nucleus': 1.0, 'actin': 1.0, 'rna': 1.0}
    morph_original = morph_base.copy()

    vm._apply_confluence_morphology_bias(morph_base, p=0.5)

    # Original should be unchanged
    assert morph_base == morph_original, \
        "Morphology bias mutated input dict"

    print("✓ Morphology bias no-mutation: PASS")


if __name__ == "__main__":
    test_morph_bias_monotonic()
    test_morph_bias_bounded()
    test_morph_bias_deterministic()
    test_morph_bias_no_mutation()
    print("\n✅ All morphology bias tests PASSED")
