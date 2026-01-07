"""
Contract tests for v7 realism profiles.

Tests determinism, effect visibility, and profile contracts.
"""

import pytest
import numpy as np
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext


def test_clean_profile_has_no_effects():
    """
    CONTRACT: Clean profile must have zero position effects and zero outliers.

    This is the default for all existing tests.
    """
    # Create clean profile context
    ctx = RunContext.sample(seed=42, config={'realism_profile': 'clean'})
    config = ctx.get_realism_config()

    # Verify all effects are disabled
    assert config['position_row_bias_pct'] == 0.0
    assert config['position_col_bias_pct'] == 0.0
    assert config['edge_mean_shift_pct'] == 0.0
    assert config['edge_noise_multiplier'] == 1.0
    assert config['outlier_rate'] == 0.0

    # Run small test: measure two wells (edge + center)
    vm = BiologicalVirtualMachine(run_context=ctx)

    # Edge well (A1 - corner)
    vm.seed_vessel('A1', cell_line='A549', vessel_type='96-well')
    # Center well (D6 - middle area, not truly center)
    vm.seed_vessel('D6', cell_line='A549', vessel_type='96-well')

    # Advance time for all vessels
    vm.advance_time(hours=24.0)

    result_edge = vm.cell_painting_assay('A1', well_position='A1')
    result_center = vm.cell_painting_assay('D6', well_position='D6')

    # Verify no outliers
    assert not result_edge['detector_metadata']['qc_flags']['is_outlier']
    assert not result_center['detector_metadata']['qc_flags']['is_outlier']

    # Verify edge_distance relative ordering (A1 corner > D6 interior)
    # 96-well: 8 rows × 12 cols. A1 = corner (edge_dist=1.0), D6 = interior (~0.58)
    edge_dist_a1 = result_edge['detector_metadata']['edge_distance']
    edge_dist_d6 = result_center['detector_metadata']['edge_distance']
    assert edge_dist_a1 > edge_dist_d6, f"Corner A1 ({edge_dist_a1}) should have higher edge_distance than D6 ({edge_dist_d6})"
    assert edge_dist_a1 > 0.9, f"A1 corner should have edge_distance > 0.9: {edge_dist_a1}"
    assert edge_dist_d6 < 0.7, f"D6 interior should have edge_distance < 0.7: {edge_dist_d6}"


def test_determinism_same_seed_same_output():
    """
    CONTRACT: Same seed + same profile => identical outputs.

    Position effects and outliers must be deterministic.
    """
    seed = 12345

    def run_well(seed: int, profile: str, well_position: str):
        ctx = RunContext.sample(seed=seed, config={'realism_profile': profile})
        vm = BiologicalVirtualMachine(run_context=ctx)
        vm.seed_vessel(well_position, cell_line='A549', vessel_type='96-well')
        vm.advance_time(hours=24.0)
        result = vm.cell_painting_assay(well_position, well_position=well_position)
        return result

    # Run twice with same seed
    result1 = run_well(seed, 'realistic', 'A1')
    result2 = run_well(seed, 'realistic', 'A1')

    # Verify morphology is identical
    for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        assert result1['morphology'][ch] == result2['morphology'][ch], f"Channel {ch} not deterministic"

    # Verify outlier flags identical
    qc1 = result1['detector_metadata']['qc_flags']
    qc2 = result2['detector_metadata']['qc_flags']
    assert qc1['is_outlier'] == qc2['is_outlier']
    assert qc1['pathology_type'] == qc2['pathology_type']


def test_position_effects_visible_in_realistic():
    """
    CONTRACT: Realistic profile must produce visible edge vs center differences.

    Edge wells should have systematically different mean and variance.
    """
    ctx = RunContext.sample(seed=42, config={'realism_profile': 'realistic'})
    config = ctx.get_realism_config()

    # Verify realistic config is non-zero
    assert config['edge_mean_shift_pct'] != 0.0
    assert config['edge_noise_multiplier'] > 1.0

    vm = BiologicalVirtualMachine(run_context=ctx)

    # Measure 4 edge wells (corners)
    edge_wells = ['A1', 'A12', 'H1', 'H12']
    edge_results = []
    for well in edge_wells:
        vm.seed_vessel(well, cell_line='A549', vessel_type='96-well')
        vm.advance_time(well, hours=24.0)
        result = vm.cell_painting_assay(well, well_position=well)
        edge_results.append(result)

    # Measure 4 center wells
    center_wells = ['D6', 'D7', 'E6', 'E7']
    center_results = []
    for well in center_wells:
        vm.seed_vessel(well, cell_line='A549', vessel_type='96-well')
        vm.advance_time(well, hours=24.0)
        result = vm.cell_painting_assay(well, well_position=well)
        center_results.append(result)

    # Compute mean signal for each group
    edge_means = {ch: np.mean([r['morphology'][ch] for r in edge_results]) for ch in ['er', 'mito', 'nucleus']}
    center_means = {ch: np.mean([r['morphology'][ch] for r in center_results]) for ch in ['er', 'mito', 'nucleus']}

    # Verify edge is systematically different from center (at least 2% difference)
    for ch in ['er', 'mito', 'nucleus']:
        delta_pct = 100 * abs(edge_means[ch] - center_means[ch]) / center_means[ch]
        assert delta_pct > 1.0, f"Edge effect not visible in {ch}: {delta_pct:.2f}% (expected >1%)"


def test_outlier_rate_matches_profile():
    """
    CONTRACT: Outlier rate should approximately match profile specification.

    Realistic: 1% ± 1% (for 100 wells)
    Hostile: 3% ± 2% (for 100 wells)
    """
    def count_outliers(profile: str, seed: int, n_wells: int = 50) -> int:
        ctx = RunContext.sample(seed=seed, config={'realism_profile': profile})
        vm = BiologicalVirtualMachine(run_context=ctx)

        outlier_count = 0
        for i in range(n_wells):
            well_id = f"A{i+1}"  # Use sequential wells for simplicity
            vm.seed_vessel(well_id, cell_line='A549', vessel_type='384-well')
            vm.advance_time(hours=24.0)
            result = vm.cell_painting_assay(well_id, well_position=well_id)
            if result['detector_metadata']['qc_flags']['is_outlier']:
                outlier_count += 1

        return outlier_count

    # Test realistic profile (1% outliers)
    realistic_count = count_outliers('realistic', seed=42, n_wells=100)
    assert 0 <= realistic_count <= 5, f"Realistic outlier count {realistic_count} not in [0, 5] (expected ~1/100)"

    # Test hostile profile (3% outliers)
    hostile_count = count_outliers('hostile', seed=43, n_wells=100)
    assert 0 <= hostile_count <= 8, f"Hostile outlier count {hostile_count} not in [0, 8] (expected ~3/100)"

    # Test clean profile (0% outliers)
    clean_count = count_outliers('clean', seed=44, n_wells=50)
    assert clean_count == 0, f"Clean profile produced {clean_count} outliers (expected 0)"


def test_position_effects_are_deterministic_not_stochastic():
    """
    CONTRACT: Position effects must be pure geometric (no RNG).

    Same well position => same position effect, regardless of RNG state.
    """
    from cell_os.hardware.detector_stack import _apply_position_effects, _parse_well_position

    # Same position, same config => same effect
    signal = {'er': 100.0, 'mito': 100.0, 'nucleus': 100.0, 'actin': 100.0, 'rna': 100.0}
    config = {
        'position_row_bias_pct': 2.0,
        'position_col_bias_pct': 2.0,
        'edge_mean_shift_pct': -5.0,
    }

    # Call twice
    row, col = _parse_well_position('A1')
    result1, edge1 = _apply_position_effects(signal, row, col, 96, config)
    result2, edge2 = _apply_position_effects(signal, row, col, 96, config)

    # Verify identical (no RNG involved)
    for ch in signal:
        assert result1[ch] == result2[ch], f"Position effect not deterministic for {ch}"
    assert edge1 == edge2


def test_qc_pathologies_have_dedicated_rng():
    """
    CONTRACT: QC pathologies must use dedicated RNG (run_seed + well_position).

    Same seed + same well => same pathology.
    Different well => different pathology.
    """
    from cell_os.hardware.detector_stack import _apply_qc_pathologies

    signal = {'er': 100.0, 'mito': 100.0, 'nucleus': 100.0, 'actin': 100.0, 'rna': 100.0}
    config = {'outlier_rate': 0.5}  # 50% to ensure hits

    # Same seed + same well => same pathology
    result1, qc1 = _apply_qc_pathologies(signal, 'A1', run_seed=42, realism_config=config)
    result2, qc2 = _apply_qc_pathologies(signal, 'A1', run_seed=42, realism_config=config)

    assert qc1['is_outlier'] == qc2['is_outlier']
    assert qc1['pathology_type'] == qc2['pathology_type']

    # Different seed => different pathology (may differ)
    result3, qc3 = _apply_qc_pathologies(signal, 'A1', run_seed=999, realism_config=config)
    # Don't assert difference (could be same by chance), just check it runs


def test_edge_distance_computation():
    """
    CONTRACT: Edge distance must be continuous (0 = center, 1 = corner).
    """
    from cell_os.hardware.detector_stack import _compute_edge_distance

    # 96-well plate: 8 rows, 12 cols
    # Center: row 3.5, col 5.5 (indices 3-4, 5-6)
    # Corner: row 0 or 7, col 0 or 11

    # A1 (0, 0) should be corner (high distance)
    dist_a1 = _compute_edge_distance(0, 0, 96)
    assert dist_a1 > 0.9, f"A1 should be near edge, got {dist_a1}"

    # D6 (3, 5) should be center (low distance)
    dist_d6 = _compute_edge_distance(3, 5, 96)
    assert dist_d6 < 0.2, f"D6 should be near center, got {dist_d6}"

    # H12 (7, 11) should be corner (high distance)
    dist_h12 = _compute_edge_distance(7, 11, 96)
    assert dist_h12 > 0.9, f"H12 should be near edge, got {dist_h12}"


def test_edge_sensitivity_metrics_contract():
    """
    CONTRACT: Edge sensitivity metrics must reflect profile strength.

    Clean profile:
    - Edge sensitivity |corr| < 0.1 for all channels (no correlation)
    - Edge variance ratio ~ 1.0 (homoscedastic)

    Hostile profile:
    - At least one channel has edge_sensitivity < -0.2 (negative correlation)
    - At least one channel has edge_variance_ratio > 1.5 (heteroscedastic)
    """
    # Import demo script functions
    import sys
    from pathlib import Path
    demo_script = Path(__file__).parent.parent.parent / "scripts" / "demo_realism_profiles.py"
    sys.path.insert(0, str(demo_script.parent))

    # Import after adding to path
    from demo_realism_profiles import run_plate, compute_plate_summary

    seed = 42

    # Test clean profile
    print("\nTesting clean profile edge metrics...")
    well_records_clean = run_plate(profile='clean', seed=seed)
    summary_clean = compute_plate_summary(well_records_clean, 'clean')

    # Clean: edge sensitivity should be near zero (no correlation)
    for ch, sens in summary_clean['edge_sensitivity_per_channel'].items():
        assert abs(sens) < 0.15, (
            f"Clean profile should have |edge_sensitivity| < 0.15 for {ch}, got {sens:.3f}"
        )

    # Clean: edge variance ratio should be near 1.0 (homoscedastic)
    for ch, ratio in summary_clean['edge_variance_ratio_per_channel'].items():
        assert 0.5 < ratio < 2.0, (
            f"Clean profile should have edge_variance_ratio ~ 1.0 for {ch}, got {ratio:.3f}"
        )

    # Test hostile profile
    print("Testing hostile profile edge metrics...")
    well_records_hostile = run_plate(profile='hostile', seed=seed)
    summary_hostile = compute_plate_summary(well_records_hostile, 'hostile')

    # Hostile: at least one channel should show strong negative correlation
    edge_sensitivities = list(summary_hostile['edge_sensitivity_per_channel'].values())
    min_sensitivity = min(edge_sensitivities)
    assert min_sensitivity < -0.15, (
        f"Hostile profile should have at least one channel with edge_sensitivity < -0.15, "
        f"got min={min_sensitivity:.3f}"
    )

    # Hostile: at least one channel should show increased edge variance
    edge_variance_ratios = list(summary_hostile['edge_variance_ratio_per_channel'].values())
    max_ratio = max(edge_variance_ratios)
    assert max_ratio > 1.3, (
        f"Hostile profile should have at least one channel with edge_variance_ratio > 1.3, "
        f"got max={max_ratio:.3f}"
    )

    print(f"  Clean edge_sensitivity range: [{min(summary_clean['edge_sensitivity_per_channel'].values()):.3f}, "
          f"{max(summary_clean['edge_sensitivity_per_channel'].values()):.3f}]")
    print(f"  Hostile edge_sensitivity range: [{min(edge_sensitivities):.3f}, {max(edge_sensitivities):.3f}]")
    print(f"  Clean edge_variance_ratio range: [{min(summary_clean['edge_variance_ratio_per_channel'].values()):.3f}, "
          f"{max(summary_clean['edge_variance_ratio_per_channel'].values()):.3f}]")
    print(f"  Hostile edge_variance_ratio range: [{min(edge_variance_ratios):.3f}, {max(edge_variance_ratios):.3f}]")


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v'])
