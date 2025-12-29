"""
Attack 2.3: Residual edge leak provenance (3-cut decomposition).

Tests Biology OFF with 3 toggles to isolate remaining leak.
"""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext


def null_hardware_bias(*args, **kwargs):
    """Null hardware bias (Cut B)."""
    return {'volume_factor': 1.0, 'roughness_factor': 1.0}


def generate_dmso_plate_biology_off(seed: int, cut: str = "baseline"):
    """
    Generate 96-well DMSO plate with Biology OFF.

    Args:
        seed: Run seed
        cut: "baseline", "cut_a_evap", "cut_b_hardware", "cut_c_focus"
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

    # Cut B: Null hardware plating bias
    if cut == "cut_b_hardware":
        import cell_os.hardware.hardware_artifacts
        cell_os.hardware.hardware_artifacts.get_hardware_bias = null_hardware_bias

    vm = BiologicalVirtualMachine(seed=seed, run_context=rc)
    vm._load_cell_thalamus_params()

    # Cut C: Null focus factor
    if cut == "cut_c_focus":
        vm.thalamus_params['technical_noise']['focus_cv'] = 0.0

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

            state = vm.vessel_states[well_pos]

            # NULL well biology
            state.well_biology = {
                "er_baseline_shift": 0.0,
                "mito_baseline_shift": 0.0,
                "rna_baseline_shift": 0.0,
                "nucleus_baseline_shift": 0.0,
                "actin_baseline_shift": 0.0,
                "stress_susceptibility": 1.0,
            }

            # Cut A: Null evaporation (freeze volume)
            if cut == "cut_a_evap":
                state.total_evaporated_ml = 0.0
                # Freeze volume by setting to initial and preventing change
                # (evaporation happens during advance_time, so we'll need to reset after)

    vm.advance_time(24.0)

    # Cut A: If evaporation cut, reset volumes to prevent concentration shift
    if cut == "cut_a_evap":
        for row in rows:
            for col in cols:
                well_pos = f"{row}{col:02d}"
                state = vm.vessel_states[well_pos]
                # Reset to working volume (as if no evaporation occurred)
                if state.working_volume_ml is not None:
                    state.current_volume_ml = state.working_volume_ml
                state.total_evaporated_ml = 0.0

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
        auc = compute_auc(measurements, shuffle_seed=6000 + i)
        null_aucs.append(auc)
    return np.array(null_aucs)


def run_cut(cut_name: str, cut_code: str):
    """Run one cut condition."""
    print(f"\n--- {cut_name} ---")
    meas = generate_dmso_plate_biology_off(seed=42, cut=cut_code)
    auc_real = compute_auc(meas)

    null_aucs = permutation_test(meas, n_perm=1000)
    null_mean = null_aucs.mean()
    null_std = null_aucs.std()
    p95 = np.percentile(null_aucs, 95)
    p_value = (null_aucs >= auc_real).sum() / len(null_aucs)

    return {
        'auc': auc_real,
        'null_mean': null_mean,
        'null_std': null_std,
        'p95': p95,
        'p_value': p_value,
    }


def test_attack_23():
    """Attack 2.3: 3-cut residual leak provenance."""
    print("=" * 70)
    print("ATTACK 2.3: Residual Edge Leak Provenance (Biology OFF)")
    print("=" * 70)

    results = {}

    # Condition 1: Baseline (failing case from Attack 2 final validation)
    results['baseline'] = run_cut("1. Baseline Biology OFF", "baseline")

    # Condition 2: Cut A - Evaporation nulled
    results['cut_a'] = run_cut("2. Biology OFF + Cut A (evaporation nulled)", "cut_a_evap")

    # Condition 3: Cut B - Hardware plating bias identity
    results['cut_b'] = run_cut("3. Biology OFF + Cut B (hardware bias identity)", "cut_b_hardware")

    # Condition 4: Cut C - Focus factor identity
    results['cut_c'] = run_cut("4. Biology OFF + Cut C (focus factor nulled)", "cut_c_focus")

    # Results table
    print("\n" + "=" * 70)
    print("RESULTS TABLE")
    print("=" * 70)
    print(f"{'Condition':<40} {'Real AUC':>10} {'Null':>15} {'P95':>8} {'P-value':>10}")
    print("-" * 70)

    for key, label in [
        ('baseline', '1. Baseline Biology OFF'),
        ('cut_a', '2. Biology OFF + Cut A (evap null)'),
        ('cut_b', '2. Biology OFF + Cut B (hw bias null)'),
        ('cut_c', '3. Biology OFF + Cut C (focus null)'),
    ]:
        r = results[key]
        null_str = f"{r['null_mean']:.4f}±{r['null_std']:.4f}"
        print(f"{label:<40} {r['auc']:>10.4f} {null_str:>15} {r['p95']:>8.4f} {r['p_value']:>10.4f}")

    return results


if __name__ == "__main__":
    test_attack_23()
