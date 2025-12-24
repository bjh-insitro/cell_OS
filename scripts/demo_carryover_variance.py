"""
Demo script showing pipette carryover variance tracking.

Shows how sequence-dependent contamination creates "column 7 is cursed" pathology:
blank wells after high-dose dispenses get contaminated by residual carryover.
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
from cell_os.hardware.carryover_effects import (
    calculate_carryover_contamination,
    apply_carryover_to_sequence,
    compute_carryover_ridge_uncertainty,
    sample_carryover_fraction_from_prior,
    CarryoverFractionPrior,
    get_dispense_sequence_for_plate
)


def simulate_dispense_sequence_with_carryover(
    dose_sequence_uM: list,
    well_sequence: list,
    ledger: VarianceLedger,
    seed: int,
    tip_id: str = "tip_default",
    baseline_dose_uM: float = 1.0
) -> dict:
    """
    Simulate dispense sequence with carryover contamination.

    Returns dict mapping well_id -> effective_dose_uM
    """
    # Sample carryover fraction once per tip (epistemic uncertainty)
    prior = CarryoverFractionPrior()
    sampled_fraction = prior.sample(seed=seed, tip_id=tip_id)

    # Apply carryover to sequence
    effective_doses = apply_carryover_to_sequence(
        dose_sequence_uM=dose_sequence_uM,
        carryover_fraction=sampled_fraction,
        wash_efficiency=0.0  # No wash between dispenses
    )

    # Record variance contributions for each well
    results = {}
    for idx, (well_id, intended_dose, effective_dose) in enumerate(zip(well_sequence, dose_sequence_uM, effective_doses)):
        # Compute carryover contamination from previous well
        previous_dose = 0.0 if idx == 0 else dose_sequence_uM[idx - 1]

        carryover_result = calculate_carryover_contamination(
            previous_dose_uM=previous_dose,
            carryover_fraction=sampled_fraction,
            wash_efficiency=0.0
        )

        carryover_dose = carryover_result['carryover_dose_uM']

        # Record MODELED effects (deterministic given sampled fraction)
        if carryover_dose > 0:
            ledger.record(VarianceContribution(
                term="VAR_INSTRUMENT_PIPETTE_CARRYOVER_SEQUENCE",
                metric="effective_dose",
                kind=VarianceKind.MODELED,
                effect_type=EffectType.DELTA,
                value=carryover_dose,
                scope="per_well",
                correlation_group=f"carryover_tip_{tip_id}",
                context={
                    'well_id': well_id,
                    'sequence_index': idx,
                    'previous_dose_uM': previous_dose,
                    'sampled_fraction': sampled_fraction,
                    'tip_id': tip_id
                }
            ))

        # Compute ridge uncertainty (epistemic)
        if previous_dose > 0:
            ridge = compute_carryover_ridge_uncertainty(
                previous_dose_uM=previous_dose,
                frac_prior_cv=prior.cv
            )

            if ridge['carryover_dose_cv'] > 0:
                ledger.record(VarianceContribution(
                    term="VAR_CALIBRATION_CARRYOVER_FRACTION",
                    metric="effective_dose",
                    kind=VarianceKind.EPISTEMIC,
                    effect_type=EffectType.CV,
                    value=ridge['carryover_dose_cv'],
                    scope="per_instrument",
                    correlation_group="carryover_ridge",
                    context={
                        'well_id': well_id,
                        'previous_dose_uM': previous_dose,
                        'frac_prior_cv': prior.cv,
                        'tip_id': tip_id
                    }
                ))

        # Record ALEATORIC noise (pipetting variation)
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
                'well_id': well_id,
                'source': 'pipetting_variation'
            }
        ))

        results[well_id] = {
            'intended_dose_uM': intended_dose,
            'effective_dose_uM': effective_dose,
            'carryover_dose_uM': carryover_dose,
            'sequence_index': idx,
            'previous_dose_uM': previous_dose
        }

    return results, sampled_fraction


def main():
    print("=" * 80)
    print("CARRYOVER VARIANCE DEMO: explain_difference(blank_after_hot, blank_clean)")
    print("=" * 80)
    print()

    # Create variance ledger
    ledger = VarianceLedger()

    # Simulation parameters
    seed = 42
    tip_id = "multichannel_A"
    baseline_dose_uM = 1.0

    print("SCENARIO: Row-wise dispense with alternating hot/blank pattern")
    print("  Tip: multichannel channel A")
    print("  Sequence: [10 µM hot] → [blank] → [10 µM hot] → [blank] → [blank clean]")
    print()

    # Define dispense sequence (simplified 5-well pattern)
    dose_sequence_uM = [
        10.0,  # A1: Hot well (10 µM)
        0.0,   # A2: Blank after hot (should get contaminated)
        10.0,  # A3: Hot well (10 µM)
        0.0,   # A4: Blank after hot (should get contaminated)
        0.0    # A5: Blank after blank (clean)
    ]

    well_sequence = ["A1", "A2", "A3", "A4", "A5"]

    # Simulate dispense sequence
    print("Simulating dispense sequence with carryover...")
    results, sampled_fraction = simulate_dispense_sequence_with_carryover(
        dose_sequence_uM=dose_sequence_uM,
        well_sequence=well_sequence,
        ledger=ledger,
        seed=seed,
        tip_id=tip_id,
        baseline_dose_uM=baseline_dose_uM
    )

    print(f"  Sampled carryover fraction: {sampled_fraction:.4f} ({sampled_fraction*100:.2f}%)")
    print(f"    (Prior: Lognormal(mean=0.5%, CV=0.40), clipped to [0.01%, 5%])")
    print()

    # Print results
    print("DISPENSE SEQUENCE RESULTS:")
    print("=" * 80)
    for well_id in well_sequence:
        r = results[well_id]
        print(f"{well_id}: intended={r['intended_dose_uM']:.3f} µM, "
              f"effective={r['effective_dose_uM']:.4f} µM, "
              f"carryover=+{r['carryover_dose_uM']:.4f} µM")
        if r['carryover_dose_uM'] > 0:
            pct_contamination = (r['carryover_dose_uM'] / r['effective_dose_uM']) * 100
            print(f"     └─ Contaminated by {r['previous_dose_uM']:.1f} µM from previous well "
                  f"({pct_contamination:.1f}% of effective dose)")
    print()

    # Key comparison: blank_after_hot (A2) vs blank_clean (A5)
    blank_after_hot = "A2"
    blank_clean = "A5"

    print("=" * 80)
    print(f"EXPLAIN DIFFERENCE: effective_dose between {blank_after_hot} (blank after hot) and {blank_clean} (clean blank)")
    print("=" * 80)
    print()

    # Baseline for percent change
    baseline_effective_dose = baseline_dose_uM
    expected_aleatoric_sd = baseline_dose_uM * 0.03  # 3% CV

    # Call explain_difference
    explanation = explain_difference(
        ledger=ledger,
        well_a=blank_after_hot,
        well_b=blank_clean,
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
    print(f"Modeled difference:           {explanation['delta_modeled']:+.4f} µM")
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

    # Show correlation groups
    print("Correlation groups present:")
    groups = set()
    for contrib in ledger.contributions:
        if contrib.effect_type == EffectType.CV or contrib.effect_type == EffectType.DELTA:
            groups.add(contrib.correlation_group)
    for group in sorted(groups):
        count = sum(1 for c in ledger.contributions
                   if c.correlation_group == group)
        print(f"  - {group}: {count} contributions")
    print()

    # Show top terms
    print("Top variance terms:")
    for term, delta, pct in explanation['top_terms'][:5]:
        print(f"  {term}: {delta:+.4f} µM ({pct:.0f}% of modeled delta)")
    print()

    print("=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)
    print()
    print(f"1. {blank_after_hot} receives {explanation['delta_modeled']:+.4f} µM more than {blank_clean} (modeled)")
    if 'percent_change' in explanation:
        print(f"   That's {explanation['percent_change']:+.2f}% contamination from previous hot dispense")
    print()
    print(f"2. Carryover fraction = {sampled_fraction:.4f} ({sampled_fraction*100:.2f}%)")
    print(f"   {blank_after_hot} contaminated by 10 µM → gets {results[blank_after_hot]['carryover_dose_uM']:.4f} µM")
    print(f"   {blank_clean} after blank → gets {results[blank_clean]['carryover_dose_uM']:.4f} µM (clean)")
    print()
    print(f"3. Uncertainty is {explanation['aleatoric_pct']:.0f}% aleatoric, "
          f"{explanation['epistemic_pct']:.0f}% epistemic")
    if explanation['epistemic_pct'] > 30:
        print(f"   → Actionable: Run blank-after-hot calibration to reduce epistemic uncertainty")
    print()
    print(f"4. This is SEQUENCE-DEPENDENT, not geometry-dependent")
    print(f"   Column 7 is 'cursed' if it's always dispensed after column 6 (hot)")
    print(f"   Spatial position doesn't matter - only dispense order matters")
    print()

    # Demonstrate "column 7 is cursed" pathology
    print("=" * 80)
    print("PATHOLOGY DEMONSTRATION: 'Why is column 7 always contaminated?'")
    print("=" * 80)
    print()
    print("Simulating 8-column dispense pattern (row-wise, hot-blank-hot-blank...):")

    # 8-well sequence showing column pattern
    col_sequence_doses = [10.0, 0.0, 10.0, 0.0, 10.0, 0.0, 10.0, 0.0]
    col_sequence_wells = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"]

    col_ledger = VarianceLedger()
    col_results, _ = simulate_dispense_sequence_with_carryover(
        dose_sequence_uM=col_sequence_doses,
        well_sequence=col_sequence_wells,
        ledger=col_ledger,
        seed=seed,
        tip_id=tip_id
    )

    print()
    print("Effective doses by column:")
    for col_idx, well_id in enumerate(col_sequence_wells):
        r = col_results[well_id]
        col_num = col_idx + 1
        status = "HOT" if r['intended_dose_uM'] > 0 else "BLANK"
        contamination = "" if r['carryover_dose_uM'] == 0 else f" ← CONTAMINATED (+{r['carryover_dose_uM']:.4f} µM)"
        print(f"  Column {col_num} ({well_id}): {r['effective_dose_uM']:.4f} µM [{status}]{contamination}")

    print()
    print("Notice: Columns 2, 4, 6, 8 (all 'blank' wells) are contaminated")
    print("        NOT because of their position, but because they follow hot wells")
    print("        in the dispense sequence. This is sequence-dependent artifact.")
    print()


if __name__ == "__main__":
    main()
