import sqlite3
import json
import logging
import os
from typing import List, Dict, Any, Union, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseInitializer:
    """Responsible for creating connections and ensuring schema readiness."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        self._create_schema(conn)
        return conn

    def _create_schema(self, conn: sqlite3.Connection):
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS designs (
                design_id TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                library_name TEXT,
                cell_line TEXT,
                target_moi REAL,
                gRNA_count INTEGER,
                creation_date TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS batches (
                batch_id INTEGER PRIMARY KEY,
                design_id TEXT,
                plate_barcode TEXT UNIQUE,
                hardware_interface TEXT,
                run_date TEXT,
                FOREIGN KEY (design_id) REFERENCES designs (design_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                result_id INTEGER PRIMARY KEY,
                batch_id INTEGER,
                measurement_type TEXT,
                well_id TEXT,
                value REAL,
                data_path TEXT,
                metadata TEXT,
                FOREIGN KEY (batch_id) REFERENCES batches (batch_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_state (
                agent_id TEXT PRIMARY KEY,
                experiment_id TEXT,
                state_json TEXT,
                updated_at TEXT,
                FOREIGN KEY(experiment_id) REFERENCES designs(design_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                name TEXT,
                created_at TEXT,
                status TEXT
            )
        """)

        cursor.execute("""
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dino_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT,
                batch_id INTEGER,
                gene TEXT,
                guide_id TEXT,
                d_m REAL,
                z_score REAL,
                is_hit BOOLEAN,
                embedding_dim INTEGER,
                timestamp TEXT,
                FOREIGN KEY(experiment_id) REFERENCES experiments(experiment_id),
                FOREIGN KEY(batch_id) REFERENCES batches(batch_id)
            )
        """)

        conn.commit()


class ExperimentRepository:
    """Pure data-access layer for experiment records."""

    def __init__(self, connection: sqlite3.Connection):
        self.conn = connection
        self.cursor = self.conn.cursor()

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
    
    def save_dino_results(self, experiment_id: str, hits_df, batch_id: int = None):
        """Save DINO embedding analysis results (D_M, z-scores, hits) to database."""
        for _, row in hits_df.iterrows():
            self.cursor.execute(
                """
                INSERT INTO dino_embeddings 
                (experiment_id, batch_id, gene, guide_id, d_m, z_score, is_hit, embedding_dim, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    batch_id,
                    row['gene'],
                    row.get('guide_id', 'aggregate'),
                    row['d_m'],
                    row['z_score'],
                    bool(row['hit_status']),
                    None,  # embedding_dim can be added if needed
                    datetime.now().isoformat()
                )
            )
        self.conn.commit()
        
    def query_dino_hits(self, experiment_id: str = None, min_z_score: float = 2.0):
        """Query DINO hits from database."""
        if experiment_id:
            self.cursor.execute(
                """
                SELECT gene, d_m, z_score, is_hit, timestamp
                FROM dino_embeddings
                WHERE experiment_id = ? AND z_score >= ?
                ORDER BY z_score DESC
                """,
                (experiment_id, min_z_score)
            )
        else:
            self.cursor.execute(
                """
                SELECT experiment_id, gene, d_m, z_score, is_hit, timestamp
                FROM dino_embeddings
                WHERE z_score >= ?
                ORDER BY z_score DESC
                """,
                (min_z_score,)
            )
        return self.cursor.fetchall()
        
    def close(self):
        self.conn.close()


class ExperimentDB(ExperimentRepository):
    """
    Manages the centralized SQLite database for cell_OS using a dedicated initializer.
    """

    def __init__(
        self,
        db_path: str = "data/cell_os_experiments.db",
        initializer: Optional[DatabaseInitializer] = None,
    ):
        self.db_path = db_path
        self.initializer = initializer or DatabaseInitializer(db_path)
        connection = self.initializer.connect()
        super().__init__(connection)
        logger.info("Connected to Experiment Database: %s", db_path)
