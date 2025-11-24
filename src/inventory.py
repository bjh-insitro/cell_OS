"""
inventory.py

Manages the economic model of the lab:
- resources (media, reagents, consumables, etc.)
- cost information from pricing.yaml
- stock tracking (optional, but supported)
- BOM items and integration with unit operations

Adds:
    - to_dataframe() for integration with LabWorldModel
"""

from __future__ import annotations

import yaml
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Optional, Any


# ---------------------------------------------------------------------
# Core resource representation
# ---------------------------------------------------------------------

@dataclass
class Resource:
    resource_id: str
    name: str
    vendor: str
    catalog_number: str
    pack_size: float
    pack_unit: str
    pack_price_usd: float
    logical_unit: str
    unit_price_usd: float
    category: str
    stock_level: float = 0.0   # current stock (in logical_unit)
    extra: Dict[str, Any] = None


class OutOfStockError(Exception):
    pass


# BOM = "bill of materials"
@dataclass
class BOMItem:
    resource_id: str
    quantity: float


@dataclass
class UnitOpDef:
    uo_id: str
    name: str
    layer: str
    description: str
    items: List[BOMItem]
    overhead_cost: float = 0.0


# ---------------------------------------------------------------------
# Inventory Loader
# ---------------------------------------------------------------------

class Inventory:
    """
    Loads pricing.yaml into Resource objects.

    Provides:
      - price lookup
      - stock tracking (optional)
      - BOM integration
      - to_dataframe() for LabWorldModel
    """

    def __init__(self, pricing_path: str):
        self.resources: Dict[str, Resource] = {}
        self._load_pricing(pricing_path)

        # initialize stock (e.g., 10 packs of everything)
        for r in self.resources.values():
            r.stock_level = r.pack_size * 10.0

    # -----------------------------------------------------------------

    def _load_pricing(self, path: str):
        with open(path, 'r') as f:
            data = yaml.safe_load(f) or {}

        items = data.get('items', {})

        for item_id, d in items.items():

            known_keys = {
                'name', 'vendor', 'catalog_number',
                'pack_size', 'pack_unit', 'pack_price_usd',
                'logical_unit', 'unit_price_usd', 'category'
            }

            extra = {k: v for k, v in d.items() if k not in known_keys}

            self.resources[item_id] = Resource(
                resource_id=item_id,
                name=d.get('name', ''),
                vendor=d.get('vendor', ''),
                catalog_number=d.get('catalog_number', ''),
                pack_size=float(d.get('pack_size', 1.0)),
                pack_unit=d.get('pack_unit', ''),
                pack_price_usd=float(d.get('pack_price_usd', 0.0)),
                logical_unit=d.get('logical_unit', ''),
                unit_price_usd=float(d.get('unit_price_usd', 0.0)),
                category=d.get('category', ''),
                extra=extra
            )

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def get_price(self, resource_id: str) -> float:
        """Return price per logical unit."""
        if resource_id not in self.resources:
            return 0.0
        return self.resources[resource_id].unit_price_usd

    def deplete_stock(self, resource_id: str, quantity: float):
        """
        Deduct quantity from stock. Raise OutOfStockError if insufficient.
        """
        if resource_id not in self.resources:
            return

        res = self.resources[resource_id]
        if res.stock_level < quantity:
            raise OutOfStockError(
                f"Resource {resource_id} ({res.name}) out of stock! "
                f"Required: {quantity}, Available: {res.stock_level}"
            )
        res.stock_level -= quantity
    
    def consume(self, resource_id: str, amount: float, unit: str = None) -\u003e bool:
        """
        Consume reagent from inventory.
        
        Args:
            resource_id: ID of resource to consume
            amount: Amount to consume
            unit: Unit (currently ignored, assumed to match logical_unit)
            
        Returns:
            True if consumed successfully, False if insufficient stock
        """
        try:
            self.deplete_stock(resource_id, amount)
            return True
        except OutOfStockError:
            return False
    
    def check_availability(self, bom: List[BOMItem]) -\u003e Dict[str, bool]:
        """
        Check if all BOM items are in stock.
        
        Args:
            bom: List of BOMItem objects
            
        Returns:
            Dict mapping resource_id to availability (True/False)
        """
        availability = {}
        for item in bom:
            if item.resource_id not in self.resources:
                availability[item.resource_id] = False
                continue
            
            res = self.resources[item.resource_id]
            availability[item.resource_id] = res.stock_level \u003e= item.quantity
        
        return availability

    def restock(self, resource_id: str, quantity: float):
        """Add stock."""
        if resource_id in self.resources:
            self.resources[resource_id].stock_level += quantity

    # -----------------------------------------------------------------
    # New: pricing export for LabWorldModel
    # -----------------------------------------------------------------

    def to_dataframe(self) -> pd.DataFrame:
        """
        Export the resources table as a DataFrame.

        Columns:
          resource_id
          name
          category
          vendor
          catalog_number
          pack_size
          pack_unit
          pack_price_usd
          logical_unit
          unit_price_usd
          stock_level
          extra
        """

        rows = []
        for r in self.resources.values():
            rows.append(
                {
                    "resource_id": r.resource_id,
                    "name": r.name,
                    "category": r.category,
                    "vendor": r.vendor,
                    "catalog_number": r.catalog_number,
                    "pack_size": r.pack_size,
                    "pack_unit": r.pack_unit,
                    "pack_price_usd": r.pack_price_usd,
                    "logical_unit": r.logical_unit,
                    "unit_price_usd": r.unit_price_usd,
                    "stock_level": r.stock_level,
                    "extra": r.extra,
                }
            )

        return pd.DataFrame(rows)
