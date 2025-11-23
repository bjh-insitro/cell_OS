from dataclasses import dataclass
from typing import List, Protocol, Optional
from src.unit_ops import AssayRecipe, UnitOpLibrary
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

def get_assay_candidates(library: UnitOpLibrary, inventory: Inventory) -> List[AssayCandidate]:
    """
    Factory function to generate the standard list of available assays with their costs and info scores.
    """
    from src.unit_ops import (
        get_posh_full_stack_recipe, 
        get_imicroglia_differentiation_recipe, 
        get_ngn2_differentiation_recipe,
        get_imicroglia_phagocytosis_recipe
    )
    
    # Define heuristic information scores (Bits)
    # POSH (Viability) = 1 bit
    # Phagocytosis (Imaging) = 10 bits
    # Bulk RNA-seq = 100 bits
    
    # We need a way to calculate cost from recipe using Inventory
    # Since UnitOpLibrary is currently CSV based but we want Inventory costs,
    # we need a bridge or update UnitOpLibrary.
    # For now, let's calculate cost by summing up unit ops in the recipe using Inventory.
    
    def calculate_recipe_cost(recipe: AssayRecipe) -> float:
        total = 0.0
        for layer_name, steps in recipe.layers.items():
            for uo_id, count in steps:
                # Try to get cost from Inventory
                cost = inventory.calculate_uo_cost(uo_id)
                if cost == 0.0:
                    # Fallback to UnitOpLibrary if not in Inventory (e.g. D15 compute)
                    # or if it's a CSV-only op.
                    # Ideally everything should be in Inventory now.
                    # For this prototype, we assume 0 if not found, or maybe we should check library?
                    # The library has material_cost_usd but that's static. Inventory is dynamic.
                    # Let's trust Inventory.
                    pass
                total += cost * count
        return total

    candidates = []
    
    # 1. POSH (Screening)
    posh = get_posh_full_stack_recipe()
    # POSH uses C7, C8, C9, P1-P7.
    # We need to make sure these are in unit_ops.yaml or we add them.
    # For now, let's assume they are NOT in YAML yet (we only added Diff/NGN2/Phago).
    # So we might need to add them or fallback.
    # Let's add a fallback in calculate_recipe_cost to use library.get(uo_id).material_cost_usd
    
    def calculate_recipe_cost_robust(recipe: AssayRecipe) -> float:
        total = 0.0
        for layer_name, steps in recipe.layers.items():
            for uo_id, count in steps:
                cost = inventory.calculate_uo_cost(uo_id)
                if cost == 0.0:
                    # Fallback to static library cost
                    try:
                        uo = library.get(uo_id)
                        cost = uo.material_cost_usd + uo.instrument_cost_usd
                    except:
                        cost = 0.0
                total += cost * count
        return total

    # POSH
    candidates.append(AssayCandidate(
        recipe=posh,
        cost_usd=calculate_recipe_cost_robust(posh),
        information_score=1.0
    ))
    
    # iMicroglia Differentiation (RNA-seq)
    imicroglia = get_imicroglia_differentiation_recipe()
    candidates.append(AssayCandidate(
        recipe=imicroglia,
        cost_usd=calculate_recipe_cost_robust(imicroglia),
        information_score=100.0
    ))
    
    # NGN2 Differentiation (RNA-seq)
    ngn2 = get_ngn2_differentiation_recipe()
    candidates.append(AssayCandidate(
        recipe=ngn2,
        cost_usd=calculate_recipe_cost_robust(ngn2),
        information_score=100.0
    ))
    
    # iMicroglia Phagocytosis (Imaging)
    phago = get_imicroglia_phagocytosis_recipe()
    candidates.append(AssayCandidate(
        recipe=phago,
        cost_usd=calculate_recipe_cost_robust(phago),
        information_score=10.0
    ))
    
    return candidates
