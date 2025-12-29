"""
Sanity check: shuffle edge labels and confirm AUC collapses to ~0.5.

If AUC stays high after shuffling, there's ML pipeline leakage (feature includes position).
"""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext


def generate_dmso_plate_both_off(seed: int = 42):
    """
    Generate DMSO plate with well biology OFF, edge effects OFF.
    """
    realism_config = {
        'position_row_bias_pct': 0.0,
        'position_col_bias_pct': 0.0,
        'edge_mean_shift_pct': 0.0,
        'edge_noise_multiplier': 1.0,
        'outlier_rate': 0.0,
    }

    rc = RunContext.sample(seed=seed)
    rc.realism_profiles = {'cell_painting': realism_config}

    vm = BiologicalVirtualMachine(seed=seed, run_context=rc)
    vm._load_cell_thalamus_params()

    rows = [chr(ord('A') + i) for i in range(4)]
    cols = list(range(1, 7))

    measurements = []
    vessel_ids = []

    for row in rows:
        for col in cols:
            well_pos = f"{row}{col:02d}"
            vessel_id = well_pos
            vessel_ids.append((vessel_id, well_pos, row, col))

            vm.seed_vessel(
                vessel_id=vessel_id,
                cell_line="A549",
                initial_count=2000,
                vessel_type="96-well",
            )

            # Null well biology
            state = vm.vessel_states[vessel_id]
            state.well_biology = {
                "er_baseline_shift": 0.0,
                "mito_baseline_shift": 0.0,
                "rna_baseline_shift": 0.0,
                "nucleus_baseline_shift": 0.0,
                "actin_baseline_shift": 0.0,
                "stress_susceptibility": 1.0,
            }

    vm.advance_time(24.0)

    for vessel_id, well_pos, row, col in vessel_ids:
        obs = vm.cell_painting_assay(vessel_id, realism_config_override=realism_config)

        row_idx = ord(row) - ord('A')
        col_idx = col - 1
        is_edge = 1 if (row_idx == 0 or row_idx == 3 or col_idx == 0 or col_idx == 5) else 0

        measurements.append({
            'well_pos': well_pos,
            'is_edge': is_edge,
            'morphology': obs['morphology'],
        })

    return measurements


def test_sanity_shuffle():
    """Sanity check: shuffle labels and confirm AUC → 0.5."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler

    print("=" * 70)
    print("SANITY CHECK: Shuffle Edge Labels")
    print("=" * 70)

    measurements = generate_dmso_plate_both_off(seed=42)

    X = np.array([[
        m['morphology']['er'],
        m['morphology']['mito'],
        m['morphology']['nucleus'],
        m['morphology']['actin'],
        m['morphology']['rna'],
    ] for m in measurements])

    y_edge_real = np.array([m['is_edge'] for m in measurements])

    # Shuffle labels
    rng = np.random.default_rng(999)
    y_edge_shuffled = rng.permutation(y_edge_real)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Real labels
    model_real = LogisticRegression(C=1.0, max_iter=1000)
    model_real.fit(X_scaled, y_edge_real)
    y_pred_real = model_real.predict_proba(X_scaled)[:, 1]
    auc_real = roc_auc_score(y_edge_real, y_pred_real)

    # Shuffled labels
    model_shuffled = LogisticRegression(C=1.0, max_iter=1000)
    model_shuffled.fit(X_scaled, y_edge_shuffled)
    y_pred_shuffled = model_shuffled.predict_proba(X_scaled)[:, 1]
    auc_shuffled = roc_auc_score(y_edge_shuffled, y_pred_shuffled)

    print(f"\nReal labels AUC:      {auc_real:.4f}")
    print(f"Shuffled labels AUC:  {auc_shuffled:.4f}")

    if auc_shuffled > 0.65:
        print("\n❌ FAIL: Shuffled AUC is high → ML pipeline leakage (features include position)")
    elif auc_real > 0.65 and auc_shuffled < 0.60:
        print("\n✅ PASS: Signal is real, not ML leakage")
        print("Edge membership is learnable from morphology even with toggles OFF")
    else:
        print("\n🟡 WEAK: Neither real nor shuffled show strong signal")

    # Print feature stats by group
    print("\n--- Feature Means by Group ---")
    X_edge = X[y_edge_real == 1]
    X_center = X[y_edge_real == 0]
    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

    for i, ch in enumerate(channels):
        edge_mean = X_edge[:, i].mean()
        center_mean = X_center[:, i].mean()
        diff = edge_mean - center_mean
        print(f"{ch:10s} edge={edge_mean:6.2f}  center={center_mean:6.2f}  diff={diff:+6.2f}")

    return auc_real, auc_shuffled


if __name__ == "__main__":
    test_sanity_shuffle()
