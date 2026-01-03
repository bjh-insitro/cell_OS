"""
Phase 2D.1: Contamination Identifiability - Experiment Runner

Executes multi-regime experiments and collects time-series observations.

Outputs:
- observations.npy: Time-series data (vessel × time × features)
- ground_truth.npy: True contamination events (for scoring only)
- metadata.yaml: Experiment parameters and regime configs
"""

import numpy as np
import yaml
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from .identifiability_design_2d1 import (
    design_regime_configs,
    design_vessel_ids,
    design_sampling_times,
    check_preconditions,
    DEFAULT_N_VESSELS,
    DEFAULT_DURATION_H,
    DEFAULT_SAMPLING_INTERVAL_H,
    DEFAULT_CELL_LINE,
    DEFAULT_INITIAL_COUNT,
)


def run_regime(
    regime_label: str,
    contamination_config: Dict,
    vessel_ids: List[str],
    sampling_times: List[float],
    cell_line: str,
    initial_count: int,
    run_seed: int,
) -> Dict[str, Any]:
    """
    Run a single regime and collect time-series observations.

    Args:
        regime_label: Regime identifier (e.g., "A_clean")
        contamination_config: Config dict or None (for disabled regime)
        vessel_ids: List of vessel IDs
        sampling_times: List of timepoints (hours)
        cell_line: Cell line name
        initial_count: Initial cell count
        run_seed: RNG seed for this regime

    Returns:
        Dict with:
            - observations: vessel × time × features array
            - ground_truth: List of true event dicts
            - metadata: Regime parameters
    """
    print(f"Running Regime {regime_label}...")
    print(f"  Vessels: {len(vessel_ids)}")
    print(f"  Sampling: {len(sampling_times)} timepoints over {max(sampling_times):.1f}h")
    print(f"  Seed: {run_seed}")

    # Initialize VM
    vm = BiologicalVirtualMachine(seed=run_seed)

    # Set contamination config (None for disabled regime)
    if contamination_config is not None:
        vm.contamination_config = contamination_config
        print(f"  Rate multiplier: {contamination_config.get('rate_multiplier', 1.0)}×")
    else:
        vm.contamination_config = None
        print(f"  Contamination: DISABLED")

    # Seed all vessels at t=0
    for vessel_id in vessel_ids:
        vm.seed_vessel(vessel_id, cell_line, vessel_type="96-well", initial_count=initial_count)

    # Collect observations at each timepoint
    n_vessels = len(vessel_ids)
    n_times = len(sampling_times)

    # Feature vector: [cell_count, viability, er, mito, nucleus, actin, rna]
    n_features = 7
    observations = np.zeros((n_vessels, n_times, n_features))

    ground_truth_events = []

    for t_idx, t_h in enumerate(sampling_times):
        # Advance time to next sample point
        if t_idx == 0:
            dt = t_h  # From 0 to first sample
        else:
            dt = t_h - sampling_times[t_idx - 1]

        if dt > 0:
            vm.advance_time(dt)

        # Measure each vessel
        for v_idx, vessel_id in enumerate(vessel_ids):
            vessel = vm.vessel_states[vessel_id]

            # Observable features (no labels)
            observations[v_idx, t_idx, 0] = vessel.cell_count
            observations[v_idx, t_idx, 1] = vessel.viability

            # Cell Painting morphology (measurement, not ground truth)
            # Extract well position from vessel_id (format: "Plate_X_A01" → "A01")
            well_position = vessel_id.split('_')[-1] if '_' in vessel_id else vessel_id
            morph_result = vm.cell_painting_assay(vessel_id, well_position=well_position)
            if morph_result.get('status') == 'success':
                morph = morph_result['morphology']
                observations[v_idx, t_idx, 2] = morph.get('er', 0.0)
                observations[v_idx, t_idx, 3] = morph.get('mito', 0.0)
                observations[v_idx, t_idx, 4] = morph.get('nucleus', 0.0)
                observations[v_idx, t_idx, 5] = morph.get('actin', 0.0)
                observations[v_idx, t_idx, 6] = morph.get('rna', 0.0)

            # Ground truth (for scoring only, not used by detector)
            if vessel.contaminated:
                # Record event once (first time we see it)
                if not any(gt['vessel_id'] == vessel_id for gt in ground_truth_events):
                    ground_truth_events.append({
                        'vessel_id': vessel_id,
                        'vessel_index': v_idx,
                        'contamination_type': vessel.contamination_type,
                        'contamination_onset_h': vessel.contamination_onset_h,
                        'contamination_severity': vessel.contamination_severity,
                        'first_observed_at_h': t_h,
                    })

    print(f"  Completed: {len(ground_truth_events)} true events detected")

    return {
        'observations': observations,
        'ground_truth': ground_truth_events,
        'metadata': {
            'regime_label': regime_label,
            'n_vessels': n_vessels,
            'vessel_ids': vessel_ids,
            'sampling_times': sampling_times,
            'contamination_config': contamination_config,
            'run_seed': run_seed,
        }
    }


def run_identifiability_suite(
    output_dir: Path,
    n_vessels: int = DEFAULT_N_VESSELS,
    duration_h: float = DEFAULT_DURATION_H,
    sampling_interval_h: float = DEFAULT_SAMPLING_INTERVAL_H,
    cell_line: str = DEFAULT_CELL_LINE,
    initial_count: int = DEFAULT_INITIAL_COUNT,
    base_seed: int = 42,
) -> Dict[str, Any]:
    """
    Run full identifiability suite across all regimes.

    Args:
        output_dir: Directory to save results
        n_vessels: Vessels per regime
        duration_h: Duration in hours
        sampling_interval_h: Sampling interval
        cell_line: Cell line name
        initial_count: Initial cell count
        base_seed: Base RNG seed (each regime gets base_seed + offset)

    Returns:
        Dict with all regime results + metadata
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("Phase 2D.1: Contamination Identifiability Suite")
    print("=" * 80)
    print(f"Output directory: {output_dir}")
    print()

    # Check preconditions
    passed, message, expected_counts = check_preconditions(n_vessels, duration_h)
    print(f"Precondition check: {message}")
    if not passed:
        print("\n⚠️  INSUFFICIENT_EVENTS - Aborting before data generation.")
        result = {
            'status': 'INSUFFICIENT_EVENTS',
            'message': message,
            'expected_counts': expected_counts,
        }
        # Save metadata anyway
        with open(output_dir / 'metadata.yaml', 'w') as f:
            yaml.dump(result, f)
        return result

    print()

    # Design regimes
    regime_configs = design_regime_configs()
    sampling_times = design_sampling_times(duration_h, sampling_interval_h)

    results = {}
    regime_labels = ['A_clean', 'B_enriched', 'C_held_out', 'D_disabled']

    for i, regime_label in enumerate(regime_labels):
        vessel_ids = design_vessel_ids(n_vessels, regime_label)
        contamination_config = regime_configs[regime_label]
        regime_seed = base_seed + (i * 1000)  # Offset seeds per regime

        regime_result = run_regime(
            regime_label=regime_label,
            contamination_config=contamination_config,
            vessel_ids=vessel_ids,
            sampling_times=sampling_times,
            cell_line=cell_line,
            initial_count=initial_count,
            run_seed=regime_seed,
        )

        results[regime_label] = regime_result
        print()

    # Save observations and ground truth
    print("Saving results...")

    # Combine observations across regimes (regime × vessel × time × feature)
    all_observations = np.stack([results[r]['observations'] for r in regime_labels], axis=0)
    np.save(output_dir / 'observations.npy', all_observations)
    print(f"  Saved observations: {all_observations.shape}")

    # Save ground truth separately per regime
    ground_truth = {r: results[r]['ground_truth'] for r in regime_labels}
    np.save(output_dir / 'ground_truth.npy', ground_truth, allow_pickle=True)
    print(f"  Saved ground truth")

    # Save metadata
    metadata = {
        'status': 'DATA_GENERATED',
        'timestamp': datetime.now().isoformat(),
        'design': {
            'n_vessels': n_vessels,
            'duration_h': duration_h,
            'sampling_interval_h': sampling_interval_h,
            'cell_line': cell_line,
            'initial_count': initial_count,
            'base_seed': base_seed,
        },
        'regimes': {r: results[r]['metadata'] for r in regime_labels},
        'expected_counts': expected_counts,
        'feature_names': ['cell_count', 'viability', 'er', 'mito', 'nucleus', 'actin', 'rna'],
        'regime_order': regime_labels,
    }

    with open(output_dir / 'metadata.yaml', 'w') as f:
        yaml.dump(metadata, f)
    print(f"  Saved metadata.yaml")

    print()
    print("=" * 80)
    print("Data generation complete. Ready for inference.")
    print("=" * 80)

    return {
        'status': 'DATA_GENERATED',
        'results': results,
        'metadata': metadata,
    }


if __name__ == "__main__":
    import sys
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "output/identifiability_2d1"
    run_identifiability_suite(Path(output_dir))
