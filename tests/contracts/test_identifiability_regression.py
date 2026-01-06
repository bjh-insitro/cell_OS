"""
Identifiability Regression Tests

These tests assert that certain confounds remain observationally equivalent.
If these tests start failing, it means we accidentally introduced "magic disambiguation"
- a dependency that allows the agent to distinguish things that should be indistinguishable.

Purpose:
- Prevent false confidence in causal inference
- Maintain honest epistemic boundaries
- Catch layer mismatches (e.g., dose affects one pathway, EC50 affects another)
- Catch absolute-concentration dependencies that break scale invariance

When a test fails:
1. Investigate what changed in the simulator
2. Determine if the change is realistic or an artifact
3. If realistic: Update the confound matrix documentation
4. If artifact: Revert the change

Exit criteria for "confounded":
- AUC < 0.65 AND p-value > 0.1
"""

import numpy as np
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import pytest

pytest.skip("Identifiability regression tests are compute-intensive - skipping", allow_module_level=True)

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext
from cell_os.experimental_design.plate_allocator import PlateAllocator, TreatmentRequest
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline


def compute_confound_distinguishability(
    measurements: List[Dict],
    timepoints: List[float]
) -> Tuple[float, float]:
    """
    Test if two conditions are distinguishable using cross-validated permutation test.

    Returns:
        (auc_mean, p_value)
    """
    # Extract features: aggregate by (condition, dose)
    condition_map = {'A': 0, 'B': 1}
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
        stacked = []
        for tp in timepoints:
            if timepoint_features[tp]:
                mean_features = np.mean(timepoint_features[tp], axis=0)
                stacked.extend(mean_features)
            else:
                stacked.extend([0.0] * 6)

        X_list.append(stacked)
        y_list.append(condition_map[condition])

    X = np.array(X_list)
    y = np.array(y_list)

    # Pipeline with scaling inside CV
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('clf', LogisticRegression(C=1.0, max_iter=1000, solver='lbfgs'))
    ])

    # Cross-validated AUC for real labels
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_aucs = cross_val_score(pipeline, X, y, cv=cv, scoring='roc_auc')
    auc_mean = cv_aucs.mean()

    # Permutation test
    rng = np.random.default_rng(888)
    null_aucs = []

    for i in range(100):
        y_shuffled = rng.permutation(y)
        cv_aucs_null = cross_val_score(pipeline, X, y_shuffled, cv=cv, scoring='roc_auc')
        null_aucs.append(cv_aucs_null.mean())

    null_aucs = np.array(null_aucs)
    p_value = (null_aucs >= auc_mean).sum() / len(null_aucs)

    return auc_mean, p_value


def generate_ec50_vs_dose_data(seed: int, timepoints: List[float]) -> List[Dict]:
    """
    Generate data for EC50 shift vs Dose error confound.

    This pair MUST remain confounded (observationally equivalent).
    """
    measurements = []

    for condition, manipulate_ec50, dose_scale in [('A', True, 1.0), ('B', False, 0.5)]:
        rc = RunContext.sample(seed=seed)

        for timepoint_h in timepoints:
            vm = BiologicalVirtualMachine(seed=seed + int(timepoint_h * 1000), run_context=rc)
            vm._load_cell_thalamus_params()

            # Apply EC50 manipulation
            if manipulate_ec50:
                if 'cell_line_sensitivity' not in vm.thalamus_params:
                    vm.thalamus_params['cell_line_sensitivity'] = {}
                if 'tBHQ' not in vm.thalamus_params['cell_line_sensitivity']:
                    vm.thalamus_params['cell_line_sensitivity']['tBHQ'] = {}
                vm.thalamus_params['cell_line_sensitivity']['tBHQ']['A549'] = 2.0

            # Get nominal EC50
            nominal_ec50 = vm.thalamus_params['compounds']['tBHQ']['ec50_uM']

            # Dose ladder
            dose_factors = [0.0, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
            doses_uM = [nominal_ec50 * f for f in dose_factors]

            # Allocate wells
            treatments = [TreatmentRequest(f"tBHQ_{d:.3f}uM", n_replicates=3) for d in doses_uM]
            allocator = PlateAllocator(plate_format=96, seed=seed)
            assignments = allocator.allocate(treatments)

            # Seed wells
            for assignment in assignments:
                vm.seed_vessel(assignment.well_position, "A549", initial_count=2000,
                             capacity=1e7, vessel_type="96-well")

            # Apply treatments
            for assignment in assignments:
                dose_str = assignment.treatment_id.replace("tBHQ_", "").replace("uM", "")
                nominal_dose_uM = float(dose_str)

                if nominal_dose_uM > 0:
                    realized_dose_uM = nominal_dose_uM * dose_scale
                    vm.treat_with_compound(assignment.well_position, "tBHQ", realized_dose_uM)

            # Advance time
            vm.advance_time(timepoint_h)

            # Measure
            for assignment in assignments:
                vessel = vm.vessel_states[assignment.well_position]
                obs = vm.cell_painting_assay(assignment.well_position)

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


def test_ec50_vs_dose_remains_confounded():
    """
    REGRESSION TEST: EC50 shift vs Dose error must remain confounded.

    Mathematical basis:
    - EC50 × 2 and Dose × 0.5 produce identical C/EC50 ratios
    - Hill equation is scale-invariant: Effect = f(C/EC50, hill_slope)
    - Therefore observationally equivalent

    If this test fails, we accidentally introduced:
    - Absolute-concentration dependency (stress thresholds, commitment gates, etc.)
    - Layer mismatch (dose affects one pathway, EC50 affects another)
    - Run context asymmetry (EC50 modifier applied inconsistently)

    Exit criteria for "confounded":
    - AUC < 0.65 (near chance)
    - p-value > 0.1 (not significant)
    """
    print("=" * 80)
    print("REGRESSION: EC50 Shift vs Dose Error Must Remain Confounded")
    print("=" * 80)

    timepoints = [12.0, 24.0, 48.0]
    measurements = generate_ec50_vs_dose_data(seed=42, timepoints=timepoints)

    print(f"Generated {len(measurements)} measurements")

    # Test distinguishability
    auc, pval = compute_confound_distinguishability(measurements, timepoints)

    print(f"\nAUC: {auc:.4f} (must be < 0.65 for confounded)")
    print(f"P-value: {pval:.4f} (must be > 0.1 for confounded)")

    # Assert confounded
    if auc >= 0.65:
        raise AssertionError(
            f"❌ EC50 vs Dose became distinguishable (AUC={auc:.3f})!\n"
            f"   This breaks scale invariance. Check for:\n"
            f"   - Absolute-concentration dependencies\n"
            f"   - Layer mismatches\n"
            f"   - Run context asymmetries"
        )

    if pval <= 0.1:
        raise AssertionError(
            f"❌ EC50 vs Dose became significant (p={pval:.3f})!\n"
            f"   This breaks scale invariance. Check for:\n"
            f"   - Absolute-concentration dependencies\n"
            f"   - Layer mismatches\n"
            f"   - Run context asymmetries"
        )

    print("\n✅ PASS: EC50 vs Dose remains confounded (scale-invariant)")
    print("   Agent correctly cannot distinguish without calibration")


if __name__ == "__main__":
    test_ec50_vs_dose_remains_confounded()
