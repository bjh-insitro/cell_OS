"""
Workflow Optimizer - Identify Cost-Saving Opportunities

This module analyzes workflows and suggests optimizations:
- Identifies most expensive operations
- Suggests cheaper alternatives with tradeoff analysis
- Calculates ROI for method changes
- Provides batch processing recommendations
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from src.unit_ops import UnitOp, ParametricOps
from src.automation_analysis import analyze_unit_op_automation

@dataclass
class OptimizationOpportunity:
    """Represents a potential cost-saving opportunity."""
    operation_name: str
    current_method: str
    current_cost_usd: float
    
    alternative_method: str
    alternative_cost_usd: float
    
    savings_usd: float
    savings_pct: float
    
    tradeoffs: List[str]  # List of considerations (e.g., "Harsher on cells")
    recommendation: str  # "Recommended", "Consider", "Not recommended"


class WorkflowOptimizer:
    """Analyzes workflows and suggests cost optimizations."""
    
    def __init__(self, ops: ParametricOps):
        self.ops = ops
    
    def analyze_workflow(
        self,
        operations: List[UnitOp],
        frequency_per_month: int = 1
    ) -> Dict[str, any]:
        """
        Analyze a workflow for optimization opportunities.
        
        Args:
            operations: List of operations in the workflow
            frequency_per_month: How often this workflow is performed
            
        Returns:
            Dictionary with analysis results
        """
        # Calculate current costs
        total_material = sum(op.material_cost_usd for op in operations)
        total_instrument = sum(op.instrument_cost_usd for op in operations)
        total_cost = total_material + total_instrument
        
        # Identify expensive operations (top 20%)
        op_costs = [
            (op, op.material_cost_usd + op.instrument_cost_usd)
            for op in operations
        ]
        op_costs.sort(key=lambda x: x[1], reverse=True)
        
        # Top 20% or at least top 3
        num_expensive = max(3, len(op_costs) // 5)
        expensive_ops = op_costs[:num_expensive]
        
        # Calculate labor costs
        total_labor_cost = 0
        for op in operations:
            analysis = analyze_unit_op_automation(op)
            total_labor_cost += analysis.labor_cost_usd
        
        monthly_cost = (total_cost + total_labor_cost) * frequency_per_month
        
        return {
            "total_cost_per_run": total_cost,
            "material_cost": total_material,
            "instrument_cost": total_instrument,
            "labor_cost": total_labor_cost,
            "monthly_cost": monthly_cost,
            "expensive_operations": expensive_ops,
            "num_operations": len(operations)
        }
    
    def suggest_passage_alternatives(
        self,
        current_method: str,
        vessel_id: str,
        cell_type: str
    ) -> List[OptimizationOpportunity]:
        """Suggest alternative dissociation methods."""
        
        current_op = self.ops.op_passage(vessel_id, dissociation_method=current_method)
        current_cost = current_op.material_cost_usd + current_op.instrument_cost_usd
        
        # Try alternatives
        alternatives = []
        methods = ["trypsin", "tryple", "accutase", "versene"]
        
        for method in methods:
            if method == current_method:
                continue
            
            try:
                alt_op = self.ops.op_passage(vessel_id, dissociation_method=method)
                alt_cost = alt_op.material_cost_usd + alt_op.instrument_cost_usd
                
                savings = current_cost - alt_cost
                savings_pct = (savings / current_cost * 100) if current_cost > 0 else 0
                
                # Determine tradeoffs
                tradeoffs = []
                if method == "trypsin":
                    tradeoffs.append("Harsher on cells than accutase/versene")
                    tradeoffs.append("May affect cell viability for sensitive lines")
                elif method == "versene":
                    tradeoffs.append("Slower dissociation (10 min vs 5 min)")
                    tradeoffs.append("Gentlest option, preserves surface markers")
                elif method == "tryple":
                    tradeoffs.append("Good balance of cost and gentleness")
                elif method == "accutase":
                    tradeoffs.append("Most expensive but gentlest enzyme")
                
                # Recommendation logic
                if savings > 0.5 and cell_type in ["immortalized"]:
                    recommendation = "Recommended"
                elif savings > 0.5:
                    recommendation = "Consider"
                elif savings < -0.5:
                    recommendation = "Not recommended"
                else:
                    recommendation = "Minimal impact"
                
                if abs(savings) > 0.10:  # Only suggest if >$0.10 difference
                    alternatives.append(OptimizationOpportunity(
                        operation_name="Passage",
                        current_method=current_method,
                        current_cost_usd=current_cost,
                        alternative_method=method,
                        alternative_cost_usd=alt_cost,
                        savings_usd=savings,
                        savings_pct=savings_pct,
                        tradeoffs=tradeoffs,
                        recommendation=recommendation
                    ))
            except Exception:
                continue
        
        # Sort by savings (highest first)
        alternatives.sort(key=lambda x: x.savings_usd, reverse=True)
        return alternatives
    
    def suggest_freezing_alternatives(
        self,
        current_media: str,
        num_vials: int,
        cell_type: str
    ) -> List[OptimizationOpportunity]:
        """Suggest alternative freezing media."""
        
        current_op = self.ops.op_freeze(num_vials, freezing_media=current_media)
        current_cost = current_op.material_cost_usd + current_op.instrument_cost_usd
        
        alternatives = []
        media_options = ["fbs_dmso", "cryostor", "bambanker", "mfresr"]
        
        for media in media_options:
            if media == current_media:
                continue
            
            try:
                alt_op = self.ops.op_freeze(num_vials, freezing_media=media)
                alt_cost = alt_op.material_cost_usd + alt_op.instrument_cost_usd
                
                savings = current_cost - alt_cost
                savings_pct = (savings / current_cost * 100) if current_cost > 0 else 0
                
                # Tradeoffs
                tradeoffs = []
                if media == "fbs_dmso":
                    tradeoffs.append("Contains DMSO (may affect some cell types)")
                    tradeoffs.append("Cheapest option, well-established protocol")
                elif media == "cryostor":
                    tradeoffs.append("DMSO-free, good for sensitive cells")
                    tradeoffs.append("More expensive")
                elif media == "bambanker":
                    tradeoffs.append("Serum-free, ready-to-use")
                    tradeoffs.append("Good recovery rates")
                elif media == "mfresr":
                    tradeoffs.append("Optimized for stem cells")
                    tradeoffs.append("Best for iPSC/hESC")
                
                # Recommendation
                if savings > 5 and cell_type == "immortalized":
                    recommendation = "Recommended"
                elif savings > 5 and cell_type in ["iPSC", "hESC"]:
                    recommendation = "Consider (verify recovery)"
                elif savings < -5:
                    recommendation = "Not recommended"
                else:
                    recommendation = "Minimal impact"
                
                if abs(savings) > 1.0:  # Only suggest if >$1 difference
                    alternatives.append(OptimizationOpportunity(
                        operation_name="Freeze",
                        current_method=current_media,
                        current_cost_usd=current_cost,
                        alternative_method=media,
                        alternative_cost_usd=alt_cost,
                        savings_usd=savings,
                        savings_pct=savings_pct,
                        tradeoffs=tradeoffs,
                        recommendation=recommendation
                    ))
            except Exception:
                continue
        
        alternatives.sort(key=lambda x: x.savings_usd, reverse=True)
        return alternatives
    
    def calculate_roi(
        self,
        opportunity: OptimizationOpportunity,
        frequency_per_month: int
    ) -> Dict[str, float]:
        """Calculate ROI for implementing an optimization."""
        
        monthly_savings = opportunity.savings_usd * frequency_per_month
        annual_savings = monthly_savings * 12
        
        # Assume minimal switching cost (validation runs)
        switching_cost = 100.0  # ~2 validation runs
        
        payback_months = switching_cost / monthly_savings if monthly_savings > 0 else float('inf')
        
        return {
            "monthly_savings_usd": monthly_savings,
            "annual_savings_usd": annual_savings,
            "switching_cost_usd": switching_cost,
            "payback_months": payback_months
        }
    
    def generate_optimization_report(
        self,
        operations: List[UnitOp],
        cell_type: str,
        frequency_per_month: int = 10
    ) -> str:
        """Generate a comprehensive optimization report."""
        
        analysis = self.analyze_workflow(operations, frequency_per_month)
        
        report = []
        report.append("=== Workflow Optimization Report ===\n")
        report.append(f"Frequency: {frequency_per_month}x per month")
        report.append(f"Current cost per run: ${analysis['total_cost_per_run']:.2f}")
        report.append(f"Monthly cost: ${analysis['monthly_cost']:.2f}")
        report.append(f"Annual cost: ${analysis['monthly_cost'] * 12:.2f}\n")
        
        # Find passage and freeze operations
        passage_ops = [op for op in operations if "Passage" in op.name or "passage" in op.uo_id.lower()]
        freeze_ops = [op for op in operations if "Freeze" in op.name or "freeze" in op.uo_id.lower()]
        
        total_potential_savings = 0
        
        if passage_ops:
            report.append("=== Passage Optimization Opportunities ===")
            # Assume first passage op
            current_method = "accutase"  # Default assumption
            alternatives = self.suggest_passage_alternatives(current_method, "plate_6well", cell_type)
            
            for alt in alternatives[:3]:  # Top 3
                roi = self.calculate_roi(alt, frequency_per_month)
                report.append(f"\n{alt.alternative_method.upper()}:")
                report.append(f"  Savings: ${alt.savings_usd:.2f} per run ({alt.savings_pct:.1f}%)")
                report.append(f"  Monthly: ${roi['monthly_savings_usd']:.2f}")
                report.append(f"  Annual: ${roi['annual_savings_usd']:.2f}")
                report.append(f"  Recommendation: {alt.recommendation}")
                if alt.tradeoffs:
                    report.append(f"  Tradeoffs:")
                    for tradeoff in alt.tradeoffs:
                        report.append(f"    - {tradeoff}")
                
                if alt.recommendation == "Recommended":
                    total_potential_savings += roi['annual_savings_usd']
        
        if freeze_ops:
            report.append("\n=== Freezing Optimization Opportunities ===")
            current_media = "cryostor"  # Default assumption
            alternatives = self.suggest_freezing_alternatives(current_media, 10, cell_type)
            
            for alt in alternatives[:3]:
                roi = self.calculate_roi(alt, frequency_per_month)
                report.append(f"\n{alt.alternative_method.upper()}:")
                report.append(f"  Savings: ${alt.savings_usd:.2f} per run ({alt.savings_pct:.1f}%)")
                report.append(f"  Monthly: ${roi['monthly_savings_usd']:.2f}")
                report.append(f"  Annual: ${roi['annual_savings_usd']:.2f}")
                report.append(f"  Recommendation: {alt.recommendation}")
                if alt.tradeoffs:
                    report.append(f"  Tradeoffs:")
                    for tradeoff in alt.tradeoffs:
                        report.append(f"    - {tradeoff}")
                
                if alt.recommendation == "Recommended":
                    total_potential_savings += roi['annual_savings_usd']
        
        report.append(f"\n=== Summary ===")
        report.append(f"Total potential annual savings: ${total_potential_savings:.2f}")
        report.append(f"Savings as % of current annual cost: {(total_potential_savings / (analysis['monthly_cost'] * 12) * 100):.1f}%")
        
        return "\n".join(report)
