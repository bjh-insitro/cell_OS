"""
Demo script showing polished variance ledger with:
1. Reporting scale layer (percent change, z-scores)
2. Correlation group enforcement
3. Aleatoric noise present

This makes small deltas "feel" real by translating to human-meaningful units.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS/src')

from cell_os.uncertainty.variance_ledger import (
    VarianceLedger,
    VarianceContribution,
    VarianceKind,
    EffectType,
    explain_difference
)
from cell_os.hardware.aspiration_effects import (
    calculate_aspiration_detachment,
    sample_gamma_from_prior,
    get_edge_damage_contribution_to_cp_quality,
    compute_gamma_ridge_uncertainty
)


def simulate_well_with_variance(
    well_position: str,
    ledger: VarianceLedger,
    seed: int,
    sampled_gamma: float
) -> dict:
    """
    Simulate aspiration damage and record ALL variance contributions.

    Returns dict with metrics (noise_mult, segmentation_yield, etc.)
    """
    # Simulate aspiration at 9 o'clock (270°) with sampled gamma
    result = calculate_aspiration_detachment(
        well_position=well_position,
        cell_count=10000.0,
        confluence=0.6,
        aspirated_fraction=0.85,
        aspiration_angle_deg=270,
        aspiration_radius_fraction=0.75,
        base_detach_rate=0.015,
        post_fix_brittleness=0.3,
        seed=seed,
        plate_id="DEMO_P1",
        mode="normal",
        exposure_gamma=sampled_gamma,
        instrument_id="biotek_el406_cell_dispenser"
    )

    # Extract damage scores
    edge_tear_score = result.get('edge_tear_score', 0.0)
    bulk_shear_score = result.get('bulk_shear_score', 0.0)
    edge_damage_score = result.get('edge_damage_score', 0.0)

    # Compute CP quality effects (modeled)
    debris_load = 0.15
    edge_effects = get_edge_damage_contribution_to_cp_quality(
        edge_tear_score=edge_tear_score,
        bulk_shear_score=bulk_shear_score,
        debris_load=debris_load
    )

    # Compute ridge uncertainty (epistemic)
    ridge = compute_gamma_ridge_uncertainty(
        edge_tear_score=edge_tear_score,
        bulk_shear_score=bulk_shear_score,
        debris_load=debris_load,
        gamma_prior_cv=0.35
    )

    # Base noise_mult (before edge effects)
    noise_mult_base = 1.0

    # Apply edge effects
    noise_mult = noise_mult_base * edge_effects['noise_multiplier']
    segmentation_yield = 0.95 * (1.0 - edge_effects['segmentation_yield_penalty'])

    # Record MODELED effects
    if edge_damage_score > 0:
        ledger.record(VarianceContribution(
            term="VAR_INSTRUMENT_ASPIRATION_POSITION",
            metric="segmentation_yield",
            kind=VarianceKind.MODELED,
            effect_type=EffectType.DELTA,
            value=-edge_effects['segmentation_yield_penalty'],
            scope="per_well",
            correlation_group="aspiration_position",
            context={
                'well_id': well_position,
                'edge_tear_score': edge_tear_score,
                'bulk_shear_score': bulk_shear_score,
                'sampled_gamma': sampled_gamma
            }
        ))

        ledger.record(VarianceContribution(
            term="VAR_INSTRUMENT_ASPIRATION_POSITION",
            metric="noise_mult",
            kind=VarianceKind.MODELED,
            effect_type=EffectType.MULTIPLIER,
            value=edge_effects['noise_multiplier'],
            scope="per_well",
            correlation_group="aspiration_position",
            context={
                'well_id': well_position,
                'edge_tear_score': edge_tear_score,
                'bulk_shear_score': bulk_shear_score,
                'sampled_gamma': sampled_gamma
            }
        ))

    # Record EPISTEMIC uncertainty (ridge)
    if ridge['segmentation_yield_cv'] > 0:
        ledger.record(VarianceContribution(
            term="VAR_CALIBRATION_ASPIRATION_RIDGE",
            metric="segmentation_yield",
            kind=VarianceKind.EPISTEMIC,
            effect_type=EffectType.CV,
            value=ridge['segmentation_yield_cv'],
            scope="per_instrument",
            correlation_group="aspiration_ridge",
            context={
                'well_id': well_position,
                'gamma_prior_cv': 0.35
            }
        ))

    if ridge['noise_multiplier_cv'] > 0:
        ledger.record(VarianceContribution(
            term="VAR_CALIBRATION_ASPIRATION_RIDGE",
            metric="noise_mult",
            kind=VarianceKind.EPISTEMIC,
            effect_type=EffectType.CV,
            value=ridge['noise_multiplier_cv'],
            scope="per_instrument",
            correlation_group="aspiration_ridge",
            context={
                'well_id': well_position,
                'gamma_prior_cv': 0.35
            }
        ))

    # Record ALEATORIC noise (technical well-to-well variation)
    well_cv = 0.02  # 2% CV from technical noise
    ledger.record(VarianceContribution(
        term="VAR_TECH_NOISE_WELL_TO_WELL",
        metric="noise_mult",
        kind=VarianceKind.ALEATORIC,
        effect_type=EffectType.CV,
        value=well_cv,
        scope="per_well",
        correlation_group="independent",
        context={
            'well_id': well_position,
            'source': 'technical_noise_params'
        }
    ))

    return {
        'noise_mult': noise_mult,
        'segmentation_yield': segmentation_yield,
        'edge_tear_score': edge_tear_score,
        'bulk_shear_score': bulk_shear_score,
        'ridge_noise_cv': ridge['noise_multiplier_cv'],
        'ridge_seg_cv': ridge['segmentation_yield_cv'],
        'sampled_gamma': sampled_gamma
    }


def main():
    print("=" * 80)
    print("VARIANCE LEDGER DEMO (POLISHED): explain_difference with reporting scale")
    print("=" * 80)
    print()

    # Create variance ledger
    ledger = VarianceLedger()

    # Sample gamma once per run (epistemic uncertainty)
    seed = 42
    sampled_gamma = sample_gamma_from_prior(
        seed=seed,
        instrument_id="biotek_el406_cell_dispenser"
    )

    print(f"Sampled gamma (epistemic uncertainty): {sampled_gamma:.3f}")
    print(f"  (Prior: Lognormal(mean=1.0, CV=0.35), clipped to [0.3, 3.0])")
    print()

    # Simulate A1 (left edge, high aspiration exposure at 270°)
    print("Simulating A1 (left edge, high aspiration exposure)...")
    a1_metrics = simulate_well_with_variance("A1", ledger, seed, sampled_gamma)
    print(f"  noise_mult:         {a1_metrics['noise_mult']:.4f}")
    print(f"  segmentation_yield: {a1_metrics['segmentation_yield']:.4f}")
    print(f"  ridge_noise_cv:     {a1_metrics['ridge_noise_cv']:.4f}")
    print()

    # Simulate A24 (right edge, low aspiration exposure at 270°)
    print("Simulating A24 (right edge, low aspiration exposure)...")
    a24_metrics = simulate_well_with_variance("A24", ledger, seed, sampled_gamma)
    print(f"  noise_mult:         {a24_metrics['noise_mult']:.4f}")
    print(f"  segmentation_yield: {a24_metrics['segmentation_yield']:.4f}")
    print(f"  ridge_noise_cv:     {a24_metrics['ridge_noise_cv']:.4f}")
    print()

    print("=" * 80)
    print("EXPLAIN DIFFERENCE: noise_mult between A1 and A24")
    print("=" * 80)
    print()

    # Baseline value for percent change
    baseline_noise_mult = 1.0

    # Expected aleatoric SD (from tech noise params)
    expected_aleatoric_sd = 0.02  # 2% CV well-to-well

    # Call explain_difference with reporting scale
    explanation = explain_difference(
        ledger=ledger,
        well_a="A1",
        well_b="A24",
        metric="noise_mult",
        baseline_value=baseline_noise_mult,
        expected_aleatoric_sd=expected_aleatoric_sd
    )

    # Print structured report
    print(explanation['summary'])
    print()

    # Print raw data
    print("=" * 80)
    print("RAW VARIANCE DECOMPOSITION")
    print("=" * 80)
    print()
    print(f"Modeled difference:           {explanation['delta_modeled']:+.4f}")
    if 'percent_change' in explanation:
        print(f"  Percent change:             {explanation['percent_change']:+.2f}%")
    if 'z_score' in explanation:
        print(f"  Z-score vs aleatoric SD:    {explanation['z_score']:+.2f}×")
    print()
    print(f"Aleatoric uncertainty (CV):   ±{explanation['uncertainty_aleatoric_cv']:.4f}")
    print(f"Epistemic uncertainty (CV):   ±{explanation['uncertainty_epistemic_cv']:.4f}")
    print(f"Total uncertainty (CV):       ±{explanation['uncertainty_total_cv']:.4f}")
    print()

    print("Uncertainty breakdown:")
    print(f"  Aleatoric (randomness):     {explanation['aleatoric_pct']:.1f}% of total")
    print(f"  Epistemic (calibration):    {explanation['epistemic_pct']:.1f}% of total")
    print()

    # Check correlation warnings
    if explanation['correlation_warnings']:
        print("⚠️  CORRELATION WARNINGS:")
        for warning in explanation['correlation_warnings']:
            print(f"  {warning}")
        print()

    # Show correlation groups present
    print("Correlation groups present:")
    groups = set()
    for contrib in ledger.contributions:
        if contrib.effect_type == EffectType.CV:
            groups.add(contrib.correlation_group)
    for group in sorted(groups):
        count = sum(1 for c in ledger.contributions
                   if c.effect_type == EffectType.CV and c.correlation_group == group)
        print(f"  - {group}: {count} contributions")
    print()

    # Show top terms
    print("Top variance terms:")
    for term, delta, pct in explanation['top_terms'][:5]:
        print(f"  {term}: {delta:+.4f} ({pct:.0f}% of modeled delta)")
    print()

    print("=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)
    print()
    print(f"1. A1 is {explanation['delta_modeled']:+.4f} noisier than A24 (modeled)")
    if 'percent_change' in explanation:
        print(f"   That's {explanation['percent_change']:+.2f}% relative change")
    print()
    print(f"2. Uncertainty is {explanation['aleatoric_pct']:.0f}% aleatoric, "
          f"{explanation['epistemic_pct']:.0f}% epistemic")
    if explanation['epistemic_pct'] > 50:
        print(f"   → Actionable: Run microscopy calibration to reduce epistemic uncertainty")
    print()
    print(f"3. Sampled gamma = {sampled_gamma:.3f} (this instrument instance)")
    print(f"   Ridge CV = {a1_metrics['ridge_noise_cv']:.4f} (calibration uncertainty)")
    print()


if __name__ == "__main__":
    main()
