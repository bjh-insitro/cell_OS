"""
Experimental results repository for database operations.
"""
import pandas as pd
from typing import Dict, List, Optional, Any
from ..base import BaseRepository


class ExperimentalRepository(BaseRepository):
    """Repository for experimental results and measurements."""
    
    def __init__(self, db_path: str = "data/experimental_results.db"):
        super().__init__(db_path)
    
    def _init_schema(self):
        """Initialize database schema."""
        conn = self._get_connection()
        try:
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
        finally:
            conn.close()
    
    def add_measurements(self, df: pd.DataFrame):
        """Add a batch of measurements from a DataFrame."""
        conn = self._get_connection()
        try:
            # Expected columns
            expected_cols = [
                "plate_id", "well_id", "cell_line", "compound", "dose_uM", 
                "time_h", "raw_signal", "is_control", "date", 
                "incubator_id", "liquid_handler_id", "viability_norm"
            ]
            
            # Filter to available columns
            cols_to_use = [c for c in expected_cols if c in df.columns]
            
            df[cols_to_use].to_sql("measurements", conn, if_exists="append", index=False)
        finally:
            conn.close()
    
    def get_measurements(self, cell_line: Optional[str] = None, 
                        compound: Optional[str] = None,
                        plate_id: Optional[str] = None) -> pd.DataFrame:
        """Retrieve measurements with optional filtering."""
        conn = self._get_connection()
        try:
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
            return df
        finally:
            conn.close()
    
    def get_dose_response(self, cell_line: str, compound: str) -> pd.DataFrame:
        """Get dose-response data for a specific cell line and compound."""
        return self.get_measurements(cell_line=cell_line, compound=compound)
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics of the database."""
        stats = {}
        
        # Total measurements
        result = self._fetch_one("SELECT COUNT(*) as count FROM measurements")
        stats["total_measurements"] = result['count'] if result else 0
        
        # Cell lines
        rows = self._fetch_all("SELECT DISTINCT cell_line FROM measurements")
        stats["cell_lines"] = [row['cell_line'] for row in rows]
        
        # Compounds
        rows = self._fetch_all("SELECT DISTINCT compound FROM measurements WHERE compound IS NOT NULL")
        stats["compounds"] = [row['compound'] for row in rows]
        
        # Plates
        result = self._fetch_one("SELECT COUNT(DISTINCT plate_id) as count FROM measurements")
        stats["plates"] = result['count'] if result else 0
        
        return stats
