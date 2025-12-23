"""
Seeding Density Repository

Provides access to vessel types and cell-line-specific seeding densities from the database.

This is the SINGLE SOURCE OF TRUTH for seeding densities across the entire system.
"""

import sqlite3
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VesselType:
    """Physical properties of a culture vessel."""
    vessel_type_id: str
    display_name: str
    category: str  # 'plate', 'flask', 'dish', 'bioreactor'
    surface_area_cm2: float
    working_volume_ml: float
    max_volume_ml: float
    well_count: Optional[int]  # None for flasks (single compartment)
    max_capacity_cells_per_well: float
    description: Optional[str]


@dataclass
class SeedingDensity:
    """Cell-line-specific seeding parameters for a vessel type."""
    cell_line_id: str
    vessel_type_id: str
    nominal_cells_per_well: int
    low_multiplier: float
    high_multiplier: float
    notes: Optional[str]

    def get_cells(self, density_level: str = "NOMINAL") -> int:
        """
        Get cell count for a specific density level.

        Args:
            density_level: One of "LOW", "NOMINAL", "HIGH"

        Returns:
            Number of cells to seed
        """
        multipliers = {
            "LOW": self.low_multiplier,
            "NOMINAL": 1.0,
            "HIGH": self.high_multiplier,
            "NONE": 0
        }
        multiplier = multipliers.get(density_level, 1.0)
        return int(self.nominal_cells_per_well * multiplier)


class SeedingDensityRepository:
    """Repository for accessing seeding density data from the database."""

    def __init__(self, db_path: str = "data/cell_lines.db"):
        """
        Initialize repository.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

    def _connect(self) -> sqlite3.Connection:
        """Create database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_vessel_type(self, vessel_type_id: str) -> Optional[VesselType]:
        """
        Get vessel type by ID.

        Args:
            vessel_type_id: Vessel type identifier (e.g., "384-well", "T75")

        Returns:
            VesselType object or None if not found
        """
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT vessel_type_id, display_name, category,
                       surface_area_cm2, working_volume_ml, max_volume_ml,
                       well_count, max_capacity_cells_per_well, description
                FROM vessel_types
                WHERE vessel_type_id = ?
                """,
                (vessel_type_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            return VesselType(
                vessel_type_id=row["vessel_type_id"],
                display_name=row["display_name"],
                category=row["category"],
                surface_area_cm2=row["surface_area_cm2"],
                working_volume_ml=row["working_volume_ml"],
                max_volume_ml=row["max_volume_ml"],
                well_count=row["well_count"],
                max_capacity_cells_per_well=row["max_capacity_cells_per_well"],
                description=row["description"]
            )

    def get_seeding_density(
        self,
        cell_line_id: str,
        vessel_type_id: str
    ) -> Optional[SeedingDensity]:
        """
        Get seeding density for a cell line in a specific vessel type.

        Args:
            cell_line_id: Cell line identifier (e.g., "A549", "HepG2")
            vessel_type_id: Vessel type identifier (e.g., "384-well", "T75")

        Returns:
            SeedingDensity object or None if not found

        Example:
            >>> repo = SeedingDensityRepository()
            >>> density = repo.get_seeding_density("A549", "384-well")
            >>> cells_nominal = density.get_cells("NOMINAL")  # 3000
            >>> cells_high = density.get_cells("HIGH")  # 3900
        """
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT cell_line_id, vessel_type_id, nominal_cells_per_well,
                       low_multiplier, high_multiplier, notes
                FROM seeding_densities
                WHERE cell_line_id = ? AND vessel_type_id = ?
                """,
                (cell_line_id, vessel_type_id)
            )
            row = cursor.fetchone()
            if not row:
                return None

            return SeedingDensity(
                cell_line_id=row["cell_line_id"],
                vessel_type_id=row["vessel_type_id"],
                nominal_cells_per_well=row["nominal_cells_per_well"],
                low_multiplier=row["low_multiplier"],
                high_multiplier=row["high_multiplier"],
                notes=row["notes"]
            )

    def get_cells_to_seed(
        self,
        cell_line_id: str,
        vessel_type_id: str,
        density_level: str = "NOMINAL"
    ) -> int:
        """
        Convenience method to directly get the number of cells to seed.

        Args:
            cell_line_id: Cell line identifier
            vessel_type_id: Vessel type identifier
            density_level: One of "LOW", "NOMINAL", "HIGH"

        Returns:
            Number of cells to seed

        Raises:
            ValueError: If cell line or vessel type not found

        Example:
            >>> repo = SeedingDensityRepository()
            >>> cells = repo.get_cells_to_seed("A549", "384-well", "NOMINAL")
            >>> print(cells)  # 3000
        """
        density = self.get_seeding_density(cell_line_id, vessel_type_id)
        if not density:
            # Try to provide helpful error message
            vessel = self.get_vessel_type(vessel_type_id)
            if not vessel:
                raise ValueError(
                    f"Unknown vessel type: {vessel_type_id}. "
                    f"Available: {', '.join(self.list_vessel_types())}"
                )
            raise ValueError(
                f"No seeding density configured for {cell_line_id} in {vessel_type_id}. "
                f"Please add entry to seeding_densities table."
            )

        return density.get_cells(density_level)

    def list_vessel_types(self, category: Optional[str] = None) -> List[str]:
        """
        List all vessel type IDs.

        Args:
            category: Optional filter by category ('plate', 'flask', etc.)

        Returns:
            List of vessel type IDs
        """
        with self._connect() as conn:
            if category:
                cursor = conn.execute(
                    "SELECT vessel_type_id FROM vessel_types WHERE category = ? ORDER BY surface_area_cm2",
                    (category,)
                )
            else:
                cursor = conn.execute(
                    "SELECT vessel_type_id FROM vessel_types ORDER BY surface_area_cm2"
                )
            return [row["vessel_type_id"] for row in cursor.fetchall()]

    def list_cell_lines_for_vessel(self, vessel_type_id: str) -> List[str]:
        """
        List all cell lines that have seeding densities configured for a vessel type.

        Args:
            vessel_type_id: Vessel type identifier

        Returns:
            List of cell line IDs
        """
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT cell_line_id FROM seeding_densities WHERE vessel_type_id = ? ORDER BY cell_line_id",
                (vessel_type_id,)
            )
            return [row["cell_line_id"] for row in cursor.fetchall()]

    def get_all_for_cell_line(self, cell_line_id: str) -> List[Dict[str, Any]]:
        """
        Get all seeding densities for a cell line across all vessel types.

        Args:
            cell_line_id: Cell line identifier

        Returns:
            List of dictionaries with vessel type info and seeding densities
        """
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT vt.vessel_type_id, vt.display_name, vt.category,
                       vt.surface_area_cm2, vt.well_count,
                       sd.nominal_cells_per_well, sd.low_multiplier, sd.high_multiplier
                FROM seeding_densities sd
                JOIN vessel_types vt ON sd.vessel_type_id = vt.vessel_type_id
                WHERE sd.cell_line_id = ?
                ORDER BY vt.surface_area_cm2
                """,
                (cell_line_id,)
            )
            results = []
            for row in cursor.fetchall():
                results.append({
                    "vessel_type_id": row["vessel_type_id"],
                    "display_name": row["display_name"],
                    "category": row["category"],
                    "surface_area_cm2": row["surface_area_cm2"],
                    "well_count": row["well_count"],
                    "nominal_cells": row["nominal_cells_per_well"],
                    "low_cells": int(row["nominal_cells_per_well"] * row["low_multiplier"]),
                    "high_cells": int(row["nominal_cells_per_well"] * row["high_multiplier"])
                })
            return results


# Global singleton instance
_REPO_INSTANCE: Optional[SeedingDensityRepository] = None


def get_repository(db_path: str = "data/cell_lines.db") -> SeedingDensityRepository:
    """
    Get or create singleton repository instance.

    Args:
        db_path: Path to database

    Returns:
        SeedingDensityRepository instance
    """
    global _REPO_INSTANCE
    if _REPO_INSTANCE is None:
        _REPO_INSTANCE = SeedingDensityRepository(db_path)
    return _REPO_INSTANCE


# Convenience function for most common use case
def get_cells_to_seed(
    cell_line_id: str,
    vessel_type_id: str,
    density_level: str = "NOMINAL",
    db_path: str = "data/cell_lines.db"
) -> int:
    """
    Quick lookup of cells to seed (convenience function).

    Args:
        cell_line_id: Cell line identifier (e.g., "A549")
        vessel_type_id: Vessel type identifier (e.g., "384-well")
        density_level: One of "LOW", "NOMINAL", "HIGH"
        db_path: Path to database

    Returns:
        Number of cells to seed

    Example:
        >>> from cell_os.database.repositories.seeding_density import get_cells_to_seed
        >>> cells = get_cells_to_seed("A549", "384-well", "NOMINAL")
        >>> print(cells)  # 3000
    """
    repo = get_repository(db_path)
    return repo.get_cells_to_seed(cell_line_id, vessel_type_id, density_level)
