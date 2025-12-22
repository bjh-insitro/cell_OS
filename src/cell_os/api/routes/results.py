"""
Results Routes

Endpoints for retrieving experimental results and data visualizations.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
import numpy as np
from sklearn.decomposition import PCA

from cell_os.database.cell_thalamus_db import CellThalamusDB

logger = logging.getLogger(__name__)

router = APIRouter()

# These will be injected from main app
DB_PATH: str = ""


def init_globals(db_path):
    """Initialize global state from main app"""
    global DB_PATH
    DB_PATH = db_path


@router.get("/api/thalamus/designs/{design_id}/results")
async def get_results(design_id: str):
    """Get all results for a design"""
    try:
        db = CellThalamusDB(db_path=DB_PATH)
        results = db.get_results(design_id)
        db.close()

        if not results:
            raise HTTPException(status_code=404, detail="No results found")

        return results

    except Exception as e:
        logger.error(f"Error getting results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/thalamus/designs/{design_id}/morphology")
async def get_morphology_matrix(design_id: str):
    """Get morphology matrix for PCA visualization"""
    try:
        db = CellThalamusDB(db_path=DB_PATH)
        matrix, well_ids = db.get_morphology_matrix(design_id)
        db.close()

        if not matrix:
            raise HTTPException(status_code=404, detail="No morphology data found")

        return {
            "matrix": matrix,
            "well_ids": well_ids,
            "channels": ["ER", "Mito", "Nucleus", "Actin", "RNA"]
        }

    except Exception as e:
        logger.error(f"Error getting morphology: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/thalamus/designs/{design_id}/pca")
async def get_pca_data(design_id: str, channels: Optional[str] = None):
    """
    Compute real PCA on morphology data with optional channel selection.

    Args:
        design_id: Design ID
        channels: Comma-separated channel names (e.g., "er,mito,rna"). Defaults to all 5.

    Returns:
        PC scores, loadings, variance explained, and well metadata
    """
    try:
        db = CellThalamusDB(db_path=DB_PATH)
        results = db.get_results(design_id)

        if not results:
            db.close()
            raise HTTPException(status_code=404, detail="No results found")

        # All available channels in order
        all_channels = ['er', 'mito', 'nucleus', 'actin', 'rna']
        channel_map = {
            'er': 'morph_er',
            'mito': 'morph_mito',
            'nucleus': 'morph_nucleus',
            'actin': 'morph_actin',
            'rna': 'morph_rna'
        }

        # Parse selected channels
        if channels:
            selected_channels = [c.strip().lower() for c in channels.split(',')]
            # Validate channels
            selected_channels = [c for c in selected_channels if c in all_channels]
            if not selected_channels:
                selected_channels = all_channels
        else:
            selected_channels = all_channels

        # Extract morphology matrix for selected channels
        matrix = []
        well_metadata = []

        for result in results:
            # Get values for selected channels
            values = [result[channel_map[ch]] for ch in selected_channels]

            # Skip if any values are None
            if None in values:
                continue

            matrix.append(values)
            well_metadata.append({
                'well_id': result['well_id'],
                'cell_line': result['cell_line'],
                'compound': result['compound'],
                'dose_uM': result['dose_uM'],
                'timepoint_h': result['timepoint_h'],
                'is_sentinel': result['is_sentinel']
            })

        db.close()

        if len(matrix) < 2:
            raise HTTPException(status_code=400, detail="Not enough data points for PCA")

        # Convert to numpy array
        X = np.array(matrix, dtype=float)

        # Compute PCA (2 components)
        pca = PCA(n_components=2)
        pc_scores = pca.fit_transform(X)

        # Get loadings (eigenvectors)
        loadings = pca.components_.T  # Shape: (n_channels, 2)

        # Variance explained
        variance_explained = pca.explained_variance_ratio_

        return {
            'pc_scores': pc_scores.tolist(),  # List of [PC1, PC2] for each well
            'loadings': loadings.tolist(),    # List of [PC1_loading, PC2_loading] for each channel
            'variance_explained': {
                'pc1': float(variance_explained[0]),
                'pc2': float(variance_explained[1]),
                'total': float(variance_explained[0] + variance_explained[1])
            },
            'channels': selected_channels,
            'well_metadata': well_metadata,
            'n_wells': len(well_metadata)
        }

    except Exception as e:
        logger.error(f"Error computing PCA: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/thalamus/designs/{design_id}/dose-response")
async def get_dose_response(design_id: str, compound: str, cell_line: str, metric: str = "atp_signal", timepoint: Optional[float] = None):
    """Get dose-response data for a specific compound/cell line with error bars"""
    try:
        db = CellThalamusDB(db_path=DB_PATH)
        data = db.get_dose_response_data(design_id, compound, cell_line, metric, timepoint)
        db.close()

        if not data:
            raise HTTPException(status_code=404, detail="No dose-response data found")

        # Convert to dict format with mean, std, n
        return {
            "doses": [d[0] for d in data],
            "values": [d[1] for d in data],  # mean
            "std": [d[2] for d in data],     # standard deviation
            "n": [d[3] for d in data],       # sample size
            "compound": compound,
            "cell_line": cell_line,
            "metric": metric
        }

    except Exception as e:
        logger.error(f"Error getting dose-response: {e}")
        raise HTTPException(status_code=500, detail=str(e))
