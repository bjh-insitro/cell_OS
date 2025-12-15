"""
Cell Thalamus Database Module

Handles storage and retrieval of Cell Thalamus experimental data:
- Experimental designs (Phase 0-3)
- Morphology results (5-channel Cell Painting)
- ATP viability results (scalar anchor)
- Metadata (plate, day, operator, sentinel flags)
"""

import sqlite3
import logging
import json
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class CellThalamusDB:
    """Database for Cell Thalamus experimental results."""

    def __init__(self, db_path: str = "data/cell_thalamus_results.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row  # Return dict-like rows
        self._create_schema()
        logger.info(f"Connected to Cell Thalamus DB: {db_path}")

    def _create_schema(self):
        """Create database schema for Cell Thalamus."""
        cursor = self.conn.cursor()

        # Designs table - stores experimental design metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS thalamus_designs (
                design_id TEXT PRIMARY KEY,
                phase INTEGER NOT NULL,
                cell_lines TEXT,
                compounds TEXT,
                doses TEXT,
                timepoints TEXT,
                created_at TEXT,
                metadata TEXT
            )
        """)

        # Results table - stores all experimental measurements
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS thalamus_results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                design_id TEXT NOT NULL,
                well_id TEXT NOT NULL,
                cell_line TEXT NOT NULL,
                compound TEXT NOT NULL,
                dose_uM REAL NOT NULL,
                timepoint_h REAL NOT NULL,
                plate_id TEXT NOT NULL,
                day INTEGER NOT NULL,
                operator TEXT NOT NULL,
                is_sentinel BOOLEAN DEFAULT 0,

                -- Morphology (5 channels from Cell Painting)
                morph_er REAL,
                morph_mito REAL,
                morph_nucleus REAL,
                morph_actin REAL,
                morph_rna REAL,

                -- Scalar anchor (ATP viability)
                atp_signal REAL,

                -- Optional: genotype for Phase 1+
                genotype TEXT DEFAULT 'WT',

                timestamp TEXT,

                FOREIGN KEY (design_id) REFERENCES thalamus_designs (design_id)
            )
        """)

        # Create indices for fast queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_design
            ON thalamus_results(design_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_compound
            ON thalamus_results(compound, cell_line)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_sentinel
            ON thalamus_results(is_sentinel, compound)
        """)

        self.conn.commit()
        logger.info("Cell Thalamus schema created")

    def save_design(self, design_id: str, phase: int, cell_lines: List[str],
                   compounds: List[str], doses: List[float], timepoints: List[float],
                   metadata: Optional[Dict] = None):
        """Save an experimental design."""
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO thalamus_designs
            (design_id, phase, cell_lines, compounds, doses, timepoints, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            design_id,
            phase,
            json.dumps(cell_lines),
            json.dumps(compounds),
            json.dumps(doses),
            json.dumps(timepoints),
            datetime.now().isoformat(),
            json.dumps(metadata) if metadata else None
        ))

        self.conn.commit()
        logger.info(f"Saved design {design_id} (Phase {phase})")

    def insert_result(self, design_id: str, well_id: str, cell_line: str,
                     compound: str, dose_uM: float, timepoint_h: float,
                     plate_id: str, day: int, operator: str,
                     morphology: Dict[str, float], atp_signal: float,
                     is_sentinel: bool = False, genotype: str = 'WT'):
        """Insert a single experimental result."""
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO thalamus_results
            (design_id, well_id, cell_line, compound, dose_uM, timepoint_h,
             plate_id, day, operator, is_sentinel,
             morph_er, morph_mito, morph_nucleus, morph_actin, morph_rna,
             atp_signal, genotype, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            design_id, well_id, cell_line, compound, dose_uM, timepoint_h,
            plate_id, day, operator, is_sentinel,
            morphology['er'], morphology['mito'], morphology['nucleus'],
            morphology['actin'], morphology['rna'],
            atp_signal, genotype,
            datetime.now().isoformat()
        ))

        self.conn.commit()

    def insert_results_batch(self, results: List[Dict[str, Any]]):
        """
        Insert multiple experimental results in a single transaction.

        Args:
            results: List of result dicts with keys:
                design_id, well_id, cell_line, compound, dose_uM, timepoint_h,
                plate_id, day, operator, is_sentinel, morphology (dict),
                atp_signal, genotype (optional)
        """
        if not results:
            return

        cursor = self.conn.cursor()
        timestamp = datetime.now().isoformat()

        # Prepare data tuples
        data = []
        for result in results:
            morphology = result['morphology']
            genotype = result.get('genotype', 'WT')

            data.append((
                result['design_id'],
                result['well_id'],
                result['cell_line'],
                result['compound'],
                result['dose_uM'],
                result['timepoint_h'],
                result['plate_id'],
                result['day'],
                result['operator'],
                result['is_sentinel'],
                morphology['er'],
                morphology['mito'],
                morphology['nucleus'],
                morphology['actin'],
                morphology['rna'],
                result['atp_signal'],
                genotype,
                timestamp
            ))

        # Batch insert
        cursor.executemany("""
            INSERT INTO thalamus_results
            (design_id, well_id, cell_line, compound, dose_uM, timepoint_h,
             plate_id, day, operator, is_sentinel,
             morph_er, morph_mito, morph_nucleus, morph_actin, morph_rna,
             atp_signal, genotype, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)

        self.conn.commit()
        logger.info(f"Batch inserted {len(results)} results")

    def get_results(self, design_id: str, filters: Optional[Dict] = None) -> List[Dict]:
        """
        Retrieve results for a design with optional filters.

        Args:
            design_id: Design ID to query
            filters: Optional dict with keys: cell_line, compound, is_sentinel, etc.

        Returns:
            List of result dicts
        """
        cursor = self.conn.cursor()

        query = "SELECT * FROM thalamus_results WHERE design_id = ?"
        params = [design_id]

        if filters:
            for key, value in filters.items():
                query += f" AND {key} = ?"
                params.append(value)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_sentinel_data(self, design_id: str) -> List[Dict]:
        """Get all sentinel well data for SPC analysis."""
        return self.get_results(design_id, filters={'is_sentinel': True})

    def get_morphology_matrix(self, design_id: str) -> Tuple[List[List[float]], List[str]]:
        """
        Get morphology data as a matrix for dimensionality reduction.

        Returns:
            (matrix, well_ids) where matrix is N x 5 (5 channels)
        """
        results = self.get_results(design_id)

        matrix = []
        well_ids = []

        for row in results:
            features = [
                row['morph_er'],
                row['morph_mito'],
                row['morph_nucleus'],
                row['morph_actin'],
                row['morph_rna']
            ]
            matrix.append(features)
            well_ids.append(row['well_id'])

        return matrix, well_ids

    def get_designs(self, phase: Optional[int] = None) -> List[Dict]:
        """Get all designs, optionally filtered by phase, ordered by most recent first."""
        cursor = self.conn.cursor()

        if phase is not None:
            cursor.execute("SELECT * FROM thalamus_designs WHERE phase = ? ORDER BY created_at DESC", (phase,))
        else:
            cursor.execute("SELECT * FROM thalamus_designs ORDER BY created_at DESC")

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_dose_response_data(self, design_id: str, compound: str,
                               cell_line: str, metric: str = 'atp_signal') -> List[Tuple[float, float, float, int]]:
        """
        Get dose-response data for a specific compound and cell line.

        Args:
            design_id: Design ID
            compound: Compound name
            cell_line: Cell line name
            metric: Metric to plot ('atp_signal', 'viability_pct', or channel name like 'morph_er')

        Returns:
            List of (dose, mean, std, n) tuples aggregated across replicates
        """
        cursor = self.conn.cursor()

        # Map morphology channel names to column names
        morph_map = {
            'er': 'morph_er',
            'mito': 'morph_mito',
            'nucleus': 'morph_nucleus',
            'actin': 'morph_actin',
            'rna': 'morph_rna'
        }

        # Handle normalized viability percentage
        if metric == 'viability_pct':
            # Get DMSO control mean for this cell line
            cursor.execute("""
                SELECT AVG(atp_signal)
                FROM thalamus_results
                WHERE design_id = ? AND compound = 'DMSO' AND cell_line = ?
            """, (design_id, cell_line))
            dmso_mean = cursor.fetchone()[0]

            if not dmso_mean or dmso_mean == 0:
                return []  # Can't normalize without DMSO control

            # Get compound data and normalize
            cursor.execute("""
                SELECT dose_uM, (atp_signal / ?) * 100 as viability_pct
                FROM thalamus_results
                WHERE design_id = ? AND compound = ? AND cell_line = ? AND is_sentinel = 0
                ORDER BY dose_uM
            """, (dmso_mean, design_id, compound, cell_line))
            rows = cursor.fetchall()

            # Aggregate by dose: compute mean, std, n
            from collections import defaultdict
            import math

            dose_groups = defaultdict(list)
            for dose, value in rows:
                dose_groups[dose].append(value)

            result = []
            for dose in sorted(dose_groups.keys()):
                values = dose_groups[dose]
                n = len(values)
                mean = sum(values) / n if n > 0 else 0

                if n > 1:
                    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
                    std = math.sqrt(variance)
                else:
                    std = 0.0

                result.append((dose, mean, std, n))

            return result

        # Handle regular metrics
        column = morph_map.get(metric, metric)

        query = f"""
            SELECT dose_uM, {column}
            FROM thalamus_results
            WHERE design_id = ? AND compound = ? AND cell_line = ? AND is_sentinel = 0
            ORDER BY dose_uM
        """

        cursor.execute(query, (design_id, compound, cell_line))
        rows = cursor.fetchall()

        # Aggregate by dose: compute mean, std, n
        from collections import defaultdict
        import math

        dose_groups = defaultdict(list)
        for dose, value in rows:
            if value is not None:  # Skip NULL values
                dose_groups[dose].append(value)

        result = []
        for dose in sorted(dose_groups.keys()):
            values = dose_groups[dose]
            n = len(values)
            mean = sum(values) / n if n > 0 else 0

            if n > 1:
                variance = sum((x - mean) ** 2 for x in values) / (n - 1)
                std = math.sqrt(variance)
            else:
                std = 0.0

            result.append((dose, mean, std, n))

        return result

    def close(self):
        """Close database connection."""
        self.conn.close()
        logger.info("Closed Cell Thalamus DB")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
