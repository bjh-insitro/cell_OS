import sqlite3
import json
from typing import List, Dict, Any, Union, Tuple
from datetime import datetime

class ExperimentDB:
    """
    Manages the centralized SQLite database for all cell_OS experiment history and metadata.
    Establishes a schema to link Design, Batches (Physical Runs), and Results (Measurements).
    """
    
    def __init__(self, db_path: str = 'data/cell_os_experiments.db'):
        # Ensure the data directory exists before connecting
        import os
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_schema()
        print(f"✅ Connected to Experiment Database: {db_path}")

    def _create_schema(self):
        """
        Defines the tables required for linking campaign steps: 
        designs (The Plan) -> batches (The Run) -> results (The Data).
        """
        
        # 1. DESIGNS Table: High-level experiment and library metadata
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS designs (
                design_id TEXT PRIMARY KEY,       -- Unique ID for the experiment design (e.g., 'POSH_SCREEN_GOLGI')
                project_name TEXT NOT NULL,
                library_name TEXT,
                cell_line TEXT,
                target_moi REAL,                 -- Target MOI from design
                gRNA_count INTEGER,
                creation_date TEXT
            )
        """)
        
        # 2. BATCHES Table: Links the design to a physical execution (e.g., a plate)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS batches (
                batch_id INTEGER PRIMARY KEY,
                design_id TEXT,
                plate_barcode TEXT UNIQUE,       -- Unique identifier for the plate/physical run
                hardware_interface TEXT,         -- e.g., 'MockSimulator' or 'RealLab'
                run_date TEXT,
                FOREIGN KEY (design_id) REFERENCES designs (design_id)
            )
        """)

        # 3. RESULTS Table: Stores the actual quantitative measurements
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                result_id INTEGER PRIMARY KEY,
                batch_id INTEGER,
                measurement_type TEXT,           -- e.g., 'titration_moi', 'dino_embedding_dm', 'lv_transduction_eff'
                well_id TEXT,                    -- Can be NULL if result is plate-level (e.g., D_M)
                value REAL,                      -- Primary numerical value (e.g., MOI, D_M, or TE)
                data_path TEXT,                  -- Path to corresponding raw/processed data (e.g., /data/processed/embeddings.csv)
                metadata TEXT,                   -- JSON string for complex data/embeddings/full vectors
                FOREIGN KEY (batch_id) REFERENCES batches (batch_id)
            )
        """)
        
        # 4. AGENT_STATE Table: Stores the serialized state of agents for crash recovery
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_state (
                agent_id TEXT PRIMARY KEY,
                experiment_id TEXT,
                state_json TEXT,
                updated_at TEXT,
                FOREIGN KEY(experiment_id) REFERENCES designs(design_id)
            )
        """)
        
        # 5. EXPERIMENTS Table: Legacy table for backward compatibility with state_manager
        # Maps to designs table conceptually
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                name TEXT,
                created_at TEXT,
                status TEXT
            )
        """)
        
        # 6. TITRATION_RESULTS Table: Specialized table for LV titration data
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS titration_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT,
                cell_line TEXT,
                round_number INTEGER,
                volume_ul REAL,
                fraction_bfp REAL,
                cost_usd REAL,
                timestamp TEXT,
                FOREIGN KEY(experiment_id) REFERENCES experiments(experiment_id)
            )
        """)
        
        self.conn.commit()

    def insert_design(self, design_data: Dict[str, Any]) -> None:
        """Inserts a new experiment design record."""
        design_data['creation_date'] = datetime.now().isoformat()
        
        # We must explicitly list columns for safe insertion
        cols = ', '.join(design_data.keys())
        placeholders = ', '.join(['?'] * len(design_data))
        
        self.cursor.execute(f"INSERT OR REPLACE INTO designs ({cols}) VALUES ({placeholders})", 
                            list(design_data.values()))
        self.conn.commit()

    def insert_batch(self, batch_data: Dict[str, Any]) -> int:
        """Inserts a new batch record and returns the new batch_id."""
        batch_data['run_date'] = datetime.now().isoformat()
        cols = ', '.join(batch_data.keys())
        placeholders = ', '.join(['?'] * len(batch_data))
        
        self.cursor.execute(f"INSERT INTO batches ({cols}) VALUES ({placeholders})", 
                            list(batch_data.values()))
        self.conn.commit()
        return self.cursor.lastrowid

    def insert_result(self, batch_id: int, measurement_type: str, value: float, 
                      well_id: str = None, data_path: str = None, metadata: Union[Dict, List] = None) -> None:
        """Inserts a new quantitative result linked to a specific batch."""
        
        metadata_json = json.dumps(metadata) if metadata is not None else None
        
        self.cursor.execute("""
            INSERT INTO results (batch_id, measurement_type, value, well_id, data_path, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (batch_id, measurement_type, value, well_id, data_path, metadata_json))
        self.conn.commit()

    def query_phenotypic_hits(self, project_name: str, min_effect_size: float = 2.0) -> List[Tuple]:
        """
        Example Query: Finds all POSH runs with a strong phenotypic shift (D_M > threshold).
        """
        self.cursor.execute("""
            SELECT 
                T1.design_id,
                T2.plate_barcode,
                T3.value AS D_M_Effect_Size
            FROM designs T1
            JOIN batches T2 ON T1.design_id = T2.design_id
            JOIN results T3 ON T2.batch_id = T3.batch_id
            WHERE 
                T1.project_name = ? AND
                T3.measurement_type = 'dino_embedding_dm' AND 
                T3.value >= ?
        """, (project_name, min_effect_size))
        return self.cursor.fetchall()
    
    # --- Agent State Management (for crash recovery) ---
    
    def save_experiment(self, experiment_id: str, name: str):
        """Save an experiment record (for backward compatibility)."""
        self.cursor.execute(
            "INSERT OR IGNORE INTO experiments (experiment_id, name, created_at, status) VALUES (?, ?, ?, ?)",
            (experiment_id, name, datetime.now().isoformat(), "ACTIVE")
        )
        self.conn.commit()
    
    def save_agent_state(self, agent_id: str, experiment_id: str, state: Dict[str, Any]):
        """Save agent state for crash recovery."""
        state_json = json.dumps(state)
        self.cursor.execute(
            """
            INSERT INTO agent_state (agent_id, experiment_id, state_json, updated_at) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET 
                state_json=excluded.state_json,
                updated_at=excluded.updated_at
            """,
            (agent_id, experiment_id, state_json, datetime.now().isoformat())
        )
        self.conn.commit()
    
    def load_agent_state(self, agent_id: str) -> Union[Dict[str, Any], None]:
        """Load agent state from DB."""
        self.cursor.execute("SELECT state_json FROM agent_state WHERE agent_id = ?", (agent_id,))
        self.cursor.row_factory = sqlite3.Row
        row = self.cursor.fetchone()
        
        if row:
            return json.loads(row[0])  # row[0] is state_json
        return None
    
    def log_titration_data(self, experiment_id: str, cell_line: str, round_num: int, vol: float, bfp: float, cost: float):
        """Log titration result (specialized for AutonomousTitrationAgent)."""
        self.cursor.execute(
            """
            INSERT INTO titration_results (experiment_id, cell_line, round_number, volume_ul, fraction_bfp, cost_usd, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (experiment_id, cell_line, round_num, vol, bfp, cost, datetime.now().isoformat())
        )
        self.conn.commit()
        
    def close(self):
        self.conn.close()