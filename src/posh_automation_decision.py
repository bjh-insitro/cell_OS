"""
POSH Automation Decision Helper

Helps users decide between manual, semi-automated, and fully automated
Vanilla POSH workflows based on their specific parameters.
"""

from dataclasses import dataclass
from typing import Literal

@dataclass
class LabParameters:
    """Parameters for POSH automation decision."""
    experiments_per_year: int
    capital_budget_usd: float
    technician_hourly_rate_usd: float = 60.0
    timeline_years: int = 5
    
@dataclass
class AutomationRecommendation:
    """Recommendation for POSH automation level."""
    workflow: Literal["manual", "semi_automated", "full_automated"]
    capital_cost_usd: float
    annual_operating_cost_usd: float
    break_even_years: float
    five_year_npv_usd: float
    rationale: str
    
def recommend_posh_automation(params: LabParameters) -> AutomationRecommendation:
    """
    Recommend POSH automation level based on lab parameters.
    
    Args:
        params: Lab parameters (throughput, budget, labor costs)
        
    Returns:
        AutomationRecommendation with workflow type and financial analysis
    """
    
    # Cost parameters
    MANUAL_SETUP = 50_000
    SEMI_AUTO_SETUP = 170_000  # Manual + liquid handler
    FULL_AUTO_SETUP = 500_000  # Complete system
    
    # Per-experiment costs (6-well plate)
    REAGENT_COST = 2_600
    MANUAL_LABOR_HOURS = 40
    AUTO_LABOR_HOURS = 8
    
    # Maintenance (annual, % of capital)
    MANUAL_MAINTENANCE_PCT = 0.05
    SEMI_AUTO_MAINTENANCE_PCT = 0.10
    FULL_AUTO_MAINTENANCE_PCT = 0.12
    
    # Calculate per-experiment costs
    manual_labor_cost = MANUAL_LABOR_HOURS * params.technician_hourly_rate_usd
    auto_labor_cost = AUTO_LABOR_HOURS * params.technician_hourly_rate_usd
    
    manual_per_exp = REAGENT_COST + manual_labor_cost
    auto_per_exp = REAGENT_COST + auto_labor_cost
    
    savings_per_exp = manual_per_exp - auto_per_exp
    annual_savings = savings_per_exp * params.experiments_per_year
    
    # Decision logic
    if params.experiments_per_year < 10:
        # Very low throughput - manual only
        workflow = "manual"
        capital = MANUAL_SETUP
        annual_maint = capital * MANUAL_MAINTENANCE_PCT
        annual_operating = (manual_per_exp * params.experiments_per_year) + annual_maint
        break_even = float('inf')
        npv_5yr = -(capital + (annual_operating * params.timeline_years))
        rationale = (
            f"Low throughput ({params.experiments_per_year}/year) does not justify automation. "
            f"Manual workflow is most cost-effective."
        )
        
    elif params.experiments_per_year < 25:
        # Low-medium throughput - manual or semi-auto
        if params.capital_budget_usd >= SEMI_AUTO_SETUP:
            workflow = "semi_automated"
            capital = SEMI_AUTO_SETUP
            annual_maint = capital * SEMI_AUTO_MAINTENANCE_PCT
            # Semi-auto: 60% of manual labor (liquid handling automated)
            semi_labor_hours = MANUAL_LABOR_HOURS * 0.6
            semi_per_exp = REAGENT_COST + (semi_labor_hours * params.technician_hourly_rate_usd)
            annual_operating = (semi_per_exp * params.experiments_per_year) + annual_maint
            semi_savings = (manual_per_exp - semi_per_exp) * params.experiments_per_year
            break_even = capital / semi_savings if semi_savings > 0 else float('inf')
            npv_5yr = (semi_savings * params.timeline_years) - capital - (annual_maint * params.timeline_years)
            rationale = (
                f"Medium throughput ({params.experiments_per_year}/year) with sufficient budget. "
                f"Semi-automation provides good balance of cost and efficiency."
            )
        else:
            workflow = "manual"
            capital = MANUAL_SETUP
            annual_maint = capital * MANUAL_MAINTENANCE_PCT
            annual_operating = (manual_per_exp * params.experiments_per_year) + annual_maint
            break_even = float('inf')
            npv_5yr = -(capital + (annual_operating * params.timeline_years))
            rationale = (
                f"Medium throughput ({params.experiments_per_year}/year) but limited budget. "
                f"Manual workflow recommended. Re-evaluate after 1-2 years."
            )
            
    elif params.experiments_per_year < 50:
        # Medium-high throughput
        if params.capital_budget_usd >= FULL_AUTO_SETUP:
            workflow = "full_automated"
            capital = FULL_AUTO_SETUP
            annual_maint = capital * FULL_AUTO_MAINTENANCE_PCT
            annual_operating = (auto_per_exp * params.experiments_per_year) + annual_maint
            break_even = capital / annual_savings if annual_savings > 0 else float('inf')
            npv_5yr = (annual_savings * params.timeline_years) - capital - (annual_maint * params.timeline_years)
            rationale = (
                f"High throughput ({params.experiments_per_year}/year) with sufficient budget. "
                f"Full automation recommended for efficiency and reproducibility. "
                f"Break-even in {break_even:.1f} years."
            )
        elif params.capital_budget_usd >= SEMI_AUTO_SETUP:
            workflow = "semi_automated"
            capital = SEMI_AUTO_SETUP
            annual_maint = capital * SEMI_AUTO_MAINTENANCE_PCT
            semi_labor_hours = MANUAL_LABOR_HOURS * 0.6
            semi_per_exp = REAGENT_COST + (semi_labor_hours * params.technician_hourly_rate_usd)
            annual_operating = (semi_per_exp * params.experiments_per_year) + annual_maint
            semi_savings = (manual_per_exp - semi_per_exp) * params.experiments_per_year
            break_even = capital / semi_savings if semi_savings > 0 else float('inf')
            npv_5yr = (semi_savings * params.timeline_years) - capital - (annual_maint * params.timeline_years)
            rationale = (
                f"High throughput ({params.experiments_per_year}/year) with moderate budget. "
                f"Semi-automation recommended. Plan to upgrade to full automation when budget allows."
            )
        else:
            workflow = "manual"
            capital = MANUAL_SETUP
            annual_maint = capital * MANUAL_MAINTENANCE_PCT
            annual_operating = (manual_per_exp * params.experiments_per_year) + annual_maint
            break_even = float('inf')
            npv_5yr = -(capital + (annual_operating * params.timeline_years))
            rationale = (
                f"High throughput ({params.experiments_per_year}/year) but very limited budget. "
                f"Manual workflow will be labor-intensive. Strongly consider seeking funding for automation."
            )
            
    else:  # >= 50 experiments/year
        # Very high throughput - full automation strongly recommended
        if params.capital_budget_usd >= FULL_AUTO_SETUP:
            workflow = "full_automated"
            capital = FULL_AUTO_SETUP
            annual_maint = capital * FULL_AUTO_MAINTENANCE_PCT
            annual_operating = (auto_per_exp * params.experiments_per_year) + annual_maint
            break_even = capital / annual_savings if annual_savings > 0 else float('inf')
            npv_5yr = (annual_savings * params.timeline_years) - capital - (annual_maint * params.timeline_years)
            rationale = (
                f"Very high throughput ({params.experiments_per_year}/year). "
                f"Full automation is essential for efficiency and reproducibility. "
                f"Strong ROI with break-even in {break_even:.1f} years and 5-year NPV of ${npv_5yr:,.0f}."
            )
        else:
            workflow = "semi_automated"
            capital = SEMI_AUTO_SETUP
            annual_maint = capital * SEMI_AUTO_MAINTENANCE_PCT
            semi_labor_hours = MANUAL_LABOR_HOURS * 0.6
            semi_per_exp = REAGENT_COST + (semi_labor_hours * params.technician_hourly_rate_usd)
            annual_operating = (semi_per_exp * params.experiments_per_year) + annual_maint
            semi_savings = (manual_per_exp - semi_per_exp) * params.experiments_per_year
            break_even = capital / semi_savings if semi_savings > 0 else float('inf')
            npv_5yr = (semi_savings * params.timeline_years) - capital - (annual_maint * params.timeline_years)
            rationale = (
                f"Very high throughput ({params.experiments_per_year}/year) but limited budget. "
                f"Semi-automation recommended as interim solution. "
                f"CRITICAL: Plan to upgrade to full automation ASAP - manual/semi-auto will be a bottleneck."
            )
    
    return AutomationRecommendation(
        workflow=workflow,
        capital_cost_usd=capital,
        annual_operating_cost_usd=annual_operating,
        break_even_years=break_even,
        five_year_npv_usd=npv_5yr,
        rationale=rationale
    )


if __name__ == "__main__":
    # Example scenarios
    scenarios = [
        ("Academic Lab", LabParameters(10, 100_000)),
        ("Biotech Startup (Early)", LabParameters(25, 200_000)),
        ("Biotech Startup (Growth)", LabParameters(50, 500_000)),
        ("Pharma/Large Biotech", LabParameters(100, 1_000_000)),
    ]
    
    print("=" * 80)
    print("POSH AUTOMATION RECOMMENDATIONS")
    print("=" * 80)
    
    for name, params in scenarios:
        rec = recommend_posh_automation(params)
        print(f"\n{name}:")
        print(f"  Throughput: {params.experiments_per_year} experiments/year")
        print(f"  Budget: ${params.capital_budget_usd:,.0f}")
        print(f"  → Recommendation: {rec.workflow.upper().replace('_', ' ')}")
        print(f"  → Capital Cost: ${rec.capital_cost_usd:,.0f}")
        print(f"  → Annual Operating: ${rec.annual_operating_cost_usd:,.0f}")
        if rec.break_even_years < 100:
            print(f"  → Break-Even: {rec.break_even_years:.1f} years")
        else:
            print(f"  → Break-Even: Never (not cost-effective)")
        print(f"  → 5-Year NPV: ${rec.five_year_npv_usd:,.0f}")
        print(f"  → Rationale: {rec.rationale}")
