"""
Cell Line Database

Manages cell line metadata, protocols, and inventory with full relationship tracking.
Replaces the 614-line cell_lines.yaml with a queryable database.
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class CellLine:
    """Core cell line metadata."""
    cell_line_id: str
    display_name: str
    cell_type: str  # iPSC, immortalized, primary, differentiated
    growth_media: str
    wash_buffer: Optional[str] = None
    detach_reagent: Optional[str] = None
    coating_required: bool = False
    coating_reagent: Optional[str] = None
    cost_tier: str = "standard"  # budget, standard, premium
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class CellLineCharacteristic:
    """Cell line characteristics (dissociation method, transfection, etc.)."""
    cell_line_id: str
    characteristic: str  # dissociation_method, transfection_method, etc.
    value: str
    notes: Optional[str] = None


@dataclass
class ProtocolParameters:
    """Protocol parameters for a specific vessel type."""
    cell_line_id: str
    protocol_type: str  # passage, thaw, feed
    vessel_type: str  # T75, T25, etc.
    parameters: Dict[str, Any]  # All volumes, times, temperatures


class CellLineDatabase:
    """
    Database for cell line management with full protocol and inventory tracking.
    
    Features:
    - Cell line metadata and characteristics
    - Protocol parameters for different vessel types
    - Inventory tracking (vials, locations, passage numbers)
    - Usage history
    - Relationship tracking
    """
    
    def __init__(self, db_path: str = "data/cell_lines.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Core cell line metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cell_lines (
                cell_line_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                cell_type TEXT NOT NULL,
                growth_media TEXT NOT NULL,
                wash_buffer TEXT,
                detach_reagent TEXT,
                coating_required BOOLEAN DEFAULT 0,
                coating_reagent TEXT,
                cost_tier TEXT DEFAULT 'standard',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Cell line characteristics (flexible key-value for profile data)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cell_line_characteristics (
                char_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cell_line_id TEXT NOT NULL,
                characteristic TEXT NOT NULL,
                value TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (cell_line_id) REFERENCES cell_lines(cell_line_id)
            )
        """)
        
        # Protocol parameters (passage, thaw, feed)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cell_line_protocols (
                protocol_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cell_line_id TEXT NOT NULL,
                protocol_type TEXT NOT NULL,
                vessel_type TEXT NOT NULL,
                parameters TEXT NOT NULL,
                FOREIGN KEY (cell_line_id) REFERENCES cell_lines(cell_line_id),
                UNIQUE(cell_line_id, protocol_type, vessel_type)
            )
        """)
        
        # Cell line inventory (actual vials)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cell_line_inventory (
                inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cell_line_id TEXT NOT NULL,
                vial_id TEXT UNIQUE NOT NULL,
                passage_number INTEGER,
                freeze_date DATE,
                location TEXT,
                status TEXT DEFAULT 'available',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cell_line_id) REFERENCES cell_lines(cell_line_id)
            )
        """)
        
        # Usage history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cell_line_usage (
                usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cell_line_id TEXT NOT NULL,
                vial_id TEXT,
                execution_id TEXT,
                usage_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                purpose TEXT,
                notes TEXT,
                FOREIGN KEY (cell_line_id) REFERENCES cell_lines(cell_line_id),
                FOREIGN KEY (vial_id) REFERENCES cell_line_inventory(vial_id)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cell_type ON cell_lines(cell_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_coating ON cell_lines(coating_required)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cost_tier ON cell_lines(cost_tier)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_char_cell_line ON cell_line_characteristics(cell_line_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_protocol_cell_line ON cell_line_protocols(cell_line_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_cell_line ON cell_line_inventory(cell_line_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_status ON cell_line_inventory(status)")
        
        conn.commit()
        conn.close()
    
    def add_cell_line(self, cell_line: CellLine) -> str:
        """Add a new cell line."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if cell_line.created_at is None:
            cell_line.created_at = datetime.now().isoformat()
        if cell_line.updated_at is None:
            cell_line.updated_at = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT OR REPLACE INTO cell_lines (
                cell_line_id, display_name, cell_type, growth_media,
                wash_buffer, detach_reagent, coating_required, coating_reagent,
                cost_tier, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cell_line.cell_line_id, cell_line.display_name, cell_line.cell_type,
            cell_line.growth_media, cell_line.wash_buffer, cell_line.detach_reagent,
            cell_line.coating_required, cell_line.coating_reagent, cell_line.cost_tier,
            cell_line.created_at, cell_line.updated_at
        ))
        
        conn.commit()
        conn.close()
        
        return cell_line.cell_line_id
    
    def get_cell_line(self, cell_line_id: str) -> Optional[CellLine]:
        """Get cell line by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM cell_lines WHERE cell_line_id = ?", (cell_line_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return CellLine(
                cell_line_id=row[0],
                display_name=row[1],
                cell_type=row[2],
                growth_media=row[3],
                wash_buffer=row[4],
                detach_reagent=row[5],
                coating_required=bool(row[6]),
                coating_reagent=row[7],
                cost_tier=row[8],
                created_at=row[9],
                updated_at=row[10]
            )
        return None
    
    def find_cell_lines(self, **filters) -> List[CellLine]:
        """Find cell lines matching filters."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        where_clauses = []
        params = []
        
        if 'cell_type' in filters:
            where_clauses.append("cell_type = ?")
            params.append(filters['cell_type'])
        
        if 'coating_required' in filters:
            where_clauses.append("coating_required = ?")
            params.append(filters['coating_required'])
        
        if 'cost_tier' in filters:
            where_clauses.append("cost_tier = ?")
            params.append(filters['cost_tier'])
        
        query = "SELECT * FROM cell_lines"
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [
            CellLine(
                cell_line_id=row[0],
                display_name=row[1],
                cell_type=row[2],
                growth_media=row[3],
                wash_buffer=row[4],
                detach_reagent=row[5],
                coating_required=bool(row[6]),
                coating_reagent=row[7],
                cost_tier=row[8],
                created_at=row[9],
                updated_at=row[10]
            )
            for row in rows
        ]
    
    def add_characteristic(self, char: CellLineCharacteristic):
        """Add a cell line characteristic."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO cell_line_characteristics (
                cell_line_id, characteristic, value, notes
            ) VALUES (?, ?, ?, ?)
        """, (char.cell_line_id, char.characteristic, char.value, char.notes))
        
        conn.commit()
        conn.close()
    
    def get_characteristics(self, cell_line_id: str) -> Dict[str, str]:
        """Get all characteristics for a cell line."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT characteristic, value FROM cell_line_characteristics
            WHERE cell_line_id = ?
        """, (cell_line_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return {row[0]: row[1] for row in rows}
    
    def add_protocol(self, protocol: ProtocolParameters):
        """Add protocol parameters for a cell line."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO cell_line_protocols (
                cell_line_id, protocol_type, vessel_type, parameters
            ) VALUES (?, ?, ?, ?)
        """, (
            protocol.cell_line_id,
            protocol.protocol_type,
            protocol.vessel_type,
            json.dumps(protocol.parameters)
        ))
        
        conn.commit()
        conn.close()
    
    def get_protocol(
        self,
        cell_line_id: str,
        protocol_type: str,
        vessel_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get protocol parameters."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT parameters FROM cell_line_protocols
            WHERE cell_line_id = ? AND protocol_type = ? AND vessel_type = ?
        """, (cell_line_id, protocol_type, vessel_type))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None

    def get_protocols(
        self,
        cell_line_id: str,
        protocol_type: str
    ) -> Dict[str, Dict[str, Any]]:
        """Return all protocol parameters for a cell line and protocol type."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT vessel_type, parameters FROM cell_line_protocols
            WHERE cell_line_id = ? AND protocol_type = ?
            """,
            (cell_line_id, protocol_type),
        )
        rows = cursor.fetchall()
        conn.close()
        return {row[0]: json.loads(row[1]) for row in rows}
    
    def add_vial(
        self,
        cell_line_id: str,
        vial_id: str,
        passage_number: int,
        location: str,
        freeze_date: Optional[str] = None,
        notes: Optional[str] = None
    ) -> int:
        """Add a vial to inventory."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if freeze_date is None:
            freeze_date = datetime.now().date().isoformat()
        
        cursor.execute("""
            INSERT INTO cell_line_inventory (
                cell_line_id, vial_id, passage_number, freeze_date, location, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (cell_line_id, vial_id, passage_number, freeze_date, location, notes))
        
        inventory_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return inventory_id
    
    def get_available_vials(self, cell_line_id: str) -> List[Dict[str, Any]]:
        """Get all available vials for a cell line."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM cell_line_inventory
            WHERE cell_line_id = ? AND status = 'available'
            ORDER BY passage_number
        """, (cell_line_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "inventory_id": row[0],
                "cell_line_id": row[1],
                "vial_id": row[2],
                "passage_number": row[3],
                "freeze_date": row[4],
                "location": row[5],
                "status": row[6],
                "notes": row[7]
            }
            for row in rows
        ]
    
    def use_vial(
        self,
        vial_id: str,
        execution_id: Optional[str] = None,
        purpose: str = "experiment",
        notes: Optional[str] = None
    ):
        """Mark a vial as used and log usage."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get cell line ID
        cursor.execute("SELECT cell_line_id FROM cell_line_inventory WHERE vial_id = ?", (vial_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Vial {vial_id} not found")
        
        cell_line_id = row[0]
        
        # Update vial status
        cursor.execute("""
            UPDATE cell_line_inventory
            SET status = 'used'
            WHERE vial_id = ?
        """, (vial_id,))
        
        # Log usage
        cursor.execute("""
            INSERT INTO cell_line_usage (
                cell_line_id, vial_id, execution_id, purpose, notes
            ) VALUES (?, ?, ?, ?, ?)
        """, (cell_line_id, vial_id, execution_id, purpose, notes))
        
        conn.commit()
        conn.close()
    
    def get_all_cell_lines(self) -> List[str]:
        """Get list of all cell line IDs."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT cell_line_id FROM cell_lines ORDER BY cell_line_id")
        rows = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in rows]
    
    def get_usage_history(self, cell_line_id: str) -> List[Dict[str, Any]]:
        """Get usage history for a cell line."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM cell_line_usage
            WHERE cell_line_id = ?
            ORDER BY usage_date DESC
        """, (cell_line_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "usage_id": row[0],
                "cell_line_id": row[1],
                "vial_id": row[2],
                "execution_id": row[3],
                "usage_date": row[4],
                "purpose": row[5],
                "notes": row[6]
            }
            for row in rows
        ]
