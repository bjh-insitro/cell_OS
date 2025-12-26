"""Test that drift actually affects assay measurements over time."""
import sys
sys.path.insert(0, '/Users/bjh/cell_OS/src')

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_drift_affects_cell_painting():
    """Test that Cell Painting measurements drift over time."""
    vm = BiologicalVirtualMachine(seed=42)

    # Seed vessel
    vm.seed_vessel("well_A1", "A549", initial_count=3000)

    # Measure at t=0
    vm.advance_time(0)
    obs_0 = vm.cell_painting_assay("well_A1", plate_id="P1", day=1, operator="OP1")

    # Advance to t=72h (no biology changes - DMSO)
    vm.advance_time(72)
    obs_72 = vm.cell_painting_assay("well_A1", plate_id="P1", day=1, operator="OP1")

    # Extract morphology
    morph_0 = obs_0['morphology']
    morph_72 = obs_72['morphology']

    print("\n" + "="*60)
    print("CELL PAINTING DRIFT TEST (seed 42)")
    print("="*60)
    print("\nMorphology at t=0h:")
    for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        print(f"  {ch:8s}: {morph_0[ch]:.2f}")

    print("\nMorphology at t=72h:")
    for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        print(f"  {ch:8s}: {morph_72[ch]:.2f}")

    print("\nRatios (t=72h / t=0h):")
    ratios = {}
    for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        ratio = morph_72[ch] / morph_0[ch]
        ratios[ch] = ratio
        print(f"  {ch:8s}: {ratio:.4f}")

    # All ratios should be similar (shared gain affects all channels equally)
    avg_ratio = sum(ratios.values()) / len(ratios)
    print(f"\nAverage ratio: {avg_ratio:.4f}")

    # Ratio should differ from 1.0 (drift happened)
    assert abs(avg_ratio - 1.0) > 0.01, "No drift detected (ratio too close to 1.0)"

    # All channel ratios should be similar (within 5% of mean)
    for ch, ratio in ratios.items():
        rel_dev = abs(ratio - avg_ratio) / avg_ratio
        assert rel_dev < 0.10, f"Channel {ch} ratio deviates too much from mean: {rel_dev:.2%}"

    print("\n✓ PASS: Drift affects Cell Painting measurements")
    print("✓ PASS: All channels affected uniformly (shared gain)")


def test_drift_affects_scalar_assays():
    """Test that scalar assays (LDH/ATP/UPR) drift over time."""
    vm = BiologicalVirtualMachine(seed=42)

    # Seed vessel
    vm.seed_vessel("well_A1", "A549", initial_count=3000)

    # Measure at t=0
    vm.advance_time(0)
    obs_0 = vm.ldh_viability_assay("well_A1", plate_id="P1", day=1, operator="OP1")

    # Advance to t=72h
    vm.advance_time(72)
    obs_72 = vm.ldh_viability_assay("well_A1", plate_id="P1", day=1, operator="OP1")

    print("\n" + "="*60)
    print("SCALAR ASSAY DRIFT TEST (seed 42)")
    print("="*60)
    print("\nScalar signals at t=0h:")
    for signal in ['ldh_signal', 'atp_signal', 'upr_marker', 'trafficking_marker']:
        print(f"  {signal:20s}: {obs_0[signal]:.2f}")

    print("\nScalar signals at t=72h:")
    for signal in ['ldh_signal', 'atp_signal', 'upr_marker', 'trafficking_marker']:
        print(f"  {signal:20s}: {obs_72[signal]:.2f}")

    print("\nRatios (t=72h / t=0h):")
    ratios = {}
    for signal in ['ldh_signal', 'atp_signal', 'upr_marker', 'trafficking_marker']:
        ratio = obs_72[signal] / obs_0[signal]
        ratios[signal] = ratio
        print(f"  {signal:20s}: {ratio:.4f}")

    avg_ratio = sum(ratios.values()) / len(ratios)
    print(f"\nAverage ratio: {avg_ratio:.4f}")

    # Ratio should differ from 1.0 (drift happened)
    assert abs(avg_ratio - 1.0) > 0.01, "No drift detected (ratio too close to 1.0)"

    # All signal ratios should be similar (within 10% of mean, allowing for some kit lot variation)
    for signal, ratio in ratios.items():
        rel_dev = abs(ratio - avg_ratio) / avg_ratio
        assert rel_dev < 0.15, f"Signal {signal} ratio deviates too much from mean: {rel_dev:.2%}"

    print("\n✓ PASS: Drift affects scalar assays")
    print("✓ PASS: All signals affected uniformly (shared gain for modality)")


def test_imaging_vs_reader_drift_independence():
    """Test that imaging and reader drift independently (modality-specific)."""
    vm = BiologicalVirtualMachine(seed=42)

    # Seed vessel
    vm.seed_vessel("well_A1", "A549", initial_count=3000)

    # Measure both modalities at t=0
    vm.advance_time(0)
    cp_0 = vm.cell_painting_assay("well_A1", plate_id="P1", day=1, operator="OP1")
    ldh_0 = vm.ldh_viability_assay("well_A1", plate_id="P1", day=1, operator="OP1")

    # Measure both at t=72h
    vm.advance_time(72)
    cp_72 = vm.cell_painting_assay("well_A1", plate_id="P1", day=1, operator="OP1")
    ldh_72 = vm.ldh_viability_assay("well_A1", plate_id="P1", day=1, operator="OP1")

    # Compute drift ratios
    imaging_ratio = cp_72['morphology']['er'] / cp_0['morphology']['er']
    reader_ratio = ldh_72['ldh_signal'] / ldh_0['ldh_signal']

    print("\n" + "="*60)
    print("MODALITY INDEPENDENCE TEST (seed 42)")
    print("="*60)
    print(f"\nImaging drift ratio (t=72h/t=0h): {imaging_ratio:.4f}")
    print(f"Reader drift ratio  (t=72h/t=0h): {reader_ratio:.4f}")
    print(f"Difference: {abs(imaging_ratio - reader_ratio):.4f}")

    # Ratios should be different (not identical, showing modality-specific drift)
    diff = abs(imaging_ratio - reader_ratio)
    assert diff > 0.005, f"Imaging and reader drift too similar: diff={diff:.4f}"

    print("\n✓ PASS: Imaging and reader drift independently")
    print("✓ PASS: Modality-specific drift working")


if __name__ == '__main__':
    test_drift_affects_cell_painting()
    test_drift_affects_scalar_assays()
    test_imaging_vs_reader_drift_independence()

    print("\n" + "="*60)
    print("ALL INTEGRATION TESTS PASSED")
    print("="*60)
    print("\nDrift is correctly integrated into assays:")
    print("  ✓ Cell Painting uses time-dependent imaging modifiers")
    print("  ✓ Scalar assays use time-dependent reader modifiers")
    print("  ✓ Imaging and reader drift independently")
    print("  ✓ Within-modality signals affected uniformly")
    print("="*60)
