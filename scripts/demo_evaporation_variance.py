"""
Demo script showing evaporation variance tracking.

Shows how edge wells experience higher evaporation → concentration drift →
dose amplification, with both modeled (geometry) and epistemic (rate) uncertainty.
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
from cell_os.hardware.evaporation_effects import (
    calculate_evaporation_exposure,
    calculate_volume_loss_over_time,
    get_evaporation_contribution_to_effective_dose,
    compute_evaporation_ridge_uncertainty,
    sample_evaporation_rate_from_prior
)


def simulate_well_with_evaporation(
    well_position: str,
    time_hours: float,
    ledger: VarianceLedger,
    seed: int,
    sampled_rate: float,
    baseline_dose_uM: float = 1.0
) -> dict:
    """
    Simulate evaporation for a well and record variance contributions.

    Returns dict with effective_dose, concentration_multiplier, etc.
    """
    # Calculate spatial exposure (deterministic geometry)
    exposure = calculate_evaporation_exposure(well_position, plate_format=384)

    # Calculate volume loss over time
    initial_volume_ul = 50.0  # 384-well typical
    volume_result = calculate_volume_loss_over_time(
        initial_volume_ul=initial_volume_ul,
        time_hours=time_hours,
        base_evap_rate_ul_per_h=sampled_rate,
        exposure=exposure,
        min_volume_fraction=0.3
    )

    # Calculate effective dose change
    dose_result = get_evaporation_contribution_to_effective_dose(
        concentration_multiplier=volume_result['concentration_multiplier'],
        baseline_dose_uM=baseline_dose_uM
    )

    # Compute ridge uncertainty (epistemic)
    ridge = compute_evaporation_ridge_uncertainty(
        exposure=exposure,
        time_hours=time_hours,
        initial_volume_ul=initial_volume_ul,
        rate_prior_cv=0.30
    )

    # Record MODELED effects (deterministic geometry)
    ledger.record(VarianceContribution(
        term="VAR_INSTRUMENT_EVAPORATION_GEOMETRY",
        metric="effective_dose",
        kind=VarianceKind.MODELED,
        effect_type=EffectType.MULTIPLIER,
        value=dose_result['effective_dose_multiplier'],
        scope="per_well",
        correlation_group="evaporation_geometry",
        context={
            'well_id': well_position,
            'exposure': exposure,
            'time_hours': time_hours,
            'volume_fraction': volume_result['volume_fraction'],
            'sampled_rate': sampled_rate
        }
    ))

    # Record EPISTEMIC uncertainty (rate prior ridge)
    if ridge['effective_dose_cv'] > 0:
        ledger.record(VarianceContribution(
            term="VAR_CALIBRATION_EVAPORATION_RATE",
            metric="effective_dose",
            kind=VarianceKind.EPISTEMIC,
            effect_type=EffectType.CV,
            value=ridge['effective_dose_cv'],
            scope="per_instrument",
            correlation_group="evaporation_ridge",
            context={
                'well_id': well_position,
                'rate_prior_cv': 0.30,
                'exposure': exposure,
                'time_hours': time_hours
            }
        ))

    # Record ALEATORIC noise (pipetting variation in dosing)
    # Small baseline variation in delivered dose
    dose_cv = 0.03  # 3% CV from pipetting
    ledger.record(VarianceContribution(
        term="VAR_TECH_NOISE_PIPETTING",
        metric="effective_dose",
        kind=VarianceKind.ALEATORIC,
        effect_type=EffectType.CV,
        value=dose_cv,
        scope="per_well",
        correlation_group="independent",
        context={
            'well_id': well_position,
            'source': 'pipetting_variation'
        }
    ))

    return {
        'effective_dose_multiplier': dose_result['effective_dose_multiplier'],
        'effective_dose_uM': baseline_dose_uM * dose_result['effective_dose_multiplier'],
        'dose_delta_uM': dose_result['dose_delta_uM'],
        'dose_delta_fraction': dose_result['dose_delta_fraction'],
        'volume_fraction': volume_result['volume_fraction'],
        'volume_lost_ul': volume_result['volume_lost_ul'],
        'exposure': exposure,
        'ridge_dose_cv': ridge['effective_dose_cv'],
        'sampled_rate': sampled_rate
    }


def main():
    print("=" * 80)
    print("EVAPORATION VARIANCE DEMO: explain_difference('A1', 'D6', 'effective_dose')")
    print("=" * 80)
    print()

    # Create variance ledger
    ledger = VarianceLedger()

    # Sample evaporation rate once per plate (epistemic uncertainty)
    seed = 42
    sampled_rate = sample_evaporation_rate_from_prior(
        seed=seed,
        instrument_id="plate_default"
    )

    print(f"Sampled evaporation rate: {sampled_rate:.3f} µL/h (epistemic uncertainty)")
    print(f"  (Prior: Lognormal(mean=0.5 µL/h, CV=0.30), clipped to [0.1, 2.0])")
    print()

    # Simulation parameters
    time_hours = 48.0  # 48 hours incubation
    baseline_dose_uM = 1.0  # 1 µM compound dose

    print(f"Simulation: {time_hours:.0f}h incubation, {baseline_dose_uM:.1f} µM baseline dose")
    print()

    # Simulate A1 (corner, maximum evaporation exposure)
    print("Simulating A1 (corner well, max evaporation exposure)...")
    a1_metrics = simulate_well_with_evaporation(
        "A1", time_hours, ledger, seed, sampled_rate, baseline_dose_uM
    )
    print(f"  exposure:              {a1_metrics['exposure']:.3f}× (corner)")
    print(f"  volume_lost:           {a1_metrics['volume_lost_ul']:.2f} µL")
    print(f"  volume_fraction:       {a1_metrics['volume_fraction']:.3f}")
    print(f"  effective_dose:        {a1_metrics['effective_dose_uM']:.3f} µM")
    print(f"  dose_increase:         +{a1_metrics['dose_delta_fraction']:.1%}")
    print(f"  ridge_dose_cv:         {a1_metrics['ridge_dose_cv']:.4f}")
    print()

    # Simulate D6 (mid-plate, lower evaporation exposure)
    print("Simulating D6 (mid-plate well, lower evaporation exposure)...")
    d6_metrics = simulate_well_with_evaporation(
        "D6", time_hours, ledger, seed, sampled_rate, baseline_dose_uM
    )
    print(f"  exposure:              {d6_metrics['exposure']:.3f}× (mid-plate)")
    print(f"  volume_lost:           {d6_metrics['volume_lost_ul']:.2f} µL")
    print(f"  volume_fraction:       {d6_metrics['volume_fraction']:.3f}")
    print(f"  effective_dose:        {d6_metrics['effective_dose_uM']:.3f} µM")
    print(f"  dose_increase:         +{d6_metrics['dose_delta_fraction']:.1%}")
    print(f"  ridge_dose_cv:         {d6_metrics['ridge_dose_cv']:.4f}")
    print()

    print("=" * 80)
    print("EXPLAIN DIFFERENCE: effective_dose between A1 and D6")
    print("=" * 80)
    print()

    # Baseline value for percent change
    baseline_effective_dose = baseline_dose_uM

    # Expected aleatoric SD (from pipetting variation)
    expected_aleatoric_sd = baseline_dose_uM * 0.03  # 3% CV

    # Call explain_difference with reporting scale
    explanation = explain_difference(
        ledger=ledger,
        well_a="A1",
        well_b="D6",
        metric="effective_dose",
        baseline_value=baseline_effective_dose,
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

    # Show correlation groups
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
    print(f"1. A1 receives {explanation['delta_modeled']:+.4f} higher effective dose than D6 (modeled)")
    if 'percent_change' in explanation:
        print(f"   That's {explanation['percent_change']:+.2f}% more compound exposure at corner")
    print()
    print(f"2. Evaporation geometry is {abs(explanation['delta_modeled'] / baseline_dose_uM):.1%} effect")
    print(f"   Corner (A1) loses {a1_metrics['volume_lost_ul']:.1f}µL, mid-plate (D6) loses {d6_metrics['volume_lost_ul']:.1f}µL")
    print()
    print(f"3. Uncertainty is {explanation['aleatoric_pct']:.0f}% aleatoric, "
          f"{explanation['epistemic_pct']:.0f}% epistemic")
    if explanation['epistemic_pct'] > 30:
        print(f"   → Actionable: Run gravimetric calibration to reduce epistemic uncertainty")
    print()
    print(f"4. Sampled rate = {sampled_rate:.3f} µL/h (this plate instance)")
    print(f"   Ridge CV = {a1_metrics['ridge_dose_cv']:.4f} (calibration uncertainty)")
    print()


if __name__ == "__main__":
    main()
