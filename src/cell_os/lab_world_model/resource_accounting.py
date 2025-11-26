"""
Resource Accounting module.
Calculates costs based on resource usage logs.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .resource_costs import ResourceCosts

@dataclass
class ResourceAccounting:
    """
    Accounting engine for calculating costs.
    
    Pure logic component that uses ResourceCosts to price items
    in a usage log.
    """
    resource_costs: ResourceCosts

    def calculate_cost(self, resource_id: str, quantity: float) -> float:
        """
        Calculate cost for a specific quantity of a resource.
        
        Args:
            resource_id: ID of the resource (must exist in pricing)
            quantity: Amount consumed (in logical units)
            
        Returns:
            Cost in USD
        """
        unit_price = self.resource_costs.get_unit_price(resource_id)
        return unit_price * quantity

    def aggregate_costs(self, usage_log: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate costs from a usage log.
        
        Args:
            usage_log: List of dicts with keys 'resource_id', 'quantity'
            
        Returns:
            Dict with:
                - total_cost_usd: float
                - breakdown: Dict[resource_id, float] (cost per resource)
        """
        total_cost = 0.0
        breakdown = {}
        
        for entry in usage_log:
            rid = entry.get('resource_id')
            qty = entry.get('quantity', 0.0)
            
            if not rid:
                continue
                
            cost = self.calculate_cost(rid, qty)
            total_cost += cost
            
            breakdown[rid] = breakdown.get(rid, 0.0) + cost
            
        return {
            "total_cost_usd": total_cost,
            "breakdown": breakdown
        }
