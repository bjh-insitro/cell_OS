"""
Catalog Routes

Endpoints for design catalog and custom design generation.
"""

import logging
import json
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException

from ..models import DesignGeneratorRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/thalamus/catalog")
async def get_design_catalog():
    """Get the design catalog with all versions and evolution history"""
    try:
        catalog_path = Path(__file__).parent.parent.parent.parent.parent / "data" / "designs" / "catalog.json"

        if not catalog_path.exists():
            raise HTTPException(status_code=404, detail="Catalog not found")

        with open(catalog_path, 'r') as f:
            catalog = json.load(f)

        return catalog

    except Exception as e:
        logger.error(f"Error getting design catalog: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/thalamus/catalog/designs/{design_id}")
async def get_catalog_design(design_id: str):
    """Get full design file from catalog"""
    try:
        designs_dir = Path(__file__).parent.parent.parent.parent.parent / "data" / "designs"
        catalog_path = designs_dir / "catalog.json"

        if not catalog_path.exists():
            raise HTTPException(status_code=404, detail="Catalog not found")

        # Load catalog to get filename
        with open(catalog_path, 'r') as f:
            catalog = json.load(f)

        # Find design in catalog
        design_entry = None
        for design in catalog['designs']:
            if design['design_id'] == design_id:
                design_entry = design
                break

        if not design_entry:
            raise HTTPException(status_code=404, detail=f"Design {design_id} not found in catalog")

        # Load full design file
        design_file = designs_dir / design_entry['filename']
        if not design_file.exists():
            raise HTTPException(status_code=404, detail=f"Design file {design_entry['filename']} not found")

        with open(design_file, 'r') as f:
            design_data = json.load(f)

        return {
            "catalog_entry": design_entry,
            "design_data": design_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting catalog design: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/thalamus/generate-design")
async def generate_design(request: DesignGeneratorRequest):
    """Generate a custom experimental design using DesignGenerator"""
    try:
        # Import DesignGenerator from scripts
        scripts_path = str(Path(__file__).parent.parent.parent.parent.parent / "scripts")
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)

        from design_catalog import DesignGenerator

        # Initialize generator
        generator = DesignGenerator()

        # Convert request to kwargs
        kwargs = {
            'design_id': request.design_id,
            'description': request.description,
        }

        # Add optional parameters
        if request.cell_lines is not None:
            kwargs['cell_lines'] = request.cell_lines
        if request.compounds is not None:
            kwargs['compounds'] = request.compounds
        if request.dose_multipliers is not None:
            kwargs['dose_multipliers'] = request.dose_multipliers
        if request.days is not None:
            kwargs['days'] = request.days
        if request.operators is not None:
            kwargs['operators'] = request.operators
        if request.timepoints_h is not None:
            kwargs['timepoints_h'] = request.timepoints_h
        if request.sentinel_config is not None:
            kwargs['sentinel_config'] = request.sentinel_config

        kwargs['replicates_per_dose'] = request.replicates_per_dose
        kwargs['plate_format'] = request.plate_format
        kwargs['checkerboard'] = request.checkerboard
        kwargs['exclude_corners'] = request.exclude_corners
        kwargs['exclude_edges'] = request.exclude_edges

        # Generate design
        logger.info(f"Generating design: {request.design_id}")
        design = generator.create_design(**kwargs)

        logger.info(f"Design generated successfully: {request.design_id} ({design['metadata']['total_wells']} wells)")

        return design

    except ValueError as e:
        # Design validation errors (not enough wells, etc.)
        logger.error(f"Design validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating design: {e}")
        raise HTTPException(status_code=500, detail=str(e))
