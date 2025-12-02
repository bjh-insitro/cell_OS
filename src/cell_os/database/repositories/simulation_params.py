"""
Simulation parameters repository for database operations.
"""
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from ..base import BaseRepository


@dataclass
class CellLineSimParams:
    """Simulation parameters for a cell line."""
    cell_line_id: str
    doubling_time_h: float
    max_confluence: float
    max_passage: int
    senescence_rate: float
    seeding_efficiency: float
    passage_stress: float
    cell_count_cv: float
    viability_cv: float
    biological_cv: float
    coating_required: bool = False
    version: int = 1
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class CompoundSensitivity:
    """Compound sensitivity data for a cell line."""
    compound_name: str
    cell_line_id: str
    ic50_um: float
    hill_slope: float
    confidence_interval_low: Optional[float] = None
    confidence_interval_high: Optional[float] = None
    source: str = "estimated"
    version: int = 1
    valid_from: Optional[str] = None
    notes: Optional[str] = None


class SimulationParamsRepository(BaseRepository):
    """Repository for simulation parameters with versioning support."""
    
    def __init__(self, db_path: str = "data/simulation_params.db"):
        super().__init__(db_path)
    
    def _init_schema(self):
        """Initialize database schema."""
        conn = self._get_raw_connection()
        try:
            cursor = conn.cursor()
            
            # Cell line parameters table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cell_line_params (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cell_line_id TEXT NOT NULL,
                    doubling_time_h REAL NOT NULL,
                    max_confluence REAL NOT NULL,
                    max_passage INTEGER NOT NULL,
                    senescence_rate REAL NOT NULL,
                    seeding_efficiency REAL NOT NULL,
                    passage_stress REAL NOT NULL,
                    cell_count_cv REAL NOT NULL,
                    viability_cv REAL NOT NULL,
                    biological_cv REAL NOT NULL,
                    coating_required INTEGER DEFAULT 0,
                    version INTEGER DEFAULT 1,
                    valid_from TEXT DEFAULT CURRENT_TIMESTAMP,
                    valid_to TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Compound sensitivity table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS compound_sensitivity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    compound_name TEXT NOT NULL,
                    cell_line_id TEXT NOT NULL,
                    ic50_um REAL NOT NULL,
                    hill_slope REAL NOT NULL,
                    confidence_interval_low REAL,
                    confidence_interval_high REAL,
                    source TEXT DEFAULT 'estimated',
                    version INTEGER DEFAULT 1,
                    valid_from TEXT DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(compound_name, cell_line_id, version)
                )
            """)
            
            # Default parameters table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS default_params (
                    param_name TEXT PRIMARY KEY,
                    param_value REAL NOT NULL,
                    description TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Simulation run log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS simulation_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT NOT NULL,
                    cell_line_id TEXT NOT NULL,
                    param_version INTEGER NOT NULL,
                    results_path TEXT,
                    metadata TEXT,
                    run_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
        finally:
            conn.close()
    
    def add_cell_line_params(self, params: CellLineSimParams):
        """Add or update cell line simulation parameters."""
        # Invalidate previous version
        self._execute(
            "UPDATE cell_line_params SET valid_to = ? WHERE cell_line_id = ? AND valid_to IS NULL",
            (datetime.now().isoformat(), params.cell_line_id)
        )
        
        # Insert new version
        data = asdict(params)
        if not data.get('valid_from'):
            data['valid_from'] = datetime.now().isoformat()
        
        self._insert('cell_line_params', data)
    
    def get_cell_line_params(self, cell_line_id: str, version: Optional[int] = None) -> Optional[CellLineSimParams]:
        """Get simulation parameters for a cell line."""
        if version:
            row = self._fetch_one(
                "SELECT * FROM cell_line_params WHERE cell_line_id = ? AND version = ?",
                (cell_line_id, version)
            )
        else:
            # Get latest active version
            row = self._fetch_one(
                "SELECT * FROM cell_line_params WHERE cell_line_id = ? AND valid_to IS NULL ORDER BY version DESC LIMIT 1",
                (cell_line_id,)
            )
        
        if row:
            row = {k: v for k, v in row.items() if k not in ['id', 'created_at']}
            return CellLineSimParams(**row)
        return None
    
    def add_compound_sensitivity(self, sensitivity: CompoundSensitivity):
        """Add compound sensitivity data."""
        data = asdict(sensitivity)
        if not data.get('valid_from'):
            data['valid_from'] = datetime.now().isoformat()
        
        self._insert('compound_sensitivity', data)
    
    def get_compound_sensitivity(self, compound_name: str, cell_line_id: str,
                                 version: Optional[int] = None) -> Optional[CompoundSensitivity]:
        """Get compound sensitivity for a cell line."""
        if version:
            row = self._fetch_one(
                "SELECT * FROM compound_sensitivity WHERE compound_name = ? AND cell_line_id = ? AND version = ?",
                (compound_name, cell_line_id, version)
            )
        else:
            # Get latest version
            row = self._fetch_one(
                "SELECT * FROM compound_sensitivity WHERE compound_name = ? AND cell_line_id = ? ORDER BY version DESC LIMIT 1",
                (compound_name, cell_line_id)
            )
        
        if row:
            # DEBUG: Print row keys to debug sensitivity_id issue
            # print(f"DEBUG: Row keys: {row.keys()}")
            row = {k: v for k, v in row.items() if k not in ['id', 'sensitivity_id', 'created_at']}
            return CompoundSensitivity(**row)
        return None
    
    def find_sensitive_compounds(self, cell_line_id: str, max_ic50: float) -> List[CompoundSensitivity]:
        """Find all compounds with IC50 below threshold for a cell line."""
        rows = self._fetch_all(
            "SELECT * FROM compound_sensitivity WHERE cell_line_id = ? AND ic50_um <= ? ORDER BY ic50_um",
            (cell_line_id, max_ic50)
        )
        
        sensitivities = []
        for row in rows:
            row = {k: v for k, v in row.items() if k not in ['id', 'sensitivity_id', 'created_at']}
            sensitivities.append(CompoundSensitivity(**row))
        return sensitivities
    
    def set_default_param(self, param_name: str, param_value: float, description: str = ""):
        """Set a default parameter value."""
        data = {
            'param_name': param_name,
            'param_value': param_value,
            'description': description,
            'updated_at': datetime.now().isoformat()
        }
        # Use INSERT OR REPLACE for upsert
        if self.use_pooling:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO default_params (param_name, param_value, description, updated_at) VALUES (?, ?, ?, ?)",
                    (param_name, param_value, description, data['updated_at'])
                )
                conn.commit()
        else:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO default_params (param_name, param_value, description, updated_at) VALUES (?, ?, ?, ?)",
                    (param_name, param_value, description, data['updated_at'])
                )
                conn.commit()
            finally:
                conn.close()
    
    def get_default_param(self, param_name: str) -> Optional[float]:
        """Get a default parameter value."""
        row = self._fetch_one(
            "SELECT param_value FROM default_params WHERE param_name = ?",
            (param_name,)
        )
        return row['param_value'] if row else None
    
    def log_simulation_run(self, campaign_id: str, cell_line_id: str, param_version: int,
                          results_path: Optional[str] = None, metadata: Optional[Dict] = None):
        """Log a simulation run with the parameter version used."""
        data = {
            'campaign_id': campaign_id,
            'cell_line_id': cell_line_id,
            'param_version': param_version,
            'results_path': results_path,
            'metadata': json.dumps(metadata) if metadata else None
        }
        self._insert('simulation_runs', data)
    
    def get_all_cell_lines(self) -> List[str]:
        """Get list of all cell lines with parameters."""
        rows = self._fetch_all("SELECT DISTINCT cell_line_id FROM cell_line_params")
        return [row['cell_line_id'] for row in rows]
    
    def get_all_compounds(self) -> List[str]:
        """Get list of all compounds with sensitivity data."""
        rows = self._fetch_all("SELECT DISTINCT compound_name FROM compound_sensitivity")
        return [row['compound_name'] for row in rows]
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export all data to dictionary (for backup or YAML export)."""
        export = {
            'cell_line_params': [],
            'compound_sensitivity': [],
            'default_params': {}
        }
        
        # Export cell line params
        rows = self._fetch_all("SELECT * FROM cell_line_params WHERE valid_to IS NULL")
        for row in rows:
            row = {k: v for k, v in row.items() if k not in ['id', 'created_at']}
            export['cell_line_params'].append(row)
        
        # Export compound sensitivity
        rows = self._fetch_all("SELECT * FROM compound_sensitivity")
        for row in rows:
            row = {k: v for k, v in row.items() if k not in ['id', 'created_at']}
            export['compound_sensitivity'].append(row)
        
        # Export default params
        rows = self._fetch_all("SELECT param_name, param_value FROM default_params")
        for row in rows:
            export['default_params'][row['param_name']] = row['param_value']
        
        return export
