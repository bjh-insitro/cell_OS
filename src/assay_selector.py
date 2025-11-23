from dataclasses import dataclass
from typing import List, Protocol, Optional
from src.unit_ops import UnitOpLibrary, UnitOp, AssayRecipe, ParametricOps
from src.inventory import Inventory

@dataclass
class AssayCandidate:
    recipe: AssayRecipe
    cost_usd: float
    information_score: float

    @property
    def roi(self) -> float:
        """Bits per Dollar"""
        if self.cost_usd == 0:
            return 0.0
        return self.information_score / self.cost_usd

class AssaySelector(Protocol):
    def select(self, candidates: List[AssayCandidate], budget_usd: float) -> Optional[AssayCandidate]:
        ...

class GreedyROISelector:
    """
    Selects the assay with the highest ROI (Information / Cost) that fits within the budget.
    """
    def select(self, candidates: List[AssayCandidate], budget_usd: float) -> Optional[AssayCandidate]:
        # Filter candidates that fit in budget
        valid_candidates = [c for c in candidates if c.cost_usd <= budget_usd]
        
        if not valid_candidates:
            return None
            
        # Sort by ROI descending
        valid_candidates.sort(key=lambda x: x.roi, reverse=True)
        
        return valid_candidates[0]


class CostConstrainedSelector:
    """
    Advanced selector that considers budget constraints and can optimize methods.
    
    Features:
    - Filters by budget
    - Can suggest method optimizations to fit budget
    - Provides explanations for selections
    """
    
    def __init__(self, cell_line: Optional[str] = None):
        """
        Args:
            cell_line: If provided, will optimize methods for this cell type
        """
        self.cell_line = cell_line
    
    def select(
        self, 
        candidates: List[AssayCandidate], 
        budget_usd: float,
        prioritize_info: bool = True
    ) -> Optional[AssayCandidate]:
        """
        Select best assay within budget.
        
        Args:
            candidates: List of assay candidates
            budget_usd: Maximum budget
            prioritize_info: If True, maximize info gain. If False, maximize ROI.
            
        Returns:
            Selected candidate or None if nothing fits budget
        """
        # Filter by budget
        valid_candidates = [c for c in candidates if c.cost_usd <= budget_usd]
        
        if not valid_candidates:
            return None
        
        # Sort by priority
        if prioritize_info:
            # Maximize information gain (even if ROI is lower)
            valid_candidates.sort(key=lambda x: x.information_score, reverse=True)
        else:
            # Maximize ROI
            valid_candidates.sort(key=lambda x: x.roi, reverse=True)
        
        return valid_candidates[0]
    
    def explain_selection(
        self,
        selected: AssayCandidate,
        candidates: List[AssayCandidate],
        budget_usd: float
    ) -> str:
        """Generate explanation for why this assay was selected."""
        
        explanation = []
        explanation.append(f"Selected: {selected.recipe.name}")
        explanation.append(f"Cost: ${selected.cost_usd:.2f} (Budget: ${budget_usd:.2f})")
        explanation.append(f"Information: {selected.information_score:.1f} bits")
        explanation.append(f"ROI: {selected.roi:.2f} bits/$")
        
        # Compare to alternatives
        valid_alternatives = [c for c in candidates if c.cost_usd <= budget_usd and c != selected]
        if valid_alternatives:
            explanation.append("\nAlternatives within budget:")
            for alt in valid_alternatives[:3]:  # Top 3
                explanation.append(f"  - {alt.recipe.name}: ${alt.cost_usd:.2f}, "
                                 f"{alt.information_score:.1f} bits, ROI={alt.roi:.2f}")
        
        # Show what's excluded by budget
        excluded = [c for c in candidates if c.cost_usd > budget_usd]
        if excluded:
            explanation.append(f"\nExcluded by budget ({len(excluded)} assays):")
            for exc in excluded[:2]:
                explanation.append(f"  - {exc.recipe.name}: ${exc.cost_usd:.2f} "
                                 f"(${exc.cost_usd - budget_usd:.2f} over budget)")
        
        return "\n".join(explanation)

def get_assay_candidates(ops: ParametricOps, inventory: Inventory) -> List[AssayCandidate]:
    """
    Factory function to generate the standard list of available assays with their costs and info scores.
    """
    from src.unit_ops import (
        get_imicroglia_differentiation_recipe, 
        get_ngn2_differentiation_recipe,
        get_imicroglia_phagocytosis_recipe
    )
    
    candidates = []
    
    def calculate_recipe_cost(recipe: AssayRecipe) -> float:
        # Use the derive_score method which now handles UnitOp objects with costs
        # We pass None as library since we expect all items to be UnitOp objects from ParametricOps
        score = recipe.derive_score(None)
        return score.total_usd

    # 1. iMicroglia Differentiation (RNA-seq)
    imicroglia = get_imicroglia_differentiation_recipe(ops)
    candidates.append(AssayCandidate(
        recipe=imicroglia,
        cost_usd=calculate_recipe_cost(imicroglia),
        information_score=100.0
    ))
    
    # 2. NGN2 Differentiation (RNA-seq)
    ngn2 = get_ngn2_differentiation_recipe(ops)
    candidates.append(AssayCandidate(
        recipe=ngn2,
        cost_usd=calculate_recipe_cost(ngn2),
        information_score=100.0
    ))
    
    # 3. iMicroglia Phagocytosis (Imaging)
    phago = get_imicroglia_phagocytosis_recipe(ops)
    candidates.append(AssayCandidate(
        recipe=phago,
        cost_usd=calculate_recipe_cost(phago),
        information_score=10.0
    ))
    
    return candidates
