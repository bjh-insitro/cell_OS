"""
Test that scalar assays (ATP/LDH/UPR/TRAFFICKING) respond to RunContext drift.

Fix: Biochemical readouts were living in a "sterile vacuum" immune to lot/instrument effects,
teaching agents "always trust scalars when they disagree with morphology" which doesn't transfer.

Now scalar assays get:
- reader_gain (plate reader instrument drift, correlated with imaging illumination_bias)
- scalar_assay_biases (per-assay kit lot effects, like channel_biases but for biochem)
"""

import sys
import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.run_context import RunContext


def test_scalar_assays_respond_to_reader_gain():
    """
    Test that scalar assays respond to RunContext reader_gain drift.

    Two contexts with different reader_gain should produce different scalar readouts
    from same biology.
    """
    # Create two contexts with different instrument_shift (affects reader_gain)
    ctx1 = RunContext.sample(seed=42, config={'context_strength': 0.0})  # Neutral
    ctx2 = RunContext.sample(seed=43, config={'context_strength': 2.0})  # Strong drift

    # Same biology, different measurement contexts
    vm1 = BiologicalVirtualMachine(seed=100, run_context=ctx1)
    vm1.seed_vessel("test_well", "A549", 1e6)
    vm1.treat_with_compound("test_well", "tunicamycin", dose_uM=1.0)
    vm1.advance_time(12.0)
    result1 = vm1.atp_viability_assay("test_well")

    vm2 = BiologicalVirtualMachine(seed=100, run_context=ctx2)
    vm2.seed_vessel("test_well", "A549", 1e6)
    vm2.treat_with_compound("test_well", "tunicamycin", dose_uM=1.0)
    vm2.advance_time(12.0)
    result2 = vm2.atp_viability_assay("test_well")

    # Check that readouts differ due to reader_gain
    print(f"Context 1 (neutral) reader_gain: {ctx1.get_measurement_modifiers()['reader_gain']:.3f}")
    print(f"Context 2 (strong) reader_gain: {ctx2.get_measurement_modifiers()['reader_gain']:.3f}")
    print(f"\nATP signal:")
    print(f"  Context 1: {result1['atp_signal']:.1f}")
    print(f"  Context 2: {result2['atp_signal']:.1f}")
    print(f"  Ratio: {result2['atp_signal'] / result1['atp_signal']:.3f}")

    # Readouts should differ (not identical despite same seed)
    ratio = result2['atp_signal'] / result1['atp_signal']
    if abs(ratio - 1.0) < 0.01:
        print(f"❌ FAIL: Readouts too similar (ratio={ratio:.3f}), reader_gain not applied")
        return False

    # Biology should be identical (same seed)
    if abs(vm1.vessel_states["test_well"].viability - vm2.vessel_states["test_well"].viability) > 1e-6:
        print(f"❌ FAIL: Biology differs across contexts (violates observer independence)")
        return False

    print(f"✓ PASS: Scalar assays respond to reader_gain (ratio={ratio:.3f})")
    return True


def test_scalar_assay_kit_lot_effects():
    """
    Test that per-assay kit lot biases work independently.

    ATP and UPR should have different lot multipliers even within same context.
    """
    ctx = RunContext.sample(seed=50, config={'context_strength': 1.5})
    meas_mods = ctx.get_measurement_modifiers()

    atp_bias = meas_mods['scalar_assay_biases']['ATP']
    ldh_bias = meas_mods['scalar_assay_biases']['LDH']
    upr_bias = meas_mods['scalar_assay_biases']['UPR']

    print(f"Scalar assay kit lot biases:")
    print(f"  ATP: {atp_bias:.3f}×")
    print(f"  LDH: {ldh_bias:.3f}×")
    print(f"  UPR: {upr_bias:.3f}×")

    # Biases should not be identical (independent lot sampling)
    if atp_bias == ldh_bias == upr_bias:
        print(f"❌ FAIL: All assay biases identical (not independent)")
        return False

    # Biases should be reasonable (0.8× to 1.2× roughly)
    for name, bias in [('ATP', atp_bias), ('LDH', ldh_bias), ('UPR', upr_bias)]:
        if bias < 0.7 or bias > 1.3:
            print(f"❌ FAIL: {name} bias out of range ({bias:.3f}×)")
            return False

    print(f"✓ PASS: Per-assay kit lot biases independent and reasonable")
    return True


def test_reader_gain_correlated_with_imaging():
    """
    Test that reader_gain (scalars) is correlated with illumination_bias (imaging).

    Both driven by instrument_shift, so cross-modality drift should be correlated.
    """
    # Sample many contexts and check correlation
    reader_gains = []
    illumination_biases = []

    for seed in range(100, 150):
        ctx = RunContext.sample(seed=seed, config={'context_strength': 1.0})
        meas_mods = ctx.get_measurement_modifiers()
        reader_gains.append(meas_mods['reader_gain'])
        illumination_biases.append(meas_mods['illumination_bias'])

    correlation = float(np.corrcoef(reader_gains, illumination_biases)[0, 1])

    print(f"Correlation between reader_gain and illumination_bias: {correlation:.3f}")
    print(f"  (Expected: ~1.0 since both from instrument_shift)")

    if abs(correlation - 1.0) > 0.1:
        print(f"❌ FAIL: Correlation too low ({correlation:.3f}), not properly shared")
        return False

    print(f"✓ PASS: reader_gain and illumination_bias strongly correlated (ρ={correlation:.3f})")
    return True


def test_no_double_application():
    """
    Test that run context modifiers are not double-applied.

    Verify that applying reader_gain + assay_bias doesn't stack with plate/day/operator factors.
    """
    # Create context with known gains
    ctx = RunContext.sample(seed=60, config={'context_strength': 0.0})  # Neutral context
    meas_mods = ctx.get_measurement_modifiers()

    # With neutral context, reader_gain should be ~1.0
    reader_gain = meas_mods['reader_gain']
    print(f"Neutral context reader_gain: {reader_gain:.4f}")

    if abs(reader_gain - 1.0) > 0.05:
        print(f"⚠ WARN: Neutral context reader_gain not ~1.0 ({reader_gain:.4f})")

    # Run assay and check output is reasonable
    vm = BiologicalVirtualMachine(seed=200, run_context=ctx)
    vm.seed_vessel("test_well", "A549", 1e6)
    result = vm.atp_viability_assay("test_well")

    atp_signal = result['atp_signal']
    print(f"ATP signal with neutral context: {atp_signal:.1f}")

    # Should be near baseline (~100), not wildly off
    if atp_signal < 50 or atp_signal > 200:
        print(f"❌ FAIL: ATP signal out of range ({atp_signal:.1f}), possible double-application")
        return False

    print(f"✓ PASS: No evidence of double-application (ATP signal reasonable)")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Scalar Assay Run Context Integration")
    print("=" * 70)
    print()

    tests = [
        ("Scalar assays respond to reader_gain", test_scalar_assays_respond_to_reader_gain),
        ("Per-assay kit lot effects independent", test_scalar_assay_kit_lot_effects),
        ("reader_gain correlated with imaging", test_reader_gain_correlated_with_imaging),
        ("No double-application of modifiers", test_no_double_application),
    ]

    results = []
    for name, test_func in tests:
        print(f"\nTest: {name}")
        print("-" * 70)
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ EXCEPTION: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
        print()

    print("=" * 70)
    print("Summary:")
    print("=" * 70)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    print()
    print(f"Total: {passed}/{total} passed")
    print("=" * 70)

    sys.exit(0 if passed == total else 1)
