"""
Fast contract tests for ADC quantization (analog-to-digital conversion).

Tests verify:
1. Dormant default preserves behavior (golden-preserving)
2. Step lattice (outputs are multiples of step)
3. Half-up rounding (explicit rounding behavior, not banker's)
4. Bits-derived step with ceiling
5. ValueError when bits>0 but ceiling<=0
6. Idempotence (quantize(quantize(y)) == quantize(y))
7. Monotone (preserves order)
8. Interaction with saturation

Runtime: <5 seconds (deterministic, no Monte Carlo)
"""

import pytest
from cell_os.hardware._impl import quantize_adc


def test_quantization_dormant_default_noop():
    """Dormant mode (bits=0, step=0.0) is no-op (golden-preserving)."""
    # Test primitive directly
    test_inputs = [0.0, 10.3, 50.7, 150.9, 800.1]

    for y in test_inputs:
        y_q = quantize_adc(y, step=0.0, bits=0)
        assert y_q == y, f"Dormant mode not no-op: y={y:.3f} → y_q={y_q:.3f}"

    print("✓ Dormant mode (bits=0, step=0.0) is no-op")


def test_quantization_step_lattice():
    """Step mode produces multiples of step (lattice structure)."""
    step = 0.5
    test_inputs = [0.0, 0.1, 0.3, 0.6, 1.0, 2.3, 5.7, 10.0]

    for y in test_inputs:
        y_q = quantize_adc(y, step=step)

        # Output should be multiple of step
        k = round(y_q / step)
        expected = k * step
        assert abs(y_q - expected) < 1e-9, \
            f"Not a lattice point: y={y:.3f} → y_q={y_q:.3f}, expected {expected:.3f}"

    print(f"✓ Step mode produces multiples of step={step}")


def test_quantization_half_up_rounding():
    """Half-up rounding (not banker's rounding)."""
    step = 1.0

    # Test explicit half-up cases
    test_cases = [
        (0.25, 0.0),  # Below half → floor
        (0.49, 0.0),  # Below half → floor
        (0.50, 1.0),  # Exactly half → up (NOT banker's 0)
        (0.51, 1.0),  # Above half → up
        (0.75, 1.0),  # Above half → up
        (1.50, 2.0),  # Half → up
        (2.50, 3.0),  # Half → up
        (3.50, 4.0),  # Half → up
    ]

    for y, expected in test_cases:
        y_q = quantize_adc(y, step=step, mode="round_half_up")
        assert y_q == expected, \
            f"Half-up rounding failed: y={y:.2f} → y_q={y_q:.2f}, expected {expected:.2f}"

    print("✓ Half-up rounding (floor(y + 0.5), not banker's)")


def test_quantization_bits_mode_with_ceiling():
    """Bits-mode derives step from ceiling."""
    ceiling = 800.0
    bits = 8  # 255 codes

    # Derived step = ceiling / (2^bits - 1) = 800 / 255 ≈ 3.137
    expected_step = ceiling / 255.0

    # Test various inputs
    test_cases = [
        (0.0, 0.0),          # Zero
        (100.0, None),       # Mid-range (check lattice)
        (800.0, 800.0),      # At ceiling
        (900.0, 800.0),      # Above ceiling (clamps)
    ]

    for y, expected_output in test_cases:
        y_q = quantize_adc(y, bits=bits, ceiling=ceiling)

        if expected_output is not None:
            assert y_q == expected_output, \
                f"Bits-mode failed: y={y:.1f} → y_q={y_q:.3f}, expected {expected_output:.3f}"
        else:
            # Check lattice structure
            k = round(y_q / expected_step)
            expected_lattice = k * expected_step
            assert abs(y_q - expected_lattice) < 1e-6, \
                f"Bits-mode not on lattice: y={y:.1f} → y_q={y_q:.3f}, step={expected_step:.3f}"

    print(f"✓ Bits-mode (bits={bits}, ceiling={ceiling}) derives step correctly")


def test_quantization_bits_mode_requires_ceiling():
    """Bits-mode raises ValueError if ceiling <= 0."""
    # Should raise ValueError
    with pytest.raises(ValueError, match="requires ceiling > 0"):
        quantize_adc(y=100.0, bits=12, ceiling=0.0)

    with pytest.raises(ValueError, match="requires ceiling > 0"):
        quantize_adc(y=100.0, bits=8, ceiling=-1.0)

    print("✓ Bits-mode raises ValueError when ceiling <= 0")


def test_quantization_idempotence():
    """Quantization is idempotent: quantize(quantize(y)) == quantize(y)."""
    step = 0.5
    test_inputs = [0.0, 1.3, 5.7, 10.2, 50.9, 100.3]

    for y in test_inputs:
        y_q1 = quantize_adc(y, step=step)
        y_q2 = quantize_adc(y_q1, step=step)

        assert y_q1 == y_q2, \
            f"Not idempotent: y={y:.3f} → y_q1={y_q1:.3f} → y_q2={y_q2:.3f}"

    print("✓ Quantization is idempotent")


def test_quantization_monotone():
    """Quantization preserves order (monotone)."""
    step = 1.0
    test_inputs = [0.0, 1.2, 2.4, 3.6, 5.8, 10.1, 20.3, 50.7]

    y_q_prev = -float('inf')
    for y in test_inputs:
        y_q = quantize_adc(y, step=step)

        assert y_q >= y_q_prev, \
            f"Not monotone: y={y:.3f} → y_q={y_q:.3f} < prev={y_q_prev:.3f}"

        y_q_prev = y_q

    print("✓ Quantization is monotone")


def test_quantization_with_saturation_interaction():
    """Quantization correctly handles saturated inputs."""
    ceiling = 600.0
    bits = 8  # 255 codes, step ≈ 2.35 AU

    # Test inputs that saturate first, then quantize
    from cell_os.hardware._impl import apply_saturation

    # High input: saturates at ceiling, then quantizes to ceiling
    y_high = 1000.0
    y_sat = apply_saturation(y_high, ceiling=ceiling, knee_start_frac=0.85, tau_frac=0.08)
    y_q = quantize_adc(y_sat, bits=bits, ceiling=ceiling)

    assert y_q <= ceiling, \
        f"Quantization after saturation exceeds ceiling: y={y_high:.1f} → y_sat={y_sat:.3f} → y_q={y_q:.3f}"

    # Quantization of ceiling should map to ceiling (boundary case)
    y_q_ceiling = quantize_adc(ceiling, bits=bits, ceiling=ceiling)
    assert y_q_ceiling == ceiling, \
        f"Ceiling not preserved: quantize(ceiling={ceiling}) = {y_q_ceiling:.3f}, expected {ceiling}"

    print("✓ Quantization interacts correctly with saturation")


def test_quantization_end_to_end_measurement():
    """End-to-end: quantization in Cell Painting pipeline (dormant default)."""
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    # Create VM with default config (quantization dormant)
    vm = BiologicalVirtualMachine(seed=42)

    # Seed and measure (quantization should be dormant)
    vm.seed_vessel("well_A1", "A549", initial_count=5000, capacity=1e6)
    vm.advance_time(12.0)

    # Measure twice (should be identical with same seed, quantization dormant)
    result1 = vm.cell_painting_assay("well_A1")
    result2 = vm.cell_painting_assay("well_A1")

    morph1 = result1['morphology']
    morph2 = result2['morphology']

    # With dormant quantization, measurements should still differ (stochastic noise)
    # But quantization itself shouldn't introduce errors when dormant
    # Just verify no crash
    assert morph1 is not None and morph2 is not None

    print("✓ End-to-end measurement with dormant quantization (no crash)")


def test_quantization_visible_banding_at_low_signal():
    """Quantization creates visible banding at low signal (coarse steps)."""
    ceiling = 800.0
    bits = 8  # 255 codes, step ≈ 3.14 AU

    # At low signal (y ~ 10-20 AU), step is ~30% of signal (very coarse)
    low_signal_inputs = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
    quantized_outputs = [quantize_adc(y, bits=bits, ceiling=ceiling) for y in low_signal_inputs]

    # Should see discrete jumps (not continuous)
    unique_outputs = len(set(quantized_outputs))
    assert unique_outputs < len(low_signal_inputs), \
        f"No banding observed: {len(low_signal_inputs)} inputs → {unique_outputs} unique outputs"

    # At least 2 consecutive inputs should map to same quantized value (banding)
    has_banding = any(
        quantized_outputs[i] == quantized_outputs[i+1]
        for i in range(len(quantized_outputs) - 1)
    )
    assert has_banding, "No banding observed at low signal"

    print(f"✓ Visible banding at low signal: {len(low_signal_inputs)} inputs → {unique_outputs} unique outputs")


def test_quantization_detector_metadata():
    """Detector metadata includes censoring flags for agent reasoning."""
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    # Create VM with saturation + quantization enabled
    vm = BiologicalVirtualMachine(seed=42)
    vm._load_cell_thalamus_params()

    # Enable saturation on all channels (required for bits-mode quantization)
    vm.thalamus_params['technical_noise']['saturation_ceiling_er'] = 200.0
    vm.thalamus_params['technical_noise']['saturation_ceiling_mito'] = 250.0
    vm.thalamus_params['technical_noise']['saturation_ceiling_nucleus'] = 300.0
    vm.thalamus_params['technical_noise']['saturation_ceiling_actin'] = 220.0
    vm.thalamus_params['technical_noise']['saturation_ceiling_rna'] = 240.0

    # Enable quantization (shared default, all channels)
    vm.thalamus_params['technical_noise']['adc_quant_bits_default'] = 8  # 255 codes

    # Enable additive floor only on ER (for SNR test)
    vm.thalamus_params['technical_noise']['additive_floor_sigma_er'] = 3.0

    # Seed and measure
    vm.seed_vessel("test_well", "A549", initial_count=5000, capacity=1e6)
    vm.advance_time(12.0)
    result = vm.cell_painting_assay("test_well")

    # Verify detector_metadata is present
    assert 'detector_metadata' in result, "detector_metadata missing from result"

    meta = result['detector_metadata']

    # Verify structure
    assert 'is_saturated' in meta
    assert 'is_quantized' in meta
    assert 'quant_step' in meta
    assert 'snr_floor_proxy' in meta

    # Verify per-channel data
    for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        assert ch in meta['is_saturated']
        assert ch in meta['is_quantized']
        assert ch in meta['quant_step']
        assert ch in meta['snr_floor_proxy']

    # Verify values for ER (saturation + quantization enabled)
    assert isinstance(meta['is_saturated']['er'], bool)
    assert meta['is_quantized']['er'] is True  # Quantization enabled
    assert meta['quant_step']['er'] > 0  # Non-zero step
    assert meta['snr_floor_proxy']['er'] is not None  # Additive floor enabled

    # Verify values for other channels (only quantization enabled, no saturation/floor)
    assert meta['is_saturated']['mito'] is False  # No saturation
    assert meta['is_quantized']['mito'] is True  # Quantization enabled (shared default)
    assert meta['snr_floor_proxy']['mito'] is None  # No additive floor

    print(f"✓ Detector metadata present with correct structure")
    print(f"  ER: saturated={meta['is_saturated']['er']}, quantized={meta['is_quantized']['er']}, "
          f"step={meta['quant_step']['er']:.3f}, snr={meta['snr_floor_proxy']['er']:.1f}")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
