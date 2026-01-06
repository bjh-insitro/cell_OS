"""
Confound Regression Test - Lock identifiability boundaries.

These tests MUST pass to prevent accidental tells from "improving realism."
If any of these flip to distinguishable, investigate for leakage before celebrating.
"""

import json
import pytest

pytest.skip("Depends on confound_matrix results file from skipped tests", allow_module_level=True)


def test_pair1_remains_confounded():
    """EC50 shift vs Dose error must stay confounded (scale invariance)."""
    with open('/tmp/confound_matrix_results.json', 'r') as f:
        results = json.load(f)

    pair1 = next(r for r in results if r['pair_name'] == 'EC50 shift vs Dose error')

    # Strict thresholds: AUC < 0.65 AND p > 0.1
    assert pair1['multi_tp_auc'] < 0.65, (
        f"Pair 1 became distinguishable (AUC={pair1['multi_tp_auc']:.3f})! "
        f"This violates Hill-model scale symmetry. "
        f"Check for seed leakage, batch asymmetry, or implementation tell."
    )
    assert pair1['multi_tp_pval'] > 0.1, (
        f"Pair 1 p-value too low (p={pair1['multi_tp_pval']:.3f})! "
        f"Scale invariance broken."
    )
    assert pair1['verdict'] == 'Confounded', (
        f"Pair 1 verdict changed to '{pair1['verdict']}'! "
        f"Must remain 'Confounded' to maintain honest identifiability boundary."
    )


def test_pair2_remains_distinguishable():
    """Dose error vs Assay gain must stay distinguishable (cross-modal detection)."""
    with open('/tmp/confound_matrix_results.json', 'r') as f:
        results = json.load(f)

    pair2 = next(r for r in results if r['pair_name'] == 'Dose error vs Assay gain')

    # Must be distinguishable: AUC > 0.7 AND p < 0.05
    assert pair2['multi_tp_auc'] > 0.7, (
        f"Pair 2 became confounded (AUC={pair2['multi_tp_auc']:.3f})! "
        f"Cross-modal features (viability-morphology discordance) should separate these. "
        f"Check if measurement model collapsed to single scalar."
    )
    assert pair2['multi_tp_pval'] < 0.05, (
        f"Pair 2 p-value too high (p={pair2['multi_tp_pval']:.3f})! "
        f"Should be strongly distinguishable via cross-modal ratios."
    )
    assert pair2['verdict'] == 'Distinguishable', (
        f"Pair 2 verdict changed to '{pair2['verdict']}'! "
        f"Must remain 'Distinguishable' - this is a healthy separation."
    )


def test_pair3_remains_confounded():
    """Death vs Debris must stay confounded under dual parity (deliberate trapdoor).

    This is NOT a bug. This is the honest epistemic boundary given:
    - Dual parity: E[viability] and E[morphology] matched at 24h
    - Observable set: {viability, 5-channel means, replicate stds}
    - No empty-well controls

    If this flips to distinguishable without adding new observables:
    - Check for accidental tells (debris flag, different RNG streams)
    - Check for correlations leaking condition information
    - Check for feature engineering that mines artifacts

    Correct intervention: Agent must run empty-well controls to separate.
    """
    with open('/tmp/confound_matrix_results.json', 'r') as f:
        results = json.load(f)

    pair3 = next(r for r in results if r['pair_name'] == 'Death vs Debris')

    # Strict thresholds: AUC < 0.65 AND p > 0.1
    assert pair3['multi_tp_auc'] < 0.65, (
        f"Pair 3 became distinguishable (AUC={pair3['multi_tp_auc']:.3f})! "
        f"This violates dual-parity confound contract. "
        f"Check for:\n"
        f"  - Accidental tells (debris flag, RNG leakage)\n"
        f"  - Feature engineering that mines artifacts\n"
        f"  - New observables added without updating test\n"
        f"If deliberate: add empty-well controls as explicit observable."
    )
    assert pair3['multi_tp_pval'] > 0.1, (
        f"Pair 3 p-value too low (p={pair3['multi_tp_pval']:.3f})! "
        f"Dual parity should force confounding."
    )
    assert pair3['verdict'] == 'Confounded', (
        f"Pair 3 verdict changed to '{pair3['verdict']}'! "
        f"Must remain 'Confounded' under dual parity. "
        f"Agent must run empty-well controls to separate, not infer magically."
    )


def test_confound_contract_documented():
    """Verify all confound requirements are documented."""
    with open('/tmp/confound_matrix_results.json', 'r') as f:
        results = json.load(f)

    # Check that confounded pairs have required metadata
    confounded = [r for r in results if r['verdict'] == 'Confounded']

    for pair in confounded:
        assert pair['requires_metadata'] != 'N/A', (
            f"{pair['pair_name']} is confounded but has no required metadata! "
            f"Must document what external information agent needs."
        )

        # Pair-specific checks
        if 'EC50' in pair['pair_name']:
            assert 'Calibration' in pair['requires_metadata'] or 'dose verification' in pair['requires_metadata'], (
                f"Pair 1 must require calibration compounds or dose verification"
            )
        elif 'Death vs Debris' in pair['pair_name']:
            assert 'Empty well' in pair['requires_metadata'] or 'background' in pair['requires_metadata'], (
                f"Pair 3 must require empty-well controls or background measurement"
            )


if __name__ == "__main__":
    test_pair1_remains_confounded()
    test_pair2_remains_distinguishable()
    test_pair3_remains_confounded()
    test_confound_contract_documented()
    print("✅ All confound regression tests passed")
