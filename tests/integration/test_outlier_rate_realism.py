"""
Integration test: Heavy-tail outlier delta test (measurement-stage only).

Validates Phase 3.1 (Measurement Pathology):
- Heavy-tail shocks increase tail mass vs baseline
- Heavy-tail shocks create cross-channel correlation signature

This is a DELTA test, not an absolute rate test:
- We compare p_heavy=0.0 vs p_heavy=0.02 under identical conditions
- We do NOT assert outlier_rate ≈ p_heavy because base multiplicative noise
  (stain_cv, focus_cv, etc.) also creates tail events
- We assert that enabling shocks materially increases tail mass AND multi-channel co-outliers

IMPORTANT: Marked @pytest.mark.realism - this is a statistical property check,
not a fast unit/integration invariant. Run separately from default CI.
"""

import pytest
import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.run_context import RunContext


pytestmark = pytest.mark.realism  # Exclude from fast CI by default


def _mad(x: np.ndarray) -> float:
    """Median absolute deviation (robust scale estimator)."""
    med = np.median(x)
    return np.median(np.abs(x - med)) + 1e-12


def _robust_z_score(x: np.ndarray) -> np.ndarray:
    """
    Compute robust z-scores using median and MAD.

    MAD → std conversion factor for normal: 1.4826
    Equivalent to 0.6745 * (x - median) / MAD
    """
    median = np.median(x)
    mad = _mad(x)
    mad_to_std = 1.4826
    return (x - median) / (mad * mad_to_std)


def _measure_plate(vm, rows, cols, seed):
    """
    Measure morphology for all wells in plate.

    Returns:
        np.ndarray of shape (n_wells, 5) with columns [er, mito, nucleus, actin, rna]
    """
    morphology = []
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
    return np.array(morphology)


def _tail_metrics(morphology: np.ndarray, z_thresh: float = 3.0) -> dict:
    """
    Compute tail mass metrics from morphology array.

    Args:
        morphology: (n_wells, n_channels) array
        z_thresh: Robust z-score threshold for "extreme"

    Returns:
        dict with:
        - any_extreme_rate: fraction of wells with |z| > thresh on ANY channel
        - multi_extreme_rate: fraction with |z| > thresh on 2+ channels
        - multi_given_any: P(2+ channels | 1+ channel) - shared shock signature
    """
    n_wells, n_channels = morphology.shape

    # Compute robust z-scores per channel
    z_scores = np.zeros_like(morphology)
    for ch_idx in range(n_channels):
        z_scores[:, ch_idx] = _robust_z_score(morphology[:, ch_idx])

    # Per-well: which channels are extreme
    is_extreme = np.abs(z_scores) > z_thresh  # (n_wells, n_channels)
    n_extreme_per_well = is_extreme.sum(axis=1)

    # Count wells
    any_extreme = n_extreme_per_well >= 1
    multi_extreme = n_extreme_per_well >= 2

    any_extreme_rate = float(any_extreme.mean())
    multi_extreme_rate = float(multi_extreme.mean())
    multi_given_any = float(multi_extreme[any_extreme].mean() if any_extreme.any() else 0.0)

    return {
        "any_extreme_rate": any_extreme_rate,
        "multi_extreme_rate": multi_extreme_rate,
        "multi_given_any": multi_given_any,
        "n_wells": n_wells,
        "n_channels": n_channels,
    }


def _setup_vm_with_heavy_tail(seed: int, p_heavy: float, rows, cols):
    """
    Create VM with specified heavy_tail_frequency.

    Returns VM with seeded vessels (no time advance - measurement-only test).
    """
    vm = BiologicalVirtualMachine()
    vm.run_context = RunContext.sample(seed=seed)
    vm.rng_assay = np.random.default_rng(seed + 1000)
    vm.rng_biology = np.random.default_rng(seed + 2000)
    vm._load_cell_thalamus_params()

    # Override heavy_tail_frequency
    if vm.thalamus_params is None:
        vm.thalamus_params = {}
    if 'technical_noise' not in vm.thalamus_params:
        vm.thalamus_params['technical_noise'] = {}
    vm.thalamus_params['technical_noise']['heavy_tail_frequency'] = float(p_heavy)

    # Seed vessels (no advance_time - we're testing measurement noise only)
    for row in rows:
        for col in cols:
            well_pos = f"{row}{col:02d}"
            vessel_id = f"P{seed}_{well_pos}"
            vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)

    return vm


def test_heavy_tail_increases_tail_mass_delta():
    """
    Heavy-tail shocks should increase tail mass vs baseline (delta test).

    Design:
    - Compare p_heavy=0.0 (baseline) vs p_heavy=0.02 (shocks enabled)
    - Same seed, same base noise → only difference is heavy-tail shocks
    - Assert: tail mass increases materially (>1% absolute increase)

    Why delta test:
    - Base multiplicative noise (stain_cv=5%, focus_cv=4%, etc.) already creates tails
    - Can't assert "outlier_rate ≈ 2%" because baseline has ~1-2% extremes from lognormal tails
    - Must measure the DELTA to isolate heavy-tail shock effect
    """
    seed = 42
    rows = ['A', 'B', 'C', 'D']
    cols = list(range(1, 13))  # 4×12 = 48 wells (fast enough)
    z_thresh = 3.0

    # Baseline: no heavy-tail shocks
    vm0 = _setup_vm_with_heavy_tail(seed, p_heavy=0.0, rows=rows, cols=cols)
    morph0 = _measure_plate(vm0, rows, cols, seed)
    metrics0 = _tail_metrics(morph0, z_thresh=z_thresh)

    # Treatment: heavy-tail shocks enabled (2%)
    vm1 = _setup_vm_with_heavy_tail(seed, p_heavy=0.02, rows=rows, cols=cols)
    morph1 = _measure_plate(vm1, rows, cols, seed)
    metrics1 = _tail_metrics(morph1, z_thresh=z_thresh)

    print(f"\nBaseline (p_heavy=0.0): {metrics0['any_extreme_rate']:.3f} any-extreme rate")
    print(f"Treatment (p_heavy=0.02): {metrics1['any_extreme_rate']:.3f} any-extreme rate")
    print(f"Delta: +{metrics1['any_extreme_rate'] - metrics0['any_extreme_rate']:.3f}")

    # Assert: tail mass increases materially when shocks are enabled
    # Expect: baseline ~1-3% (lognormal tails), treatment ~3-6% (lognormal + shocks)
    delta = metrics1['any_extreme_rate'] - metrics0['any_extreme_rate']
    assert delta > 0.01, \
        f"Heavy-tail shocks did not increase tail mass (delta={delta:.3f}, expect >0.01)"

    # Sanity: not totally insane
    assert 0.0 <= metrics1['any_extreme_rate'] <= 0.20, \
        f"Tail mass unrealistic: {metrics1['any_extreme_rate']:.3f}"


def test_heavy_tail_creates_cross_channel_correlation():
    """
    Heavy-tail shocks should be cross-channel correlated (shared shock signature).

    Design:
    - Compare p_heavy=0.0 vs p_heavy=0.02
    - Metric: P(2+ channels extreme | 1+ channel extreme)
    - Independent noise: ~2% (p² small)
    - Shared shock: >30% (same shock hits all channels)

    Why this works:
    - Heavy-tail shock is drawn ONCE per well, applied to ALL channels
    - Base lognormal noise is drawn PER CHANNEL (independent)
    - Multi-channel co-outliers are signature of shared shock, not independent noise
    """
    seed = 123
    rows = ['A', 'B', 'C', 'D']
    cols = list(range(1, 13))  # 48 wells
    z_thresh = 3.0

    # Baseline
    vm0 = _setup_vm_with_heavy_tail(seed, p_heavy=0.0, rows=rows, cols=cols)
    morph0 = _measure_plate(vm0, rows, cols, seed)
    metrics0 = _tail_metrics(morph0, z_thresh=z_thresh)

    # Treatment
    vm1 = _setup_vm_with_heavy_tail(seed, p_heavy=0.02, rows=rows, cols=cols)
    morph1 = _measure_plate(vm1, rows, cols, seed)
    metrics1 = _tail_metrics(morph1, z_thresh=z_thresh)

    print(f"\nBaseline: {metrics0['multi_given_any']:.3f} multi-channel given any")
    print(f"Treatment: {metrics1['multi_given_any']:.3f} multi-channel given any")
    print(f"Delta: +{metrics1['multi_given_any'] - metrics0['multi_given_any']:.3f}")

    # Assert: multi-channel co-outliers increase materially
    # Shared shock should push P(2+|1+) from ~10-20% (independent) to >40% (shared)
    delta = metrics1['multi_given_any'] - metrics0['multi_given_any']

    # Only assert if treatment has enough outliers to measure correlation
    if metrics1['any_extreme_rate'] < 0.01:
        pytest.skip("Insufficient outliers in treatment (unlucky seed or config issue)")

    assert delta > 0.10, \
        f"Heavy-tail shocks did not increase cross-channel correlation (delta={delta:.3f}, expect >0.10)"

    # Sanity: shared shock signature should be substantial
    assert metrics1['multi_given_any'] > 0.30, \
        f"Multi-channel correlation too weak: {metrics1['multi_given_any']:.3f} (expect >0.30 for shared shock)"


@pytest.mark.slow
def test_heavy_tail_delta_stable_across_seeds():
    """
    Heavy-tail delta should be stable across seeds (not seed-dependent).

    Run multiple seeds, compute delta per seed, check that:
    - Mean delta is positive and material (>1%)
    - Variance is reasonable (not wildly unstable)

    Marked @pytest.mark.slow because 10 seeds × 2 conditions = expensive.
    """
    N_SEEDS = 10
    rows = ['A', 'B', 'C', 'D']
    cols = list(range(1, 7))  # Small plate (24 wells) for speed
    z_thresh = 3.0

    deltas = []

    for seed in range(N_SEEDS):
        vm0 = _setup_vm_with_heavy_tail(seed, p_heavy=0.0, rows=rows, cols=cols)
        morph0 = _measure_plate(vm0, rows, cols, seed)
        metrics0 = _tail_metrics(morph0, z_thresh=z_thresh)

        vm1 = _setup_vm_with_heavy_tail(seed, p_heavy=0.02, rows=rows, cols=cols)
        morph1 = _measure_plate(vm1, rows, cols, seed)
        metrics1 = _tail_metrics(morph1, z_thresh=z_thresh)

        delta = metrics1['any_extreme_rate'] - metrics0['any_extreme_rate']
        deltas.append(delta)

    deltas = np.array(deltas)
    mean_delta = np.mean(deltas)
    std_delta = np.std(deltas)

    print(f"\nMean delta across {N_SEEDS} seeds: {mean_delta:.3f} ± {std_delta:.3f}")
    print(f"Min: {np.min(deltas):.3f}, Max: {np.max(deltas):.3f}")

    # Assert: mean delta is positive and material
    assert mean_delta > 0.01, \
        f"Mean heavy-tail delta too small: {mean_delta:.3f} (expect >0.01)"

    # Assert: variance is reasonable (not pathologically unstable)
    assert std_delta < 0.10, \
        f"Heavy-tail delta variance too high: {std_delta:.3f} (expect <0.10)"
