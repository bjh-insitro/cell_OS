#!/usr/bin/env python
"""Test cost calculation for imaging experiments."""

from cell_os.imaging.cost import calculate_imaging_cost, calculate_batch_cost
from cell_os.imaging.acquisition import ExperimentPlan
from cell_os.posteriors import SliceKey


def main():
    # Create sample experiment plan
    plan = ExperimentPlan(
        slice_key=SliceKey("U2OS", "TBHP", 24.0, "cellrox_mean"),
        dose_uM=0.46,
        stress_value=0.67,
        viability_value=0.75,
        cells_per_field_pred=225.0,
        good_fields_per_well_pred=150.0,
        score=0.55,
    )
    
    # Calculate cost
    cost = calculate_imaging_cost(plan, wells_per_dose=3, fields_per_well=9)
    
    print("Imaging Experiment Cost Breakdown")
    print("=" * 60)
    print(f"Dose: {plan.dose_uM:.3f} µM")
    print(f"Predicted stress: {plan.stress_value:.3f}")
    print(f"Predicted viability: {plan.viability_value:.3f}")
    print(f"Acquisition score: {plan.score:.3f}")
    print()
    print("Cost Breakdown:")
    print(f"  Reagents:     ${cost.reagent_cost_usd:>8.2f}")
    print(f"  Consumables:  ${cost.consumable_cost_usd:>8.2f}")
    print(f"  Instrument:   ${cost.instrument_cost_usd:>8.2f}")
    print(f"  {'─' * 24}")
    print(f"  Total:        ${cost.total_cost_usd:>8.2f}")
    print()
    
    # Batch cost
    batch_plans = [plan] * 5  # 5 doses
    batch_cost = calculate_batch_cost(batch_plans)
    print(f"Cost for 5-dose batch: ${batch_cost:.2f}")
    print(f"Cost per dose: ${batch_cost / 5:.2f}")


if __name__ == "__main__":
    main()
