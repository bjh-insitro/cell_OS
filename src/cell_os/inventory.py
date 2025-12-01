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
import sqlite3
import json
import os
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
    Loads pricing into Resource objects.
    Prioritizes SQLite DB, falls back to pricing.yaml.

    Provides:
      - price lookup
      - stock tracking (optional)
      - BOM integration
      - to_dataframe() for LabWorldModel
    """

    def __init__(self, pricing_path: str = None, db_path: str = "data/inventory.db"):
        self.resources: Dict[str, Resource] = {}
        self.usage_log: List[Dict[str, Any]] = []  # Log of all consumed resources
        
        loaded = False

        # If a pricing file is explicitly provided, prefer it for backwards compatibility
        if pricing_path:
            try:
                self._load_pricing(pricing_path)
                if self.resources:
                    for resource in self.resources.values():
                        resource.stock_level = resource.pack_size * 10.0
                    loaded = True
            except FileNotFoundError:
                pass
        
        # Otherwise try loading from DB
        if not loaded and db_path and os.path.exists(db_path):
            try:
                self._load_from_db(db_path)
                if self.resources:
                    loaded = True
            except Exception as e:
                print(f"Warning: Failed to load inventory from DB: {e}")
        
        # If nothing was loaded, ensure resources dict is populated and stock defaults make sense
        if not loaded and self.resources:
            for r in self.resources.values():
                r.stock_level = r.pack_size * 10.0

    def _load_from_db(self, db_path: str):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if resources table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resources'")
        if not cursor.fetchone():
            conn.close()
            return

        cursor.execute("SELECT * FROM resources")
        rows = cursor.fetchall()
        
        # Get column names
        col_names = [description[0] for description in cursor.description]
        
        for row in rows:
            d = dict(zip(col_names, row))
            
            extra = {}
            if d.get('extra_json'):
                try:
                    extra = json.loads(d['extra_json'])
                except:
                    pass
            
            self.resources[d['resource_id']] = Resource(
                resource_id=d['resource_id'],
                name=d['name'],
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
            
        conn.close()

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
    
    def get_resource(self, resource_id: str) -> Resource:
        """
        Get a resource by ID.
        """
        if resource_id not in self.resources:
            raise KeyError(f"Resource '{resource_id}' not found in inventory")
        return self.resources[resource_id]

    def get_unit_price(self, resource_id: str) -> float:
        """
        Return the unit price for a given resource.
        """
        return self.get_resource(resource_id).unit_price_usd

    def compute_bom_cost(self, items: List[BOMItem]) -> float:
        """
        Compute total cost for a list of BOM items.
        """
        total = 0.0
        for item in items:
            unit_price = self.get_unit_price(item.resource_id)
            total += unit_price * item.quantity
        return total

    def check_availability(self, items: List[BOMItem]) -> Dict[str, bool]:
        """
        Check if all items are available in sufficient quantity.
        
        Parameters
        ----------
        items : List[BOMItem]
            Items to check
        
        Returns
        -------
        availability : Dict[str, bool]
            Mapping of resource_id to availability status
        """
        availability = {}
        for item in items:
            resource = self.get_resource(item.resource_id)
            availability[item.resource_id] = resource.stock_level >= item.quantity
        return availability

    def add_stock(self, resource_id: str, quantity: float, unit: str) -> None:
        """Add stock to inventory.
        
        Parameters
        ----------
        resource_id : str
            Resource identifier
        quantity : float
            Amount to add
        unit : str
            Unit of measurement (must match resource's logical_unit)
        
        Raises
        ------
        KeyError
            If resource not found
        ValueError
            If unit doesn't match resource's logical_unit
        """
        resource = self.get_resource(resource_id)
        
        if unit != resource.logical_unit:
            raise ValueError(
                f"Unit mismatch: {unit} != {resource.logical_unit} for {resource_id}"
            )
        
        resource.stock_level += quantity

    def consume(self, resource_id: str, quantity: float, unit: str) -> None:
        """Consume stock from inventory.
        
        Parameters
        ----------
        resource_id : str
            Resource identifier
        quantity : float
            Amount to consume
        unit : str
            Unit of measurement (must match resource's logical_unit)
        
        Raises
        ------
        KeyError
            If resource not found
        ValueError
            If unit doesn't match resource's logical_unit
        OutOfStockError
            If insufficient stock available
        """
        resource = self.get_resource(resource_id)
        
        if unit != resource.logical_unit:
            raise ValueError(
                f"Unit mismatch: {unit} != {resource.logical_unit} for {resource_id}"
            )
        
        if resource.stock_level < quantity:
            raise OutOfStockError(
                f"Insufficient stock for {resource_id}: "
                f"requested {quantity} {unit}, available {resource.stock_level} {unit}"
            )
        
        resource.stock_level -= quantity
        
        # Log usage
        self.usage_log.append({
            "resource_id": resource_id,
            "quantity": quantity,
            "unit": unit,
            "timestamp": pd.Timestamp.now()
        })

    def check_stock(self, resource_id: str) -> float:
        """Check current stock level for a resource.
        
        Parameters
        ----------
        resource_id : str
            Resource identifier
        
        Returns
        -------
        stock_level : float
            Current stock level in resource's logical_unit
        
        Raises
        ------
        KeyError
            If resource not found
        """
        return self.get_resource(resource_id).stock_level

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert inventory to a DataFrame for LabWorldModel integration.
        
        Returns
        -------
        df : pd.DataFrame
            DataFrame with columns: resource_id, name, vendor, catalog_number,
            pack_size, pack_unit, pack_price_usd, logical_unit, unit_price_usd,
            category, stock_level
        """
        rows = []
        for rid, res in self.resources.items():
            rows.append({
                "resource_id": rid,
                "name": res.name,
                "vendor": res.vendor,
                "catalog_number": res.catalog_number,
                "pack_size": res.pack_size,
                "pack_unit": res.pack_unit,
                "pack_price_usd": res.pack_price_usd,
                "logical_unit": res.logical_unit,
                "unit_price_usd": res.unit_price_usd,
                "category": res.category,
                "stock_level": res.stock_level,
            })
        return pd.DataFrame(rows)
