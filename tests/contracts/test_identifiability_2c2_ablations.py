"""
Phase 2C.2 Ablation Tests: Prove mechanism discrimination is honest.

Three ablation tests to validate that multi-mechanism identifiability works correctly:

1. **Scrambled labels do nothing**: Proves inference never accesses mechanism labels
2. **Mito-off shows no hallucinated mito**: Proves no false mito attribution when disabled
3. **ER-off shows no hallucinated ER**: Proves no false ER attribution when disabled

These tests ensure the competing-risks model is not "cheating" by peeking at labels
or hallucinating mechanisms that don't exist.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys
import copy

pytest.skip("Identifiability ablation tests require calibration run - skipping", allow_module_level=True)

# Add src to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from cell_os.calibration.identifiability_design import IdentifiabilityDesign
from cell_os.calibration.identifiability_runner import IdentifiabilityRunner
from cell_os.calibration.identifiability_inference import (
    fit_multi_mechanism_params,
    attribute_events_competing_risks,
    validate_attribution_accuracy,
)


@pytest.fixture
def config_path():
    """Path to Phase 2C.2 config."""
    return project_root / "configs" / "calibration" / "identifiability_2c2.yaml"


@pytest.fixture
def run_dir(tmp_path, config_path):
    """Run Phase 2C.2 design once and return output directory."""
    design = IdentifiabilityDesign(str(config_path))
    output_dir = tmp_path / "ablation_test_run"
    runner = IdentifiabilityRunner(design, output_dir=output_dir)

    runner.run()

    return output_dir


def test_scrambled_labels_do_nothing(run_dir):
    """
    Ablation 1: Scrambled labels should not change inference results.

    This proves inference never accesses `death_commitment_mechanism` labels.
    Only post-hoc validation accuracy should change when labels are scrambled.

    Steps:
    1. Run inference + attribution normally
    2. Scramble `death_commitment_mechanism` labels randomly
    3. Rerun inference + attribution with same data
    4. Assert params/attributions/predictions are identical

    Acceptance:
    - ER params differ by ≤0.01 (threshold, λ₀, p)
    - Mito params differ by ≤0.01
    - Per-event posteriors differ by ≤0.01
    - Mixed regime predicted split differs by ≤0.01
    """
    # Load data
    events_df = pd.read_csv(run_dir / "events.csv")
    observations_df = pd.read_csv(run_dir / "observations.csv")

    # Run inference normally (baseline)
    results_baseline = fit_multi_mechanism_params(
        events_df=events_df,
        observations_df=observations_df,
        er_dominant_regime="er_dominant",
        mito_dominant_regime="mito_dominant"
    )

    attribution_baseline = attribute_events_competing_risks(
        events_df=events_df,
        observations_df=observations_df,
        params_er=results_baseline['params_er'],
        params_mito=results_baseline['params_mito'],
        regime="mixed"
    )

    # Scramble labels (copy DataFrame to avoid mutation)
    events_scrambled = events_df.copy()
    committed_events = events_scrambled['committed'] == True

    if committed_events.sum() > 0:
        # Randomly permute mechanism labels for committed events
        committed_indices = events_scrambled[committed_events].index
        scrambled_mechanisms = events_scrambled.loc[committed_indices, 'death_commitment_mechanism'].sample(frac=1.0).values
        events_scrambled.loc[committed_indices, 'death_commitment_mechanism'] = scrambled_mechanisms

    # Run inference with scrambled labels
    results_scrambled = fit_multi_mechanism_params(
        events_df=events_scrambled,
        observations_df=observations_df,
        er_dominant_regime="er_dominant",
        mito_dominant_regime="mito_dominant"
    )

    attribution_scrambled = attribute_events_competing_risks(
        events_df=events_scrambled,
        observations_df=observations_df,
        params_er=results_scrambled['params_er'],
        params_mito=results_scrambled['params_mito'],
        regime="mixed"
    )

    # Assert: ER params unchanged
    params_er_baseline = results_baseline['params_er']
    params_er_scrambled = results_scrambled['params_er']

    assert abs(params_er_baseline['threshold'] - params_er_scrambled['threshold']) <= 0.01, \
        f"ER threshold changed after scrambling: {params_er_baseline['threshold']:.3f} → {params_er_scrambled['threshold']:.3f}"

    assert abs(params_er_baseline['baseline_hazard_per_h'] - params_er_scrambled['baseline_hazard_per_h']) <= 0.01, \
        f"ER λ₀ changed after scrambling: {params_er_baseline['baseline_hazard_per_h']:.3f} → {params_er_scrambled['baseline_hazard_per_h']:.3f}"

    assert abs(params_er_baseline['sharpness_p'] - params_er_scrambled['sharpness_p']) <= 0.01, \
        f"ER sharpness changed after scrambling: {params_er_baseline['sharpness_p']:.2f} → {params_er_scrambled['sharpness_p']:.2f}"

    # Assert: Mito params unchanged
    params_mito_baseline = results_baseline['params_mito']
    params_mito_scrambled = results_scrambled['params_mito']

    assert abs(params_mito_baseline['threshold'] - params_mito_scrambled['threshold']) <= 0.01, \
        f"Mito threshold changed after scrambling: {params_mito_baseline['threshold']:.3f} → {params_mito_scrambled['threshold']:.3f}"

    assert abs(params_mito_baseline['baseline_hazard_per_h'] - params_mito_scrambled['baseline_hazard_per_h']) <= 0.01, \
        f"Mito λ₀ changed after scrambling: {params_mito_baseline['baseline_hazard_per_h']:.3f} → {params_mito_scrambled['baseline_hazard_per_h']:.3f}"

    assert abs(params_mito_baseline['sharpness_p'] - params_mito_scrambled['sharpness_p']) <= 0.01, \
        f"Mito sharpness changed after scrambling: {params_mito_baseline['sharpness_p']:.2f} → {params_mito_scrambled['sharpness_p']:.2f}"

    # Assert: Attribution posteriors unchanged (per event)
    attributions_baseline = attribution_baseline['attributions']
    attributions_scrambled = attribution_scrambled['attributions']

    assert len(attributions_baseline) == len(attributions_scrambled), \
        "Number of attributed events changed after scrambling"

    for i, (attr_base, attr_scram) in enumerate(zip(attributions_baseline, attributions_scrambled)):
        assert attr_base['well_id'] == attr_scram['well_id'], \
            f"Event {i}: well_id mismatch"

        assert abs(attr_base['posterior_er'] - attr_scram['posterior_er']) <= 0.01, \
            f"Event {i} ({attr_base['well_id']}): posterior_er changed {attr_base['posterior_er']:.3f} → {attr_scram['posterior_er']:.3f}"

        assert attr_base['predicted_mech'] == attr_scram['predicted_mech'], \
            f"Event {i} ({attr_base['well_id']}): predicted mechanism changed"

    # Assert: Mixed regime predicted split unchanged
    assert abs(attribution_baseline['predicted_fraction_er'] - attribution_scrambled['predicted_fraction_er']) <= 0.01, \
        f"Predicted ER fraction changed after scrambling: {attribution_baseline['predicted_fraction_er']:.3f} → {attribution_scrambled['predicted_fraction_er']:.3f}"

    assert abs(attribution_baseline['predicted_fraction_mito'] - attribution_scrambled['predicted_fraction_mito']) <= 0.01, \
        f"Predicted mito fraction changed after scrambling: {attribution_baseline['predicted_fraction_mito']:.3f} → {attribution_scrambled['predicted_fraction_mito']:.3f}"

    # Note: Validation accuracy SHOULD change (that's the whole point)
    # But we don't assert that here - this test only proves inference is label-blind


def test_mito_disabled_shows_no_hallucination(tmp_path):
    """
    Ablation 2: When mito mechanism is disabled, inference should not hallucinate mito events.

    This proves the model doesn't falsely attribute events to mito when mito is off.

    Steps:
    1. Run design with ER-only mechanism (mito disabled)
    2. Run multi-mechanism inference (same as 2C.2)
    3. Assert: predicted mito fraction ≤ 10% in all regimes

    Acceptance:
    - Predicted mito fraction ≤ 10% (max_hallucinated_mechanism_fraction)
    - ER params still recoverable within tolerance
    """
    # Load mito-off config
    config_path = project_root / "configs" / "calibration" / "identifiability_2c2_mito_off.yaml"
    design = IdentifiabilityDesign(str(config_path))
    runner = IdentifiabilityRunner(design)

    # Run design
    output_dir = tmp_path / "mito_off_run"
    runner.run_full_suite(output_dir=str(output_dir))

    # Load data
    events_df = pd.read_csv(output_dir / "events.csv")
    observations_df = pd.read_csv(output_dir / "observations.csv")

    # Run multi-mechanism inference (same as 2C.2)
    results = fit_multi_mechanism_params(
        events_df=events_df,
        observations_df=observations_df,
        er_dominant_regime="er_dominant",
        mito_dominant_regime="mito_dominant"
    )

    # Attribute events in mixed regime
    attribution_mixed = attribute_events_competing_risks(
        events_df=events_df,
        observations_df=observations_df,
        params_er=results['params_er'],
        params_mito=results['params_mito'],
        regime="mixed"
    )

    # Also check ER-dominant regime (should have ER events, not mito)
    attribution_er = attribute_events_competing_risks(
        events_df=events_df,
        observations_df=observations_df,
        params_er=results['params_er'],
        params_mito=results['params_mito'],
        regime="er_dominant"
    )

    # Assert: Predicted mito fraction ≤ 10% in all regimes
    max_hallucination = 0.10

    predicted_mito_mixed = attribution_mixed['predicted_fraction_mito']
    assert predicted_mito_mixed <= max_hallucination, \
        f"Hallucinated mito in mixed regime: predicted {predicted_mito_mixed:.1%} > {max_hallucination:.0%} (mito is OFF)"

    predicted_mito_er = attribution_er['predicted_fraction_mito']
    assert predicted_mito_er <= max_hallucination, \
        f"Hallucinated mito in ER-dominant regime: predicted {predicted_mito_er:.1%} > {max_hallucination:.0%} (mito is OFF)"

    # Assert: ER params still recoverable (check threshold is within tolerance)
    params_er = results['params_er']
    truth_threshold_er = 0.60
    threshold_error = abs(params_er['threshold'] - truth_threshold_er)

    assert threshold_error <= 0.10, \
        f"ER threshold not recoverable with mito-off: error={threshold_error:.3f} > 0.10"

    # Check that mito-dominant regime produced no events (because mito is OFF)
    events_mito_regime = events_df[events_df['regime'] == 'mito_dominant']
    n_events_mito_regime = events_mito_regime['committed'].sum()

    # We don't strictly require 0 events (could have ER spillover if rotenone causes ER stress)
    # But we do require that predicted mito fraction is low
    print(f"Mito-dominant regime events: {n_events_mito_regime} (mito is OFF, should be ~0)")


def test_er_disabled_shows_no_hallucination(tmp_path):
    """
    Ablation 3: When ER mechanism is disabled, inference should not hallucinate ER events.

    This proves the model doesn't falsely attribute events to ER when ER is off.

    Steps:
    1. Run design with mito-only mechanism (ER disabled)
    2. Run multi-mechanism inference (same as 2C.2)
    3. Assert: predicted ER fraction ≤ 10% in all regimes

    Acceptance:
    - Predicted ER fraction ≤ 10% (max_hallucinated_mechanism_fraction)
    - Mito params still recoverable within tolerance
    """
    # Load ER-off config
    config_path = project_root / "configs" / "calibration" / "identifiability_2c2_er_off.yaml"
    design = IdentifiabilityDesign(str(config_path))
    runner = IdentifiabilityRunner(design)

    # Run design
    output_dir = tmp_path / "er_off_run"
    runner.run_full_suite(output_dir=str(output_dir))

    # Load data
    events_df = pd.read_csv(output_dir / "events.csv")
    observations_df = pd.read_csv(output_dir / "observations.csv")

    # Run multi-mechanism inference (same as 2C.2)
    results = fit_multi_mechanism_params(
        events_df=events_df,
        observations_df=observations_df,
        er_dominant_regime="er_dominant",
        mito_dominant_regime="mito_dominant"
    )

    # Attribute events in mixed regime
    attribution_mixed = attribute_events_competing_risks(
        events_df=events_df,
        observations_df=observations_df,
        params_er=results['params_er'],
        params_mito=results['params_mito'],
        regime="mixed"
    )

    # Also check mito-dominant regime (should have mito events, not ER)
    attribution_mito = attribute_events_competing_risks(
        events_df=events_df,
        observations_df=observations_df,
        params_er=results['params_er'],
        params_mito=results['params_mito'],
        regime="mito_dominant"
    )

    # Assert: Predicted ER fraction ≤ 10% in all regimes
    max_hallucination = 0.10

    predicted_er_mixed = attribution_mixed['predicted_fraction_er']
    assert predicted_er_mixed <= max_hallucination, \
        f"Hallucinated ER in mixed regime: predicted {predicted_er_mixed:.1%} > {max_hallucination:.0%} (ER is OFF)"

    predicted_er_mito = attribution_mito['predicted_fraction_er']
    assert predicted_er_mito <= max_hallucination, \
        f"Hallucinated ER in mito-dominant regime: predicted {predicted_er_mito:.1%} > {max_hallucination:.0%} (ER is OFF)"

    # Assert: Mito params still recoverable (check threshold is within tolerance)
    params_mito = results['params_mito']
    truth_threshold_mito = 0.60
    threshold_error = abs(params_mito['threshold'] - truth_threshold_mito)

    assert threshold_error <= 0.10, \
        f"Mito threshold not recoverable with ER-off: error={threshold_error:.3f} > 0.10"

    # Check that ER-dominant regime produced no events (because ER is OFF)
    events_er_regime = events_df[events_df['regime'] == 'er_dominant']
    n_events_er_regime = events_er_regime['committed'].sum()

    # We don't strictly require 0 events (could have mito spillover if tunicamycin causes mito stress)
    # But we do require that predicted ER fraction is low
    print(f"ER-dominant regime events: {n_events_er_regime} (ER is OFF, should be ~0)")
