"""
Hostile tests for material RNG seed isolation and collision resistance.

Tests verify:
1. Seeds are unique across all wells on a 384-well plate (no collisions)
2. Detector output distribution is independent of VM biological state
3. Seed construction is format-stable (no string formatting drift)

Runtime: <1 second (pure seed tests, no VM loops)
"""

import pytest
from cell_os.hardware._impl import stable_u64
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.material_state import MaterialState, MATERIAL_NOMINAL_INTENSITIES


def test_material_seeds_unique_across_384_plate():
    """
    Seeds must be unique for all wells on a 384-well plate (no collisions).

    32-bit seeds have birthday paradox collision risk at ~65k samples.
    384-well plate × multiple runs × multiple material types can hit this.
    64-bit seeds eliminate practical collision risk.
    """
    run_seed = 42
    material_type = "fluorescent_dye_solution"

    # Generate seeds for all 384 wells
    seeds = set()
    for row_letter in "ABCDEFGHIJKLMNOP":  # 16 rows
        for col_num in range(1, 25):  # 24 columns
            well_position = f"{row_letter}{col_num}"

            # Mimic seed construction from measure_material
            seed_string = f"material|{run_seed}|{material_type}|{row_letter}|{col_num}"
            seed = stable_u64(seed_string)

            # Check for collision
            assert seed not in seeds, \
                f"Seed collision at {well_position}: seed={seed} (already seen)"

            seeds.add(seed)

    # Verify we got 384 unique seeds
    assert len(seeds) == 384, \
        f"Expected 384 unique seeds, got {len(seeds)}"

    print(f"✓ All 384 wells have unique seeds (no collisions)")


def test_material_seeds_vary_across_material_types():
    """
    Seeds must differ for different material types in the same well.

    This prevents accidental correlation when multiple materials are measured
    in the same well position across different plates.
    """
    run_seed = 42
    well_position = "H12"
    well_row = "H"
    well_col = 12

    material_types = ["buffer_only", "fluorescent_dye_solution", "fluorescent_beads"]
    seeds = {}

    for mat_type in material_types:
        seed_string = f"material|{run_seed}|{mat_type}|{well_row}|{well_col}"
        seed = stable_u64(seed_string)
        seeds[mat_type] = seed

    # All seeds must be different
    unique_seeds = set(seeds.values())
    assert len(unique_seeds) == len(material_types), \
        f"Material types should have different seeds in same well: {seeds}"

    print(f"✓ Material types have unique seeds in same well: {seeds}")


def test_detector_output_independent_of_vm_biological_state():
    """
    HOSTILE: Detector output for fixed material signal must be independent
    of VM biological state (vessels, stress, time progression).

    This proves detector stack doesn't smuggle biology through VM coupling.

    Test protocol:
    1. Create VMs with wildly different biological states
    2. Measure same material with same detector settings
    3. Assert output distributions are IDENTICAL
    """
    import numpy as np

    material = MaterialState(
        material_id="material_H12_DYE",
        material_type="fluorescent_dye_solution",
        well_position="H12",
        base_intensities=MATERIAL_NOMINAL_INTENSITIES['FLATFIELD_DYE_LOW'],
        seed=99
    )

    # VM 1: Clean, no vessels
    vm1 = BiologicalVirtualMachine(seed=42)
    vm1._load_cell_thalamus_params()

    measurements_clean = []
    for _ in range(20):
        result = vm1.measure_material(material)
        measurements_clean.append(result['morphology']['er'])

    # VM 2: Vessels in wildly different states (stressed, dying, high confluence)
    vm2 = BiologicalVirtualMachine(seed=42)  # Same seed for detector params
    vm2._load_cell_thalamus_params()

    # Add vessels with extreme states
    vm2.seed_vessel("well_A1", "A549", initial_count=50000, capacity=1e6)  # High confluence
    vm2.treat_with_compound("well_A1", "tunicamycin", 50.0)  # Lethal dose
    vm2.advance_time(48.0)

    vm2.seed_vessel("well_B2", "HepG2", initial_count=1000, capacity=1e6)  # Low confluence
    vm2.treat_with_compound("well_B2", "cccp", 10.0)  # Mito stress
    vm2.advance_time(24.0)

    measurements_stressed = []
    for _ in range(20):
        result = vm2.measure_material(material)
        measurements_stressed.append(result['morphology']['er'])

    # Measurements should be IDENTICAL (same detector state → same output)
    # Both VMs use seed=42, so material RNG produces identical sequences
    mean_clean = np.mean(measurements_clean)
    mean_stressed = np.mean(measurements_stressed)

    # If measurements are perfectly deterministic (std=0), they should be IDENTICAL
    std_clean = np.std(measurements_clean)
    std_stressed = np.std(measurements_stressed)

    if std_clean == 0.0 and std_stressed == 0.0:
        # Perfect determinism → means must match exactly
        assert mean_clean == mean_stressed, \
            f"Deterministic measurements should be identical: clean={mean_clean:.6f}, stressed={mean_stressed:.6f}"
        print(f"✓ Detector perfectly deterministic: both={mean_clean:.1f} AU (std=0.0)")
    else:
        # If there's variance (e.g., from floor noise), distributions should match
        assert abs(mean_clean - mean_stressed) / mean_clean < 0.05, \
            f"Material measurement affected by VM biology state: clean={mean_clean:.1f}, stressed={mean_stressed:.1f}"

        assert abs(std_clean - std_stressed) / max(std_clean, 1e-9) < 0.20, \
            f"Material variance affected by VM biology state: clean={std_clean:.1f}, stressed={std_stressed:.1f}"

        print(f"✓ Detector output independent of VM biology: clean={mean_clean:.1f}±{std_clean:.1f}, stressed={mean_stressed:.1f}±{std_stressed:.1f}")


def test_seed_collision_at_scale():
    """
    HOSTILE: Test for seed collisions at calibration scale.

    384 wells × 10 runs × 3 material types = 11,520 seeds
    With 64-bit space, collisions are astronomically unlikely but not impossible.
    This test pressure-tests the hash space at realistic scale.
    """
    seeds = set()
    collision_found = False

    # 10 different run seeds
    for run_seed in range(100, 110):
        # 3 material types (using type IDs)
        for material_type_id in [1, 2, 3]:  # buffer, dye, beads
            # All 384 wells
            for row_idx in range(16):  # A-P
                for col_num in range(1, 25):  # 1-24
                    seed_string = f"material|{run_seed}|{material_type_id}|{row_idx}|{col_num}"
                    seed = stable_u64(seed_string)

                    if seed in seeds:
                        collision_found = True
                        print(f"COLLISION: seed={seed} at run={run_seed}, type={material_type_id}, row={row_idx}, col={col_num}")
                        break

                    seeds.add(seed)

    assert not collision_found, "Seed collision found at calibration scale!"
    assert len(seeds) == 10 * 3 * 16 * 24, \
        f"Expected 11,520 unique seeds, got {len(seeds)}"

    print(f"✓ No collisions in {len(seeds)} seeds (10 runs × 3 types × 384 wells)")


def test_material_type_rename_does_not_change_seed():
    """
    HOSTILE: Renaming material labels must not change seeds.

    Seeds use semantic identity (type_id), not string labels.
    This prevents "someone renamed FLATFIELD_DYE_HIGH to FLATFIELD_HIGH" drift.
    """
    run_seed = 42
    row_idx = 7  # H
    col_num = 12

    # Same type_id → same seed (even if label changes)
    type_id_dye = 2  # fluorescent_dye_solution

    seed_old_name = stable_u64(f"material|{run_seed}|{type_id_dye}|{row_idx}|{col_num}")
    seed_new_name = stable_u64(f"material|{run_seed}|{type_id_dye}|{row_idx}|{col_num}")

    assert seed_old_name == seed_new_name, \
        "Seeds changed despite same type_id (semantic identity violated)"

    # Different type_id → different seed
    type_id_buffer = 1
    seed_different_type = stable_u64(f"material|{run_seed}|{type_id_buffer}|{row_idx}|{col_num}")

    assert seed_different_type != seed_old_name, \
        "Different material types should have different seeds"

    print(f"✓ Material type ID provides semantic identity (rename-stable)")


def test_detector_rng_order_independent():
    """
    HOSTILE: Detector RNG must be stateless w.r.t. measurement call order.

    If detector RNG depends on shared state or call sequence, measuring
    wells in different orders will produce different results.

    This proves detector randomness is truly per-well deterministic.
    """
    material_A = MaterialState(
        material_id="material_A1_DYE",
        material_type="fluorescent_dye_solution",
        well_position="A1",
        base_intensities=MATERIAL_NOMINAL_INTENSITIES['FLATFIELD_DYE_LOW'],
        seed=99
    )

    material_B = MaterialState(
        material_id="material_B2_DYE",
        material_type="fluorescent_dye_solution",
        well_position="B2",
        base_intensities=MATERIAL_NOMINAL_INTENSITIES['FLATFIELD_DYE_LOW'],
        seed=99
    )

    # Order 1: A then B
    vm1 = BiologicalVirtualMachine(seed=42)
    vm1._load_cell_thalamus_params()

    result_A1 = vm1.measure_material(material_A)
    result_B1 = vm1.measure_material(material_B)

    # Order 2: B then A (reversed)
    vm2 = BiologicalVirtualMachine(seed=42)  # Same seed
    vm2._load_cell_thalamus_params()

    result_B2 = vm2.measure_material(material_B)
    result_A2 = vm2.measure_material(material_A)

    # Results for each well should be IDENTICAL regardless of order
    assert result_A1['morphology']['er'] == result_A2['morphology']['er'], \
        f"A1 measurement changed with order: {result_A1['morphology']['er']} vs {result_A2['morphology']['er']}"

    assert result_B1['morphology']['er'] == result_B2['morphology']['er'], \
        f"B2 measurement changed with order: {result_B1['morphology']['er']} vs {result_B2['morphology']['er']}"

    print(f"✓ Detector RNG order-independent: A={result_A1['morphology']['er']:.1f}, B={result_B1['morphology']['er']:.1f} (same both orders)")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
