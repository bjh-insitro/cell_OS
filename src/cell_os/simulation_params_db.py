"""
Simulation Parameters Database

Manages biological parameters for cell lines and compounds used in simulations.
Provides versioning, history tracking, and easy querying.
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import warnings

warnings.warn(
    "cell_os.simulation_params_db is deprecated and will be removed. "
    "Use cell_os.database.repositories.simulation_params instead.",
    DeprecationWarning,
    stacklevel=2
)


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
    source: str = "estimated"  # literature, experimental, estimated
    version: int = 1
    valid_from: Optional[str] = None
    notes: Optional[str] = None


class SimulationParamsDatabase:
    """
    Database for simulation parameters with versioning support.
    
    Features:
    - Cell line biological parameters
    - Compound sensitivity data (IC50, Hill slope)
    - Parameter versioning and history
    - Easy migration from YAML
    - Query interface for simulations
    """
    
    def __init__(self, db_path: str = "data/simulation_params.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Cell line simulation parameters
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sim_cell_line_params (
                param_id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                coating_required BOOLEAN DEFAULT 0,
                version INTEGER DEFAULT 1,
                valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                valid_to TIMESTAMP,
                notes TEXT
            )
        """)
        
        # Compound sensitivity data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS compound_sensitivity (
                sensitivity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                compound_name TEXT NOT NULL,
                cell_line_id TEXT NOT NULL,
                ic50_um REAL NOT NULL,
                hill_slope REAL NOT NULL,
                confidence_interval_low REAL,
                confidence_interval_high REAL,
                source TEXT DEFAULT 'estimated',
                version INTEGER DEFAULT 1,
                valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            )
        """)
        
        # Default parameters
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS default_params (
                param_name TEXT PRIMARY KEY,
                param_value REAL NOT NULL,
                description TEXT
            )
        """)
        
        # Simulation runs (links simulations to parameter versions)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulation_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id TEXT NOT NULL,
                cell_line_id TEXT NOT NULL,
                param_version INTEGER NOT NULL,
                run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                results_path TEXT,
                metadata TEXT,
                FOREIGN KEY (param_version) REFERENCES sim_cell_line_params(param_id)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cell_line ON sim_cell_line_params(cell_line_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_version ON sim_cell_line_params(version)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_compound ON compound_sensitivity(compound_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_compound_cell ON compound_sensitivity(compound_name, cell_line_id)")
        
        conn.commit()
        conn.close()
    
    def add_cell_line_params(self, params: CellLineSimParams) -> int:
        """Add or update cell line simulation parameters."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Set valid_from if not provided
        if params.valid_from is None:
            params.valid_from = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO sim_cell_line_params (
                cell_line_id, doubling_time_h, max_confluence, max_passage,
                senescence_rate, seeding_efficiency, passage_stress,
                cell_count_cv, viability_cv, biological_cv, coating_required,
                version, valid_from, valid_to, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            params.cell_line_id, params.doubling_time_h, params.max_confluence,
            params.max_passage, params.senescence_rate, params.seeding_efficiency,
            params.passage_stress, params.cell_count_cv, params.viability_cv,
            params.biological_cv, params.coating_required, params.version,
            params.valid_from, params.valid_to, params.notes
        ))
        
        param_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return param_id
    
    def get_cell_line_params(self, cell_line_id: str, version: Optional[int] = None) -> Optional[CellLineSimParams]:
        """
        Get simulation parameters for a cell line.
        
        Args:
            cell_line_id: Cell line identifier
            version: Specific version (default: latest active version)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if version is not None:
            cursor.execute("""
                SELECT * FROM sim_cell_line_params
                WHERE cell_line_id = ? AND version = ?
            """, (cell_line_id, version))
        else:
            # Get latest active version
            cursor.execute("""
                SELECT * FROM sim_cell_line_params
                WHERE cell_line_id = ? AND valid_to IS NULL
                ORDER BY version DESC
                LIMIT 1
            """, (cell_line_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return CellLineSimParams(
                cell_line_id=row[1],
                doubling_time_h=row[2],
                max_confluence=row[3],
                max_passage=row[4],
                senescence_rate=row[5],
                seeding_efficiency=row[6],
                passage_stress=row[7],
                cell_count_cv=row[8],
                viability_cv=row[9],
                biological_cv=row[10],
                coating_required=bool(row[11]),
                version=row[12],
                valid_from=row[13],
                valid_to=row[14],
                notes=row[15]
            )
        return None
    
    def add_compound_sensitivity(self, sensitivity: CompoundSensitivity) -> int:
        """Add compound sensitivity data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if sensitivity.valid_from is None:
            sensitivity.valid_from = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO compound_sensitivity (
                compound_name, cell_line_id, ic50_um, hill_slope,
                confidence_interval_low, confidence_interval_high,
                source, version, valid_from, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sensitivity.compound_name, sensitivity.cell_line_id,
            sensitivity.ic50_um, sensitivity.hill_slope,
            sensitivity.confidence_interval_low, sensitivity.confidence_interval_high,
            sensitivity.source, sensitivity.version, sensitivity.valid_from,
            sensitivity.notes
        ))
        
        sensitivity_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return sensitivity_id
    
    def get_compound_sensitivity(
        self,
        compound_name: str,
        cell_line_id: str,
        version: Optional[int] = None
    ) -> Optional[CompoundSensitivity]:
        """Get compound sensitivity for a cell line."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if version is not None:
            cursor.execute("""
                SELECT * FROM compound_sensitivity
                WHERE compound_name = ? AND cell_line_id = ? AND version = ?
            """, (compound_name, cell_line_id, version))
        else:
            # Get latest version
            cursor.execute("""
                SELECT * FROM compound_sensitivity
                WHERE compound_name = ? AND cell_line_id = ?
                ORDER BY version DESC
                LIMIT 1
            """, (compound_name, cell_line_id))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return CompoundSensitivity(
                compound_name=row[1],
                cell_line_id=row[2],
                ic50_um=row[3],
                hill_slope=row[4],
                confidence_interval_low=row[5],
                confidence_interval_high=row[6],
                source=row[7],
                version=row[8],
                valid_from=row[9],
                notes=row[10]
            )
        return None
    
    def find_sensitive_compounds(self, cell_line_id: str, max_ic50: float) -> List[CompoundSensitivity]:
        """Find all compounds with IC50 below threshold for a cell line."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM compound_sensitivity
            WHERE cell_line_id = ? AND ic50_um <= ?
            ORDER BY ic50_um
        """, (cell_line_id, max_ic50))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            CompoundSensitivity(
                compound_name=row[1],
                cell_line_id=row[2],
                ic50_um=row[3],
                hill_slope=row[4],
                confidence_interval_low=row[5],
                confidence_interval_high=row[6],
                source=row[7],
                version=row[8],
                valid_from=row[9],
                notes=row[10]
            )
            for row in rows
        ]
    
    def set_default_param(self, param_name: str, param_value: float, description: str = ""):
        """Set a default parameter value."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO default_params (param_name, param_value, description)
            VALUES (?, ?, ?)
        """, (param_name, param_value, description))
        
        conn.commit()
        conn.close()
    
    def get_default_param(self, param_name: str) -> Optional[float]:
        """Get a default parameter value."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT param_value FROM default_params WHERE param_name = ?", (param_name,))
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else None
    
    def log_simulation_run(
        self,
        campaign_id: str,
        cell_line_id: str,
        param_version: int,
        results_path: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> int:
        """Log a simulation run with the parameter version used."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO simulation_runs (
                campaign_id, cell_line_id, param_version, results_path, metadata
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            campaign_id, cell_line_id, param_version, results_path,
            json.dumps(metadata) if metadata else None
        ))
        
        run_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return run_id
    
    def get_all_cell_lines(self) -> List[str]:
        """Get list of all cell lines with parameters."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT cell_line_id FROM sim_cell_line_params")
        rows = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in rows]
    
    def get_all_compounds(self) -> List[str]:
        """Get list of all compounds with sensitivity data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT compound_name FROM compound_sensitivity")
        rows = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in rows]
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export all data to dictionary (for backup or YAML export)."""
        result = {
            "cell_lines": {},
            "compound_sensitivity": {},
            "defaults": {}
        }
        
        # Export cell line params
        for cell_line_id in self.get_all_cell_lines():
            params = self.get_cell_line_params(cell_line_id)
            if params:
                result["cell_lines"][cell_line_id] = asdict(params)
        
        # Export compound sensitivity
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM compound_sensitivity")
        for row in cursor.fetchall():
            compound = row[1]
            if compound not in result["compound_sensitivity"]:
                result["compound_sensitivity"][compound] = {}
            
            result["compound_sensitivity"][compound][row[2]] = row[3]  # cell_line: ic50
        
        # Export defaults
        cursor.execute("SELECT * FROM default_params")
        for row in cursor.fetchall():
            result["defaults"][row[0]] = row[1]
        
        conn.close()
        
        return result
