"""
Attack 2.1: Decompose edge learnability into instrument vs biology.

Test edge AUC under 4 conditions:
1. Edge effects ON, well biology OFF
2. Edge effects OFF, well biology ON
3. Both ON
4. Both OFF
"""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext


def generate_dmso_plate_with_toggles(
    seed: int = 42,
    enable_edge_effects: bool = True,
    enable_well_biology: bool = True
):
    """
    Generate DMSO plate with instrument and biology toggles.

    Args:
        seed: Run seed
        enable_edge_effects: If False, disable detector position effects
        enable_well_biology: If False, disable persistent well biology offsets

    Returns:
        measurements: List of dicts with well_pos, morphology, edge label
    """
    # Configure realism to toggle edge effects
    if enable_edge_effects:
        realism_config = None  # Use run_context defaults
    else:
        realism_config = {
            'position_row_bias_pct': 0.0,
            'position_col_bias_pct': 0.0,
            'edge_mean_shift_pct': 0.0,
            'edge_noise_multiplier': 1.0,  # 1.0 = no amplification
            'outlier_rate': 0.0,
        }

    rc = RunContext.sample(seed=seed)
    if not enable_edge_effects:
        rc.realism_profiles = {'cell_painting': realism_config}

    vm = BiologicalVirtualMachine(seed=seed, run_context=rc)
    vm._load_cell_thalamus_params()

    # 4x6 grid (24 wells)
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

            # Toggle well biology by zeroing out persistent offsets
            if not enable_well_biology:
                state = vm.vessel_states[vessel_id]
                state.well_biology = {
                    "er_baseline_shift": 0.0,
                    "mito_baseline_shift": 0.0,
                    "rna_baseline_shift": 0.0,
                    "nucleus_baseline_shift": 0.0,
                    "actin_baseline_shift": 0.0,
                    "stress_susceptibility": 1.0,  # Multiplicative, use 1.0 = no effect
                }

    vm.advance_time(24.0)

    for vessel_id, well_pos, row, col in vessel_ids:
        # Pass realism_config_override to measurement if edge effects disabled
        if enable_edge_effects:
            obs = vm.cell_painting_assay(vessel_id)
        else:
            obs = vm.cell_painting_assay(vessel_id, realism_config_override=realism_config)

        row_idx = ord(row) - ord('A')
        col_idx = col - 1
        is_edge = 1 if (row_idx == 0 or row_idx == 3 or col_idx == 0 or col_idx == 5) else 0

        measurements.append({
            'well_pos': well_pos,
            'row_idx': row_idx,
            'col_idx': col_idx,
            'is_edge': is_edge,
            'morphology': obs['morphology'],
        })

    return measurements


def test_edge_auc_decomposition():
    """
    Test edge prediction AUC under 4 conditions to decompose leakage source.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler

    print("=" * 70)
    print("ATTACK 2.1: Edge Learnability Decomposition")
    print("=" * 70)

    conditions = [
        ("Both ON", True, True),
        ("Edge ON, Biology OFF", True, False),
        ("Edge OFF, Biology ON", False, True),
        ("Both OFF", False, False),
    ]

    results = []

    for name, edge_on, bio_on in conditions:
        print(f"\n--- {name} ---")
        print(f"Edge effects: {'ON' if edge_on else 'OFF'}")
        print(f"Well biology: {'ON' if bio_on else 'OFF'}")

        measurements = generate_dmso_plate_with_toggles(
            seed=42,
            enable_edge_effects=edge_on,
            enable_well_biology=bio_on
        )

        # Extract features
        X = np.array([[
            m['morphology']['er'],
            m['morphology']['mito'],
            m['morphology']['nucleus'],
            m['morphology']['actin'],
            m['morphology']['rna'],
        ] for m in measurements])

        y_edge = np.array([m['is_edge'] for m in measurements])

        # Standardize
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Train edge classifier
        model = LogisticRegression(C=1.0, max_iter=1000)
        model.fit(X_scaled, y_edge)
        y_pred_proba = model.predict_proba(X_scaled)[:, 1]
        auc = roc_auc_score(y_edge, y_pred_proba)

        print(f"Edge AUC: {auc:.4f}")
        results.append((name, auc))

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, auc in results:
        marker = "🔴" if auc > 0.65 else "🟢"
        print(f"{marker} {name:30s} AUC = {auc:.4f}")

    print("\nInterpretation:")
    both_on = results[0][1]
    edge_only = results[1][1]
    bio_only = results[2][1]
    both_off = results[3][1]

    if edge_only > 0.65 and bio_only < 0.60:
        print("→ Leakage is INSTRUMENT-DRIVEN (edge effects in detector)")
    elif bio_only > 0.65 and edge_only < 0.60:
        print("→ Leakage is BIOLOGY-DRIVEN (well hash encodes edge membership)")
    elif both_on > 0.65 and edge_only > 0.60 and bio_only > 0.60:
        print("→ Leakage is BOTH (instrument + biology, likely correlated)")
    elif both_on > 0.65 and edge_only < 0.60 and bio_only < 0.60:
        print("→ Leakage is INTERACTION (only when both present)")
    else:
        print("→ Mixed or weak signal")

    return results


if __name__ == "__main__":
    test_edge_auc_decomposition()
