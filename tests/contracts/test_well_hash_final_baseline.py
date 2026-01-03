"""
Final baseline test after fixing hardware_bias roughness seed.

Attack 2 completion test: Biology OFF should now pass.
"""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext


def generate_dmso_plate_biology_off(seed: int):
    """Generate 96-well DMSO plate with Biology OFF."""
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

    rows = [chr(ord('A') + i) for i in range(8)]
    cols = list(range(1, 13))

    for row in rows:
        for col in cols:
            well_pos = f"{row}{col:02d}"

            vm.seed_vessel(
                vessel_id=well_pos,
                cell_line="A549",
                initial_count=2000,
                vessel_type="96-well",
            )

            # NULL well biology
            state = vm.vessel_states[well_pos]
            state.well_biology = {
                "er_baseline_shift": 0.0,
                "mito_baseline_shift": 0.0,
                "rna_baseline_shift": 0.0,
                "nucleus_baseline_shift": 0.0,
                "actin_baseline_shift": 0.0,
                "stress_susceptibility": 1.0,
            }

    vm.advance_time(24.0)

    measurements = []
    for row in rows:
        for col in cols:
            well_pos = f"{row}{col:02d}"
            obs = vm.cell_painting_assay(well_pos, realism_config_override=realism_config)

            row_idx = ord(row) - ord('A')
            col_idx = col - 1
            is_edge = 1 if (row_idx == 0 or row_idx == 7 or col_idx == 0 or col_idx == 11) else 0

            measurements.append({
                'is_edge': is_edge,
                'morphology': obs['morphology'],
            })

    return measurements


def compute_auc(measurements, shuffle_seed=None):
    """Compute edge AUC with optional shuffling."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler

    X = np.array([[
        m['morphology']['er'],
        m['morphology']['mito'],
        m['morphology']['nucleus'],
        m['morphology']['actin'],
        m['morphology']['rna'],
    ] for m in measurements])

    y = np.array([m['is_edge'] for m in measurements])

    if shuffle_seed is not None:
        rng = np.random.default_rng(shuffle_seed)
        y = rng.permutation(y)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LogisticRegression(C=1.0, max_iter=1000, solver='lbfgs')
    model.fit(X_scaled, y)
    y_pred = model.predict_proba(X_scaled)[:, 1]

    return roc_auc_score(y, y_pred)


def test_final_baseline():
    """Final baseline after fixing hardware_bias roughness."""
    print("=" * 70)
    print("ATTACK 2 FINAL BASELINE: Biology OFF (post-fix)")
    print("=" * 70)

    print("\nGenerating 96-well DMSO plate (Biology OFF)...")
    meas = generate_dmso_plate_biology_off(seed=42)
    auc_real = compute_auc(meas)

    print(f"Real AUC: {auc_real:.4f}")
    print("\nRunning 1000 permutations...")

    null_aucs = []
    for i in range(1000):
        auc = compute_auc(meas, shuffle_seed=7000 + i)
        null_aucs.append(auc)
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/1000...")

    null_aucs = np.array(null_aucs)
    null_mean = null_aucs.mean()
    null_std = null_aucs.std()
    p95 = np.percentile(null_aucs, 95)
    p_value = (null_aucs >= auc_real).sum() / len(null_aucs)

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Real AUC:        {auc_real:.4f}")
    print(f"Null mean ± std: {null_mean:.4f} ± {null_std:.4f}")
    print(f"95th percentile: {p95:.4f}")
    print(f"P-value:         {p_value:.4f}")

    if p_value >= 0.05:
        print("\n✅ ATTACK 2 COMPLETE: All position-coded leaks eliminated")
        print("   - well_biology: exchangeable (well_uid)")
        print("   - well_factor: exchangeable (well_uid)")
        print("   - hardware_bias roughness: exchangeable (well_uid)")
    else:
        print(f"\n❌ RESIDUAL LEAK PERSISTS (p={p_value:.4f})")


if __name__ == "__main__":
    test_final_baseline()
