"""
Simulation Parameters Repository

Provides access to cell line and compound parameters for the BiologicalVirtualMachine.
This replaces YAML-based parameter loading with database queries.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict


@dataclass
class CellLineParams:
    """Cell line parameters for simulation"""
    cell_line_id: str
    doubling_time_h: float
    max_confluence: float
    max_passage: Optional[int]
    senescence_rate: Optional[float]
    seeding_efficiency: float
    passage_stress: float
    lag_duration_h: float
    edge_penalty: float
    cell_count_cv: Optional[float]
    viability_cv: Optional[float]
    biological_cv: Optional[float]
    coating_required: bool


@dataclass
class CompoundSensitivity:
    """Compound sensitivity (IC50) for a specific cell line"""
    compound_id: str
    cell_line_id: str
    ic50_um: float
    hill_slope: float


class SimulationParamsRepository:
    """Repository for accessing simulation parameters from database"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Default to the standard database location
            db_path = Path(__file__).parents[4] / "data" / "cell_lines.db"
        self.db_path = str(db_path)

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_all_cell_lines(self) -> List[str]:
        """Get list of all cell line IDs"""
        conn = self._get_connection()
        cursor = conn.execute("SELECT cell_line_id FROM cell_line_growth_parameters ORDER BY cell_line_id")
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def get_cell_line_params(self, cell_line_id: str) -> Optional[CellLineParams]:
        """Get all parameters for a cell line"""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT
                cell_line_id,
                doubling_time_h,
                max_confluence,
                max_passage,
                senescence_rate,
                seeding_efficiency,
                passage_stress,
                lag_duration_h,
                edge_penalty,
                cell_count_cv,
                viability_cv,
                biological_cv,
                coating_required
            FROM cell_line_growth_parameters
            WHERE cell_line_id = ?
            """,
            (cell_line_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return CellLineParams(
            cell_line_id=row['cell_line_id'],
            doubling_time_h=row['doubling_time_h'],
            max_confluence=row['max_confluence'],
            max_passage=row['max_passage'],
            senescence_rate=row['senescence_rate'],
            seeding_efficiency=row['seeding_efficiency'],
            passage_stress=row['passage_stress'],
            lag_duration_h=row['lag_duration_h'],
            edge_penalty=row['edge_penalty'],
            cell_count_cv=row['cell_count_cv'],
            viability_cv=row['viability_cv'],
            biological_cv=row['biological_cv'],
            coating_required=bool(row['coating_required'])
        )

    def get_all_compounds(self) -> List[str]:
        """Get list of all compound IDs"""
        conn = self._get_connection()
        cursor = conn.execute("SELECT DISTINCT compound_id FROM compounds ORDER BY compound_id")
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def get_compound_sensitivity(self, compound_id: str, cell_line_id: str) -> Optional[CompoundSensitivity]:
        """Get compound IC50 and Hill slope for a specific cell line"""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT
                compound_id,
                cell_line_id,
                ic50_uM,
                hill_slope
            FROM compound_ic50
            WHERE compound_id = ? AND cell_line_id = ?
            """,
            (compound_id, cell_line_id)
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return CompoundSensitivity(
            compound_id=row['compound_id'],
            cell_line_id=row['cell_line_id'],
            ic50_um=row['ic50_uM'],
            hill_slope=row['hill_slope']
        )

    def get_default_param(self, param_name: str) -> Optional[float]:
        """
        Get default parameter value.

        For now, returns hardcoded defaults that match the YAML defaults section.
        In the future, could store these in a defaults table.
        """
        defaults = {
            'doubling_time_h': 24.0,
            'max_confluence': 0.9,
            'max_passage': 30,
            'senescence_rate': 0.01,
            'seeding_efficiency': 0.85,
            'passage_stress': 0.02,
            'cell_count_cv': 0.10,
            'viability_cv': 0.02,
            'biological_cv': 0.05,
            'lag_duration_h': 12.0,
            'edge_penalty': 0.15,
            'default_ic50': 40.0,
            'default_hill_slope': 1.5
        }
        return defaults.get(param_name)

    def get_all_ic50s_for_compound(self, compound_id: str) -> List[CompoundSensitivity]:
        """Get all IC50 values for a compound across cell lines"""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT
                compound_id,
                cell_line_id,
                ic50_uM,
                hill_slope
            FROM compound_ic50
            WHERE compound_id = ?
            ORDER BY cell_line_id
            """,
            (compound_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            CompoundSensitivity(
                compound_id=row['compound_id'],
                cell_line_id=row['cell_line_id'],
                ic50_um=row['ic50_uM'],
                hill_slope=row['hill_slope']
            )
            for row in rows
        ]

    def get_cell_line_by_alias(self, alias: str) -> Optional[str]:
        """
        Map common aliases to canonical cell line IDs.

        For example: HEK293T -> HEK293, iPSC_NGN2 -> iPSC_NGN2
        """
        alias_map = {
            'HEK293T': 'HEK293',  # HEK293T is a variant, use HEK293 params
            'HEK-293': 'HEK293',
            'HEK_293': 'HEK293',
            'IPSC': 'iPSC',  # Case insensitive
            'CHO-K1': 'CHO',
            'Jurkat-E6.1': 'Jurkat'
        }

        canonical = alias_map.get(alias)
        if canonical:
            return canonical

        # Check if the alias itself exists in database
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT cell_line_id FROM cell_line_growth_parameters WHERE cell_line_id = ?",
            (alias,)
        )
        row = cursor.fetchone()
        conn.close()

        return row[0] if row else None
