"""
Inventory Manager

Provides persistence and lot tracking for the lab inventory.
Wraps the base Inventory class to add stateful management.
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

from cell_os.inventory import Inventory, Resource, OutOfStockError


@dataclass
class Lot:
    """Represents a specific lot of a resource."""
    lot_id: str
    resource_id: str
    quantity: float
    initial_quantity: float
    expiration_date: Optional[datetime]
    received_date: datetime
    status: str = "active"  # active, depleted, expired, quarantined


class InventoryManager:
    """
    Manages persistent inventory state, lot tracking, and transactions.
    """
    
    def __init__(self, inventory: Inventory, db_path: str = "data/inventory.db"):
        self.inventory = inventory
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._sync_from_db()
        self.inventory.register_stock_sync(self.update_stock_level)
        
    def _init_db(self):
        """Initialize the inventory database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Lots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lots (
                lot_id TEXT PRIMARY KEY,
                resource_id TEXT NOT NULL,
                quantity REAL NOT NULL,
                initial_quantity REAL NOT NULL,
                expiration_date TEXT,
                received_date TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)
        
        # Transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_id TEXT NOT NULL,
                lot_id TEXT,
                quantity_change REAL NOT NULL,
                transaction_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT
            )
        """)
        
        # Stock levels cache (for fast lookup without summing lots every time)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_levels (
                resource_id TEXT PRIMARY KEY,
                total_quantity REAL NOT NULL
            )
        """)
        
        # Resources catalog table (replaces pricing.yaml)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resources (
                resource_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                vendor TEXT,
                catalog_number TEXT,
                pack_size REAL,
                pack_unit TEXT,
                pack_price_usd REAL,
                logical_unit TEXT,
                unit_price_usd REAL,
                extra_json TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        
    def _sync_from_db(self):
        """Sync in-memory Inventory object with DB state."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all stock levels
        cursor.execute("SELECT resource_id, total_quantity FROM stock_levels")
        rows = cursor.fetchall()
        
        db_stock = {row[0]: row[1] for row in rows}
        
        # Update inventory resources
        for res_id, resource in self.inventory.resources.items():
            if res_id in db_stock:
                resource.stock_level = db_stock[res_id]
            else:
                # If not in DB, initialize with default (or 0) and save to DB
                # For backward compatibility, we keep the default initialization from Inventory.__init__
                # but we should probably persist it.
                self._update_stock_level(res_id, resource.stock_level)
                
        conn.close()
        
    def update_stock_level(self, resource_id: str, new_level: float):
        """Public helper to upsert stock levels; used by Inventory callbacks."""
        self._update_stock_level(resource_id, new_level)

    def _update_stock_level(self, resource_id: str, new_level: float):
        """Update stock level in DB."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO stock_levels (resource_id, total_quantity)
            VALUES (?, ?)
        """, (resource_id, new_level))
        conn.commit()
        conn.close()

    def add_stock(self, resource_id: str, quantity: float, lot_id: Optional[str] = None, expiration_date: Optional[datetime] = None):
        """
        Add stock to inventory.
        
        Args:
            resource_id: Resource ID
            quantity: Amount to add
            lot_id: Optional lot ID (generated if None)
            expiration_date: Optional expiration date
        """
        if resource_id not in self.inventory.resources:
            raise KeyError(f"Unknown resource: {resource_id}")
            
        if lot_id is None:
            import random
            suffix = random.randint(1000, 9999)
            lot_id = f"LOT-{datetime.now().strftime('%Y%m%d')}-{resource_id[:4].upper()}-{suffix}"
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create lot
        cursor.execute("""
            INSERT INTO lots (lot_id, resource_id, quantity, initial_quantity, expiration_date, received_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            lot_id, 
            resource_id, 
            quantity, 
            quantity,
            expiration_date.isoformat() if expiration_date else None,
            datetime.now().isoformat(),
            "active"
        ))
        
        # Record transaction
        cursor.execute("""
            INSERT INTO transactions (resource_id, lot_id, quantity_change, transaction_type, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            resource_id,
            lot_id,
            quantity,
            "restock",
            datetime.now().isoformat(),
            json.dumps({})
        ))
        
        conn.commit()
        conn.close()
        
        # Update in-memory and cached total
        resource = self.inventory.resources[resource_id]
        resource.stock_level += quantity
        self._update_stock_level(resource_id, resource.stock_level)
        
    def consume_stock(self, resource_id: str, quantity: float, transaction_meta: Dict[str, Any] = None):
        """
        Consume stock, automatically depleting from oldest active lots (FIFO).
        
        Args:
            resource_id: Resource ID
            quantity: Amount to consume
            transaction_meta: Metadata (e.g., execution_id)
        """
        if resource_id not in self.inventory.resources:
            raise KeyError(f"Unknown resource: {resource_id}")
            
        resource = self.inventory.resources[resource_id]
        
        if resource.stock_level < quantity:
            raise OutOfStockError(f"Insufficient stock for {resource_id}. Required: {quantity}, Available: {resource.stock_level}")
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get active lots sorted by received_date (FIFO)
        cursor.execute("""
            SELECT lot_id, quantity FROM lots 
            WHERE resource_id = ? AND status = 'active' AND quantity > 0
            ORDER BY received_date ASC
        """, (resource_id,))
        
        lots = cursor.fetchall()
        remaining_to_consume = quantity
        
        for lot_id, lot_qty in lots:
            if remaining_to_consume <= 0:
                break
                
            consume_from_lot = min(lot_qty, remaining_to_consume)
            new_lot_qty = lot_qty - consume_from_lot
            
            # Update lot
            cursor.execute("UPDATE lots SET quantity = ? WHERE lot_id = ?", (new_lot_qty, lot_id))
            
            # If empty, mark depleted
            if new_lot_qty <= 0:
                cursor.execute("UPDATE lots SET status = 'depleted' WHERE lot_id = ?", (lot_id,))
                
            # Record transaction
            cursor.execute("""
                INSERT INTO transactions (resource_id, lot_id, quantity_change, transaction_type, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                resource_id,
                lot_id,
                -consume_from_lot,
                "usage",
                datetime.now().isoformat(),
                json.dumps(transaction_meta or {})
            ))
            
            remaining_to_consume -= consume_from_lot
            
        conn.commit()
        conn.close()
        
        # Update in-memory and cached total
        resource.stock_level -= quantity
        self._update_stock_level(resource_id, resource.stock_level)

    def get_transactions(self, resource_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get transaction history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT * FROM transactions"
        params = []
        
        if resource_id:
            query += " WHERE resource_id = ?"
            params.append(resource_id)
            
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            "id": r[0],
            "resource_id": r[1],
            "lot_id": r[2],
            "change": r[3],
            "type": r[4],
            "timestamp": r[5],
            "metadata": json.loads(r[6]) if r[6] else {}
        } for r in rows]

    def get_lots(self, resource_id: str) -> List[Dict[str, Any]]:
        """Get all lots for a resource."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM lots WHERE resource_id = ? ORDER BY received_date DESC", (resource_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            "lot_id": str(r[0]),
            "quantity": float(r[2]) if r[2] is not None else 0.0,
            "initial": float(r[3]) if r[3] is not None else 0.0,
            "expiration": str(r[4]) if r[4] else None,
            "received": str(r[5]) if r[5] else None,
            "status": str(r[6]) if r[6] else "unknown"
        } for r in rows]
