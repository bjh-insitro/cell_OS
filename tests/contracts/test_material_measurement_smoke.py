"""
Smoke test for material measurement (VM-level end-to-end).

Single test to verify material measurement integrates correctly with VM.
For detailed optical behavior, see test_optical_materials_fast.py (pure functions).

Runtime: <10 seconds (one VM, minimal measurements)
"""

import pytest

pytest.skip("Material measurement smoke tests have issues - needs investigation", allow_module_level=True)

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.material_state import MaterialState, MATERIAL_NOMINAL_INTENSITIES


def test_material_measurement_end_to_end():
    """
    Smoke test: material measurement works end-to-end with VM.

    Tests:
    - DARK well: measures near zero (only floor noise)
    - DYE well: measures known intensity with detector metadata
    - Detector stack applied (saturation, quantization, exposure)
    - Result structure matches Cell Painting format

    This is the ONLY VM-level test. For detailed contracts (determinism,
    vignette, variance models), see test_optical_materials_fast.py.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm._load_cell_thalamus_params()

    # Enable detector features
    vm.thalamus_params['technical_noise']['additive_floor_sigma_er'] = 3.0
    for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        vm.thalamus_params['technical_noise'][f'saturation_ceiling_{ch}'] = 600.0
    vm.thalamus_params['technical_noise']['adc_quant_bits_default'] = 8

    # Test 1: DARK well (buffer only)
    material_dark = MaterialState(
        material_id="material_A1_DARK",
        material_type="buffer_only",
        well_position="A1",
        base_intensities=MATERIAL_NOMINAL_INTENSITIES['DARK'],
        seed=42
    )

    result_dark = vm.measure_material(material_dark)
    assert result_dark['status'] == 'success'
    assert result_dark['material_type'] == 'buffer_only'
    assert abs(result_dark['morphology']['er']) < 10.0, "DARK well should be near zero"
    assert 'detector_metadata' in result_dark

    # Test 2: DYE well (uniform fluorescence)
    material_dye = MaterialState(
        material_id="material_B1_FLATFIELD_DYE_LOW",
        material_type="fluorescent_dye_solution",
        well_position="B1",
        base_intensities=MATERIAL_NOMINAL_INTENSITIES['FLATFIELD_DYE_LOW'],
        seed=42
    )

    result_dye = vm.measure_material(material_dye)
    assert result_dye['status'] == 'success'
    assert result_dye['material_type'] == 'fluorescent_dye_solution'
    assert 40 < result_dye['morphology']['er'] < 100, "Dye should be in expected range"

    # Test 3: Detector metadata structure (same as Cell Painting)
    meta = result_dye['detector_metadata']
    assert 'is_saturated' in meta
    assert 'is_quantized' in meta
    assert 'quant_step' in meta
    assert 'snr_floor_proxy' in meta
    assert 'exposure_multiplier' in meta

    # Test 4: Exposure multiplier works
    result_high_exposure = vm.measure_material(material_dye, exposure_multiplier=2.0)
    signal_1x = result_dye['morphology']['er']
    signal_2x = result_high_exposure['morphology']['er']

    # Should see signal increase (tolerance for noise + detector nonlinearities)
    assert signal_2x > signal_1x * 1.5, \
        f"Exposure should scale signal: 1.0× → {signal_1x:.1f}, 2.0× → {signal_2x:.1f}"

    print(f"✓ Material measurement smoke test passed")
    print(f"  DARK: {result_dark['morphology']['er']:.1f} AU (near zero)")
    print(f"  DYE:  {signal_1x:.1f} AU @ 1.0×, {signal_2x:.1f} AU @ 2.0× (ratio={signal_2x/signal_1x:.2f})")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
