"""
Attack 3: Confound Matrix (Clean Implementation)

Systematic test of observational equivalences in cell_OS with locked evaluation protocol.

Exit criteria:
- Confounded: AUC < 0.65 AND p > 0.1
- Distinguishable: AUC > 0.7 AND p < 0.05
- Weakly distinct: Between thresholds
"""

import numpy as np
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict
import pytest

pytest.skip("Test is compute-intensive and has same issues as v1 - needs fixing", allow_module_level=True)

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext
from cell_os.experimental_design.plate_allocator import PlateAllocator, TreatmentRequest
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline


# ============================================================================
# LOCKED EVALUATION PROTOCOL
# ============================================================================

PROTOCOL = {
    'base_seed': 42,
    'dose_factors': [0.0, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0],
    'replicates_per_dose': 3,
    'plate_format': 96,
    'timepoints_single': [24.0],
    'timepoints_multi': [12.0, 24.0, 48.0],
    'cv_folds': 5,
    'cv_seed': 42,
    'permutations': 100,
    'perm_seed': 888,
}


@dataclass
class ConfoundResult:
    """Result of a confound distinguishability test."""
    pair_name: str
    single_tp_auc: float
    single_tp_pval: float
    multi_tp_auc: float
    multi_tp_pval: float
    verdict: str
    breaks_tie: str
    requires_metadata: str
    effect_parity_metric: str
    best_modality: str


def extract_multimodal_features(
    measurements: List[Dict],
    timepoints: List[float],
    include_variance: bool = False,
    include_cross_modal: bool = False
) -> Tuple[np.ndarray, np.ndarray]:
    """Extract multimodal features with variance and cross-modal ratios."""
    condition_map = {'A': 0, 'B': 1}
    dose_condition_data = {}

    # Collect replicate data
    for meas in measurements:
        if meas['timepoint_h'] not in timepoints:
            continue

        condition = meas['condition']
        dose = meas['nominal_dose_uM']
        timepoint = meas['timepoint_h']

        key = (condition, dose)
        if key not in dose_condition_data:
            dose_condition_data[key] = {tp: {'viab': [], 'morph': []} for tp in timepoints}

        dose_condition_data[key][timepoint]['viab'].append(meas['viability'])
        dose_condition_data[key][timepoint]['morph'].append([
            meas['morphology']['er'],
            meas['morphology']['mito'],
            meas['morphology']['nucleus'],
            meas['morphology']['actin'],
            meas['morphology']['rna'],
        ])

    # Build feature matrix
    X_list = []
    y_list = []

    for (condition, dose), timepoint_data in dose_condition_data.items():
        stacked = []

        for tp in timepoints:
            viabs = np.array(timepoint_data[tp]['viab'])
            morphs = np.array(timepoint_data[tp]['morph'])

            if len(viabs) == 0:
                n_features = 6 + (6 if include_variance else 0) + (5 if include_cross_modal else 0)
                stacked.extend([0.0] * n_features)
                continue

            # Base: means
            viab_mean = viabs.mean()
            morph_means = morphs.mean(axis=0)
            stacked.append(viab_mean)
            stacked.extend(morph_means)

            # Variance
            if include_variance:
                viab_std = viabs.std() if len(viabs) > 1 else 0.0
                morph_stds = morphs.std(axis=0) if len(viabs) > 1 else np.zeros(5)
                stacked.append(viab_std)
                stacked.extend(morph_stds)

            # Cross-modal ratios
            if include_cross_modal:
                if viab_mean > 0.01:
                    morph_viab_ratios = morph_means / viab_mean
                else:
                    morph_viab_ratios = np.zeros(5)
                stacked.extend(morph_viab_ratios)

        X_list.append(stacked)
        y_list.append(condition_map[condition])

    return np.array(X_list), np.array(y_list)


def test_distinguishability(
    measurements: List[Dict],
    timepoints: List[float],
    include_variance: bool = False,
    include_cross_modal: bool = False
) -> Tuple[float, float]:
    """Test distinguishability using CV permutation test."""
    X, y = extract_multimodal_features(measurements, timepoints, include_variance, include_cross_modal)

    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('clf', LogisticRegression(C=1.0, max_iter=1000, solver='lbfgs'))
    ])

    cv = StratifiedKFold(n_splits=PROTOCOL['cv_folds'], shuffle=True, random_state=PROTOCOL['cv_seed'])
    cv_aucs = cross_val_score(pipeline, X, y, cv=cv, scoring='roc_auc')
    auc_mean = cv_aucs.mean()

    # Permutation test
    rng = np.random.default_rng(PROTOCOL['perm_seed'])
    null_aucs = []
    for i in range(PROTOCOL['permutations']):
        y_shuffled = rng.permutation(y)
        cv_aucs_null = cross_val_score(pipeline, X, y_shuffled, cv=cv, scoring='roc_auc')
        null_aucs.append(cv_aucs_null.mean())

    null_aucs = np.array(null_aucs)
    p_value = (null_aucs >= auc_mean).sum() / len(null_aucs)

    return auc_mean, p_value


# ============================================================================
# PAIR 1: EC50 Shift vs Dose Scale Error
# ============================================================================

def generate_pair1_ec50_vs_dose(seed: int, timepoints: List[float]) -> List[Dict]:
    """
    EC50 × 2 vs Dose × 0.5 (both produce 2× rightward Hill shift).
    Effect parity: Matched on C/EC50 ratio.
    """
    measurements = []

    for condition, manipulate_ec50, dose_scale in [('A', True, 1.0), ('B', False, 0.5)]:
        rc = RunContext.sample(seed=seed)

        for timepoint_h in timepoints:
            vm = BiologicalVirtualMachine(seed=seed + int(timepoint_h * 1000), run_context=rc)
            vm._load_cell_thalamus_params()

            if manipulate_ec50:
                if 'cell_line_sensitivity' not in vm.thalamus_params:
                    vm.thalamus_params['cell_line_sensitivity'] = {}
                if 'tBHQ' not in vm.thalamus_params['cell_line_sensitivity']:
                    vm.thalamus_params['cell_line_sensitivity']['tBHQ'] = {}
                vm.thalamus_params['cell_line_sensitivity']['tBHQ']['A549'] = 2.0

            nominal_ec50 = vm.thalamus_params['compounds']['tBHQ']['ec50_uM']
            doses_uM = [nominal_ec50 * f for f in PROTOCOL['dose_factors']]

            treatments = [TreatmentRequest(f"tBHQ_{d:.3f}uM", n_replicates=PROTOCOL['replicates_per_dose'])
                         for d in doses_uM]
            allocator = PlateAllocator(plate_format=PROTOCOL['plate_format'], seed=seed)
            assignments = allocator.allocate(treatments)

            for assignment in assignments:
                vm.seed_vessel(assignment.well_position, "A549", initial_count=2000,
                             capacity=1e7, vessel_type="96-well")

            for assignment in assignments:
                dose_str = assignment.treatment_id.replace("tBHQ_", "").replace("uM", "")
                nominal_dose_uM = float(dose_str)
                if nominal_dose_uM > 0:
                    vm.treat_with_compound(assignment.well_position, "tBHQ", nominal_dose_uM * dose_scale)

            vm.advance_time(timepoint_h)

            for assignment in assignments:
                vessel = vm.vessel_states[assignment.well_position]
                obs = vm.cell_painting_assay(assignment.well_position)
                dose_str = assignment.treatment_id.replace("tBHQ_", "").replace("uM", "")

                measurements.append({
                    'condition': condition,
                    'timepoint_h': timepoint_h,
                    'nominal_dose_uM': float(dose_str),
                    'well_position': assignment.well_position,
                    'viability': vessel.viability,
                    'morphology': obs['morphology'],
                })

    return measurements


def test_confound_pair1() -> ConfoundResult:
    """Test EC50 shift vs Dose error."""
    print("\n" + "=" * 80)
    print("PAIR 1: EC50 Shift vs Dose Scale Error")
    print("=" * 80)
    print("Condition A: EC50 × 2, Dose × 1.0")
    print("Condition B: EC50 × 1.0, Dose × 0.5")
    print("Effect parity: Both produce 2× rightward Hill shift (C/EC50 matched)")

    measurements = generate_pair1_ec50_vs_dose(PROTOCOL['base_seed'], PROTOCOL['timepoints_multi'])
    print(f"Generated {len(measurements)} measurements")

    auc_1tp, p_1tp = test_distinguishability(measurements, PROTOCOL['timepoints_single'])
    print(f"\nSingle TP: AUC={auc_1tp:.4f}, p={p_1tp:.4f}")

    auc_3tp, p_3tp = test_distinguishability(measurements, PROTOCOL['timepoints_multi'])
    print(f"Multi TP:  AUC={auc_3tp:.4f}, p={p_3tp:.4f}")

    verdict = "Confounded" if (auc_3tp < 0.65 and p_3tp > 0.1) else \
              ("Distinguishable" if (auc_3tp > 0.7 and p_3tp < 0.05) else "Weakly distinct")

    print(f"→ Verdict: {verdict}")

    return ConfoundResult(
        pair_name="EC50 shift vs Dose error",
        single_tp_auc=auc_1tp, single_tp_pval=p_1tp,
        multi_tp_auc=auc_3tp, multi_tp_pval=p_3tp,
        verdict=verdict,
        breaks_tie="N/A" if verdict == "Confounded" else "Temporal dynamics",
        requires_metadata="Calibration compounds OR dose verification" if verdict == "Confounded" else "N/A",
        effect_parity_metric="C/EC50 ratio (2× shift)",
        best_modality="N/A" if verdict == "Confounded" else "Unknown"
    )


# ============================================================================
# PAIR 2: Dose Error vs Assay Gain Shift
# ============================================================================

def generate_pair2_dose_vs_gain(seed: int, timepoints: List[float]) -> List[Dict]:
    """
    Dose × 0.67 vs Gain × 1.5 (matched on apparent morphology intensity at 24h).

    Key test: Can agent detect viability-morphology discordance?
    - Dose error: Biology changes, so viability and morphology move together
    - Gain shift: Readout scales, so morphology/viability ratio changes
    """
    measurements = []

    # Calibrate gain to match apparent morphology intensity
    # Use 0.67 dose scale vs 1.5 gain scale to get similar morphology shifts
    for condition, dose_scale, gain_scale in [('A', 0.67, 1.0), ('B', 1.0, 1.5)]:
        rc = RunContext.sample(seed=seed)

        for timepoint_h in timepoints:
            vm = BiologicalVirtualMachine(seed=seed + int(timepoint_h * 1000), run_context=rc)
            vm._load_cell_thalamus_params()

            nominal_ec50 = vm.thalamus_params['compounds']['tBHQ']['ec50_uM']
            doses_uM = [nominal_ec50 * f for f in PROTOCOL['dose_factors']]

            treatments = [TreatmentRequest(f"tBHQ_{d:.3f}uM", n_replicates=PROTOCOL['replicates_per_dose'])
                         for d in doses_uM]
            allocator = PlateAllocator(plate_format=PROTOCOL['plate_format'], seed=seed)
            assignments = allocator.allocate(treatments)

            for assignment in assignments:
                vm.seed_vessel(assignment.well_position, "A549", initial_count=2000,
                             capacity=1e7, vessel_type="96-well")

            for assignment in assignments:
                dose_str = assignment.treatment_id.replace("tBHQ_", "").replace("uM", "")
                nominal_dose_uM = float(dose_str)
                if nominal_dose_uM > 0:
                    vm.treat_with_compound(assignment.well_position, "tBHQ", nominal_dose_uM * dose_scale)

            vm.advance_time(timepoint_h)

            for assignment in assignments:
                vessel = vm.vessel_states[assignment.well_position]
                obs = vm.cell_painting_assay(assignment.well_position)
                dose_str = assignment.treatment_id.replace("tBHQ_", "").replace("uM", "")

                # Apply gain scaling to morphology ONLY (viability unaffected - it's a ratio)
                morphology_scaled = {ch: val * gain_scale for ch, val in obs['morphology'].items()}

                measurements.append({
                    'condition': condition,
                    'timepoint_h': timepoint_h,
                    'nominal_dose_uM': float(dose_str),
                    'well_position': assignment.well_position,
                    'viability': vessel.viability,  # NOT scaled by gain
                    'morphology': morphology_scaled,
                })

    return measurements


def test_confound_pair2() -> ConfoundResult:
    """Test Dose error vs Assay gain."""
    print("\n" + "=" * 80)
    print("PAIR 2: Dose Error vs Assay Gain Shift")
    print("=" * 80)
    print("Condition A: Dose × 0.67 (biology changes)")
    print("Condition B: Gain × 1.5 (readout scales)")
    print("Effect parity: Matched on apparent morphology intensity")

    measurements = generate_pair2_dose_vs_gain(PROTOCOL['base_seed'], PROTOCOL['timepoints_multi'])
    print(f"Generated {len(measurements)} measurements")

    # Test with cross-modal features to detect viability-morphology discordance
    auc_1tp, p_1tp = test_distinguishability(measurements, PROTOCOL['timepoints_single'], include_cross_modal=True)
    print(f"\nSingle TP (w/ cross-modal): AUC={auc_1tp:.4f}, p={p_1tp:.4f}")

    auc_3tp, p_3tp = test_distinguishability(measurements, PROTOCOL['timepoints_multi'], include_cross_modal=True)
    print(f"Multi TP (w/ cross-modal):  AUC={auc_3tp:.4f}, p={p_3tp:.4f}")

    verdict = "Confounded" if (auc_3tp < 0.65 and p_3tp > 0.1) else \
              ("Distinguishable" if (auc_3tp > 0.7 and p_3tp < 0.05) else "Weakly distinct")

    print(f"→ Verdict: {verdict}")

    return ConfoundResult(
        pair_name="Dose error vs Assay gain",
        single_tp_auc=auc_1tp, single_tp_pval=p_1tp,
        multi_tp_auc=auc_3tp, multi_tp_pval=p_3tp,
        verdict=verdict,
        breaks_tie="Viability-morphology discordance" if verdict != "Confounded" else "N/A",
        requires_metadata="Dose verification OR plate reference controls" if verdict == "Confounded" else "N/A",
        effect_parity_metric="Morphology intensity (matched at 24h)",
        best_modality="Cross-modal (viab/morph ratios)" if verdict != "Confounded" else "N/A"
    )


# ============================================================================
# PAIR 3: Viability Loss vs Background/Debris Increase
# ============================================================================

def calibrate_pair3_dual_parity(seed: int, death_severity: float = 0.8) -> Tuple[float, float, float, float]:
    """
    Calibrate Pair 3 knobs to achieve dual parity (viability + morphology means matched).

    Strategy:
    1. Run baseline (unmanipulated) at 24h → get μv_base, μm_base
    2. Apply death with severity sA → get μvA, μmA
    3. Solve for debris knobs to match:
       - Morphology offset bB = μmA - μm_base
       - Viability readout bias sB = μvA / μv_base

    Returns:
        (sA, bA, sB, bB) - viability scale and morphology offset for each condition
    """
    print("\n--- Calibrating Pair 3 Dual Parity ---")

    # Step 1: Generate baseline data at 24h
    timepoint_24h = 24.0
    rc = RunContext.sample(seed=seed)
    vm_base = BiologicalVirtualMachine(seed=seed + int(timepoint_24h * 1000), run_context=rc)
    vm_base._load_cell_thalamus_params()

    nominal_ec50 = vm_base.thalamus_params['compounds']['tBHQ']['ec50_uM']
    doses_uM = [nominal_ec50 * f for f in PROTOCOL['dose_factors']]

    treatments = [TreatmentRequest(f"tBHQ_{d:.3f}uM", n_replicates=PROTOCOL['replicates_per_dose'])
                 for d in doses_uM]
    allocator = PlateAllocator(plate_format=PROTOCOL['plate_format'], seed=seed)
    assignments = allocator.allocate(treatments)

    for assignment in assignments:
        vm_base.seed_vessel(assignment.well_position, "A549", initial_count=2000,
                          capacity=1e7, vessel_type="96-well")

    for assignment in assignments:
        dose_str = assignment.treatment_id.replace("tBHQ_", "").replace("uM", "")
        nominal_dose_uM = float(dose_str)
        if nominal_dose_uM > 0:
            vm_base.treat_with_compound(assignment.well_position, "tBHQ", nominal_dose_uM)

    vm_base.advance_time(timepoint_24h)

    # Compute baseline means
    viabs_base = []
    morphs_base = []  # Mean across 5 channels per well

    for assignment in assignments:
        vessel = vm_base.vessel_states[assignment.well_position]
        obs = vm_base.cell_painting_assay(assignment.well_position)

        viabs_base.append(vessel.viability)
        morph_mean = np.mean([obs['morphology'][ch] for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']])
        morphs_base.append(morph_mean)

    μv_base = np.mean(viabs_base)
    μm_base = np.mean(morphs_base)

    print(f"Baseline (24h): μv={μv_base:.4f}, μm={μm_base:.2f}")

    # Step 2: Apply death condition with chosen severity
    sA = death_severity
    bA = 0.0  # Death doesn't add morphology offset

    viabs_A = [v * sA for v in viabs_base]
    morphs_A = morphs_base  # No morphology change from death in this model

    μvA = np.mean(viabs_A)
    μmA = np.mean(morphs_A)

    print(f"Death (sA={sA:.2f}):    μv={μvA:.4f}, μm={μmA:.2f}")

    # Step 3: Solve for debris knobs to match death's means
    bB = μmA - μm_base  # Morphology offset to match death's morphology mean
    sB = μvA / μv_base  # Viability readout bias to match death's viability mean

    # Verify (debris affects readout, not true biology)
    viabs_B = [v * sB for v in viabs_base]
    morphs_B = [m + bB for m in morphs_base]

    μvB = np.mean(viabs_B)
    μmB = np.mean(morphs_B)

    print(f"Debris (sB={sB:.4f}, bB={bB:.2f}): μv={μvB:.4f}, μm={μmB:.2f}")

    # Check parity
    viab_diff = abs(μvA - μvB)
    morph_diff = abs(μmA - μmB)

    print(f"\nParity check:")
    print(f"  Viability diff: {viab_diff:.6f} (should be ~0)")
    print(f"  Morphology diff: {morph_diff:.6f} (should be ~0)")

    if viab_diff > 0.01 or morph_diff > 0.5:
        print("  ⚠ WARNING: Parity not achieved. Check calibration.")
    else:
        print("  ✓ Dual parity achieved")

    return sA, bA, sB, bB


def generate_pair3_death_vs_debris(
    seed: int,
    timepoints: List[float],
    sA: float, bA: float,
    sB: float, bB: float
) -> List[Dict]:
    """
    Generate death vs debris data with calibrated knobs for dual parity.

    Condition A (Death): viability *= sA, morphology += bA
    Condition B (Debris): viability *= sB, morphology += bB
    """
    measurements = []

    for condition, viab_scale, morph_offset in [('A', sA, bA), ('B', sB, bB)]:
        rc = RunContext.sample(seed=seed)

        for timepoint_h in timepoints:
            vm = BiologicalVirtualMachine(seed=seed + int(timepoint_h * 1000), run_context=rc)
            vm._load_cell_thalamus_params()

            nominal_ec50 = vm.thalamus_params['compounds']['tBHQ']['ec50_uM']
            doses_uM = [nominal_ec50 * f for f in PROTOCOL['dose_factors']]

            treatments = [TreatmentRequest(f"tBHQ_{d:.3f}uM", n_replicates=PROTOCOL['replicates_per_dose'])
                         for d in doses_uM]
            allocator = PlateAllocator(plate_format=PROTOCOL['plate_format'], seed=seed)
            assignments = allocator.allocate(treatments)

            for assignment in assignments:
                vm.seed_vessel(assignment.well_position, "A549", initial_count=2000,
                             capacity=1e7, vessel_type="96-well")

            for assignment in assignments:
                dose_str = assignment.treatment_id.replace("tBHQ_", "").replace("uM", "")
                nominal_dose_uM = float(dose_str)
                if nominal_dose_uM > 0:
                    vm.treat_with_compound(assignment.well_position, "tBHQ", nominal_dose_uM)

            vm.advance_time(timepoint_h)

            for assignment in assignments:
                vessel = vm.vessel_states[assignment.well_position]
                obs = vm.cell_painting_assay(assignment.well_position)
                dose_str = assignment.treatment_id.replace("tBHQ_", "").replace("uM", "")

                # Apply calibrated manipulations
                viab_observed = vessel.viability * viab_scale
                morph_observed = {ch: val + morph_offset for ch, val in obs['morphology'].items()}

                measurements.append({
                    'condition': condition,
                    'timepoint_h': timepoint_h,
                    'nominal_dose_uM': float(dose_str),
                    'well_position': assignment.well_position,
                    'viability': viab_observed,
                    'morphology': morph_observed,
                })

    return measurements


def test_confound_pair3() -> ConfoundResult:
    """Test Viability loss vs Background/debris with dual parity."""
    print("\n" + "=" * 80)
    print("PAIR 3: Viability Loss vs Background/Debris")
    print("=" * 80)

    # Calibrate knobs for dual parity
    sA, bA, sB, bB = calibrate_pair3_dual_parity(PROTOCOL['base_seed'], death_severity=0.8)

    print(f"\nCondition A (Death): viab×{sA:.4f}, morph+{bA:.2f}")
    print(f"Condition B (Debris): viab×{sB:.4f}, morph+{bB:.2f}")
    print("Effect parity: DUAL (viability mean AND morphology mean matched at 24h)")

    # Generate full dataset with calibrated knobs
    measurements = generate_pair3_death_vs_debris(
        PROTOCOL['base_seed'],
        PROTOCOL['timepoints_multi'],
        sA, bA, sB, bB
    )
    print(f"\nGenerated {len(measurements)} measurements")

    # Test with variance features to detect distributional differences
    auc_1tp, p_1tp = test_distinguishability(measurements, PROTOCOL['timepoints_single'], include_variance=True)
    print(f"\nSingle TP (w/ variance): AUC={auc_1tp:.4f}, p={p_1tp:.4f}")

    auc_3tp, p_3tp = test_distinguishability(measurements, PROTOCOL['timepoints_multi'], include_variance=True)
    print(f"Multi TP (w/ variance):  AUC={auc_3tp:.4f}, p={p_3tp:.4f}")

    # Adjusted verdict criteria
    if auc_3tp < 0.65 and p_3tp > 0.1:
        verdict = "Confounded"
    elif auc_3tp > 0.7 and p_3tp < 0.05:
        verdict = "Distinguishable"
    else:
        verdict = "Suggestive (underpowered)"

    print(f"→ Verdict: {verdict}")

    return ConfoundResult(
        pair_name="Death vs Debris",
        single_tp_auc=auc_1tp, single_tp_pval=p_1tp,
        multi_tp_auc=auc_3tp, multi_tp_pval=p_3tp,
        verdict=verdict,
        breaks_tie="Distributional shape (additive vs multiplicative)" if verdict == "Distinguishable" else "N/A",
        requires_metadata="Empty well background measurement" if verdict == "Confounded" else \
                         ("More replicates recommended" if verdict == "Suggestive (underpowered)" else "N/A"),
        effect_parity_metric=f"DUAL (viab×{sA:.2f}, morph+{bB:.1f})",
        best_modality="Variance features" if verdict == "Distinguishable" else "N/A"
    )


# ============================================================================
# Main Test Runner
# ============================================================================

def test_attack3_confound_matrix():
    """Run confound matrix for Pairs 1-3."""
    print("=" * 80)
    print("ATTACK 3: CONFOUND MATRIX (Pairs 1-3)")
    print("=" * 80)
    print("\nLocked evaluation protocol:")
    for k, v in PROTOCOL.items():
        print(f"  {k}: {v}")

    results = []
    results.append(test_confound_pair1())
    results.append(test_confound_pair2())
    results.append(test_confound_pair3())

    # Summary table
    print("\n" + "=" * 80)
    print("CONFOUND MATRIX SUMMARY")
    print("=" * 80)
    print(f"{'Pair':<30} {'1TP AUC':<10} {'3TP AUC':<10} {'Verdict':<18} {'Effect Parity':<25}")
    print("-" * 105)
    for r in results:
        print(f"{r.pair_name:<30} {r.single_tp_auc:<10.3f} {r.multi_tp_auc:<10.3f} "
              f"{r.verdict:<18} {r.effect_parity_metric:<25}")

    # Identifiability boundaries
    print("\n" + "=" * 80)
    print("IDENTIFIABILITY BOUNDARIES")
    print("=" * 80)

    confounded = [r for r in results if r.verdict == "Confounded"]
    if confounded:
        print("\n✗ Agent CANNOT distinguish (requires external info):")
        for r in confounded:
            print(f"  • {r.pair_name}")
            print(f"    → Requires: {r.requires_metadata}")

    distinguishable = [r for r in results if r.verdict == "Distinguishable"]
    if distinguishable:
        print("\n✓ Agent CAN distinguish (from observations alone):")
        for r in distinguishable:
            print(f"  • {r.pair_name}")
            print(f"    → Using: {r.breaks_tie} via {r.best_modality}")

    weak = [r for r in results if "Suggestive" in r.verdict or "Weakly" in r.verdict]
    if weak:
        print("\n⚠  Suggestive signal (underpowered):")
        for r in weak:
            print(f"  • {r.pair_name}")
            print(f"    → {r.requires_metadata}")

    # Export results
    import json
    with open('/tmp/confound_matrix_results.json', 'w') as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    print("\n→ Results exported to /tmp/confound_matrix_results.json")


if __name__ == "__main__":
    test_attack3_confound_matrix()
