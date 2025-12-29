"""
Validate well_biology exchangeable sampling fix with proper permutation test.

Uses 96-well plate and 1000-shuffle permutation baseline.
"""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext


def generate_dmso_plate_96well(seed: int, null_biology: bool = False):
    """
    Generate 96-well DMSO plate with detector edge effects OFF.

    Args:
        seed: Run seed
        null_biology: If True, manually zero out well_biology (for "biology OFF" condition)
    """
    # Disable detector edge effects
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

    # 96-well: 8 rows × 12 cols
    rows = [chr(ord('A') + i) for i in range(8)]
    cols = list(range(1, 13))

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

            if null_biology:
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

    measurements = []
    for vessel_id, well_pos, row, col in vessel_ids:
        obs = vm.cell_painting_assay(vessel_id, realism_config_override=realism_config)

        row_idx = ord(row) - ord('A')
        col_idx = col - 1
        is_edge = 1 if (row_idx == 0 or row_idx == 7 or col_idx == 0 or col_idx == 11) else 0

        measurements.append({
            'well_pos': well_pos,
            'is_edge': is_edge,
            'morphology': obs['morphology'],
        })

    return measurements


def compute_edge_auc(measurements, y_edge=None, shuffle_seed=None):
    """Compute edge AUC with optional label shuffling."""
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

    if y_edge is None:
        y_edge = np.array([m['is_edge'] for m in measurements])

    if shuffle_seed is not None:
        rng = np.random.default_rng(shuffle_seed)
        y_edge = rng.permutation(y_edge)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LogisticRegression(C=1.0, max_iter=1000, solver='lbfgs')
    model.fit(X_scaled, y_edge)
    y_pred = model.predict_proba(X_scaled)[:, 1]
    auc = roc_auc_score(y_edge, y_pred)

    return auc


def permutation_test(measurements, n_permutations=1000):
    """Run permutation test with many shuffles."""
    print(f"Running {n_permutations} permutations...")

    null_aucs = []
    for i in range(n_permutations):
        auc = compute_edge_auc(measurements, shuffle_seed=1000 + i)
        null_aucs.append(auc)
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{n_permutations}...")

    return np.array(null_aucs)


def test_fix_validation():
    """Validate fix with permutation test on 96-well plate."""
    print("=" * 70)
    print("ATTACK 2 FIX VALIDATION: Exchangeable Well Biology")
    print("=" * 70)

    # Test 1: Biology ON (should show no edge learnability after fix)
    print("\n--- TEST 1: Biology ON (post-fix) ---")
    measurements_on = generate_dmso_plate_96well(seed=42, null_biology=False)
    auc_on = compute_edge_auc(measurements_on)
    print(f"Edge AUC (biology ON): {auc_on:.4f}")

    # Test 2: Biology OFF (control)
    print("\n--- TEST 2: Biology OFF (control) ---")
    measurements_off = generate_dmso_plate_96well(seed=42, null_biology=True)
    auc_off = compute_edge_auc(measurements_off)
    print(f"Edge AUC (biology OFF): {auc_off:.4f}")

    # Permutation test on Biology ON
    print("\n--- PERMUTATION TEST (Biology ON) ---")
    null_aucs = permutation_test(measurements_on, n_permutations=1000)

    null_mean = null_aucs.mean()
    null_std = null_aucs.std()
    p_value = (null_aucs >= auc_on).sum() / len(null_aucs)

    print(f"\nNull distribution (shuffled labels):")
    print(f"  Mean: {null_mean:.4f}")
    print(f"  Std:  {null_std:.4f}")
    print(f"  95th percentile: {np.percentile(null_aucs, 95):.4f}")
    print(f"\nReal AUC: {auc_on:.4f}")
    print(f"P-value: {p_value:.4f} (fraction of shuffles >= real AUC)")

    # Decision
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)

    if p_value < 0.05 and auc_on > null_mean + 2 * null_std:
        print(f"❌ FAIL: Edge is still learnable (p={p_value:.4f})")
        print(f"  Real AUC {auc_on:.4f} >> null {null_mean:.4f} ± {null_std:.4f}")
        print("  Well biology still leaks position information")
    elif auc_on > null_mean + null_std:
        print(f"⚠️  WEAK SIGNAL: AUC slightly elevated (p={p_value:.4f})")
        print(f"  Real AUC {auc_on:.4f} vs null {null_mean:.4f} ± {null_std:.4f}")
        print("  May indicate residual leak or random fluctuation")
    else:
        print(f"✅ PASS: Edge not learnable (p={p_value:.4f})")
        print(f"  Real AUC {auc_on:.4f} within null {null_mean:.4f} ± {null_std:.4f}")
        print("  Well biology no longer encodes position")

    return {
        'auc_on': auc_on,
        'auc_off': auc_off,
        'null_mean': null_mean,
        'null_std': null_std,
        'p_value': p_value,
    }


if __name__ == "__main__":
    test_fix_validation()
