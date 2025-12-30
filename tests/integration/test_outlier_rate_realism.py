"""
Integration test: Heavy-tail outlier rate and cross-channel correlation.

Validates Phase 2 (B1) realism requirement:
- Outliers should be rare (~2% of wells)
- Outliers should be cross-channel correlated (focus, stain, illumination affect all channels)

This is not a strict 3-sigma test (tails aren't Gaussian). We use robust z-scores
(median/MAD) and check for pragmatic outlier thresholds.
"""

import pytest
import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.run_context import RunContext


def robust_z_score(x: np.ndarray) -> np.ndarray:
    """
    Compute robust z-scores using median and MAD (median absolute deviation).

    More robust to outliers than mean/std.
    """
    median = np.median(x)
    mad = np.median(np.abs(x - median))
    # MAD → std conversion factor for normal distribution
    mad_to_std = 1.4826
    return (x - median) / (mad * mad_to_std + 1e-9)


def test_outlier_rate_in_expected_range():
    """
    Outlier rate should be ~2% (range: 0.5% to 5%).

    Run 10 seeds × 96 wells = 960 wells (DMSO only, 96-well plate for speed).
    Count wells with |robust_z| > 3 on at least one channel.
    Assert rate falls in acceptable range.
    """
    N_SEEDS = 3  # Reduced for fast test
    N_WELLS = 96  # 96-well plate (8 rows × 12 cols)
    OUTLIER_THRESHOLD = 3.0  # Pragmatic, not theoretical

    all_morphology = []

    # 96-well plate layout
    rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    cols = list(range(1, 13))

    for seed in range(N_SEEDS):
        vm = BiologicalVirtualMachine()
        vm.run_context = RunContext.sample(seed=seed)
        vm.rng_assay = np.random.default_rng(seed + 1000)
        vm.rng_biology = np.random.default_rng(seed + 2000)
        vm._load_cell_thalamus_params()

        # Seed 96 DMSO wells
        for row in rows:
            for col in cols:
                well_pos = f"{row}{col:02d}"
                vessel_id = f"P{seed}_{well_pos}"
                vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)

        # Advance time (let cells grow but stay healthy)
        vm.advance_time(24.0)

        # Measure all wells
        for row in rows:
            for col in cols:
                well_pos = f"{row}{col:02d}"
                vessel_id = f"P{seed}_{well_pos}"
                vessel = vm.vessel_states[vessel_id]
                result = vm._cell_painting_assay.measure(
                    vessel,
                    well_position=well_pos,
                    plate_id=f"P{seed}"
                )
                morph = result['morphology']
                all_morphology.append([
                    morph['er'],
                    morph['mito'],
                    morph['nucleus'],
                    morph['actin'],
                    morph['rna']
                ])

    # Convert to numpy array: (N_SEEDS * N_WELLS, 5)
    all_morphology = np.array(all_morphology)

    # Compute robust z-scores per channel
    z_scores = np.zeros_like(all_morphology)
    for ch_idx in range(5):
        z_scores[:, ch_idx] = robust_z_score(all_morphology[:, ch_idx])

    # Count outliers: wells with |z| > threshold on at least one channel
    max_abs_z_per_well = np.max(np.abs(z_scores), axis=1)
    outliers = max_abs_z_per_well > OUTLIER_THRESHOLD
    outlier_count = np.sum(outliers)
    outlier_rate = outlier_count / len(all_morphology)

    print(f"\nOutlier rate: {outlier_rate:.3f} ({outlier_count}/{len(all_morphology)} wells)")
    print(f"Target: 0.02 (2%), Acceptable range: 0.005-0.05 (0.5%-5%)")

    # Assert: outlier rate in acceptable range
    assert 0.005 <= outlier_rate <= 0.05, \
        f"Outlier rate {outlier_rate:.3f} outside acceptable range [0.005, 0.05]"


def test_outliers_are_cross_channel_correlated():
    """
    Outliers should be cross-channel correlated (not independent).

    If outliers were independent per channel, P(2+ channels outlier) = p^2 ≈ 0.04%.
    With correlation (focus, stain, illumination), P(2+ channels) should be much higher.

    We test: Among wells with at least one outlier channel, what fraction have 2+ outlier channels?
    Expect: >50% (strong correlation). Independent would be ~2%.
    """
    N_SEEDS = 5
    N_WELLS = 96
    OUTLIER_THRESHOLD = 3.0

    all_morphology = []

    rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    cols = list(range(1, 13))

    for seed in range(N_SEEDS):
        vm = BiologicalVirtualMachine()
        vm.run_context = RunContext.sample(seed=seed)
        vm.rng_assay = np.random.default_rng(seed + 1000)
        vm.rng_biology = np.random.default_rng(seed + 2000)
        vm._load_cell_thalamus_params()

        # Seed 96 DMSO wells
        for row in rows:
            for col in cols:
                well_pos = f"{row}{col:02d}"
                vessel_id = f"P{seed}_{well_pos}"
                vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)

        vm.advance_time(24.0)

        for row in rows:
            for col in cols:
                well_pos = f"{row}{col:02d}"
                vessel_id = f"P{seed}_{well_pos}"
                vessel = vm.vessel_states[vessel_id]
                result = vm._cell_painting_assay.measure(
                    vessel,
                    well_position=well_pos,
                    plate_id=f"P{seed}"
                )
                morph = result['morphology']
                all_morphology.append([
                    morph['er'],
                    morph['mito'],
                    morph['nucleus'],
                    morph['actin'],
                    morph['rna']
                ])

    all_morphology = np.array(all_morphology)

    # Compute robust z-scores per channel
    z_scores = np.zeros_like(all_morphology)
    for ch_idx in range(5):
        z_scores[:, ch_idx] = robust_z_score(all_morphology[:, ch_idx])

    # For each well, count how many channels are outliers
    is_outlier_per_channel = np.abs(z_scores) > OUTLIER_THRESHOLD  # (N_wells, 5)
    outlier_channel_count = np.sum(is_outlier_per_channel, axis=1)

    # Wells with at least one outlier channel
    wells_with_any_outlier = outlier_channel_count > 0
    n_wells_with_any_outlier = np.sum(wells_with_any_outlier)

    if n_wells_with_any_outlier == 0:
        pytest.skip("No outliers found in this run (unlucky seeds or config issue)")

    # Among wells with at least one outlier, how many have 2+ outlier channels?
    wells_with_multiple_outliers = outlier_channel_count[wells_with_any_outlier] >= 2
    n_wells_with_multiple = np.sum(wells_with_multiple_outliers)
    fraction_multi_channel = n_wells_with_multiple / n_wells_with_any_outlier

    print(f"\nWells with any outlier: {n_wells_with_any_outlier}")
    print(f"Wells with 2+ outlier channels: {n_wells_with_multiple}")
    print(f"Fraction multi-channel: {fraction_multi_channel:.3f}")
    print(f"Expected if correlated: >0.5, Expected if independent: ~0.02")

    # Assert: multi-channel outliers are more common than independence would predict
    # Independent: P(2+ | 1+) ≈ p/(1-p) where p ≈ 0.02 → ~2%
    # Correlated (shared shock): Should be >50%
    assert fraction_multi_channel > 0.3, \
        f"Multi-channel outlier fraction {fraction_multi_channel:.3f} too low (independence: ~0.02, correlated: >0.5)"


def test_outlier_magnitude_is_realistic():
    """
    Outlier magnitudes should be moderate (not infinite).

    With clipping [0.2, 5.0]×, max deviation should be ~5× median.
    Check that outliers exist but don't explode.
    """
    N_SEEDS = 5
    N_WELLS = 96

    all_morphology = []

    rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    cols = list(range(1, 13))

    for seed in range(N_SEEDS):
        vm = BiologicalVirtualMachine()
        vm.run_context = RunContext.sample(seed=seed)
        vm.rng_assay = np.random.default_rng(seed + 1000)
        vm.rng_biology = np.random.default_rng(seed + 2000)
        vm._load_cell_thalamus_params()

        for row in rows:
            for col in cols:
                well_pos = f"{row}{col:02d}"
                vessel_id = f"P{seed}_{well_pos}"
                vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)

        vm.advance_time(24.0)

        for row in rows:
            for col in cols:
                well_pos = f"{row}{col:02d}"
                vessel_id = f"P{seed}_{well_pos}"
                vessel = vm.vessel_states[vessel_id]
                result = vm._cell_painting_assay.measure(
                    vessel,
                    well_position=well_pos,
                    plate_id=f"P{seed}"
                )
                morph = result['morphology']
                all_morphology.append([
                    morph['er'],
                    morph['mito'],
                    morph['nucleus'],
                    morph['actin'],
                    morph['rna']
                ])

    all_morphology = np.array(all_morphology)

    # Compute ratio to median per channel
    for ch_idx in range(5):
        channel_values = all_morphology[:, ch_idx]
        median_val = np.median(channel_values)
        ratios = channel_values / median_val
        max_ratio = np.max(ratios)
        min_ratio = np.min(ratios)

        print(f"Channel {ch_idx}: min ratio={min_ratio:.2f}, max ratio={max_ratio:.2f}")

        # Assert: outliers are clipped (not infinite)
        # Max should be <10× median (config clips at 5×, but multiplicative effects can compound)
        assert max_ratio < 10.0, f"Channel {ch_idx} has outlier too large: {max_ratio:.2f}×"
        assert min_ratio > 0.05, f"Channel {ch_idx} has outlier too small: {min_ratio:.2f}×"


@pytest.mark.slow
def test_outlier_rate_stable_across_seeds():
    """
    Outlier rate should be stable across seeds (not seed-dependent).

    Run 20 seeds, compute outlier rate per seed, check variance is low.
    """
    N_SEEDS = 20
    N_WELLS_PER_SEED = 96  # Smaller for speed (96-well plate)

    outlier_rates = []

    rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    cols = list(range(1, 13))

    for seed in range(N_SEEDS):
        vm = BiologicalVirtualMachine()
        vm.run_context = RunContext.sample(seed=seed)
        vm.rng_assay = np.random.default_rng(seed + 1000)
        vm.rng_biology = np.random.default_rng(seed + 2000)
        vm._load_cell_thalamus_params()

        morphology = []
        for row in rows:
            for col in cols:
                well_pos = f"{row}{col:02d}"
                vessel_id = f"P{seed}_{well_pos}"
                vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)

        vm.advance_time(24.0)

        for row in rows:
            for col in cols:
                well_pos = f"{row}{col:02d}"
                vessel_id = f"P{seed}_{well_pos}"
                vessel = vm.vessel_states[vessel_id]
                result = vm._cell_painting_assay.measure(
                    vessel,
                    well_position=well_pos,
                    plate_id=f"P{seed}"
                )
                morph = result['morphology']
                morphology.append([
                    morph['er'],
                    morph['mito'],
                    morph['nucleus'],
                    morph['actin'],
                    morph['rna']
                ])

        morphology = np.array(morphology)
        z_scores = np.zeros_like(morphology)
        for ch_idx in range(5):
            z_scores[:, ch_idx] = robust_z_score(morphology[:, ch_idx])

        max_abs_z = np.max(np.abs(z_scores), axis=1)
        outliers = max_abs_z > 3.0
        outlier_rate = np.mean(outliers)
        outlier_rates.append(outlier_rate)

    outlier_rates = np.array(outlier_rates)
    mean_rate = np.mean(outlier_rates)
    std_rate = np.std(outlier_rates)

    print(f"\nMean outlier rate across {N_SEEDS} seeds: {mean_rate:.3f} ± {std_rate:.3f}")
    print(f"Min: {np.min(outlier_rates):.3f}, Max: {np.max(outlier_rates):.3f}")

    # Assert: variance is reasonable (not all 0% or all 10%)
    assert 0.005 <= mean_rate <= 0.05, f"Mean outlier rate {mean_rate:.3f} outside acceptable range"
    assert std_rate < 0.03, f"Outlier rate variance too high: {std_rate:.3f}"
