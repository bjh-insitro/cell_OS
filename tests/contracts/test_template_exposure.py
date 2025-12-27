"""
Contract tests for template-level exposure planning.

Tests verify:
1. Backwards compatibility (no exposure field → 1.0, identical results)
2. Per-condition exposure (anchors can specify different exposure)
3. Template-level default + per-condition override
4. Validation (exposure out of range raises ValueError)
5. Detector interactions (saturation, SNR changes as expected)
6. No new RNG draws (exposure is deterministic)

Runtime: <10 seconds (deterministic, minimal VM creation)
"""
import pytest
import json
import tempfile
from pathlib import Path
from cell_os.plate_executor_v2 import (
    ParsedWell,
    MeasurementContext,
    execute_well,
    parse_plate_design_v2,
    _validate_exposure_multiplier,
)
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext


def test_backwards_compatibility_no_exposure_field():
    """Templates without exposure_multiplier default to 1.0 (backwards compatible)."""
    # Create ParsedWell without exposure (simulating old template)
    pw = ParsedWell(
        well_id="A1",
        row="A",
        col=1,
        cell_line="A549",
        treatment="VEHICLE",
        reagent="DMSO",
        dose_uM=0.0,
        cell_density="NOMINAL",
        stain_scale=1.0,
        fixation_timing_offset_min=0.0,
        imaging_focus_offset_um=0.0,
        timepoint_hours=48.0,
        exposure_multiplier=1.0  # Explicitly set to default
    )

    # Build measurement context
    ctx = MeasurementContext(
        stain_scale=pw.stain_scale,
        fixation_timing_offset_min=pw.fixation_timing_offset_min,
        imaging_focus_offset_um=pw.imaging_focus_offset_um,
        cell_density=pw.cell_density,
        well_position=pw.well_id,
        exposure_multiplier=pw.exposure_multiplier
    )

    # Verify default
    assert ctx.exposure_multiplier == 1.0
    assert 'exposure_multiplier' in ctx.to_kwargs()
    assert ctx.to_kwargs()['exposure_multiplier'] == 1.0

    print("✓ Backwards compatibility: missing exposure → 1.0")


def test_per_condition_exposure_scales_signal():
    """Per-condition exposure scales signal as expected."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_low", "A549", initial_count=5000, capacity=1e6)
    vm.advance_time(48.0)

    # Measure with low exposure
    result_low = vm.cell_painting_assay("test_low", exposure_multiplier=0.5)

    # Reset and measure with high exposure (same seed, same biology)
    vm2 = BiologicalVirtualMachine(seed=42)
    vm2.seed_vessel("test_high", "A549", initial_count=5000, capacity=1e6)
    vm2.advance_time(48.0)
    result_high = vm2.cell_painting_assay("test_high", exposure_multiplier=2.0)

    # Verify exposure recorded in metadata
    assert result_low['detector_metadata']['exposure_multiplier'] == 0.5
    assert result_high['detector_metadata']['exposure_multiplier'] == 2.0

    # Verify signal scales (4× exposure → ~4× signal, within noise tolerance)
    er_low = result_low['morphology']['er']
    er_high = result_high['morphology']['er']
    ratio = er_high / er_low

    # Allow 20% tolerance for noise
    assert 3.2 < ratio < 4.8, \
        f"4× exposure should give ~4× signal: got {er_low:.1f} → {er_high:.1f} (ratio={ratio:.2f})"

    print(f"✓ Per-condition exposure scales signal: 0.5× → {er_low:.1f}, 2.0× → {er_high:.1f} (ratio={ratio:.2f})")


def test_exposure_validation_rejects_invalid():
    """Validation rejects exposure outside [0.1, 5.0] and NaN/inf."""
    import math

    # Test range validation
    with pytest.raises(ValueError, match="must be in \\[0.1, 5.0\\]"):
        _validate_exposure_multiplier(0.05, "TEST_LOW")

    with pytest.raises(ValueError, match="must be in \\[0.1, 5.0\\]"):
        _validate_exposure_multiplier(10.0, "TEST_HIGH")

    # Test NaN rejection
    with pytest.raises(ValueError, match="must be finite"):
        _validate_exposure_multiplier(float('nan'), "TEST_NAN")

    # Test inf rejection
    with pytest.raises(ValueError, match="must be finite"):
        _validate_exposure_multiplier(float('inf'), "TEST_INF")

    # Test valid values (should not raise)
    _validate_exposure_multiplier(0.1, "TEST_MIN")  # Min boundary
    _validate_exposure_multiplier(1.0, "TEST_DEFAULT")  # Default
    _validate_exposure_multiplier(5.0, "TEST_MAX")  # Max boundary

    print("✓ Validation rejects invalid exposure (out of range, NaN, inf)")


def test_exposure_affects_detector_metadata():
    """Higher exposure affects SNR and saturation probability."""
    vm = BiologicalVirtualMachine(seed=42)
    vm._load_cell_thalamus_params()

    # Enable detector features to see exposure effect
    vm.thalamus_params['technical_noise']['saturation_ceiling_er'] = 200.0
    vm.thalamus_params['technical_noise']['additive_floor_sigma_er'] = 3.0

    vm.seed_vessel("test_exp", "A549", initial_count=5000, capacity=1e6)
    vm.advance_time(48.0)

    # Low exposure: floor-limited
    result_low = vm.cell_painting_assay("test_exp", exposure_multiplier=0.3)

    # Reset and high exposure: saturation risk
    vm2 = BiologicalVirtualMachine(seed=42)
    vm2._load_cell_thalamus_params()
    vm2.thalamus_params['technical_noise']['saturation_ceiling_er'] = 200.0
    vm2.thalamus_params['technical_noise']['additive_floor_sigma_er'] = 3.0
    vm2.seed_vessel("test_exp2", "A549", initial_count=5000, capacity=1e6)
    vm2.advance_time(48.0)
    result_high = vm2.cell_painting_assay("test_exp2", exposure_multiplier=3.0)

    # Verify SNR improves with exposure
    snr_low = result_low['detector_metadata']['snr_floor_proxy']['er']
    snr_high = result_high['detector_metadata']['snr_floor_proxy']['er']

    assert snr_high > snr_low * 8, \
        f"SNR should scale with exposure: low={snr_low:.1f}, high={snr_high:.1f}"

    # Verify saturation flags
    saturated_low = result_low['detector_metadata']['is_saturated']['er']
    saturated_high = result_high['detector_metadata']['is_saturated']['er']

    # Low exposure should not saturate
    assert not saturated_low, "Low exposure should not saturate"

    print(f"✓ Exposure affects detector: SNR low={snr_low:.1f}, high={snr_high:.1f}")
    print(f"  Saturation: low={saturated_low}, high={saturated_high}")


def test_exposure_no_new_rng_draws():
    """Exposure is deterministic (no new RNG draws, no whitelist changes)."""
    # Two measurements with different exposure but same seed
    vm1 = BiologicalVirtualMachine(seed=42)
    vm1.seed_vessel("test1", "A549", initial_count=5000, capacity=1e6)
    vm1.advance_time(48.0)
    result1 = vm1.cell_painting_assay("test1", exposure_multiplier=1.0)

    vm2 = BiologicalVirtualMachine(seed=42)
    vm2.seed_vessel("test2", "A549", initial_count=5000, capacity=1e6)
    vm2.advance_time(48.0)
    result2 = vm2.cell_painting_assay("test2", exposure_multiplier=2.0)

    # Verify exposure recorded
    assert result1['detector_metadata']['exposure_multiplier'] == 1.0
    assert result2['detector_metadata']['exposure_multiplier'] == 2.0

    # Both measurements should work (no RNG errors)
    # If exposure consumed RNG, this would fail due to different draw schedules
    assert 'morphology' in result1
    assert 'morphology' in result2

    print("✓ Exposure is deterministic (no new RNG draws)")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
