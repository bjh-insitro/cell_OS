import yaml
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

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
    stock_level: float = 0.0  # Current stock in logical units

class OutOfStockError(Exception):
    pass

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

class Inventory:
    def __init__(self, pricing_path: str):
        self.resources: Dict[str, Resource] = {}
        self._load_pricing(pricing_path)
        # Initialize stock with a default amount (e.g. 10 packs)
        for r in self.resources.values():
            r.stock_level = r.pack_size * 10.0

    def _load_pricing(self, path: str):
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        for item_id, item_data in data.get('items', {}).items():
            self.resources[item_id] = Resource(
                resource_id=item_id,
                name=item_data.get('name', ''),
                vendor=item_data.get('vendor', ''),
                catalog_number=item_data.get('catalog_number', ''),
                pack_size=float(item_data.get('pack_size', 1.0)),
                pack_unit=item_data.get('pack_unit', ''),
                pack_price_usd=float(item_data.get('pack_price_usd', 0.0)),
                logical_unit=item_data.get('logical_unit', ''),
                unit_price_usd=float(item_data.get('unit_price_usd', 0.0)),
                category=item_data.get('category', '')
            )

    def get_price(self, resource_id: str) -> float:
        if resource_id not in self.resources:
            return 0.0
        return self.resources[resource_id].unit_price_usd

    def deplete_stock(self, resource_id: str, quantity: float):
        """
        Deduct quantity from stock. Raise OutOfStockError if insufficient.
        """
        if resource_id not in self.resources:
            # Ignore unknown resources for now
            return
            
        res = self.resources[resource_id]
        if res.stock_level < quantity:
            raise OutOfStockError(f"Resource {resource_id} ({res.name}) out of stock! Required: {quantity}, Available: {res.stock_level}")
        
        res.stock_level -= quantity

    def restock(self, resource_id: str, quantity: float):
        """Add stock."""
        if resource_id in self.resources:
            self.resources[resource_id].stock_level += quantity
