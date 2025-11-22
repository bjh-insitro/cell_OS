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
    def __init__(self, pricing_path: str, unit_ops_path: str):
        self.resources: Dict[str, Resource] = {}
        self.unit_ops: Dict[str, UnitOpDef] = {}
        self._load_pricing(pricing_path)
        self._load_unit_ops(unit_ops_path)

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

    def _load_unit_ops(self, path: str):
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
            
        for uo_id, uo_data in data.get('unit_ops', {}).items():
            items = []
            for item_id, item_spec in uo_data.get('items', {}).items():
                items.append(BOMItem(
                    resource_id=item_id,
                    quantity=float(item_spec.get('quantity', 0.0))
                ))
            
            overhead = 0.0
            for _, ov_data in uo_data.get('overhead', {}).items():
                overhead += float(ov_data.get('cost_usd', 0.0))

            self.unit_ops[uo_id] = UnitOpDef(
                uo_id=uo_id,
                name=uo_data.get('name', ''),
                layer=uo_data.get('layer', ''),
                description=uo_data.get('description', ''),
                items=items,
                overhead_cost=overhead
            )

    def calculate_uo_cost(self, uo_id: str) -> float:
        if uo_id not in self.unit_ops:
            return 0.0
        
        uo = self.unit_ops[uo_id]
        total_cost = uo.overhead_cost
        
        for item in uo.items:
            if item.resource_id not in self.resources:
                print(f"Warning: Resource {item.resource_id} not found for UO {uo_id}")
                continue
            
            resource = self.resources[item.resource_id]
            cost = item.quantity * resource.unit_price_usd
            total_cost += cost
            
        return total_cost

    def get_bom_breakdown(self, uo_id: str) -> str:
        if uo_id not in self.unit_ops:
            return "No definition found."
        
        uo = self.unit_ops[uo_id]
        lines = []
        total = uo.overhead_cost
        
        lines.append(f"Unit Op: {uo.name}")
        if uo.overhead_cost > 0:
             lines.append(f"- Overhead: ${uo.overhead_cost:.2f}")

        for item in uo.items:
            res = self.resources.get(item.resource_id)
            if res:
                cost = item.quantity * res.unit_price_usd
                lines.append(f"- {res.name}: {item.quantity} {res.logical_unit} @ ${res.unit_price_usd:.4f}/{res.logical_unit} = ${cost:.2f}")
                total += cost
            else:
                lines.append(f"- {item.resource_id}: Resource not found")
        
        lines.append(f"Total: ${total:.2f}")
        return "\n".join(lines)
