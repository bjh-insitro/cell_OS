"""
Contract tests for material measurement (beads, dyes, buffer).

Tests verify:
1. DARK wells measure floor only (no signal)
2. Dye solutions have low variance (no biology)
3. High dye intensity tests saturation
4. Beads: dense has lower variance than sparse (averaging)
5. Materials reuse detector stack (same metadata structure)
6. Exposure multiplier works for materials

Runtime: <5 seconds (deterministic, minimal VM creation)
"""

import pytest
import numpy as np
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.material_state import (
    MaterialState,
    MATERIAL_NOMINAL_INTENSITIES,
    BEAD_COUNTS
)


def test_dark_wells_measure_floor_only():
    """DARK wells should measure only detector floor (no signal)."""
    vm = BiologicalVirtualMachine(seed=42)
    vm._load_cell_thalamus_params()

    # Enable additive floor
    vm.thalamus_params['technical_noise']['additive_floor_sigma_er'] = 3.0
    vm.thalamus_params['technical_noise']['additive_floor_sigma_mito'] = 3.0

    # Create DARK material
    material = MaterialState(
        material_id="material_A1_DARK",
        material_type="buffer_only",
        well_position="A1",
        base_intensities=MATERIAL_NOMINAL_INTENSITIES['DARK'],
        seed=42
    )
    vm.material_states = {material.material_id: material}

    # Measure multiple times
    measurements = []
    for _ in range(20):
        result = vm.measure_material(material.material_id)
        measurements.append(result['morphology']['er'])

    # Mean should be near 0 (within floor noise)
    mean_signal = np.mean(measurements)
    assert abs(mean_signal) < 10.0, \
        f"DARK well mean should be near 0, got {mean_signal:.1f}"

    # Variance should be consistent with floor sigma (~3.0)
    std_signal = np.std(measurements)
    assert 1.5 < std_signal < 6.0, \
        f"DARK well std should match floor sigma, got {std_signal:.1f}"

    print(f"✓ DARK well: mean={mean_signal:.1f}, std={std_signal:.1f} (floor-limited)")


def test_flatfield_dye_low_no_biology_variance():
    """Dye solutions have low variance (no biology)."""
    vm = BiologicalVirtualMachine(seed=42)
    vm._load_cell_thalamus_params()

    # Create FLATFIELD_DYE_LOW material
    material = MaterialState(
        material_id="material_B1_FLATFIELD_DYE_LOW",
        material_type="fluorescent_dye_solution",
        well_position="B1",
        base_intensities=MATERIAL_NOMINAL_INTENSITIES['FLATFIELD_DYE_LOW'],
        seed=42
    )
    vm.material_states = {material.material_id: material}

    # Measure 100× (same seed, but rng_assay advances)
    measurements = []
    for _ in range(100):
        result = vm.measure_material(material.material_id)
        measurements.append(result['morphology']['er'])

    # CV should be low (~3% from dye mixing, NOT ~15% from biology)
    mean_signal = np.mean(measurements)
    std_signal = np.std(measurements)
    cv = std_signal / mean_signal

    assert cv < 0.10, \
        f"Dye CV should be low (no biology variance), got {cv*100:.1f}%"

    # Mean should be close to nominal intensity
    nominal = MATERIAL_NOMINAL_INTENSITIES['FLATFIELD_DYE_LOW']['er']
    assert 0.8 * nominal < mean_signal < 1.2 * nominal, \
        f"Mean should be near nominal {nominal:.1f}, got {mean_signal:.1f}"

    print(f"✓ Dye solution: mean={mean_signal:.1f}, CV={cv*100:.1f}% (low variance, no biology)")


def test_flatfield_dye_high_tests_saturation():
    """High dye intensity should trigger saturation at high exposure."""
    vm = BiologicalVirtualMachine(seed=42)
    vm._load_cell_thalamus_params()

    # Enable saturation (ceiling = 600 AU)
    vm.thalamus_params['technical_noise']['saturation_ceiling_er'] = 600.0

    # Create FLATFIELD_DYE_HIGH material
    material = MaterialState(
        material_id="material_C1_FLATFIELD_DYE_HIGH",
        material_type="fluorescent_dye_solution",
        well_position="C1",
        base_intensities=MATERIAL_NOMINAL_INTENSITIES['FLATFIELD_DYE_HIGH'],
        seed=42
    )
    vm.material_states = {material.material_id: material}

    # Measure at high exposure (should saturate)
    result_high = vm.measure_material(material.material_id, exposure_multiplier=3.0)

    # Check saturation flag
    is_saturated = result_high['detector_metadata']['is_saturated']['er']
    signal = result_high['morphology']['er']

    # With exposure=3.0, signal = 400 × 3 = 1200, should saturate at 600
    assert is_saturated, "High exposure should saturate"
    assert signal <= 600.1, f"Saturated signal should be ≤ ceiling, got {signal:.1f}"

    # Measure at low exposure (should NOT saturate)
    result_low = vm.measure_material(material.material_id, exposure_multiplier=1.0)
    assert not result_low['detector_metadata']['is_saturated']['er'], \
        "Low exposure should not saturate"

    print(f"✓ High dye: saturated={is_saturated}, signal={signal:.1f} (tests saturation)")


def test_beads_sparse_vs_dense_averaging():
    """Dense beads have lower variance than sparse (averaging)."""
    vm = BiologicalVirtualMachine(seed=42)
    vm._load_cell_thalamus_params()

    # Create sparse beads material
    material_sparse = MaterialState(
        material_id="material_D1_MULTICOLOR_BEADS_SPARSE",
        material_type="fluorescent_beads",
        well_position="D1",
        base_intensities=MATERIAL_NOMINAL_INTENSITIES['MULTICOLOR_BEADS_SPARSE'],
        spatial_pattern='sparse',
        seed=42
    )

    # Create dense beads material
    material_dense = MaterialState(
        material_id="material_E1_MULTICOLOR_BEADS_DENSE",
        material_type="fluorescent_beads",
        well_position="E1",
        base_intensities=MATERIAL_NOMINAL_INTENSITIES['MULTICOLOR_BEADS_DENSE'],
        spatial_pattern='dense',
        seed=43  # Different seed
    )

    vm.material_states = {
        material_sparse.material_id: material_sparse,
        material_dense.material_id: material_dense
    }

    # Measure sparse beads 20× (reduced for speed)
    measurements_sparse = []
    for _ in range(20):
        result = vm.measure_material(material_sparse.material_id)
        measurements_sparse.append(result['morphology']['er'])

    # Measure dense beads 20× (reduced for speed)
    measurements_dense = []
    for _ in range(20):
        result = vm.measure_material(material_dense.material_id)
        measurements_dense.append(result['morphology']['er'])

    # Compute CVs
    cv_sparse = np.std(measurements_sparse) / np.mean(measurements_sparse)
    cv_dense = np.std(measurements_dense) / np.mean(measurements_dense)

    # Dense should have lower variance (CV_dense < CV_sparse)
    assert cv_dense < cv_sparse, \
        f"Dense beads should have lower variance: CV_sparse={cv_sparse*100:.1f}%, CV_dense={cv_dense*100:.1f}%"

    # Ratio should show clear difference (>1.5×)
    # Note: theoretical sqrt(N_dense/N_sparse) = sqrt(100/10) ≈ 3.16, but
    # detector artifacts (floor noise, quantization) reduce the ratio by adding
    # variance that doesn't scale with bead count
    ratio = cv_sparse / cv_dense
    assert ratio > 1.5, \
        f"CV ratio should show clear averaging effect (>1.5×), got {ratio:.2f}"

    print(f"✓ Beads averaging: CV_sparse={cv_sparse*100:.1f}%, CV_dense={cv_dense*100:.1f}% (ratio={ratio:.2f})")


def test_material_reuses_detector_stack():
    """Materials go through same detector as cells (identical metadata structure)."""
    vm = BiologicalVirtualMachine(seed=42)
    vm._load_cell_thalamus_params()

    # Enable all detector features (saturation required for bits-mode quantization)
    vm.thalamus_params['technical_noise']['additive_floor_sigma_er'] = 3.0
    # Enable saturation on all channels (required for bits-mode quantization)
    for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        vm.thalamus_params['technical_noise'][f'saturation_ceiling_{ch}'] = 600.0
    vm.thalamus_params['technical_noise']['adc_quant_bits_default'] = 8

    # Create material
    material = MaterialState(
        material_id="material_F1_FLATFIELD_DYE_LOW",
        material_type="fluorescent_dye_solution",
        well_position="F1",
        base_intensities=MATERIAL_NOMINAL_INTENSITIES['FLATFIELD_DYE_LOW'],
        seed=42
    )
    vm.material_states = {material.material_id: material}

    # Measure material
    result = vm.measure_material(material.material_id)

    # Verify detector_metadata structure (same as Cell Painting)
    assert 'detector_metadata' in result
    meta = result['detector_metadata']

    # Verify all fields present
    assert 'is_saturated' in meta
    assert 'is_quantized' in meta
    assert 'quant_step' in meta
    assert 'snr_floor_proxy' in meta
    assert 'exposure_multiplier' in meta

    # Verify per-channel data
    for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        assert ch in meta['is_saturated']
        assert ch in meta['is_quantized']
        assert ch in meta['quant_step']
        assert ch in meta['snr_floor_proxy']

    # Verify values make sense
    assert meta['exposure_multiplier'] == 1.0  # Default
    assert meta['is_quantized']['er'] is True  # Quantization enabled
    assert meta['quant_step']['er'] > 0  # Non-zero step
    assert meta['snr_floor_proxy']['er'] is not None  # Floor enabled

    print("✓ Material detector_metadata has identical structure to Cell Painting")


def test_exposure_multiplier_works_for_materials():
    """Exposure multiplier scales material signal (same as cells)."""
    vm = BiologicalVirtualMachine(seed=42)
    vm._load_cell_thalamus_params()

    # Create material
    material = MaterialState(
        material_id="material_G1_FLATFIELD_DYE_LOW",
        material_type="fluorescent_dye_solution",
        well_position="G1",
        base_intensities=MATERIAL_NOMINAL_INTENSITIES['FLATFIELD_DYE_LOW'],
        seed=42
    )
    vm.material_states = {material.material_id: material}

    # Measure at 1× exposure
    result_1x = vm.measure_material(material.material_id, exposure_multiplier=1.0)

    # Measure at 2× exposure (deterministic material, same dye variance seed)
    # NOTE: RNG advances from first measurement, so variance seed differs
    result_2x = vm.measure_material(material.material_id, exposure_multiplier=2.0)

    signal_1x = result_1x['morphology']['er']
    signal_2x = result_2x['morphology']['er']

    # Ratio should be ~2.0 (within tolerance for dye mixing noise)
    # Tolerance is wider than pure 2.0 because:
    # 1. Dye mixing noise (~3% CV) is independent per measurement
    # 2. Additive floor (if enabled) doesn't scale with exposure
    ratio = signal_2x / signal_1x
    assert 1.7 < ratio < 2.3, \
        f"2× exposure should give ~2× signal: got {signal_1x:.1f} → {signal_2x:.1f} (ratio={ratio:.2f})"

    # Verify exposure recorded in metadata
    assert result_1x['detector_metadata']['exposure_multiplier'] == 1.0
    assert result_2x['detector_metadata']['exposure_multiplier'] == 2.0

    print(f"✓ Exposure scales material signal: 1.0× → {signal_1x:.1f}, 2.0× → {signal_2x:.1f} (ratio={ratio:.2f})")


def test_material_measurement_no_biology_coupling():
    """Material measurements don't access VesselState biology fields."""
    vm = BiologicalVirtualMachine(seed=42)
    vm._load_cell_thalamus_params()

    # Create material WITHOUT creating any vessels
    material = MaterialState(
        material_id="material_H1_DARK",
        material_type="buffer_only",
        well_position="H1",
        base_intensities=MATERIAL_NOMINAL_INTENSITIES['DARK'],
        seed=42
    )
    vm.material_states = {material.material_id: material}

    # Verify no vessels exist
    assert len(vm.vessel_states) == 0, "Should have no vessels"

    # Measure material (should work without any vessels)
    result = vm.measure_material(material.material_id)

    # Verify result structure
    assert result['status'] == 'success'
    assert result['material_type'] == 'buffer_only'
    assert 'morphology' in result
    assert 'detector_metadata' in result

    # Verify no vessels were created
    assert len(vm.vessel_states) == 0, "Material measurement should not create vessels"

    print("✓ Material measurement works without any biology (no vessels needed)")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
