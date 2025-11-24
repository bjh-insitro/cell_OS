# src/core/costing.py

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from src.core.world_model import Artifact, UnitOp
from src.inventory import Inventory

# Constants for default volumes (can be moved to config later)
# Volumes in mL
VOL_FEED_6WELL = 2.5
VOL_FEED_12WELL = 1.5
VOL_FEED_96WELL = 0.2
VOL_FEED_T75 = 12.0
VOL_FEED_T175 = 25.0

VOL_PASSAGE_WASH_6WELL = 2.0
VOL_PASSAGE_DISSOCIATION_6WELL = 1.0
VOL_PASSAGE_QUENCH_6WELL = 2.0

# Mapping vessel_id patterns to volume constants
# This is a simple heuristic for now
VESSEL_VOL_MAP = {
    "plate_6well": VOL_FEED_6WELL,
    "plate_12well": VOL_FEED_12WELL,
    "plate_96well": VOL_FEED_96WELL,
    "t75_flask": VOL_FEED_T75,
    "t175_flask": VOL_FEED_T175,
}

class CostEngine(ABC):
    """
    Abstract base class for computing the cost of Unit Operations.
    """
    @abstractmethod
    def compute_cost(
        self,
        op: UnitOp,
        inputs: List[Artifact],
        outputs: List[Artifact],
        params: Dict[str, Any],
    ) -> float:
        """
        Compute the cost in USD for a single execution of a UnitOp.
        """
        pass


class InventoryCostEngine(CostEngine):
    """
    Cost engine that uses the Inventory system and pricing database.
    """
    def __init__(self, inventory: Inventory):
        self.inventory = inventory

    def compute_cost(
        self,
        op: UnitOp,
        inputs: List[Artifact],
        outputs: List[Artifact],
        params: Dict[str, Any],
    ) -> float:
        """
        Dispatch to specific cost calculators based on op name.
        Fallback to op.base_cost_usd.
        """
        if op.name == "op_feed":
            return self._cost_feed(inputs, params)
        elif op.name == "op_passage":
            return self._cost_passage(inputs, params)
        
        return op.base_cost_usd

    def _get_vessel_volume(self, vessel_id: str) -> float:
        """Estimate working volume based on vessel ID string."""
        for key, vol in VESSEL_VOL_MAP.items():
            if key in vessel_id:
                return vol
        return VOL_FEED_6WELL  # Default fallback

    def _resolve_media_price(self, media_name: str) -> float:
        """
        Map media string to pricing item.
        Simple heuristic mapping for demo purposes.
        """
        # Normalize
        name = media_name.lower()
        
        # Base media cost
        cost_per_ml = 0.0
        
        if "mtesr" in name:
            cost_per_ml += self.inventory.get_price("mtesr_plus_kit")
        elif "neurobasal" in name:
            cost_per_ml += self.inventory.get_price("neurobasal")
        elif "fluorobrite" in name:
            cost_per_ml += self.inventory.get_price("fluorobrite_dmem")
        elif "dmem" in name:
            # Assume standard DMEM unless specified
            cost_per_ml += self.inventory.get_price("dmem_high_glucose")
            
        # Supplements
        if "fbs" in name:
            # Assume 10% FBS
            cost_per_ml += 0.10 * self.inventory.get_price("fbs")
            
        if "penstrep" in name or "pen_strep" in name:
            # Assume 1% PenStrep
            cost_per_ml += 0.01 * self.inventory.get_price("pen_strep")
            
        if "b27" in name:
            # Assume 2% B27 (50X stock)
            cost_per_ml += 0.02 * self.inventory.get_price("b27_supp")
            
        if "n2" in name:
            # Assume 1% N2 (100X stock)
            cost_per_ml += 0.01 * self.inventory.get_price("n2_supp")
            
        if "glutamax" in name:
            # Assume 1% GlutaMAX
            cost_per_ml += 0.01 * self.inventory.get_price("glutamax")

        return cost_per_ml

    def _cost_feed(self, inputs: List[Artifact], params: Dict[str, Any]) -> float:
        """
        Calculate cost for FeedOp.
        Cost = Media Volume * Media Price
        """
        if not inputs:
            return 0.0
            
        artifact = inputs[0]
        vessel_id = artifact.state.get("vessel_id", "")
        media_name = params.get("media", artifact.state.get("media", ""))
        
        volume_ml = self._get_vessel_volume(vessel_id)
        price_per_ml = self._resolve_media_price(media_name)
        
        return volume_ml * price_per_ml

    def _cost_passage(self, inputs: List[Artifact], params: Dict[str, Any]) -> float:
        """
        Calculate cost for PassageOp.
        Cost = Dissociation Reagent + Quench Media + New Vessel + New Media (if applicable)
        
        Note: PassageOp usually implies moving to a NEW vessel, so we charge for the vessel.
        """
        if not inputs:
            return 0.0
            
        artifact = inputs[0]
        current_vessel = artifact.state.get("vessel_id", "")
        target_vessel = params.get("target_vessel", "")
        
        # 1. Dissociation Cost
        dissociation_method = params.get("dissociation_method", "trypsin")
        vol_dissociation = VOL_PASSAGE_DISSOCIATION_6WELL # Simplify: assume 6-well scale for now
        
        dissociation_price = 0.0
        if "trypsin" in dissociation_method.lower():
            dissociation_price = self.inventory.get_price("trypsin_edta")
        elif "accutase" in dissociation_method.lower():
            dissociation_price = self.inventory.get_price("accutase")
        elif "tryple" in dissociation_method.lower():
            dissociation_price = self.inventory.get_price("tryple")
            
        cost_dissociation = vol_dissociation * dissociation_price
        
        # 2. Vessel Cost
        cost_vessel = 0.0
        if "plate_6well" in target_vessel:
            cost_vessel = self.inventory.get_price("plate_6well")
        elif "plate_12well" in target_vessel:
            cost_vessel = self.inventory.get_price("plate_12well")
        elif "plate_96well" in target_vessel:
            cost_vessel = self.inventory.get_price("plate_96well_imaging_black_clearbottom")
        elif "t75" in target_vessel:
            cost_vessel = self.inventory.get_price("t75_flask")
            
        # 3. Media Cost (for resuspension/plating)
        # Passage usually involves plating in new media
        # We'll assume we fill the new vessel
        vol_media = self._get_vessel_volume(target_vessel)
        media_name = artifact.state.get("media", "") # Use existing media
        price_media = self._resolve_media_price(media_name)
        cost_media = vol_media * price_media
        
        return cost_dissociation + cost_vessel + cost_media
