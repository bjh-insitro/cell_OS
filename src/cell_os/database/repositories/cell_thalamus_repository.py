"""
Cell Thalamus Repository - provides baseline morphology data.

This is a stub repository that provides hardcoded baseline values.
In production, these would come from a database.
"""

import logging

logger = logging.getLogger(__name__)

# Baseline morphology values per cell line (channel intensities)
BASELINE_MORPHOLOGY = {
    'A549': {'er': 100.0, 'mito': 150.0, 'nucleus': 200.0, 'actin': 120.0, 'rna': 180.0},
    'HepG2': {'er': 95.0, 'mito': 140.0, 'nucleus': 190.0, 'actin': 115.0, 'rna': 170.0},
    'HEK293T': {'er': 90.0, 'mito': 135.0, 'nucleus': 185.0, 'actin': 110.0, 'rna': 165.0},
    'U2OS': {'er': 105.0, 'mito': 155.0, 'nucleus': 205.0, 'actin': 125.0, 'rna': 185.0},
}


class CellThalamusRepository:
    """Repository for cell thalamus parameters (baseline morphology)."""

    def get_baseline_morphology(self, cell_line: str) -> dict:
        """
        Get baseline morphology values for a cell line.

        Args:
            cell_line: Cell line name (e.g., 'A549', 'HepG2')

        Returns:
            Dict of channel -> baseline intensity, or None if not found
        """
        if cell_line in BASELINE_MORPHOLOGY:
            return BASELINE_MORPHOLOGY[cell_line].copy()

        # Try case-insensitive match
        for name, baseline in BASELINE_MORPHOLOGY.items():
            if name.lower() == cell_line.lower():
                return baseline.copy()

        logger.warning(f"No baseline morphology for cell line '{cell_line}'")
        return None
