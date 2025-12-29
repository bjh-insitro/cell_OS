"""
Final validation of exchangeable well UID fix (Attack 2).

Tests both Biology ON and Biology OFF with 1000-permutation baseline.
"""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext


def generate_dmso_plate(seed: int, null_biology: bool = False):
    """Generate 96-well DMSO plate with detector edge effects OFF."""
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

            if null_biology:
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


def permutation_test(measurements, n_perm=1000):
    """Run permutation test."""
    null_aucs = []
    for i in range(n_perm):
        auc = compute_auc(measurements, shuffle_seed=5000 + i)
        null_aucs.append(auc)
        if (i + 1) % 100 == 0:
            print(f"    {i + 1}/{n_perm}...")
    return np.array(null_aucs)


def test_final_validation():
    """Final validation with proper exchangeable well UIDs."""
    print("=" * 70)
    print("ATTACK 2 FINAL VALIDATION: Exchangeable Well UIDs")
    print("=" * 70)

    # Test 1: Biology ON
    print("\n--- TEST 1: Biology ON ---")
    print("Generating 96-well DMSO plate...")
    meas_on = generate_dmso_plate(seed=42, null_biology=False)
    auc_on = compute_auc(meas_on)
    print(f"Real AUC (Biology ON): {auc_on:.4f}")

    print("Running 1000 permutations (Biology ON)...")
    null_on = permutation_test(meas_on, n_perm=1000)
    null_on_mean = null_on.mean()
    null_on_std = null_on.std()
    p_on = (null_on >= auc_on).sum() / len(null_on)

    print(f"\nNull: {null_on_mean:.4f} ± {null_on_std:.4f}")
    print(f"95th percentile: {np.percentile(null_on, 95):.4f}")
    print(f"P-value: {p_on:.4f}")

    # Test 2: Biology OFF
    print("\n--- TEST 2: Biology OFF ---")
    print("Generating 96-well DMSO plate...")
    meas_off = generate_dmso_plate(seed=42, null_biology=True)
    auc_off = compute_auc(meas_off)
    print(f"Real AUC (Biology OFF): {auc_off:.4f}")

    print("Running 1000 permutations (Biology OFF)...")
    null_off = permutation_test(meas_off, n_perm=1000)
    null_off_mean = null_off.mean()
    null_off_std = null_off.std()
    p_off = (null_off >= auc_off).sum() / len(null_off)

    print(f"\nNull: {null_off_mean:.4f} ± {null_off_std:.4f}")
    print(f"95th percentile: {np.percentile(null_off, 95):.4f}")
    print(f"P-value: {p_off:.4f}")

    # Verdict
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)

    pass_on = p_on >= 0.05
    pass_off = p_off >= 0.05

    print(f"\nBiology ON:  {'✅ PASS' if pass_on else '❌ FAIL'} (p={p_on:.4f})")
    print(f"Biology OFF: {'✅ PASS' if pass_off else '❌ FAIL'} (p={p_off:.4f})")

    if pass_on and pass_off:
        print("\n✅ ATTACK 2 COMPLETE: Position-coded leaks eliminated")
        print("   - well_biology seed now uses exchangeable well_uid")
        print("   - well_factor seed now uses exchangeable well_uid")
        print("   - Edge membership NOT learnable from morphology")
    else:
        print("\n❌ RESIDUAL LEAK: Edge still learnable")
        if not pass_on:
            print("   - Biology ON failed: well_biology or well_factor still leaks")
        if not pass_off:
            print("   - Biology OFF failed: another position-coded path exists")

    return {
        'auc_on': auc_on,
        'p_on': p_on,
        'null_on_mean': null_on_mean,
        'null_on_std': null_on_std,
        'auc_off': auc_off,
        'p_off': p_off,
        'null_off_mean': null_off_mean,
        'null_off_std': null_off_std,
    }


if __name__ == "__main__":
    test_final_validation()
