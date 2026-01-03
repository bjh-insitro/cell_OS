"""
Attack 2.2 Cut 2b: Null focus_factor (per-tile position-dependent).

Test if _get_tile_focus_factor(well_position) is the 0.77 leak.
"""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext


def generate_dmso_plate_null_focus(seed: int = 42):
    """
    Generate DMSO plate with well biology OFF, edge effects OFF, focus OFF.
    """
    # Disable edge effects
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

    # NULL FOCUS: set focus_cv to 0
    vm.thalamus_params['technical_noise']['focus_cv'] = 0.0

    # 4x6 grid
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


def test_cut2b():
    """Test edge AUC with focus factor nulled."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler

    print("=" * 70)
    print("ATTACK 2.2 CUT 2b: Null Focus Factor (per-tile position)")
    print("=" * 70)

    measurements = generate_dmso_plate_null_focus(seed=42)

    X = np.array([[
        m['morphology']['er'],
        m['morphology']['mito'],
        m['morphology']['nucleus'],
        m['morphology']['actin'],
        m['morphology']['rna'],
    ] for m in measurements])

    y_edge = np.array([m['is_edge'] for m in measurements])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LogisticRegression(C=1.0, max_iter=1000)
    model.fit(X_scaled, y_edge)
    y_pred_proba = model.predict_proba(X_scaled)[:, 1]
    auc = roc_auc_score(y_edge, y_pred_proba)

    print(f"\nEdge AUC (focus nulled): {auc:.4f}")
    print(f"Baseline (both OFF from Attack 2.1): 0.7656")
    print(f"Delta: {auc - 0.7656:.4f}")

    if auc < 0.65:
        print("\n✅ LEAK ISOLATED: Focus factor (per-tile position) was the 0.77 source")
    else:
        print(f"\n⚠️  Leak persists (AUC={auc:.4f}), multiple sources likely")

    return auc


if __name__ == "__main__":
    test_cut2b()
