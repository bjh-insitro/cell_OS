"""
Experimental Results Database Interface.

Handles storage and retrieval of experimental data (e.g. plate reader measurements).
"""

import sqlite3
import pandas as pd
import warnings

warnings.warn(
    "cell_os.experimental_db is deprecated and will be removed. "
    "Use cell_os.database.repositories.experimental instead.",
    DeprecationWarning,
    stacklevel=2
)
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from datetime import datetime

class ExperimentalDatabase:
    """
    Interface for the Experimental Results Database.
    Stores raw and normalized assay measurements.
    """
    
    def __init__(self, db_path: str = "data/experimental_results.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Measurements table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_id TEXT NOT NULL,
                well_id TEXT NOT NULL,
                cell_line TEXT NOT NULL,
                compound TEXT,
                dose_uM REAL,
                time_h REAL,
                raw_signal REAL,
                is_control INTEGER,
                date TEXT,
                incubator_id TEXT,
                liquid_handler_id TEXT,
                viability_norm REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indices for common queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_exp_cell_line ON measurements(cell_line)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_exp_compound ON measurements(compound)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_exp_plate ON measurements(plate_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_exp_date ON measurements(date)")
        
        conn.commit()
        conn.close()
        
    def add_measurements(self, df: pd.DataFrame):
        """
        Add a batch of measurements from a DataFrame.
        Expected columns match the table schema (except id and created_at).
        """
        conn = sqlite3.connect(self.db_path)
        
        # Ensure columns match
        expected_cols = [
            "plate_id", "well_id", "cell_line", "compound", "dose_uM", 
            "time_h", "raw_signal", "is_control", "date", 
            "incubator_id", "liquid_handler_id", "viability_norm"
        ]
        
        # Filter to available columns
        cols_to_use = [c for c in expected_cols if c in df.columns]
        
        df[cols_to_use].to_sql("measurements", conn, if_exists="append", index=False)
        conn.close()
        
    def get_measurements(self, 
                        cell_line: Optional[str] = None, 
                        compound: Optional[str] = None,
                        plate_id: Optional[str] = None) -> pd.DataFrame:
        """
        Retrieve measurements with optional filtering.
        Returns a pandas DataFrame.
        """
        conn = sqlite3.connect(self.db_path)
        
        query = "SELECT * FROM measurements WHERE 1=1"
        params = []
        
        if cell_line:
            query += " AND cell_line = ?"
            params.append(cell_line)
            
        if compound:
            query += " AND compound = ?"
            params.append(compound)
            
        if plate_id:
            query += " AND plate_id = ?"
            params.append(plate_id)
            
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    
    def get_dose_response(self, cell_line: str, compound: str) -> pd.DataFrame:
        """
        Get dose-response data for a specific cell line and compound.
        """
        return self.get_measurements(cell_line=cell_line, compound=compound)
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics of the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        stats["total_measurements"] = cursor.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
        stats["cell_lines"] = [r[0] for r in cursor.execute("SELECT DISTINCT cell_line FROM measurements").fetchall()]
        stats["compounds"] = [r[0] for r in cursor.execute("SELECT DISTINCT compound FROM measurements WHERE compound IS NOT NULL").fetchall()]
        stats["plates"] = cursor.execute("SELECT COUNT(DISTINCT plate_id) FROM measurements").fetchone()[0]
        
        conn.close()
        return stats
