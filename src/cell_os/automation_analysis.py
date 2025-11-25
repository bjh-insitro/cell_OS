"""
Automation Feasibility Analysis

This module analyzes unit operations and recipes to determine automation feasibility,
identify manual bottlenecks, and estimate labor vs automation cost tradeoffs.
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from cell_os.unit_ops import UnitOp, AssayRecipe

@dataclass
class AutomationAnalysis:
    """Analysis of automation feasibility for a recipe or operation."""
    total_steps: int
    automatable_steps: int
    manual_steps: int
    automation_percentage: float
    
    # Bottlenecks
    manual_bottlenecks: List[str]  # List of manual step names
    
    # Cost analysis
    estimated_labor_hours: float
    labor_cost_usd: float  # At $50/hr technician rate
    automation_cost_usd: float  # Instrument depreciation
    
    # Recommendations
    automation_feasible: bool
    blocking_steps: List[str]  # Steps that prevent full automation
    recommendations: List[str]


def analyze_unit_op_automation(op: UnitOp, labor_rate_usd_per_hour: float = 50.0) -> AutomationAnalysis:
    """
    Analyze automation feasibility for a single unit operation.
    
    Args:
        op: Unit operation to analyze
        labor_rate_usd_per_hour: Hourly labor cost for technician
        
    Returns:
        AutomationAnalysis with feasibility assessment
    """
    # If no sub_steps, analyze the operation itself
    if not op.sub_steps:
        steps = [op]
    else:
        steps = op.sub_steps
    
    total_steps = len(steps)
    automatable_steps = sum(1 for s in steps if s.automation_fit >= 1)
    manual_steps = total_steps - automatable_steps
    
    automation_percentage = (automatable_steps / total_steps * 100) if total_steps > 0 else 0
    
    # Identify manual bottlenecks
    manual_bottlenecks = [
        s.name for s in steps 
        if s.automation_fit == 0
    ]
    
    # Estimate labor time based on staff_attention scores
    # staff_attention: 0=none, 1=low, 2=medium, 3=high
    # Rough estimate: 0=0min, 1=5min, 2=15min, 3=30min per step
    attention_to_minutes = {0: 0, 1: 5, 2: 15, 3: 30}
    total_labor_minutes = sum(
        attention_to_minutes.get(s.staff_attention, 15) 
        for s in steps
    )
    estimated_labor_hours = total_labor_minutes / 60.0
    labor_cost_usd = estimated_labor_hours * labor_rate_usd_per_hour
    
    # Automation cost is sum of instrument costs
    automation_cost_usd = sum(s.instrument_cost_usd for s in steps)
    
    # Determine if automation is feasible
    automation_feasible = manual_steps == 0
    blocking_steps = manual_bottlenecks.copy()
    
    # Generate recommendations
    recommendations = []
    if automation_percentage >= 90:
        recommendations.append("Excellent automation candidate - minimal manual intervention")
    elif automation_percentage >= 70:
        recommendations.append("Good automation candidate - some manual steps remain")
        if manual_bottlenecks:
            recommendations.append(f"Manual bottlenecks: {', '.join(manual_bottlenecks[:3])}")
    elif automation_percentage >= 50:
        recommendations.append("Partial automation possible - significant manual work remains")
    else:
        recommendations.append("Poor automation candidate - mostly manual process")
    
    # Cost comparison
    if labor_cost_usd > automation_cost_usd * 2:
        recommendations.append(f"High labor cost (${labor_cost_usd:.2f}) - automation would save money")
    elif labor_cost_usd < automation_cost_usd * 0.5:
        recommendations.append(f"Low labor cost (${labor_cost_usd:.2f}) - manual may be more economical")
    
    return AutomationAnalysis(
        total_steps=total_steps,
        automatable_steps=automatable_steps,
        manual_steps=manual_steps,
        automation_percentage=automation_percentage,
        manual_bottlenecks=manual_bottlenecks,
        estimated_labor_hours=estimated_labor_hours,
        labor_cost_usd=labor_cost_usd,
        automation_cost_usd=automation_cost_usd,
        automation_feasible=automation_feasible,
        blocking_steps=blocking_steps,
        recommendations=recommendations
    )


def analyze_recipe_automation(recipe: AssayRecipe, labor_rate_usd_per_hour: float = 50.0) -> Dict[str, AutomationAnalysis]:
    """
    Analyze automation feasibility for an entire recipe across all layers.
    
    Args:
        recipe: Assay recipe to analyze
        labor_rate_usd_per_hour: Hourly labor cost
        
    Returns:
        Dictionary mapping layer names to AutomationAnalysis
    """
    analyses = {}
    
    for layer_name, ops_with_counts in recipe.ops_by_layer.items():
        # Aggregate all operations in this layer
        all_steps = []
        for op, count in ops_with_counts:
            if op.sub_steps:
                all_steps.extend(op.sub_steps * count)
            else:
                all_steps.extend([op] * count)
        
        # Create a synthetic UnitOp for analysis
        layer_op = UnitOp(
            uo_id=f"{recipe.assay_id}_{layer_name}",
            name=f"{layer_name} layer",
            layer=layer_name,
            category="composite",
            time_score=0,
            cost_score=0,
            automation_fit=0,
            failure_risk=0,
            staff_attention=0,
            instrument=None,
            sub_steps=all_steps
        )
        
        analyses[layer_name] = analyze_unit_op_automation(layer_op, labor_rate_usd_per_hour)
    
    return analyses


def compare_automation_methods(op1: UnitOp, op2: UnitOp, method1_name: str, method2_name: str) -> str:
    """
    Compare automation feasibility between two methods.
    
    Args:
        op1: First operation
        op2: Second operation
        method1_name: Name of first method
        method2_name: Name of second method
        
    Returns:
        Comparison summary string
    """
    analysis1 = analyze_unit_op_automation(op1)
    analysis2 = analyze_unit_op_automation(op2)
    
    summary = []
    summary.append(f"=== {method1_name} vs {method2_name} ===")
    summary.append(f"{method1_name}: {analysis1.automation_percentage:.1f}% automatable ({analysis1.manual_steps} manual steps)")
    summary.append(f"{method2_name}: {analysis2.automation_percentage:.1f}% automatable ({analysis2.manual_steps} manual steps)")
    
    if analysis1.automation_feasible and not analysis2.automation_feasible:
        summary.append(f"✓ {method1_name} is fully automatable, {method2_name} is not")
    elif analysis2.automation_feasible and not analysis1.automation_feasible:
        summary.append(f"✓ {method2_name} is fully automatable, {method1_name} is not")
    elif analysis1.automation_percentage > analysis2.automation_percentage:
        summary.append(f"✓ {method1_name} is more automatable")
    elif analysis2.automation_percentage > analysis1.automation_percentage:
        summary.append(f"✓ {method2_name} is more automatable")
    else:
        summary.append("= Both methods have similar automation feasibility")
    
    # Labor cost comparison
    labor_diff = analysis1.labor_cost_usd - analysis2.labor_cost_usd
    if abs(labor_diff) > 5:
        if labor_diff > 0:
            summary.append(f"💰 {method2_name} saves ${abs(labor_diff):.2f} in labor costs")
        else:
            summary.append(f"💰 {method1_name} saves ${abs(labor_diff):.2f} in labor costs")
    
    return "\n".join(summary)


def generate_automation_report(op: UnitOp) -> str:
    """
    Generate a detailed automation feasibility report for an operation.
    
    Args:
        op: Unit operation to analyze
        
    Returns:
        Formatted report string
    """
    analysis = analyze_unit_op_automation(op)
    
    report = []
    report.append(f"=== Automation Feasibility Report: {op.name} ===")
    report.append(f"Total Steps: {analysis.total_steps}")
    report.append(f"Automatable: {analysis.automatable_steps} ({analysis.automation_percentage:.1f}%)")
    report.append(f"Manual: {analysis.manual_steps}")
    report.append(f"")
    report.append(f"Labor Estimate: {analysis.estimated_labor_hours:.2f} hours (${analysis.labor_cost_usd:.2f})")
    report.append(f"Automation Cost: ${analysis.automation_cost_usd:.2f}")
    report.append(f"")
    
    if analysis.manual_bottlenecks:
        report.append(f"Manual Bottlenecks:")
        for bottleneck in analysis.manual_bottlenecks:
            report.append(f"  - {bottleneck}")
        report.append(f"")
    
    report.append(f"Recommendations:")
    for rec in analysis.recommendations:
        report.append(f"  • {rec}")
    
    return "\n".join(report)
