"""
Resource Costs module.
Stores pricing information.
"""

from __future__ import annotations
import pandas as pd
from dataclasses import dataclass, field

@dataclass
class ResourceCosts:
    """
    Registry for economic information.
    """
    pricing: pd.DataFrame = field(default_factory=pd.DataFrame)

    def get_unit_price(self, resource_id: str) -> float:
        """
        Look up unit price for a resource.
        
        Args:
            resource_id: Resource identifier
            
        Returns:
            Unit price in USD, or 0.0 if not found.
        """
        if self.pricing.empty:
            return 0.0
            
        # Check if resource_id is in the index or a column
        # Assuming pricing dataframe has 'resource_id' column or index
        
        # If 'resource_id' is a column
        if "resource_id" in self.pricing.columns:
            row = self.pricing[self.pricing["resource_id"] == resource_id]
            if not row.empty:
                return float(row.iloc[0].get("unit_price_usd", 0.0))
                
        # If index is resource_id (common for pricing.yaml load)
        # But we need to be sure. Let's check if it's in the index.
        if resource_id in self.pricing.index:
             return float(self.pricing.loc[resource_id].get("unit_price_usd", 0.0))
             
        # Fallback: check if 'id' column exists
        if "id" in self.pricing.columns:
            row = self.pricing[self.pricing["id"] == resource_id]
            if not row.empty:
                return float(row.iloc[0].get("unit_price_usd", 0.0))

        return 0.0
