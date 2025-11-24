"""
posh_decision_engine.py

Interactive decision engine for selecting optimal POSH configuration.
Helps users choose between protocol variants, multimodal options, and automation levels.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

class POSHProtocol(Enum):
    ZOMBIE = "zombie"
    VANILLA = "vanilla"

class AutomationLevel(Enum):
    MANUAL = "manual"
    SEMI_AUTO = "semi_automated"
    FULL_AUTO = "fully_automated"

class ExperimentScale(Enum):
    PILOT = "pilot"          # 1-10 plates
    MEDIUM = "medium"        # 10-50 plates
    LARGE = "large"          # 50+ plates

@dataclass
class UserRequirements:
    """User's experimental requirements and constraints."""
    num_plates: int
    budget_usd: float
    timeline_weeks: int
    has_automation: bool = False
    needs_multimodal: bool = False
    tissue_samples: bool = False
    technical_expertise: str = "intermediate"  # beginner, intermediate, expert

@dataclass
class POSHRecommendation:
    """Recommended POSH configuration with justification."""
    protocol: POSHProtocol
    multimodal: bool
    automation: AutomationLevel
    estimated_cost_usd: float
    estimated_time_weeks: float
    justification: str
    warnings: List[str]
    alternatives: List[str]

class POSHDecisionEngine:
    """Decision engine for POSH configuration selection."""
    
    # Cost estimates (per plate, 6-well)
    COSTS = {
        "zombie_manual": 850.0,
        "zombie_auto": 950.0,
        "vanilla_manual": 3363.0,
        "vanilla_auto": 3463.0,
        "multimodal_addon": 500.0,
    }
    
    # Time estimates (per plate, hours)
    TIMES = {
        "zombie_manual": 24.0,
        "zombie_auto": 8.0,
        "vanilla_manual": 96.0,
        "vanilla_auto": 32.0,
        "multimodal_addon": 12.0,
    }
    
    def __init__(self):
        pass
    
    def recommend(self, req: UserRequirements) -> POSHRecommendation:
        """Generate recommendation based on user requirements."""
        
        warnings = []
        alternatives = []
        
        # Decision 1: Protocol Selection (Zombie is almost always better)
        protocol = POSHProtocol.ZOMBIE
        justification_parts = []
        
        # Only use Vanilla if user explicitly needs it for comparison
        if req.num_plates > 100:
            warnings.append("For very large screens (>100 plates), consider Zombie POSH's simpler workflow.")
        
        justification_parts.append(
            f"**Protocol: Zombie POSH** - Superior to Vanilla POSH in every metric: "
            f"75% cost savings, 76% faster, higher signal, nuclear localization."
        )
        
        # Decision 2: Multimodal
        multimodal = req.needs_multimodal
        if multimodal:
            justification_parts.append(
                f"**Multimodal: Enabled** - Includes HCR FISH and IBEX immunofluorescence "
                f"for comprehensive phenotyping (+${self.COSTS['multimodal_addon']:.0f}/plate)."
            )
        else:
            justification_parts.append(
                f"**Multimodal: Disabled** - Standard ISS-only readout. "
                f"Enable multimodal for RNA/protein measurements."
            )
            alternatives.append("Enable multimodal imaging for deeper phenotyping")
        
        # Decision 3: Automation Level
        automation = self._decide_automation(req)
        
        if automation == AutomationLevel.MANUAL:
            justification_parts.append(
                f"**Automation: Manual** - Cost-effective for {req.num_plates} plates. "
                f"Requires ~{req.num_plates * 3:.0f} staff-hours."
            )
            if req.num_plates > 20:
                alternatives.append("Consider semi-automation for >20 plates to reduce labor")
        
        elif automation == AutomationLevel.SEMI_AUTO:
            justification_parts.append(
                f"**Automation: Semi-Automated** - Liquid handler reduces hands-on time by 60%. "
                f"Optimal for {req.num_plates} plates."
            )
        
        else:  # FULL_AUTO
            justification_parts.append(
                f"**Automation: Fully Automated** - Integrated system for high throughput. "
                f"Required for {req.num_plates} plates."
            )
            if req.num_plates < 50:
                warnings.append("Full automation may be overkill for <50 plates. Consider semi-auto.")
        
        # Calculate Costs
        base_key = f"{protocol.value}_{automation.value.split('_')[0]}"
        cost_per_plate = self.COSTS.get(base_key, self.COSTS["zombie_manual"])
        if multimodal:
            cost_per_plate += self.COSTS["multimodal_addon"]
        
        total_cost = cost_per_plate * req.num_plates
        
        # Calculate Time
        time_per_plate = self.TIMES.get(base_key, self.TIMES["zombie_manual"])
        if multimodal:
            time_per_plate += self.TIMES["multimodal_addon"]
        
        # Assume 5 plates/week for manual, 10/week for semi, 20/week for full
        throughput = {"manual": 5, "semi_automated": 10, "fully_automated": 20}
        plates_per_week = throughput[automation.value]
        total_weeks = req.num_plates / plates_per_week
        
        # Budget Check
        if total_cost > req.budget_usd:
            warnings.append(
                f"⚠️ Estimated cost (${total_cost:,.0f}) exceeds budget (${req.budget_usd:,.0f}). "
                f"Consider reducing plate count or disabling multimodal."
            )
        
        # Timeline Check
        if total_weeks > req.timeline_weeks:
            warnings.append(
                f"⚠️ Estimated timeline ({total_weeks:.1f} weeks) exceeds target ({req.timeline_weeks} weeks). "
                f"Consider automation or parallel processing."
            )
        
        justification = "\n\n".join(justification_parts)
        
        return POSHRecommendation(
            protocol=protocol,
            multimodal=multimodal,
            automation=automation,
            estimated_cost_usd=total_cost,
            estimated_time_weeks=total_weeks,
            justification=justification,
            warnings=warnings,
            alternatives=alternatives
        )
    
    def _decide_automation(self, req: UserRequirements) -> AutomationLevel:
        """Decide automation level based on scale and capabilities."""
        
        if not req.has_automation:
            return AutomationLevel.MANUAL
        
        if req.num_plates < 20:
            return AutomationLevel.MANUAL
        elif req.num_plates < 50:
            return AutomationLevel.SEMI_AUTO
        else:
            return AutomationLevel.FULL_AUTO
    
    def compare_configurations(self, req: UserRequirements) -> Dict[str, POSHRecommendation]:
        """Compare multiple configurations."""
        
        configs = {}
        
        # Base recommendation
        configs["recommended"] = self.recommend(req)
        
        # Manual alternative
        req_manual = UserRequirements(
            num_plates=req.num_plates,
            budget_usd=req.budget_usd,
            timeline_weeks=req.timeline_weeks,
            has_automation=False,
            needs_multimodal=req.needs_multimodal,
            tissue_samples=req.tissue_samples
        )
        configs["manual"] = self.recommend(req_manual)
        
        # Multimodal alternative (if not already enabled)
        if not req.needs_multimodal:
            req_multi = UserRequirements(
                num_plates=req.num_plates,
                budget_usd=req.budget_usd,
                timeline_weeks=req.timeline_weeks,
                has_automation=req.has_automation,
                needs_multimodal=True,
                tissue_samples=req.tissue_samples
            )
            configs["multimodal"] = self.recommend(req_multi)
        
        return configs
