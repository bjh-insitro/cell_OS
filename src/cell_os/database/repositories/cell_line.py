"""
Cell line repository for database operations.
"""
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from ..base import BaseRepository


@dataclass
class CellLine:
    """Core cell line metadata."""
    cell_line_id: str
    display_name: str
    cell_type: str
    growth_media: str
    wash_buffer: Optional[str] = None
    detach_reagent: Optional[str] = None
    coating_required: bool = False
    coating_reagent: Optional[str] = None
    cost_tier: str = "standard"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class CellLineCharacteristic:
    """Cell line characteristics (dissociation method, transfection, etc.)."""
    cell_line_id: str
    characteristic: str
    value: str
    notes: Optional[str] = None


@dataclass
class ProtocolParameters:
    """Protocol parameters for a specific vessel type."""
    cell_line_id: str
    protocol_type: str
    vessel_type: str
    parameters: Dict[str, Any]


class CellLineRepository(BaseRepository):
    """Repository for cell line management with protocol and inventory tracking."""
    
    def __init__(self, db_path: str = "data/cell_lines.db"):
        super().__init__(db_path)
    
    def _init_schema(self):
        """Initialize database schema."""
        conn = self._get_raw_connection()
        try:
            cursor = conn.cursor()
            
            # Cell lines table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cell_lines (
                    cell_line_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    cell_type TEXT NOT NULL,
                    growth_media TEXT NOT NULL,
                    wash_buffer TEXT,
                    detach_reagent TEXT,
                    coating_required INTEGER DEFAULT 0,
                    coating_reagent TEXT,
                    cost_tier TEXT DEFAULT 'standard',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Characteristics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cell_line_characteristics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cell_line_id TEXT NOT NULL,
                    characteristic TEXT NOT NULL,
                    value TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (cell_line_id) REFERENCES cell_lines(cell_line_id),
                    UNIQUE(cell_line_id, characteristic)
                )
            """)
            
            # Protocol parameters table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS protocol_parameters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cell_line_id TEXT NOT NULL,
                    protocol_type TEXT NOT NULL,
                    vessel_type TEXT NOT NULL,
                    parameters TEXT NOT NULL,
                    FOREIGN KEY (cell_line_id) REFERENCES cell_lines(cell_line_id),
                    UNIQUE(cell_line_id, protocol_type, vessel_type)
                )
            """)
            
            # Vial inventory table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vial_inventory (
                    vial_id TEXT PRIMARY KEY,
                    cell_line_id TEXT NOT NULL,
                    passage_number INTEGER NOT NULL,
                    location TEXT NOT NULL,
                    freeze_date TEXT,
                    status TEXT DEFAULT 'available',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cell_line_id) REFERENCES cell_lines(cell_line_id)
                )
            """)
            
            # Vial usage log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vial_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vial_id TEXT NOT NULL,
                    execution_id TEXT,
                    purpose TEXT DEFAULT 'experiment',
                    used_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY (vial_id) REFERENCES vial_inventory(vial_id)
                )
            """)
            
            conn.commit()
        finally:
            conn.close()
    
    def add_cell_line(self, cell_line: CellLine):
        """Add a new cell line."""
        data = asdict(cell_line)
        if not data.get('created_at'):
            data['created_at'] = datetime.now().isoformat()
        data['updated_at'] = datetime.now().isoformat()
        
        self._insert('cell_lines', data)
    
    def get_cell_line(self, cell_line_id: str) -> Optional[CellLine]:
        """Get cell line by ID."""
        row = self._fetch_one(
            "SELECT * FROM cell_lines WHERE cell_line_id = ?",
            (cell_line_id,)
        )
        return CellLine(**row) if row else None
    
    def find_cell_lines(self, **filters) -> List[CellLine]:
        """Find cell lines matching filters."""
        where_clauses = []
        params = []
        
        for key, value in filters.items():
            if key in ['cell_type', 'growth_media', 'cost_tier']:
                where_clauses.append(f"{key} = ?")
                params.append(value)
            elif key == 'coating_required':
                where_clauses.append("coating_required = ?")
                params.append(1 if value else 0)
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        rows = self._fetch_all(f"SELECT * FROM cell_lines WHERE {where_sql}", tuple(params))
        
        return [CellLine(**row) for row in rows]
    
    def add_characteristic(self, char: CellLineCharacteristic):
        """Add a cell line characteristic."""
        data = asdict(char)
        self._insert('cell_line_characteristics', data)
    
    def get_characteristics(self, cell_line_id: str) -> List[CellLineCharacteristic]:
        """Get all characteristics for a cell line."""
        rows = self._fetch_all(
            "SELECT cell_line_id, characteristic, value, notes FROM cell_line_characteristics WHERE cell_line_id = ?",
            (cell_line_id,)
        )
        return [CellLineCharacteristic(**row) for row in rows]
    
    def add_protocol(self, protocol: ProtocolParameters):
        """Add protocol parameters for a cell line."""
        data = asdict(protocol)
        data['parameters'] = json.dumps(data['parameters'])
        self._insert('protocol_parameters', data)
    
    def get_protocol(self, cell_line_id: str, protocol_type: str, vessel_type: str) -> Optional[ProtocolParameters]:
        """Get protocol parameters."""
        row = self._fetch_one(
            "SELECT * FROM protocol_parameters WHERE cell_line_id = ? AND protocol_type = ? AND vessel_type = ?",
            (cell_line_id, protocol_type, vessel_type)
        )
        if row:
            row = {k: v for k, v in row.items() if k != 'id'}
            row['parameters'] = json.loads(row['parameters'])
            return ProtocolParameters(**row)
        return None
    
    def get_protocols(self, cell_line_id: str, protocol_type: str) -> List[ProtocolParameters]:
        """Return all protocol parameters for a cell line and protocol type."""
        rows = self._fetch_all(
            "SELECT * FROM protocol_parameters WHERE cell_line_id = ? AND protocol_type = ?",
            (cell_line_id, protocol_type)
        )
        protocols = []
        for row in rows:
            row = {k: v for k, v in row.items() if k != 'id'}
            row['parameters'] = json.loads(row['parameters'])
            protocols.append(ProtocolParameters(**row))
        return protocols
    
    def add_vial(self, cell_line_id: str, vial_id: str, passage_number: int, location: str,
                 freeze_date: Optional[str] = None, notes: Optional[str] = None):
        """Add a vial to inventory."""
        data = {
            'vial_id': vial_id,
            'cell_line_id': cell_line_id,
            'passage_number': passage_number,
            'location': location,
            'freeze_date': freeze_date,
            'notes': notes
        }
        self._insert('vial_inventory', data)
    
    def get_available_vials(self, cell_line_id: str) -> List[Dict[str, Any]]:
        """Get all available vials for a cell line."""
        return self._fetch_all(
            "SELECT * FROM vial_inventory WHERE cell_line_id = ? AND status = 'available' ORDER BY passage_number",
            (cell_line_id,)
        )
    
    def use_vial(self, vial_id: str, execution_id: Optional[str] = None,
                 purpose: str = "experiment", notes: Optional[str] = None):
        """Mark a vial as used and log usage."""
        # Update vial status
        self._update('vial_inventory', {'status': 'used'}, "vial_id = ?", (vial_id,))
        
        # Log usage
        usage_data = {
            'vial_id': vial_id,
            'execution_id': execution_id,
            'purpose': purpose,
            'notes': notes
        }
        self._insert('vial_usage', usage_data)
    
    def get_all_cell_lines(self) -> List[str]:
        """Get list of all cell line IDs."""
        rows = self._fetch_all("SELECT cell_line_id FROM cell_lines")
        return [row['cell_line_id'] for row in rows]
    
    def get_usage_history(self, cell_line_id: str) -> List[Dict[str, Any]]:
        """Get usage history for a cell line."""
        return self._fetch_all("""
            SELECT u.*, v.passage_number, v.location
            FROM vial_usage u
            JOIN vial_inventory v ON u.vial_id = v.vial_id
            WHERE v.cell_line_id = ?
            ORDER BY u.used_at DESC
        """, (cell_line_id,))
