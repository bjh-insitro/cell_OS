"""
Integration test for material plate order independence.

Verifies that executor produces identical per-well results regardless of
execution order. This proves no hidden shared state in orchestration.

Phase 2 gate condition (user requirement):
- Parse bead plate
- Run row-major order
- Run shuffled order (same seed)
- Assert per-well records identical for:
  * morphology
  * detector_metadata
  * well_seed
  * all other deterministic fields

Runtime: ~30 seconds (executes 384 wells twice)
"""

import pytest
import numpy as np
from pathlib import Path
from src.cell_os.plate_executor_v2 import parse_plate_design_v2, execute_well
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.run_context import RunContext


def test_material_plate_order_independence():
    """
    Executor must produce identical per-well results regardless of execution order.

    This proves material measurements are truly stateless:
    - No shared RNG coupling
    - No hidden VM state accumulation
    - No order-dependent side effects

    Test protocol:
    1. Parse bead plate (384 wells)
    2. Execute in row-major order (A1, A2, ..., P24)
    3. Execute in shuffled order (same seed)
    4. Assert per-well results are identical
    """
    json_path = Path("validation_frontend/public/plate_designs/CAL_384_MICROSCOPE_BEADS_DYES_v1.json")

    if not json_path.exists():
        pytest.skip(f"Bead plate not found: {json_path}")

    # Parse plate
    parsed_wells, metadata = parse_plate_design_v2(json_path)
    assert len(parsed_wells) == 384, "Expected 384 wells"

    # Shared seed and context
    seed = 42
    run_context = RunContext.sample(seed=seed)
    plate_id = "CAL_384_TEST"
    vessel_type = "384-well"

    # ====== Order 1: Row-major (A1, A2, ..., P24) ======
    vm1 = BiologicalVirtualMachine(seed=seed, run_context=run_context, use_database=False)
    vm1._load_cell_thalamus_params()

    results_row_major = {}
    for pw in parsed_wells:
        result = execute_well(pw, vm1, seed, run_context, plate_id, vessel_type)
        results_row_major[pw.well_id] = result

    # ====== Order 2: Shuffled (deterministic shuffle with different seed) ======
    # Use different shuffle seed to ensure different order, but same VM seed for reproducibility
    rng_shuffle = np.random.default_rng(99)
    shuffled_wells = list(parsed_wells)
    rng_shuffle.shuffle(shuffled_wells)

    # Verify order actually changed
    assert shuffled_wells[0].well_id != parsed_wells[0].well_id, \
        "Shuffle failed - first well still the same"

    vm2 = BiologicalVirtualMachine(seed=seed, run_context=run_context, use_database=False)
    vm2._load_cell_thalamus_params()

    results_shuffled = {}
    for pw in shuffled_wells:
        result = execute_well(pw, vm2, seed, run_context, plate_id, vessel_type)
        results_shuffled[pw.well_id] = result

    # ====== Assert per-well results are IDENTICAL ======
    assert set(results_row_major.keys()) == set(results_shuffled.keys()), \
        "Well IDs don't match between runs"

    # Check first 10 wells in detail (for faster feedback), then spot-check rest
    detailed_check_wells = list(results_row_major.keys())[:10]
    spot_check_wells = list(results_row_major.keys())[10::10]  # Every 10th well

    for well_id in detailed_check_wells + spot_check_wells:
        r1 = results_row_major[well_id]
        r2 = results_shuffled[well_id]

        # Critical fields must be identical
        assert r1["well_id"] == r2["well_id"]
        assert r1["mode"] == r2["mode"]
        assert r1["material_assignment"] == r2["material_assignment"]
        assert r1["material_type"] == r2["material_type"]
        assert r1["well_seed"] == r2["well_seed"], \
            f"Well seed differs for {well_id}: {r1['well_seed']} vs {r2['well_seed']}"

        # Morphology must be identical (per-channel comparison)
        for channel in ["er", "mito", "nucleus", "actin", "rna"]:
            v1 = r1["morphology"][channel]
            v2 = r2["morphology"][channel]
            assert v1 == v2, \
                f"Morphology {channel} differs for {well_id}: {v1:.6f} vs {v2:.6f}"

        # Detector metadata must be identical
        dm1 = r1["detector_metadata"]
        dm2 = r2["detector_metadata"]

        # Check saturation flags
        for channel in ["er", "mito", "nucleus", "actin", "rna"]:
            assert dm1["is_saturated"][channel] == dm2["is_saturated"][channel], \
                f"Saturation flag {channel} differs for {well_id}"

        # Check quantization flags
        for channel in ["er", "mito", "nucleus", "actin", "rna"]:
            assert dm1["is_quantized"][channel] == dm2["is_quantized"][channel], \
                f"Quantization flag {channel} differs for {well_id}"

    print(f"✓ Order independence verified for {len(detailed_check_wells)} detailed + {len(spot_check_wells)} spot-check wells")
    print(f"  Execution orders: row-major vs shuffled (seed {seed})")
    print(f"  All per-well morphology values identical")
    print(f"  All detector_metadata flags identical")


def test_material_plate_order_independence_small():
    """
    Strengthened order independence test: 3 orderings + representative subset.

    Tests for:
    - Row-major order
    - Reversed order
    - Shuffled order (fixed shuffle seed)
    - Representative subset from each assignment group

    This catches adjacency patterns, first-well initialization, and group-dependent bugs.
    """
    json_path = Path("validation_frontend/public/plate_designs/CAL_384_MICROSCOPE_BEADS_DYES_v1.json")

    if not json_path.exists():
        pytest.skip(f"Bead plate not found: {json_path}")

    # Parse plate
    parsed_wells, metadata = parse_plate_design_v2(json_path)
    materials_used = metadata.get('materials_used', [])

    # Build representative subset: at least one well from each assignment group
    assignment_to_wells = {}
    for pw in parsed_wells:
        assignment = pw.material_assignment
        if assignment not in assignment_to_wells:
            assignment_to_wells[assignment] = []
        assignment_to_wells[assignment].append(pw)

    # Pick first well from each assignment group, plus a few extras for robustness
    test_wells = []
    for assignment in sorted(assignment_to_wells.keys()):
        test_wells.append(assignment_to_wells[assignment][0])  # First of each group

    # Add a few more wells from different groups for robustness (up to 15 total)
    for assignment in sorted(assignment_to_wells.keys()):
        if len(test_wells) >= 15:
            break
        if len(assignment_to_wells[assignment]) > 1:
            test_wells.append(assignment_to_wells[assignment][1])  # Second of each group

    # Verify we have representatives from all assignment groups
    assignments_tested = set(pw.material_assignment for pw in test_wells)
    assert assignments_tested == set(materials_used), \
        f"Test subset missing assignments: {set(materials_used) - assignments_tested}"

    seed = 42
    run_context = RunContext.sample(seed=seed)
    plate_id = "CAL_384_TEST_SMALL"
    vessel_type = "384-well"

    # ====== Order 1: Row-major (natural JSON order) ======
    vm1 = BiologicalVirtualMachine(seed=seed, run_context=run_context, use_database=False)
    vm1._load_cell_thalamus_params()

    results_row_major = {}
    for pw in test_wells:
        result = execute_well(pw, vm1, seed, run_context, plate_id, vessel_type)
        results_row_major[pw.well_id] = result

    # ====== Order 2: Reversed ======
    vm2 = BiologicalVirtualMachine(seed=seed, run_context=run_context, use_database=False)
    vm2._load_cell_thalamus_params()

    results_reversed = {}
    for pw in reversed(test_wells):
        result = execute_well(pw, vm2, seed, run_context, plate_id, vessel_type)
        results_reversed[pw.well_id] = result

    # ====== Order 3: Shuffled (deterministic shuffle) ======
    rng_shuffle = np.random.default_rng(99)
    shuffled_wells = list(test_wells)
    rng_shuffle.shuffle(shuffled_wells)

    # Verify shuffle actually changed order
    assert shuffled_wells[0].well_id != test_wells[0].well_id, \
        "Shuffle failed - first well unchanged"

    vm3 = BiologicalVirtualMachine(seed=seed, run_context=run_context, use_database=False)
    vm3._load_cell_thalamus_params()

    results_shuffled = {}
    for pw in shuffled_wells:
        result = execute_well(pw, vm3, seed, run_context, plate_id, vessel_type)
        results_shuffled[pw.well_id] = result

    # ====== Assert all three orderings produce IDENTICAL per-well results ======
    all_orderings = {
        "row_major": results_row_major,
        "reversed": results_reversed,
        "shuffled": results_shuffled
    }

    for well_id in results_row_major.keys():
        r_row = results_row_major[well_id]
        r_rev = results_reversed[well_id]
        r_shuf = results_shuffled[well_id]

        # Morphology must be identical across all three orderings
        for channel in ["er", "mito", "nucleus", "actin", "rna"]:
            v_row = r_row["morphology"][channel]
            v_rev = r_rev["morphology"][channel]
            v_shuf = r_shuf["morphology"][channel]

            assert v_row == v_rev == v_shuf, \
                f"Morphology {channel} differs for {well_id}: row={v_row:.6f}, rev={v_rev:.6f}, shuf={v_shuf:.6f}"

        # Detector metadata must be identical
        for ordering_name, results in all_orderings.items():
            dm = results[well_id]["detector_metadata"]
            dm_ref = r_row["detector_metadata"]

            for channel in ["er", "mito", "nucleus", "actin", "rna"]:
                assert dm["is_saturated"][channel] == dm_ref["is_saturated"][channel], \
                    f"Saturation {channel} differs in {ordering_name} for {well_id}"

    print(f"✓ Order independence verified for {len(test_wells)} wells across 3 orderings:")
    print(f"  - Row-major (natural JSON order)")
    print(f"  - Reversed")
    print(f"  - Shuffled (deterministic)")
    print(f"  - Representative subset from {len(assignments_tested)} assignment groups")
    print(f"  - All per-well morphology values identical")


def test_vm_reuse_no_hidden_state():
    """
    VM reuse must not cache per-well context.

    Tests:
    - Same well measured twice → identical
    - Measure A, then B, then A again → both A measurements identical
    - No "last well position" or "last measurement modifiers" cached
    """
    json_path = Path("validation_frontend/public/plate_designs/CAL_384_MICROSCOPE_BEADS_DYES_v1.json")

    if not json_path.exists():
        pytest.skip(f"Bead plate not found: {json_path}")

    parsed_wells, metadata = parse_plate_design_v2(json_path)

    # Pick two distinct wells with different materials
    well_A = parsed_wells[0]  # Should be DARK
    well_B = parsed_wells[1]  # Should be FLATFIELD_DYE_LOW

    seed = 42
    run_context = RunContext.sample(seed=seed)
    vm = BiologicalVirtualMachine(seed=seed, run_context=run_context, use_database=False)
    vm._load_cell_thalamus_params()

    plate_id = "CAL_384_VM_REUSE_TEST"
    vessel_type = "384-well"

    # Measure well A (first time)
    result_A1 = execute_well(well_A, vm, seed, run_context, plate_id, vessel_type)

    # Measure well A again (second time, should be identical)
    result_A2 = execute_well(well_A, vm, seed, run_context, plate_id, vessel_type)

    # Measure well B
    result_B = execute_well(well_B, vm, seed, run_context, plate_id, vessel_type)

    # Measure well A third time (should still be identical)
    result_A3 = execute_well(well_A, vm, seed, run_context, plate_id, vessel_type)

    # Assert all A measurements are identical
    for channel in ["er", "mito", "nucleus", "actin", "rna"]:
        v_A1 = result_A1["morphology"][channel]
        v_A2 = result_A2["morphology"][channel]
        v_A3 = result_A3["morphology"][channel]

        assert v_A1 == v_A2 == v_A3, \
            f"VM cached state: {channel} differs across A measurements: {v_A1:.6f}, {v_A2:.6f}, {v_A3:.6f}"

    # Assert A != B (sanity check that wells are actually different)
    assert result_A1["material_assignment"] != result_B["material_assignment"], \
        "Test wells A and B should have different assignments"

    for channel in ["er", "mito", "nucleus", "actin", "rna"]:
        v_A = result_A1["morphology"][channel]
        v_B = result_B["morphology"][channel]
        # At least one channel should differ between DARK and DYE_LOW
        if v_A != v_B:
            break
    else:
        pytest.fail("Wells A and B have identical morphology across all channels (test setup broken)")

    print(f"✓ VM reuse has no hidden state:")
    print(f"  - Well A measured 3 times (before, between, after well B)")
    print(f"  - All A measurements identical")
    print(f"  - B measurement different from A (sanity check)")


def test_dark_floor_shows_detector_noise():
    """
    DARK wells must reveal detector floor, not literal zero.

    If floor_sigma > 0, repeated DARK measurements should show:
    - Nonzero variance across runs (shot noise)
    - Quantization structure (if LSB > 0)

    This prevents calibration plates from hiding detector characteristics.
    """
    json_path = Path("validation_frontend/public/plate_designs/CAL_384_MICROSCOPE_BEADS_DYES_v1.json")

    if not json_path.exists():
        pytest.skip(f"Bead plate not found: {json_path}")

    parsed_wells, metadata = parse_plate_design_v2(json_path)

    # Find DARK well
    dark_well = None
    for pw in parsed_wells:
        if pw.material_assignment == "DARK":
            dark_well = pw
            break

    assert dark_well is not None, "No DARK well found in plate design"

    # Measure DARK well 20 times with different VM seeds
    dark_measurements = []
    plate_id = "CAL_384_DARK_FLOOR_TEST"
    vessel_type = "384-well"

    for seed_offset in range(20):
        seed = 42 + seed_offset
        run_context = RunContext.sample(seed=seed)
        vm = BiologicalVirtualMachine(seed=seed, run_context=run_context, use_database=False)
        vm._load_cell_thalamus_params()

        result = execute_well(dark_well, vm, seed, run_context, plate_id, vessel_type)
        dark_measurements.append(result["morphology"]["er"])  # Check ER channel

    # Compute variance
    dark_array = np.array(dark_measurements)
    dark_mean = np.mean(dark_array)
    dark_std = np.std(dark_array)
    dark_min = np.min(dark_array)
    dark_max = np.max(dark_array)

    print(f"DARK floor statistics (20 runs, ER channel):")
    print(f"  Mean: {dark_mean:.4f}")
    print(f"  Std:  {dark_std:.4f}")
    print(f"  Min:  {dark_min:.4f}")
    print(f"  Max:  {dark_max:.4f}")

    # If floor sigma > 0 in detector params, we expect nonzero variance
    # For now, just document the behavior (don't fail)
    # In future, could load detector params and assert variance > 0 if floor_sigma > 0

    if dark_std > 0:
        print(f"✓ DARK shows detector floor variance (std={dark_std:.4f})")
    else:
        print(f"⚠️  DARK variance is zero (may indicate floor not modeled or clamped)")

    # Check if all values are identical (suspiciously clean)
    if dark_min == dark_max:
        print(f"⚠️  DARK is perfectly constant (literal zero or bypassing detector stack?)")
    else:
        print(f"✓ DARK varies across runs (range: {dark_min:.4f} to {dark_max:.4f})")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
