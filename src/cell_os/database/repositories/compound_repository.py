"""
Compound Repository

Provides access to compound and IC50 data from the database.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict


@dataclass
class Compound:
    """Compound metadata"""
    compound_id: str
    common_name: str
    cas_number: Optional[str]
    pubchem_cid: Optional[int]
    molecular_weight: Optional[float]
    mechanism: Optional[str]
    target: Optional[str]
    compound_class: Optional[str]
    notes: Optional[str]


@dataclass
class CompoundIC50:
    """IC50 value for a compound in a specific cell line"""
    compound_id: str
    cell_line_id: str
    ic50_uM: float
    ic50_range_min_uM: Optional[float]
    ic50_range_max_uM: Optional[float]
    hill_slope: float
    assay_type: Optional[str]
    assay_duration_h: Optional[int]
    source: str
    reference_url: Optional[str]
    pubmed_id: Optional[str]
    notes: Optional[str]
    date_verified: str

    @property
    def is_verified(self) -> bool:
        """Check if this IC50 value has PubMed verification"""
        return self.pubmed_id is not None and self.pubmed_id != ''

    @property
    def is_estimated(self) -> bool:
        """Check if this is an estimated value"""
        return 'Estimated' in self.source or 'YAML' in self.source


class CompoundRepository:
    """Repository for accessing compound and IC50 data"""

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

    def get_compound(self, compound_id: str) -> Optional[Compound]:
        """Get compound metadata by ID"""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM compounds
            WHERE compound_id = ?
            """,
            (compound_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return Compound(
            compound_id=row['compound_id'],
            common_name=row['common_name'],
            cas_number=row['cas_number'],
            pubchem_cid=row['pubchem_cid'],
            molecular_weight=row['molecular_weight'],
            mechanism=row['mechanism'],
            target=row['target'],
            compound_class=row['compound_class'],
            notes=row['notes']
        )

    def get_all_compounds(self) -> List[Compound]:
        """Get all compounds"""
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM compounds ORDER BY common_name")
        rows = cursor.fetchall()
        conn.close()

        return [
            Compound(
                compound_id=row['compound_id'],
                common_name=row['common_name'],
                cas_number=row['cas_number'],
                pubchem_cid=row['pubchem_cid'],
                molecular_weight=row['molecular_weight'],
                mechanism=row['mechanism'],
                target=row['target'],
                compound_class=row['compound_class'],
                notes=row['notes']
            )
            for row in rows
        ]

    def get_ic50(self, compound_id: str, cell_line_id: str) -> Optional[CompoundIC50]:
        """Get IC50 value for a compound in a specific cell line"""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM compound_ic50
            WHERE compound_id = ? AND cell_line_id = ?
            """,
            (compound_id, cell_line_id)
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return CompoundIC50(
            compound_id=row['compound_id'],
            cell_line_id=row['cell_line_id'],
            ic50_uM=row['ic50_uM'],
            ic50_range_min_uM=row['ic50_range_min_uM'],
            ic50_range_max_uM=row['ic50_range_max_uM'],
            hill_slope=row['hill_slope'],
            assay_type=row['assay_type'],
            assay_duration_h=row['assay_duration_h'],
            source=row['source'],
            reference_url=row['reference_url'],
            pubmed_id=row['pubmed_id'],
            notes=row['notes'],
            date_verified=row['date_verified']
        )

    def get_all_ic50s_for_compound(self, compound_id: str) -> List[CompoundIC50]:
        """Get all IC50 values for a compound across cell lines"""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM compound_ic50
            WHERE compound_id = ?
            ORDER BY cell_line_id
            """,
            (compound_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            CompoundIC50(
                compound_id=row['compound_id'],
                cell_line_id=row['cell_line_id'],
                ic50_uM=row['ic50_uM'],
                ic50_range_min_uM=row['ic50_range_min_uM'],
                ic50_range_max_uM=row['ic50_range_max_uM'],
                hill_slope=row['hill_slope'],
                assay_type=row['assay_type'],
                assay_duration_h=row['assay_duration_h'],
                source=row['source'],
                reference_url=row['reference_url'],
                pubmed_id=row['pubmed_id'],
                notes=row['notes'],
                date_verified=row['date_verified']
            )
            for row in rows
        ]

    def get_all_ic50s_for_cell_line(self, cell_line_id: str) -> List[CompoundIC50]:
        """Get all IC50 values for a cell line across compounds"""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM compound_ic50
            WHERE cell_line_id = ?
            ORDER BY compound_id
            """,
            (cell_line_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            CompoundIC50(
                compound_id=row['compound_id'],
                cell_line_id=row['cell_line_id'],
                ic50_uM=row['ic50_uM'],
                ic50_range_min_uM=row['ic50_range_min_uM'],
                ic50_range_max_uM=row['ic50_range_max_uM'],
                hill_slope=row['hill_slope'],
                assay_type=row['assay_type'],
                assay_duration_h=row['assay_duration_h'],
                source=row['source'],
                reference_url=row['reference_url'],
                pubmed_id=row['pubmed_id'],
                notes=row['notes'],
                date_verified=row['date_verified']
            )
            for row in rows
        ]

    def get_compound_summary(self) -> Dict[str, Dict]:
        """Get summary statistics for all compounds"""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT
                c.compound_id,
                c.common_name,
                c.mechanism,
                COUNT(ic50.cell_line_id) as num_cell_lines,
                AVG(ic50.ic50_uM) as avg_ic50_uM,
                MIN(ic50.ic50_uM) as min_ic50_uM,
                MAX(ic50.ic50_uM) as max_ic50_uM
            FROM compounds c
            LEFT JOIN compound_ic50 ic50 ON c.compound_id = ic50.compound_id
            GROUP BY c.compound_id
            ORDER BY c.common_name
            """
        )
        rows = cursor.fetchall()
        conn.close()

        return {
            row['compound_id']: {
                'common_name': row['common_name'],
                'mechanism': row['mechanism'],
                'num_cell_lines': row['num_cell_lines'],
                'avg_ic50_uM': row['avg_ic50_uM'],
                'min_ic50_uM': row['min_ic50_uM'],
                'max_ic50_uM': row['max_ic50_uM']
            }
            for row in rows
        }


# Convenience function for backward compatibility with existing code
def get_compound_ic50(compound_id: str, cell_line_id: str, db_path: Optional[str] = None) -> Optional[float]:
    """
    Get IC50 value (in µM) for a compound in a specific cell line.

    Args:
        compound_id: Compound identifier
        cell_line_id: Cell line identifier
        db_path: Optional path to database (defaults to standard location)

    Returns:
        IC50 value in µM, or None if not found
    """
    repo = CompoundRepository(db_path)
    ic50 = repo.get_ic50(compound_id, cell_line_id)
    return ic50.ic50_uM if ic50 else None


def get_compound_hill_slope(compound_id: str, cell_line_id: str, db_path: Optional[str] = None) -> float:
    """
    Get Hill slope for a compound in a specific cell line.

    Args:
        compound_id: Compound identifier
        cell_line_id: Cell line identifier
        db_path: Optional path to database

    Returns:
        Hill slope value (defaults to 1.0 if not found)
    """
    repo = CompoundRepository(db_path)
    ic50 = repo.get_ic50(compound_id, cell_line_id)
    return ic50.hill_slope if ic50 else 1.0
