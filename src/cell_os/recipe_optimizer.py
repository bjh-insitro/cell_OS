"""
Recipe Optimizer - Intelligent Recipe Generation

This module creates optimized recipes based on constraints:
- Cell type (uses cell line database for optimal methods)
- Budget tier (budget, standard, premium)
- Automation requirements (avoids manual steps if needed)
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from cell_os.unit_ops import UnitOp, ParametricOps, AssayRecipe
from cell_os.cell_line_database import get_cell_line_profile, CellLineProfile

@dataclass
class RecipeConstraints:
    """Constraints for recipe optimization."""
    cell_line: str
    budget_tier: str = "standard"  # "budget", "standard", "premium"
    automation_required: bool = False
    max_cost_usd: Optional[float] = None
    prioritize_speed: bool = False  # If True, minimize time_score


class RecipeOptimizer:
    """Optimizes recipes based on constraints."""
    
    def __init__(self, ops: ParametricOps):
        self.ops = ops
    
    def _select_dissociation_method(self, profile: CellLineProfile, constraints: RecipeConstraints) -> str:
        """Select optimal dissociation method based on constraints."""
        
        # If automation required, avoid scraping
        if constraints.automation_required and profile.dissociation_method == "scraping":
            # Fallback to tryple (gentle and automatable)
            return "tryple"
        
        # Budget tier adjustments
        if constraints.budget_tier == "budget":
            # Use cheapest automatable method
            if profile.cell_type in ["immortalized"]:
                return "trypsin"  # Cheapest for hardy cells
            else:
                return "tryple"  # Cheap but gentler
        
        elif constraints.budget_tier == "premium":
            # Use recommended method from profile
            return profile.dissociation_method
        
        else:  # standard
            # Balance cost and quality
            if profile.dissociation_method in ["accutase", "versene"]:
                return profile.dissociation_method
            else:
                return "tryple"
    
    def _select_freezing_media(self, profile: CellLineProfile, constraints: RecipeConstraints) -> str:
        """Select optimal freezing media based on constraints."""
        
        if constraints.budget_tier == "budget":
            return "fbs_dmso"  # Cheapest option
        
        elif constraints.budget_tier == "premium":
            return profile.freezing_media  # Use recommended
        
        else:  # standard
            # Balance cost and quality
            if profile.cell_type in ["immortalized"]:
                return "fbs_dmso"
            elif profile.freezing_media == "cryostor":
                return "bambanker"  # Cheaper alternative
            else:
                return profile.freezing_media
    
    def _select_transfection_method(self, profile: CellLineProfile, constraints: RecipeConstraints) -> str:
        """Select optimal transfection method based on constraints."""
        
        if constraints.budget_tier == "budget":
            if profile.cell_type == "immortalized":
                return "pei"  # Cheapest
            else:
                return "lipofectamine"  # More reliable
        
        elif constraints.budget_tier == "premium":
            return profile.transfection_method
        
        else:  # standard
            if profile.transfection_method in ["pei", "calcium_phosphate"]:
                return profile.transfection_method
            else:
                return "lipofectamine"
    
    def _select_counting_method(self, constraints: RecipeConstraints) -> str:
        """Select optimal counting method based on constraints."""
        
        if constraints.automation_required:
            return "automated"  # Only automatable option
        
        if constraints.budget_tier == "budget":
            # Hemocytometer is cheap in materials but expensive in labor
            # Automated is better value overall
            return "automated"
        
        return "automated"  # Default
    
    def get_optimized_spin_up_recipe(
        self, 
        constraints: RecipeConstraints,
        num_vials: int = 10
    ) -> Tuple[List[UnitOp], Dict[str, str]]:
        """
        Generate optimized spin-up recipe.
        
        Args:
            constraints: Recipe constraints
            num_vials: Number of vials to freeze
            
        Returns:
            Tuple of (operations list, methods used dict)
        """
        profile = get_cell_line_profile(constraints.cell_line)
        if not profile:
            raise ValueError(f"Unknown cell line: {constraints.cell_line}")
        
        # Select optimal methods
        dissociation = self._select_dissociation_method(profile, constraints)
        freezing = self._select_freezing_media(profile, constraints)
        counting = self._select_counting_method(constraints)
        
        methods_used = {
            "dissociation": dissociation,
            "freezing": freezing,
            "counting": counting,
            "coating": profile.coating,
            "media": profile.media
        }
        
        # Build recipe
        ops_list = []
        
        # 1. Thaw initial vial
        ops_list.append(self.ops.op_thaw("plate_6well"))
        
        # 2. Expand (3 passages)
        for i in range(3):
            ops_list.append(self.ops.op_passage("plate_6well", dissociation_method=dissociation))
        
        # 3. Final expansion to T175
        ops_list.append(self.ops.op_passage("flask_t175", dissociation_method=dissociation))
        
        # 4. Freeze master bank
        ops_list.append(self.ops.op_freeze(num_vials, freezing_media=freezing))
        
        return ops_list, methods_used
    
    def get_optimized_maintenance_recipe(
        self,
        constraints: RecipeConstraints,
        vessel_id: str = "plate_6well"
    ) -> Tuple[List[UnitOp], Dict[str, str]]:
        """Generate optimized weekly maintenance recipe."""
        
        profile = get_cell_line_profile(constraints.cell_line)
        if not profile:
            raise ValueError(f"Unknown cell line: {constraints.cell_line}")
        
        dissociation = self._select_dissociation_method(profile, constraints)
        
        methods_used = {
            "dissociation": dissociation,
            "media": profile.media
        }
        
        ops_list = []
        
        # Feed 3x per week
        for _ in range(3):
            ops_list.append(self.ops.op_feed(vessel_id, media=profile.media))
        
        # Passage 1x per week
        ops_list.append(self.ops.op_passage(vessel_id, dissociation_method=dissociation))
        
        return ops_list, methods_used
    
    def calculate_recipe_cost(self, ops_list: List[UnitOp]) -> Dict[str, float]:
        """Calculate total cost for a recipe."""
        
        total_material = sum(op.material_cost_usd for op in ops_list)
        total_instrument = sum(op.instrument_cost_usd for op in ops_list)
        total_cost = total_material + total_instrument
        
        return {
            "material_cost_usd": total_material,
            "instrument_cost_usd": total_instrument,
            "total_cost_usd": total_cost
        }
    
    def compare_budget_tiers(
        self,
        cell_line: str,
        recipe_type: str = "spin_up"
    ) -> Dict[str, Dict]:
        """
        Compare costs across budget tiers.
        
        Args:
            cell_line: Cell line to analyze
            recipe_type: "spin_up" or "maintenance"
            
        Returns:
            Dictionary with tier -> {cost, methods} mapping
        """
        results = {}
        
        for tier in ["budget", "standard", "premium"]:
            constraints = RecipeConstraints(
                cell_line=cell_line,
                budget_tier=tier
            )
            
            if recipe_type == "spin_up":
                ops_list, methods = self.get_optimized_spin_up_recipe(constraints)
            else:
                ops_list, methods = self.get_optimized_maintenance_recipe(constraints)
            
            costs = self.calculate_recipe_cost(ops_list)
            
            results[tier] = {
                "cost": costs["total_cost_usd"],
                "methods": methods,
                "operations": ops_list
            }
        
        return results


def generate_optimization_report(
    optimizer: RecipeOptimizer,
    cell_line: str,
    recipe_type: str = "spin_up"
) -> str:
    """Generate a formatted optimization report."""
    
    comparison = optimizer.compare_budget_tiers(cell_line, recipe_type)
    
    report = []
    report.append(f"=== Recipe Optimization Report: {cell_line} ({recipe_type}) ===\n")
    
    for tier in ["budget", "standard", "premium"]:
        data = comparison[tier]
        report.append(f"{tier.upper()}:")
        report.append(f"  Total Cost: ${data['cost']:.2f}")
        report.append(f"  Methods:")
        for method_type, method_name in data['methods'].items():
            report.append(f"    {method_type}: {method_name}")
        report.append("")
    
    # Calculate savings
    budget_cost = comparison["budget"]["cost"]
    premium_cost = comparison["premium"]["cost"]
    savings = premium_cost - budget_cost
    pct = (savings / premium_cost * 100) if premium_cost > 0 else 0
    
    report.append(f"Savings (Budget vs Premium): ${savings:.2f} ({pct:.1f}%)")
    
    return "\n".join(report)
