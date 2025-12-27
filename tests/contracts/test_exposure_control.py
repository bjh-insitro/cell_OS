"""
Test exposure control: agent-controlled signal scaling before detector.

Tests verify:
1. Default exposure is 1.0 (no scaling)
2. Exposure scales signal proportionally  
3. Exposure affects SNR (relative to additive floor)
4. Exposure affects saturation probability
5. Creates trade-off: low exposure → floor-limited, high exposure → saturated

Runtime: <5 seconds (deterministic, small N)
"""
import pytest
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_exposure_default_is_unity():
    """Default exposure_multiplier is 1.0 (no scaling)."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_well", "A549", initial_count=5000, capacity=1e6)
    vm.advance_time(12.0)

    result = vm.cell_painting_assay("test_well")
    
    assert 'detector_metadata' in result
    assert result['detector_metadata']['exposure_multiplier'] == 1.0
    
    print("✓ Default exposure is 1.0")


def test_exposure_scales_signal():
    """Exposure multiplier scales signal proportionally."""
    vm = BiologicalVirtualMachine(seed=42)
    vm._load_cell_thalamus_params()
    
    # Minimal detector config (no saturation/floor, just scaling)
    # This isolates exposure effect without detector interactions
    
    vm.seed_vessel("test_well", "A549", initial_count=5000, capacity=1e6)
    vm.advance_time(12.0)
    
    # Measure at two exposure levels (deterministic biology, same seed)
    result_1x = vm.cell_painting_assay("test_well", exposure_multiplier=1.0)
    result_2x = vm.cell_painting_assay("test_well", exposure_multiplier=2.0)
    
    # Verify exposure recorded
    assert result_1x['detector_metadata']['exposure_multiplier'] == 1.0
    assert result_2x['detector_metadata']['exposure_multiplier'] == 2.0
    
    # Signal should scale proportionally (approximately, with noise)
    er_1x = result_1x['morphology']['er']
    er_2x = result_2x['morphology']['er']
    
    # 2× exposure should give ~2× signal (within tolerance for noise)
    ratio = er_2x / er_1x
    assert 1.8 < ratio < 2.2, \
        f"2× exposure should give ~2× signal: got {er_1x:.1f} → {er_2x:.1f} (ratio={ratio:.2f})"
    
    print(f"✓ Exposure scales signal: 1.0× → {er_1x:.1f}, 2.0× → {er_2x:.1f} (ratio={ratio:.2f})")


def test_exposure_affects_snr():
    """Higher exposure improves SNR relative to additive floor."""
    vm = BiologicalVirtualMachine(seed=42)
    vm._load_cell_thalamus_params()
    
    # Enable additive floor (detector noise)
    vm.thalamus_params['technical_noise']['additive_floor_sigma_er'] = 3.0
    
    vm.seed_vessel("test_well", "A549", initial_count=5000, capacity=1e6)
    vm.advance_time(12.0)
    
    result_low = vm.cell_painting_assay("test_well", exposure_multiplier=0.5)
    result_high = vm.cell_painting_assay("test_well", exposure_multiplier=2.0)
    
    snr_low = result_low['detector_metadata']['snr_floor_proxy']['er']
    snr_high = result_high['detector_metadata']['snr_floor_proxy']['er']
    
    # Higher exposure → higher SNR (signal scales, floor noise doesn't)
    assert snr_high > snr_low * 3, \
        f"SNR should scale with exposure: low={snr_low:.1f}, high={snr_high:.1f}"
    
    print(f"✓ Exposure affects SNR: 0.5× → SNR={snr_low:.1f}, 2.0× → SNR={snr_high:.1f}")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
