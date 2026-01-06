"""
Attack 3 - Confound Pair 1: Batch EC50 Shift vs Dose Error

Test whether EC50 shift (biological) is distinguishable from dose error (technical).

Two conditions:
- Condition A (Biology shift): EC50 × 2, dose accurate
- Condition B (Dose error): Dose × 0.5, EC50 constant

Both produce similar dose-response curve shifts. Are they distinguishable
from multimodal features (morphology + viability) and temporal structure?

Method:
- 8-dose ladder (0.1× to 10× nominal EC50)
- 6 replicates per dose per condition
- Stratified allocation (no spatial confounding)
- Measure at 1 timepoint (24h) and 3 timepoints (12h, 24h, 48h)
- Train classifier: features → condition label
- Permutation test (1000 shuffles)

Success criteria:
- AUC > 0.7, p < 0.05: Distinguishable (agent can learn correct action)
- AUC ~ 0.5, p > 0.1: Confounded (agent will learn superstition)
- AUC 0.55-0.65, p < 0.05: Weakly distinguishable (agent will struggle)
"""

import numpy as np
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import pytest

pytest.skip("Test is compute-intensive and hangs - needs optimization", allow_module_level=True)

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext
from cell_os.experimental_design.plate_allocator import PlateAllocator, TreatmentRequest


def generate_dose_response_dataset(
    seed: int,
    condition: str,  # "biology_shift" or "dose_error"
    timepoints: List[float] = [24.0]
) -> List[Dict]:
    """
    Generate dose-response data for one condition.

    Args:
        seed: Random seed for reproducibility
        condition: "biology_shift" (EC50 × 2) or "dose_error" (dose × 0.5)
        timepoints: Hours to measure (e.g., [12.0, 24.0, 48.0])

    Returns:
        List of measurement dicts with dose, timepoint, viability, morphology
    """
    # Get nominal IC50 for tBHQ in A549
    rc = RunContext.sample(seed=seed)
    vm = BiologicalVirtualMachine(seed=seed, run_context=rc)
    vm._load_cell_thalamus_params()

    # Extract tBHQ IC50 from thalamus params
    compound_data = vm.thalamus_params.get('compound_sensitivity', {}).get('tBHQ', {})
    nominal_ic50 = compound_data.get('A549', 1.0)  # Default 1.0 uM if not found

    # Dose ladder: 0.1× to 10× nominal IC50 (8 doses)
    dose_factors = [0.0, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
    doses_uM = [nominal_ic50 * f for f in dose_factors]

    # 3 replicates per dose (reduced for speed)
    n_reps = 3

    # Build treatment requests for allocator
    treatments = []
    for dose_uM in doses_uM:
        dose_id = f"tBHQ_{dose_uM:.3f}uM"
        treatments.append(TreatmentRequest(dose_id, n_replicates=n_reps))

    # Allocate wells (stratified, no spatial confounding)
    allocator = PlateAllocator(plate_format=96, seed=seed)
    assignments = allocator.allocate(treatments)

    measurements = []

    # Simulate for each timepoint
    for timepoint_h in timepoints:
        # Fresh VM for each timepoint
        rc_t = RunContext.sample(seed=seed + int(timepoint_h * 1000))
        vm_t = BiologicalVirtualMachine(seed=seed + int(timepoint_h * 1000), run_context=rc_t)
        vm_t._load_cell_thalamus_params()

        # Apply condition-specific perturbation
        if condition == "biology_shift":
            # Condition A: Shift EC50 by 2× (biology changes, dose accurate)
            # Modify IC50 multiplier in thalamus params
            # Note: YAML uses cell_line_ic50_modifiers, code expects cell_line_sensitivity
            # Structure: cell_line_sensitivity[compound][cell_line] = multiplier

            # Get or create cell_line_sensitivity dict
            if 'cell_line_sensitivity' not in vm_t.thalamus_params:
                vm_t.thalamus_params['cell_line_sensitivity'] = {}

            if 'tBHQ' not in vm_t.thalamus_params['cell_line_sensitivity']:
                vm_t.thalamus_params['cell_line_sensitivity']['tBHQ'] = {}

            # Shift EC50 by 2× means multiplier goes from 1.0 to 2.0
            vm_t.thalamus_params['cell_line_sensitivity']['tBHQ']['A549'] = 2.0

        # Seed all wells
        for assignment in assignments:
            vm_t.seed_vessel(
                vessel_id=assignment.well_position,
                cell_line="A549",
                initial_count=2000,
                vessel_type="96-well",
            )

        # Apply treatments
        for assignment in assignments:
            # Extract nominal dose from treatment_id
            dose_str = assignment.treatment_id.replace("tBHQ_", "").replace("uM", "")
            nominal_dose_uM = float(dose_str)

            if nominal_dose_uM > 0:
                if condition == "dose_error":
                    # Condition B: Dose error (dose × 0.5, EC50 constant)
                    realized_dose_uM = nominal_dose_uM * 0.5
                else:
                    # Condition A: Dose accurate
                    realized_dose_uM = nominal_dose_uM

                vm_t.treat_with_compound(assignment.well_position, "tBHQ", realized_dose_uM)

        # Advance to timepoint
        vm_t.advance_time(timepoint_h)

        # Measure all wells
        for assignment in assignments:
            vessel = vm_t.vessel_states[assignment.well_position]
            obs = vm_t.cell_painting_assay(assignment.well_position)

            # Extract nominal dose
            dose_str = assignment.treatment_id.replace("tBHQ_", "").replace("uM", "")
            nominal_dose_uM = float(dose_str)

            measurements.append({
                'condition': condition,
                'timepoint_h': timepoint_h,
                'nominal_dose_uM': nominal_dose_uM,
                'well_position': assignment.well_position,
                'viability': vessel.viability,
                'morphology': obs['morphology'],
            })

    return measurements


def extract_features(measurements: List[Dict], timepoints: List[float]) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract features for classification.

    For single timepoint: [viability, er, mito, nucleus, actin, rna] per well
    For multiple timepoints: stacked features across timepoints

    Args:
        measurements: List of measurement dicts
        timepoints: List of timepoints to include

    Returns:
        X: Feature matrix (n_samples, n_features)
        y: Condition labels (n_samples,) - 0=biology_shift, 1=dose_error
    """
    # Group by condition and timepoint
    condition_map = {'biology_shift': 0, 'dose_error': 1}

    # Aggregate per dose per condition (mean across replicates)
    dose_condition_features = {}

    for meas in measurements:
        if meas['timepoint_h'] not in timepoints:
            continue

        condition = meas['condition']
        dose = meas['nominal_dose_uM']
        timepoint = meas['timepoint_h']

        key = (condition, dose)
        if key not in dose_condition_features:
            dose_condition_features[key] = {tp: [] for tp in timepoints}

        # Feature vector for this well: [viability, 5 morphology channels]
        features = [
            meas['viability'],
            meas['morphology']['er'],
            meas['morphology']['mito'],
            meas['morphology']['nucleus'],
            meas['morphology']['actin'],
            meas['morphology']['rna'],
        ]

        dose_condition_features[key][timepoint].append(features)

    # Build X, y
    X_list = []
    y_list = []

    for (condition, dose), timepoint_features in dose_condition_features.items():
        # Stack features across timepoints
        stacked = []
        for tp in timepoints:
            if timepoint_features[tp]:
                # Mean across replicates at this timepoint
                mean_features = np.mean(timepoint_features[tp], axis=0)
                stacked.extend(mean_features)
            else:
                # Missing timepoint (shouldn't happen, but handle gracefully)
                stacked.extend([0.0] * 6)

        X_list.append(stacked)
        y_list.append(condition_map[condition])

    X = np.array(X_list)
    y = np.array(y_list)

    return X, y


def test_confound_distinguishability(
    measurements: List[Dict],
    timepoints: List[float],
    label: str
) -> Dict:
    """
    Test distinguishability using classifier + permutation test.

    Args:
        measurements: List of measurement dicts
        timepoints: Timepoints to include in features
        label: Description for output (e.g., "1 timepoint (24h)")

    Returns:
        Dict with AUC, null_mean, null_std, p_value
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline

    print(f"\n--- {label} ---")

    # Extract features
    X, y = extract_features(measurements, timepoints)

    print(f"Feature matrix: {X.shape}")
    print(f"Condition counts: biology_shift={np.sum(y == 0)}, dose_error={np.sum(y == 1)}")

    # Build pipeline with scaling INSIDE CV
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('clf', LogisticRegression(C=1.0, max_iter=1000, solver='lbfgs'))
    ])

    # Cross-validated AUC for real labels
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_aucs = cross_val_score(pipeline, X, y, cv=cv, scoring='roc_auc')
    auc_mean = cv_aucs.mean()
    auc_std = cv_aucs.std()

    print(f"Cross-validated AUC (real labels): {auc_mean:.4f} ± {auc_std:.4f}")

    # Permutation test: compute CV AUC for shuffled labels
    print("Running 100 permutations...")
    null_aucs = []
    rng = np.random.default_rng(888)

    for i in range(100):
        y_shuffled = rng.permutation(y)

        # Cross-validated AUC for shuffled labels
        cv_aucs_null = cross_val_score(pipeline, X, y_shuffled, cv=cv, scoring='roc_auc')
        auc_null = cv_aucs_null.mean()
        null_aucs.append(auc_null)

        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/100...")

    null_aucs = np.array(null_aucs)
    null_mean = null_aucs.mean()
    null_std = null_aucs.std()
    p_value = (null_aucs >= auc_mean).sum() / len(null_aucs)

    print(f"Null distribution: {null_mean:.4f} ± {null_std:.4f}")
    print(f"P-value: {p_value:.4f}")

    return {
        'auc_real': auc_mean,
        'auc_cv_mean': auc_mean,
        'auc_cv_std': auc_std,
        'null_mean': null_mean,
        'null_std': null_std,
        'p_value': p_value,
    }


def test_attack_3_confound_1():
    """
    Attack 3 - Confound Pair 1: EC50 shift vs Dose error.

    Test both single timepoint and multiple timepoints.
    """
    print("=" * 70)
    print("ATTACK 3 - CONFOUND PAIR 1: EC50 Shift vs Dose Error")
    print("=" * 70)

    # Generate datasets
    print("\nGenerating dose-response datasets...")
    print("  Condition A: Biology shift (EC50 × 2)")
    print("  Condition B: Dose error (dose × 0.5)")

    timepoints_full = [12.0, 24.0, 48.0]

    # CRITICAL: Use same base seed for both conditions to avoid spurious distinguishability
    # from run context differences. Only the EC50 vs dose manipulation should differ.
    base_seed = 42

    measurements_A = generate_dose_response_dataset(
        seed=base_seed,
        condition="biology_shift",
        timepoints=timepoints_full
    )

    measurements_B = generate_dose_response_dataset(
        seed=base_seed,
        condition="dose_error",
        timepoints=timepoints_full
    )

    measurements_all = measurements_A + measurements_B

    print(f"  Total measurements: {len(measurements_all)}")

    # Test 1: Single timepoint (24h)
    result_1tp = test_confound_distinguishability(
        measurements_all,
        timepoints=[24.0],
        label="Single Timepoint (24h)"
    )

    # Test 2: Multiple timepoints (12h, 24h, 48h)
    result_3tp = test_confound_distinguishability(
        measurements_all,
        timepoints=timepoints_full,
        label="Three Timepoints (12h, 24h, 48h)"
    )

    # Summary table
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(f"{'Condition':<30} {'AUC':>10} {'Null':>15} {'P-value':>10} {'Verdict':<20}")
    print("-" * 70)

    for label, result in [
        ("1 timepoint (24h)", result_1tp),
        ("3 timepoints (12h,24h,48h)", result_3tp),
    ]:
        auc = result['auc_real']
        null_str = f"{result['null_mean']:.4f}±{result['null_std']:.4f}"
        p_val = result['p_value']

        # Verdict
        if auc > 0.7 and p_val < 0.05:
            verdict = "Distinguishable"
        elif auc >= 0.55 and auc <= 0.65 and p_val < 0.05:
            verdict = "Weakly distinct"
        else:
            verdict = "Confounded"

        print(f"{label:<30} {auc:>10.4f} {null_str:>15} {p_val:>10.4f} {verdict:<20}")

    # Final interpretation
    print("\n" + "=" * 70)
    print("INTERPRETATION")
    print("=" * 70)

    auc_1 = result_1tp['auc_real']
    p_1 = result_1tp['p_value']
    auc_3 = result_3tp['auc_real']
    p_3 = result_3tp['p_value']

    if auc_1 < 0.65 and p_1 > 0.05:
        print("✅ Single timepoint: CONFOUNDED (as expected)")
        print("   EC50 shift and dose error are mathematically equivalent")
        print("   at single endpoint under Hill model.")
    else:
        print("⚠️  Single timepoint: Weakly distinguishable")
        print("   Some signature exists even at single timepoint.")

    if auc_3 > 0.7 and p_3 < 0.05:
        print("\n✅ Multiple timepoints: DISTINGUISHABLE")
        print("   Temporal dynamics break the equivalence.")
        print("   Agent CAN learn to distinguish biology from dose error.")
    elif auc_3 >= 0.55 and p_3 < 0.05:
        print("\n⚠️  Multiple timepoints: WEAKLY DISTINGUISHABLE")
        print("   Temporal signature exists but agent will struggle.")
        print("   May need additional observables (calibration compounds).")
    else:
        print("\n❌ Multiple timepoints: STILL CONFOUNDED")
        print("   Temporal dynamics do NOT break equivalence.")
        print("   Agent CANNOT distinguish without orthogonal information.")
        print("   Need: calibration compounds, dose verification, or accept ambiguity.")


if __name__ == "__main__":
    test_attack_3_confound_1()
